#!/usr/bin/env python3
"""Push-based deploy: resolve and download release refs here on the runner,
then push the finished release tree and per-app encrypted vault files to
each target host over SSH, and run a short remote command sequence.

Reads a JSON config from stdin (see README's "deploy-shared.yml" section
for the exact shape). Decryption stays strictly server-side - the host's
only vault-related capability is `sops decrypt` on a file it's handed,
plus a dumb `cat` to concatenate multiple decrypted sources for one app.
Ref-resolution, app-bundle merging, and env_refs collision detection all
happen here instead, replacing the copies of this logic ansible/deploy.yml
used to carry once per caller.
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
from collisions import check_env_collisions
from fabric import Connection
from resolve import download_ref

MACHINERY_ASSET = "flightdeck.zip"
APPS_BUNDLE_ASSET = "flightdeck-apps.zip"


class DeployError(Exception):
    pass


def build_release(config, work_dir):
    pull_dir = work_dir / "pull"
    release_dir = work_dir / "release"

    bundle = download_ref(config["app_ref"], pull_dir / "machinery", default_asset=MACHINERY_ASSET)
    release_dir.mkdir(parents=True)
    with ZipFile(bundle) as archive:
        archive.extractall(release_dir)

    apps_dir = release_dir / "apps"
    apps_dir.mkdir(exist_ok=True)

    for index, ref in enumerate(config["app_refs"], start=1):
        package_dir = pull_dir / f"apps-{index}"
        bundle = download_ref(ref, package_dir / "pull", default_asset=APPS_BUNDLE_ASSET)
        extract_dir = package_dir / "extract"
        with ZipFile(bundle) as archive:
            archive.extractall(extract_dir)

        package_apps_dir = extract_dir / "apps"
        if not package_apps_dir.is_dir():
            raise DeployError(f"Package {ref} does not contain apps/")

        for app_path in sorted(package_apps_dir.iterdir()):
            if not app_path.is_dir():
                continue
            target = apps_dir / app_path.name
            if target.exists():
                raise DeployError(f"App conflicts with an existing app: {app_path.name}")
            shutil.copytree(app_path, target)

    return release_dir


def resolve_app_envs(config, work_dir):
    pull_dir = work_dir / "envs"
    app_envs = {}
    for app, app_config in config["apps"].items():
        paths = [
            download_ref(ref, pull_dir / app / str(index))
            for index, ref in enumerate(app_config["env_refs"], start=1)
        ]
        check_env_collisions(paths)
        app_envs[app] = paths
    return app_envs


def archive_release(release_dir, work_dir):
    archive_path = work_dir / "release.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        for entry in sorted(release_dir.iterdir()):
            tar.add(entry, arcname=entry.name)
    return archive_path


def expand_home(path, home):
    return home + path[1:] if path.startswith("~") else path


def push_app_envs(connection, release_path, shared_path, sops_key_file, app_envs):
    vaults_path = f"{shared_path}/vaults-tmp"
    connection.run(f"mkdir -p {shlex.quote(vaults_path)}", hide=True)
    try:
        for app, paths in app_envs.items():
            remote_sources = []
            for index, local_path in enumerate(paths, start=1):
                remote_path = f"{vaults_path}/{app}-{index}.sops.env"
                connection.put(str(local_path), remote=remote_path)
                remote_sources.append(remote_path)

            app_env_path = f"{release_path}/apps/{app}/.env"
            decrypt_steps = " && ".join(
                f"SOPS_AGE_KEY_FILE={shlex.quote(sops_key_file)} sops decrypt {shlex.quote(source)}"
                f" >> {shlex.quote(app_env_path)}.tmp"
                for source in remote_sources
            )
            connection.run(
                f": > {shlex.quote(app_env_path)}.tmp && "
                f"{decrypt_steps} && "
                f"mv {shlex.quote(app_env_path)}.tmp {shlex.quote(app_env_path)} && "
                f"chmod 600 {shlex.quote(app_env_path)}",
                hide=True,
            )
    finally:
        connection.run(f"rm -rf {shlex.quote(vaults_path)}", hide=True)


def prune_releases(connection, releases_path, keep_releases):
    result = connection.run(f"ls -1dt {shlex.quote(releases_path)}/*/ 2>/dev/null || true", hide=True)
    releases = [line.strip().rstrip("/") for line in result.stdout.splitlines() if line.strip()]
    stale = releases[keep_releases:]
    if stale:
        connection.run("rm -rf " + " ".join(shlex.quote(release) for release in stale), hide=True)


def deploy_to_host(host, archive_path, app_envs, config):
    connection = Connection(host)
    connection.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    home = connection.run("echo $HOME", hide=True).stdout.strip()
    base_path = expand_home(config.get("path", "~/flightdeck"), home)
    sops_key_file = expand_home(config.get("sops_age_key_file", "~/.config/sops/age/keys.txt"), home)
    keep_releases = config.get("keep_releases", 5)

    releases_path = f"{base_path}/releases"
    shared_path = f"{base_path}/shared"
    current_path = f"{base_path}/current"
    release_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    release_path = f"{releases_path}/{release_name}"

    connection.run(
        f"mkdir -p {shlex.quote(base_path)} {shlex.quote(releases_path)} {shlex.quote(shared_path)}",
        hide=True,
    )

    connection.run(f"mkdir -p {shlex.quote(release_path)}", hide=True)
    connection.put(str(archive_path), remote=f"{release_path}.tar.gz")
    connection.run(f"tar -xzf {shlex.quote(release_path)}.tar.gz -C {shlex.quote(release_path)}", hide=True)
    connection.run(f"rm -f {shlex.quote(release_path)}.tar.gz", hide=True)

    push_app_envs(connection, release_path, shared_path, sops_key_file, app_envs)

    connection.run(f"ln -sfn {shlex.quote(release_path)} {shlex.quote(current_path)}", hide=True)

    apps = " ".join(shlex.quote(app) for app in app_envs)
    connection.run(f"cd {shlex.quote(current_path)} && FLIGHTDECK_SKIP_ENV_GENERATION=1 ./deploy.sh {apps}")

    prune_releases(connection, releases_path, keep_releases)


def validate_config(config):
    if not config.get("hosts"):
        raise DeployError("Config must set hosts to a non-empty list")
    if not config.get("app_ref"):
        raise DeployError("Config must set app_ref")
    if not config.get("app_refs"):
        raise DeployError("Config must set app_refs to a non-empty list")
    if not config.get("apps"):
        raise DeployError("Config must set apps to a non-empty object")


def main():
    config = json.load(sys.stdin)
    validate_config(config)
    with tempfile.TemporaryDirectory(prefix="flightdeck-deploy-") as raw_dir:
        work_dir = Path(raw_dir)
        release_dir = build_release(config, work_dir)
        app_envs = resolve_app_envs(config, work_dir)
        archive_path = archive_release(release_dir, work_dir)

        for host in config["hosts"]:
            print(f"Deploying to {host}")
            deploy_to_host(host, archive_path, app_envs, config)


if __name__ == "__main__":
    main()
