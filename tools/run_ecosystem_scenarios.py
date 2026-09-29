#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Run the eight declared ecosystem scenarios through the published runtime."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import site
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import ecosystem_certify

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class ScenarioFailure(AssertionError):
    pass


class Scenario:
    def __init__(self, identifier: str):
        self.identifier = identifier
        self.steps: list[dict[str, Any]] = []
        self.assertions: list[str] = []
        self.contract: dict[str, Any] = {}
        self.participant_revisions: dict[str, str] = {}
        self.runtime_lock_sha256 = ""

    def record(self, component: str, inputs: object, output: object) -> None:
        self.steps.append({
            "component": component,
            "input_sha256": ecosystem_certify.digest(inputs),
            "output": output,
        })

    def require(self, label: str, condition: bool) -> None:
        if not condition:
            raise ScenarioFailure(f"{self.identifier}: {label}")
        self.assertions.append(label)

    def emit(self, output: Path) -> dict:
        trace = {
            "schema_version": 1,
            "kind": "loomground-ecosystem-scenario-trace",
            "id": self.identifier,
            "contract": self.contract,
            "participant_revisions": self.participant_revisions,
            "runtime_lock_sha256": self.runtime_lock_sha256,
            "steps": self.steps,
            "assertions": sorted(set(self.assertions)),
        }
        trace_bytes = ecosystem_certify.canonical_json(trace) + b"\n"
        trace_dir = output / "traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        (trace_dir / f"{self.identifier}.json").write_bytes(trace_bytes)
        result = {
            "schema_version": 1,
            "kind": "scenario",
            "id": self.identifier,
            "status": "passed",
            "assertions": sorted(set(self.assertions)),
            "trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
        }
        (output / f"scenario-{self.identifier}.json").write_bytes(
            ecosystem_certify.canonical_json(result) + b"\n"
        )
        return result


class Runtime:
    def __init__(self, client):
        self.client = client

    async def call(
        self,
        scenario: Scenario,
        name: str,
        arguments: dict[str, Any],
        project: Callable[[Any], Any] = lambda value: value,
    ) -> Any:
        response = await self.client.call_tool(name, arguments)
        envelope = response.structured_content
        if not isinstance(envelope, dict) or not envelope.get("ok"):
            raise ScenarioFailure(f"{scenario.identifier}: {name} failed: {envelope}")
        value = envelope["result"]
        scenario.record(name, arguments, project(value))
        return value


def verify_runtime_bundle(runtime_destination: Path, runtime_sources_path: Path) -> str:
    lock_path = runtime_destination / "bundle" / "runtime-lock.json"
    lock_bytes = lock_path.read_bytes()
    lock = json.loads(lock_bytes)
    sources = ecosystem_certify.load_json(runtime_sources_path)
    expected = {item["name"]: item["commit"] for item in sources["packages"]}
    actual = {
        item["name"]: item["source"]["commit"]
        for item in lock.get("packages", [])
        if item.get("source", {}).get("source") == "git"
    }
    if actual != expected:
        raise ScenarioFailure("installed runtime lock differs from the 32 declared runtime pins")
    return hashlib.sha256(lock_bytes).hexdigest()


