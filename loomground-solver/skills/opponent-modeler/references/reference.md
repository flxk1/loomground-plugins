# opponent-modeler - reference

## How it runs — wraps the installed kernel, never re-implements it

The work is the `loomground_solver` kernel: `scenario` possible-worlds (one world per opponent
type), the `decision` methods (which option a maximin / maximax / expected-utility opponent
picks), the `world_model` add-on (their tracked state), and `narrow` / fingerprint-space
inference to pin their type from the pairs of situations already seen. This skill builds the
request and reads the result; it holds no copied engine and fails closed if the kernel is absent.

Deeper recursive belief modelling (an opponent reasoning about your reasoning) is expressed by
composing scenarios or registering a method with `register_method` — the kernel ships the
decision-theoretic and possible-worlds substrate, not a fixed recursion depth.

## Inputs

- **options** — the moves available to the opponent.
- **payoffs** — their valuation over outcomes (from the situation, not invented).
- **observations** — prior behaviour, used to infer type.
- **profile / method** — which decision rule to attribute (default: expected-utility with a
  maximin fallback for a cautious adversary).

## What it returns

The opponent's likely move with the method that produced it, the inferred type and its
confidence, the tendencies you can exploit, and — for any branch the evidence does not settle —
an `ESCALATE` rather than a guess. Signed and replayable.

## Guardrails

- **Options and payoffs are given, not fabricated.** The skill reasons; it does not invent the
  game.
- **The kernel disposes.** Every prediction carries its method and trace; nothing is asserted
  without one.
- **Escalate the undecided.** An unpinned type or branch returns `ESCALATE`.
- **Provider-neutral, local-first, no external side effects.**

## Pairing

This skill reasons under uncertainty and feeds `strategic-analysis` and `probability-tracker`.
Questions of obligation hand off to the separately licensed RVND governance package.
