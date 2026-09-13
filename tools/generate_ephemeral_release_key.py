#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Generate a per-artifact Ed25519 key pair for an attested release build."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def generate(directory: Path, stem: str) -> dict:
    if not directory.is_absolute() or not directory.is_dir() or directory.is_symlink():
        raise ValueError("key output must be an absolute real existing directory")
    if not stem or Path(stem).name != stem:
        raise ValueError("key stem must be one safe filename component")
    private_path = directory / f"{stem}-private.pem"
    public_path = directory / f"{stem}-public.pem"
    if private_path.exists() or public_path.exists():
        raise ValueError("ephemeral key output already exists")
    key = Ed25519PrivateKey.generate()
    private_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    os.chmod(private_path, 0o600)
    public_bytes = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_path.write_bytes(public_bytes)
    fingerprint = hashlib.sha256(public_bytes).hexdigest()
    return {
        "private_key": str(private_path),
        "public_key": str(public_path),
        "key_id": f"loomground-runtime-ephemeral-{fingerprint[:16]}",
        "public_key_sha256": fingerprint,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--stem", required=True)
    args = parser.parse_args()
    try:
        result = generate(args.directory, args.stem)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
