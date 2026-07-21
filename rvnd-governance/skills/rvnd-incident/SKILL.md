---
name: rvnd-incident
description: Respond to a governance incident in RVND - hold or freeze an agent, revoke a grant with a signed tombstone, seal a folder to air-gap, or transfer custody, each recorded to the signed chain. Drives RVND; the safe direction (tightening) is immediate, loosening back needs approval; fail-closed. Triggers - "freeze this agent", "revoke that grant", "seal this folder", "something is wrong stop it", "transfer custody", "air-gap this now".
---

# rvnd-incident

The response path for when something is wrong. Freeze an agent, revoke a grant, seal a folder off
from the cloud, or hand custody to someone else — fast, in the safe direction, and on the record.

Tightening is the safe direction and can be immediate. Loosening back — lifting a freeze, restoring
a grant, opening a sealed folder — is a normal loosening: it needs a named approver and a rationale.
Incidents do not get a shortcut around that.

**Runtime containment is not a Loomground change.** A hold, a suspend, a seal, a custody transfer
are RVND *runtime* actions — outside Loomground syntax. Do not present them as policy declarations.
Only when the incident is an actual policy change — removing an authority cord, adding a
`prohibition`, lowering a `grade` — does it become a Loomground proposal that flows through the
normal propose → validate → confirm → apply cycle.

## What it does

- **Hold / freeze** — stop an agent or an action now. A hold is immediate; it is the safe
  direction and needs no loosening approval to apply.
- **Revoke** — withdraw a grant. Erasure is a **signed tombstone**, not a silent delete: it purges
  this folder's record and blocks re-ingestion, and it cannot recall copies that already left the
  boundary. Say so when you render it.
- **Seal / air-gap** — mark a folder local-only so its work is kept from a cloud model; the
  governance paths exclude cloud endpoints and build no network request. This tightens — apply it.
- **Transfer** — hand custody of a governed scope to another principal, recorded and signed;
  cross-machine continue is same-key only.

Every incident action routes through the server into the per-folder Ed25519-signed chain.

## The rules

- Tightening now, loosening later with approval. Freezing is immediate; unfreezing is a loosening
  and needs a named approver and rationale.
- Revocation is a signed tombstone with honest limits — it cannot recall what already left.
- Resolve the principal and the scope before acting — no-id wall, even in an incident.

## More

- `references/reference.md` - each action, its direction, and what it can and cannot undo.
- `../../references/protocol.md` - the shared protocol, Sign routing, tightening vs loosening.
- `../../references/vocabulary.md` - which incident actions are runtime vs a real construct.
- `manifest.yaml` - runtime actions (outside Loomground) vs the constructs it may propose.
- `references/eval.json` - what it drives, guarantees, and review status.
