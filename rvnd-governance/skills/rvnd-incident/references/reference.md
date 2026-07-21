# rvnd-incident - reference

## What it drives

The RVND control surfaces for stopping and re-scoping: oversight holds, lane revocation and
supersession, air-gap sealing, and custody transfer via sessions. This skill sequences those
server operations and records the outcome; it holds no enforcement logic of its own and fabricates
no authority to act.

## The direction rule governs everything here

An incident is urgent, but urgency does not reverse the safety gradient:

- **Tightening is the safe direction and can be immediate.** Freezing an agent, holding an action,
  revoking a grant, sealing a folder — all narrow authority, so they apply now and record who did
  it and why.
- **Loosening back is still a loosening.** Lifting a freeze, restoring a revoked grant, opening a
  sealed folder, widening a transferred scope — each needs a new versioned lane, a named approver,
  and a rationale, and is fail-closed until it has them. An incident is not a licence to loosen
  without approval.

## The four actions

**Hold / freeze.** Stop an agent or a specific action immediately. This is the safe direction, so
it applies without a loosening approval. Route it through the oversight stop; it records to the
chain. Reserved acts and time-based stops use the same mechanism.

**Revoke.** Withdraw a grant, or erase a record. Erasure is a **signed tombstone**: it purges this
folder's record and blocks re-ingestion. It is not a silent delete, and it **cannot recall copies
that already left the boundary** — render that limit every time, so no one over-relies on a
revoke. To narrow an agent going forward, supersede its lane with a narrower version.

**Seal / air-gap.** Mark a folder local-only. Its governance paths then exclude cloud endpoints
and build no network request; its work is kept from a cloud model. The in-process check is the
default; an OS-level egress lock is the stronger tier that binds every process on the host. Sealing
tightens, so apply it; note which tier is in force.

**Transfer.** Hand custody of a governed scope to another principal. RVND carries this through
environment-level sessions (`.rvnd` bundles) and custody adapters; the handoff is recorded and
signed. Cross-machine continue is **same-key only** — state that constraint rather than implying a
free handoff.

## Identity, even in an incident

Resolve the principal and the folder scope before acting. The no-id wall does not lift under
pressure: an unresolved target means the action stops, not that you pick a plausible one to move
faster.

## Guardrails

- Tightening immediate; loosening back needs a named approver and rationale.
- Revocation is a signed tombstone with honest limits — never rendered as a total recall.
- Air-gap sealing builds no network request; do not route a sealed folder's work to a cloud model.
- Transfer is same-key across machines; recorded and signed either way.
- Fail-closed throughout: unreachable server or unresolved principal → the action does not happen.

## Pairing

Handles what `rvnd-audit` surfaces when a chain or an action looks wrong, and reverses or contains
what `rvnd-govern` and `rvnd-decide` put in place. Restoring normal operation afterwards routes
back through `rvnd-govern` as an ordinary approved change.
