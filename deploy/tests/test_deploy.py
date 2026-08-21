import importlib.util
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

DEPLOY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEPLOY_DIR))

MODULE_PATH = DEPLOY_DIR / "deploy.py"
SPEC = importlib.util.spec_from_file_location("deploy_entrypoint", MODULE_PATH)
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)

# deploy.py's own `from collisions import ...` performs a real sys.path
# import, registering the canonical module here - reuse it so exception
# identity matches what deploy.py actually raises.
collisions = sys.modules["collisions"]


def make_zip(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


class ValidateConfigTest(unittest.TestCase):
    VALID = {
        "hosts": ["user@host"],
        "app_ref": "owner/repo@latest",
        "app_refs": ["owner/repo@latest"],
        "apps": {"traefik": {"env_refs": ["owner/repo@latest:a.sops.env"]}},
    }

    def test_accepts_valid_config(self):
        deploy.validate_config(self.VALID)  # does not raise

    def test_rejects_missing_hosts(self):
        with self.assertRaises(deploy.DeployError):
            deploy.validate_config({**self.VALID, "hosts": []})

    def test_rejects_missing_app_ref(self):
        with self.assertRaises(deploy.DeployError):
            deploy.validate_config({**self.VALID, "app_ref": ""})

    def test_rejects_missing_app_refs(self):
        with self.assertRaises(deploy.DeployError):
            deploy.validate_config({**self.VALID, "app_refs": []})

    def test_rejects_missing_apps(self):
        with self.assertRaises(deploy.DeployError):
            deploy.validate_config({**self.VALID, "apps": {}})


class ExpandHomeTest(unittest.TestCase):
    def test_expands_tilde_prefix(self):
        self.assertEqual(deploy.expand_home("~/flightdeck", "/home/deploy"), "/home/deploy/flightdeck")

    def test_leaves_absolute_path_untouched(self):
        self.assertEqual(deploy.expand_home("/opt/flightdeck", "/home/deploy"), "/opt/flightdeck")


class BuildReleaseTest(unittest.TestCase):
    def test_merges_app_bundles_into_release(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            machinery_zip = make_zip(work_dir / "src" / "flightdeck.zip", {"up.sh": "#!/bin/bash\n"})
            apps_zip = make_zip(
                work_dir / "src" / "flightdeck-apps.zip",
                {
                    "apps/traefik/docker-compose.yml": "traefik: {}\n",
                    "apps/rybbit/docker-compose.yml": "rybbit: {}\n",
                },
            )

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                return machinery_zip if default_asset == deploy.MACHINERY_ASSET else apps_zip

            config = {"app_ref": "owner/repo@latest", "app_refs": ["owner/repo@latest:apps.zip"]}
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref):
                release_dir = deploy.build_release(config, work_dir / "work")

            self.assertTrue((release_dir / "up.sh").is_file())
            self.assertTrue((release_dir / "apps" / "traefik" / "docker-compose.yml").is_file())
            self.assertTrue((release_dir / "apps" / "rybbit" / "docker-compose.yml").is_file())

    def test_raises_on_app_conflict_across_bundles(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            machinery_zip = make_zip(work_dir / "src" / "flightdeck.zip", {"up.sh": "#!/bin/bash\n"})
            apps_zip = make_zip(
                work_dir / "src" / "flightdeck-apps.zip",
                {"apps/traefik/docker-compose.yml": "traefik: {}\n"},
            )

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                return machinery_zip if default_asset == deploy.MACHINERY_ASSET else apps_zip

            config = {
                "app_ref": "owner/repo@latest",
                "app_refs": ["owner/repo@latest:a.zip", "owner/repo@latest:b.zip"],
            }
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref), self.assertRaises(deploy.DeployError):
                deploy.build_release(config, work_dir / "work")

    def test_raises_when_bundle_has_no_apps_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            machinery_zip = make_zip(work_dir / "src" / "flightdeck.zip", {"up.sh": "#!/bin/bash\n"})
            empty_zip = make_zip(work_dir / "src" / "empty.zip", {"README.md": "n/a\n"})

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                return machinery_zip if default_asset == deploy.MACHINERY_ASSET else empty_zip

            config = {"app_ref": "owner/repo@latest", "app_refs": ["owner/repo@latest:empty.zip"]}
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref), self.assertRaises(deploy.DeployError):
                deploy.build_release(config, work_dir / "work")


