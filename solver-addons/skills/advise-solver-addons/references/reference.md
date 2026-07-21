# advise-solver-addons - reference

## How it runs — wraps the installed kernel, never re-implements it

The work is the `loomground_solver.addons.advise` public API. This skill builds the JSON
payload and reads the result; it holds no copied decision engine and fails closed if the
Solver package is absent or the payload is invalid.

## Inputs

- **policy** — add-on activation modes and thresholds (`world_model.mode`, `world_model.threshold`,
  `metacognition.mode`, `metacognition.minimum_runs`).
- **problem** — the problem context: `as_of` timestamp, `sources`, `claims_may_conflict`,
  and `available_inputs`.
- **runs** — optional array of prior run records (for metacognition eligibility). Records must
  declare `verified: true` only after the host has verified the replay/signature.

## What it returns

Per add-on:
- **score** — the computed eligibility score.
- **threshold** — the configured threshold for recommendation.
- **recommend** — whether the add-on is recommended given the score and mode.
- **reason** — human-readable explanation.
- **required_inputs** — what the add-on needs to function.
- **missing_inputs** — what is absent from the current context.
- **activation_performed** — always `false` (this skill advises, never activates).

## Guardrails

- **Provider-neutral.** Does not import, name, or select any graph, retriever, model,
  vector database, or storage provider.
- **Advice only.** Never retrieves evidence, inspects a graph, loads a provider, writes
  proposals, or activates an add-on.
- **No authorization.** A recommendation is not an authorization; the host must authorize
  and load its own configured provider separately.
- **Verification is host-asserted.** Does not infer verification from a signature; accepts
  `verified: true` only when the host has actually verified.
- **Fail closed.** Returns an error when the Solver is missing or the payload/mode is invalid.

## Pairing

This skill produces recommendations that a host or orchestrator may act on. It does not
depend on other Loomground skills but complements the analytic solver skills by advising
when their add-ons are useful.
