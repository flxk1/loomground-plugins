<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->

# loomground-plugins

Distribute Loomground skills and one pinned runtime to Claude, Codex/OpenAI,
Cursor, n8n and generic MCP/Agent Skills hosts from their canonical repositories.

## Problem

Without one catalogue, host packages drift from the skills and versions maintained beside each Loomground tool.

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

The runtime release pipeline builds Linux/macOS/Windows Python 3.12 bundles,
authenticated by GitHub OIDC/Sigstore attestation and signed with an
ephemeral key discarded after use. See
[docs/RUNTIME-RELEASE.md](docs/RUNTIME-RELEASE.md).

The ecosystem certification contract covers the 41 catalogued Loomground
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
| ecosystem certification | `ecosystem/manifest.json`: the 41 catalogued repositories, exact revisions, invariants and scenarios |
| release gate | JSON validity, supply-chain checks, generated-catalogue parity, tests |

## Family

Interfaces and authoring: consumes committed skills from 13 Loomground repositories at immutable pins, produces installation packages for supported hosts. Plane execution stays in `loomground-mcp` and the source repositories.

## Status

Installer 0.4.0 · runtime release 0.1.0 · 0.1.0 catalogue · 13 source plugins + 1 suite entry point · 25 source skills + 1 control skill · Python >=3.11 for release tooling.

## License

Apache-2.0 · `LICENSES/Apache-2.0.txt` · `NOTICE`.
