import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ecosystem_certify  # noqa: E402


@pytest.fixture
def manifests():
    ecosystem = ecosystem_certify.load_json(ROOT / "ecosystem/manifest.json")
    runtime = ecosystem_certify.load_json(ROOT / "runtime/runtime-sources.json")
    return ecosystem, runtime


def write_results(directory: Path, manifest: dict, self_commit: str) -> None:
    revisions = ecosystem_certify.expected_revisions(manifest, self_commit)
    for name, commit in revisions.items():
        result = {
            "schema_version": 1,
            "kind": "repository",
            "name": name,
            "commit": commit,
            "status": "passed",
            "checks": ["contract", "unit"],
            "evidence_sha256": hashlib.sha256(name.encode()).hexdigest(),
        }
        (directory / f"repository-{name}.json").write_text(json.dumps(result), encoding="utf-8")
    for scenario in manifest["scenarios"]:
        identifier = scenario["id"]
        result = {
            "schema_version": 1,
            "kind": "scenario",
            "id": identifier,
            "status": "passed",
            "assertions": ["expected-outcome", "fail-closed"],
            "trace_sha256": hashlib.sha256(identifier.encode()).hexdigest(),
        }
        (directory / f"scenario-{identifier}.json").write_text(json.dumps(result), encoding="utf-8")


def write_scenario_traces(directory: Path, manifest: dict, self_commit: str) -> None:
    revisions = ecosystem_certify.expected_revisions(manifest, self_commit)
    trace_dir = directory / "traces"
    trace_dir.mkdir()
    for scenario in manifest["scenarios"]:
        identifier = scenario["id"]
        trace = {
            "schema_version": 1,
            "kind": "loomground-ecosystem-scenario-trace",
            "id": identifier,
            "contract": {
                "outcome": scenario["outcome"],
                "invariant": scenario["invariant"],
                "participants": scenario["participants"],
            },
            "participant_revisions": {
                name: revisions[name] for name in scenario["participants"]
            },
            "runtime_lock_sha256": "7" * 64,
            "steps": [{"component": "test", "input_sha256": "8" * 64, "output": {"passed": True}}],
            "assertions": ["expected-outcome", "fail-closed"],
        }
        trace_bytes = ecosystem_certify.canonical_json(trace) + b"\n"
        (trace_dir / f"{identifier}.json").write_bytes(trace_bytes)
        result_path = directory / f"scenario-{identifier}.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["trace_sha256"] = hashlib.sha256(trace_bytes).hexdigest()
        result_path.write_text(json.dumps(result), encoding="utf-8")


def test_manifest_covers_all_repositories_and_runtime_pins(manifests):
    ecosystem, runtime = manifests
    manifest = ecosystem_certify.validate_manifest(ecosystem, runtime)
    assert len(manifest["repositories"]) == 41
    assert len(runtime["packages"]) == 32
    participants = {
        name for scenario in manifest["scenarios"] for name in scenario["participants"]
    }
    assert participants == {repo["name"] for repo in manifest["repositories"]}


def test_manifest_rejects_runtime_revision_drift(manifests):
    ecosystem, runtime = copy.deepcopy(manifests)
    runtime["packages"][0]["commit"] = "0" * 40
    with pytest.raises(ecosystem_certify.CertificationError, match="revision mismatch"):
        ecosystem_certify.validate_manifest(ecosystem, runtime)


def test_manifest_rejects_repository_missing_from_scenarios(manifests):
    ecosystem, runtime = copy.deepcopy(manifests)
    for scenario in ecosystem["scenarios"]:
        if "privacy-shield" in scenario["participants"]:
            scenario["participants"].remove("privacy-shield")
    with pytest.raises(ecosystem_certify.CertificationError, match="absent from ecosystem scenarios"):
        ecosystem_certify.validate_manifest(ecosystem, runtime)


def test_certificate_is_deterministic_and_schema_valid(manifests, tmp_path):
    ecosystem, runtime = manifests
    manifest = ecosystem_certify.validate_manifest(ecosystem, runtime)
    self_commit = "a" * 40
    write_results(tmp_path, manifest, self_commit)
    first = ecosystem_certify.certify(manifest, tmp_path, self_commit)
    second = ecosystem_certify.certify(manifest, tmp_path, self_commit)
    assert first == second
    assert ecosystem_certify.verify_certificate(first) == first

    schema = ecosystem_certify.load_json(ROOT / "schemas/ecosystem-certification.schema.json")
    Draft202012Validator(schema).validate(first)


