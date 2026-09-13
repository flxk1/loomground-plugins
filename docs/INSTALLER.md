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

Safety invariants for version 0.1.0:

1. `plan` and `doctor` never write files or run discovered executables.
2. The reported enforcement mode is always `advisory`.
3. Missing runtime distribution and unpublished host bundles are reported as
   blockers, not replaced with mutable installs.
4. No production key, approval, dispatch or host permission is requested.

The next version may add execution only behind an explicit flag. It must stage
all changes, validate the staged configuration, replace atomically, retain a
rollback copy and prove idempotence in host-level smoke tests.
