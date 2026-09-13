#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Build a deterministic, Ed25519-signed offline Loomground runtime bundle."""

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

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loomground_installer.bundle import BundleError, canonical_json, dsse_pae  # noqa: E402
from loomground_installer.runtime_bundle import (  # noqa: E402
    RUNTIME_ENVELOPE_NAME,
    RUNTIME_LOCK_NAME,
    RUNTIME_PAYLOAD_TYPE,
    RUNTIME_SBOM_NAME,
    runtime_sbom,
    validate_runtime_lock,
    verify_runtime_bundle,
)


def _private_key(path: Path) -> Ed25519PrivateKey:
    try:
        key = load_pem_private_key(path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise BundleError(f"cannot load runtime signing key: {exc}") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise BundleError("runtime signing key must be Ed25519")
    return key


def _digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _file_records(root: Path) -> list[dict]:
    records = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == RUNTIME_ENVELOPE_NAME:
            continue
        size, digest = _digest(path)
        records.append({
            "path": path.relative_to(root).as_posix(),
            "size": size,
            "sha256": digest,
        })
    return records


def build(lock_path: Path, wheelhouse: Path, output: Path, signing_key: Path, key_id: str) -> Path:
    if not key_id:
        raise BundleError("runtime key id is required")
    if output.exists() or output.is_symlink():
        raise BundleError(f"runtime output already exists: {output}")
    if not output.is_absolute() or not output.parent.is_dir() or output.parent.is_symlink():
        raise BundleError("runtime output must be absolute below a real existing parent")
    if not wheelhouse.is_dir() or wheelhouse.is_symlink():
        raise BundleError("wheelhouse must be a real directory")
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"cannot read runtime lock: {exc}") from exc
    *_, packages = validate_runtime_lock(lock)
    expected_wheels = {package.wheel for package in packages}
    actual_wheels = {path.name for path in wheelhouse.iterdir() if path.is_file() and path.suffix == ".whl"}
    if actual_wheels != expected_wheels:
        raise BundleError(
            f"wheelhouse differs from runtime lock: missing={sorted(expected_wheels - actual_wheels)}, "
            f"extra={sorted(actual_wheels - expected_wheels)}"
        )
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.stage-", dir=output.parent))
    try:
        (stage / "wheels").mkdir()
        (stage / RUNTIME_LOCK_NAME).write_bytes(canonical_json(lock) + b"\n")
        (stage / RUNTIME_SBOM_NAME).write_bytes(canonical_json(runtime_sbom(lock)) + b"\n")
        for package in packages:
            source = wheelhouse / package.wheel
            if source.is_symlink():
                raise BundleError(f"wheelhouse contains symlink: {package.wheel}")
            size, digest = _digest(source)
            if not size or digest != package.sha256:
                raise BundleError(f"wheel digest differs from runtime lock: {package.wheel}")
            shutil.copyfile(source, stage / "wheels" / package.wheel, follow_symlinks=False)
        statement = {
            "schema_version": 1,
            "key_id": key_id,
            "lock": lock,
            "files": _file_records(stage),
        }
        payload = canonical_json(statement)
        signature = _private_key(signing_key).sign(dsse_pae(RUNTIME_PAYLOAD_TYPE, payload))
        envelope = {
            "payloadType": RUNTIME_PAYLOAD_TYPE,
            "payload": base64.b64encode(payload).decode("ascii"),
            "signatures": [{"keyid": key_id, "sig": base64.b64encode(signature).decode("ascii")}],
        }
        (stage / RUNTIME_ENVELOPE_NAME).write_text(
            json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(stage, output)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--signing-key", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--verify-with", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = build(args.lock, args.wheelhouse, args.output, args.signing_key, args.key_id)
        verify_runtime_bundle(output, args.verify_with)
    except (OSError, BundleError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
