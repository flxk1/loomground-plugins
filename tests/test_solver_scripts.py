"""Behaviour smoke tests for the loomground-solver wrapper scripts.

Each analytic script must delegate to the installed kernel and return the kernel's
{choice, ranking, scores}. Run with the kernel importable on PYTHONPATH.
Fail-closed: with the kernel absent, a script must exit non-zero, not fabricate.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SK = Path(__file__).resolve().parents[1] / "loomground-solver" / "skills"
try:
    from loomground_solver import method as _kernel_method
except ImportError:
    KERNEL_AVAILABLE = False
else:
    KERNEL_AVAILABLE = callable(_kernel_method)

def _run(script, payload, env=None):
    p = subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stdout, p.stderr

def test_opponent_modeler_expected_utility():
    if not KERNEL_AVAILABLE:
        import pytest
        pytest.skip("loomground-solver kernel is not installed")
    rc, out, _ = _run(SK/"opponent-modeler/scripts/run.py",
                      {"payoffs": {"bluff": {"call": -2, "fold": 3}, "check": {"call": 1, "fold": 0}},
                       "probabilities": {"call": 0.6, "fold": 0.4}})
    assert rc == 0, out
    assert json.loads(out)["result"]["choice"] == "check"

def test_probability_tracker_bayes():
    if not KERNEL_AVAILABLE:
        import pytest
        pytest.skip("loomground-solver kernel is not installed")
    rc, out, _ = _run(SK/"probability-tracker/scripts/run.py",
                      {"prior": {"guilty": 0.3, "innocent": 0.7},
                       "likelihoods": {"guilty": {"match": 0.9}, "innocent": {"match": 0.2}},
                       "evidence": "match"})
    assert rc == 0, out
    r = json.loads(out)["result"]
    assert r["choice"] == "guilty" and abs(r["scores"]["guilty"] - 0.658537) < 1e-4

def test_fail_closed_without_kernel(tmp_path):
    # A bare nonexistent PYTHONPATH entry cannot hide a kernel installed in
    # site-packages; a stub package that raises on import shadows any install.
    stub = tmp_path / "loomground_solver"
    stub.mkdir()
    (stub / "__init__.py").write_text("raise ImportError('kernel unavailable')\n")
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    for script in sorted(SK.glob("*/scripts/run.py")):
        rc, out, err = _run(script, {"vectors": {"a": [1, 1]}}, env=env)
        assert rc == 2 and "error" in err.lower(), (script, rc, out, err)
