# ADR-000 — Device / OS / domain-neutral, config-driven KG package

**Status:** Accepted   **Deciders:** Loomground KG product

## Context
The Loomground Versum KG is a product, not a one-off for one machine. Its tools (bulk
`migrate_full`, the live `sync`/`watch` indexer, and the `kg_query` cockpit lens) must run
unchanged on any machine, OS, and knowledge domain. Early scripts hardcoded one user's home
paths and one legal profile — fine as a spike, wrong as a product.

## Decision
**All machine-, library-, and domain-specific values live in a single JSON config; the code
carries none.** Every tool resolves the config from, in order: `--config` → the
`LOOMGROUND_KG_CONFIG` env var → `./loomground-kg.config.json` → the tool's own directory.
The config declares `kg_root`, `profile_id`, `exclude_prefixes`, `watch_interval_seconds`, and
a list of `libraries` (each with `id`, `root_path`, `urn_namespace`, optional `registry_csv`,
`registry_path_prefix`). The engine core stays domain-neutral (guarded by the
dependency-inversion test); domain vocabulary lives only in profiles; OS-specific auto-start
(launchd/systemd) is a thin adapter *outside* the core.

## Options considered
| Option | Assessment |
|---|---|
| Hardcode paths per install | Low effort, not a product; every machine needs a code edit. |
| Scattered env vars | Works but undocumented surface; no single source of truth. |
| **One config file, resolver order** *(chosen)* | One machine-specific artifact; code fully portable; testable; matches how migrate/sync/query already differ only by paths. |

## Trade-offs
One config to keep correct (the `root_path` pointer is load-bearing — a stale value unresolves
a library). Paid down by: config is the *only* device artifact, validated on load, and the
same file drives every tool so they can never disagree.

## Consequences
- Easier: the package is a real product — clone, drop a config, run; works on any machine/domain.
- Easier: N libraries and N profiles are config, not code.
- Harder: nothing may read a path from anywhere but the config; new tools must use the resolver.
- Revisit: multi-library domain-name collisions currently share a flat `by-domain/<domain>`
  folder (disambiguated by the `library` column on each claim); namespace the layout by
  `library_id` if libraries grow to collide.

## Action items
1. [x] `migrate_full.py`, `kg_query.py` read the config; no baked paths.
2. [x] `config.example.json` (neutral) ships in the package; the real config is the one device file.
3. [ ] `sync`/`watch` (Live Index) read the same config (in build).
4. [ ] launchd/systemd auto-start ships as an adapter outside the engine core.
