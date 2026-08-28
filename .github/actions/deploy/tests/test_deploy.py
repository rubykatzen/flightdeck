import importlib.util
import io
import json
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


class LoadTargetTest(unittest.TestCase):
    def test_parses_a_target_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "heimdall.yml"
            manifest_path.write_text(
                "hosts: [user@host]\napp_refs: [owner/repo@latest]\n"
                "apps:\n  traefik:\n    env_refs: [owner/repo@latest:a.sops.env]\n"
            )

            target = deploy.load_target(manifest_path)

            self.assertEqual(target["hosts"], ["user@host"])
            self.assertEqual(target["app_refs"], ["owner/repo@latest"])
            self.assertEqual(target["apps"]["traefik"]["env_refs"], ["owner/repo@latest:a.sops.env"])


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
                return apps_zip, "owner/repo@v1.0.0:apps.zip"

            config = {"app_refs": ["owner/repo@latest:apps.zip"]}
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref):
                release_dir, resolved_app_refs = deploy.build_release(config, work_dir / "work")

            self.assertEqual(resolved_app_refs, ["owner/repo@v1.0.0:apps.zip"])
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
                return (zips["a.zip"], "owner/repo@v1.0.0:a.zip") if "a.zip" in ref else (zips["b.zip"], "owner/repo@v1.0.0:b.zip")

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
                return (zips["a.zip"], "owner/repo@v1.0.0:a.zip") if "a.zip" in ref else (zips["b.zip"], "owner/repo@v1.0.0:b.zip")

            config = {"app_refs": ["owner/repo@latest:a.zip", "owner/repo@latest:b.zip"]}
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref), self.assertRaises(deploy.DeployError):
                deploy.build_release(config, work_dir / "work")

    def test_raises_when_bundle_has_no_apps_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            empty_zip = make_zip(work_dir / "src" / "empty.zip", {"README.md": "n/a\n"})

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                return empty_zip, "owner/repo@v1.0.0:empty.zip"

            config = {"app_refs": ["owner/repo@latest:empty.zip"]}
            with patch.object(deploy, "download_ref", side_effect=fake_download_ref), self.assertRaises(deploy.DeployError):
                deploy.build_release(config, work_dir / "work")


