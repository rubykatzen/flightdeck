import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "load-targets.py"
SPEC = importlib.util.spec_from_file_location("load_targets", MODULE_PATH)
load_targets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(load_targets)


TARGET = """\
encrypt:
  asset: hawkeye.sops.env
  keys: [hawkeye]
  apps: [traefik, rybbit]
  env:
    APPS_DOMAIN: RUBYKATZEN_COM_DOMAIN
deploy:
  flightdeck_ref: rubykatzen/flightdeck@v1.2.3
  env_ref: rubykatzen/config@v2.0.0:hawkeye.sops.env
  extra_refs:
    - rubykatzen/apps@v3.0.0:flightdeck-extra.zip
  host:
    inventory: [100.75.50.2]
    user: rubykatzen-com
    path: ~/flightdeck
    sops_age_key_file: ~/.config/sops/age/keys.txt
  credentials:
    variables:
      tailscale_oauth_client_id: TAILSCALE_OAUTH_CLIENT_ID
    secrets:
      ssh_private_key: DEPLOY_SSH_PRIVATE_KEY
      tailscale_oauth_secret: TAILSCALE_OAUTH_SECRET
"""


class LoadTargetsTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        (self.directory / "hawkeye.yml").write_text(TARGET)

    def test_builds_encrypt_matrix(self):
        matrix = load_targets.build_matrix(self.directory, "encrypt")
        self.assertEqual(
            matrix,
            {
                "include": [
                    {
                        "target": "hawkeye",
                        "manifest": str(self.directory / "hawkeye.yml"),
                        "asset": "hawkeye.sops.env",
                    }
                ]
            },
        )

    def test_builds_deploy_matrix(self):
        item = load_targets.build_matrix(self.directory, "deploy")["include"][0]
        self.assertEqual(item["inventory"], ["100.75.50.2"])
        self.assertEqual(item["flightdeck_ref"], "rubykatzen/flightdeck@v1.2.3")
        self.assertEqual(item["extra_refs"], ["rubykatzen/apps@v3.0.0:flightdeck-extra.zip"])
        self.assertEqual(item["ssh_private_key_secret"], "DEPLOY_SSH_PRIVATE_KEY")
        self.assertNotIn("apps", item)

    def test_filters_selected_target(self):
        (self.directory / "other.yml").write_text(TARGET.replace("hawkeye.sops.env", "other.sops.env"))
        matrix = load_targets.build_matrix(self.directory, "encrypt", "hawkeye")
        self.assertEqual([item["target"] for item in matrix["include"]], ["hawkeye"])

    def test_rejects_unknown_target(self):
        with self.assertRaisesRegex(load_targets.TargetError, "unknown target"):
            load_targets.build_matrix(self.directory, "deploy", "missing")

    def test_rejects_missing_selected_section(self):
        (self.directory / "encrypt-only.yml").write_text(TARGET.split("deploy:\n", maxsplit=1)[0])
        with self.assertRaisesRegex(load_targets.TargetError, "has no deploy section"):
            load_targets.build_matrix(self.directory, "deploy", "encrypt-only")

    def test_rejects_string_inventory(self):
        path = self.directory / "hawkeye.yml"
        path.write_text(TARGET.replace("inventory: [100.75.50.2]", 'inventory: "100.75.50.2,"'))
        with self.assertRaisesRegex(load_targets.TargetError, "inventory must be a non-empty array"):
            load_targets.build_matrix(self.directory, "deploy")

    def test_rejects_apps_in_env(self):
        path = self.directory / "hawkeye.yml"
        path.write_text(TARGET.replace("    APPS_DOMAIN:", "    APPS: RUBYKATZEN_COM_APPS\n    APPS_DOMAIN:"))
        with self.assertRaisesRegex(load_targets.TargetError, "must be configured through"):
            load_targets.build_matrix(self.directory, "encrypt")

    def test_rejects_duplicate_apps(self):
        path = self.directory / "hawkeye.yml"
        path.write_text(TARGET.replace("apps: [traefik, rybbit]", "apps: [traefik, rybbit, traefik]"))
        with self.assertRaisesRegex(load_targets.TargetError, "duplicate app names"):
            load_targets.build_matrix(self.directory, "encrypt")

    def test_rejects_duplicate_keys(self):
        path = self.directory / "hawkeye.yml"
        path.write_text(TARGET.replace("  asset: hawkeye.sops.env", "  asset: one.sops.env\n  asset: two.sops.env"))
        with self.assertRaisesRegex(load_targets.TargetError, "duplicate YAML key"):
            load_targets.build_matrix(self.directory, "encrypt")


if __name__ == "__main__":
    unittest.main()
