#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Bind a successful isolated native test log to one repository result."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import ecosystem_certify

GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def emit(name: str, commit: str, log: Path, output: Path) -> dict:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("invalid repository name")
    if not GIT_SHA.fullmatch(commit):
        raise ValueError("commit must be a full Git SHA")
    log_bytes = log.read_bytes()
    if not log_bytes:
        raise ValueError("native test log is empty")
    evidence = {
        "schema_version": 1,
        "kind": "native-test-evidence",
        "repository": name,
        "commit": commit,
        "check": "test",
        "log_sha256": hashlib.sha256(log_bytes).hexdigest(),
    }
    evidence_bytes = ecosystem_certify.canonical_json(evidence) + b"\n"
    evidence_dir = output / "evidence"
    log_dir = output / "logs"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{name}.log").write_bytes(log_bytes)
    (evidence_dir / f"{name}.json").write_bytes(evidence_bytes)
    result = {
        "schema_version": 1,
        "kind": "repository",
        "name": name,
        "commit": commit,
        "status": "passed",
        "checks": ["test"],
        "evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
    }
    (output / f"repository-{name}.json").write_bytes(
        ecosystem_certify.canonical_json(result) + b"\n"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = emit(args.name, args.commit, args.log, args.output)
        print(f"NATIVE TEST EVIDENCE PASS: {result['name']}@{result['commit']}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"NATIVE TEST EVIDENCE FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
