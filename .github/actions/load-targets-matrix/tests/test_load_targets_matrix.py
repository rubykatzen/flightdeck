import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "load-targets-matrix.py"
SPEC = importlib.util.spec_from_file_location("load_targets_matrix", MODULE_PATH)
load_targets_matrix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(load_targets_matrix)


HEIMDALL = """\
app_refs: [rubykatzen/flightdeck@latest]
apps:
  traefik: {}
hosts: [root@100.75.53.13]
ssh_private_key_secret: DEPLOY_SSH_PRIVATE_KEY
sops_age_key_secret: HEIMDALL_AGE_PRIVATE_KEY
"""

MAINFRAME = """\
app_refs: [rubykatzen/flightdeck@latest, owner/extra-apps@latest]
apps:
  rybbit: {}
hosts: [deploy@app1.example.com, deploy@app2.example.com]
path: ~/flightdeck
ssh_private_key_secret: DEPLOY_SSH_PRIVATE_KEY
sops_age_key_secret: MAINFRAME_AGE_PRIVATE_KEY
"""


class LoadTargetsMatrixTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        (self.directory / "heimdall.yml").write_text(HEIMDALL)
        (self.directory / "mainframe.yml").write_text(MAINFRAME)

    def test_builds_matrix_from_all_manifests(self):
        matrix = load_targets_matrix.build_matrix(self.directory)
        self.assertEqual(
            sorted(item["name"] for item in matrix["include"]),
            ["heimdall", "mainframe"],
        )

    def test_merges_manifest_fields_with_name_and_manifest(self):
        item = load_targets_matrix.build_matrix(self.directory, "heimdall")["include"][0]
        self.assertEqual(item["name"], "heimdall")
        self.assertEqual(item["manifest"], str(self.directory / "heimdall.yml"))
        self.assertEqual(item["hosts"], ["root@100.75.53.13"])
        self.assertEqual(item["ssh_private_key_secret"], "DEPLOY_SSH_PRIVATE_KEY")
        self.assertEqual(item["sops_age_key_secret"], "HEIMDALL_AGE_PRIVATE_KEY")

    def test_filters_selected_manifest(self):
        matrix = load_targets_matrix.build_matrix(self.directory, "heimdall")
        self.assertEqual([item["name"] for item in matrix["include"]], ["heimdall"])

    def test_rejects_unknown_name(self):
        with self.assertRaisesRegex(load_targets_matrix.ManifestError, "unknown name"):
            load_targets_matrix.build_matrix(self.directory, "missing")

    def test_rejects_empty_directory(self):
        empty = self.directory / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(load_targets_matrix.ManifestError, "no manifests found"):
            load_targets_matrix.build_matrix(empty)

    def test_rejects_invalid_manifest_filename(self):
        (self.directory / "Heimdall_Prod.yml").write_text(HEIMDALL)
        with self.assertRaisesRegex(load_targets_matrix.ManifestError, "invalid manifest filename"):
            load_targets_matrix.build_matrix(self.directory)

    def test_rejects_duplicate_manifest_name(self):
        (self.directory / "heimdall.yaml").write_text(HEIMDALL)
        with self.assertRaisesRegex(load_targets_matrix.ManifestError, "duplicate manifest name"):
            load_targets_matrix.build_matrix(self.directory)

    def test_rejects_non_mapping_manifest(self):
        (self.directory / "heimdall.yml").write_text("- one\n- two\n")
        with self.assertRaisesRegex(load_targets_matrix.ManifestError, "must contain a YAML mapping"):
            load_targets_matrix.build_matrix(self.directory)

    def test_rejects_duplicate_yaml_key(self):
        (self.directory / "heimdall.yml").write_text("hosts: [one]\nhosts: [two]\n")
        with self.assertRaisesRegex(load_targets_matrix.ManifestError, "duplicate YAML key"):
            load_targets_matrix.build_matrix(self.directory)

    def test_rejects_missing_hosts(self):
        (self.directory / "heimdall.yml").write_text(HEIMDALL.replace("hosts: [root@100.75.53.13]\n", ""))
        with self.assertRaisesRegex(load_targets_matrix.ManifestError, "must set hosts"):
            load_targets_matrix.build_matrix(self.directory)

    def test_rejects_missing_app_refs(self):
        (self.directory / "heimdall.yml").write_text(
            HEIMDALL.replace("app_refs: [rubykatzen/flightdeck@latest]\n", "")
        )
        with self.assertRaisesRegex(load_targets_matrix.ManifestError, "must set app_refs"):
            load_targets_matrix.build_matrix(self.directory)

    def test_rejects_missing_apps(self):
        (self.directory / "heimdall.yml").write_text(HEIMDALL.replace("apps:\n  traefik: {}\n", ""))
        with self.assertRaisesRegex(load_targets_matrix.ManifestError, "must set apps"):
            load_targets_matrix.build_matrix(self.directory)

    def test_rejects_missing_ssh_private_key_secret(self):
        (self.directory / "heimdall.yml").write_text(
            HEIMDALL.replace("ssh_private_key_secret: DEPLOY_SSH_PRIVATE_KEY\n", "")
        )
        with self.assertRaisesRegex(load_targets_matrix.ManifestError, "must set ssh_private_key_secret"):
            load_targets_matrix.build_matrix(self.directory)

    def test_rejects_missing_sops_age_key_secret(self):
        (self.directory / "heimdall.yml").write_text(
            HEIMDALL.replace("sops_age_key_secret: HEIMDALL_AGE_PRIVATE_KEY\n", "")
        )
        with self.assertRaisesRegex(load_targets_matrix.ManifestError, "must set sops_age_key_secret"):
            load_targets_matrix.build_matrix(self.directory)


if __name__ == "__main__":
    unittest.main()
