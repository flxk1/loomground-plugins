import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ecosystem_certify  # noqa: E402
import emit_native_test_result  # noqa: E402


def test_emit_binds_log_and_commit(tmp_path):
    log = tmp_path / "test.log"
    log.write_bytes(b"17 passed\n")
    output = tmp_path / "results"
    result = emit_native_test_result.emit("oversight-certificate", "a" * 40, log, output)
    evidence = output / "evidence/oversight-certificate.json"
    assert result["commit"] == "a" * 40
    assert result["checks"] == ["test"]
    assert result["evidence_sha256"] == hashlib.sha256(evidence.read_bytes()).hexdigest()
    assert ecosystem_certify.load_json(evidence)["log_sha256"] == hashlib.sha256(log.read_bytes()).hexdigest()
    assert (output / "logs/oversight-certificate.log").read_bytes() == log.read_bytes()


@pytest.mark.parametrize("name,commit", [("Bad Name", "a" * 40), ("valid", "short")])
def test_emit_rejects_invalid_identity(tmp_path, name, commit):
    log = tmp_path / "test.log"
    log.write_text("pass", encoding="utf-8")
    with pytest.raises(ValueError):
        emit_native_test_result.emit(name, commit, log, tmp_path / "results")


def test_emit_rejects_empty_log(tmp_path):
    log = tmp_path / "test.log"
    log.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        emit_native_test_result.emit("valid", "b" * 40, log, tmp_path / "results")


def test_native_log_mutation_is_detected(tmp_path):
    log = tmp_path / "test.log"
    log.write_text("pass", encoding="utf-8")
    output = tmp_path / "results"
    emit_native_test_result.emit("only-repo", "c" * 40, log, output)
    (output / "logs/only-repo.log").write_text("mutated", encoding="utf-8")
    manifest = {
        "repositories": [{"name": "only-repo", "revision": "c" * 40}]
    }
    with pytest.raises(ecosystem_certify.CertificationError, match="log digest mismatch"):
        ecosystem_certify.verify_repository_results(
            manifest, output, "d" * 40, verify_evidence_files=True
        )