class RenderAppConfigsTest(unittest.TestCase):
    def test_renders_templates_found_for_app_next_to_the_template(self):
        with tempfile.TemporaryDirectory() as directory:
            release_dir = Path(directory)
            app_dir = release_dir / "apps" / "codecov"
            app_dir.mkdir(parents=True)
            (app_dir / "codecov.yml.tpl").write_text("email: ${ADMIN_MAIL}\n")

            deploy.render_app_configs(release_dir, "codecov", {"ADMIN_MAIL": "a@example.com"})

            rendered_path = app_dir / "codecov.yml"
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
            release_dir = self._release_dir_with_app(work_dir, "codecov", template="email: ${ADMIN_MAIL}\n")
            ciphertext = work_dir / "a.sops.env"
            ciphertext.write_text("ADMIN_MAIL=ENC[...]\n")

            config = {"apps": {"codecov": {"env_refs": ["owner/repo@latest:a.sops.env"]}}}

            with (
                patch.object(deploy, "download_ref", return_value=(ciphertext, "owner/repo@v1.0.0:a.sops.env")),
                patch.object(deploy, "decrypt_env", return_value="ADMIN_MAIL=a@example.com\n"),
            ):
                resolved_env_refs = deploy.resolve_app_envs(config, work_dir / "work", release_dir, work_dir / "key.txt")

            self.assertEqual(resolved_env_refs, {"codecov": ["owner/repo@v1.0.0:a.sops.env"]})

            env_path = release_dir / "apps" / "codecov" / ".env"
            self.assertEqual(env_path.read_text(), "APP_NAME=codecov\nADMIN_MAIL=a@example.com\n")
            self.assertEqual(oct(env_path.stat().st_mode)[-3:], "600")

            rendered_path = release_dir / "apps" / "codecov" / "codecov.yml"
            self.assertEqual(rendered_path.read_text(), "email: a@example.com\n")

    def test_app_without_env_refs_gets_no_vault_decrypted(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            release_dir = self._release_dir_with_app(work_dir, "beszel")

            config = {"apps": {"beszel": {}}}

            with (
                patch.object(deploy, "download_ref") as fake_download_ref,
                patch.object(deploy, "decrypt_env") as fake_decrypt_env,
            ):
                resolved_env_refs = deploy.resolve_app_envs(config, work_dir / "work", release_dir, work_dir / "key.txt")

            fake_download_ref.assert_not_called()
            fake_decrypt_env.assert_not_called()
            self.assertEqual(resolved_env_refs, {"beszel": []})

            env_path = release_dir / "apps" / "beszel" / ".env"
            self.assertEqual(env_path.read_text(), "APP_NAME=beszel\n")

    def test_raises_on_collision_within_one_apps_own_env_refs(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            release_dir = self._release_dir_with_app(work_dir, "traefik")
            first_env = work_dir / "a.sops.env"
            first_env.write_text("DOMAIN=ENC[AES256_GCM,data:Ab==,iv:xx==,tag:yy==,type:str]\n")
            second_env = work_dir / "b.sops.env"
            second_env.write_text("DOMAIN=ENC[AES256_GCM,data:Cd==,iv:xx==,tag:yy==,type:str]\n")

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                path = first_env if ref.endswith(":a.sops.env") else second_env
                return path, ref

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
            traefik_env.write_text("DOMAIN=ENC[AES256_GCM,data:Ab==,iv:xx==,tag:yy==,type:str]\n")
            rybbit_env = work_dir / "b.sops.env"
            rybbit_env.write_text("DOMAIN=ENC[AES256_GCM,data:Cd==,iv:xx==,tag:yy==,type:str]\n")

            def fake_download_ref(ref, out_dir, default_asset=None, run=None):
                path = traefik_env if "traefik" in ref else rybbit_env
                return path, ref

            def fake_decrypt_env(path, age_key_file, run=None):
                return "DOMAIN=example.com\n"

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


class WriteReleaseManifestTest(unittest.TestCase):
    def test_writes_manifest_with_sorted_apps(self):
        with tempfile.TemporaryDirectory() as directory:
            release_dir = Path(directory)

            deploy.write_release_manifest(
                release_dir,
                "20260824T211714Z",
                ["owner/repo@v0.8.0"],
                {
                    "traefik": ["owner/repo@v0.8.0:traefik.sops.env"],
                    "cloudflared": ["owner/repo@v0.8.0:cloudflared.sops.env"],
                },
            )

            manifest = json.loads((release_dir / "manifest.json").read_text())
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["release"], "20260824T211714Z")
            self.assertEqual(manifest["app_refs"], ["owner/repo@v0.8.0"])
            self.assertEqual(manifest["apps"], ["cloudflared", "traefik"])
            self.assertEqual(
                manifest["env_refs"],
                {
                    "traefik": ["owner/repo@v0.8.0:traefik.sops.env"],
                    "cloudflared": ["owner/repo@v0.8.0:cloudflared.sops.env"],
                },
            )
            self.assertNotIn("target", manifest)


class FakeConnection:
    """Stand-in for fabric.Connection - records commands/uploads instead of
    opening a real SSH session, so deploy_to_host's command sequence can be
    verified without a local sshd."""

    def __init__(self, host, previous_manifest=""):
        self.host = host
        self.client = SimpleNamespace(set_missing_host_key_policy=lambda policy: None)
        self.commands = []
        self.uploads = []
        self.previous_manifest = previous_manifest

    def run(self, command, hide=False):
        self.commands.append(command)
        if command == "echo $HOME":
            return SimpleNamespace(stdout="/home/deploy\n")
        if command.startswith("ls -1dt"):
            releases = "\n".join(f"/home/deploy/flightdeck/releases/rel{i}/" for i in range(7))
            return SimpleNamespace(stdout=releases + "\n")
        if "manifest.json" in command and command.startswith("cat "):
            return SimpleNamespace(stdout=self.previous_manifest)
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
                    release_name="20260824T211714Z",
                )

            self.assertEqual(fake.uploads[0], (str(archive_path), fake.uploads[0][1]))
            self.assertTrue(fake.uploads[0][1].endswith(".tar.gz"))
            self.assertEqual(len(fake.uploads), 1)

            joined = "\n".join(fake.commands)
            self.assertIn("docker network create traefik", joined)
            self.assertIn("docker network create databases", joined)
            self.assertIn("docker network create mcp", joined)
            self.assertIn("tar -xzf", joined)
            self.assertIn("/home/deploy/flightdeck/releases/20260824T211714Z", joined)
            self.assertIn("mkdir -p /home/deploy/flightdeck/apps-data/traefik", joined)
            self.assertIn("mkdir -p /home/deploy/flightdeck/apps-data/rybbit", joined)
            self.assertIn("DATA_DIR=/home/deploy/flightdeck/apps-data/traefik", joined)
            self.assertIn("DATA_DIR=/home/deploy/flightdeck/apps-data/rybbit", joined)
            self.assertIn("apps/traefik/.env", joined)
            self.assertIn("apps/rybbit/.env", joined)
            self.assertIn("ln -sfn", joined)
            self.assertIn("apps/rybbit && docker compose pull && docker compose up -d --remove-orphans", joined)
            self.assertIn("apps/traefik && docker compose pull && docker compose up -d --remove-orphans", joined)

            prune_command = next(command for command in fake.commands if command.startswith("rm -rf") and "rel" in command)
            for stale in ("rel5", "rel6"):
                self.assertIn(stale, prune_command)
            for kept in ("rel0", "rel1", "rel2", "rel3", "rel4"):
                self.assertNotIn(kept, prune_command)

    def test_stops_apps_removed_from_the_desired_set(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            archive_path = work_dir / "release.tar.gz"
            archive_path.write_text("fake archive\n")
            config = {"hosts": ["deploy@host"], "keep_releases": 5}

            previous_manifest = json.dumps({"apps": ["traefik", "gatus"]})
            fake = FakeConnection("deploy@host", previous_manifest=previous_manifest)
            with patch.object(deploy, "Connection", return_value=fake):
                deploy.deploy_to_host(
                    "deploy@host",
                    archive_path,
                    apps=["traefik"],
                    networks=["traefik"],
                    config=config,
                    release_name="20260824T211714Z",
                )

            joined = "\n".join(fake.commands)
            self.assertIn("cd /home/deploy/flightdeck/current/apps/gatus 2>/dev/null && docker compose down || true", joined)
            self.assertNotIn("apps/traefik 2>/dev/null && docker compose down", joined)

    def test_no_previous_manifest_stops_nothing(self):
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
                    apps=["traefik"],
                    networks=["traefik"],
                    config=config,
                    release_name="20260824T211714Z",
                )

            joined = "\n".join(fake.commands)
            self.assertNotIn("docker compose down", joined)


