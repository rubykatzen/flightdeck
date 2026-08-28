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


def validate_target(name, manifest):
    if not isinstance(manifest.get("hosts"), list) or not manifest["hosts"]:
        raise ManifestError(f"target {name!r} must set hosts to a non-empty list")
    if not isinstance(manifest.get("app_refs"), list) or not manifest["app_refs"]:
        raise ManifestError(f"target {name!r} must set app_refs to a non-empty list")
    if not isinstance(manifest.get("apps"), dict) or not manifest["apps"]:
        raise ManifestError(f"target {name!r} must set apps to a non-empty object")
    if not isinstance(manifest.get("ssh_private_key_secret"), str) or not manifest["ssh_private_key_secret"]:
        raise ManifestError(f"target {name!r} must set ssh_private_key_secret to a non-empty string")
    if not isinstance(manifest.get("sops_age_key_secret"), str) or not manifest["sops_age_key_secret"]:
        raise ManifestError(f"target {name!r} must set sops_age_key_secret to a non-empty string")


def build_matrix(directory, selected="all"):
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
        if not NAME_RE.fullmatch(name):
            raise ManifestError(f"invalid manifest filename: {path.name}")
        if name in seen_names:
            raise ManifestError(f"duplicate manifest name: {name}")
        seen_names.add(name)
        manifest = load_manifest(path)
        validate_target(name, manifest)
        if selected != "all" and name != selected:
            continue
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
    parser.add_argument("--name", default="all")
    args = parser.parse_args(argv)
    try:
        matrix = build_matrix(args.directory, args.name)
        encoded = json.dumps(matrix, separators=(",", ":"))
        write_github_output("matrix", encoded)
        write_github_output("count", len(matrix["include"]))
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
