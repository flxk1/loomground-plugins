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

`ecosystem/repository-checks.json` names the native GitHub checks required for
each exact revision. `tools/collect_github_evidence.py` queries GitHub directly,
normalizes the matching check-run identifiers and conclusions, preserves that
evidence, and emits a repository result only when every required check completed
successfully at the exact commit. It ignores unrelated checks but never accepts a
similarly named, stale, pending, skipped, or failed required check.

The manually dispatched `ecosystem-repository-evidence` workflow exercises this
against GitHub. The first observed baseline was 37/41. The pinned commits of
`loomground-epistemic`, `loomground-factual`, `loomground-workspace`, and
`oversight-certificate` have no GitHub check runs, so an isolated four-entry
matrix checks out those exact revisions and runs their native Pytest suites. For
`loomground-epistemic`, its exact `loomground-factual` dependency is checked out
separately. Each successful log is hashed and bound to its repository result.

The final job merges GitHub evidence and native backfill evidence, then requires
exactly 41 unique passing results at the manifest revisions. No job may replace a
missing result with an inventory assertion.

The central release gate validates the inventory, check-contract parity, pin
parity, schemas, negative cases and deterministic aggregation. Promotion to an
ecosystem release must additionally supply all 41 repository results and eight
scenario results. The complete repository executor is implemented; the eight
cross-repository scenario adapters remain the next integration boundary.
