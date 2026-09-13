import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_packages  # noqa: E402


def canonical_packages():
    return sorted(build_packages.package_dirs([]), key=lambda path: path.name)


def plugin_manifests():
    return build_packages.all_plugin_manifests()


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

    def test_external_marketplace_sources_are_commit_locked(self):
        sources = build_packages.external_marketplace_sources()
        expected = {path.name for path in canonical_packages()} | {
            data["name"] for data in build_packages.external_plugin_manifests()
        }
        self.assertEqual(set(sources), expected)
        for source in sources.values():
            build_packages.validate_marketplace_source(source, ROOT / "externals.json")

    def test_mutable_external_source_is_rejected(self):
        mutable = {"source": "url", "url": "https://example.invalid/repo.git"}
        with self.assertRaisesRegex(build_packages.PackageError, "full 40-character"):
            build_packages.validate_marketplace_source(mutable, ROOT / "externals.json")

    def test_generated_manifests_credit_contributors_only(self):
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
            self.assertEqual(manifest["author"], {"name": "Loomground Contributors"})

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
        self.assertEqual(marketplace["owner"], {"name": "Loomground Contributors"})
        listed = [plugin["name"] for plugin in marketplace["plugins"]]
        plugins = plugin_manifests()
        expected = [path.name for path in canonical_packages()] + [data["name"] for data in plugins]
        self.assertEqual(listed, sorted(expected))
        locked_sources = build_packages.marketplace_sources()
        for package_dir in canonical_packages():
            data = json.loads((package_dir / "package.json").read_text())
            manifest = json.loads((package_dir / ".claude-plugin/plugin.json").read_text())
            self.assertEqual(manifest, build_packages.claude_manifest(data))
            entry = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == data["name"])
            expected_source = locked_sources.get(data["name"], f"./{data['name']}")
            self.assertEqual(entry["source"], expected_source)
            self.assertEqual(entry["version"], data["version"])
            self.assertEqual(entry["description"], data["description"])
        for data in plugins:
            entry = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == data["name"])
            self.assertEqual(entry["source"], locked_sources[data["name"]])
            self.assertEqual(entry["version"], data["version"])
            self.assertEqual(entry["description"], data["description"])
            self.assertEqual(entry["keywords"], data.get("keywords", []))
            if "mcpServers" in data:
                self.assertEqual(data["mcpServers"], build_packages.MCP_SERVERS)

    def test_suite_is_one_local_entry_point_with_valid_contract_schemas(self):
        suite = ROOT / "plugins/loomground-suite"
        codex = json.loads((suite / ".codex-plugin/plugin.json").read_text())
        claude = json.loads((suite / ".claude-plugin/plugin.json").read_text())
        mcp = json.loads((suite / ".mcp.json").read_text())
        self.assertEqual(codex["name"], "loomground-suite")
        self.assertEqual(claude["mcpServers"], mcp["mcpServers"])
        self.assertEqual(mcp["mcpServers"], build_packages.MCP_SERVERS)
        for name in ("action-intent.schema.json", "enforcement-receipt.schema.json"):
            schema = json.loads((suite / "schemas" / name).read_text())
            Draft202012Validator.check_schema(schema)

    def test_plugin_manifest_without_sibling_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            with self.assertRaisesRegex(build_packages.PackageError, "sibling checkout required"):
                build_packages.load_plugin_manifest("missing", Path(temporary))

    def test_built_packages_preserve_canonical_runtime_declarations(self):
        subprocess.run(
            [sys.executable, "tools/build_packages.py", "--target", "generic"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        for package_dir in canonical_packages():
            source = json.loads((package_dir / "package.json").read_text())
            built = json.loads(
                (ROOT / "dist/generic" / package_dir.name / "package.json").read_text()
            )
            self.assertEqual(built["runtime"], source["runtime"])


if __name__ == "__main__":
    unittest.main()
