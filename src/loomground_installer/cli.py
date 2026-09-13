# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Command-line entry point for safe Loomground installation planning."""

from __future__ import annotations

import argparse
import json
import sys

from .core import InstallerError, create_plan, doctor, load_profiles


def _parser() -> argparse.ArgumentParser:
    profiles = sorted(load_profiles()["profiles"])
    parser = argparse.ArgumentParser(prog="loomground")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan", help="print an installation plan without changing the system")
    plan.add_argument("--profile", choices=profiles)
    plan.add_argument("--host", action="append", default=[], choices=("auto", "claude", "codex"))
    plan.add_argument("--json", action="store_true")

    check = commands.add_parser("doctor", help="inspect installation state without changing the system")
    check.add_argument("--host", action="append", default=[], choices=("auto", "claude", "codex"))
    check.add_argument("--json", action="store_true")
    return parser


def _print_plan(args: argparse.Namespace) -> int:
    plan = create_plan(args.profile, args.host)
    if args.json:
        print(json.dumps(plan.to_dict(), indent=2))
        return 0
    print(f"Loomground installation plan: {plan.profile}")
    print(f"Hosts: {', '.join(plan.hosts)}")
    print(f"Enforcement: {plan.enforcement_mode}")
    print("Changes made: none")
    for number, operation in enumerate(plan.operations, 1):
        instruction = operation.instruction or "blocked"
        print(f"{number}. [{operation.host}] {operation.description}")
        print(f"   {instruction}")
        if operation.reason:
            print(f"   reason: {operation.reason}")
    return 0


def _print_doctor(args: argparse.Namespace) -> int:
    checks = doctor(args.host)
    if args.json:
        print(json.dumps([check.__dict__ for check in checks], indent=2))
    else:
        for check in checks:
            print(f"{check.status.upper():8} {check.name}: {check.detail}")
    return 0 if all(check.status in {"ok", "unknown"} for check in checks) else 1


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            return _print_plan(args)
        return _print_doctor(args)
    except InstallerError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
