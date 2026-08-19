#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

MANIFEST_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
SOURCE_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*(?:__[A-Z0-9_]+)*$")
KEY_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
APP_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SSH_DESTINATION_RE = re.compile(
    r"^(?P<user>[a-z_][a-z0-9_-]*)@(?P<host>[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)$"
)
RELEASE_REF_RE = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)?$"
)
ENV_REF_RE = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+\.sops\.env$"
)
ASSET_RE = re.compile(r"^[A-Za-z0-9_.-]+\.sops\.env$")


class ManifestError(Exception):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def construct_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ManifestError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_mapping,
)


def require_mapping(value, location):
    if not isinstance(value, dict):
        raise ManifestError(f"{location} must be a mapping")
    return value


def reject_unknown(mapping, allowed, location):
    unknown = sorted(set(mapping) - set(allowed))
    if unknown:
        raise ManifestError(f"{location} contains unknown keys: {', '.join(unknown)}")


def require_string(mapping, key, location, default=None):
    value = mapping.get(key, default)
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{location}.{key} must be a non-empty string")
    return value


def validate_encrypt(value, location):
    encrypt = require_mapping(value, location)
    reject_unknown(encrypt, {"asset", "keys", "apps", "env"}, location)
    asset = require_string(encrypt, "asset", location)
    if not ASSET_RE.fullmatch(asset):
        raise ManifestError(f"{location}.asset must be named like server.sops.env")
    keys = encrypt.get("keys")
    if not isinstance(keys, list) or not keys:
        raise ManifestError(f"{location}.keys must be a non-empty array")
    if any(not isinstance(key, str) or not KEY_NAME_RE.fullmatch(key) for key in keys):
        raise ManifestError(f"{location}.keys contains an invalid age key name")
    apps = encrypt.get("apps")
    if not isinstance(apps, list) or not apps:
        raise ManifestError(f"{location}.apps must be a non-empty array")
    if any(not isinstance(app, str) or not APP_NAME_RE.fullmatch(app) for app in apps):
        raise ManifestError(f"{location}.apps contains an invalid app name")
    if len(apps) != len(set(apps)):
        raise ManifestError(f"{location}.apps contains duplicate app names")
    env = require_mapping(encrypt.get("env"), f"{location}.env")
    if not env:
        raise ManifestError(f"{location}.env must not be empty")
    for output_name, source_name in env.items():
        if not isinstance(output_name, str) or not ENV_NAME_RE.fullmatch(output_name):
            raise ManifestError(f"{location}.env contains an invalid output name: {output_name!r}")
        if not isinstance(source_name, str) or not SOURCE_NAME_RE.fullmatch(source_name):
            raise ManifestError(f"{location}.env.{output_name} has an invalid source name")
    if "APPS" in env:
        raise ManifestError(f"{location}.env.APPS must be configured through {location}.apps")
    return {"asset": asset}


def validate_credentials(value, location):
    credentials = require_mapping(value, location)
    reject_unknown(credentials, {"variables", "secrets"}, location)
    variables = require_mapping(credentials.get("variables", {}), f"{location}.variables")
    secrets = require_mapping(credentials.get("secrets"), f"{location}.secrets")
    reject_unknown(variables, {"tailscale_oauth_client_id"}, f"{location}.variables")
    reject_unknown(
        secrets,
        {"ssh_private_key", "tailscale_oauth_secret"},
        f"{location}.secrets",
    )
    ssh_private_key = require_string(secrets, "ssh_private_key", f"{location}.secrets")
    client_id = variables.get("tailscale_oauth_client_id", "")
    client_secret = secrets.get("tailscale_oauth_secret", "")
    for name, value_name in (
        ("tailscale_oauth_client_id", client_id),
        ("tailscale_oauth_secret", client_secret),
    ):
        if not isinstance(value_name, str):
            raise ManifestError(f"{location}.{name} must be a string")
    if bool(client_id) != bool(client_secret):
        raise ManifestError(f"{location} must configure both Tailscale OAuth names or neither")
    return {
        "ssh_private_key_secret": ssh_private_key,
        "tailscale_oauth_client_id_variable": client_id,
        "tailscale_oauth_secret": client_secret,
    }


