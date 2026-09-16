<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->
# Changelog

## 2026-09-13 — ecosystem certification

- Revision-bound 41-repository, 8-scenario ecosystem certificate
  (`ecosystem/manifest.json`, `tools/ecosystem_certify.py`).
- Native GitHub check evidence collection plus isolated native-test backfill
  for pins without check-run history (`tools/collect_github_evidence.py`).
- Scenario execution against the published signed runtime
  (`tools/run_ecosystem_scenarios.py`).

## 2026-09-13 — loomground-runtime 0.1.0

- Six-platform Python 3.12 runtime release: build, ephemeral Ed25519 keys,
  GitHub OIDC/Sigstore attestation, portable checksums, cross-platform
  marker filtering (`tools/assemble_runtime_release.py`,
  `tools/generate_ephemeral_release_key.py`, `tools/runtime_release_gate.py`).

## 2026-09-13 — loomground-installer 0.1.0 → 0.4.0

- 0.1.0: safe installation planner (`loomground plan`, `loomground doctor`).
- 0.2.0: signed transactional bundles (Ed25519 bundle verify/install).
- 0.3.0: signed runtime bundle and cross-host adapters (Claude, Codex,
  Cursor, OpenAI, n8n, generic).
- 0.4.0: attested runtime onboarding (`loomground onboard`, guided
  non-mutating host/maker handoff).

## 2026-09-11 – 2026-09-12 — marketplace

- Initial catalogue: 13 source plugins, `loomground-suite` control skill,
  `.claude-plugin/marketplace.json` (8b01752).
- Agent plugin registration, policy-compiler repin (deontic-0.2 modal fix),
  family-canon README/llms.txt conventions.
