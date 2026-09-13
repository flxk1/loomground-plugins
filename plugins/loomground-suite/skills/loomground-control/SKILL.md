---
name: loomground-control
description: >-
  Put another skill, agent or plugin behind Loomground policy control. Use when
  an external workflow such as Legal Ops, continuous monitoring or an agent
  team must be checked, admitted, evidenced and reconciled through Loomground.
---

# Loomground Control

Treat the external plugin as the maker and Loomground as its control plane.
Loomground does not replace the maker's domain reasoning. It governs the
maker's proposed side effect.

Start with `loomground_catalogue` and use `loomground_skill` to load the pinned
specialist skill needed for the request. Never substitute an unpinned local
copy when the MCP catalogue identifies a pinned body.

## Control boundary

Before a boundary-relevant action, form one immutable action intent containing:

- maker identity, plugin or skill version, and requested authority;
- action kind, target and SHA-256 digest of its canonical inputs;
- expected effects, reversibility and data destinations;
- policy scope and the human principal, if one exists.

The host should validate this object against
`../../schemas/action-intent.schema.json`. The same `intentId` and
`inputDigest` must survive every later stage. A changed input is a new intent,
not a continuation of an earlier admission.

## Preflight

1. Compile prose policy with `policy_compile`; use `policy_check` when explicit
   cases are available. Ingesting policy into Versum and compiling it do not
   activate it. Enforcement requires a host-authorized activation record bound
   to the compiled policy digest.
2. For external data transfer, call `privacy_scan` on the exact outbound
   content. A clean overlay is the candidate payload; "cleared" is not proof
   of zero residual personal data.
3. Evaluate the approved lane with `lane_evaluate` and the current lease and
   tripwires with `drift_breaker`. Missing lane, capability, policy receipt or
   lease is fail-closed for enforcement.
4. Call `a2a_plan`, then `a2a_admission_preview` with role-owned receipts bound
   to the action digest. Only `admitted` may be presented to an enforcement
   adapter. `ready` or a plan is never execution authority.

`hold`, `refuse`, `route-human`, `OPEN`, missing evidence and a reserved action
must not be rendered as permission. Surface the exact blocking reason and the
authority required to continue.

## Enforcement

An MCP evaluation cannot itself stop a different plugin. Real enforcement
exists only when the host gives an adapter exclusive control of the privileged
effect: API write, message send, deployment, deletion, payment or comparable
mutation. The adapter must verify a single-use, expiring decision bound to the
exact intent and policy digest immediately before the effect, perform the
effect, and return a receipt. If the maker can bypass that adapter, describe the
result as advisory.

A new policy digest must invalidate or re-evaluate affected admissions and
leases. Never apply an old admission to new policy merely because both versions
occupy the same Versum scope.

The target receipt contract is
`../../schemas/enforcement-receipt.schema.json`. The present Loomground MCP
surface produces plans and admission previews, not production authorization
tokens; do not invent a signature, receipt or enforced state.

## Postflight

Call `a2a_reconcile` with the host's actual control receipt and the postflight
plane receipts. Use `effect_reconcile` where observed external effects must be
matched to authorizations. Emit or verify evidence only through the provided
evidence tools.

Keep the state labels exact:

- `assessed`: Loomground evaluated the intent;
- `admitted`: the preview may be handed to the host;
- `enforced`: the adapter actually gated the effect and returned a valid
  receipt;
- `reconciled`: observed effects matched the authorized effects;
- `certified`: the returned result explicitly says so.

Never infer a later state from an earlier one.
