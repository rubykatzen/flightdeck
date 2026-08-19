import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "load-targets.py"
SPEC = importlib.util.spec_from_file_location("load_targets", MODULE_PATH)
load_targets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(load_targets)


ENCRYPT = """\
asset: hawkeye.sops.env
keys: [hawkeye]
apps: [traefik, rybbit]
env:
  APPS_DOMAIN: RUBYKATZEN_COM_DOMAIN
"""

TARGET = """\
flightdeck_ref: rubykatzen/flightdeck@v1.2.3
env_ref: rubykatzen/config@v2.0.0:hawkeye.sops.env
extra_refs:
  - rubykatzen/apps@v3.0.0:flightdeck-extra.zip
hosts: [rubykatzen-com@100.75.50.2]
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
        self.root = Path(self.temporary_directory.name)
        self.encrypt_directory = self.root / "encrypt"
        self.targets_directory = self.root / "targets"
        self.encrypt_directory.mkdir()
        self.targets_directory.mkdir()
        (self.encrypt_directory / "hawkeye.yml").write_text(ENCRYPT)
        (self.targets_directory / "hawkeye.yml").write_text(TARGET)

    def test_builds_encrypt_matrix(self):
        matrix = load_targets.build_matrix(self.encrypt_directory, "encrypt")
        self.assertEqual(
            matrix,
            {
                "include": [
                    {
                        "target": "hawkeye",
                        "manifest": str(self.encrypt_directory / "hawkeye.yml"),
                        "asset": "hawkeye.sops.env",
                    }
                ]
            },
        )

    def test_builds_deploy_matrix(self):
        item = load_targets.build_matrix(self.targets_directory, "deploy")["include"][0]
        self.assertEqual(item["hosts"], ["rubykatzen-com@100.75.50.2"])
        self.assertEqual(item["flightdeck_ref"], "rubykatzen/flightdeck@v1.2.3")
        self.assertEqual(item["extra_refs"], ["rubykatzen/apps@v3.0.0:flightdeck-extra.zip"])
        self.assertEqual(item["path"], "~/flightdeck")
        self.assertEqual(item["sops_age_key_file"], "~/.config/sops/age/keys.txt")
        self.assertEqual(item["ssh_private_key_secret"], "DEPLOY_SSH_PRIVATE_KEY")

    def test_allows_deploy_path_default_overrides(self):
        path = self.targets_directory / "hawkeye.yml"
        path.write_text(
            TARGET.replace("path: ~/flightdeck\n", "").replace(
                "sops_age_key_file: ~/.config/sops/age/keys.txt\n", ""
            )
        )
        item = load_targets.build_matrix(self.targets_directory, "deploy")["include"][0]
        self.assertEqual(item["path"], "~/flightdeck")
        self.assertEqual(item["sops_age_key_file"], "~/.config/sops/age/keys.txt")

        path.write_text(
            TARGET.replace("path: ~/flightdeck", "path: ~/custom").replace(
                "sops_age_key_file: ~/.config/sops/age/keys.txt",
                "sops_age_key_file: ~/.config/sops/age/custom.txt",
            )
        )
        item = load_targets.build_matrix(self.targets_directory, "deploy")["include"][0]
        self.assertEqual(item["path"], "~/custom")
        self.assertEqual(item["sops_age_key_file"], "~/.config/sops/age/custom.txt")

    def test_filters_selected_config(self):
        (self.encrypt_directory / "other.yml").write_text(
            ENCRYPT.replace("hawkeye.sops.env", "other.sops.env")
        )
        matrix = load_targets.build_matrix(self.encrypt_directory, "encrypt", "hawkeye")
        self.assertEqual([item["target"] for item in matrix["include"]], ["hawkeye"])

    def test_rejects_unknown_config(self):
        with self.assertRaisesRegex(load_targets.TargetError, "unknown target"):
            load_targets.build_matrix(self.targets_directory, "deploy", "missing")

    def test_rejects_wrong_config_type(self):
        with self.assertRaisesRegex(load_targets.TargetError, "unknown keys"):
            load_targets.build_matrix(self.encrypt_directory, "deploy")

    def test_rejects_invalid_ssh_destination(self):
        path = self.targets_directory / "hawkeye.yml"
        path.write_text(TARGET.replace("rubykatzen-com@100.75.50.2", "100.75.50.2"))
        with self.assertRaisesRegex(load_targets.TargetError, "invalid user@host destination"):
            load_targets.build_matrix(self.targets_directory, "deploy")

    def test_rejects_duplicate_host_addresses(self):
        path = self.targets_directory / "hawkeye.yml"
        path.write_text(
            TARGET.replace(
                "hosts: [rubykatzen-com@100.75.50.2]",
                "hosts: [first@100.75.50.2, second@100.75.50.2]",
            )
        )
        with self.assertRaisesRegex(load_targets.TargetError, "duplicate host addresses"):
            load_targets.build_matrix(self.targets_directory, "deploy")

    def test_rejects_apps_in_env(self):
        path = self.encrypt_directory / "hawkeye.yml"
        path.write_text(ENCRYPT.replace("  APPS_DOMAIN:", "  APPS: RUBYKATZEN_COM_APPS\n  APPS_DOMAIN:"))
        with self.assertRaisesRegex(load_targets.TargetError, "must be configured through"):
            load_targets.build_matrix(self.encrypt_directory, "encrypt")

    def test_rejects_duplicate_apps(self):
        path = self.encrypt_directory / "hawkeye.yml"
        path.write_text(ENCRYPT.replace("apps: [traefik, rybbit]", "apps: [traefik, rybbit, traefik]"))
        with self.assertRaisesRegex(load_targets.TargetError, "duplicate app names"):
            load_targets.build_matrix(self.encrypt_directory, "encrypt")

    def test_rejects_duplicate_keys(self):
        path = self.encrypt_directory / "hawkeye.yml"
        path.write_text(ENCRYPT.replace("asset: hawkeye.sops.env", "asset: one.sops.env\nasset: two.sops.env"))
        with self.assertRaisesRegex(load_targets.TargetError, "duplicate YAML key"):
            load_targets.build_matrix(self.encrypt_directory, "encrypt")


if __name__ == "__main__":
    unittest.main()
