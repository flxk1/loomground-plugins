import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def canonical_packages():
    local = [path.parent for path in ROOT.glob("*/package.json") if path.parent.parent == ROOT]
    externals = json.loads((ROOT / "externals.json").read_text()) if (ROOT / "externals.json").is_file() else {}
    external = [(ROOT / rel).resolve() for rel in externals.values()]
    return sorted(local + external, key=lambda path: path.name)


class PackageBuildTests(unittest.TestCase):
    def test_all_canonical_packages_validate_and_build(self):
        result = subprocess.run(
            [sys.executable, "tools/build_packages.py", "--target", "all"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for package in (path.name for path in canonical_packages()):
            for target in ("claude", "codex", "generic"):
                self.assertTrue((ROOT / "dist" / target / package / "skills").is_dir())

    def test_validate_and_build_single_package(self):
        result = subprocess.run(
            [sys.executable, "tools/build_packages.py", "loomground-versum", "--target", "all"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for target in ("claude", "codex", "generic"):
            self.assertTrue((ROOT / "dist" / target / "loomground-versum" / "skills").is_dir())
        manifest = json.loads((ROOT / "dist/codex/loomground-versum/.codex-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], "loomground-versum")
        self.assertEqual(manifest["skills"], "./skills/")

    def test_bad_package_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            package = Path(temporary)
            (package / "package.json").write_text("{}", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "tools/build_packages.py", package.name, "--validate-only"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_generated_manifests_credit_flxk1_only(self):
        subprocess.run(
            [sys.executable, "tools/build_packages.py", "loomground-versum", "--target", "all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        paths = (
            ROOT / "dist/claude/loomground-versum/.claude-plugin/plugin.json",
            ROOT / "dist/codex/loomground-versum/.codex-plugin/plugin.json",
        )
        for path in paths:
            manifest = json.loads(path.read_text())
            self.assertEqual(manifest["author"], {"name": "flxk1"})

    def test_canonical_packages_match_json_schema(self):
        schema = json.loads((ROOT / "schemas/loomground-package.schema.json").read_text())
        validator = Draft202012Validator(schema)
        for package_dir in canonical_packages():
            manifest = json.loads((package_dir / "package.json").read_text())
            errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.path))
            self.assertEqual(errors, [], f"{package_dir.name}: {[error.message for error in errors]}")

    def test_generated_packages_exclude_platform_metadata(self):
        stale = ROOT / "dist/claude/removed-package"
        stale.mkdir(parents=True, exist_ok=True)
        (stale / "marker").write_text("stale", encoding="utf-8")
        subprocess.run(
            [sys.executable, "tools/build_packages.py", "--target", "all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        self.assertEqual(list((ROOT / "dist").rglob(".DS_Store")), [])
        self.assertEqual(list((ROOT / "dist").rglob("__pycache__")), [])
        self.assertFalse(stale.exists())

    def test_committed_claude_artifacts_are_in_sync(self):
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(marketplace["owner"], {"name": "flxk1"})
        listed = [plugin["name"] for plugin in marketplace["plugins"]]
        self.assertEqual(listed, [path.name for path in canonical_packages()])
        for package_dir in canonical_packages():
            data = json.loads((package_dir / "package.json").read_text())
            manifest = json.loads((package_dir / ".claude-plugin/plugin.json").read_text())
            self.assertEqual(manifest["name"], data["name"])
            self.assertEqual(manifest["version"], data["version"])
            self.assertEqual(manifest["description"], data["description"])
            entry = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == data["name"])
            expected_source = data["adapters"]["claude"].get("marketplaceSource", f"./{data['name']}")
            self.assertEqual(entry["source"], expected_source)
            self.assertEqual(entry["version"], data["version"])
            self.assertEqual(entry["description"], data["description"])

    def test_runtime_dependencies_are_declared(self):
        expected = {
            "loomground-governance": ["loomground-governance"],
            "loomground-solver": ["loomground-governance", "loomground-solver"],
            "loomground-versum": ["versum"],
        }
        actual = {
            package_dir.name: json.loads((package_dir / "package.json").read_text())["runtime"]["requires"]
            for package_dir in canonical_packages()
        }
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
