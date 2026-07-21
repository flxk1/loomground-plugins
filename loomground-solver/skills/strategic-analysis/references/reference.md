# strategic-analysis - reference

## How it runs — wraps the installed kernel

Uses the `loomground_solver` `decision` methods — **maximin, maximax, Hurwicz, minimax-regret,
satisficing, Pareto dominance, lexicographic** — plus `scenario` possible-worlds resolution and
`narrow` inference in fingerprint space. This skill assembles the options, payoffs and worlds and
reads the ranked result; it re-implements none of it and fails closed without the kernel.

The kernel provides decision-theoretic and possible-worlds reasoning, not a built-in Nash or
Level-k equilibrium solver. Where an equilibrium concept is wanted, it is added as a registered
method (`register_method`) — this skill will use it if present and otherwise reasons with the
shipped decision rules, saying which it used.

## What it returns

The recommended move and the decision rule behind it, the ranked alternatives, the threats
(worlds where the plan fails) and opportunities (worlds it exploits), and an `ESCALATE` for
branches the analysis cannot settle. Signed and replayable.

## Guardrails

- **Options and payoffs are given.** The skill reasons over the situation; it does not fabricate it.
- **Name the rule.** Every recommendation states the decision method it came from — no hidden judgement.
- **Escalate the undecided.** Genuinely open branches return `ESCALATE`, not a forced pick.
- **Provider-neutral, local-first, no side effects.**

## Pairing

The planning member of the analytic lobe. Consumes `opponent-modeler` and `probability-tracker`;
paired against the deductive governance lobe for reasoning under obligation.

