#!/usr/bin/env python3
"""Resolve and download owner/repo@tag[:asset] release refs via the gh CLI.

Single shared implementation for every ref this deploy tool downloads
(the machinery bundle, app bundles, and per-app encrypted env assets) -
the thing three-going-on-four copies of this same ~30-line parse/resolve/
download sequence used to be, once per caller, in ansible/deploy.yml.
"""
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

REF_RE = re.compile(r"^(?P<repo>[^@]+)@(?P<tag>[^:]+)(?::(?P<asset>.+))?$")


class RefError(Exception):
    pass


@dataclass(frozen=True)
class ResolvedRef:
    repo: str
    tag: str
    asset: str


def parse_ref(ref, default_asset=None):
    match = REF_RE.fullmatch(ref)
    if not match:
        raise RefError(f"Invalid release ref: {ref}. Expected owner/repo@tag or owner/repo@tag:asset")
    asset = match.group("asset") or default_asset
    if not asset:
        raise RefError(f"Invalid release ref: {ref} has no asset and no default was provided")
    return ResolvedRef(repo=match.group("repo"), tag=match.group("tag"), asset=asset)


def resolve_latest(repo, run=subprocess.run):
    result = run(
        ["gh", "release", "view", "--repo", repo, "--json", "tagName", "--jq", ".tagName"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RefError(f"Could not resolve GitHub latest release for {repo}: {result.stderr.strip()}")
    tag = result.stdout.strip()
    if not tag or tag == "null":
        raise RefError(f"Could not resolve GitHub latest release for {repo}")
    return tag


def download_ref(ref, out_dir, default_asset=None, run=subprocess.run):
    resolved = parse_ref(ref, default_asset)
    tag = resolved.tag
    if tag == "latest":
        tag = resolve_latest(resolved.repo, run=run)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = run(
        [
            "gh",
            "release",
            "download",
            tag,
            "--repo",
            resolved.repo,
            "--pattern",
            resolved.asset,
            "--dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RefError(f"Failed to download {resolved.asset} from {resolved.repo}@{tag}: {result.stderr.strip()}")

    path = out_dir / resolved.asset
    if not path.is_file():
        raise RefError(f"{resolved.asset} was not found in {resolved.repo}@{tag}")
    return path, f"{resolved.repo}@{tag}:{resolved.asset}"
