import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "collisions.py"
SPEC = importlib.util.spec_from_file_location("collisions", MODULE_PATH)
collisions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collisions)


TRAEFIK_ENV = """\
HTTP_PORT=ENC[AES256_GCM,data:Ab==,iv:xx==,tag:yy==,type:str]
HTTPS_PORT=ENC[AES256_GCM,data:Cd==,iv:xx==,tag:yy==,type:str]
DOMAIN=ENC[AES256_GCM,data:Ef==,iv:xx==,tag:yy==,type:str]
sops_age__list_0__map_enc=-----BEGIN AGE ENCRYPTED FILE-----
sops_lastmodified=2026-08-19T00:00:00Z
sops_mac=ENC[AES256_GCM,data:Gh==,iv:xx==,tag:yy==,type:str]
sops_version=3.13.1
"""

RYBBIT_ENV = """\
DATABASE_PASSWORD=ENC[AES256_GCM,data:Ij==,iv:xx==,tag:yy==,type:str]
KEY_HEX_32=ENC[AES256_GCM,data:Kl==,iv:xx==,tag:yy==,type:str]
sops_lastmodified=2026-08-19T00:00:00Z
sops_version=3.13.1
"""

COLLIDING_ENV = """\
DOMAIN=ENC[AES256_GCM,data:Mn==,iv:xx==,tag:yy==,type:str]
sops_version=3.13.1
"""


def write(directory, name, content):
    path = Path(directory) / name
    path.write_text(content)
    return path


class CheckEnvCollisionsTest(unittest.TestCase):
    def test_no_collision_across_clean_files(self):
        with tempfile.TemporaryDirectory() as directory:
            traefik = write(directory, "traefik.sops.env", TRAEFIK_ENV)
            rybbit = write(directory, "rybbit.sops.env", RYBBIT_ENV)
            collisions.check_env_collisions([traefik, rybbit])  # does not raise

    def test_raises_on_real_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            traefik = write(directory, "traefik.sops.env", TRAEFIK_ENV)
            colliding = write(directory, "colliding.sops.env", COLLIDING_ENV)
            with self.assertRaises(collisions.CollisionError):
                collisions.check_env_collisions([traefik, colliding])

    def test_ignores_sops_metadata_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            traefik = write(directory, "traefik.sops.env", TRAEFIK_ENV)
            rybbit = write(directory, "rybbit.sops.env", RYBBIT_ENV)
            keys = collisions.extract_keys(traefik) | collisions.extract_keys(rybbit)
            self.assertFalse(any(key.startswith("sops_") for key in keys))
            self.assertIn("HTTP_PORT", keys)
            self.assertIn("KEY_HEX_32", keys)


if __name__ == "__main__":
    unittest.main()
