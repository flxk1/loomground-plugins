# compile-loomground-policy - reference

## How it runs — wraps the real kernel, never re-implements it

```
loomground-solver loomground <policy.lg> [--transport <transport.json>] [-o out.json]
```

The installed `loomground_solver` parses the `.lg` source, validates the policy graph,
evaluates transports, and reproduces the canonical observation. This skill drives that command
and reads its report; the parser, validator, and grammar live in the package, not here.

## Steps

1. **Compile.** Map each norm record (from `extract-policy-norms`) into `.lg` rules: deontic
   modality, Tatbestand elements as guards, Rechtsfolge as the consequence, exceptions as
   defeaters, priority and temporal validity as annotations.
2. **Validate the policy graph.** Run `loomground-solver loomground policy.lg`; read the graph
   validation. A policy that does not validate does not ship — report the errors, don't paper over.
3. **Dry-run a transport** (optional). If a sample situation is supplied as a transport, evaluate
   it to confirm the policy behaves as intended before it governs anything.
4. **Hand off, gated.** A validated `.lg` is a *candidate* policy. It becomes governance-
   authoritative only after a person confirms — never automatically.

## Guardrails

- **Never re-implement the grammar.** Always go through the installed `loomground-solver`.
- **Validated or blocked.** An unvalidated policy graph never advances.
- **Human-authoritative.** Compilation proposes a policy; a person makes it binding.
- **Fail closed.** If the kernel is missing or the source is malformed, stop and report; never
  emit an unvalidated policy as if it were ready.

## Relationship

- **extract-policy-norms** — supplies the norm records this skill compiles.
- **reason-governance-rules** — runs cases against the validated `.lg` policy.
- **loomground_solver.ports.Governance** — the host interface through which RVND makes a
  confirmed policy authoritative.

