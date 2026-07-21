---
name: rvnd-decide
description: Run the human oversight sign-off in RVND - put an item to a person as approve/hold/deny, capture the named approver and rationale a loosening needs, and record the decision to the signed chain. Drives RVND oversight; renders discrete lamps, no dials or scores; fail-closed. Triggers - "who signs off on this", "put this to oversight", "approve or hold this", "escalate for human decision", "does this need approval".
---

# rvnd-decide

The confirm step, in depth. When an action needs a person — because it loosens authority, raises a
grade, imports policy, or is a reserved act — this skill puts it to them cleanly and records what
they decide, so the approval is real, attributed, and signed.

The person decides; you record. You do not pre-select an outcome, nudge toward approve, or treat
silence as a yes.

## What it does

1. **Query** the oversight state: is this item reserved for a person? What is the lowest autonomy
   limit the applicable rules set? Is there a time-based stop?
2. **Present** the item as three discrete outcomes — **approve / hold / deny**. No slider, no
   confidence score.
3. **Resolve** the approver's identity. An unresolved person cannot decide — no-id wall.
4. **Require** a rationale for any approval that loosens. The approval is inert without it.
5. **Record** the decision through the server; it folds into the per-folder Ed25519-signed chain
   with the approver attached.

## The rules

- A task reserved for a person cannot run automatically. Surface it; do not route around it.
- A loosening (higher grade, wider scope, new connector, more permissive policy) needs a **named
  approver and a written rationale**. An agent cannot self-sign a loosening.
- Render the outcome as the person chose it. A hold is a hold. A deny is a deny. Neither is
  paraphrased into something more permissive.

## More

- `references/reference.md` - the oversight surface, reserved acts, and rationale enforcement.
- `../../references/protocol.md` - the shared protocol, Sign routing, tightening vs loosening.
- `references/eval.json` - what it drives, guarantees, and review status.
