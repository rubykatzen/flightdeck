#!/usr/bin/env python3
"""Renovate: re-pull and recreate one app's containers, wherever it's
already deployed, without touching versions - no new app bundle, no new
vault-sourced env, no rebuilt release tree. Just `docker compose pull &&
docker compose up -d` against that app's already-current release on each
matching target host.

Unlike deploy/deploy.py (one target per invocation, resolved by the
caller's own GitHub Actions matrix), this reads every target manifest
under a directory itself and finds which ones run the given app - the
input is a directory, not a pre-resolved single target's config. See
README's "Renovate (prototype)" section for the exact contract.

Reads a JSON config from stdin: {"app": "<name>", "targets_directory": "targets"}.
Needs GITHUB_SECRETS_JSON in the environment to resolve each matched
target's `credentials.secrets.ssh_private_key` GitHub Secret name to its
actual value - there's no per-target workflow_call here to do that ahead
of time.
"""
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import paramiko
import yaml
from fabric import Connection


class RenovateError(Exception):
    pass


def load_targets(directory):
    directory = Path(directory)
    paths = sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))
    if not paths:
        raise RenovateError(f"no target manifests found in {directory}")
    return [(path.stem, yaml.safe_load(path.read_text())) for path in paths]


def find_matching_targets(targets, app):
    return [(name, manifest) for name, manifest in targets if app in (manifest.get("apps") or {})]


def resolve_secret(secrets, name):
    if name not in secrets:
        raise RenovateError(f"GitHub Secret not found: {name}")
    return secrets[name]


def load_ssh_key(secrets, secret_name, run=subprocess.run):
    key_text = resolve_secret(secrets, secret_name)
    result = run(["ssh-add", "-"], input=key_text, capture_output=True, text=True)
    if result.returncode != 0:
        raise RenovateError(f"Failed to load SSH key {secret_name}: {result.stderr.strip()}")


def expand_home(path, home):
    return home + path[1:] if path.startswith("~") else path


def renovate_host(host, base_path, app):
    connection = Connection(host)
    connection.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    home = connection.run("echo $HOME", hide=True).stdout.strip()
    compose_dir = f"{expand_home(base_path, home)}/current/apps/{app}"
    connection.run(f"cd {shlex.quote(compose_dir)} && docker compose pull && docker compose up -d --remove-orphans")


def renovate_target(name, manifest, app, secrets, run=subprocess.run):
    ssh_secret_name = manifest["credentials"]["secrets"]["ssh_private_key"]
    load_ssh_key(secrets, ssh_secret_name, run=run)
    base_path = manifest.get("path", "~/flightdeck")
    for host in manifest["hosts"]:
        print(f"Renovating {app} on {name} ({host})")
        renovate_host(host, base_path, app)


def main():
    config = json.load(sys.stdin)
    app = config["app"]
    targets_directory = config.get("targets_directory", "targets")
    secrets = json.loads(os.environ["GITHUB_SECRETS_JSON"])

    targets = load_targets(targets_directory)
    matches = find_matching_targets(targets, app)
    if not matches:
        raise RenovateError(f"app {app!r} not found in any target manifest under {targets_directory}")

    for name, manifest in matches:
        renovate_target(name, manifest, app, secrets)


if __name__ == "__main__":
    main()
