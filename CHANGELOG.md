<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->
# Changelog

## 2026-09-27 — install requirements

- README, `docs/SUITE.md`, `docs/INSTALLER.md` and `llms.txt` state install
  prerequisites up front: Python 3.12 with pip for the runtime, Python `>=3.11`
  for the installer CLI, no bundled interpreter, git only for source installs,
  release platforms, and that the plugin does not install the runtime.
- `loomground doctor` python/pip/git checks and the Claude Code SessionStart
  hook message documented; Codex relies on `doctor` and docs.
- `docs/INSTALLER.md` labels its runtime-lock JSON as a schema example.
- `tests/test_docs_requirements.py` fails when a documented runtime Python
  version drifts from `runtime/runtime-sources.json`.
- `requirements.py`'s `_candidate_paths`/`load_runtime_sources`/
  `supported_runtime_python` gained a narrow, default-preserving `start`/
  `include_packaged` injection point, so tests can drive the real
  file-finding/parsing path against a temp `runtime-sources.json` instead of
  a lambda; `tests/test_doctor_requirements.py` adds a file-driven mutation
  test that flips the verdict through the real loader.
- Added `runtime_python_label`, the one short-label formatter for the
  supported runtime Python range (single minor, same-major span with an en
  dash, or an explicit `>=A.B, <C.D` constraint string for cross-major
  ranges); `loomground doctor`, `tools/render_suite_hook.py` (which
  generates the loomground-suite SessionStart hook's label line) and
  `tests/test_docs_requirements.py` all call it, replacing the retired
  `minimum_runtime_python_label` and the hook's hand-copied literal.

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
