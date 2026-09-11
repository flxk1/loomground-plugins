<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->

# Loomground plugins

Universal skill packages for Loomground tools (deontic, governance, ingest, solver, versum, and the
factual, epistemic, norm and topos planes), installable on **Claude Code**,
**Codex**, and **generic skill hosts** from one canonical source.

## Install on Claude Code

This repository is a Claude Code plugin marketplace — no build step needed:

```
/plugin marketplace add flxk1/loomground-plugins
/plugin install loomground-versum@loomground
```

Available plugins: `loomground-deontic`, `loomground-governance`,
`loomground-ingest`, `loomground-solver`, `loomground-versum`, `loomground-factual`,
`loomground-epistemic`, `loomground-norm`, `loomground-topos`.
Every plane plugin wires the `loomground` MCP server (`loomground-mcp serve --transport stdio`,
from [loomground-mcp](https://github.com/flxk1/loomground-mcp)) so its skill can call the
plane's tool. (Solver add-on advice ships inside `loomground-solver` as the
`advise-solver-addons` skill; the `.lg` patch-authoring skill ships inside
`loomground-governance`, invoked as `loomground`; the KG cockpit and chat skills ship
inside `loomground-versum`; the ingest-plane skill ships inside `loomground-ingest`.)

## The skills

Each plugin is standalone — install just the one you want; it needs none of the others.
After `/plugin marketplace add flxk1/loomground-plugins`, run the install line under each
plugin (or `/plugin` to browse and click-install). 10 plugins, 22 skills.

### loomground-governance  ·  `/plugin install loomground-governance@loomground`
- **loomground** — Express an AI-governance requirement as a verified `.lg` policy-graph patch
  (oversight, reservation, prohibition, separation-of-duty/quorum, redress, delegation,
  disclosure); validate or fix a patch; judge whether a requirement is expressible.

### loomground-deontic  ·  `/plugin install loomground-deontic@loomground`
- **deontic** — Transcribe a natural-language norm into a verified deontic formula
  `O/P/F(bearer : action)`; classify the Hohfeldian incident (claim, duty, privilege,
  no-right, power, liability, immunity, disability).

### loomground-ingest  ·  `/plugin install loomground-ingest@loomground`
- **loomground-ingest** — Drive the ingest plane: turn an acquired artifact into a dimensioned
  subgraph (nodes, edges, dimension, provenance, quarantine); dry-run by default; writes only
  through a governed sink.

### loomground-solver  ·  `/plugin install loomground-solver@loomground`
- **analyse-risks** — Score and rank risks by impact × likelihood and prioritise mitigations.
- **estimate-liability** — Estimate the conditional probability of liability as a calibrated
  range (Bayesian); an organisational estimate, not legal advice.
- **litigation-risk-assessor** — Quantify exposure, weigh merits, recommend settle vs fight.
- **opponent-modeler** — Model an adversary — options, payoffs, likely move, exploitable tendencies.
- **probability-tracker** — Maintain and update a calibrated probability as evidence arrives.
- **strategic-analysis** — Analyse a competitive/adversarial position — moves, threats,
  opportunities, plan — via decision methods and possible-worlds.
- **advise-solver-addons** — Assess whether a Solver problem needs the world-model add-on, or
  whether runs are ready for metacognitive analysis.

### loomground-versum  ·  `/plugin install loomground-versum@loomground`
- **loomground-kg** — The cockpit over the Versum knowledge graph: state, what grounds a claim,
  what to run next, routing.
- **loomground-kg-chat** — Conversational, read-only Q&A over the KG, grounded on every read,
  local-model-first.
- **loomground-knowledge-write** — The single write path into a KG; delegates every executable
  write to the capture-to-kg writer. Never fetches.
- **loomground-curate** — Coordinate-identity curation to mint the concept / mental-model layer
  (whole KG or one domain); build domain canon.
- **loomground-enrich** — Grow the graph from research findings — extract, validate, propose with
  confidence; writes route through `loomground-knowledge-write`.
- **loomground-organise** — Organise documents into a Versum by shared mental models, a person
  confirming every placement.
- **loomground-mental-model** — The mental-model engine: scan content into a grounded ConceptGraph
  and project it to the format that answers the question.

### loomground-factual  ·  `/plugin install loomground-factual@loomground`
- **factual** — Lower one plain assertion into a factual triple (subject, predicate, object) with
  dimension, negation and quantification; the MCP server carries `factual_lower`.

### loomground-epistemic  ·  `/plugin install loomground-epistemic@loomground`
- **epistemic** — Who knows or believes what, at which certainty band (K/B, holder, proposition,
  certainty, source); the MCP server carries `epistemic_extract`.

### loomground-norm  ·  `/plugin install loomground-norm@loomground`
- **norm** — Lift running text into a RuleFacet and on into a rendered deontic formula, in the 24
  EU languages; the MCP server carries `norm_extract`.

### loomground-topos  ·  `/plugin install loomground-topos@loomground`
- **topos** — Read and write `lt`, the legal-system topology language (systems, levels, organs,
  instruments, competences, relations, assertions); the MCP server carries `topos_parse`.


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
| `externals.json` | Every plugin's canonical source lives in its tool repository, mapped here as a sibling-checkout path plus the immutable commit pin. `kind: package` externals carry a `package.json` and build for all three hosts; `kind: plugin` externals (`loomground-factual`, `loomground-epistemic`, `loomground-norm`, `loomground-topos`) carry only their committed `.claude-plugin/plugin.json`, listed verbatim for Claude Code |
| `.claude-plugin/marketplace.json` | Claude Code marketplace catalog (generated, committed) |
| `schemas/` | The `loomground-package.schema.json` package contract |
| `tools/` | `build_packages.py` — validates packages, generates host distributions and the committed Claude artifacts; `release_gate.py` and `supply_chain_gate.py` enforce the release and supply-chain gates |
| `tests/` | Package, build, and skill-script tests |
| `docs/` | Planning and quality notes |

Each package's `package.json` is its single source of truth and lives in the tool repository
next to the skills it describes (plugin-lives-with-tool); this repository is the catalog and
build front-end, and rebuilding here requires the sibling checkouts listed in
`externals.json`. The Claude artifacts (`marketplace.json` here, `plugin.json` in each tool
repository) are generated and **committed**, because Claude Code installs from the
repositories themselves; Codex and generic distributions are generated into `dist/`, which
stays out of the repository. After editing any `package.json`, or re-pinning a commit in
`externals.json`, rerun `python3 tools/build_packages.py --target all` and commit the synced
Claude artifacts in every repository the run touched — `tests/test_package_build.py` fails if
they drift.

## Test

```bash
python3 -m pytest -q
python3 tools/release_gate.py  # required before release
```

The complete release definition of done is in
[`docs/RELEASE-DoD.md`](docs/RELEASE-DoD.md).

Do not edit generated files (`dist/`, `.claude-plugin/`). Use stable capability identifiers such
as `knowledge.capture` for relationships between packages, and keep user data and credentials
outside package directories.

## Authorship

This work is authored by **Loomground Contributors** and was assisted by Claude and Codex. Claude and Codex are
acknowledged as tools, not authors or co-authors.
## License

Apache License 2.0. See `LICENSE`, `LICENSES/Apache-2.0.txt`, and `NOTICE`.
