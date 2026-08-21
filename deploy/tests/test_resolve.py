import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).resolve().parents[1] / "resolve.py"
SPEC = importlib.util.spec_from_file_location("resolve", MODULE_PATH)
resolve = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resolve)


def fake_run(calls, results):
    def run(cmd, **kwargs):
        calls.append(cmd)
        return results.pop(0)

    return run


def ok(stdout=""):
    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def fail(stderr="boom"):
    return SimpleNamespace(returncode=1, stdout="", stderr=stderr)


class ParseRefTest(unittest.TestCase):
    def test_parses_explicit_asset(self):
        resolved = resolve.parse_ref("owner/repo@v1.2.3:thing.zip")
        self.assertEqual(resolved.repo, "owner/repo")
        self.assertEqual(resolved.tag, "v1.2.3")
        self.assertEqual(resolved.asset, "thing.zip")

    def test_applies_default_asset(self):
        resolved = resolve.parse_ref("owner/repo@latest", default_asset="flightdeck.zip")
        self.assertEqual(resolved.asset, "flightdeck.zip")

    def test_explicit_asset_overrides_default(self):
        resolved = resolve.parse_ref("owner/repo@latest:custom.zip", default_asset="flightdeck.zip")
        self.assertEqual(resolved.asset, "custom.zip")

    def test_rejects_missing_at(self):
        with self.assertRaises(resolve.RefError):
            resolve.parse_ref("owner/repo-v1.2.3")

    def test_rejects_missing_asset_and_default(self):
        with self.assertRaises(resolve.RefError):
            resolve.parse_ref("owner/repo@v1.2.3")

    def test_rejects_empty_tag(self):
        with self.assertRaises(resolve.RefError):
            resolve.parse_ref("owner/repo@", default_asset="a.zip")


class ResolveLatestTest(unittest.TestCase):
    def test_resolves_tag(self):
        calls = []
        run = fake_run(calls, [ok("v1.2.3\n")])
        tag = resolve.resolve_latest("owner/repo", run=run)
        self.assertEqual(tag, "v1.2.3")
        self.assertIn("release", calls[0])
        self.assertIn("view", calls[0])

    def test_raises_on_null(self):
        calls = []
        run = fake_run(calls, [ok("null\n")])
        with self.assertRaises(resolve.RefError):
            resolve.resolve_latest("owner/repo", run=run)

    def test_raises_on_failure(self):
        calls = []
        run = fake_run(calls, [fail("no releases")])
        with self.assertRaises(resolve.RefError):
            resolve.resolve_latest("owner/repo", run=run)


class DownloadRefTest(unittest.TestCase):
    def test_downloads_pinned_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            asset = out / "thing.zip"

            def run(cmd, **kwargs):
                if "download" in cmd:
                    asset.write_text("data")
                return ok()

            path = resolve.download_ref("owner/repo@v1.2.3:thing.zip", out, run=run)
            self.assertEqual(path, asset)
            self.assertTrue(path.is_file())

    def test_resolves_latest_before_download(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            asset = out / "flightdeck.zip"
            calls = []

            def run(cmd, **kwargs):
                calls.append(cmd)
                if "view" in cmd:
                    return ok("v9.9.9\n")
                asset.write_text("data")
                return ok()

            resolve.download_ref("owner/repo@latest", out, default_asset="flightdeck.zip", run=run)
            download_call = [c for c in calls if "download" in c][0]
            self.assertIn("v9.9.9", download_call)

    def test_raises_when_asset_missing_after_download(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)

            def run(cmd, **kwargs):
                return ok()  # succeeds but never writes the file

            with self.assertRaises(resolve.RefError):
                resolve.download_ref("owner/repo@v1.2.3:thing.zip", out, run=run)

    def test_raises_on_download_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)

            def run(cmd, **kwargs):
                return fail("not found")

            with self.assertRaises(resolve.RefError):
                resolve.download_ref("owner/repo@v1.2.3:thing.zip", out, run=run)


if __name__ == "__main__":
    unittest.main()
