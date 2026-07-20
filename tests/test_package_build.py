import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


class PackageBuildTests(unittest.TestCase):
    def test_all_canonical_packages_validate_and_build(self):
        result = subprocess.run(
            [sys.executable, "tools/build_packages.py", "--target", "all"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for package in ("loomground-kg", "loomground-versum", "solver-addons"):
            for target in ("claude", "codex", "generic"):
                self.assertTrue((ROOT / "dist" / target / package / "skills").is_dir())

    def test_validate_and_build_versum(self):
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
        for package in ("loomground-kg", "loomground-versum", "solver-addons"):
            manifest = json.loads((ROOT / package / "package.json").read_text())
            errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.path))
            self.assertEqual(errors, [], f"{package}: {[error.message for error in errors]}")

    def test_generated_packages_exclude_platform_metadata(self):
        subprocess.run(
            [sys.executable, "tools/build_packages.py", "--target", "all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        self.assertEqual(list((ROOT / "dist").rglob(".DS_Store")), [])
        self.assertEqual(list((ROOT / "dist").rglob("__pycache__")), [])

    def test_runtime_dependencies_are_declared(self):
        versum = json.loads((ROOT / "loomground-versum/package.json").read_text())
        solver = json.loads((ROOT / "solver-addons/package.json").read_text())
        self.assertEqual(versum["runtime"]["requires"], ["versum"])
        self.assertEqual(solver["runtime"]["requires"], ["loomground-language", "loomground-solver"])


if __name__ == "__main__":
    unittest.main()
