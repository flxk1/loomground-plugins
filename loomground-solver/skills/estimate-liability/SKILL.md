---
name: estimate-liability
description: Estimate the conditional probability of liability (or other adverse outcome) as a calibrated range, given evidence factors. Solver analytic skill wrapping the kernel's Bayesian method; an organisational estimate, not legal advice. Triggers - "how likely is liability", "exposure probability", "odds of an adverse finding".
---

# estimate-liability

Turn a set of evidence factors into a calibrated estimate of how likely an adverse outcome is.
The kernel updates a prior on each factor's likelihood and reports a range, with the assumptions
that move it — so the number is defensible, not asserted.

## Run it

```
echo '{"prior":{...},"likelihoods":{...},"evidence":"e"}' | python3 scripts/run.py
```

Delegates to the installed engine; holds no copied logic and exits non-zero if the engine is absent.

## More

- `references/reference.md` - full inputs, semantics, and guardrails.
- `references/eval.json` - what it wraps, determinism, and test status.
