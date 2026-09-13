"""Unit tests for the supply-chain SBOM builder's path handling."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import supply_chain_gate  # noqa: E402


class NodeModulesPathTests(unittest.TestCase):
    def _leaf(self, path: str) -> str:
        return path.rsplit("node_modules/", 1)[-1]

    def test_nested_node_modules_yields_leaf_package_name(self):
        # A nested dependency path must resolve to the leaf package, not the
        # first-level survivor left behind by a single-prefix strip.
        self.assertEqual(
            self._leaf("node_modules/foo/node_modules/bar"), "bar"
        )

    def test_top_level_node_modules_unchanged(self):
        self.assertEqual(self._leaf("node_modules/foo"), "foo")

    def test_builder_records_leaf_name_for_nested_dependency(self):
        items: dict[str, dict] = {}
        path = "node_modules/foo/node_modules/bar"
        supply_chain_gate.add(
            items, self._leaf(path), "1.2.3", "MIT", "package-lock.json"
        )
        self.assertIn("bar@1.2.3", items)
        self.assertEqual(items["bar@1.2.3"]["name"], "bar")


if __name__ == "__main__":
    unittest.main()
