# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loomground_installer.core import InstallerError, create_plan, doctor, load_profiles, resolve_hosts


def fake_which(*available):
    paths = {name: f"/test/bin/{name}" for name in available}
    return paths.get


class InstallerTests(unittest.TestCase):
    def test_full_profile_is_exact_marketplace(self):
        profiles = load_profiles()["profiles"]
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(set(profiles["full"]), {entry["name"] for entry in marketplace["plugins"]})
        for names in profiles.values():
            self.assertEqual(names, sorted(set(names)))
            self.assertLessEqual(set(names), set(profiles["full"]))

    def test_wheel_metadata_declares_the_cli(self):
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertEqual(metadata["project"]["scripts"]["loomground"], "loomground_installer.cli:main")
        self.assertEqual(metadata["project"]["dependencies"], [])

    def test_auto_detects_hosts_without_executing_them(self):
        self.assertEqual(resolve_hosts(["auto"], fake_which("claude", "codex")), ("claude", "codex"))
        self.assertEqual(resolve_hosts([], fake_which("codex")), ("codex",))
        with self.assertRaisesRegex(InstallerError, "no supported host"):
            resolve_hosts([], fake_which())

    def test_plan_is_explicitly_non_mutating(self):
        plan = create_plan("compliance", ["claude"], fake_which("claude"))
        self.assertFalse(plan.mutates_system)
        self.assertEqual(plan.enforcement_mode, "advisory")
        self.assertEqual(plan.operations[0].kind, "runtime")
        self.assertFalse(any(operation.executable for operation in plan.operations))
        self.assertEqual(
            [operation.kind for operation in plan.operations[1:]],
            ["marketplace"] + ["plugin"] * len(plan.plugins),
        )

    def test_doctor_reads_codex_config_without_changing_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / ".codex" / "config.toml"
            config.parent.mkdir()
            config.write_text('[mcp_servers.loomground]\ncommand = "loomground-mcp"\nargs = ["serve", "--transport", "stdio"]\n')
            before = config.read_bytes()
            checks = doctor(["codex"], fake_which("codex", "loomground-mcp"), environment={}, home=root)
            self.assertEqual({check.name: check.status for check in checks}["codex-mcp"], "ok")
            self.assertEqual(config.read_bytes(), before)

    def test_cli_plan_json_makes_no_home_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = dict(os.environ)
            environment["HOME"] = temporary
            environment["PYTHONPATH"] = str(ROOT / "src")
            result = subprocess.run(
                [sys.executable, "-m", "loomground_installer.cli", "plan", "--profile", "core", "--host", "codex", "--json"],
                cwd=ROOT, env=environment, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(any(Path(temporary).iterdir()))
            self.assertFalse(json.loads(result.stdout)["mutates_system"])


if __name__ == "__main__":
    unittest.main()
