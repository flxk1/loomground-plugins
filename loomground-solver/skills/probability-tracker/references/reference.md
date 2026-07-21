# probability-tracker - reference

## Run it

```
echo '{"prior":{"h1":0.3,"h2":0.7},"likelihoods":{"h1":{"e":0.9},"h2":{"e":0.2}},"evidence":"e"}' \
  | python3 scripts/run.py
```

Returns the kernel's `{choice (MAP hypothesis), ranking, scores (posterior)}`. Delegates to
`loomground_solver`; holds no copied maths and exits non-zero if the kernel is absent.

## More

- `references/reference.md` — inputs, update semantics, calibration guidance, and guardrails.
- `references/eval.json` — what it wraps, determinism, and test status.

