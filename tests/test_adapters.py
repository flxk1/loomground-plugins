# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loomground_installer.adapters import CONTROL_TOOLS, HOSTS, render_adapter  # noqa: E402
from loomground_installer.bundle import BundleError  # noqa: E402


class HostAdapterTests(unittest.TestCase):
    def test_every_declared_host_renders_one_loomground_endpoint(self):
        destination = Path("/opt/loomground/runtime")
        remote = "https://loomground.example/mcp"
        rendered = {
            host: render_adapter(
                host,
                runtime_destination=destination,
                server_url=remote if host in {"n8n", "openai"} else None,
            )
            for host in HOSTS
        }
        self.assertEqual(set(rendered), {"claude", "codex", "cursor", "n8n", "openai", "generic"})
        self.assertEqual(
            rendered["claude"]["content"],
            rendered["cursor"]["content"],
        )
        self.assertIn("/opt/loomground/runtime/bin/loomground-mcp", rendered["codex"]["content"])
        self.assertEqual(rendered["openai"]["content"]["server_url"], remote)
        self.assertEqual(rendered["n8n"]["parameters"]["SSE Endpoint"], remote)
        self.assertEqual(tuple(rendered["n8n"]["parameters"]["Selected Tools"]), CONTROL_TOOLS)
        self.assertFalse(any(item["secret_material_included"] for item in rendered.values()))

    def test_local_adapters_require_an_absolute_runtime_destination(self):
        for host in ("claude", "codex", "cursor"):
            with self.subTest(host=host), self.assertRaisesRegex(BundleError, "absolute runtime"):
                render_adapter(host, runtime_destination=Path("relative"))

    def test_remote_adapters_reject_insecure_non_loopback_and_url_credentials(self):
        with self.assertRaisesRegex(BundleError, "must use HTTPS"):
            render_adapter("n8n", server_url="http://loomground.example/sse")
        with self.assertRaisesRegex(BundleError, "must not contain credentials"):
            render_adapter("openai", server_url="https://token@loomground.example/mcp")
        local = render_adapter("n8n", server_url="http://127.0.0.1:8765/sse")
        self.assertEqual(local["parameters"]["SSE Endpoint"], "http://127.0.0.1:8765/sse")

    def test_cli_renders_machine_readable_cursor_configuration(self):
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [
                sys.executable, "-m", "loomground_installer.cli", "adapter",
                "--host", "cursor", "--runtime-destination", "/opt/loomground/runtime",
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = json.loads(result.stdout)
        self.assertEqual(rendered["destination_hint"], ".cursor/mcp.json")
        self.assertEqual(
            rendered["content"]["mcpServers"]["loomground"]["command"],
            "/opt/loomground/runtime/bin/loomground-mcp",
        )


if __name__ == "__main__":
    unittest.main()
