#!/usr/bin/env python3
"""Decrypt SOPS-encrypted dotenv vault assets on the runner.

Symmetric counterpart to encrypt-env/action.yml's `sops encrypt` call -
same dotenv input/output type, same tool, just decrypt instead of encrypt.
"""
import os
import subprocess


class VaultError(Exception):
    pass


def decrypt_env(sops_env_path, age_key_file, run=subprocess.run):
    result = run(
        ["sops", "decrypt", "--input-type", "dotenv", "--output-type", "dotenv", str(sops_env_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "SOPS_AGE_KEY_FILE": str(age_key_file)},
    )
    if result.returncode != 0:
        raise VaultError(f"Failed to decrypt {sops_env_path}: {result.stderr.strip()}")
    return result.stdout


def parse_dotenv(text):
    values = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if not key:
            continue
        values[key] = value
    return values
