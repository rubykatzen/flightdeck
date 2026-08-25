import importlib.util
import io
import json
import sys
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

    def __init__(self, host):
        self.host = host
        self.client = SimpleNamespace(set_missing_host_key_policy=lambda policy: None)
        self.commands = []

    def run(self, command, hide=False):
        self.commands.append(command)
        if command == "echo $HOME":
            return SimpleNamespace(stdout="/home/deploy\n")
        return SimpleNamespace(stdout="")


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
        self.assertIn("docker compose pull && docker compose up -d --remove-orphans", joined)


class MainTest(unittest.TestCase):
    def _run_main(self, config):
        with patch.object(sys, "stdin", io.StringIO(json.dumps(config))):
            renovate.main()

    def test_skips_a_target_that_does_not_run_the_app(self):
        with patch.object(renovate, "renovate_host") as fake_renovate_host:
            self._run_main({"app": "beszel", "hosts": ["deploy@host"], "apps": {"traefik": {}}})

        fake_renovate_host.assert_not_called()

    def test_renovates_every_host_when_the_target_runs_the_app(self):
        with patch.object(renovate, "renovate_host") as fake_renovate_host:
            self._run_main(
                {
                    "app": "beszel",
                    "hosts": ["deploy@app1.example.com", "deploy@app2.example.com"],
                    "path": "~/flightdeck",
                    "apps": {"beszel": {}},
                }
            )

        self.assertEqual(
            fake_renovate_host.call_args_list,
            [
                unittest.mock.call("deploy@app1.example.com", "~/flightdeck", "beszel"),
                unittest.mock.call("deploy@app2.example.com", "~/flightdeck", "beszel"),
            ],
        )

    def test_defaults_path_when_omitted(self):
        with patch.object(renovate, "renovate_host") as fake_renovate_host:
            self._run_main({"app": "beszel", "hosts": ["deploy@host"], "apps": {"beszel": {}}})

        fake_renovate_host.assert_called_once_with("deploy@host", "~/flightdeck", "beszel")


if __name__ == "__main__":
    unittest.main()
