---
name: compile-loomground-policy
description: RVND-owned. Compile structured norms into a validated Loomground .lg policy program and validate the policy graph, via the installed loomground_solver. Triggers - "compile the policy", "translate norms into loomground", "make this runnable by the solver", "validate the policy grammar".
---

# compile-loomground-policy

The second step of the RVND pipeline: turn extracted norms into the **executable grammar** the
Solver runs. It compiles the norm records into a Loomground `.lg` policy program — Tatbestand →
Rechtsfolge as rules over Federation-5D pairs and typed nD coordinates — and validates the
policy graph through the installed kernel. It emits grammar; it does not reason or decide.

## Run it

```
echo '{"source":"<.lg>","transport":{...}}' | python3 scripts/compile.py
```

Delegates to the installed engine; holds no copied logic and exits non-zero if the engine is absent.

## When to use

- Structured norms exist and need to become a runnable policy.
- A `.lg` policy needs validating or a change needs re-validating before it governs.

Do NOT use it to extract norms (that is the prior skill), to decide a case, or to resolve rule
conflicts — those are separate skills.

## More

- `references/reference.md` - full inputs, semantics, and guardrails.
- `references/eval.json` - what it wraps, determinism, and test status.
