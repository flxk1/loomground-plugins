# Loomground plugins

Canonical source packages and the small build tool used to produce Claude, Codex, and generic
skill-host distributions.

## Repository contents

- `<package>/package.json` is the canonical package manifest.
- `<package>/skills/` contains the portable skill source.
- `schemas/loomground-package.schema.json` defines the package contract.
- `tools/build_packages.py` validates packages and generates host distributions.
- `.claude-plugin/marketplace.json` is the Claude marketplace index.

Generated files under `dist/`, local workspace configuration, caches, and installed package
copies do not belong in the repository.

## Build and test

```bash
python3 tools/build_packages.py --target all
python3 -m unittest discover -s tests
```

Do not edit generated files under `dist/`. Use stable capability identifiers such as
`knowledge.capture` for relationships between packages, and keep user data and credentials
outside package directories.

## Authorship

This work is authored by **flxk1** and was assisted by Claude and Codex. Claude and Codex are
acknowledged as tools, not authors or co-authors.
