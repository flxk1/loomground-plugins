---
name: advise-solver-addons
description: Deterministically assess whether a Loomground Solver problem benefits from the optional world-model add-on or whether verified historical runs are ready for metacognitive analysis. Use when users ask whether to enable Solver add-ons, need an explainable add-on recommendation, want required or missing inputs identified, or need provider-neutral activation guidance. Do not use it to select a graph, retriever, model, storage provider, or authorization mechanism.
---

# Advise Solver add-ons

Produce advice, never activation. Keep every graph, retrieval system, model,
database and product adapter opaque. Use only declared request/run metadata.

## Workflow

1. Build a JSON payload with `policy`, `problem`, and/or `runs`.
2. Run `python scripts/advise.py INPUT.json`, or pipe the payload on stdin.
3. Report each score, threshold, reason, required input and missing input.
4. State explicitly that `activation_performed` is false.
5. If activation is requested, require the host to authorize and load its own
   configured provider separately. Never choose one.

## Input

```json
{
  "policy": {
    "world_model": {"mode": "recommend", "threshold": 2},
    "metacognition": {"mode": "manual", "minimum_runs": 3}
  },
  "problem": {
    "as_of": "2026-07-19T00:00:00Z",
    "sources": ["source:a", "source:b"],
    "claims_may_conflict": true,
    "available_inputs": ["context_provider", "reference_time"]
  },
  "runs": []
}
```

Allowed world-model modes are `off`, `recommend`, and `required`. Allowed
metacognition modes are `off`, `manual`, and `scheduled`.

Run records may declare `verified: true` only after the host has actually
verified the replay/signature. Do not infer verification from a signature.

## Mathematics

World-model score:

```text
W = I(time-sensitive) + I(current-state-required) + I(external-evidence)
  + I(multiple-sources) + I(possible-conflict) + I(freshness-required)
```

Recommend when the configured mode is not `off` and `W >= threshold`.

Metacognition is eligible only when the number of declared verified records is
at least `minimum_runs` and those records occupy at most one scope. `manual`
mode is eligible but never automatically recommended. `scheduled` may be
recommended. This is deterministic counting, not model judgment.

## Hard boundaries

- Do not import or name a graph, orchestrator, world-model implementation,
  vector database, model vendor, or other provider in recommendation logic.
- Do not retrieve evidence, inspect a graph, load a provider, write proposals,
  or activate an add-on.
- Do not convert a recommendation into authorization.
- Do not claim records are verified unless a host verified them first.
- Fail closed when Solver is missing or the payload/mode is invalid.

The script delegates to the installed `loomground_solver.addons.advise` public
API. It does not contain a copied decision engine.
