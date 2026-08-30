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

    def __init__(self, host, snapshots=None, labels=None):
        self.host = host
        self.client = SimpleNamespace(set_missing_host_key_policy=lambda policy: None)
        self.commands = []
        self.snapshots = list(snapshots or [{}, {}])
        self.current_snapshot = {}
        self.labels = labels or {}

    def run(self, command, hide=False):
        self.commands.append(command)
        if command == "echo $HOME":
            return SimpleNamespace(stdout="/home/deploy\n")
        if command.endswith("docker compose ps --all -q"):
            self.current_snapshot = self.snapshots.pop(0)
            return SimpleNamespace(stdout="\n".join(self.current_snapshot))
        if command.startswith("docker inspect "):
            container_id = command.split()[2]
            container = self.current_snapshot[container_id]
            return SimpleNamespace(
                stdout=json.dumps(
                    [
                        {
                            "Image": container["image_id"],
                            "Config": {
                                "Image": container["image"],
                                "Labels": {"com.docker.compose.service": container["service"]},
                            },
                        }
                    ]
                )
            )
        if command.startswith("docker image inspect "):
            image_id = command.split()[3]
            return SimpleNamespace(stdout=json.dumps(self.labels.get(image_id)))
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
        self.assertIn("docker compose pull", joined)
        self.assertIn("docker compose up -d --remove-orphans", joined)
        self.assertEqual(joined.count("docker compose ps --all -q"), 2)

    def test_returns_version_transition_when_the_image_changed(self):
        before = {
            "container-old": {
                "service": "beszel",
                "image": "henrygd/beszel:latest",
                "image_id": "sha256:old",
            }
        }
        after = {
            "container-new": {
                "service": "beszel",
                "image": "henrygd/beszel:latest",
                "image_id": "sha256:new",
            }
        }
        labels = {
            "sha256:old": {"org.opencontainers.image.version": "0.12.8"},
            "sha256:new": {"org.opencontainers.image.version": "0.12.9"},
        }
        fake = FakeConnection("deploy@host", [before, after], labels)
        with patch.object(renovate, "Connection", return_value=fake):
            self.assertEqual(
                renovate.renovate_host("deploy@host", "~/flightdeck", "beszel"),
                [
                    {
                        "service": "beszel",
                        "image": "henrygd/beszel:latest",
                        "before": {"id": "sha256:old", "version": "0.12.8"},
                        "after": {"id": "sha256:new", "version": "0.12.9"},
                    }
                ],
            )

    def test_returns_no_transitions_when_the_image_was_already_current(self):
        containers = {
            "container": {
                "service": "beszel",
                "image": "henrygd/beszel:latest",
                "image_id": "sha256:same",
            }
        }
        fake = FakeConnection("deploy@host", [containers, containers])
        with patch.object(renovate, "Connection", return_value=fake):
            self.assertEqual(renovate.renovate_host("deploy@host", "~/flightdeck", "beszel"), [])

    def test_reports_the_specific_changed_service_in_a_multiservice_app(self):
        before = {
            "client-container": {
                "service": "client",
                "image": "ghcr.io/rybbit-io/rybbit-client:latest",
                "image_id": "sha256:client-old",
            },
            "backend-container": {
                "service": "backend",
                "image": "ghcr.io/rybbit-io/rybbit-backend:latest",
                "image_id": "sha256:backend-same",
            },
        }
        after = {
            "client-container": {
                "service": "client",
                "image": "ghcr.io/rybbit-io/rybbit-client:latest",
                "image_id": "sha256:client-new",
            },
            "backend-container": {
                "service": "backend",
                "image": "ghcr.io/rybbit-io/rybbit-backend:latest",
                "image_id": "sha256:backend-same",
            },
        }
        labels = {
            "sha256:client-old": {"org.opencontainers.image.version": "1.6.0"},
            "sha256:client-new": {"org.opencontainers.image.version": "1.6.1"},
        }
        fake = FakeConnection("deploy@host", [before, after], labels)

        with patch.object(renovate, "Connection", return_value=fake):
            changes = renovate.renovate_host("deploy@host", "~/flightdeck", "rybbit")

        self.assertEqual([change["service"] for change in changes], ["client"])

    def test_preserves_missing_versions_for_downstream_image_id_fallback(self):
        before = {
            "app": {
                "id": "sha256:1234567890abcdef",
                "image": "app:latest",
                "version": None,
            }
        }
        after = {
            "app": {
                "id": "sha256:abcdef1234567890",
                "image": "app:latest",
                "version": None,
            }
        }

        self.assertEqual(
            renovate.image_transitions(before, after),
            [
                {
                    "service": "app",
                    "image": "app:latest",
                    "before": {"id": "sha256:1234567890abcdef", "version": None},
                    "after": {"id": "sha256:abcdef1234567890", "version": None},
                }
            ],
        )


