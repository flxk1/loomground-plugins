# litigation-risk-assessor - reference

## How it runs — wraps the installed kernel

Uses the `loomground_solver` `decision` methods — **expected utility** for the base recommendation,
**minimax-regret** and **maximin** for the risk-averse view — closing on the bounded
`decision_space`. Probabilities can come from `estimate-liability` / `probability-tracker`. This
skill assembles outcomes, values and probabilities and reads the ranked result; it re-implements
nothing and fails closed without the kernel.

## Inputs

- **outcomes** — win, lose, and settlement points, each with its monetary (or utility) value.
- **probabilities** — the likelihood of each, stated (or drawn from the analytic siblings).
- **costs** — legal spend and time, folded into the value of each path.

## What it returns

The recommended strategy (fight / settle / settle-at-X) with the decision rule behind it, the
expected value and the worst-case exposure, the ranked alternatives, and the sensitivity — which
probability or value, if wrong, flips the recommendation. Replayable.

## Guardrails

- **Values and probabilities are given.** The skill weighs them; it does not invent the case.
- **Name the rule, show the downside.** Expected value never hides the worst case.
- **Not legal advice.** An organisational risk assessment; the legal merits are a lawyer's call.
- **Provider-neutral, local-first, replayable.**

## Pairing

Consumes `estimate-liability` and `probability-tracker`. A dispute that turns on a governance rule
hands off to the separately licensed RVND governance package.
