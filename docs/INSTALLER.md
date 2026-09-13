<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->

# Loomground installer contract

The `loomground` command is currently a non-mutating bootstrap planner. It
stabilises profiles, host detection and diagnostics before host configuration
or package installation is automated.

```bash
python3 -m pip install .
loomground plan --profile compliance --host auto
loomground doctor --host auto
```

Profiles select task-level plugins, not separate copies of their runtime
dependencies:

- `compliance` (default): A2A Compliance, policy, evidence, privacy,
  governance and solver.
- `core`: language planes, governance, ingest and solver.
- `knowledge`: ingest, Versum, factual/epistemic language and solver.
- `full`: all 13 marketplace plugins.

## Signed bundles and transactional installation

A release operator builds a profile bundle with an Ed25519 key supplied from
outside the repository:

```bash
python3 tools/build_profile_bundle.py \
  --profile compliance --target codex \
  --output /absolute/path/loomground-compliance \
  --signing-key /secure/path/release-private.pem \
  --key-id loomground-release-2026
```

The private key is neither generated nor stored by the builder. A user obtains
the trusted public key through an independent release channel, verifies the
bundle, and chooses an explicit installation destination:

```bash
loomground bundle verify /path/to/bundle --public-key /path/to/release-public.pem
loomground bundle install /path/to/bundle \
  --public-key /path/to/release-public.pem \
  --destination /absolute/path/chosen/by/user
```

Installation verifies the DSSE/Ed25519 signature, every file path, the complete
file set, byte sizes and SHA-256 digests before staging. It then swaps the staged
tree atomically. An existing destination is retained as a uniquely named sibling
backup. Reinstalling the same digest is a no-op. Rollback also verifies the
backup before swapping it back:

```bash
loomground bundle rollback \
  --destination /absolute/path/chosen/by/user \
  --backup /absolute/path/.chosen.by.user.loomground-backup-… \
  --public-key /path/to/release-public.pem
```

Safety invariants:

1. `plan` and `doctor` never write files or run discovered executables.
2. Bundle installation writes only below an explicit absolute destination and
   its existing parent; it never edits host configuration.
3. Signature and content verification finish before staging or replacement.
4. Existing installs are retained for rollback; failed replacement restores
   the original tree.
5. The reported enforcement mode is always `advisory`.
6. Missing runtime distribution and unpublished host bundles are reported as
   blockers, not replaced with mutable installs.
7. No approval, dispatch or host permission is requested.

This installs a verified skill/profile tree, not the Loomground runtime and not
host registration. Those remain separate until a signed runtime artifact and
host-specific configuration adapters have their own rollback-tested contracts.
