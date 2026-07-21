---
name: resolve-rule-conflicts
description: Solver-owned. Resolve conflicting rules soundly via the kernel's reinstatement-sound defeasibility and rule-packs, mapping lex superior/specialis/posterior. Triggers - "these rules conflict", "which rule wins", "resolve the contradiction", "why did it come out undecided".
---

# resolve-rule-conflicts

When two rules point opposite ways, this skill decides which one governs — soundly, with the
defeat chain shown. It drives the kernel's defeasibility layer (grounded, reinstatement-sound)
and rule-packs; it does not invent a tie-break.

## When to use

- A governance check came back `undecided` or named conflicting rules.
- A new rule may override an existing one and you need the sound result, not a hunch.

Do NOT use it to author, compile, or run a first-pass verdict — it takes over *after* a conflict
is exposed.

## More

- `references/reference.md` - full inputs, semantics, and guardrails.
- `references/eval.json` - what it wraps, determinism, and test status.
