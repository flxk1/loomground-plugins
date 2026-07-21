# resolve-rule-conflicts - reference

## How it runs — wraps the real kernel, never re-implements it

The kernel already carries scenario / possible-worlds resolution with grounded defeasibility and
rule-packs. This skill builds the conflicting-rule scenario and runs it through the same entry
points as `reason-governance-rules`:

```
loomground-solver verify <request.json>
loomground-solver loomground <policy.lg> --transport <transport.json>
```

reading the resolution from the result. The defeat semantics live in the package.

## What it does

1. **Identify the clash.** From a verdict that turned `undecided` or flagged competing rules,
   isolate the rules in conflict and the case facts that fire them.
2. **Apply priority as defeaters.** Map the legal priority principles onto the kernel's defeater
   topology: **lex superior** (hierarchy), **lex specialis** (specificity), **lex posterior**
   (recency). Priority markers come from the norms (`extract-policy-norms`), not from guesswork.
3. **Resolve soundly.** Run the scenario; take the reinstatement-sound extension — the set of
   rules that survives after defeaters and reinstatements settle. Report which rule prevails and
   the chain that defeated the others.
4. **Escalate real undecidability.** If no priority principle settles it — a genuine antinomy —
   return `ESCALATE` with the competing extensions, rather than forcing a winner.

## Guardrails

- **Sound, not convenient.** The winner is the reinstatement-sound extension, not the rule the
  model prefers.
- **Priority from the norms.** Superior / specialis / posterior come from the norm records, not
  invented ordering.
- **Escalate genuine antinomies.** No forced tie-break; a real conflict returns `ESCALATE`.
- **Fail closed.** Missing kernel or ambiguous priority inputs → stop and report.

## Relationship

- **reason-governance-rules** — hands off here when a verdict turns on conflicting rules.
- **extract-policy-norms** — supplies the priority markers this skill resolves by.
- **loomground_solver** scenario / rule-pack layer — the real defeasibility engine wrapped here.

