import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The skills live in-tree with their tools since the plugin migration; these
# behavior tests run against the sibling checkouts and skip when absent.
ORGANISE = ROOT.parent / "loomground-versum/skills/loomground-organise/scripts/organise.py"
KG_QUERY = ROOT.parent / "loomground-kg/skills/loomground-kg/scripts/kg_query.py"


class CliBehaviorTests(unittest.TestCase):
    def run_cli(self, *args):
        script = Path(args[0])
        if not script.exists():
            self.skipTest(f"sibling checkout not available: {script}")
        return subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True)

    def test_organiser_rejects_missing_paths(self):
        missing = ROOT / "does-not-exist"
        result = self.run_cli(ORGANISE, "list", "--review", missing)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("review directory not found", result.stderr)
        result = self.run_cli(ORGANISE, "suggest", "--store", missing, "--concepts", "a")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("concept store not found", result.stderr)

    def test_organiser_rejects_invalid_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "policy.json"
            path.write_text(json.dumps({"effort": {"mode": "magic"}}))
            result = self.run_cli(ORGANISE, "config", path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown effort mode", result.stderr)

    def test_organiser_rejects_invalid_top_k(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            (store / "by-domain").mkdir()
            result = self.run_cli(ORGANISE, "suggest", "--store", store,
                                  "--concepts", "a", "--top-k", "0")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--top-k must be at least 1", result.stderr)

    def test_kg_query_rejects_missing_config_and_arguments(self):
        result = self.run_cli(KG_QUERY, "status", "--config", ROOT / "missing-config.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("KG config not found", result.stderr)
        for command in ("urn", "search"):
            result = self.run_cli(KG_QUERY, command)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires an argument", result.stderr)

    def test_kg_query_rejects_invalid_limit(self):
        result = self.run_cli(KG_QUERY, "status", "--limit", "0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--limit must be at least 1", result.stderr)


if __name__ == "__main__":
    unittest.main()
