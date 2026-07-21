# estimate-liability - reference

## How it runs — wraps the installed kernel

Uses the `loomground_solver` **Bayesian-update** inference method for the conditional probability
and **expected-utility** for the exposure weighting, closing on the bounded `decision_space`
(accepted / undecided / rejected) where a threshold is set. This skill supplies the factors and
weights and reads the result; no copied maths, fails closed without the kernel.

## Inputs

- **factors** — the evidence elements and, for each, its bearing on the outcome (likelihood).
- **prior / base rate** — from precedent or context, stated explicitly.
- **threshold** (optional) — the level above which action is warranted, for the decision space.

## What it returns

A calibrated probability **range** (not a lone point), the factor-by-factor update chain, the
assumptions it is most sensitive to, and — if a threshold was given — where it lands in the
decision space. Replayable.

## Guardrails

- **A range, with assumptions.** Never a false point estimate; always the sensitivity.
- **Inputs are stated.** Base rates and factor weights are explicit, never invented silently.
- **Not legal advice.** An organisational estimate; a qualified lawyer owns the legal call.
- **Provider-neutral, local-first, replayable.**

## Pairing

Consumes `probability-tracker`. Its probabilistic estimate can feed the separately licensed RVND
governance package when a rule's triggering conditions turn on a likelihood.
