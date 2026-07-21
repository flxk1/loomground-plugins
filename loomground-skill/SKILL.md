---
name: loomground
description: Express an AI-governance requirement as a verified Loomground policy-graph patch. Use when the user wants to encode a governance rule (human oversight, reservation, prohibition, separation of duty / quorum, redress or contestation, delegation, disclosure obligation) as a .loom patch; validate or fix an existing patch; or judge whether a requirement is expressible in Loomground versus belonging to a host. The procedure drafts the patch, applies the litmus to classify each requirement as expressible, policy, or host, validates the result against the schemas and the reference implementation, and reports what the patch governs and what was handed off to a host. Triggers on "express this as Loomground", "write a .loom patch", "is this governable in Loomground", "validate this patch", "governance as a policy graph".
---

# Loomground skill — draft, validate, classify

Turn a natural-language AI-governance requirement into a **verified** Loomground
policy-graph patch. Loomground *declares* governance; it never computes, aggregates,
schedules, persists, or communicates. Your job is to express what is declarable and
**hand the rest to a host**, then prove the patch is well-formed.

## Step 0 — Load the language
Read `llms.txt` (the self-contained guide) and `language-card.json` from the
Loomground standard. They give the whole vocabulary: 4 nodes (`actor`, `human`,
`gate`, `master`), 3 cords (authority, pipe, egress), the token
`{id, kind, risk, party, provenance}`, 5 verdicts, and the 8 declarations.

## Step 1 — Classify each requirement (the litmus)
For every requirement in the request, decide:
- **express** — a regulation/standard *names* it as a declaration (reserve to a
  human, prohibit a practice, require a quorum, attach a disclosure obligation,
  make a decision contestable, delegate authority, mark a responsible party).
- **policy** — a deployment *chooses its values* (which kinds are reserved, what
  the auto-vs-human basis is, thresholds). Note it; do not hard-code it.
- **host** — a runtime *does* it: compute a metric, count or aggregate across
  decisions, compare to a threshold, measure elapsed time, watermark, persist,
  inspect payload, or communicate. **Not expressible — do not force it into a
  guard.** Record it as a host hand-off.

A guard may range only over `kind`, `risk`, `party`. If you need a computed value,
it is a host concern.

## Step 2 — Draft the patch (`.loom`)
Declare nodes, then wire cords. Use only declarations that survived Step 1 as
*express*. Example shape:
```
actor  bot
human  dpo  role dpo
gate   decide  risk high  grant bot
reserve automated_decision by dpo when risk >= high
redress automated_decision by appeals overturn within 30d
cord bot    -> decide
cord decide -> master
```
Keep it forward-only: one master, acyclic pipes, every gate on a path to the master.

## Step 3 — Validate (reference implementation is the checker)
Write the patch to a file and run `python3 validate.py PATCH.loom`. It uses the
Loomground reference implementation to parse and check the patch and prints either
`WELL-FORMED` with the projection, or `REJECTED (parse|apply): reason`. Fix and
re-run until well-formed. (If the reference implementation is not on `PYTHONPATH`,
validate the patch structurally against `schema/patch.schema.json`.)

## Step 4 — Report
Give the user: (a) the validated `.loom` patch; (b) **what it governs** (the
verdicts/obligations it declares); (c) the **host hand-offs** — the host/policy
requirements from Step 1 that the language deliberately does not express. Never
claim the patch satisfies a legal obligation; it expresses a measure.
