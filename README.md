<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->

# loomground-plugins

Distribute Loomground skills and one pinned runtime to Claude, Codex/OpenAI, Cursor, n8n and generic MCP/Agent Skills hosts from their canonical repositories.

## Problem

Without one catalogue, host packages drift from the skills and versions maintained beside each Loomground tool.

## Requirements

Check these before installing; `loomground doctor` checks the first three for
you.

| Requirement | Needed for | Source |
| --- | --- | --- |
| Python 3.12 (`>=3.12, <3.13`) with pip | the Loomground runtime | `runtime/runtime-sources.json` |
| Python `>=3.11` | the `loomground` installer CLI itself | `pyproject.toml` `requires-python` |
| git | installing from source only | not needed for signed bundles |

- No Python interpreter is bundled. A runtime bundle carries locked wheels
  only; `loomground runtime install` and `loomground onboard` install them with
  the interpreter that runs `loomground`, and the installed launcher stays bound
  to that interpreter. The installer CLI starts on `>=3.11`, but runtime
  installation requires it to run under Python 3.12.
- Signed runtime bundles are built by `.github/workflows/runtime-release.yml`
  on the runners `ubuntu-24.04`, `ubuntu-24.04-arm`, `macos-14`,
  `macos-15-intel`, `windows-2025` and `windows-11-arm`, which
  `docs/RUNTIME-RELEASE.md` describes as Linux x86-64/ARM64, macOS Intel/ARM64
  and Windows x86-64/ARM64. Each bundle is named
  `loomground-runtime-<version>-<platform>-py312`, where `<platform>` is
  `runtime_platform()` (`<system>-<machine>` as the build machine reports it,
  e.g. `darwin-arm64`); the installer rejects a bundle whose platform or
  Python range does not match.
- The Claude Code or Codex plugin alone does not install the runtime. It
  registers a `loomground-mcp` server that must already be on `PATH`. Run
  `loomground onboard` to install the runtime.

`loomground doctor` reports three requirement checks next to its host checks:

| Check | Statuses | Fix it prints |
| --- | --- | --- |
| `python` | `ok`, `unsupported` (running interpreter outside `3.12 <= python < 3.13`), `unknown` (range file not found) | install a CPython interpreter satisfying that range and re-run `loomground onboard` with it |
| `pip` | `ok`, `missing` | `python -m ensurepip --upgrade` |
| `git` | `ok`, `missing` (informational) | install git only if installing from source |

`python` and `pip` failures make `doctor` exit non-zero; `git` never does.
`loomground doctor --json` lists them under `requirement_checks`.

In Claude Code, the `loomground-suite` plugin adds a SessionStart hook. When
`loomground-mcp` is not on `PATH`, it shows:

```text
Loomground runtime not installed: run `loomground onboard` (Python 3.12 required)
```

The hook checks only `PATH`; it is silent when `loomground-mcp` is found.
Codex has no plugin hook: Codex users rely on `loomground doctor` and these
docs.

## Install

```text
Claude Code: /plugin install loomground-suite@loomground
Codex:       codex plugin add loomground-suite@loomground
```

Register the marketplace first. The suite installs the control skill and MCP
registration; the executable runtime installs separately. See
[docs/SUITE.md](docs/SUITE.md).

Safe bootstrap preview (host configuration and runtime components stay
untouched):

```bash
python3 -m pip install .
loomground plan --profile compliance --host auto
loomground doctor --host auto
```

One guided command verifies the downloaded release assets and installs the
runtime, without changing existing host settings:

```bash
loomground onboard
```

Bundle installation requires an explicit destination and trusted Ed25519
public key, leaving Claude and Codex configuration untouched. See
[docs/INSTALLER.md](docs/INSTALLER.md).

The runtime release pipeline builds signed wheel bundles for a Python 3.12
interpreter the user already has, on the six platforms listed under
Requirements. Each is authenticated by GitHub OIDC/Sigstore attestation and
signed with an ephemeral key discarded after use. See
[docs/RUNTIME-RELEASE.md](docs/RUNTIME-RELEASE.md).

The ecosystem certification contract covers the 41 certified Loomground
repositories at exact revisions and eight cross-repository failure
scenarios; missing, stale, or mutated evidence cannot produce a passing
certificate. It does not prove every possible composition, external host
implementation, policy corpus or live credential boundary. See
[docs/ECOSYSTEM-TESTING.md](docs/ECOSYSTEM-TESTING.md).

## Usage

`externals.json` pins 13 public source repositories by commit;
`tools/build_packages.py` validates them and builds host-specific packages.
`.claude-plugin/marketplace.json` is the committed catalogue that
`loomground-suite` composes without copying the repositories.

The catalogue distributes 25 skills across governance, runtime controls,
evidence, ingest, solver analysis, Versum knowledge work, and the language
planes.

A maker with an alternate effect route can bypass the control plane; that
deployment is advisory, not enforced.

## Example

```text
in : python3 tools/build_packages.py --target codex
out: dist/codex/<package>/ contains the pinned skills and installation metadata
```

## Interface

| Surface | Contract |
| --- | --- |
| source registry | `externals.json`: repository URL, immutable commit, sibling path |
| package manifest | `<source>/package.json` against `schemas/loomground-package.schema.json` |
| Claude catalogue | `.claude-plugin/marketplace.json`, regenerated from pins |
| ecosystem certification | `ecosystem/manifest.json`: the 41 certified repositories, exact revisions, invariants and scenarios |
| release gate | JSON validity, supply-chain checks, generated-catalogue parity, tests |

## Family

Interfaces and authoring: consumes committed skills from 13 Loomground repositories at immutable pins, produces installation packages for supported hosts. Plane execution stays in `loomground-mcp` and the source repositories.

## Status

Installer 0.4.0 · runtime release 0.1.0 · 0.1.0 catalogue · 13 source plugins + 1 suite entry point · 25 source skills + 1 control skill · Python 3.12 for the runtime · Python >=3.11 for the installer CLI.

## License

Apache-2.0 · `LICENSES/Apache-2.0.txt` · `NOTICE`.