def validate_deploy(value, location):
    deploy = require_mapping(value, location)
    reject_unknown(
        deploy,
        {
            "flightdeck_ref",
            "env_ref",
            "extra_refs",
            "hosts",
            "path",
            "sops_age_key_file",
            "credentials",
            "keep_releases",
        },
        location,
    )
    flightdeck_ref = require_string(deploy, "flightdeck_ref", location)
    env_ref = require_string(deploy, "env_ref", location)
    if not RELEASE_REF_RE.fullmatch(flightdeck_ref):
        raise ManifestError(f"{location}.flightdeck_ref must be in owner/repo@tag format")
    if not ENV_REF_RE.fullmatch(env_ref):
        raise ManifestError(f"{location}.env_ref must be in owner/repo@tag:asset.sops.env format")
    extra_refs = deploy.get("extra_refs", [])
    if not isinstance(extra_refs, list):
        raise ManifestError(f"{location}.extra_refs must be an array")
    if any(not isinstance(ref, str) or not RELEASE_REF_RE.fullmatch(ref) for ref in extra_refs):
        raise ManifestError(f"{location}.extra_refs contains an invalid release ref")
    keep_releases = deploy.get("keep_releases", 5)
    if not isinstance(keep_releases, int) or isinstance(keep_releases, bool) or keep_releases < 1:
        raise ManifestError(f"{location}.keep_releases must be a positive integer")
    hosts = deploy.get("hosts")
    if not isinstance(hosts, list) or not hosts:
        raise ManifestError(f"{location}.hosts must be a non-empty array")
    destinations = []
    for destination in hosts:
        if not isinstance(destination, str) or not SSH_DESTINATION_RE.fullmatch(destination):
            raise ManifestError(f"{location}.hosts contains an invalid user@host destination")
        destinations.append(SSH_DESTINATION_RE.fullmatch(destination).group("host"))
    if len(destinations) != len(set(destinations)):
        raise ManifestError(f"{location}.hosts contains duplicate host addresses")
    path = require_string(deploy, "path", location, "~/flightdeck")
    sops_key_file = require_string(
        deploy,
        "sops_age_key_file",
        location,
        "~/.config/sops/age/keys.txt",
    )
    result = {
        "flightdeck_ref": flightdeck_ref,
        "env_ref": env_ref,
        "extra_refs": extra_refs,
        "hosts": hosts,
        "path": path,
        "keep_releases": keep_releases,
        "sops_age_key_file": sops_key_file,
    }
    result.update(validate_credentials(deploy.get("credentials"), f"{location}.credentials"))
    return result


def load_config(path, mode):
    try:
        value = yaml.load(path.read_text(), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ManifestError(f"{path} is not valid YAML: {exc}") from exc
    config = require_mapping(value, str(path))
    if mode == "encrypt":
        return validate_encrypt(config, str(path))
    return validate_deploy(config, str(path))


def build_matrix(directory, mode, selected="all"):
    if mode not in {"encrypt", "deploy"}:
        raise ManifestError("mode must be encrypt or deploy")
    paths = sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))
    if not paths:
        raise ManifestError(f"no manifests found in {directory}")
    names = {path.stem for path in paths}
    if selected != "all" and selected not in names:
        raise ManifestError(f"unknown name: {selected}")
    include = []
    seen_names = set()
    for path in paths:
        name = path.stem
        if not MANIFEST_NAME_RE.fullmatch(name):
            raise ManifestError(f"invalid manifest filename: {path.name}")
        if name in seen_names:
            raise ManifestError(f"duplicate manifest name: {name}")
        seen_names.add(name)
        config = load_config(path, mode)
        if selected != "all" and name != selected:
            continue
        item = {"name": name, "manifest": str(path)}
        item.update(config)
        include.append(item)
    return {"include": include}


def write_github_output(name, value):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--name", default="all")
    args = parser.parse_args(argv)
    try:
        directory = args.directory or Path("encrypt" if args.mode == "encrypt" else "targets")
        matrix = build_matrix(directory, args.mode, args.name)
        encoded = json.dumps(matrix, separators=(",", ":"))
        write_github_output("matrix", encoded)
        write_github_output("count", len(matrix["include"]))
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
