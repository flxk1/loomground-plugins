"""Behaviour smoke tests for the loomground-solver wrapper scripts.

Each analytic script must delegate to the installed kernel and return the kernel's
{choice, ranking, scores}. Run with the kernel importable on PYTHONPATH.
Fail-closed: with the kernel absent, a script must exit non-zero, not fabricate.
"""
import json, subprocess, sys, os
from pathlib import Path

SK = Path(__file__).resolve().parents[1] / "loomground-solver" / "skills"

def _run(script, payload, env=None):
    p = subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stdout, p.stderr

def test_opponent_modeler_expected_utility():
    rc, out, _ = _run(SK/"opponent-modeler/scripts/run.py",
                      {"payoffs": {"bluff": {"call": -2, "fold": 3}, "check": {"call": 1, "fold": 0}},
                       "probabilities": {"call": 0.6, "fold": 0.4}})
    assert rc == 0, out
    assert json.loads(out)["result"]["choice"] == "check"

def test_probability_tracker_bayes():
    rc, out, _ = _run(SK/"probability-tracker/scripts/run.py",
                      {"prior": {"guilty": 0.3, "innocent": 0.7},
                       "likelihoods": {"guilty": {"match": 0.9}, "innocent": {"match": 0.2}},
                       "evidence": "match"})
    assert rc == 0, out
    r = json.loads(out)["result"]
    assert r["choice"] == "guilty" and abs(r["scores"]["guilty"] - 0.658537) < 1e-4

def test_fail_closed_without_kernel():
    env = dict(os.environ, PYTHONPATH="/nonexistent-kernel-path")
    rc, out, err = _run(SK/"analyse-risks/scripts/run.py", {"vectors": {"a": [1, 1]}}, env=env)
    assert rc == 2 and "error" in err.lower()
