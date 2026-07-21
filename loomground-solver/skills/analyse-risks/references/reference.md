# analyse-risks - reference

## How it runs — wraps the installed kernel

Uses the `loomground_solver` `decision` methods (**expected utility** for impact×likelihood,
**lexicographic / Pareto** ordering for the ranking) and the **Bayesian-update** method where a
likelihood must be estimated from evidence. Deterministic where the inputs are given. This skill
supplies the register and reads the ranked result; it re-implements no scoring and fails closed
without the kernel.

## Inputs

- **risks** — each with a described impact and a likelihood (given, or estimated from evidence).
- **scale / scheme** — the impact and likelihood scale and how they combine (stated; a documented
  default if unspecified).
- **appetite** (optional) — the threshold above which a risk must be mitigated, for the decision space.

## What it returns

A scored risk register, a heat-map ranking (impact × likelihood), prioritised mitigations, and —
against a stated appetite — which risks breach it. The scoring scheme is shown with the result.
Replayable.

## Guardrails

- **Scheme is visible.** The scale and combination rule are stated with the scores, never hidden.
- **Inputs are given.** Impacts and likelihoods are explicit; estimated ones are marked.
- **No invented risks.** The skill scores the register; it does not manufacture entries.
- **Provider-neutral, local-first, replayable.**

## Pairing

Consumes `probability-tracker` for evidence-based likelihoods. A risk that is really a rule
violation hands off to the separately licensed RVND governance package.
