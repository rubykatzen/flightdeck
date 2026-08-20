import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "load-yaml-matrix.py"
SPEC = importlib.util.spec_from_file_location("load_yaml_matrix", MODULE_PATH)
load_yaml_matrix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(load_yaml_matrix)


HAWKEYE = """\
flightdeck_ref: rubykatzen/flightdeck@v1.2.3
hosts: [rubykatzen-com@100.75.50.2]
"""

MAINFRAME = """\
flightdeck_ref: rubykatzen/flightdeck@v1.0.0
hosts: [deploy@100.64.0.1]
"""


class LoadYamlMatrixTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        (self.directory / "hawkeye.yml").write_text(HAWKEYE)
        (self.directory / "mainframe.yml").write_text(MAINFRAME)

    def test_builds_matrix_from_all_manifests(self):
        matrix = load_yaml_matrix.build_matrix(self.directory)
        self.assertEqual(
            sorted(item["name"] for item in matrix["include"]),
            ["hawkeye", "mainframe"],
        )

    def test_merges_manifest_fields_with_name_and_manifest(self):
        item = load_yaml_matrix.build_matrix(self.directory, "hawkeye")["include"][0]
        self.assertEqual(item["name"], "hawkeye")
        self.assertEqual(item["manifest"], str(self.directory / "hawkeye.yml"))
        self.assertEqual(item["flightdeck_ref"], "rubykatzen/flightdeck@v1.2.3")
        self.assertEqual(item["hosts"], ["rubykatzen-com@100.75.50.2"])

    def test_filters_selected_manifest(self):
        matrix = load_yaml_matrix.build_matrix(self.directory, "hawkeye")
        self.assertEqual([item["name"] for item in matrix["include"]], ["hawkeye"])

    def test_rejects_unknown_name(self):
        with self.assertRaisesRegex(load_yaml_matrix.ManifestError, "unknown name"):
            load_yaml_matrix.build_matrix(self.directory, "missing")

    def test_rejects_empty_directory(self):
        empty = self.directory / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(load_yaml_matrix.ManifestError, "no manifests found"):
            load_yaml_matrix.build_matrix(empty)

    def test_rejects_invalid_manifest_filename(self):
        (self.directory / "Hawkeye_Prod.yml").write_text(HAWKEYE)
        with self.assertRaisesRegex(load_yaml_matrix.ManifestError, "invalid manifest filename"):
            load_yaml_matrix.build_matrix(self.directory)

    def test_rejects_duplicate_manifest_name(self):
        (self.directory / "hawkeye.yaml").write_text(HAWKEYE)
        with self.assertRaisesRegex(load_yaml_matrix.ManifestError, "duplicate manifest name"):
            load_yaml_matrix.build_matrix(self.directory)

    def test_rejects_non_mapping_manifest(self):
        (self.directory / "hawkeye.yml").write_text("- one\n- two\n")
        with self.assertRaisesRegex(load_yaml_matrix.ManifestError, "must contain a YAML mapping"):
            load_yaml_matrix.build_matrix(self.directory)

    def test_rejects_duplicate_yaml_key(self):
        (self.directory / "hawkeye.yml").write_text("hosts: [one]\nhosts: [two]\n")
        with self.assertRaisesRegex(load_yaml_matrix.ManifestError, "duplicate YAML key"):
            load_yaml_matrix.build_matrix(self.directory)


if __name__ == "__main__":
    unittest.main()
