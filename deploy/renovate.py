#!/usr/bin/env python3
"""Renovate: re-pull and recreate one app's containers on one already-
resolved target, without touching versions - no new app bundle, no new
vault-sourced env, no rebuilt release tree. Just `docker compose pull &&
docker compose up -d` against that app's already-current release on each
of the target's hosts.

One invocation is scoped to one target, same as deploy/deploy.py - the
matrix fan-out across every target under a directory, and per-target
secret/Tailscale resolution, live in renovate-shared.yml's own two-job
matrix (see README's "Renovate" section), not here. This script doesn't
know about targets/ or GitHub Secrets at all.

Reads a JSON config from stdin: {"app": "<name>", "hosts": [...], "path":
"...", "apps": {...}}. `apps` is this one target's own `apps` mapping, as
declared in its targets/*.yml manifest - since the matrix fans out to
every target regardless of whether it actually runs the requested app,
`app` not being a key in it just means this target is a clean no-op, not
an error.
"""
import json
import shlex
import sys

import paramiko
from fabric import Connection


def expand_home(path, home):
    return home + path[1:] if path.startswith("~") else path


def renovate_host(host, base_path, app):
    connection = Connection(host)
    connection.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    home = connection.run("echo $HOME", hide=True).stdout.strip()
    compose_dir = f"{expand_home(base_path, home)}/current/apps/{app}"
    connection.run(f"cd {shlex.quote(compose_dir)} && docker compose pull && docker compose up -d --remove-orphans")


def main():
    config = json.load(sys.stdin)
    app = config["app"]
    apps = config.get("apps") or {}
    if app not in apps:
        print(f"{app!r} is not deployed on this target, skipping")
        return

    base_path = config.get("path", "~/flightdeck")
    for host in config["hosts"]:
        print(f"Renovating {app} on {host}")
        renovate_host(host, base_path, app)


if __name__ == "__main__":
    main()
