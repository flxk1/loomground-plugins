"""Behaviour tests for the rvnd-build-surface linter.

The linter is deterministic and offline. It must accept honest surfaces and
fail closed on any that could show a request as a grant: a proposal card with
'granted' in its status vocabulary, a composition that renders 'proposal'
without 'patch' and 'receipt', a non-fail-closed composition, or a missing
attribution/score flag.
"""
import json, subprocess, sys
from pathlib import Path

LINT = (Path(__file__).resolve().parents[1] / "rvnd-governance" / "skills"
        / "rvnd-build-surface" / "scripts" / "lint_surface.py")


def _run(payload):
    p = subprocess.run([sys.executable, str(LINT)], input=json.dumps(payload),
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def test_valid_composition_passes():
    rc, out, err = _run({
        "name": "govern-flow", "server": "rvnd-governance",
        "skills": ["rvnd-govern"],
        "cards": ["context", "proposal", "patch", "decision", "receipt"],
        "fail_closed": True, "human_confirmation": True,
    })
    assert rc == 0, err
    assert json.loads(out)["valid"] is True


def test_proposal_without_receipt_fails_closed():
    rc, _, err = _run({
        "name": "bad-flow", "server": "rvnd-governance",
        "skills": ["rvnd-govern"], "cards": ["context", "proposal", "patch"],
        "fail_closed": True,
    })
    assert rc == 1 and "receipt" in err


def test_non_fail_closed_composition_rejected():
    rc, _, err = _run({
        "name": "leaky", "server": "rvnd-governance",
        "skills": ["rvnd-audit"], "cards": ["context"], "fail_closed": False,
    })
    assert rc == 1 and "fail_closed" in err


def test_proposal_card_granted_vocabulary_rejected():
    rc, _, err = _run({
        "card": "proposal", "step": "propose",
        "reads": ["propose"], "renders": ["requested change"],
        "status_vocabulary": ["requested", "granted"],
        "forbids_scores": True, "attributed": True,
    })
    assert rc == 1 and "granted" in err.lower()


def test_valid_proposal_card_passes():
    rc, out, err = _run({
        "card": "proposal", "step": "propose",
        "reads": ["propose"], "renders": ["requested change", "direction"],
        "status_vocabulary": ["requested", "pending", "proposed"],
        "forbids_scores": True, "attributed": True,
    })
    assert rc == 0, err
    assert json.loads(out)["kind"] == "card"


def test_unknown_shape_fails_closed():
    rc, _, err = _run({"nonsense": True})
    assert rc == 2 and "card" in err


def _proposal(**over):
    p = {
        "proposal_id": "p1",
        "intent": {"text": "Maria must approve external publication", "actor": "user_17", "host": "chat"},
        "scope": {"boundary_id": "bnd_press_kit", "members": ["folder:press-kit"]},
        "loomground": {"language_version": "0.8.0a1",
                       "constructs": [{"type": "reservation", "kind": "external-publication"}]},
        "residual": [],
        "validation": {"well_formed": True},
        "versions": {"loomground_language": "0.8.0a1"},
        "confirmation": {"required": True},
    }
    p.update(over)
    return p


def test_valid_proposal_passes():
    rc, out, err = _run(_proposal())
    assert rc == 0, err
    assert json.loads(out)["kind"] == "proposal"


def test_proposal_invented_construct_rejected():
    rc, _, err = _run(_proposal(loomground={
        "language_version": "0.8.0a1",
        "constructs": [{"type": "responsibly"}]}))
    assert rc == 1 and "not a real" in err


def test_proposal_missing_version_rejected():
    rc, _, err = _run(_proposal(versions={}))
    assert rc == 1 and "loomground_language" in err
