<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->

# loomground-plugins

Distribute Loomground skills to Claude Code, Codex, and generic Agent Skills hosts from their canonical repositories.

## Problem

Without one catalogue, host packages drift from the skills and versions maintained beside each Loomground tool.

## Install

One host-facing entry point:

```text
Claude Code: /plugin install loomground-suite@loomground
Codex:       codex plugin add loomground-suite@loomground
```

Register the corresponding marketplace first. The suite installs the central
control skill and MCP registration; it does not yet install the executable
runtime. See [docs/SUITE.md](docs/SUITE.md) for exact host commands, external
plugin integration and the remaining one-install boundary.

Safe bootstrap preview (does not change host configuration or install runtime
components):

```bash
python3 -m pip install .
loomground plan --profile compliance --host auto
loomground doctor --host auto
```

See [docs/INSTALLER.md](docs/INSTALLER.md) for profiles, current blockers and
the signed-bundle and transactional installation contract. Bundle installation
always requires an explicit destination and trusted Ed25519 public key; it does
not edit Claude or Codex configuration.

Manual installation remains available:

Claude Code:

```text
/plugin marketplace add flxk1/loomground-plugins
/plugin install loomground-suite@loomground
```

Codex or a generic Agent Skills host:

```bash
python3 -m pip install -r requirements-dev.txt
python3 tools/build_packages.py --target codex  # or: generic, all
```

Generated packages land under `dist/` and remain untracked.

## Usage

`externals.json` pins 13 public source repositories by commit. Five sources carry a `package.json`; eight sources carry a committed Claude plugin manifest. `tools/build_packages.py` validates those sources and builds host-specific packages. `.claude-plugin/marketplace.json` is the committed Claude Code catalogue; `loomground-suite` composes it without copying the repositories.

The catalogue distributes 25 skills across governance, runtime controls, evidence, ingest, solver analysis, Versum knowledge work, and the language planes.

## Example

```text
in : python3 tools/build_packages.py --target codex
out: dist/codex/<package>/ contains the pinned skills and installation metadata
```

## Contracts

| Surface | Contract |
| --- | --- |
| source registry | `externals.json`: repository URL, immutable commit, sibling path |
| package manifest | `<source>/package.json`, checked against `schemas/loomground-package.schema.json` |
| Claude catalogue | `.claude-plugin/marketplace.json`, regenerated from the pinned sources |
| release gate | JSON validity, supply-chain checks, generated-catalogue parity, tests |

## Family

Interfaces and authoring. Consumes committed skills from 13 Loomground repositories at immutable pins. Produces installation packages for supported skill hosts. Plane execution remains in `loomground-mcp` and the source repositories.

## Status

0.1.0 catalogue · 13 source plugins + 1 suite entry point · 25 source skills + 1 control skill · Python >=3.11 for release tooling.

## License

Apache-2.0 · `LICENSES/Apache-2.0.txt` · `NOTICE`.
