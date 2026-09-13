#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Collect revision-bound GitHub check evidence for the Loomground ecosystem."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

import ecosystem_certify

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKS = ROOT / "ecosystem/repository-checks.json"
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class EvidenceError(ValueError):
    pass


def validate_check_contract(document: object, manifest: dict) -> dict[str, list[str]]:
    if not isinstance(document, dict) or set(document) != {"schema_version", "owner", "repositories"}:
        raise EvidenceError("check contract has invalid top-level keys")
    if document["schema_version"] != 1 or document["owner"] != manifest["owner"]:
        raise EvidenceError("check contract identity does not match the ecosystem manifest")
    if not isinstance(document["repositories"], list):
        raise EvidenceError("check contract repositories must be an array")

    contracts: dict[str, list[str]] = {}
    ordered_names = []
    for index, raw in enumerate(document["repositories"]):
        if not isinstance(raw, dict) or set(raw) != {"name", "required_checks"}:
            raise EvidenceError(f"check contract repository[{index}] has invalid keys")
        name, checks = raw["name"], raw["required_checks"]
        if not isinstance(name, str) or not isinstance(checks, list) or not checks:
            raise EvidenceError(f"invalid check contract for {name!r}")
        if checks != sorted(set(checks)) or any(not isinstance(item, str) or not item for item in checks):
            raise EvidenceError(f"required checks must be non-empty and uniquely sorted: {name}")
        ordered_names.append(name)
        contracts[name] = checks

    manifest_names = [repo["name"] for repo in manifest["repositories"]]
    if ordered_names != manifest_names or set(contracts) != set(manifest_names):
        raise EvidenceError("check contracts do not exactly cover the ecosystem manifest")
    return contracts


def github_check_runs(owner: str, name: str, commit: str, token: str) -> list[dict]:
    url = (
        f"https://api.github.com/repos/{owner}/{name}/commits/{commit}/check-runs"
        "?filter=latest&per_page=100"
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "loomground-ecosystem-certifier/1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            document = json.load(response)
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"GitHub check query failed for {name}@{commit}: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("check_runs"), list):
        raise EvidenceError(f"GitHub returned malformed check evidence for {name}@{commit}")
    return document["check_runs"]


def normalize_evidence(
    owner: str,
    name: str,
    commit: str,
    required: list[str],
    runs: list[dict],
) -> dict:
    selected = []
    for raw in runs:
        if not isinstance(raw, dict) or raw.get("name") not in required:
            continue
        app = raw.get("app")
        selected.append(
            {
                "app": app.get("slug") if isinstance(app, dict) else None,
                "conclusion": raw.get("conclusion"),
                "details_url": raw.get("details_url"),
                "head_sha": raw.get("head_sha"),
                "id": raw.get("id"),
                "name": raw.get("name"),
                "status": raw.get("status"),
            }
        )
    selected.sort(key=lambda item: (str(item["name"]), int(item["id"] or 0)))
    return {
        "schema_version": 1,
        "kind": "github-check-evidence",
        "owner": owner,
        "repository": name,
        "commit": commit,
        "required_checks": required,
        "check_runs": selected,
    }


def passing_result(evidence: dict) -> dict:
    commit = evidence["commit"]
    required = evidence["required_checks"]
    runs = evidence["check_runs"]
    passed = {
        run["name"]
        for run in runs
        if run["head_sha"] == commit
        and run["status"] == "completed"
        and run["conclusion"] == "success"
    }
    missing = sorted(set(required) - passed)
    if missing:
        raise EvidenceError(
            f"{evidence['repository']}@{commit} lacks successful required checks: {missing}"
        )
    evidence_bytes = ecosystem_certify.canonical_json(evidence) + b"\n"
    return {
        "schema_version": 1,
        "kind": "repository",
        "name": evidence["repository"],
        "commit": commit,
        "status": "passed",
        "checks": required,
        "evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
    }


def collect(
    manifest: dict,
    contracts: dict[str, list[str]],
    self_commit: str,
    output: Path,
    token: str,
    excluded: set[str] | None = None,
    fetch=github_check_runs,
) -> tuple[int, list[str]]:
    if not GIT_SHA.fullmatch(self_commit):
        raise EvidenceError("self commit must be a full Git SHA")
    if output.exists() and any(output.iterdir()):
        raise EvidenceError(f"output directory must be absent or empty: {output}")
    evidence_dir = output / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    revisions = ecosystem_certify.expected_revisions(manifest, self_commit)
    excluded = excluded or set()
    unknown_exclusions = excluded - set(revisions)
    if unknown_exclusions:
        raise EvidenceError(f"unknown excluded repositories: {sorted(unknown_exclusions)}")
    failures = []
    passed_count = 0
    for name in sorted(revisions):
        if name in excluded:
            continue
        commit = revisions[name]
        try:
            runs = fetch(manifest["owner"], name, commit, token)
            evidence = normalize_evidence(
                manifest["owner"], name, commit, contracts[name], runs
            )
            evidence_bytes = ecosystem_certify.canonical_json(evidence) + b"\n"
            (evidence_dir / f"{name}.json").write_bytes(evidence_bytes)
            result = passing_result(evidence)
            (output / f"repository-{name}.json").write_bytes(
                ecosystem_certify.canonical_json(result) + b"\n"
            )
            passed_count += 1
        except EvidenceError as exc:
            failures.append(str(exc))
    return passed_count, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ecosystem_certify.DEFAULT_MANIFEST)
    parser.add_argument("--runtime-sources", type=Path, default=ROOT / "runtime/runtime-sources.json")
    parser.add_argument("--check-contract", type=Path, default=DEFAULT_CHECKS)
    parser.add_argument("--self-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()
    try:
        token = os.environ.get(args.token_env, "")
        if not token:
            raise EvidenceError(f"missing GitHub token in {args.token_env}")
        manifest = ecosystem_certify.validate_manifest(
            ecosystem_certify.load_json(args.manifest),
            ecosystem_certify.load_json(args.runtime_sources),
        )
        contracts = validate_check_contract(
            ecosystem_certify.load_json(args.check_contract), manifest
        )
        passed, failures = collect(
            manifest, contracts, args.self_commit, args.output, token, set(args.exclude)
        )
        expected = 41 - len(set(args.exclude))
        if failures:
            for failure in failures:
                print(f"GITHUB EVIDENCE FAIL: {failure}")
            print(f"GITHUB EVIDENCE INCOMPLETE: {passed}/{expected} selected repositories passed")
            return 1
        print(f"GITHUB EVIDENCE PASS: {passed}/{expected} selected repositories passed")
        return 0
    except (EvidenceError, ecosystem_certify.CertificationError, OSError) as exc:
        print(f"GITHUB EVIDENCE FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
