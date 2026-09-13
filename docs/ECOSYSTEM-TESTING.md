<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->

# Ecosystem testing

Loomground is certified as one revision-bound system, not as 41 unrelated green
repositories. The canonical inventory is `ecosystem/manifest.json`.

## What must pass

1. **Inventory:** exactly 41 uniquely sorted public repositories with canonical
   URLs, immutable revisions, one stated invariant and one test profile each.
2. **Runtime parity:** the 32 executable packages must use the exact commits in
   `runtime/runtime-sources.json`. `loomground-plugins` uses `self`, resolved to
   the commit being certified.
3. **Repository evidence:** one and only one passing result for every pinned
   repository. The result binds the commit, sorted check names and the SHA-256 of
   its external evidence.
4. **System evidence:** one and only one passing result for every declared
   cross-repository scenario. Every repository participates in at least one
   scenario.
5. **Certificate integrity:** canonical JSON produces a deterministic certificate
   digest. Any later mutation invalidates it.

The eight initial scenarios exercise cross-host parity, conflicting jurisdiction,
erasure and reingestion, single-use maker admission, PII egress denial, policy
freshness, tripwire quarantine, and reconciliation of an unpermitted effect.

## Commands

Validate the inventory and its runtime pins offline:

```bash
python tools/ecosystem_certify.py
```

After repository and scenario jobs have written JSON results conforming to
`schemas/ecosystem-test-result.schema.json`, aggregate them:

```bash
python tools/ecosystem_certify.py \
  --results /absolute/results \
  --self-commit "$GITHUB_SHA" \
  --output /absolute/ecosystem-certification.json
```

Verify the resulting artifact independently:

```bash
python tools/ecosystem_certify.py \
  --verify-certificate /absolute/ecosystem-certification.json
```

The certificate schema is `schemas/ecosystem-certification.schema.json`.

## Trust boundary

The aggregator does not claim that a test ran merely because a repository is
listed. It accepts only a complete result set and binds every result to the pinned
revision. The execution layer must still check out those revisions, run each
repository's native tests and the scenario adapters in isolated jobs, hash the
full logs, and attach CI provenance to each result. A missing executor artifact is
a hard failure, never an implicit pass.

The central release gate currently validates the inventory, pin parity, schemas,
negative cases and deterministic aggregation. Promotion to an ecosystem release
must additionally supply the 41 repository results and eight scenario results;
that fan-out CI executor is the next integration boundary.
