import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ACTION_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = ACTION_DIR / "prepare.py"
SPEC = importlib.util.spec_from_file_location("prepare_telegram_operation_message", MODULE_PATH)
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


class FormatMessageTest(unittest.TestCase):
    def test_formats_deploy_header(self):
        message = prepare.format_message(
            "dupmachine/flightdeck",
            "deploy",
            "mainframe",
            "https://github.com/dupmachine/flightdeck/actions/runs/123",
        )

        self.assertEqual(
            message,
            "*dupmachine/flightdeck* · "
            "[deploy](https://github.com/dupmachine/flightdeck/actions/runs/123) completed · "
            "*mainframe*",
        )

    def test_groups_renovated_apps_by_host(self):
        message = prepare.format_message(
            "dupmachine/flightdeck",
            "renovate",
            "hawkeye",
            "https://github.com/dupmachine/flightdeck/actions/runs/123",
            [
                {"app": "gatus", "host": "root@100.75.50.2"},
                {"app": "yamtrack", "host": "root@100.75.50.2"},
                {"app": "sure", "host": "deploy@app2.example.com"},
            ],
        )

        self.assertEqual(
            message,
            "*dupmachine/flightdeck* · "
            "[renovate](https://github.com/dupmachine/flightdeck/actions/runs/123) completed · "
            "*hawkeye*\n\n"
            "*root@100\\.75\\.50\\.2*\n"
            "• gatus\n"
            "• yamtrack\n\n"
            "*deploy@app2\\.example\\.com*\n"
            "• sure",
        )

    def test_escapes_dynamic_markdown(self):
        message = prepare.format_message(
            "owner/repo_test",
            "deploy-now",
            "prod.main",
            "https://example.com/run/1)",
            [{"app": "api_v2", "host": "root@host.example"}],
        )

        self.assertEqual(
            message,
            "*owner/repo\\_test* · [deploy\\-now](https://example.com/run/1\\)) completed · "
            "*prod\\.main*\n\n*root@host\\.example*\n• api\\_v2",
        )

    def test_rejects_unstructured_items(self):
        with self.assertRaisesRegex(ValueError, "items must be a JSON array"):
            prepare.format_message("owner/repo", "renovate", "target", "https://example.com", {"app": "gatus"})

    def test_rejects_empty_object_items(self):
        with self.assertRaisesRegex(ValueError, "items must be a JSON array"):
            prepare.format_message("owner/repo", "renovate", "target", "https://example.com", {})

    def test_truncates_an_oversized_item_list(self):
        items = [{"app": f"app-{index}-" + "x" * 100, "host": "root@host"} for index in range(100)]

        message = prepare.format_message("owner/repo", "renovate", "target", "https://example.com", items)

        self.assertLessEqual(len(message), prepare.TELEGRAM_MESSAGE_LIMIT)
        self.assertRegex(message, r"…and \d+ more$")


class MainTest(unittest.TestCase):
    def test_writes_multiline_message_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "output"
            environment = {
                "GITHUB_OUTPUT": str(output_path),
                "REPOSITORY": "dupmachine/flightdeck",
                "OPERATION": "renovate",
                "TARGET": "hawkeye",
                "RUN_URL": "https://github.com/dupmachine/flightdeck/actions/runs/123",
                "ITEMS": json.dumps([{"app": "gatus", "host": "root@host"}]),
            }
            with patch.dict(os.environ, environment, clear=True):
                prepare.main()

            output = output_path.read_text()

        self.assertIn("message<<ghdelim_", output)
        self.assertIn("*dupmachine/flightdeck*", output)
        self.assertIn("*root@host*\n• gatus", output)


if __name__ == "__main__":
    unittest.main()
