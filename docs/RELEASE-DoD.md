<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->
# Release definition of done

A release is done only when every item below is true. The executable authority
is `python3 tools/release_gate.py`; this document explains what that gate proves
and what still requires a human decision.

## Automated, blocking

- [ ] Every package named by `externals.json` exists as a sibling checkout and
      its `package.json` passes the published JSON Schema plus the stricter
      semantic checks in `tools/build_packages.py`.
- [ ] Package names, versions, skills, capabilities, runtime requirements,
      configuration files, authorship, and all three adapter declarations are
      internally coherent.
- [ ] The committed Claude marketplace is data-equivalent to the
      catalog generated from the canonical package manifests. No hand-edited or
      stale entry may ship.
- [ ] The complete test suite passes. Environment-dependent host-CLI tests may
      skip only when that CLI is unavailable; the human installation checks
      below remain blocking. Tests cover CLI
      behavior, package construction, runtime dependency declarations, generated
      artifacts, organisation policy, and bundled solver scripts.
- [ ] No tracked `.DS_Store`, bytecode, cache, secret-shaped environment file,
      or generated `dist/` artifact is present.
- [ ] Every JSON document in the release surface parses.

## Human, blocking

- [ ] Each changed package has an intentional SemVer decision. User-visible
      changes are described in that package's changelog or release notes.
- [ ] Capability descriptions state what the skill does and its limits; they do
      not claim certification, correctness, or authority the runtime cannot
      prove.
- [ ] Runtime dependencies are minimal, version-bounded, and exactly declared.
- [ ] Licensing and authorship are correct in every source repository.
- [ ] The release commit contains only reviewed source and regenerated metadata.
- [ ] Installation is smoke-tested once on Claude, Codex, and a generic host
      from the artifacts produced by that exact commit.

## Release command

```bash
python3 tools/release_gate.py
python3 tools/build_packages.py --target all
git diff --exit-code
```

The final `git diff` must be empty: generation during the release must reproduce
the committed marketplace exactly.
