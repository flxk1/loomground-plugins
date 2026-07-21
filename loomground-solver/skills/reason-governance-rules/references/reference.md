# reason-governance-rules - reference

## How it runs — wraps the real kernel, never re-implements it

```
loomground-solver verify <request.json> [-o result.json]
loomground-solver loomground <policy.lg> --transport <transport.json> [-o result.json]
```

The installed `loomground_solver` runs the subsumption and path composition and returns the
contract. This skill builds the request, invokes the kernel, and reads the result; it holds no
copied decision engine.

## What it returns

- **Justified-answer contract** — `PASS`, `VIOLATION`, or `ESCALATE`, with the fired rules and
  the exceptions considered as the proof.
- **Decision space** — `accepted` / `undecided` / `rejected`. This is the governance boundary,
  not a suggestion: an automatic actor may act on `accepted`, is confined to `undecided`
  (escalate to a human), and **cannot touch `rejected`**. Wire this to the `autonomy-grades`
  level for the actor.
- **Replayable provenance** — a signed record so the same case re-runs to the same verdict.
- **Negative space** — unfired defeaters, untriggered exceptions, and gaps, surfaced so a silent
  non-match is visible rather than assumed compliant.

## Guardrails

- **The kernel disposes.** A model may propose a reading; the verdict is the kernel's, with its
  proof. Never assert a verdict the kernel did not return.
- **Escalate, never guess.** Undecided coordinates return `ESCALATE` / `undecided`; they are not
  smoothed into a PASS.
- **Respect the decision space.** Never let an automatic actor act outside `accepted`.
- **Fail closed.** Missing kernel, invalid policy, or malformed case → stop and report.

## Relationship

- **compile-loomground-policy** — supplies the validated `.lg` policy this skill runs against.
- **resolve-rule-conflicts** — takes over when the verdict turns on conflicting rules.
- **autonomy-grades** — consumes the decision space to bound what an actor may do unattended.

