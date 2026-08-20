#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path

import yaml

ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
SOURCE_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*(?:__[A-Z0-9_]+)*$")
KEY_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
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


def load_json_env(name):
    raw = os.environ.get(name, "{}")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{name} must contain valid JSON") from exc
    if not isinstance(value, dict):
        raise ManifestError(f"{name} must contain a JSON object")
    return value


def load_manifest(path):
    try:
        manifest = yaml.load(path.read_text(), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ManifestError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ManifestError(f"{path} must contain a YAML mapping")
    unknown = sorted(set(manifest) - {"asset", "keys", "env"})
    if unknown:
        raise ManifestError("manifest contains unknown keys: " + ", ".join(unknown))
    asset = manifest.get("asset")
    keys = manifest.get("keys")
    env = manifest.get("env")
    if not isinstance(asset, str) or not ASSET_RE.fullmatch(asset):
        raise ManifestError("asset must be named like server.sops.env")
    if not isinstance(keys, list) or not keys:
        raise ManifestError("keys must be a non-empty list")
    if not isinstance(env, dict) or not env:
        raise ManifestError("env must be a non-empty mapping")
    for key in keys:
        if not isinstance(key, str) or not KEY_NAME_RE.fullmatch(key):
            raise ManifestError(f"invalid key name: {key!r}")
    for output_name, source_name in env.items():
        if not isinstance(output_name, str) or not ENV_NAME_RE.fullmatch(output_name):
            raise ManifestError(f"invalid output env name: {output_name!r}")
        if not isinstance(source_name, str) or not SOURCE_NAME_RE.fullmatch(source_name):
            raise ManifestError(f"invalid source key for {output_name}: {source_name!r}")
    return manifest


def dotenv_value(value):
    value = str(value)
    if "\x00" in value:
        raise ManifestError("env values cannot contain NUL bytes")
    if "\n" in value or "\r" in value:
        raise ManifestError("env values cannot contain newlines")
    return shlex.quote(value)


def resolve_value(source_name, secrets, variables):
    secret = secrets.get(source_name)
    if secret not in (None, ""):
        return secret
    variable = variables.get(source_name)
    if variable not in (None, ""):
        return variable
    return None


def render_env(manifest, secrets, variables):
    lines = []
    missing = []
    for output_name, source_name in manifest["env"].items():
        value = resolve_value(source_name, secrets, variables)
        if value is None:
            missing.append(source_name)
            continue
        lines.append(f"{output_name}={dotenv_value(value)}")
    if missing:
        raise ManifestError("missing GitHub Secrets/Variables: " + ", ".join(sorted(missing)))
    return "\n".join(lines) + "\n"


def write_github_outputs(values):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}={value}\n")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        secrets = load_json_env("GITHUB_SECRETS_JSON")
        variables = load_json_env("GITHUB_VARS_JSON")
        args.output.write_text(render_env(manifest, secrets, variables))
        args.output.chmod(0o600)
        write_github_outputs(
            {
                "asset": manifest["asset"],
                "keys": ",".join(manifest["keys"]),
            }
        )
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
