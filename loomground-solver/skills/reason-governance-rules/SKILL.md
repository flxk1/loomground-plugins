---
name: reason-governance-rules
description: Solver-owned. Reason a case against a compiled policy to a justified PASS/VIOLATION/ESCALATE verdict plus the accepted/undecided/rejected decision space, with a replayable proof. Wraps the kernel's verify; fails closed without it. Triggers - "is this compliant", "check against the policy", "does this violate the rules", "run the governance check".
---

# reason-governance-rules

The reasoning step: given a case and a validated `.lg` policy, the Solver decides — and shows
its work. This skill wraps the kernel's rule reasoning (subsumption, Tatbestand → Rechtsfolge,
exceptions, defeasibility) and returns a verdict you can replay, never a prose opinion.

## Run it

```
echo '{...reasoning request...}' | python3 scripts/reason.py
```

Delegates to the installed engine; holds no copied logic and exits non-zero if the engine is absent.

## When to use

- Check an action, document, or plan against a compiled governance policy.
- Produce a compliance verdict that must be explainable and reproducible.

Do NOT use it to author or compile a policy (earlier skills), and do NOT resolve genuine rule
conflicts here — hand those to `resolve-rule-conflicts`.

## More

- `references/reference.md` - full inputs, semantics, and guardrails.
- `references/eval.json` - what it wraps, determinism, and test status.
