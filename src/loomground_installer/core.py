# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Pure planning and read-only diagnostics.

This module deliberately has no subprocess or file-write primitive. A future
executor can consume ``InstallPlan`` only after its operations have separate,
host-specific transactional implementations.
"""

from __future__ import annotations

import json
import os
import shutil
import tomllib
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path
from typing import Callable, Iterable

HOSTS = ("claude", "codex")
MARKETPLACE = "flxk1/loomground-plugins"


class InstallerError(ValueError):
    """An invalid or unsupported installation request."""


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class Operation:
    host: str
    kind: str
    description: str
    instruction: str | None
    executable: bool
    reason: str | None = None


@dataclass(frozen=True)
class InstallPlan:
    schema_version: int
    profile: str
    hosts: tuple[str, ...]
    plugins: tuple[str, ...]
    enforcement_mode: str
    mutates_system: bool
    operations: tuple[Operation, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def load_profiles() -> dict:
    path = resources.files("loomground_installer").joinpath("profiles.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("default") not in data.get("profiles", {}):
        raise InstallerError("invalid bundled profile registry")
    profiles = data["profiles"]
    if any(not isinstance(names, list) or not names for names in profiles.values()):
        raise InstallerError("every profile must contain at least one plugin")
    return data


def resolve_profile(name: str | None) -> tuple[str, tuple[str, ...]]:
    data = load_profiles()
    selected = name or data["default"]
    if selected not in data["profiles"]:
        raise InstallerError(
            f"unknown profile {selected!r}; choose from {', '.join(sorted(data['profiles']))}"
        )
    return selected, tuple(data["profiles"][selected])


def detect_hosts(which: Callable[[str], str | None] = shutil.which) -> tuple[str, ...]:
    return tuple(host for host in HOSTS if which(host))


def resolve_hosts(requested: Iterable[str], which: Callable[[str], str | None] = shutil.which) -> tuple[str, ...]:
    values = tuple(dict.fromkeys(requested))
    if not values or values == ("auto",):
        detected = detect_hosts(which)
        if not detected:
            raise InstallerError("no supported host detected; pass --host claude or --host codex")
        return detected
    if "auto" in values:
        raise InstallerError("--host auto cannot be combined with explicit hosts")
    invalid = sorted(set(values) - set(HOSTS))
    if invalid:
        raise InstallerError(f"unsupported host: {', '.join(invalid)}")
    return values


def create_plan(profile: str | None, hosts: Iterable[str], which: Callable[[str], str | None] = shutil.which) -> InstallPlan:
    profile_name, plugins = resolve_profile(profile)
    selected_hosts = resolve_hosts(hosts, which)
    operations: list[Operation] = []

    if not which("loomground-mcp"):
        operations.append(Operation(
            host="shared",
            kind="runtime",
            description="Install the pinned loomground-mcp runtime in an isolated environment",
            instruction=None,
            executable=False,
            reason="no signed runtime bundle or package-index release exists yet",
        ))
    else:
        operations.append(Operation(
            host="shared",
            kind="runtime-check",
            description="Verify the existing loomground-mcp command and its 55-tool catalogue",
            instruction="loomground-mcp tools",
            executable=False,
            reason="verification execution is intentionally deferred to a future transactional executor",
        ))

    if "claude" in selected_hosts:
        operations.append(Operation(
            host="claude",
            kind="marketplace",
            description="Register the immutable Loomground marketplace",
            instruction=f"Run inside Claude Code: /plugin marketplace add {MARKETPLACE}",
            executable=False,
        ))
        operations.append(Operation(
            host="claude",
            kind="plugin",
            description=f"Install the Loomground Suite entry point for the {profile_name} profile",
            instruction="Run inside Claude Code: /plugin install loomground-suite@loomground",
            executable=False,
        ))

    if "codex" in selected_hosts:
        operations.append(Operation(
            host="codex",
            kind="plugin",
            description=f"Install the Loomground Suite entry point for the {profile_name} profile",
            instruction="codex plugin add loomground-suite@loomground",
            executable=False,
            reason="the repository marketplace must already be registered with Codex",
        ))

    return InstallPlan(
        schema_version=1,
        profile=profile_name,
        hosts=selected_hosts,
        plugins=plugins,
        enforcement_mode="advisory",
        mutates_system=False,
        operations=tuple(operations),
    )


def _codex_config_path(environment: dict[str, str] | None = None, home: Path | None = None) -> Path:
    env = os.environ if environment is None else environment
    root = Path(env["CODEX_HOME"]).expanduser() if env.get("CODEX_HOME") else (home or Path.home()) / ".codex"
    return root / "config.toml"


def _codex_mcp_check(path: Path) -> Check:
    if not path.is_file():
        return Check("codex-mcp", "missing", f"configuration not found at {path}")
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Check("codex-mcp", "error", f"cannot read configuration: {exc}")
    entry = config.get("mcp_servers", {}).get("loomground")
    if not isinstance(entry, dict):
        return Check("codex-mcp", "missing", "mcp_servers.loomground is not configured")
    if entry.get("command") != "loomground-mcp":
        return Check("codex-mcp", "mismatch", "configured command is not loomground-mcp")
    return Check("codex-mcp", "ok", "loomground MCP server is registered")


def doctor(hosts: Iterable[str], which: Callable[[str], str | None] = shutil.which,
           environment: dict[str, str] | None = None, home: Path | None = None) -> tuple[Check, ...]:
    selected_hosts = resolve_hosts(hosts, which)
    runtime = which("loomground-mcp")
    checks = [Check(
        "runtime",
        "ok" if runtime else "missing",
        runtime or "loomground-mcp is not on PATH",
    )]
    for host in selected_hosts:
        executable = which(host)
        checks.append(Check(f"host-{host}", "ok" if executable else "missing", executable or f"{host} is not on PATH"))
        if host == "codex":
            checks.append(_codex_mcp_check(_codex_config_path(environment, home)))
        else:
            checks.append(Check(
                "claude-marketplace",
                "unknown",
                "Claude marketplace state is not read without invoking the host CLI",
            ))
    return tuple(checks)
