---
name: extract-policy-norms
description: RVND-owned. Extract deontic norms (obligation/prohibition/permission, Tatbestand, Rechtsfolge, exceptions, priority) from policy text, grounded to spans. Feeds compile-loomground-policy. Triggers - "extract the policy rules", "turn this regulation into norms", "what are the obligations here".
---

# extract-policy-norms

The first step of the RVND governance pipeline: read a policy and get its **rules as data**.
This skill turns prose obligations into structured, grounded norm records — the input a
`NormSource` serves and `compile-loomground-policy` turns into a `.lg` program. It extracts;
it does not translate to grammar, run the kernel, or decide anything.

## When to use

- A regulation, contract, internal policy, or standard needs its rules made explicit.
- You are preparing a policy to run through the Solver and need the norm layer first.

Do NOT use it to decide compliance, to translate to `.lg` grammar, or to resolve conflicts —
those are the later skills. Do NOT invent a rule the text does not state; an implied rule is
flagged as a gap, not asserted.

## More

- `references/reference.md` - full inputs, semantics, and guardrails.
- `references/eval.json` - what it wraps, determinism, and test status.