class MainTest(unittest.TestCase):
    def _run_main(self, directory, apps, manifest_text, manifest_name="heimdall"):
        manifest_path = Path(directory) / f"{manifest_name}.yml"
        manifest_path.write_text(manifest_text)
        output_path = Path(directory) / "outputs"

        config = {"apps": apps, "target_manifest": str(manifest_path)}
        with (
            patch.object(sys, "stdin", io.StringIO(json.dumps(config))),
            patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}),
        ):
            renovate.main()
        return output_path.read_text() if output_path.exists() else ""

    def test_skips_a_target_that_runs_none_of_the_requested_apps(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(renovate, "renovate_host") as fake_renovate_host,
        ):
            outputs = self._run_main(directory, ["beszel"], "apps:\n  traefik: {}\nhosts: [deploy@host]\n")

        fake_renovate_host.assert_not_called()
        self.assertIn("updated=false\n", outputs)
        self.assertIn("target_name=heimdall\n", outputs)

    def test_renovates_every_app_when_apps_is_empty(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(renovate, "renovate_host", return_value=[]) as fake_renovate_host,
        ):
            self._run_main(directory, [], "apps:\n  traefik: {}\n  gatus: {}\nhosts: [deploy@host]\n")

        fake_renovate_host.assert_any_call("deploy@host", "~/flightdeck", "traefik")
        fake_renovate_host.assert_any_call("deploy@host", "~/flightdeck", "gatus")
        self.assertEqual(fake_renovate_host.call_count, 2)

    def test_skips_a_target_with_no_apps_when_apps_is_empty(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(renovate, "renovate_host") as fake_renovate_host,
        ):
            outputs = self._run_main(directory, [], "apps: {}\nhosts: [deploy@host]\n")

        fake_renovate_host.assert_not_called()
        self.assertIn("updated=false\n", outputs)

    def test_renovates_only_the_requested_apps_present_on_the_target(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(renovate, "renovate_host", return_value=[]) as fake_renovate_host,
        ):
            self._run_main(
                directory,
                ["traefik", "rybbit", "beszel"],
                "apps:\n  traefik: {}\n  gatus: {}\nhosts: [deploy@host]\n",
            )

        fake_renovate_host.assert_called_once_with("deploy@host", "~/flightdeck", "traefik")

    def test_reports_updated_app_host_pairs_when_the_image_changed(self):
        def fake_renovate_host(host, base_path, app):
            if app == "beszel" and host == "deploy@app1.example.com":
                return [
                    {
                        "service": "beszel",
                        "image": "henrygd/beszel:latest",
                        "before": {"id": "sha256:old", "version": "0.12.8"},
                        "after": {"id": "sha256:new", "version": "0.12.9"},
                    }
                ]
            return []

        manifest = (
            "apps:\n  beszel: {}\n  traefik: {}\n"
            "hosts: [deploy@app1.example.com, deploy@app2.example.com]\npath: ~/flightdeck\n"
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(renovate, "renovate_host", side_effect=fake_renovate_host),
        ):
            outputs = self._run_main(directory, ["beszel", "traefik"], manifest)

        self.assertIn("updated=true\n", outputs)
        self.assertIn("updated_hosts=beszel@deploy@app1.example.com\n", outputs)
        self.assertIn(
            'updated_items=[{"app":"beszel","host":"deploy@app1.example.com","changes":'
            '[{"service":"beszel","image":"henrygd/beszel:latest","before":'
            '{"id":"sha256:old","version":"0.12.8"},"after":'
            '{"id":"sha256:new","version":"0.12.9"}}]}]\n',
            outputs,
        )

    def test_reports_not_updated_when_every_host_was_already_current(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(renovate, "renovate_host", return_value=[]),
        ):
            outputs = self._run_main(directory, ["beszel"], "apps:\n  beszel: {}\nhosts: [deploy@host]\n")

        self.assertIn("updated=false\n", outputs)
        self.assertIn("updated_hosts=\n", outputs)
        self.assertIn("updated_items=[]\n", outputs)

    def test_defaults_path_when_omitted(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(renovate, "renovate_host", return_value=[]) as fake_renovate_host,
        ):
            self._run_main(directory, ["beszel"], "apps:\n  beszel: {}\nhosts: [deploy@host]\n")

        fake_renovate_host.assert_called_once_with("deploy@host", "~/flightdeck", "beszel")

    def test_derives_target_name_from_manifest_filename(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(renovate, "renovate_host", return_value=[]),
        ):
            outputs = self._run_main(
                directory, ["beszel"], "apps:\n  beszel: {}\nhosts: [deploy@host]\n", manifest_name="mainframe"
            )

        self.assertIn("target_name=mainframe\n", outputs)


if __name__ == "__main__":
    unittest.main()
