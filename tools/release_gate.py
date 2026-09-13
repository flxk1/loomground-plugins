#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Fail-closed release gate for the Loomground plugin marketplace."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import build_packages

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {".pytest_cache", "__pycache__", "dist"}
FORBIDDEN_NAMES = {".DS_Store", ".env", ".env.local"}


def fail(message: str) -> None:
    raise SystemExit(f"RELEASE GATE FAIL: {message}")


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    return [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]


def main() -> int:
    for command, description in (
        ([sys.executable, "tools/supply_chain_gate.py", "--self-test"], "supply-chain self-test"),
        ([sys.executable, "tools/supply_chain_gate.py"], "supply-chain license/SBOM gate"),
        ([sys.executable, "tools/ecosystem_certify.py"], "ecosystem inventory gate"),
        ([sys.executable, "tools/runtime_release_gate.py"], "runtime release gate"),
    ):
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            fail(f"{description} failed")

    files = tracked_files()
    bad = [
        path.relative_to(ROOT)
        for path in files
        if path.name in FORBIDDEN_NAMES or FORBIDDEN_PARTS.intersection(path.parts)
    ]
    if bad:
        fail("tracked release debris: " + ", ".join(map(str, bad)))

    for path in files:
        if path.suffix == ".json":
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")

    try:
        directories = build_packages.package_dirs([])
        packages = [build_packages.load_package(path) for path in directories]
        plugins = build_packages.all_plugin_manifests()
    except (OSError, KeyError, TypeError, ValueError) as exc:
        fail(str(exc))

    expected = build_packages.marketplace_manifest(
        packages, build_packages.marketplace_sources(), plugins)
    actual = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    if actual != expected:
        fail("committed marketplace differs from canonical package manifests")

    test = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)
    if test.returncode:
        fail("test suite failed")

    print(
        f"RELEASE GATE PASS: {len(packages)} packages, {len(plugins)} plugin manifests, "
        f"{len(files)} tracked files, marketplace and tests coherent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
