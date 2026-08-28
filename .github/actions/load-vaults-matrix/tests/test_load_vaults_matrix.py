import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "load-vaults-matrix.py"
SPEC = importlib.util.spec_from_file_location("load_vaults_matrix", MODULE_PATH)
load_vaults_matrix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(load_vaults_matrix)


TRAEFIK = """\
asset: mainframe-traefik.sops.env
keys:
  - mainframe
env:
  HTTP_PORT: ${MAINFRAME_TRAEFIK_HTTP_PORT}
"""

RYBBIT = """\
asset: mainframe-rybbit.sops.env
keys:
  - mainframe
env:
  DOMAIN: ${MAINFRAME_DOMAIN}
"""


class LoadVaultsMatrixTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        (self.directory / "traefik.yml").write_text(TRAEFIK)
        (self.directory / "rybbit.yml").write_text(RYBBIT)

    def test_builds_matrix_from_all_manifests(self):
        matrix = load_vaults_matrix.build_matrix(self.directory)
        self.assertEqual(
            sorted(item["name"] for item in matrix["include"]),
            ["rybbit", "traefik"],
        )

    def test_merges_manifest_fields_with_name_and_manifest(self):
        matrix = load_vaults_matrix.build_matrix(self.directory)
        item = next(item for item in matrix["include"] if item["name"] == "traefik")
        self.assertEqual(item["manifest"], str(self.directory / "traefik.yml"))
        self.assertEqual(item["asset"], "mainframe-traefik.sops.env")
        self.assertEqual(item["keys"], ["mainframe"])

    def test_rejects_empty_directory(self):
        empty = self.directory / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(load_vaults_matrix.ManifestError, "no manifests found"):
            load_vaults_matrix.build_matrix(empty)

    def test_rejects_invalid_manifest_filename(self):
        (self.directory / "Traefik_Prod.yml").write_text(TRAEFIK)
        with self.assertRaisesRegex(load_vaults_matrix.ManifestError, "invalid manifest filename"):
            load_vaults_matrix.build_matrix(self.directory)

    def test_rejects_duplicate_manifest_name(self):
        (self.directory / "traefik.yaml").write_text(TRAEFIK)
        with self.assertRaisesRegex(load_vaults_matrix.ManifestError, "duplicate manifest name"):
            load_vaults_matrix.build_matrix(self.directory)

    def test_rejects_non_mapping_manifest(self):
        (self.directory / "traefik.yml").write_text("- one\n- two\n")
        with self.assertRaisesRegex(load_vaults_matrix.ManifestError, "must contain a YAML mapping"):
            load_vaults_matrix.build_matrix(self.directory)

    def test_rejects_duplicate_yaml_key(self):
        (self.directory / "traefik.yml").write_text("keys: [one]\nkeys: [two]\n")
        with self.assertRaisesRegex(load_vaults_matrix.ManifestError, "duplicate YAML key"):
            load_vaults_matrix.build_matrix(self.directory)

    def test_rejects_missing_asset(self):
        (self.directory / "traefik.yml").write_text("keys: [mainframe]\nenv: {HTTP_PORT: '80'}\n")
        with self.assertRaisesRegex(load_vaults_matrix.ManifestError, "must set asset"):
            load_vaults_matrix.build_matrix(self.directory)

    def test_rejects_empty_keys(self):
        (self.directory / "traefik.yml").write_text(
            "asset: mainframe-traefik.sops.env\nkeys: []\nenv: {HTTP_PORT: '80'}\n"
        )
        with self.assertRaisesRegex(load_vaults_matrix.ManifestError, "must set keys"):
            load_vaults_matrix.build_matrix(self.directory)

    def test_rejects_missing_env(self):
        (self.directory / "traefik.yml").write_text("asset: mainframe-traefik.sops.env\nkeys: [mainframe]\n")
        with self.assertRaisesRegex(load_vaults_matrix.ManifestError, "must set env"):
            load_vaults_matrix.build_matrix(self.directory)


if __name__ == "__main__":
    unittest.main()
