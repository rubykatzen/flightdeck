#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


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


def load_manifest(path):
    try:
        value = yaml.load(path.read_text(), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ManifestError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError(f"{path} must contain a YAML mapping")
    return value


def validate_vault(name, manifest):
    if not isinstance(manifest.get("asset"), str) or not manifest["asset"]:
        raise ManifestError(f"vault {name!r} must set asset to a non-empty string")
    if not isinstance(manifest.get("keys"), list) or not manifest["keys"]:
        raise ManifestError(f"vault {name!r} must set keys to a non-empty list")
    if not isinstance(manifest.get("env"), dict) or not manifest["env"]:
        raise ManifestError(f"vault {name!r} must set env to a non-empty mapping")


def build_matrix(directory):
    paths = sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))
    if not paths:
        raise ManifestError(f"no manifests found in {directory}")
    include = []
    seen_names = set()
    for path in paths:
        name = path.stem
        if not NAME_RE.fullmatch(name):
            raise ManifestError(f"invalid manifest filename: {path.name}")
        if name in seen_names:
            raise ManifestError(f"duplicate manifest name: {name}")
        seen_names.add(name)
        manifest = load_manifest(path)
        validate_vault(name, manifest)
        item = {"name": name, "manifest": str(path)}
        item.update(manifest)
        include.append(item)
    return {"include": include}


def write_github_output(name, value):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        matrix = build_matrix(args.directory)
        encoded = json.dumps(matrix, separators=(",", ":"))
        write_github_output("matrix", encoded)
        write_github_output("count", len(matrix["include"]))
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
