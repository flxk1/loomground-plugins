---
name: analyse-risks
description: Score and rank risks by impact x likelihood and prioritise mitigations, via the kernel's decision methods. Solver analytic skill; fails closed without the kernel. Triggers - "analyse the risks", "risk matrix", "score these risks", "what to mitigate first".
---

# analyse-risks

Take a list of risks and turn it into a defensible priority order. Each risk gets an impact and a
likelihood; the kernel scores and ranks them, and proposes mitigations in priority order — with
the scoring scheme shown so the ranking is auditable, not a black box.

## Run it

```
echo '{"vectors":{"riskA":[impact,likelihood]}}' | python3 scripts/run.py
```

Delegates to the installed engine; holds no copied logic and exits non-zero if the engine is absent.

## More

- `references/reference.md` - full inputs, semantics, and guardrails.
- `references/eval.json` - what it wraps, determinism, and test status.
