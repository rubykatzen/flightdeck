#!/usr/bin/env python3
"""Renovate: re-pull and recreate one-or-more apps' containers on one
target, read directly from that target's own targets/*.yml manifest,
without touching versions - no new app bundle, no new vault-sourced env,
no rebuilt release tree. Just `docker compose pull && docker compose
up -d` per requested app, against its already-current release, on each
of the target's hosts.

Unlike deploy/deploy.py, which receives an already-flattened config, this
takes a manifest *path* and parses it itself - the same shape encrypt-env's
render-env.py already uses for vault manifests, rather than flattening a
target's hosts/apps/path into separate inputs the caller has to build.
renovate-shared.yml's own two-job matrix (see README's "Renovate" section)
is what finds every target and resolves its secrets; this script never
reads a directory or touches GitHub Secrets itself.

Reads a JSON config from stdin: {"apps": ["traefik", "rybbit"],
"target_manifest": "targets/heimdall.yml"}. Any requested app that isn't
a key in that manifest's own `apps` mapping is skipped, not an error - a
target-matrix fan-out dispatches to every target regardless of which of
the requested apps it actually runs; skipping all of them there is a
clean no-op.

Writes `updated`/`updated_hosts`/`target_name` to $GITHUB_OUTPUT so the
calling workflow can notify only when a host's image actually changed,
rather than on every run. `updated_hosts` lists `app@host` pairs, since
more than one app may have been renovated in the same run.
"""
import json
import os
import shlex
import sys
from pathlib import Path

import paramiko
import yaml
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
    requested_apps = config["apps"]
    manifest_path = Path(config["target_manifest"])
    target_name = manifest_path.stem
    write_github_output("target_name", target_name)

    target = yaml.safe_load(manifest_path.read_text())
    target_apps = target.get("apps") or {}
    matching_apps = [app for app in requested_apps if app in target_apps]
    if not matching_apps:
        print(f"none of {requested_apps} are deployed on target {target_name!r}, skipping")
        write_github_output("updated", "false")
        return

    base_path = target.get("path", "~/flightdeck")
    updated = []
    for app in matching_apps:
        for host in target["hosts"]:
            print(f"Renovating {app} on {host}")
            if renovate_host(host, base_path, app):
                updated.append(f"{app}@{host}")

    write_github_output("updated", "true" if updated else "false")
    write_github_output("updated_hosts", ",".join(updated))


if __name__ == "__main__":
    main()
