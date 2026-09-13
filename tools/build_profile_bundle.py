#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Build a deterministic, Ed25519-signed Loomground profile bundle."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import build_packages
from loomground_installer.bundle import ENVELOPE_NAME, PAYLOAD_TYPE, canonical_json, dsse_pae
from loomground_installer.core import load_profiles, resolve_profile


def _safe_source_tree(root: Path) -> None:
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"source is not a real directory: {root}")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"source bundle input contains symlink: {path}")


def _copy_plugin(source: Path, destination: Path, name: str, target: str, source_record: dict) -> None:
    skills = source / "skills"
    _safe_source_tree(skills)
    shutil.copytree(skills, destination / "skills")
    metadata = {
        "schema_version": 1,
        "name": name,
        "skills": "./skills/",
        "source": source_record,
        "target": target,
    }
    (destination / "loomground-source.json").write_bytes(canonical_json(metadata) + b"\n")


def _files(root: Path) -> list[dict]:
    records = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == ENVELOPE_NAME:
            continue
        content = path.read_bytes()
        records.append({
            "path": path.relative_to(root).as_posix(),
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    return records


def _private_key(path: Path) -> Ed25519PrivateKey:
    try:
        key = load_pem_private_key(path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"cannot load signing key: {exc}") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("profile bundle signing key must be Ed25519")
    return key


def build(profile: str, target: str, output: Path, signing_key: Path, key_id: str) -> Path:
    if not key_id:
        raise ValueError("key id is required")
    if output.exists() or output.is_symlink():
        raise ValueError(f"output already exists: {output}")
    if not output.is_absolute() or not output.parent.is_dir():
        raise ValueError("output must be an absolute path below an existing parent")
    profile_name, plugins = resolve_profile(profile)
    externals = build_packages.external_config()
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.stage-", dir=output.parent))
    try:
        sources = {}
        for name in plugins:
            entry = externals[name]
            source = (ROOT / entry["path"]).resolve()
            source_record = entry["source"]
            _copy_plugin(source, stage / "plugins" / name, name, target, source_record)
            sources[name] = source_record
        statement = {
            "schema_version": 1,
            "profile": profile_name,
            "target": target,
            "key_id": key_id,
            "plugins": list(plugins),
            "sources": sources,
            "files": _files(stage),
        }
        payload = canonical_json(statement)
        signature = _private_key(signing_key).sign(dsse_pae(PAYLOAD_TYPE, payload))
        envelope = {
            "payloadType": PAYLOAD_TYPE,
            "payload": base64.b64encode(payload).decode("ascii"),
            "signatures": [{"keyid": key_id, "sig": base64.b64encode(signature).decode("ascii")}],
        }
        (stage / ENVELOPE_NAME).write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(stage, output)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=sorted(load_profiles()["profiles"]), required=True)
    parser.add_argument("--target", choices=("claude", "codex", "generic"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--signing-key", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    args = parser.parse_args()
    try:
        output = build(args.profile, args.target, args.output, args.signing_key, args.key_id)
    except (OSError, KeyError, ValueError, build_packages.PackageError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
