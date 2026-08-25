import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "render-env.py"
SPEC = importlib.util.spec_from_file_location("render_env", MODULE_PATH)
render_env = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_env)


class RenderEnvTest(unittest.TestCase):
    def test_render_prefers_secrets_over_variables(self):
        manifest = {"env": {"DOMAIN": "${DOMAIN}", "TIMEZONE": "${TIMEZONE}"}}
        output = render_env.render_env(
            manifest,
            {"DOMAIN": "secret.example"},
            {"DOMAIN": "var.example", "TIMEZONE": "Europe/Berlin"},
        )
        self.assertIn("DOMAIN=secret.example\n", output)
        self.assertIn("TIMEZONE=Europe/Berlin\n", output)

    def test_quotes_shell_sensitive_values(self):
        output = render_env.render_env({"env": {"TOKEN": "${TOKEN}"}}, {"TOKEN": "hello world"}, {})
        self.assertIn("TOKEN='hello world'\n", output)

    def test_rejects_raw_env(self):
        with self.assertRaises(render_env.ManifestError):
            render_env.load_manifest(self.write_manifest("asset: test.sops.env\nraw_env: [APPS]\n"))

    def test_missing_source_fails(self):
        with self.assertRaises(render_env.ManifestError):
            render_env.render_env({"env": {"TOKEN": "${TOKEN}"}}, {}, {})

    def test_literal_values_pass_through_without_lookup(self):
        manifest = {"env": {"DISABLE_SIGNUP": True, "MAX_RETRIES": 5, "LABEL": "internal-only"}}
        output = render_env.render_env(manifest, {}, {})
        self.assertIn("DISABLE_SIGNUP=true\n", output)
        self.assertIn("MAX_RETRIES=5\n", output)
        self.assertIn("LABEL=internal-only\n", output)

    def test_literal_false_renders_lowercase(self):
        output = render_env.render_env({"env": {"FLAG": False}}, {}, {})
        self.assertIn("FLAG=false\n", output)

    def test_rejects_malformed_reference(self):
        with self.assertRaises(render_env.ManifestError):
            render_env.load_manifest(self.write_manifest("asset: test.sops.env\nkeys: [k]\nenv:\n  TOKEN: ${lowercase}\n"))

    def test_rejects_dict_or_list_literal(self):
        with self.assertRaises(render_env.ManifestError):
            render_env.load_manifest(self.write_manifest("asset: test.sops.env\nkeys: [k]\nenv:\n  TOKEN: [a, b]\n"))

    def test_duplicate_yaml_keys_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.yml"
            path.write_text(
                "asset: mainframe.sops.env\n"
                "keys: [master, server]\n"
                "env:\n"
                "  TOKEN: FIRST\n"
                "  TOKEN: SECOND\n"
            )
            with self.assertRaises(render_env.ManifestError):
                render_env.load_manifest(path)

    def write_manifest(self, content):
        self.addCleanup(lambda: self._manifest_tmp.cleanup())
        self._manifest_tmp = tempfile.TemporaryDirectory()
        path = Path(self._manifest_tmp.name) / "manifest.yml"
        path.write_text(content)
        return path

    def test_main_writes_env_and_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.yml"
            env_path = root / ".env"
            outputs_path = root / "outputs"
            manifest_path.write_text(
                "asset: mainframe.sops.env\n"
                "keys: [master, server]\n"
                "env:\n"
                "  TOKEN: ${TOKEN}\n"
            )
            old_env = os.environ.copy()
            os.environ.update(
                {
                    "GITHUB_SECRETS_JSON": json.dumps({"TOKEN": "secret"}),
                    "GITHUB_VARS_JSON": "{}",
                    "GITHUB_OUTPUT": str(outputs_path),
                }
            )
            try:
                result = render_env.main(["--manifest", str(manifest_path), "--output", str(env_path)])
            finally:
                os.environ.clear()
                os.environ.update(old_env)
            self.assertEqual(result, 0)
            self.assertIn("TOKEN=secret\n", env_path.read_text())
            self.assertIn("asset=mainframe.sops.env\n", outputs_path.read_text())
            self.assertIn("keys=master,server\n", outputs_path.read_text())


if __name__ == "__main__":
    unittest.main()
