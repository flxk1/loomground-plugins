# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Command-line entry point for safe Loomground installation planning."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .adapters import HOSTS as ADAPTER_HOSTS, render_adapter
from .bundle import BundleError, install_bundle, rollback_install, verify_bundle
from .core import HOSTS, InstallerError, create_plan, doctor, load_profiles
from .runtime_bundle import (
    install_runtime_bundle,
    rollback_runtime_install,
    verify_runtime_bundle,
)


def _parser() -> argparse.ArgumentParser:
    profiles = sorted(load_profiles()["profiles"])
    parser = argparse.ArgumentParser(prog="loomground")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan", help="print an installation plan without changing the system")
    plan.add_argument("--profile", choices=profiles)
    plan.add_argument("--host", action="append", default=[], choices=("auto",) + HOSTS)
    plan.add_argument("--json", action="store_true")

    check = commands.add_parser("doctor", help="inspect installation state without changing the system")
    check.add_argument("--host", action="append", default=[], choices=("auto",) + HOSTS)
    check.add_argument("--json", action="store_true")

    bundle = commands.add_parser("bundle", help="verify or transactionally install a signed profile bundle")
    bundle_commands = bundle.add_subparsers(dest="bundle_command", required=True)
    verify = bundle_commands.add_parser("verify")
    verify.add_argument("bundle", type=Path)
    verify.add_argument("--public-key", type=Path, required=True)
    install = bundle_commands.add_parser("install")
    install.add_argument("bundle", type=Path)
    install.add_argument("--public-key", type=Path, required=True)
    install.add_argument("--destination", type=Path, required=True)
    rollback = bundle_commands.add_parser("rollback")
    rollback.add_argument("--destination", type=Path, required=True)
    rollback.add_argument("--backup", type=Path, required=True)
    rollback.add_argument("--public-key", type=Path, required=True)

    runtime = commands.add_parser("runtime", help="verify or transactionally install a signed offline runtime")
    runtime_commands = runtime.add_subparsers(dest="runtime_command", required=True)
    runtime_verify = runtime_commands.add_parser("verify")
    runtime_verify.add_argument("bundle", type=Path)
    runtime_verify.add_argument("--public-key", type=Path, required=True)
    runtime_install = runtime_commands.add_parser("install")
    runtime_install.add_argument("bundle", type=Path)
    runtime_install.add_argument("--public-key", type=Path, required=True)
    runtime_install.add_argument("--destination", type=Path, required=True)
    runtime_rollback = runtime_commands.add_parser("rollback")
    runtime_rollback.add_argument("--destination", type=Path, required=True)
    runtime_rollback.add_argument("--backup", type=Path, required=True)
    runtime_rollback.add_argument("--public-key", type=Path, required=True)

    adapter = commands.add_parser("adapter", help="render a host registration without changing host files")
    adapter.add_argument("--host", choices=ADAPTER_HOSTS, required=True)
    adapter.add_argument("--runtime-destination", type=Path)
    adapter.add_argument("--server-url")
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
        if args.command == "doctor":
            return _print_doctor(args)
        if args.command == "adapter":
            print(json.dumps(render_adapter(
                args.host,
                runtime_destination=args.runtime_destination,
                server_url=args.server_url,
            ), indent=2))
            return 0
        if args.command == "runtime":
            if args.runtime_command == "verify":
                verified = verify_runtime_bundle(args.bundle, args.public_key)
                print(json.dumps({
                    "status": "verified",
                    "runtime": verified.runtime_name,
                    "version": verified.runtime_version,
                    "key_id": verified.key_id,
                    "bundle_digest": verified.digest,
                    "packages": len(verified.packages),
                    "platforms": list(verified.platforms),
                }, indent=2))
                return 0
            if args.runtime_command == "install":
                runtime_result = install_runtime_bundle(args.bundle, args.public_key, args.destination)
            else:
                runtime_result = rollback_runtime_install(args.destination, args.backup, args.public_key)
            print(json.dumps(runtime_result.to_dict(), indent=2))
            return 0
        if args.bundle_command == "verify":
            result = verify_bundle(args.bundle, args.public_key)
            print(json.dumps({
                "status": "verified", "profile": result.profile, "target": result.target,
                "key_id": result.key_id, "bundle_digest": result.digest,
                "files": len(result.files),
            }, indent=2))
            return 0
        if args.bundle_command == "install":
            result = install_bundle(args.bundle, args.public_key, args.destination)
        else:
            result = rollback_install(args.destination, args.backup, args.public_key)
        print(json.dumps(result.to_dict(), indent=2))
        return 0
    except (InstallerError, BundleError, OSError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
