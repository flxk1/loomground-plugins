# loomground-versum

This is a portable Loomground source package. `package.json` is the canonical package manifest;
Claude, Codex, and generic host layouts are generated with
`python3 tools/build_packages.py loomground-versum --target all` from the repository root.
Files under `dist/` are build artifacts and should not be edited directly.

The Loomground Versum knowledge-graph plugin: get a document into the graph, and get it to
the right place — without ever filing it on a guess.

Two skills, one doctrine (the graph is the source of truth; folders are a projection; every
write goes through one door):

- **loomground-knowledge-write** — the single write path. Admits a source (PDF, URL, or
  citation): resolves identity, dedups, writes the house stub + `canonical_urn` sidecar, and
  indexes candidate claims. Deterministic on the happy path; a local model only when identity
  bottoms out. Nothing else writes to the graph.
- **loomground-organise** — LLM-driven placement. For a document waiting in the review queue,
  it ranks the domains and existing sources it shares the most mental models with (rarity-
  weighted concept overlap), shows that evidence, and — only after a person confirms — hands
  the write to loomground-knowledge-write. It names no domain and never auto-files; low-overlap
  or novel items stay in review.

## Effort is yours to set

loomground-organise routes each placement to the cheapest sufficient tier by default (a
`cascade`: deterministic when one domain dominates → local model when it's close → cloud only
on your opt-in). That default is a config file, not a cage. Set `mode` to `cloud` to put the
strongest reader on every placement, `local` to keep everything on the machine, or
`deterministic` for no model at all. The skill asks once and saves your choice. See
`skills/loomground-organise/organise.config.example.json`.

## Requirements

- The ranking helper (`organise.py`) is self-contained (standard library only) and reads a
  by-domain concept store.
- Capture and concept extraction require the **versum engine** (the `versum` package) installed
  in the environment — loomground-knowledge-write drives `python -m versum capture`, and a
  document's concepts come from the engine extractor before organise can rank them.

## Data vs code

Code (this plugin, the engine) is fixed and versioned. Your documents, the graph, and the
effort-policy config are workspace data and live with your workspace, never inside the plugin.
