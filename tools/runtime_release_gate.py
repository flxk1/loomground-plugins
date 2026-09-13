#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Offline structural gate for the GitHub-native runtime release pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from assemble_runtime_release import load_licenses, load_sources  # noqa: E402
from loomground_installer.runtime_bundle import normalize_name  # noqa: E402
from lock_runtime_third_party import validate_hash_lock  # noqa: E402


def main() -> int:
    try:
        _, _, root, sources = load_sources(ROOT / "runtime" / "runtime-sources.json")
        if root != "loomground-mcp" or len(sources) != 32:
            raise ValueError("runtime source manifest must contain loomground-mcp plus 31 pinned planes")
        validate_hash_lock(
            ROOT / "runtime" / "third-party-requirements.in",
            ROOT / "runtime" / "third-party-requirements.txt",
        )
        third_party_names = {
            normalize_name(line.split("==", 1)[0])
            for line in (ROOT / "runtime" / "third-party-requirements.in")
            .read_text(encoding="utf-8")
            .splitlines()
            if line and not line.startswith("#")
        }
        licenses = load_licenses(ROOT / "runtime" / "third-party-licenses.json")
        if set(licenses) != third_party_names:
            raise ValueError("runtime license map differs from the third-party package set")
        validate_hash_lock(
            ROOT / "runtime" / "build-requirements.in",
            ROOT / "runtime" / "build-requirements.txt",
        )
        workflow = (ROOT / ".github" / "workflows" / "runtime-release.yml").read_text(
            encoding="utf-8"
        )
        if "secrets." in workflow or "actions/attest@" not in workflow:
            raise ValueError("runtime workflow must use GitHub attestation without repository secrets")
        if "generate_ephemeral_release_key.py" not in workflow or "trap 'rm -f" not in workflow:
            raise ValueError("runtime workflow must generate and remove one ephemeral signing key per artifact")
    except (OSError, ValueError) as exc:
        print(f"RUNTIME RELEASE GATE FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"RUNTIME RELEASE GATE PASS: {len(sources)} pinned sources, hash locks and OIDC workflow coherent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