def git_commit(path: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


async def cross_host_runtime_parity(runtime: Runtime, runtime_destination: Path) -> Scenario:
    from loomground_installer.adapters import HOSTS, render_adapter

    scenario = Scenario("cross-host-runtime-parity")
    adapters = {}
    for host in HOSTS:
        kwargs = (
            {"server_url": "https://loomground.example/mcp"}
            if host in {"openai", "n8n"}
            else {"runtime_destination": runtime_destination}
        )
        adapters[host] = render_adapter(host, **kwargs)
    scenario.record("loomground-installer.adapters", {"hosts": list(HOSTS)}, {
        host: {
            "host": adapter["host"],
            "transport": adapter["transport"],
            "secret_material_included": adapter["secret_material_included"],
        }
        for host, adapter in adapters.items()
    })
    plan = await runtime.call(scenario, "a2a_plan", {
        "context": {"maker_id": "maker-1"},
        "target_kind": "edit",
        "governance": {"actions": [{"kind": "edit"}]},
        "planes": [],
    }, lambda value: {
        "coverage": len(value["plan"]["repository_coverage"]),
        "missing_required": value["plan"]["missing_required"],
        "ready": value["plan"]["ready"],
        "dispatch_performed": value["dispatch_performed"],
    })
    scenario.require("all-six-host-adapters-render", set(adapters) == set(HOSTS))
    scenario.require("host-adapters-contain-no-secret-material", all(not item["secret_material_included"] for item in adapters.values()))
    scenario.require("family-plan-covers-41-repositories", len(plan["plan"]["repository_coverage"]) == 41)
    scenario.require("distribution-never-dispatches", plan["dispatch_performed"] is False)
    return scenario


async def conflicting_jurisdiction(runtime: Runtime) -> Scenario:
    from loomground_legal import Relation, applicable_law

    scenario = Scenario("conflicting-jurisdiction-escalates")
    law = applicable_law("DE")
    outranks = [r for r in law.relations if r.relation is Relation.OUTRANKS]
    scenario.record("loomground-legal.applicable_law", {"jurisdiction": "DE"}, {
        "systems": list(law.systems),
        "primacy": [{"subject": r.subject, "object": r.object, "note": r.note} for r in outranks],
    })
    grounded = await runtime.call(scenario, "a2a_ground", {
        "context": {
            "maker_id": "maker-1",
            "autonomy": {
                "requested": "L3",
                "delegated": "L3",
                "factors": [{"name": "jurisdiction-conflict", "ceiling": "L0", "why": "EU/DE primacy requires review"}],
            },
        },
        "planes": ["escalation"],
    }, lambda value: {"recommended_action": value["recommended_action"], "grounding": value["grounding"]["verdict"]})
    reserved = await runtime.call(scenario, "a2a_plan", {
        "context": {"maker_id": "maker-1"},
        "target_kind": "transfer",
        "governance": {"actions": [{"kind": "transfer"}], "reserved": [{"kind": "transfer", "by": "human-owner"}]},
        "planes": [],
    }, lambda value: {"ready": value["plan"]["ready"], "disposition": value["plan"]["disposition"], "dispatch_performed": value["dispatch_performed"]})
    scenario.require("de-jurisdiction-closes-over-eu", list(law.systems) == ["DE", "EU"])
    scenario.require("primacy-conflict-is-explicit", bool(outranks) and "escalates" in outranks[0].note)
    scenario.require("conflict-routes-to-human", grounded["recommended_action"] == "route-human")
    scenario.require("reserved-action-is-not-dispatched", not reserved["plan"]["ready"] and reserved["dispatch_performed"] is False)
    return scenario


def _receipts(owners: dict[str, str], names: tuple[str, ...], action_digest: str) -> list[dict[str, Any]]:
    return [{
        "role": owners[name],
        "capability": f"tool:{name}",
        "status": "NOT_APPLICABLE",
        "action_digest": action_digest,
        "input_digest": ecosystem_certify.digest({"tool": name, "action": action_digest}),
        "reason": "scenario action has no input for this capability",
    } for name in names]


async def maker_action_admitted_once(runtime: Runtime) -> Scenario:
    import a2a_compliance as a2a
    from a2a_compliance.lifecycle import TOOL_OWNERS

    scenario = Scenario("maker-action-admitted-once")
    base = {
        "context": {"maker_id": "maker-1", "proposed_action": {"bearer": "maker-1", "action": "write report"}},
        "target_kind": "write",
        "governance": {"actions": [{"kind": "write"}], "obligations": ["record-effects"]},
        "planes": [],
    }
    plan = await runtime.call(scenario, "a2a_plan", base, lambda value: {"action_digest": value["plan"]["action_digest"], "ready": value["plan"]["ready"]})
    action_digest = plan["plan"]["action_digest"]
    preflight = _receipts(TOOL_OWNERS, a2a.PREFLIGHT_TOOLS, action_digest)
    preview = await runtime.call(scenario, "a2a_admission_preview", {**base, "receipts": preflight}, lambda value: {"state": value["preview"]["state"], "admitted": value["preview"]["admitted"], "dispatch_performed": value["dispatch_performed"]})
    once = await runtime.call(scenario, "effect_reconcile", {
        "auths": [{"id": "auth-1", "action": "fs.write", "subject": "/out/report", "at": "2026-09-13T10:00:00Z"}],
        "effects": [{"id": "effect-1", "action": "fs.write", "subject": "/out/report", "at": "2026-09-13T10:00:01Z", "authorisation_id": "auth-1"}],
        "since": "2026-09-13T00:00:00Z", "until": "2026-09-14T00:00:00Z",
    }, lambda value: {"status": value["status"], "matched": len(value["matched"]), "duplicated": len(value["duplicated"])})
    twice = await runtime.call(scenario, "effect_reconcile", {
        "auths": [{"id": "auth-1", "action": "fs.write", "subject": "/out/report", "at": "2026-09-13T10:00:00Z"}],
        "effects": [
            {"id": "effect-1", "action": "fs.write", "subject": "/out/report", "at": "2026-09-13T10:00:01Z", "authorisation_id": "auth-1"},
            {"id": "effect-2", "action": "fs.write", "subject": "/out/report", "at": "2026-09-13T10:00:02Z", "authorisation_id": "auth-1"},
        ],
        "since": "2026-09-13T00:00:00Z", "until": "2026-09-14T00:00:00Z",
    }, lambda value: {"status": value["status"], "duplicated": len(value["duplicated"])})
    scenario.require("complete-preflight-admits-exact-digest", preview["preview"]["admitted"] is True)
    scenario.require("admission-preview-never-dispatches", preview["dispatch_performed"] is False)
    scenario.require("single-effect-reconciles", once["status"] != "diverged" and len(once["duplicated"]) == 0)
    scenario.require("duplicate-effect-is-detected", twice["status"] == "diverged" and bool(twice["duplicated"]))
    return scenario


async def pii_egress_denied(runtime: Runtime, temp: Path) -> Scenario:
    scenario = Scenario("pii-egress-denied")
    privacy = await runtime.call(scenario, "privacy_scan", {
        "text": "Contact Ada at ada@example.com.",
        "mode": "regex_only",
        "audit_log_path": str(temp / "privacy.jsonl"),
    }, lambda value: {"pii_detected": value["documents"][0]["pii_detected"], "overlay": value["documents"][0]["overlay"]})
    locked = await runtime.call(scenario, "lock_text", {"text": "Send ada@example.com to the external model."}, lambda value: {"action": value["action"], "verdict": value["verdict"]})
    lane = await runtime.call(scenario, "lane_evaluate", {
        "lane": None,
        "request": {"agent": "maker-1", "action_class": "publish", "autonomy_grade": "L1", "footprint": ["personal-data"]},
    }, lambda value: value)
    scenario.require("privacy-plane-detects-pii", privacy["documents"][0]["pii_detected"] is True)
    scenario.require("privacy-overlay-removes-address", "ada@example.com" not in privacy["documents"][0]["overlay"])
    scenario.require("lock-refuses-raw-egress", locked["action"] == "refuse")
    scenario.require("unapproved-lane-denies-egress", lane["allowed"] is False)
    return scenario


async def policy_change_invalidates_admission(runtime: Runtime) -> Scenario:
    scenario = Scenario("policy-change-invalidates-admission")
    compiled = await runtime.call(scenario, "policy_compile", {"policy": "The maker may publish reports."}, lambda value: {"norms": value["draft"]["norms"], "mode": value["grounding_seam"]["mode"]})
    freshness = await runtime.call(scenario, "norm_freshness", {
        "pins": [{"rule_id": "publish", "source": {"uri": "policy://publication", "version": "v1"}}],
        "observed": {"policy://publication": {"current_version": "v2", "change_kind": "amendment"}},
    }, lambda value: {"freshness": value["verdicts"][0]["freshness"]})
    preview = await runtime.call(scenario, "a2a_admission_preview", {
        "context": {"maker_id": "maker-1", "proposed_action": {"bearer": "maker-1", "action": "publish reports"}, "policy": compiled["grounding_seam"]},
        "target_kind": "publish",
        "governance": {"actions": [{"kind": "publish"}]},
        "planes": [],
        "receipts": [],
    }, lambda value: {"state": value["preview"]["state"], "admitted": value["preview"]["admitted"], "dispatch_performed": value["dispatch_performed"]})
    scenario.require("amended-source-is-not-fresh", freshness["verdicts"][0]["freshness"] != "fresh")
    scenario.require("stale-policy-has-no-admission", preview["preview"]["admitted"] is False)
    scenario.require("stale-policy-has-no-dispatch", preview["dispatch_performed"] is False)
    return scenario


async def tripwire_quarantines_maker(runtime: Runtime) -> Scenario:
    scenario = Scenario("tripwire-quarantines-maker")
    breaker = await runtime.call(scenario, "drift_breaker", {
        "lease": {"agent": "maker-1", "granted_grade": "L3", "expires_at": 1000.0},
        "metrics": {"drift_structural": True},
        "now": 990.0,
    }, lambda value: {"state": value["state"], "effective_grade": value["effective_grade"], "verdict": value["verdict"]})
    ground = await runtime.call(scenario, "a2a_ground", {
        "context": {"maker_id": "maker-1", "proxies": [{"metric": "tickets_closed", "stands_for": "problems_solved", "metric_movement": "improved", "value_movement": "worsened"}]},
        "planes": ["proxy"],
    }, lambda value: {"recommended_action": value["recommended_action"], "grounding": value["grounding"]["verdict"]})
    scenario.require("drift-tripwire-quarantines", breaker["state"] == "QUARANTINED")
    scenario.require("quarantine-removes-autonomy", breaker["effective_grade"] == "L0")
    scenario.require("gamed-proxy-holds-action", ground["recommended_action"] == "hold")
    return scenario


async def unpermitted_effect_reconciled(runtime: Runtime) -> Scenario:
    scenario = Scenario("unpermitted-effect-reconciled")
    reconciled = await runtime.call(scenario, "effect_reconcile", {
        "auths": [{"id": "auth-1", "action": "fs.write", "subject": "/out/report", "at": "2026-09-13T10:00:00Z"}],
        "effects": [{"id": "effect-x", "action": "fs.write", "subject": "/out/other", "at": "2026-09-13T10:00:01Z"}],
        "since": "2026-09-13T00:00:00Z", "until": "2026-09-14T00:00:00Z",
    }, lambda value: {"status": value["status"], "unpermitted": [item["id"] for item in value["observed_not_authorised"]]})
    posture = await runtime.call(scenario, "enforcement_compare", {
        "a": {"engine": "gateway", "controls": [{"name": "deny-egress", "enabled": True}], "effective_from": "2026-09-13T00:00:00Z"},
        "b": {"engine": "gateway", "controls": [{"name": "deny-egress", "enabled": False}], "effective_from": "2026-09-13T10:00:00Z"},
    }, lambda value: value)
    scenario.require("unpermitted-effect-diverges", reconciled["status"] == "diverged")
    scenario.require("unpermitted-effect-is-identified", [item["id"] for item in reconciled["observed_not_authorised"]] == ["effect-x"])
    scenario.require("weakened-posture-is-visible", posture["change"] == "weakened")
    return scenario


def erasure_blocks_reingestion(temp: Path) -> Scenario:
    temp.mkdir(parents=True, exist_ok=False)
    os.environ["WORKSPACE_KEY_DIR"] = str(temp / "keys")
    os.environ["WORKSPACES_ALLOW_UNREGISTERED"] = "1"
    from loomground_audit_chain import signing
    from loomground_audit_chain.mutation_log import LogEvent, MutationLog
    from loomground_erasure import erasure, forgotten_subjects

    scenario = Scenario("erasure-blocks-reingestion")
    signing.ensure_keypair()
    signing.ensure_controller_keypair()
    workspace, log_root = temp / "workspace", temp / "logs"
    workspace.mkdir()
    log_root.mkdir()
    pair = {
        "id": "sha256:scenario-pair",
        "problem": {"id": "sha256:problem", "summary": "Jane Doe account", "type": "case", "facets": {}},
        "solution": {"id": "sha256:scenario-pair", "problem_id": "sha256:problem", "body": "Jane Doe requested erasure", "body_format": "prose", "authority_tier": 5, "confidence": 1.0, "cited_sources": [], "extractor_chain": ["scenario"]},
    }
    log = MutationLog(workspace, log_root=log_root)
    log.append(LogEvent(event="ingest", folder_path=str(workspace), pair_id=pair["id"], lifecycle_state="live", channel="document", actor="scenario", extra={"pair": pair, "distribution_scope": "private"}))
    report = erasure.execute(str(workspace), "Jane Doe", legal_basis="art_17_1_a", requester_ref="scenario", reason="data subject request", log_root=log_root)
    hits = forgotten_subjects.check_text(workspace, "Jane Doe")
    verification = MutationLog(workspace, log_root=log_root).verify_chain()
    scenario.record("loomground-erasure.execute", {"subject": "sha256:redacted", "legal_basis": "art_17_1_a"}, {"purged_event_count": report.purged_event_count, "controller_countersigned": report.controller_countersigned, "guard_matches": len(hits), "chain_ok": verification.ok})
    scenario.require("erasure-purges-matching-event", report.purged_event_count >= 1)
    scenario.require("erasure-is-controller-countersigned", report.controller_countersigned is True)
    scenario.require("forgotten-subject-guard-blocks-reingestion", bool(hits))
    scenario.require("post-erasure-audit-chain-verifies", verification.ok is True)
    return scenario


async def run(args) -> list[Scenario]:
    runtime_lock_sha256 = verify_runtime_bundle(args.runtime_destination, args.runtime_sources)
    site.addsitedir(str(args.runtime_lib))
    sys.path.insert(0, str(args.legal_src))
    os.environ["BRAIN_PRIVACY_AUDIT_LOG"] = str(args.scratch / "privacy-gate.jsonl")
    from mcp import Client
    from loomground_mcp import build_server

    temp = args.scratch
    temp.mkdir(parents=True, exist_ok=False)
    scenarios: list[Scenario] = []
    async with Client(build_server()) as client:
        runtime = Runtime(client)
        scenarios.extend([
            await conflicting_jurisdiction(runtime),
            await cross_host_runtime_parity(runtime, args.runtime_destination),
            erasure_blocks_reingestion(temp / "erasure"),
            await maker_action_admitted_once(runtime),
            await pii_egress_denied(runtime, temp),
            await policy_change_invalidates_admission(runtime),
            await tripwire_quarantines_maker(runtime),
            await unpermitted_effect_reconciled(runtime),
        ])
    for scenario in scenarios:
        scenario.runtime_lock_sha256 = runtime_lock_sha256
    return scenarios


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-lib", type=Path, required=True)
    parser.add_argument("--runtime-destination", type=Path, required=True)
    parser.add_argument("--legal-src", type=Path, required=True)
    parser.add_argument("--runtime-sources", type=Path, default=ROOT / "runtime/runtime-sources.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--self-commit")
    args = parser.parse_args()
    try:
        if args.output.exists() and any(args.output.iterdir()):
            raise ScenarioFailure("scenario output directory must be absent or empty")
        if args.scratch.exists():
            raise ScenarioFailure("scenario scratch directory must be absent")
        args.output.mkdir(parents=True, exist_ok=True)
        manifest = ecosystem_certify.validate_manifest(
            ecosystem_certify.load_json(ecosystem_certify.DEFAULT_MANIFEST),
            ecosystem_certify.load_json(args.runtime_sources),
        )
        self_commit = args.self_commit or ecosystem_certify.current_commit()
        revisions = ecosystem_certify.expected_revisions(manifest, self_commit)
        if git_commit(args.legal_src) != revisions["loomground-legal"]:
            raise ScenarioFailure("loomground-legal checkout differs from its manifest revision")
        scenarios = asyncio.run(run(args))
        contracts = {item["id"]: item for item in manifest["scenarios"]}
        expected = sorted(contracts)
        actual = sorted(scenario.identifier for scenario in scenarios)
        if actual != expected:
            raise ScenarioFailure(f"scenario implementation mismatch: {actual} != {expected}")
        for scenario in sorted(scenarios, key=lambda item: item.identifier):
            contract = contracts[scenario.identifier]
            scenario.contract = {
                "outcome": contract["outcome"],
                "invariant": contract["invariant"],
                "participants": contract["participants"],
            }
            scenario.participant_revisions = {
                name: revisions[name] for name in contract["participants"]
            }
            scenario.emit(args.output)
        print(f"ECOSYSTEM SCENARIOS PASS: {len(scenarios)}/8")
        return 0
    except (OSError, ValueError, ScenarioFailure) as exc:
        print(f"ECOSYSTEM SCENARIOS FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