class ResolveAppEnvsTest(unittest.TestCase):
    def test_collects_paths_per_app(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            traefik_env = work_dir / "traefik.sops.env"
            traefik_env.write_text("HTTP_PORT=ENC[AES256_GCM,data:Ab==,iv:xx==,tag:yy==,type:str]\n")
            rybbit_env = work_dir / "rybbit.sops.env"
            rybbit_env.write_text("APPS_KEY_HEX_32=ENC[AES256_GCM,data:Cd==,iv:xx==,tag:yy==,type:str]\n")

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                return traefik_env if "traefik" in ref else rybbit_env

            config = {
                "apps": {
                    "traefik": {"env_refs": ["owner/repo@latest:hawkeye-traefik.sops.env"]},
                    "rybbit": {"env_refs": ["owner/repo@latest:hawkeye-rybbit.sops.env"]},
                }
            }
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref):
                app_envs = deploy.resolve_app_envs(config, work_dir / "work")

            self.assertEqual(app_envs, {"traefik": [traefik_env], "rybbit": [rybbit_env]})

    def test_allows_same_key_across_different_apps(self):
        # Each app gets its own separate .env, so two apps' vaults sharing a
        # key (e.g. both declaring APPS_DOMAIN) is not a collision - only
        # multiple env_refs feeding the *same* app are checked against
        # each other.
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            traefik_env = work_dir / "a.sops.env"
            traefik_env.write_text("APPS_DOMAIN=ENC[AES256_GCM,data:Ab==,iv:xx==,tag:yy==,type:str]\n")
            rybbit_env = work_dir / "b.sops.env"
            rybbit_env.write_text("APPS_DOMAIN=ENC[AES256_GCM,data:Cd==,iv:xx==,tag:yy==,type:str]\n")

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                return traefik_env if "traefik" in ref else rybbit_env

            config = {
                "apps": {
                    "traefik": {"env_refs": ["owner/repo@latest:hawkeye-traefik.sops.env"]},
                    "rybbit": {"env_refs": ["owner/repo@latest:hawkeye-rybbit.sops.env"]},
                }
            }
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref):
                app_envs = deploy.resolve_app_envs(config, work_dir / "work")  # does not raise

            self.assertEqual(app_envs, {"traefik": [traefik_env], "rybbit": [rybbit_env]})

    def test_raises_on_collision_within_one_apps_own_env_refs(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            first_env = work_dir / "a.sops.env"
            first_env.write_text("APPS_DOMAIN=ENC[AES256_GCM,data:Ab==,iv:xx==,tag:yy==,type:str]\n")
            second_env = work_dir / "b.sops.env"
            second_env.write_text("APPS_DOMAIN=ENC[AES256_GCM,data:Cd==,iv:xx==,tag:yy==,type:str]\n")

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                return first_env if ref.endswith(":a.sops.env") else second_env

            config = {
                "apps": {
                    "traefik": {
                        "env_refs": [
                            "owner/repo@latest:a.sops.env",
                            "owner/repo@latest:b.sops.env",
                        ]
                    },
                }
            }
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref), self.assertRaises(collisions.CollisionError):
                deploy.resolve_app_envs(config, work_dir / "work")


class ArchiveReleaseTest(unittest.TestCase):
    def test_archives_release_contents_without_wrapper_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            release_dir = work_dir / "release"
            (release_dir / "apps" / "traefik").mkdir(parents=True)
            (release_dir / "up.sh").write_text("#!/bin/bash\n")
            (release_dir / "apps" / "traefik" / "docker-compose.yml").write_text("traefik: {}\n")

            archive_path = deploy.archive_release(release_dir, work_dir)

            with tarfile.open(archive_path) as tar:
                names = set(tar.getnames())
            self.assertIn("up.sh", names)
            self.assertIn("apps/traefik/docker-compose.yml", names)


class FakeConnection:
    """Stand-in for fabric.Connection - records commands/uploads instead of
    opening a real SSH session, so deploy_to_host's command sequence can be
    verified without a local sshd."""

    def __init__(self, host):
        self.host = host
        self.client = SimpleNamespace(set_missing_host_key_policy=lambda policy: None)
        self.commands = []
        self.uploads = []

    def run(self, command, hide=False):
        self.commands.append(command)
        if command == "echo $HOME":
            return SimpleNamespace(stdout="/home/deploy\n")
        if command.startswith("ls -1dt"):
            releases = "\n".join(f"/home/deploy/flightdeck/releases/rel{i}/" for i in range(7))
            return SimpleNamespace(stdout=releases + "\n")
        return SimpleNamespace(stdout="")

    def put(self, local, remote):
        self.uploads.append((local, remote))


class DeployToHostTest(unittest.TestCase):
    def test_pushes_release_and_app_envs_then_deploys_and_prunes(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            archive_path = work_dir / "release.tar.gz"
            archive_path.write_text("fake archive\n")
            traefik_env = work_dir / "traefik.sops.env"
            traefik_env.write_text("HTTP_PORT=ENC[...]\n")
            app_envs = {"traefik": [traefik_env]}
            config = {"hosts": ["deploy@host"], "keep_releases": 5}

            fake = FakeConnection("deploy@host")
            with patch.object(deploy, "Connection", return_value=fake):
                deploy.deploy_to_host("deploy@host", archive_path, app_envs, config)

            self.assertEqual(fake.uploads[0], (str(archive_path), fake.uploads[0][1]))
            self.assertTrue(fake.uploads[0][1].endswith(".tar.gz"))
            self.assertEqual(fake.uploads[1], (str(traefik_env), fake.uploads[1][1]))

            joined = "\n".join(fake.commands)
            self.assertIn("tar -xzf", joined)
            self.assertIn("sops decrypt", joined)
            self.assertIn("ln -sfn", joined)
            self.assertIn("FLIGHTDECK_SKIP_ENV_GENERATION=1 ./deploy.sh traefik", joined)

            prune_command = next(command for command in fake.commands if command.startswith("rm -rf") and "rel" in command)
            for stale in ("rel5", "rel6"):
                self.assertIn(stale, prune_command)
            for kept in ("rel0", "rel1", "rel2", "rel3", "rel4"):
                self.assertNotIn(kept, prune_command)


if __name__ == "__main__":
    unittest.main()
