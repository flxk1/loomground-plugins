# loomground-solver

The Solver plugin: the **deductive / rule** side of the Loomground Solver, exposed as skills over
the installed `loomground_solver` kernel. It is the skill layer for governance rule-reasoning —
the reasoning engine itself (subsumption, the PASS/VIOLATION/ESCALATE contract, the
accepted/undecided/rejected decision space, defeasibility, rule-packs, the `.lg` grammar) already
lives in the kernel; these skills drive it and never re-implement it.

This sits beside the Solver's **analytic / probabilistic** side (opponent modelling, probability
tracking, strategic analysis) — same replayable, escalate-the-undecided discipline, different job:
reasoning under *obligation* rather than under *uncertainty*.

## The four skills (the RVND → Solver pipeline)

| Skill | Invocation role | Job |
|---|---|---|
| `extract-policy-norms` | RVND | policy/regulatory text → structured deontic norms (modality, Tatbestand, Rechtsfolge, exceptions, priority, validity), grounded to spans |
| `compile-loomground-policy` | RVND | norms → a validated Loomground `.lg` policy program (`loomground-solver loomground policy.lg`) |
| `reason-governance-rules` | Solver | a case → a justified verdict (PASS / VIOLATION / ESCALATE) + decision space (accepted / undecided / rejected) + replayable proof (`loomground-solver verify`) |
| `resolve-rule-conflicts` | Solver | conflicting rules → the reinstatement-sound winner (lex superior / specialis / posterior over defeaters) |

Data flows extract → compile → reason, with resolve taking over when a verdict turns on
conflicting rules. RVND owns extract + compile (it injects norms through
`loomground_solver.ports.NormSource` / `Governance`); the Solver owns reason + resolve. All four
live in this one plugin.

## Requires

The installed `loomground_solver` package (the kernel). These skills are thin wrappers over its
public API and CLI (`loomground-solver verify` / `loomground-solver loomground`); they carry no
copied decision engine and fail closed if the kernel is absent.

## Boundaries

Deterministic floor, model on the rails, local-first. Compilation proposes a policy; a person
makes it authoritative. Verdicts are the kernel's, with proof — never asserted past what it
returns. The decision space is a governance boundary: wire `accepted`/`undecided`/`rejected` to
the actor's `autonomy-grades` level.