class MainTest(unittest.TestCase):
    def test_reads_target_manifest_and_merges_sops_age_key(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "heimdall.yml"
            manifest_path.write_text(
                "hosts: [deploy@host]\n"
                "app_refs: [owner/repo@latest]\n"
                "apps:\n  traefik:\n    env_refs: [owner/repo@latest:a.sops.env]\n"
            )
            stdin_config = {"target_manifest": str(manifest_path), "sops_age_key": "AGE-SECRET-KEY-1..."}

            with (
                patch.object(sys, "stdin", io.StringIO(json.dumps(stdin_config))),
                patch.object(
                    deploy, "build_release", return_value=(Path(directory) / "release", ["owner/repo@v1.0.0"])
                ) as fake_build_release,
                patch.object(
                    deploy,
                    "resolve_app_envs",
                    return_value={"traefik": ["owner/repo@v1.0.0:a.sops.env"]},
                ) as fake_resolve_app_envs,
                patch.object(deploy, "write_release_manifest"),
                patch.object(deploy, "archive_release", return_value=Path(directory) / "release.tar.gz"),
                patch.object(deploy, "list_required_networks", return_value=[]),
                patch.object(deploy, "deploy_to_host") as fake_deploy_to_host,
            ):
                deploy.main()

            config_arg = fake_build_release.call_args[0][0]
            self.assertEqual(config_arg["hosts"], ["deploy@host"])
            self.assertEqual(config_arg["app_refs"], ["owner/repo@latest"])
            self.assertEqual(config_arg["sops_age_key"], "AGE-SECRET-KEY-1...")

            fake_resolve_app_envs.assert_called_once()
            fake_deploy_to_host.assert_called_once()
            host, archive_path, apps, networks, deploy_config = fake_deploy_to_host.call_args[0][:5]
            expected = ("deploy@host", Path(directory) / "release.tar.gz", ["traefik"], [], config_arg)
            self.assertEqual((host, archive_path, apps, networks, deploy_config), expected)

    def test_raises_when_sops_age_key_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "heimdall.yml"
            manifest_path.write_text("hosts: [deploy@host]\napp_refs: [owner/repo@latest]\napps:\n  traefik: {}\n")
            stdin_config = {"target_manifest": str(manifest_path), "sops_age_key": ""}

            with (
                patch.object(sys, "stdin", io.StringIO(json.dumps(stdin_config))),
                self.assertRaises(deploy.DeployError),
            ):
                deploy.main()


if __name__ == "__main__":
    unittest.main()
