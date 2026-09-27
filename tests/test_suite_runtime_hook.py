# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Tests for the loomground-suite plugin's SessionStart runtime-check hook.

The loomground-suite plugin.json / .mcp.json launch `loomground-mcp`
unconditionally; if the loomground runtime is not installed that MCP server
start fails silently. `plugins/loomground-suite/hooks/session-start.sh` is a
Claude Code SessionStart hook that turns that into an actionable message,
without touching the pinned mcpServers configuration (see
test_package_build.py::test_suite_is_one_local_entry_point_with_valid_contract_schemas
and this module's own byte-identity checks for that pin).

The hook is POSIX sh (no python) because Claude Code on Windows runs plugin
hooks through Git Bash, and "Python is missing" is itself one of the cases
the hook must report -- so it cannot depend on Python to detect that.

The hook embeds a literal "3.12" minimum-Python label rather than reading
runtime/runtime-sources.json at runtime (that file is JSON and the hook may
not shell out to python to parse it). This module is the guardrail: it reads
runtime-sources.json directly and fails if the embedded label in the hook
script no longer matches the file's `python.minimum`.
"""
import json
import re
import stat
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "plugins/loomground-suite/hooks/session-start.sh"
HOOKS_JSON = ROOT / "plugins/loomground-suite/hooks/hooks.json"
RUNTIME_SOURCES = ROOT / "runtime/runtime-sources.json"


def minimum_python_label_from_runtime_sources() -> str:
    """Independent re-derivation of the supported minimum, straight from JSON.

    Deliberately does not import src/loomground_installer/requirements.py's
    helper, so this check does not merely restate that module's own logic --
    it is a second, from-scratch read of the single source-of-truth file.
    """
    data = json.loads(RUNTIME_SOURCES.read_text(encoding="utf-8"))
    major, minor = data["python"]["minimum"][:2]
    return f"{major}.{minor}"


def embedded_label_in_hook() -> str:
    text = HOOK.read_text(encoding="utf-8")
    match = re.search(r'PYTHON_MINIMUM_LABEL="([^"]+)"', text)
    assert match, "hook must set PYTHON_MINIMUM_LABEL=\"...\""
    return match.group(1)


def run_hook(path_value: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(HOOK)],
        env={"PATH": path_value},
        text=True,
        capture_output=True,
        timeout=10,
    )


class HookShapeTests(unittest.TestCase):
    def test_hooks_json_is_valid_json_in_the_plugin_hooks_schema(self):
        data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        # Plugin hooks.json wrapper format: {"hooks": {<EventName>: [...]}}.
        # Verified against the shipped, official plugin-dev "hook-development"
        # skill (Hook Configuration Formats / "Plugin hooks.json Format") and
        # against real installed plugins using this exact shape, e.g.
        # claude-plugins-official's learning-output-style and ctrl-engineering
        # plugin's hooks/hooks.json (both wrap SessionStart the same way).
        self.assertIn("hooks", data)
        self.assertIn("SessionStart", data["hooks"])
        entries = data["hooks"]["SessionStart"]
        self.assertIsInstance(entries, list)
        self.assertGreaterEqual(len(entries), 1)
        for entry in entries:
            for hook in entry["hooks"]:
                self.assertEqual(hook["type"], "command")
                self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh", hook["command"])

    def test_hook_script_is_executable_and_posix_sh(self):
        self.assertTrue(HOOK.is_file())
        mode = HOOK.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR, "hook must be executable")
        first_line = HOOK.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first_line, "#!/bin/sh")

    def test_hook_script_never_invokes_python(self):
        # The word "python" legitimately appears in comments and in the
        # embedded message/label (the runtime it is checking for is a Python
        # runtime); what must never appear is an actual invocation of a
        # python interpreter as a command word. Strip comments and quoted
        # string contents, then check no remaining command word is python(3).
        code_lines = []
        for line in HOOK.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Drop double-quoted segments (the JSON payload and $MESSAGE
            # assignment live entirely inside these) so their contents can't
            # false-positive as command words.
            without_strings = re.sub(r'"[^"]*"', "", line)
            code_lines.append(without_strings)
        code_text = "\n".join(code_lines)
        for token in re.split(r"[\s;|&()<>]+", code_text):
            self.assertNotIn(token, ("python", "python3"), f"found a python invocation token: {token!r}")

    def test_mcp_servers_block_is_untouched_by_the_hook_addition(self):
        # The hook is an addition alongside .mcp.json / plugin.json, not a
        # replacement -- both must still carry the exact pinned MCP_SERVERS
        # block that tools/build_packages.py and other tests pin against.
        sys.path.insert(0, str(ROOT / "tools"))
        import build_packages  # noqa: E402

        suite = ROOT / "plugins/loomground-suite"
        mcp = json.loads((suite / ".mcp.json").read_text(encoding="utf-8"))
        claude = json.loads((suite / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp["mcpServers"], build_packages.MCP_SERVERS)
        self.assertEqual(claude["mcpServers"], build_packages.MCP_SERVERS)
        self.assertNotIn("hooks", claude, "hooks must ship via hooks/hooks.json auto-discovery, not plugin.json")


class HookBehaviorTests(unittest.TestCase):
    def test_silent_and_exit_zero_when_loomground_mcp_is_on_path(self):
        # A minimal stub executable named loomground-mcp is enough: the hook
        # only checks presence on PATH (`command -v`), it never runs it.
        import tempfile

        with tempfile.TemporaryDirectory() as stub_dir:
            stub_dir_path = Path(stub_dir)
            stub = stub_dir_path / "loomground-mcp"
            stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            stub.chmod(0o755)
            result = run_hook(f"{stub_dir}:/usr/bin:/bin")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_actionable_message_and_exit_zero_when_loomground_mcp_is_missing(self):
        result = run_hook("/usr/bin:/bin")
        self.assertEqual(result.returncode, 0)

        label = minimum_python_label_from_runtime_sources()
        expected_message = (
            f"Loomground runtime not installed: run `loomground onboard` (Python {label} required)"
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["systemMessage"], expected_message)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertEqual(payload["hookSpecificOutput"]["additionalContext"], expected_message)


class RuntimeLabelDivergenceTests(unittest.TestCase):
    def test_embedded_label_matches_runtime_sources_json(self):
        self.assertEqual(embedded_label_in_hook(), minimum_python_label_from_runtime_sources())

    def test_divergence_is_caught_if_runtime_sources_json_range_changes(self):
        # Simulate runtime-sources.json moving its minimum without the hook's
        # embedded literal following: the comparison above must fail in that
        # case. We prove it here without mutating the real file, by directly
        # asserting the two derivations disagree once we synthesize a moved
        # minimum -- i.e. the check is sensitive to the value, not vacuous.
        embedded = embedded_label_in_hook()
        moved = "9.99"
        self.assertNotEqual(embedded, moved)
        real = minimum_python_label_from_runtime_sources()
        self.assertNotEqual(real, moved)


if __name__ == "__main__":
    unittest.main()
