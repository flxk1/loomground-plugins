# extract-policy-norms - reference

## What it extracts, per rule

- **Deontic modality** — obligation, prohibition, or permission (and duty-holder).
- **Tatbestand** — the triggering elements that must hold for the rule to apply.
- **Rechtsfolge** — the legal consequence when the Tatbestand is met.
- **Exceptions / defeaters** — conditions that block or override the rule.
- **Scope** — who/what/where it binds; jurisdiction; addressees.
- **Priority markers** — hierarchy, specificity, and date, so lex superior / specialis /
  posterior can be resolved later (by `resolve-rule-conflicts`, not here).
- **Temporal validity** — in force from / until; transitional rules.
- **Grounding** — the exact source span each of the above came from.

## How it runs

Deterministic-first, local model on the rails, per the effort policy the user owns. Identity,
citation, and span anchoring are computation; a model is invited only to segment prose into
rule units and label modality, and its output is checked against the closed deontic vocabulary
before it is kept. Output is a structured norm set (JSON), each record carrying its grounding.

## Guardrails

- **Grounded or flagged.** Every element traces to a span; anything inferred is marked, not
  stated as text.
- **No decision, no translation.** This skill only structures the norms.
- **Deontic vocabulary is closed.** Modalities come from the fixed set, not free text.
- **Domain-neutral.** The vocabulary of a field comes from a profile, not hard-coded here.

## Relationship

- **compile-loomground-policy** — consumes these norms and compiles them to a `.lg` policy.
- **loomground_solver.ports.NormSource** — the host interface these records are served through
  to RVND / the Solver.

