<!-- SPDX-License-Identifier: Apache-2.0 -->
# loomground skill

The **operational** layer over the Loomground language: a skill that turns an
AI-governance requirement into a *verified* `.loom` policy-graph patch.

`SKILL.md` is the procedure — draft → validate → classify:
1. Load the language (`llms.txt`, `language-card.json` from the standard).
2. Apply the litmus: classify each requirement as **express** (a declaration),
   **policy** (a deployment value), or **host** (compute/aggregate/schedule/
   persist/communicate — not expressible; hand it off).
3. Draft the `.loom` patch from the *express* set.
4. Validate with `validate.py`, which runs the Loomground reference implementation
   as the checker.
5. Report what the patch governs and what was handed to a host.

This is a *host* artifact that **uses** the language; it is not part of the
standard. It expects the Loomground standard (for `llms.txt` and the schemas) and
the reference implementation (`loomground-ref`, for `validate.py`) to be available.

## Use
```bash
python3 validate.py PATCH.loom    # WELL-FORMED + projection, or REJECTED (stage): reason
```

## Provenance
Written with AI assistance (Claude, Anthropic) under human direction; the human
author makes the decisions and is responsible for the content.
