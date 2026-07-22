import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The skill lives in-tree with its tool since the plugin migration; this policy
# test runs against the sibling checkout and skips when absent.
MODULE = ROOT.parent / "loomground-versum/skills/loomground-organise/scripts/suggest.py"
if not MODULE.exists():
    raise unittest.SkipTest(f"sibling checkout not available: {MODULE}")
SPEC = importlib.util.spec_from_file_location("loomground_organise_suggest", MODULE)
SUGGEST = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SUGGEST
SPEC.loader.exec_module(SUGGEST)


class OrganisePolicyTests(unittest.TestCase):
    def test_valid_modes_are_accepted(self):
        for mode in ("cascade", "cloud", "local", "deterministic"):
            self.assertEqual(SUGGEST.load_policy({"effort": {"mode": mode}}).mode, mode)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown effort mode"):
            SUGGEST.load_policy({"effort": {"mode": "nonsense"}})

    def test_invalid_thresholds_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "dominance"):
            SUGGEST.load_policy({"effort": {"dominance": 1.5}})
        with self.assertRaisesRegex(ValueError, "min_signal"):
            SUGGEST.load_policy({"effort": {"min_signal": -0.1}})

    def test_unknown_settings_and_invalid_shapes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown effort setting"):
            SUGGEST.load_policy({"effort": {"mod": "cascade"}})
        with self.assertRaisesRegex(ValueError, "must be a JSON object"):
            SUGGEST.load_policy({"effort": []})


if __name__ == "__main__":
    unittest.main()
