# Loomground plugins

Universal skill packages for Loomground tools (Versum, Solver, KG), installable on **Claude
Code**, **Codex**, and **generic skill hosts** from one canonical source.

## Install on Claude Code

This repository is a Claude Code plugin marketplace — no build step needed:

```
/plugin marketplace add flxk1/loomground-plugins
/plugin install loomground-versum@loomground
```

Available plugins: `loomground-kg`, `loomground-skill`, `loomground-solver`,
`loomground-versum`. (Solver add-on advice ships inside `loomground-solver` as the
`advise-solver-addons` skill.)

## Install on Codex or a generic skill host

Build the host distributions, then install from `dist/`:

```bash
python3 -m pip install -r requirements-dev.txt   # once
python3 tools/build_packages.py --target codex   # or: generic, all
```

Codex bundles land in `dist/codex/<package>/`; generic hosts follow
`dist/generic/<package>/INSTALL.md`.

## Repository layout

| Path | Role |
| --- | --- |
| `loomground-skill/` | Marketplace-local universal package: `package.json` (canonical manifest), `skills/` (portable skill source), `.claude-plugin/plugin.json` (generated, committed) |
| `externals.json` | Packages whose canonical source lives in their tool repository (`loomground-kg`, `loomground-solver`, `loomground-versum`), as sibling-checkout paths |
| `.claude-plugin/marketplace.json` | Claude Code marketplace catalog (generated, committed) |
| `schemas/` | The `loomground-package.schema.json` package contract |
| `tools/` | `build_packages.py` — validates packages, generates host distributions and the committed Claude artifacts |
| `tests/` | Package, build, and skill-script tests |
| `docs/` | Planning and quality notes |

`<package>/package.json` is the single source of truth for each package. For the migrated
packages listed in `externals.json` it lives in the tool repository next to the skills it
describes (plugin-lives-with-tool); rebuilding here requires those sibling checkouts. The
Claude artifacts (`marketplace.json`, per-package `plugin.json`) are generated and
**committed** — in this repository for local packages, in the tool repositories for external
ones — because Claude Code installs from the repositories themselves; Codex and generic
distributions are generated into `dist/`, which stays out of the repository. After editing any
`package.json`, rerun `python3 tools/build_packages.py --target all` and commit the synced
Claude artifacts in every repository the run touched — `tests/test_package_build.py` fails if
they drift.

## Test

```bash
python3 -m pytest -q
```

Do not edit generated files (`dist/`, `.claude-plugin/`). Use stable capability identifiers such
as `knowledge.capture` for relationships between packages, and keep user data and credentials
outside package directories.

## Authorship

This work is authored by **flxk1** and was assisted by Claude and Codex. Claude and Codex are
acknowledged as tools, not authors or co-authors.
