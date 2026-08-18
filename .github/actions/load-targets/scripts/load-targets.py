#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

TARGET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
SOURCE_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*(?:__[A-Z0-9_]+)*$")
KEY_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RELEASE_REF_RE = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)?$"
)
ENV_REF_RE = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+\.sops\.env$"
)
ASSET_RE = re.compile(r"^[A-Za-z0-9_.-]+\.sops\.env$")


class TargetError(Exception):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def construct_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise TargetError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_mapping,
)


def require_mapping(value, location):
    if not isinstance(value, dict):
        raise TargetError(f"{location} must be a mapping")
    return value


def reject_unknown(mapping, allowed, location):
    unknown = sorted(set(mapping) - set(allowed))
    if unknown:
        raise TargetError(f"{location} contains unknown keys: {', '.join(unknown)}")


def require_string(mapping, key, location, default=None):
    value = mapping.get(key, default)
    if not isinstance(value, str) or not value:
        raise TargetError(f"{location}.{key} must be a non-empty string")
    return value


def validate_encrypt(value, location):
    encrypt = require_mapping(value, location)
    reject_unknown(encrypt, {"asset", "keys", "env"}, location)
    asset = require_string(encrypt, "asset", location)
    if not ASSET_RE.fullmatch(asset):
        raise TargetError(f"{location}.asset must be named like server.sops.env")
    keys = encrypt.get("keys")
    if not isinstance(keys, list) or not keys:
        raise TargetError(f"{location}.keys must be a non-empty array")
    if any(not isinstance(key, str) or not KEY_NAME_RE.fullmatch(key) for key in keys):
        raise TargetError(f"{location}.keys contains an invalid age key name")
    env = require_mapping(encrypt.get("env"), f"{location}.env")
    if not env:
        raise TargetError(f"{location}.env must not be empty")
    for output_name, source_name in env.items():
        if not isinstance(output_name, str) or not ENV_NAME_RE.fullmatch(output_name):
            raise TargetError(f"{location}.env contains an invalid output name: {output_name!r}")
        if not isinstance(source_name, str) or not SOURCE_NAME_RE.fullmatch(source_name):
            raise TargetError(f"{location}.env.{output_name} has an invalid source name")
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
            raise TargetError(f"{location}.{name} must be a string")
    if bool(client_id) != bool(client_secret):
        raise TargetError(f"{location} must configure both Tailscale OAuth names or neither")
    return {
        "ssh_private_key_secret": ssh_private_key,
        "tailscale_oauth_client_id_variable": client_id,
        "tailscale_oauth_secret": client_secret,
    }


def validate_deploy(value, location):
    deploy = require_mapping(value, location)
    reject_unknown(
        deploy,
        {"flightdeck_ref", "env_ref", "extra_refs", "host", "credentials", "keep_releases"},
        location,
    )
    flightdeck_ref = require_string(deploy, "flightdeck_ref", location)
    env_ref = require_string(deploy, "env_ref", location)
    if not RELEASE_REF_RE.fullmatch(flightdeck_ref):
        raise TargetError(f"{location}.flightdeck_ref must be in owner/repo@tag format")
    if not ENV_REF_RE.fullmatch(env_ref):
        raise TargetError(f"{location}.env_ref must be in owner/repo@tag:asset.sops.env format")
    extra_refs = deploy.get("extra_refs", [])
    if not isinstance(extra_refs, list):
        raise TargetError(f"{location}.extra_refs must be an array")
    if any(not isinstance(ref, str) or not RELEASE_REF_RE.fullmatch(ref) for ref in extra_refs):
        raise TargetError(f"{location}.extra_refs contains an invalid release ref")
    keep_releases = deploy.get("keep_releases", 5)
    if not isinstance(keep_releases, int) or isinstance(keep_releases, bool) or keep_releases < 1:
        raise TargetError(f"{location}.keep_releases must be a positive integer")
    host = require_mapping(deploy.get("host"), f"{location}.host")
    reject_unknown(host, {"inventory", "user", "path", "sops_age_key_file"}, f"{location}.host")
    inventory = host.get("inventory")
    if not isinstance(inventory, list) or not inventory:
        raise TargetError(f"{location}.host.inventory must be a non-empty array")
    if any(not isinstance(item, str) or not item for item in inventory):
        raise TargetError(f"{location}.host.inventory must contain non-empty strings")
    user = require_string(host, "user", f"{location}.host", "root")
    path = require_string(host, "path", f"{location}.host", "~/flightdeck")
    sops_key_file = require_string(
        host,
        "sops_age_key_file",
        f"{location}.host",
        "~/.config/sops/age/keys.txt",
    )
    result = {
        "flightdeck_ref": flightdeck_ref,
        "env_ref": env_ref,
        "extra_refs": extra_refs,
        "inventory": inventory,
        "user": user,
        "path": path,
        "keep_releases": keep_releases,
        "sops_age_key_file": sops_key_file,
    }
    result.update(validate_credentials(deploy.get("credentials"), f"{location}.credentials"))
    return result


def load_target(path):
    try:
        value = yaml.load(path.read_text(), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise TargetError(f"{path} is not valid YAML: {exc}") from exc
    target = require_mapping(value, str(path))
    reject_unknown(target, {"encrypt", "deploy"}, str(path))
    if not target:
        raise TargetError(f"{path} must contain encrypt or deploy")
    result = {}
    if "encrypt" in target:
        result["encrypt"] = validate_encrypt(target["encrypt"], f"{path}.encrypt")
    if "deploy" in target:
        result["deploy"] = validate_deploy(target["deploy"], f"{path}.deploy")
    return result


def build_matrix(directory, mode, selected="all"):
    if mode not in {"encrypt", "deploy"}:
        raise TargetError("mode must be encrypt or deploy")
    paths = sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))
    if not paths:
        raise TargetError(f"no target manifests found in {directory}")
    names = {path.stem for path in paths}
    if selected != "all" and selected not in names:
        raise TargetError(f"unknown target: {selected}")
    include = []
    seen_names = set()
    for path in paths:
        name = path.stem
        if not TARGET_NAME_RE.fullmatch(name):
            raise TargetError(f"invalid target filename: {path.name}")
        if name in seen_names:
            raise TargetError(f"duplicate target name: {name}")
        seen_names.add(name)
        target = load_target(path)
        if selected != "all" and name != selected:
            continue
        if mode not in target:
            if selected != "all":
                raise TargetError(f"target {name} has no {mode} section")
            continue
        item = {"target": name, "manifest": str(path)}
        item.update(target[mode])
        include.append(item)
    return {"include": include}


def write_github_output(name, value):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path("targets"))
    parser.add_argument("--mode", required=True)
    parser.add_argument("--target", default="all")
    args = parser.parse_args(argv)
    try:
        matrix = build_matrix(args.directory, args.mode, args.target)
        encoded = json.dumps(matrix, separators=(",", ":"))
        write_github_output("matrix", encoded)
        write_github_output("count", len(matrix["include"]))
    except TargetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
