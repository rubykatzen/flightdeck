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


def write_target(directory, name, content):
    path = Path(directory) / f"{name}.yml"
    path.write_text(content)
    return path


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


class LoadTargetsTest(unittest.TestCase):
    def test_reads_every_manifest_in_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            write_target(directory, "heimdall", "apps:\n  traefik: {}\n")
            write_target(directory, "mainframe", "apps:\n  rybbit: {}\n")

            targets = renovate.load_targets(directory)

            self.assertEqual(
                sorted(targets),
                [("heimdall", {"apps": {"traefik": {}}}), ("mainframe", {"apps": {"rybbit": {}}})],
            )

    def test_raises_when_directory_has_no_manifests(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(renovate.RenovateError):
            renovate.load_targets(directory)


class FindMatchingTargetsTest(unittest.TestCase):
    def test_matches_targets_running_the_app(self):
        targets = [
            ("heimdall", {"apps": {"traefik": {}, "beszel": {}}}),
            ("mainframe", {"apps": {"rybbit": {}}}),
        ]

        matches = renovate.find_matching_targets(targets, "beszel")

        self.assertEqual(matches, [("heimdall", {"apps": {"traefik": {}, "beszel": {}}})])

    def test_ignores_targets_without_an_apps_mapping(self):
        targets = [("empty", {})]

        self.assertEqual(renovate.find_matching_targets(targets, "beszel"), [])


class LoadSshKeyTest(unittest.TestCase):
    def test_adds_resolved_secret_to_the_agent(self):
        calls = []

        def fake_run(args, input=None, capture_output=None, text=None):
            calls.append((args, input))
            return SimpleNamespace(returncode=0, stderr="")

        renovate.load_ssh_key({"HEIMDALL_SSH_KEY": "-----KEY-----"}, "HEIMDALL_SSH_KEY", run=fake_run)

        self.assertEqual(calls, [(["ssh-add", "-"], "-----KEY-----")])

    def test_raises_on_missing_secret(self):
        with self.assertRaises(renovate.RenovateError):
            renovate.load_ssh_key({}, "MISSING_SECRET")

    def test_raises_when_ssh_add_fails(self):
        def fake_run(args, input=None, capture_output=None, text=None):
            return SimpleNamespace(returncode=1, stderr="bad key")

        with self.assertRaises(renovate.RenovateError):
            renovate.load_ssh_key({"KEY": "text"}, "KEY", run=fake_run)


class RenovateTargetTest(unittest.TestCase):
    def test_renovates_every_host_without_touching_versions(self):
        manifest = {
            "hosts": ["deploy@app1.example.com", "deploy@app2.example.com"],
            "path": "~/flightdeck",
            "credentials": {"secrets": {"ssh_private_key": "DEPLOY_SSH_PRIVATE_KEY"}},
        }
        secrets = {"DEPLOY_SSH_PRIVATE_KEY": "-----KEY-----"}
        fakes = {}

        def fake_connection(host):
            fakes[host] = FakeConnection(host)
            return fakes[host]

        ssh_calls = []

        def fake_run(args, input=None, capture_output=None, text=None):
            ssh_calls.append(input)
            return SimpleNamespace(returncode=0, stderr="")

        with patch.object(renovate, "Connection", side_effect=fake_connection):
            renovate.renovate_target("mainframe", manifest, "beszel", secrets, run=fake_run)

        self.assertEqual(ssh_calls, ["-----KEY-----"])
        for host in manifest["hosts"]:
            joined = "\n".join(fakes[host].commands)
            self.assertIn("cd /home/deploy/flightdeck/current/apps/beszel", joined)
            self.assertIn("docker compose pull && docker compose up -d --remove-orphans", joined)


class MainTest(unittest.TestCase):
    def _run_main(self, directory, app, secrets):
        stdin = io.StringIO(json.dumps({"app": app, "targets_directory": str(directory)}))
        with (
            patch.object(sys, "stdin", stdin),
            patch.dict(os.environ, {"GITHUB_SECRETS_JSON": json.dumps(secrets)}),
        ):
            renovate.main()

    def test_raises_when_app_matches_no_target(self):
        with tempfile.TemporaryDirectory() as directory:
            write_target(directory, "heimdall", "apps:\n  traefik: {}\n")

            with self.assertRaises(renovate.RenovateError):
                self._run_main(directory, "beszel", {})

    def test_renovates_every_matching_target(self):
        with tempfile.TemporaryDirectory() as directory:
            write_target(
                directory,
                "heimdall",
                "apps:\n  beszel: {}\nhosts: [deploy@host]\ncredentials:\n  secrets:\n    ssh_private_key: KEY\n",
            )
            write_target(directory, "mainframe", "apps:\n  rybbit: {}\nhosts: [deploy@other]\n")

            with (
                patch.object(renovate, "renovate_target") as fake_renovate_target,
            ):
                self._run_main(directory, "beszel", {"KEY": "-----KEY-----"})

            fake_renovate_target.assert_called_once()
            name, manifest, app, secrets = fake_renovate_target.call_args[0]
            self.assertEqual((name, app), ("heimdall", "beszel"))


if __name__ == "__main__":
    unittest.main()
