# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Safe, host-neutral onboarding around one verified Loomground runtime."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .adapters import CONTROL_TOOLS, HOSTS, render_adapter
from .bundle import BundleError, canonical_json
from .runtime_bundle import install_runtime_bundle

CONFIG_NAMES = {
    "claude": "claude.mcp.json",
    "codex": "codex.mcp.toml",
    "cursor": "cursor.mcp.json",
    "n8n": "n8n.mcp-client.json",
    "openai": "openai.mcp-tool.json",
    "generic": "generic.mcp.json",
}

LOCAL_HOSTS = {"claude", "codex", "cursor"}
REMOTE_HOSTS = {"n8n", "openai"}


@dataclass(frozen=True)
class OnboardingReceipt:
    status: str
    runtime: dict
    output: str
    hosts: tuple[str, ...]
    makers: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _explicit_directory(path: Path, label: str) -> Path:
    if not path.is_absolute() or path == Path(path.anchor):
        raise BundleError(f"{label} must be an explicit absolute non-root path")
    if path.is_symlink() or path.exists():
        raise BundleError(f"{label} must not already exist")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise BundleError(f"{label} parent must be a real existing directory")
    return path


def _normalize_hosts(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    hosts = tuple(dict.fromkeys(value.strip().lower() for value in values if value.strip()))
    invalid = sorted(set(hosts) - set(HOSTS))
    if invalid:
        raise BundleError(f"unsupported onboarding hosts: {', '.join(invalid)}")
    if not hosts:
        raise BundleError("onboarding requires at least one host")
    return hosts


def _normalize_makers(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    makers: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            continue
        if len(value) > 100 or any(character in value for character in "\r\n\0"):
            raise BundleError("maker names must be single-line values of at most 100 characters")
        folded = value.casefold()
        if folded not in seen:
            seen.add(folded)
            makers.append(value)
    return tuple(makers)


def _config_payload(host: str, adapter: dict) -> str:
    if host == "codex":
        return adapter["content"]
    if host == "n8n":
        value = {
            "node": adapter["node"],
            "parameters": adapter["parameters"],
            "secret_binding": adapter["secret_binding"],
        }
    else:
        value = adapter["content"]
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _next_steps(hosts: tuple[str, ...], makers: tuple[str, ...]) -> str:
    instructions = {
        "claude": "Merge `hosts/claude.mcp.json` into `.mcp.json`, then install `loomground-suite@loomground` from the Loomground marketplace.",
        "codex": "Merge `hosts/codex.mcp.toml` into `$CODEX_HOME/config.toml`, then install `loomground-suite@loomground`.",
        "cursor": "Merge `hosts/cursor.mcp.json` into `.cursor/mcp.json`; keep existing MCP servers.",
        "openai": "Add `hosts/openai.mcp-tool.json` as the MCP tool and bind its bearer token from the application's secret store.",
        "n8n": "Create an MCP Client Tool from `hosts/n8n.mcp-client.json` and bind an n8n bearer credential; never copy the token into workflow JSON.",
        "generic": "Merge `hosts/generic.mcp.json` into the host's MCP configuration.",
    }
    lines = [
        "# Loomground next steps",
        "",
        "The runtime is installed. This onboarding pack has not modified any host configuration.",
        "",
    ]
    for number, host in enumerate(hosts, 1):
        lines.append(f"{number}. **{host}** — {instructions[host]}")
    lines.extend([
        "",
        "## Existing skills and agents",
        "",
    ])
    if makers:
        lines.append(f"Declared makers: {', '.join(makers)}.")
    else:
        lines.append("No external makers were declared. Add them later to the same action-intent boundary.")
    lines.extend([
        "",
        "A maker proposes a normalized action intent. Loomground compiles and checks policy, privacy, lane, drift and A2A admission before the credential-owning adapter may dispatch that exact admitted digest. Reconciliation and evidence verification follow the effect.",
        "",
        "This declaration alone does not enforce anything. Hard enforcement exists only when the maker cannot reach the target system except through the Loomground-controlled adapter. Direct credentials or alternate execution paths make the integration advisory.",
        "",
    ])
    return "\n".join(lines)


def onboard(
    bundle: Path,
    public_key: Path,
    destination: Path,
    output: Path,
    hosts: list[str] | tuple[str, ...],
    *,
    server_url: str | None = None,
    makers: list[str] | tuple[str, ...] = (),
) -> OnboardingReceipt:
    """Install a verified runtime and atomically emit non-secret host handoff files."""
    selected_hosts = _normalize_hosts(hosts)
    selected_makers = _normalize_makers(makers)
    output = _explicit_directory(output, "onboarding output")
    if set(selected_hosts) & REMOTE_HOSTS and not server_url:
        raise BundleError("OpenAI and n8n onboarding require --server-url")

    adapters: dict[str, dict] = {}
    for host in selected_hosts:
        adapters[host] = render_adapter(
            host,
            runtime_destination=destination if host in LOCAL_HOSTS or (host == "generic" and not server_url) else None,
            server_url=server_url if host in REMOTE_HOSTS or (host == "generic" and server_url) else None,
        )

    receipt = install_runtime_bundle(bundle, public_key, destination)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.loomground-onboard-stage-", dir=output.parent))
    try:
        host_dir = stage / "hosts"
        host_dir.mkdir()
        for host, adapter in adapters.items():
            (host_dir / CONFIG_NAMES[host]).write_text(_config_payload(host, adapter), encoding="utf-8")
            (host_dir / f"{host}.adapter.json").write_bytes(canonical_json(adapter) + b"\n")
        maker_records = [
            {
                "name": maker,
                "role": "maker",
                "enforcement": "mediated-only",
                "required_control_tools": list(CONTROL_TOOLS),
                "bypass_condition": "Direct target credentials or an alternate execution path exist.",
            }
            for maker in selected_makers
        ]
        manifest = {
            "schema_version": 1,
            "runtime": receipt.to_dict(),
            "hosts": [
                {
                    "host": host,
                    "config": f"hosts/{CONFIG_NAMES[host]}",
                    "adapter": f"hosts/{host}.adapter.json",
                    "destination_hint": adapters[host].get("destination_hint"),
                }
                for host in selected_hosts
            ],
            "makers": maker_records,
            "host_configuration_modified": False,
            "secret_material_included": False,
        }
        (stage / "onboarding.json").write_bytes(canonical_json(manifest) + b"\n")
        (stage / "NEXT-STEPS.md").write_text(_next_steps(selected_hosts, selected_makers), encoding="utf-8")
        os.replace(stage, output)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return OnboardingReceipt(
        "ready", receipt.to_dict(), str(output), selected_hosts, selected_makers
    )
