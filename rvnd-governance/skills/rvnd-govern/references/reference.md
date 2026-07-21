# rvnd-govern - reference

## What it drives — the RVND server, never a local engine

This skill holds no governance logic. It sequences calls to the RVND governance MCP server (the
action gate, `governance_lane_list`, `governance_map`, `officer` preview, `governance_lane_register`)
and renders their results. If the server is absent or its governance layer is off, the skill fails
closed — it does not fabricate a verdict.

## Identity first — the no-id wall

Before step 3, resolve three identities the server recognises: the **agent** (a registered agent
with a lane, not "the assistant"), the **folder scope**, and the **acting person** for any step
that needs confirmation. An unresolved principal stops the flow there. Never invent or reuse an
identity to continue. A folder with no policy is ungoverned and therefore fail-closed for
consequential acts — register or resolve it first.

## The action envelope

A proposal is an explicit object, not a sentence. Assemble it from the situation, not from
guesses:

- **agent** — the resolved agent identity.
- **folder_context** — the absolute path of the governed scope.
- **action_class** — the class of act (e.g. summarise, classify, write, send), matched to the
  lane's permitted classes.
- **grade** — the autonomy grade requested. May equal the lane's `max_grade` or be lower, never
  higher.
- **footprints** — the data footprints touched (e.g. personal-data), matched to the lane.
- **connectors** — the connectors used (e.g. local-model). A connector change is a denial unless
  re-approved.
- **policy_fingerprint** — the compiled policy the request assumes.

The server checks every constrained dimension. Missing scope values, an unapproved action or
footprint, a connector change, a policy change, or a grade increase each produce a denial.

## Tightening vs loosening

Decide the direction before you render anything:

- **Tightening** (a lower grade, fewer classes, a narrower footprint, sealing the folder) is the
  safe direction. Preview it through the officer preview so the shown effect is the server's, then
  apply. Records who tightened and why.
- **Loosening** (a higher grade, more classes, a new connector, opening a sealed folder, a more
  permissive policy) is dangerous. It **always** needs a new versioned lane, a named approver, and
  a written rationale, and it is fail-closed until it has them. Never loosen implicitly or by
  reusing a prior approval for a different scope.

## What it returns

The server's verdict (allow / hold / deny) as a discrete lamp, the rule that produced it, and —
once applied — the signed receipt. Nothing is asserted without its rule and key. A held or denied
action is rendered as held or denied, never softened.

## Guardrails

- The server decides; this skill renders. No host-side verdict, ever.
- Fail-closed on every write path: missing step, unreachable server, unresolved principal → stop.
- Requested is not granted. Status words stay "requested / pending / proposed" until the receipt.
- Attributed, not asserted — every outcome carries rule, key, and (for loosening) approver.

## Pairing

The entry point for the plugin. `rvnd-decide` owns the human confirm step in depth; `rvnd-audit`
verifies the receipts this skill produces; `rvnd-incident` handles the stop/revoke/transfer path
when something goes wrong; `rvnd-build-surface` composes the cards this cycle renders.
