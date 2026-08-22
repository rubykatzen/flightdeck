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

NETWORKS_YML = """\
networks:
  internal:
  databases:
    external: true
  mcp:
    external: true
  traefik:
    external: true
"""


def make_zip(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


class ValidateConfigTest(unittest.TestCase):
    VALID = {
        "hosts": ["user@host"],
        "app_refs": ["owner/repo@latest"],
        "apps": {"traefik": {"env_refs": ["owner/repo@latest:a.sops.env"]}},
        "sops_age_key": "AGE-SECRET-KEY-1...",
    }

    def test_accepts_valid_config(self):
        deploy.validate_config(self.VALID)  # does not raise

    def test_rejects_missing_hosts(self):
        with self.assertRaises(deploy.DeployError):
            deploy.validate_config({**self.VALID, "hosts": []})

    def test_rejects_missing_app_refs(self):
        with self.assertRaises(deploy.DeployError):
            deploy.validate_config({**self.VALID, "app_refs": []})

    def test_rejects_missing_apps(self):
        with self.assertRaises(deploy.DeployError):
            deploy.validate_config({**self.VALID, "apps": {}})

    def test_rejects_missing_sops_age_key(self):
        with self.assertRaises(deploy.DeployError):
            deploy.validate_config({**self.VALID, "sops_age_key": ""})


class ExpandHomeTest(unittest.TestCase):
    def test_expands_tilde_prefix(self):
        self.assertEqual(deploy.expand_home("~/flightdeck", "/home/deploy"), "/home/deploy/flightdeck")

    def test_leaves_absolute_path_untouched(self):
        self.assertEqual(deploy.expand_home("/opt/flightdeck", "/home/deploy"), "/opt/flightdeck")


class BuildReleaseTest(unittest.TestCase):
    def test_merges_app_dirs_and_shared_top_level_files(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            apps_zip = make_zip(
                work_dir / "src" / "flightdeck-apps.zip",
                {
                    "apps/common.yml": "services: {}\n",
                    "apps/networks.yml": NETWORKS_YML,
                    "apps/traefik/docker-compose.yml": "traefik: {}\n",
                    "apps/rybbit/docker-compose.yml": "rybbit: {}\n",
                },
            )

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                return apps_zip

            config = {"app_refs": ["owner/repo@latest:apps.zip"]}
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref):
                release_dir = deploy.build_release(config, work_dir / "work")

            self.assertTrue((release_dir / "apps" / "common.yml").is_file())
            self.assertTrue((release_dir / "apps" / "networks.yml").is_file())
            self.assertTrue((release_dir / "apps" / "traefik" / "docker-compose.yml").is_file())
            self.assertTrue((release_dir / "apps" / "rybbit" / "docker-compose.yml").is_file())

    def test_raises_on_app_dir_conflict_across_bundles(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            first_zip = make_zip(work_dir / "src" / "a.zip", {"apps/traefik/docker-compose.yml": "a: {}\n"})
            second_zip = make_zip(work_dir / "src" / "b.zip", {"apps/traefik/docker-compose.yml": "b: {}\n"})
            zips = {"a.zip": first_zip, "b.zip": second_zip}

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                return zips["a.zip"] if "a.zip" in ref else zips["b.zip"]

            config = {"app_refs": ["owner/repo@latest:a.zip", "owner/repo@latest:b.zip"]}
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref), self.assertRaises(deploy.DeployError):
                deploy.build_release(config, work_dir / "work")

    def test_raises_on_shared_file_conflict_across_bundles(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            first_zip = make_zip(work_dir / "src" / "a.zip", {"apps/common.yml": "a: {}\n"})
            second_zip = make_zip(work_dir / "src" / "b.zip", {"apps/common.yml": "b: {}\n"})
            zips = {"a.zip": first_zip, "b.zip": second_zip}

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                return zips["a.zip"] if "a.zip" in ref else zips["b.zip"]

            config = {"app_refs": ["owner/repo@latest:a.zip", "owner/repo@latest:b.zip"]}
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref), self.assertRaises(deploy.DeployError):
                deploy.build_release(config, work_dir / "work")

    def test_raises_when_bundle_has_no_apps_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            empty_zip = make_zip(work_dir / "src" / "empty.zip", {"README.md": "n/a\n"})

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                return empty_zip

            config = {"app_refs": ["owner/repo@latest:empty.zip"]}
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref), self.assertRaises(deploy.DeployError):
                deploy.build_release(config, work_dir / "work")


