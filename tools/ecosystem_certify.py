#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Validate the complete Loomground inventory and emit deterministic certification."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "ecosystem" / "manifest.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
LAYERS = {"assurance", "control", "distribution", "grounding", "knowledge", "language", "reasoning"}
OUTCOMES = {"admit-once", "deliver", "deny", "escalate", "forget", "quarantine", "reconcile"}


class CertificationError(ValueError):
    pass


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CertificationError(f"cannot read {path}: {exc}") from exc


def _exact_keys(value: object, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise CertificationError(f"{label} must contain exactly {sorted(keys)}")
    return value


def validate_manifest(document: object, runtime_sources: object) -> dict:
    manifest = _exact_keys(
        document,
        {"schema_version", "owner", "repository_count", "repositories", "scenarios"},
        "ecosystem manifest",
    )
    if manifest["schema_version"] != 1 or manifest["owner"] != "flxk1":
        raise CertificationError("unsupported ecosystem manifest identity")
    repositories = manifest["repositories"]
    if not isinstance(repositories, list) or manifest["repository_count"] != 41:
        raise CertificationError("ecosystem manifest must declare 41 repositories")
    if len(repositories) != manifest["repository_count"]:
        raise CertificationError("repository_count differs from repository inventory")

    names = []
    by_name = {}
    for index, raw in enumerate(repositories):
        repo = _exact_keys(
            raw,
            {"name", "url", "revision", "layer", "invariant", "test_profile"},
            f"repository[{index}]",
        )
        name = repo["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise CertificationError(f"invalid repository name: {name!r}")
        if repo["url"] != f"https://github.com/flxk1/{name}":
            raise CertificationError(f"non-canonical repository URL for {name}")
        if repo["revision"] != "self" and not GIT_SHA.fullmatch(str(repo["revision"])):
            raise CertificationError(f"invalid revision for {name}")
        if repo["revision"] == "self" and name != "loomground-plugins":
            raise CertificationError("only loomground-plugins may use the self revision")
        if repo["layer"] not in LAYERS:
            raise CertificationError(f"invalid layer for {name}")
        if not isinstance(repo["invariant"], str) or not repo["invariant"].strip():
            raise CertificationError(f"missing invariant for {name}")
        if repo["test_profile"] not in {"conformance", "python", "release"}:
            raise CertificationError(f"invalid test profile for {name}")
        names.append(name)
        by_name[name] = repo
    if names != sorted(names) or len(set(names)) != len(names):
        raise CertificationError("repository inventory must be uniquely sorted")

    runtime = _exact_keys(
        runtime_sources,
        {"schema_version", "python", "root", "packages"},
        "runtime source manifest",
    )
    if not isinstance(runtime["packages"], list):
        raise CertificationError("runtime packages must be an array")
    runtime_pins = {}
    for index, raw in enumerate(runtime["packages"]):
        package = _exact_keys(raw, {"name", "url", "commit"}, f"runtime package[{index}]")
        if package["name"] in runtime_pins:
            raise CertificationError(f"duplicate runtime package: {package['name']}")
        runtime_pins[package["name"]] = package["commit"]
    if len(runtime_pins) != 32 or not set(runtime_pins).issubset(by_name):
        raise CertificationError("all 32 runtime packages must be represented")
    for name, commit in runtime_pins.items():
        if by_name[name]["revision"] != commit:
            raise CertificationError(f"ecosystem/runtime revision mismatch for {name}")

    scenarios = manifest["scenarios"]
    if not isinstance(scenarios, list) or not scenarios:
        raise CertificationError("ecosystem manifest requires scenarios")
    scenario_ids = []
    scenario_participants: set[str] = set()
    for index, raw in enumerate(scenarios):
        scenario = _exact_keys(
            raw,
            {"id", "participants", "outcome", "invariant"},
            f"scenario[{index}]",
        )
        if not isinstance(scenario["id"], str) or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*", scenario["id"]
        ):
            raise CertificationError(f"invalid scenario id: {scenario['id']!r}")
        scenario_ids.append(scenario["id"])
        if scenario["outcome"] not in OUTCOMES:
            raise CertificationError(f"invalid scenario outcome for {scenario['id']}")
        if not isinstance(scenario["participants"], list) or not scenario["participants"]:
            raise CertificationError(f"scenario {scenario['id']} has no participants")
        unknown = set(scenario["participants"]) - set(names)
        if unknown:
            raise CertificationError(f"scenario {scenario['id']} has unknown participants: {sorted(unknown)}")
        if not isinstance(scenario["invariant"], str) or not scenario["invariant"].strip():
            raise CertificationError(f"scenario {scenario['id']} has no invariant")
        if scenario["participants"] != sorted(set(scenario["participants"])):
            raise CertificationError(f"scenario participants must be uniquely sorted: {scenario['id']}")
        scenario_participants.update(scenario["participants"])
    if scenario_ids != sorted(scenario_ids) or len(set(scenario_ids)) != len(scenario_ids):
        raise CertificationError("scenario inventory must be uniquely sorted")
    if scenario_participants != set(names):
        missing = sorted(set(names) - scenario_participants)
        raise CertificationError(f"repositories absent from ecosystem scenarios: {missing}")
    return manifest


def current_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    commit = result.stdout.strip()
    if not GIT_SHA.fullmatch(commit):
        raise CertificationError("cannot resolve the current repository commit")
    return commit


def expected_revisions(manifest: dict, self_commit: str) -> dict[str, str]:
    if not GIT_SHA.fullmatch(self_commit):
        raise CertificationError("self commit must be a full Git SHA")
    return {
        repo["name"]: self_commit if repo["revision"] == "self" else repo["revision"]
        for repo in manifest["repositories"]
    }


def _result_files(results: Path) -> list[dict]:
    if not results.is_dir():
        raise CertificationError(f"results directory does not exist: {results}")
    documents = [load_json(path) for path in sorted(results.glob("*.json"))]
    if any(not isinstance(document, dict) for document in documents):
        raise CertificationError("every result file must contain one JSON object")
    return documents


def certify(manifest: dict, results: Path, self_commit: str) -> dict:
    revisions = expected_revisions(manifest, self_commit)
    repository_results = {}
    scenario_results = {}
    for result in _result_files(results):
        kind = result.get("kind")
        identifier = result.get("name") if kind == "repository" else result.get("id")
        target = repository_results if kind == "repository" else scenario_results
        if kind not in {"repository", "scenario"} or not isinstance(identifier, str):
            raise CertificationError("result has an invalid kind or identifier")
        if identifier in target:
            raise CertificationError(f"duplicate {kind} result: {identifier}")
        target[identifier] = result

    if set(repository_results) != set(revisions):
        raise CertificationError("repository results do not exactly cover the ecosystem inventory")
    expected_scenarios = {scenario["id"] for scenario in manifest["scenarios"]}
    if set(scenario_results) != expected_scenarios:
        raise CertificationError("scenario results do not exactly cover the scenario inventory")

    certified_repositories = []
    for name in sorted(revisions):
        result = _exact_keys(
            repository_results[name],
            {"schema_version", "kind", "name", "commit", "status", "checks", "evidence_sha256"},
            f"repository result {name}",
        )
        if result["schema_version"] != 1 or result["kind"] != "repository":
            raise CertificationError(f"unsupported repository result for {name}")
        if result["commit"] != revisions[name] or result["status"] != "passed":
            raise CertificationError(f"repository result did not pass at the pinned revision: {name}")
        if not isinstance(result["checks"], list) or not result["checks"]:
            raise CertificationError(f"repository result has no checks: {name}")
        if result["checks"] != sorted(set(result["checks"])):
            raise CertificationError(f"repository checks must be uniquely sorted: {name}")
        if not SHA256.fullmatch(str(result["evidence_sha256"])):
            raise CertificationError(f"invalid repository evidence digest: {name}")
        certified_repositories.append({
            "name": name,
            "commit": result["commit"],
            "checks": result["checks"],
            "evidence_sha256": result["evidence_sha256"],
        })

    certified_scenarios = []
    for identifier in sorted(expected_scenarios):
        result = _exact_keys(
            scenario_results[identifier],
            {"schema_version", "kind", "id", "status", "assertions", "trace_sha256"},
            f"scenario result {identifier}",
        )
        if result["schema_version"] != 1 or result["kind"] != "scenario" or result["status"] != "passed":
            raise CertificationError(f"scenario result did not pass: {identifier}")
        if not isinstance(result["assertions"], list) or result["assertions"] != sorted(set(result["assertions"])):
            raise CertificationError(f"scenario assertions must be non-empty and uniquely sorted: {identifier}")
        if not result["assertions"] or not SHA256.fullmatch(str(result["trace_sha256"])):
            raise CertificationError(f"invalid scenario evidence: {identifier}")
        certified_scenarios.append({
            "id": identifier,
            "assertions": result["assertions"],
            "trace_sha256": result["trace_sha256"],
        })

    certificate = {
        "schema_version": 1,
        "kind": "loomground-ecosystem-certification",
        "status": "passed",
        "manifest_sha256": digest(manifest),
        "repositories": certified_repositories,
        "scenarios": certified_scenarios,
    }
    certificate["certificate_sha256"] = digest(certificate)
    return certificate


def verify_certificate(document: object) -> dict:
    certificate = _exact_keys(
        document,
        {
            "schema_version", "kind", "status", "manifest_sha256", "repositories",
            "scenarios", "certificate_sha256",
        },
        "ecosystem certificate",
    )
    if (
        certificate["schema_version"] != 1
        or certificate["kind"] != "loomground-ecosystem-certification"
        or certificate["status"] != "passed"
    ):
        raise CertificationError("unsupported or non-passing ecosystem certificate")
    claimed = certificate["certificate_sha256"]
    payload = dict(certificate)
    del payload["certificate_sha256"]
    if not SHA256.fullmatch(str(claimed)) or digest(payload) != claimed:
        raise CertificationError("ecosystem certificate digest mismatch")
    return certificate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--runtime-sources", type=Path, default=ROOT / "runtime/runtime-sources.json")
    parser.add_argument("--results", type=Path)
    parser.add_argument("--self-commit")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-certificate", type=Path)
    args = parser.parse_args()
    try:
        if args.verify_certificate:
            certificate = verify_certificate(load_json(args.verify_certificate))
            print(
                "ECOSYSTEM CERTIFICATE PASS: "
                f"{len(certificate['repositories'])} repositories, "
                f"{len(certificate['scenarios'])} scenarios"
            )
            return 0
        manifest = validate_manifest(load_json(args.manifest), load_json(args.runtime_sources))
        if args.results is None:
            print(f"ECOSYSTEM INVENTORY PASS: {len(manifest['repositories'])} repositories, {len(manifest['scenarios'])} scenarios")
            return 0
        certificate = certify(manifest, args.results, args.self_commit or current_commit())
        payload = canonical_json(certificate) + b"\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(payload)
        else:
            print(payload.decode(), end="")
        return 0
    except (CertificationError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ECOSYSTEM CERTIFICATION FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