def test_result_schema_accepts_both_result_kinds(manifests, tmp_path):
    ecosystem, runtime = manifests
    manifest = ecosystem_certify.validate_manifest(ecosystem, runtime)
    write_results(tmp_path, manifest, "b" * 40)
    schema = ecosystem_certify.load_json(ROOT / "schemas/ecosystem-test-result.schema.json")
    validator = Draft202012Validator(schema)
    for path in tmp_path.glob("*.json"):
        validator.validate(json.loads(path.read_text(encoding="utf-8")))


def test_certificate_rejects_missing_repository_result(manifests, tmp_path):
    ecosystem, runtime = manifests
    manifest = ecosystem_certify.validate_manifest(ecosystem, runtime)
    write_results(tmp_path, manifest, "c" * 40)
    next(tmp_path.glob("repository-*.json")).unlink()
    with pytest.raises(ecosystem_certify.CertificationError, match="do not exactly cover"):
        ecosystem_certify.certify(manifest, tmp_path, "c" * 40)


def test_repository_only_verification_accepts_exact_41_results(manifests, tmp_path):
    ecosystem, runtime = manifests
    manifest = ecosystem_certify.validate_manifest(ecosystem, runtime)
    write_results(tmp_path, manifest, "2" * 40)
    for path in tmp_path.glob("scenario-*.json"):
        path.unlink()
    results = ecosystem_certify.verify_repository_results(manifest, tmp_path, "2" * 40)
    assert len(results) == 41


def test_scenario_verification_binds_traces_to_contract_and_revisions(manifests, tmp_path):
    ecosystem, runtime = manifests
    manifest = ecosystem_certify.validate_manifest(ecosystem, runtime)
    self_commit = "3" * 40
    write_results(tmp_path, manifest, self_commit)
    write_scenario_traces(tmp_path, manifest, self_commit)
    results = ecosystem_certify.verify_scenario_results(
        manifest, tmp_path, self_commit, verify_trace_files=True
    )
    assert len(results) == 8


def test_scenario_verification_rejects_mutated_trace(manifests, tmp_path):
    ecosystem, runtime = manifests
    manifest = ecosystem_certify.validate_manifest(ecosystem, runtime)
    self_commit = "4" * 40
    write_results(tmp_path, manifest, self_commit)
    write_scenario_traces(tmp_path, manifest, self_commit)
    path = next((tmp_path / "traces").glob("*.json"))
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ecosystem_certify.CertificationError, match="trace digest mismatch"):
        ecosystem_certify.verify_scenario_results(
            manifest, tmp_path, self_commit, verify_trace_files=True
        )


def test_certificate_rejects_wrong_revision(manifests, tmp_path):
    ecosystem, runtime = manifests
    manifest = ecosystem_certify.validate_manifest(ecosystem, runtime)
    write_results(tmp_path, manifest, "d" * 40)
    path = tmp_path / "repository-loomground-plugins.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    result["commit"] = "e" * 40
    path.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ecosystem_certify.CertificationError, match="pinned revision"):
        ecosystem_certify.certify(manifest, tmp_path, "d" * 40)


def test_certificate_rejects_failed_scenario(manifests, tmp_path):
    ecosystem, runtime = manifests
    manifest = ecosystem_certify.validate_manifest(ecosystem, runtime)
    write_results(tmp_path, manifest, "f" * 40)
    path = next(tmp_path.glob("scenario-*.json"))
    result = json.loads(path.read_text(encoding="utf-8"))
    result["status"] = "failed"
    path.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ecosystem_certify.CertificationError, match="did not pass"):
        ecosystem_certify.certify(manifest, tmp_path, "f" * 40)


def test_certificate_digest_detects_mutation(manifests, tmp_path):
    ecosystem, runtime = manifests
    manifest = ecosystem_certify.validate_manifest(ecosystem, runtime)
    write_results(tmp_path, manifest, "1" * 40)
    certificate = ecosystem_certify.certify(manifest, tmp_path, "1" * 40)
    certificate["repositories"][0]["checks"].append("mutated")
    with pytest.raises(ecosystem_certify.CertificationError, match="digest mismatch"):
        ecosystem_certify.verify_certificate(certificate)
