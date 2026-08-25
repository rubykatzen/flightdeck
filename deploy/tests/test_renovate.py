import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

DEPLOY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEPLOY_DIR))

MODULE_PATH = DEPLOY_DIR / "renovate.py"
SPEC = importlib.util.spec_from_file_location("renovate_entrypoint", MODULE_PATH)
renovate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renovate)


class FakeConnection:
    """Stand-in for fabric.Connection - records commands instead of opening
    a real SSH session, mirroring test_deploy.py's FakeConnection."""

    def __init__(self, host, pull_stdout=""):
        self.host = host
        self.client = SimpleNamespace(set_missing_host_key_policy=lambda policy: None)
        self.commands = []
        self.pull_stdout = pull_stdout

    def run(self, command, hide=False):
        self.commands.append(command)
        if command == "echo $HOME":
            return SimpleNamespace(stdout="/home/deploy\n")
        return SimpleNamespace(stdout=self.pull_stdout)


class ExpandHomeTest(unittest.TestCase):
    def test_expands_tilde_prefix(self):
        self.assertEqual(renovate.expand_home("~/flightdeck", "/home/deploy"), "/home/deploy/flightdeck")

    def test_leaves_absolute_path_untouched(self):
        self.assertEqual(renovate.expand_home("/opt/flightdeck", "/home/deploy"), "/opt/flightdeck")


class RenovateHostTest(unittest.TestCase):
    def test_pulls_and_recreates_without_touching_the_release(self):
        fake = FakeConnection("deploy@host")
        with patch.object(renovate, "Connection", return_value=fake):
            renovate.renovate_host("deploy@host", "~/flightdeck", "beszel")

        joined = "\n".join(fake.commands)
        self.assertIn("cd /home/deploy/flightdeck/current/apps/beszel", joined)
        self.assertIn("before=$(docker compose images -q)", joined)
        self.assertIn("docker compose pull", joined)
        self.assertIn("after=$(docker compose images -q)", joined)
        self.assertIn("docker compose up -d --remove-orphans", joined)

    def test_returns_true_when_the_image_changed(self):
        fake = FakeConnection("deploy@host", pull_stdout="RENOVATE_UPDATED\n")
        with patch.object(renovate, "Connection", return_value=fake):
            self.assertTrue(renovate.renovate_host("deploy@host", "~/flightdeck", "beszel"))

    def test_returns_false_when_the_image_was_already_current(self):
        fake = FakeConnection("deploy@host", pull_stdout="")
        with patch.object(renovate, "Connection", return_value=fake):
            self.assertFalse(renovate.renovate_host("deploy@host", "~/flightdeck", "beszel"))


class MainTest(unittest.TestCase):
    def _run_main(self, config):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "outputs"
            with (
                patch.object(sys, "stdin", io.StringIO(json.dumps(config))),
                patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}),
            ):
                renovate.main()
            return output_path.read_text() if output_path.exists() else ""

    def test_skips_a_target_that_does_not_run_the_app(self):
        with patch.object(renovate, "renovate_host") as fake_renovate_host:
            outputs = self._run_main({"app": "beszel", "hosts": ["deploy@host"], "apps": {"traefik": {}}})

        fake_renovate_host.assert_not_called()
        self.assertIn("updated=false\n", outputs)

    def test_reports_updated_hosts_when_the_image_changed(self):
        def fake_renovate_host(host, base_path, app):
            return host == "deploy@app1.example.com"

        with patch.object(renovate, "renovate_host", side_effect=fake_renovate_host):
            outputs = self._run_main(
                {
                    "app": "beszel",
                    "hosts": ["deploy@app1.example.com", "deploy@app2.example.com"],
                    "path": "~/flightdeck",
                    "apps": {"beszel": {}},
                }
            )

        self.assertIn("updated=true\n", outputs)
        self.assertIn("updated_hosts=deploy@app1.example.com\n", outputs)

    def test_reports_not_updated_when_every_host_was_already_current(self):
        with patch.object(renovate, "renovate_host", return_value=False):
            outputs = self._run_main({"app": "beszel", "hosts": ["deploy@host"], "apps": {"beszel": {}}})

        self.assertIn("updated=false\n", outputs)
        self.assertIn("updated_hosts=\n", outputs)

    def test_defaults_path_when_omitted(self):
        with patch.object(renovate, "renovate_host", return_value=False) as fake_renovate_host:
            self._run_main({"app": "beszel", "hosts": ["deploy@host"], "apps": {"beszel": {}}})

        fake_renovate_host.assert_called_once_with("deploy@host", "~/flightdeck", "beszel")


if __name__ == "__main__":
    unittest.main()
