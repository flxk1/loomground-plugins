# rvnd-decide - reference

## What it drives

The RVND oversight surface. This skill reads the oversight state for an item, presents it to a
person as three discrete outcomes, and records their decision through the server so it signs into
the chain. It holds no decision logic and computes no recommendation — the person decides.

## When an item lands here

RVND oversight checks each action against the lowest autonomy limit set by the applicable rules
and against a time-based stop. An item reaches this skill when:

- it is a **reserved act** the policy holds for a person;
- it **loosens** authority (a higher grade, wider action classes, a new footprint or connector, a
  more permissive policy import);
- an autonomy ceiling or a time-based stop halted it pending review.

A task reserved for a person cannot run automatically. This skill does not have a path that lets
it run anyway.

## The three outcomes

Present exactly **approve**, **hold**, **deny** — discrete lamps, never a numeric score or a
dial. Do not pre-select one. Do not phrase the prompt to steer toward approve. Show the verdict
context and the rule from the patch preview so the person decides on the facts.

## Approver identity and rationale

- Resolve the approver to an identity the server recognises before the decision is taken. An
  unresolved person hits the no-id wall and cannot decide.
- An approval that **loosens** requires a written rationale. Enforce it as a gate: without a
  rationale, the approval does not complete. This is not a form field for its own sake — it is
  what makes the widening auditable later.
- A tightening or a routine governed action still records its actor but does not need a separate
  human approver unless policy says so.

## Recording

The decision routes through the server into the per-folder Ed25519-signed hash chain, with the
approver and rationale attached. The host does not sign; it asks the server to record, and the
server signs. Once recorded, `rvnd-audit` can verify it and the receipt card can render it.

## Guardrails

- The person decides; the skill records. No recommendation, no default, no nudge.
- Discrete outcomes only — approve / hold / deny. No dials or scores.
- Loosening is inert without a named approver and a rationale.
- Fail-closed: an unresolved approver, an unreachable server, or a missing rationale for a
  loosening all mean the decision does not complete.

## Pairing

Owns the confirm step that `rvnd-govern` routes into. Feeds `rvnd-audit`, which verifies the
signed decisions this skill produces. Escalations that turn into stops or revocations hand off to
`rvnd-incident`.
