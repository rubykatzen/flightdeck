#!/usr/bin/env python3
"""Detect duplicate env keys across an app's env_refs sources, from ciphertext.

SOPS's dotenv output format only encrypts values, not key names
(`DOMAIN=ENC[...]`), so this needs no decryption at all - it runs in
CI, before anything is pushed to the target host, on files whose private
key CI never has access to in the first place.
"""
from pathlib import Path


class CollisionError(Exception):
    pass


def extract_keys(sops_env_path):
    keys = set()
    for line in Path(sops_env_path).read_text().splitlines():
        if "=" not in line:
            continue
        key = line.split("=", 1)[0]
        if not key or key.startswith("sops_"):
            continue
        keys.add(key)
    return keys


def check_env_collisions(sops_env_paths):
    seen = {}
    for path in sops_env_paths:
        for key in extract_keys(path):
            if key in seen:
                raise CollisionError(
                    f"Env key conflicts with an existing source: {key} "
                    f"(in {seen[key]} and {path})"
                )
            seen[key] = path
