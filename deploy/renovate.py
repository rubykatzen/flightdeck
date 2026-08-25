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

Writes `updated`/`updated_hosts` to $GITHUB_OUTPUT so the calling
workflow can notify only when a host's image actually changed, rather
than on every run.
"""
import json
import os
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
    compose_dir = shlex.quote(f"{expand_home(base_path, home)}/current/apps/{app}")
    command = (
        f"cd {compose_dir} && before=$(docker compose images -q) && docker compose pull "
        f'&& after=$(docker compose images -q) && docker compose up -d --remove-orphans '
        f'&& if [ "$before" != "$after" ]; then echo RENOVATE_UPDATED; fi'
    )
    result = connection.run(command)
    return "RENOVATE_UPDATED" in result.stdout


def write_github_output(name, value):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def main():
    config = json.load(sys.stdin)
    app = config["app"]
    apps = config.get("apps") or {}
    if app not in apps:
        print(f"{app!r} is not deployed on this target, skipping")
        write_github_output("updated", "false")
        return

    base_path = config.get("path", "~/flightdeck")
    updated_hosts = []
    for host in config["hosts"]:
        print(f"Renovating {app} on {host}")
        if renovate_host(host, base_path, app):
            updated_hosts.append(host)

    write_github_output("updated", "true" if updated_hosts else "false")
    write_github_output("updated_hosts", ",".join(updated_hosts))


if __name__ == "__main__":
    main()
