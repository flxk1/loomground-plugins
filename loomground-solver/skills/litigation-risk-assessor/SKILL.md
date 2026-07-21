---
name: litigation-risk-assessor
description: Assess dispute risk - quantify exposure, weigh merits, recommend settle or fight - via the kernel's decision theory. Solver analytic skill; an organisational assessment, not legal advice. Triggers - "assess litigation risk", "what's our exposure", "settle or fight", "weigh the merits".
---

# litigation-risk-assessor

Weigh a dispute the way a decision analyst would: enumerate the outcomes (win / lose / settle at
various points), attach a value and a probability to each, and let the kernel compute the
expected value and the downside, then recommend a line — with the rule that produced it shown.

## Run it

```
echo '{"payoffs":{...},"probabilities":{...}}' | python3 scripts/run.py
```

Delegates to the installed engine; holds no copied logic and exits non-zero if the engine is absent.

## More

- `references/reference.md` - full inputs, semantics, and guardrails.
- `references/eval.json` - what it wraps, determinism, and test status.
