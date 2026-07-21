#!/usr/bin/env python3
"""Lint an RVND surface card, composition manifest, or proposal envelope.

Deterministic, offline, dependency-light. Reads one JSON object from stdin (or a
file path argument; "-" also means stdin) and checks it against the plugin's
schemas/ — surface-card.schema.json for a card, composition.schema.json for a
composition, proposal.schema.json for a governance proposal envelope. Chooses the
schema by shape: a "card" key means a card, a "cards"/"skills" key means a
composition, an "intent"/"loomground"/"proposal_id" key means a proposal.

Beyond JSON-Schema shape, it enforces the invariants the schemas encode in prose
so a surface cannot be built that shows a request as a grant:
  - a composition that renders a proposal must also render patch and receipt;
  - forbids_scores and attributed must be true where the schema requires them;
  - the proposal card's status vocabulary must exclude granted/enabled/active.

Fails closed: any violation exits non-zero. If the optional jsonschema package
is present it is used for full structural validation as well; if not, the plain
checks still run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"
CARD_STATUS_FORBIDDEN = {"granted", "enabled", "active", "in-effect", "in effect"}
# The real loomground-language 0.8.0a1 constructs: node classes, cords, declarations.
# Anything not in this set is residual, never a construct.
REAL_CONSTRUCTS = {
    "actor", "human", "gate", "master",
    "authority", "pipe", "egress",
    "reservation", "quorum", "prohibition", "temporal",
    "egress-obligation", "redress", "party", "delegation", "autonomy-grade",
}


def _read_input(argv: list[str]) -> str:
    if not argv or argv[0] == "-":
        return sys.stdin.read()
    return Path(argv[0]).read_text(encoding="utf-8")


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _jsonschema_check(instance: dict, schema: dict, errors: list[str]) -> None:
    try:
        from jsonschema import Draft202012Validator  # optional
    except ImportError:
        return
    for err in sorted(Draft202012Validator(schema).iter_errors(instance),
                      key=lambda e: list(e.path)):
        errors.append(f"schema: {err.message}")


def _check_card(doc: dict, errors: list[str]) -> None:
    _jsonschema_check(doc, _load_schema("surface-card.schema.json"), errors)
    if doc.get("card") == "proposal":
        vocab = {str(w).lower() for w in doc.get("status_vocabulary", [])}
        leaked = vocab & CARD_STATUS_FORBIDDEN
        if leaked:
            errors.append(
                "proposal card status_vocabulary must not contain "
                f"{sorted(leaked)} — a request is never rendered as granted"
            )
    for flag in ("forbids_scores", "attributed"):
        if flag in doc and doc[flag] is not True:
            errors.append(f"{flag} must be true (discrete lamps, attributed-not-asserted)")


def _check_composition(doc: dict, errors: list[str]) -> None:
    _jsonschema_check(doc, _load_schema("composition.schema.json"), errors)
    cards = set(doc.get("cards", []))
    if "proposal" in cards:
        for needed in ("patch", "receipt"):
            if needed not in cards:
                errors.append(
                    f"a composition that renders 'proposal' must also render '{needed}' "
                    "so a request is never shown as an outcome"
                )
    if doc.get("fail_closed") is not True:
        errors.append("fail_closed must be true")
    if doc.get("server", "rvnd-governance") != "rvnd-governance":
        errors.append("server must be 'rvnd-governance'")


def _check_proposal(doc: dict, errors: list[str]) -> None:
    _jsonschema_check(doc, _load_schema("proposal.schema.json"), errors)
    # residual ledger must be present (may be empty) - never omitted
    if "residual" not in doc or not isinstance(doc["residual"], list):
        errors.append("proposal must carry a 'residual' ledger array (may be empty, never omitted)")
    # constructs restricted to the real vocabulary - anything else is residual
    constructs = (doc.get("loomground") or {}).get("constructs") or []
    for c in constructs:
        t = c.get("type") if isinstance(c, dict) else None
        if t not in REAL_CONSTRUCTS:
            errors.append(
                f"loomground construct {t!r} is not a real 0.8.0a1 construct - "
                "it must be residual, not approximated"
            )
    # version grounding: language version must be recorded
    versions = doc.get("versions") or {}
    if not versions.get("loomground_language"):
        errors.append("versions.loomground_language is required (version grounding)")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        doc = json.loads(_read_input(argv))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not isinstance(doc, dict):
        print("error: input must be a JSON object", file=sys.stderr)
        return 2

    errors: list[str] = []
    if "intent" in doc or "loomground" in doc or "proposal_id" in doc:
        kind = "proposal"
        _check_proposal(doc, errors)
    elif "card" in doc:
        kind = "card"
        _check_card(doc, errors)
    elif "cards" in doc or "skills" in doc:
        kind = "composition"
        _check_composition(doc, errors)
    else:
        print("error: cannot tell a proposal ('intent'/'loomground') from a card ('card') "
              "or a composition ('cards'/'skills')", file=sys.stderr)
        return 2

    if errors:
        for e in errors:
            print(f"invalid {kind}: {e}", file=sys.stderr)
        return 1
    print(json.dumps({"kind": kind, "valid": True}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