class RenderAppConfigsTest(unittest.TestCase):
    def test_renders_templates_found_for_app_next_to_the_template(self):
        with tempfile.TemporaryDirectory() as directory:
            release_dir = Path(directory)
            app_dir = release_dir / "apps" / "traefik"
            app_dir.mkdir(parents=True)
            (app_dir / "traefik.yml.tpl").write_text("email: ${APPS_ADMIN_MAIL}\n")

            deploy.render_app_configs(release_dir, "traefik", {"APPS_ADMIN_MAIL": "a@example.com"})

            rendered_path = app_dir / "traefik.yml"
            self.assertEqual(rendered_path.read_text(), "email: a@example.com\n")
            self.assertEqual(oct(rendered_path.stat().st_mode)[-3:], "600")

    def test_does_nothing_when_app_has_no_templates(self):
        with tempfile.TemporaryDirectory() as directory:
            release_dir = Path(directory)
            (release_dir / "apps" / "rybbit").mkdir(parents=True)

            deploy.render_app_configs(release_dir, "rybbit", {})  # does not raise

            self.assertEqual(list((release_dir / "apps" / "rybbit").iterdir()), [])


class ResolveAppEnvsTest(unittest.TestCase):
    def _release_dir_with_app(self, work_dir, app, template=None):
        app_dir = work_dir / "release" / "apps" / app
        app_dir.mkdir(parents=True)
        if template is not None:
            (app_dir / f"{app}.yml.tpl").write_text(template)
        return work_dir / "release"

    def test_writes_decrypted_env_and_renders_configs(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            release_dir = self._release_dir_with_app(work_dir, "traefik", template="email: ${APPS_ADMIN_MAIL}\n")
            ciphertext = work_dir / "a.sops.env"
            ciphertext.write_text("APPS_ADMIN_MAIL=ENC[...]\n")

            config = {"apps": {"traefik": {"env_refs": ["owner/repo@latest:a.sops.env"]}}}

            with (
                patch.object(deploy, "download_ref", return_value=ciphertext),
                patch.object(deploy, "decrypt_env", return_value="APPS_ADMIN_MAIL=a@example.com\n"),
            ):
                deploy.resolve_app_envs(config, work_dir / "work", release_dir, work_dir / "key.txt")

            env_path = release_dir / "apps" / "traefik" / ".env"
            self.assertEqual(env_path.read_text(), "APPS_ADMIN_MAIL=a@example.com\n")
            self.assertEqual(oct(env_path.stat().st_mode)[-3:], "600")

            rendered_path = release_dir / "apps" / "traefik" / "traefik.yml"
            self.assertEqual(rendered_path.read_text(), "email: a@example.com\n")

    def test_raises_on_collision_within_one_apps_own_env_refs(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            release_dir = self._release_dir_with_app(work_dir, "traefik")
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
                deploy.resolve_app_envs(config, work_dir / "work", release_dir, work_dir / "key.txt")

    def test_allows_same_key_across_different_apps(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            release_dir = self._release_dir_with_app(work_dir, "traefik")
            self._release_dir_with_app(work_dir, "rybbit")
            traefik_env = work_dir / "a.sops.env"
            traefik_env.write_text("APPS_DOMAIN=ENC[AES256_GCM,data:Ab==,iv:xx==,tag:yy==,type:str]\n")
            rybbit_env = work_dir / "b.sops.env"
            rybbit_env.write_text("APPS_DOMAIN=ENC[AES256_GCM,data:Cd==,iv:xx==,tag:yy==,type:str]\n")

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                return traefik_env if "traefik" in ref else rybbit_env

            def fake_decrypt_env(path, age_key_file, run=None):
                return "APPS_DOMAIN=example.com\n"

            config = {
                "apps": {
                    "traefik": {"env_refs": ["owner/repo@latest:hawkeye-traefik.sops.env"]},
                    "rybbit": {"env_refs": ["owner/repo@latest:hawkeye-rybbit.sops.env"]},
                }
            }
            with (
                patch.object(deploy, "download_ref", side_effect=fake_download_ref),
                patch.object(deploy, "decrypt_env", side_effect=fake_decrypt_env),
            ):
                deploy.resolve_app_envs(config, work_dir / "work", release_dir, work_dir / "key.txt")  # does not raise


class ListRequiredNetworksTest(unittest.TestCase):
    def test_returns_only_external_networks(self):
        with tempfile.TemporaryDirectory() as directory:
            release_dir = Path(directory)
            apps_dir = release_dir / "apps"
            apps_dir.mkdir()
            (apps_dir / "networks.yml").write_text(NETWORKS_YML)

            networks = deploy.list_required_networks(release_dir)

            self.assertEqual(sorted(networks), ["databases", "mcp", "traefik"])
            self.assertNotIn("internal", networks)


class ArchiveReleaseTest(unittest.TestCase):
    def test_archives_release_contents_without_wrapper_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            release_dir = work_dir / "release"
            (release_dir / "apps" / "traefik").mkdir(parents=True)
            (release_dir / "apps" / "common.yml").write_text("services: {}\n")
            (release_dir / "apps" / "traefik" / "docker-compose.yml").write_text("traefik: {}\n")

            archive_path = deploy.archive_release(release_dir, work_dir)

            with tarfile.open(archive_path) as tar:
                names = set(tar.getnames())
            self.assertIn("apps/common.yml", names)
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
    def test_full_sequence(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            archive_path = work_dir / "release.tar.gz"
            archive_path.write_text("fake archive\n")
            config = {"hosts": ["deploy@host"], "keep_releases": 5}

            fake = FakeConnection("deploy@host")
            with patch.object(deploy, "Connection", return_value=fake):
                deploy.deploy_to_host(
                    "deploy@host",
                    archive_path,
                    apps=["traefik", "rybbit"],
                    networks=["traefik", "databases", "mcp"],
                    config=config,
                )

            self.assertEqual(fake.uploads[0], (str(archive_path), fake.uploads[0][1]))
            self.assertTrue(fake.uploads[0][1].endswith(".tar.gz"))
            self.assertEqual(len(fake.uploads), 1)

            joined = "\n".join(fake.commands)
            self.assertIn("docker network create traefik", joined)
            self.assertIn("docker network create databases", joined)
            self.assertIn("docker network create mcp", joined)
            self.assertIn("acme.json", joined)
            self.assertIn("tar -xzf", joined)
            self.assertIn("mkdir -p /home/deploy/flightdeck/apps-data/traefik", joined)
            self.assertIn("mkdir -p /home/deploy/flightdeck/apps-data/rybbit", joined)
            self.assertIn("ln -sfn", joined)
            self.assertIn("apps/rybbit && docker compose pull && docker compose up -d --remove-orphans", joined)
            self.assertIn("apps/traefik && docker compose pull && docker compose up -d --remove-orphans", joined)

            prune_command = next(command for command in fake.commands if command.startswith("rm -rf") and "rel" in command)
            for stale in ("rel5", "rel6"):
                self.assertIn(stale, prune_command)
            for kept in ("rel0", "rel1", "rel2", "rel3", "rel4"):
                self.assertNotIn(kept, prune_command)


if __name__ == "__main__":
    unittest.main()
