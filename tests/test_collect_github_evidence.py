import copy
import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import collect_github_evidence  # noqa: E402
import ecosystem_certify  # noqa: E402


@pytest.fixture
def inventory():
    manifest = ecosystem_certify.validate_manifest(
        ecosystem_certify.load_json(ROOT / "ecosystem/manifest.json"),
        ecosystem_certify.load_json(ROOT / "runtime/runtime-sources.json"),
    )
    contract_document = ecosystem_certify.load_json(
        ROOT / "ecosystem/repository-checks.json"
    )
    contracts = collect_github_evidence.validate_check_contract(
        contract_document, manifest
    )
    return manifest, contract_document, contracts


def successful_fetch(contracts):
    def fetch(owner, name, commit, token):
        assert owner == "flxk1"
        assert token == "token"
        return [
            {
                "id": index + 1,
                "name": check,
                "head_sha": commit,
                "status": "completed",
                "conclusion": "success",
                "details_url": f"https://github.com/{owner}/{name}/checks/{index + 1}",
                "app": {"slug": "github-actions"},
            }
            for index, check in enumerate(reversed(contracts[name]))
        ]

    return fetch


def test_check_contract_exactly_covers_manifest(inventory):
    manifest, _, contracts = inventory
    assert list(contracts) == [repo["name"] for repo in manifest["repositories"]]
    assert all(checks == sorted(set(checks)) for checks in contracts.values())


def test_check_contract_rejects_missing_repository(inventory):
    manifest, document, _ = inventory
    altered = copy.deepcopy(document)
    altered["repositories"].pop()
    with pytest.raises(collect_github_evidence.EvidenceError, match="exactly cover"):
        collect_github_evidence.validate_check_contract(altered, manifest)


def test_passing_result_requires_every_check_at_exact_commit():
    commit = "a" * 40
    evidence = collect_github_evidence.normalize_evidence(
        "flxk1",
        "example",
        commit,
        ["release", "test"],
        [
            {"id": 2, "name": "test", "head_sha": commit, "status": "completed", "conclusion": "success", "details_url": "two", "app": {"slug": "actions"}},
            {"id": 1, "name": "release", "head_sha": commit, "status": "completed", "conclusion": "success", "details_url": "one", "app": {"slug": "actions"}},
        ],
    )
    result = collect_github_evidence.passing_result(evidence)
    assert result["checks"] == ["release", "test"]
    assert result["commit"] == commit


@pytest.mark.parametrize("field,value", [("head_sha", "b" * 40), ("status", "in_progress"), ("conclusion", "failure")])
def test_passing_result_rejects_stale_or_failed_check(field, value):
    commit = "a" * 40
    run = {"id": 1, "name": "test", "head_sha": commit, "status": "completed", "conclusion": "success", "details_url": "one", "app": {"slug": "actions"}}
    run[field] = value
    evidence = collect_github_evidence.normalize_evidence(
        "flxk1", "example", commit, ["test"], [run]
    )
    with pytest.raises(collect_github_evidence.EvidenceError, match="lacks successful"):
        collect_github_evidence.passing_result(evidence)


def test_collect_writes_complete_revision_bound_result_set(inventory, tmp_path):
    manifest, _, contracts = inventory
    self_commit = "c" * 40
    passed, failures = collect_github_evidence.collect(
        manifest,
        contracts,
        self_commit,
        tmp_path / "results",
        "token",
        fetch=successful_fetch(contracts),
    )
    assert passed == 41
    assert failures == []
    result_files = sorted((tmp_path / "results").glob("repository-*.json"))
    assert len(result_files) == 41
    for path in result_files:
        result = ecosystem_certify.load_json(path)
        evidence_path = tmp_path / "results/evidence" / f"{result['name']}.json"
        assert result["evidence_sha256"] == hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    own = ecosystem_certify.load_json(
        tmp_path / "results/repository-loomground-plugins.json"
    )
    assert own["commit"] == self_commit
    verified = ecosystem_certify.verify_repository_results(
        manifest, tmp_path / "results", self_commit, verify_evidence_files=True
    )
    assert len(verified) == 41


def test_repository_evidence_mutation_is_detected(inventory, tmp_path):
    manifest, _, contracts = inventory
    output = tmp_path / "results"
    collect_github_evidence.collect(
        manifest, contracts, "3" * 40, output, "token", fetch=successful_fetch(contracts)
    )
    (output / "evidence/loomground.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ecosystem_certify.CertificationError, match="digest mismatch"):
        ecosystem_certify.verify_repository_results(
            manifest, output, "3" * 40, verify_evidence_files=True
        )


def test_collect_reports_partial_evidence_without_fabricating_pass(inventory, tmp_path):
    manifest, _, contracts = inventory
    fetch = successful_fetch(contracts)

    def one_missing(owner, name, commit, token):
        if name == "oversight-certificate":
            return []
        return fetch(owner, name, commit, token)

    passed, failures = collect_github_evidence.collect(
        manifest, contracts, "d" * 40, tmp_path / "results", "token", fetch=one_missing
    )
    assert passed == 40
    assert len(failures) == 1
    assert "oversight-certificate" in failures[0]
    assert not (tmp_path / "results/repository-oversight-certificate.json").exists()


def test_collect_refuses_nonempty_output(inventory, tmp_path):
    manifest, _, contracts = inventory
    output = tmp_path / "results"
    output.mkdir()
    (output / "stale.json").write_text("{}", encoding="utf-8")
    with pytest.raises(collect_github_evidence.EvidenceError, match="absent or empty"):
        collect_github_evidence.collect(
            manifest, contracts, "e" * 40, output, "token", fetch=successful_fetch(contracts)
        )


def test_collect_can_delegate_explicit_backfill_repositories(inventory, tmp_path):
    manifest, _, contracts = inventory
    excluded = {"loomground-factual", "oversight-certificate"}
    passed, failures = collect_github_evidence.collect(
        manifest,
        contracts,
        "f" * 40,
        tmp_path / "results",
        "token",
        excluded,
        fetch=successful_fetch(contracts),
    )
    assert passed == 39
    assert failures == []
    assert not (tmp_path / "results/repository-loomground-factual.json").exists()
