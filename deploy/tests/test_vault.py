import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).resolve().parents[1] / "vault.py"
SPEC = importlib.util.spec_from_file_location("vault", MODULE_PATH)
vault = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vault)


def fake_run(calls, results):
    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return results.pop(0)

    return run


def ok(stdout=""):
    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def fail(stderr="boom"):
    return SimpleNamespace(returncode=1, stdout="", stderr=stderr)


class DecryptEnvTest(unittest.TestCase):
    def test_returns_decrypted_stdout(self):
        calls = []
        run = fake_run(calls, [ok("DOMAIN=example.com\n")])
        plaintext = vault.decrypt_env("traefik.sops.env", "/tmp/key.txt", run=run)
        self.assertEqual(plaintext, "DOMAIN=example.com\n")

    def test_passes_sops_decrypt_dotenv_args(self):
        calls = []
        run = fake_run(calls, [ok()])
        vault.decrypt_env("traefik.sops.env", "/tmp/key.txt", run=run)
        cmd, kwargs = calls[0]
        self.assertEqual(cmd, ["sops", "decrypt", "--input-type", "dotenv", "--output-type", "dotenv", "traefik.sops.env"])
        self.assertEqual(kwargs["env"]["SOPS_AGE_KEY_FILE"], "/tmp/key.txt")

    def test_raises_on_failure(self):
        calls = []
        run = fake_run(calls, [fail("no matching key found")])
        with self.assertRaises(vault.VaultError):
            vault.decrypt_env("traefik.sops.env", "/tmp/key.txt", run=run)


class ParseDotenvTest(unittest.TestCase):
    def test_parses_key_value_pairs(self):
        values = vault.parse_dotenv("DOMAIN=example.com\nHTTP_PORT=80\n")
        self.assertEqual(values, {"DOMAIN": "example.com", "HTTP_PORT": "80"})

    def test_splits_only_on_first_equals(self):
        values = vault.parse_dotenv("HTPASSWD=user:pass=word\n")
        self.assertEqual(values["HTPASSWD"], "user:pass=word")

    def test_ignores_lines_without_equals(self):
        values = vault.parse_dotenv("not a valid line\nDOMAIN=example.com\n")
        self.assertEqual(values, {"DOMAIN": "example.com"})

    def test_ignores_blank_lines(self):
        values = vault.parse_dotenv("\n\nDOMAIN=example.com\n")
        self.assertEqual(values, {"DOMAIN": "example.com"})


if __name__ == "__main__":
    unittest.main()
