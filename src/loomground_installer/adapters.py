# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Pure host-registration renderers for one installed Loomground runtime."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from .bundle import BundleError

HOSTS = ("claude", "codex", "cursor", "n8n", "openai", "generic")
CONTROL_TOOLS = (
    "loomground_catalogue",
    "loomground_skill",
    "policy_compile",
    "policy_check",
    "privacy_scan",
    "lane_evaluate",
    "drift_breaker",
    "a2a_plan",
    "a2a_admission_preview",
    "a2a_reconcile",
    "effect_reconcile",
    "evidence_verify",
)


def _launcher(destination: Path | None) -> str:
    if destination is None or not destination.is_absolute() or destination == Path(destination.anchor):
        raise BundleError("local host adapter requires an explicit absolute runtime destination")
    return str(destination / "bin" / "loomground-mcp")


def _remote_url(value: str | None) -> str:
    if not value:
        raise BundleError("remote host adapter requires --server-url")
    parsed = urlparse(value)
    loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme not in ({"http", "https"} if loopback else {"https"}) or not parsed.netloc:
        raise BundleError("remote MCP URL must use HTTPS, except for an explicit loopback URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise BundleError("remote MCP URL must not contain credentials or a fragment")
    return value


def _stdio_config(launcher: str) -> dict:
    return {
        "mcpServers": {
            "loomground": {
                "command": launcher,
                "args": ["serve", "--transport", "stdio"],
            }
        }
    }


def render_adapter(
    host: str,
    *,
    runtime_destination: Path | None = None,
    server_url: str | None = None,
) -> dict:
    if host not in HOSTS:
        raise BundleError(f"unsupported host adapter {host!r}")
    if host in {"claude", "cursor"}:
        config = _stdio_config(_launcher(runtime_destination))
        return {
            "schema_version": 1,
            "host": host,
            "transport": "stdio",
            "destination_hint": ".mcp.json" if host == "claude" else ".cursor/mcp.json",
            "content": config,
            "secret_material_included": False,
        }
    if host == "codex":
        launcher = _launcher(runtime_destination)
        toml = (
            "[mcp_servers.loomground]\n"
            f"command = {json.dumps(launcher)}\n"
            'args = ["serve", "--transport", "stdio"]\n'
        )
        return {
            "schema_version": 1,
            "host": "codex",
            "transport": "stdio",
            "destination_hint": "$CODEX_HOME/config.toml",
            "merge": "mcp_servers.loomground",
            "content": toml,
            "secret_material_included": False,
        }
    if host == "openai":
        url = _remote_url(server_url)
        return {
            "schema_version": 1,
            "host": "openai",
            "transport": "remote-mcp",
            "content": {
                "type": "mcp",
                "server_label": "loomground",
                "server_url": url,
                "require_approval": "always",
            },
            "secret_binding": "Resolve the bearer token from the application's secret store and set authorization at request time.",
            "secret_material_included": False,
        }
    if host == "n8n":
        url = _remote_url(server_url)
        return {
            "schema_version": 1,
            "host": "n8n",
            "transport": "sse",
            "node": "MCP Client Tool",
            "parameters": {
                "SSE Endpoint": url,
                "Authentication": "Bearer credential",
                "Tools to Include": "Selected",
                "Selected Tools": list(CONTROL_TOOLS),
            },
            "secret_binding": "Create an n8n bearer credential; do not place the token in workflow JSON.",
            "secret_material_included": False,
        }
    if server_url:
        content = {"mcpServers": {"loomground": {"url": _remote_url(server_url)}}}
        transport = "remote-mcp"
    else:
        content = _stdio_config(_launcher(runtime_destination))
        transport = "stdio"
    return {
        "schema_version": 1,
        "host": "generic",
        "transport": transport,
        "content": content,
        "secret_material_included": False,
    }
