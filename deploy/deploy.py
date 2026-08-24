#!/usr/bin/env python3
"""Push-based deploy: resolve, download, decrypt, and render everything
here on the runner, then push a fully finished release tree - real
plaintext `.env` files and already-rendered config - to each target host
over SSH, and run a short remote command sequence. The target host needs
nothing but Docker and Docker Compose: no sops, no age key, no gh, no
flightdeck scripts of any kind.

Reads a JSON config from stdin (see README's "deploy-shared.yml" section
for the exact shape).
"""
import json
import shlex
import shutil
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import paramiko
import yaml
from collisions import check_env_collisions
from fabric import Connection
from render import render_template
from resolve import download_ref
from vault import decrypt_env, parse_dotenv

APPS_BUNDLE_ASSET = "flightdeck-apps.zip"


class DeployError(Exception):
    pass


def build_release(config, work_dir):
    pull_dir = work_dir / "pull"
    release_dir = work_dir / "release"
    apps_dir = release_dir / "apps"
    apps_dir.mkdir(parents=True)

    for index, ref in enumerate(config["app_refs"], start=1):
        package_dir = pull_dir / f"apps-{index}"
        bundle = download_ref(ref, package_dir / "pull", default_asset=APPS_BUNDLE_ASSET)
        extract_dir = package_dir / "extract"
        with ZipFile(bundle) as archive:
            archive.extractall(extract_dir)

        package_apps_dir = extract_dir / "apps"
        if not package_apps_dir.is_dir():
            raise DeployError(f"Package {ref} does not contain apps/")

        for entry in sorted(package_apps_dir.iterdir()):
            target = apps_dir / entry.name
            if target.exists():
                raise DeployError(f"App conflicts with an existing app: {entry.name}")
            if entry.is_dir():
                shutil.copytree(entry, target)
            else:
                shutil.copy2(entry, target)

    return release_dir


def render_app_configs(release_dir, app, values):
    app_dir = release_dir / "apps" / app
    for template in sorted(app_dir.glob("*.tpl")):
        rendered_path = template.with_name(template.stem)
        rendered_path.write_text(render_template(template.read_text(), values))
        rendered_path.chmod(0o600)


def resolve_app_envs(config, work_dir, release_dir, age_key_file):
    pull_dir = work_dir / "envs"
    for app, app_config in config["apps"].items():
        paths = [
            download_ref(ref, pull_dir / app / str(index))
            for index, ref in enumerate(app_config["env_refs"], start=1)
        ]
        check_env_collisions(paths)

        plaintext = f"APP_NAME={app}\n" + "".join(decrypt_env(path, age_key_file) for path in paths)
        app_env_path = release_dir / "apps" / app / ".env"
        app_env_path.write_text(plaintext)
        app_env_path.chmod(0o600)

        render_app_configs(release_dir, app, parse_dotenv(plaintext))


def list_required_networks(release_dir):
    manifest = yaml.safe_load((release_dir / "apps" / "networks.yml").read_text())
    return [
        name
        for name, definition in (manifest.get("networks") or {}).items()
        if isinstance(definition, dict) and definition.get("external")
    ]


def archive_release(release_dir, work_dir):
    archive_path = work_dir / "release.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        for entry in sorted(release_dir.iterdir()):
            tar.add(entry, arcname=entry.name)
    return archive_path


def expand_home(path, home):
    return home + path[1:] if path.startswith("~") else path


def bootstrap_host(connection, base_path, networks):
    connection.run(f"mkdir -p {shlex.quote(base_path)}/releases", hide=True)
    for network in networks:
        connection.run(f"docker network create {shlex.quote(network)} >/dev/null 2>&1 || true", hide=True)


def push_release(connection, archive_path, release_path):
    connection.run(f"mkdir -p {shlex.quote(release_path)}", hide=True)
    connection.put(str(archive_path), remote=f"{release_path}.tar.gz")
    connection.run(f"tar -xzf {shlex.quote(release_path)}.tar.gz -C {shlex.quote(release_path)}", hide=True)
    connection.run(f"rm -f {shlex.quote(release_path)}.tar.gz", hide=True)
    connection.run(f"chmod 600 {shlex.quote(release_path)}/apps/*/.env", hide=True)


def prune_releases(connection, releases_path, keep_releases):
    result = connection.run(f"ls -1dt {shlex.quote(releases_path)}/*/ 2>/dev/null || true", hide=True)
    releases = [line.strip().rstrip("/") for line in result.stdout.splitlines() if line.strip()]
    stale = releases[keep_releases:]
    if stale:
        connection.run("rm -rf " + " ".join(shlex.quote(release) for release in stale), hide=True)


def deploy_to_host(host, archive_path, apps, networks, config):
    connection = Connection(host)
    connection.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    home = connection.run("echo $HOME", hide=True).stdout.strip()
    base_path = expand_home(config.get("path", "~/flightdeck"), home)
    keep_releases = config.get("keep_releases", 5)

    releases_path = f"{base_path}/releases"
    current_path = f"{base_path}/current"
    release_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    release_path = f"{releases_path}/{release_name}"

    bootstrap_host(connection, base_path, networks)
    push_release(connection, archive_path, release_path)
    for app in apps:
        data_dir = f"{base_path}/apps-data/{app}"
        connection.run(f"mkdir -p {shlex.quote(data_dir)}", hide=True)
        env_path = f"{release_path}/apps/{app}/.env"
        connection.run(f"echo {shlex.quote(f'DATA_DIR={data_dir}')} >> {shlex.quote(env_path)}", hide=True)

    connection.run(f"ln -sfn {shlex.quote(release_path)} {shlex.quote(current_path)}", hide=True)

    for app in apps:
        compose_dir = f"{current_path}/apps/{app}"
        connection.run(f"cd {shlex.quote(compose_dir)} && docker compose pull && docker compose up -d --remove-orphans")

    prune_releases(connection, releases_path, keep_releases)
    connection.run("docker container prune -f && docker image prune -a -f")


def validate_config(config):
    if not config.get("hosts"):
        raise DeployError("Config must set hosts to a non-empty list")
    if not config.get("app_refs"):
        raise DeployError("Config must set app_refs to a non-empty list")
    if not config.get("apps"):
        raise DeployError("Config must set apps to a non-empty object")
    if not config.get("sops_age_key"):
        raise DeployError("Config must set sops_age_key")


def main():
    config = json.load(sys.stdin)
    validate_config(config)
    with tempfile.TemporaryDirectory(prefix="flightdeck-deploy-") as raw_dir:
        work_dir = Path(raw_dir)

        age_key_file = work_dir / "age-key.txt"
        age_key_file.write_text(config["sops_age_key"])
        age_key_file.chmod(0o600)

        release_dir = build_release(config, work_dir)
        resolve_app_envs(config, work_dir, release_dir, age_key_file)
        archive_path = archive_release(release_dir, work_dir)
        networks = list_required_networks(release_dir)

        apps = list(config["apps"])

        for host in config["hosts"]:
            print(f"Deploying to {host}")
            deploy_to_host(host, archive_path, apps, networks, config)


if __name__ == "__main__":
    main()
