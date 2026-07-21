# Loomground skills — quality & distribution plan

*Recommendations to bring the loomground skills to current skill-platform best practice, keep them cross-platform, and distribute them. 2026-07-20.*

## Quality improvements

The reliability foundations are already strong (deterministic engine, fail-closed, explicit boundaries, human-gating, replayable output — the predictability most skills lack). Four gaps remain against current Agent-Skills best practice:

1. **Progressive disclosure.** Split each monolithic SKILL.md into a lean core (trigger + workflow + when-to-use) plus `references/*.md` loaded only when needed. This is the biggest quality delta.
2. **Trim descriptions.** The `description` frontmatter loads into the system prompt globally on every session — keep it concise and trigger-rich, not paragraph-length.
3. **Bundled evals.** Add a small Problem Set + behaviour test per skill (fixtures with known-good outcomes). This is both an Anthropic best practice ("start with evaluation") and a buyer quality signal.
4. **Restore `references/` provenance + eval records** per skill (the pattern the source packages carried).

## Cross-platform (broader than Claude) — Q1

The plan holds, because the packaging is already multi-target: each `package.json` declares `adapters.{claude, codex, generic}`, and `build_packages.py` emits `dist/claude` (`.claude-plugin/plugin.json`), `dist/codex` (`.codex-plugin/plugin.json` + interface), and `dist/generic` (INSTALL.md). All four quality improvements are platform-neutral: SKILL.md + references, lean descriptions, and evals carry across every target. Rules to stay broad:

- Keep SKILL.md free of Claude-isms; the logic lives in the engine CLI, which is platform-agnostic. Per-platform triggers live in the adapter files (`agents/openai.yaml`, the plugin manifests), not in SKILL.md.
- Broadest reach of all: expose the `versum` and `loomground_solver` engines as an **MCP server**. Then any MCP-capable agent (not only skill-supporting hosts) can use them — the skills become one front-end among several.

## Distribution (open-core) — Q2

Split, don't pick one. The engines are the moat; the solver kernel is already Apache-2.0 (permissive — commercial layers on top are allowed, and you own all the skill IP).

- **Free / open loomground repos (Apache-2.0):** the engines + the analytic solver skills (opponent-modeler, probability-tracker, strategic-analysis, estimate-liability, litigation-risk-assessor, analyse-risks) + the versum/KG/mental-model skills. These are general-purpose and are the adoption funnel and discoverability surface.
- **RVND (commercial licence):** the governance rule-reasoning skills (extract-policy-norms, compile-loomground-policy, reason-governance-rules, resolve-rule-conflicts) + the governance-layer pairs (policy-gate, bind-policy, audit, escalation, refresh) + the legal/compliance verticals. This is the high-stakes, enterprise-paying segment and the lead source. Open-core: free tier for reach, commercial governance premium for revenue and qualified leads.

**Implication:** to distribute this way, the governance lobe should separate from the analytic lobe — either split the governance skills out of `loomground-solver` into an RVND-licensed package (e.g. `loomground-governance` / `rvnd-governance`), or dual-license one plugin (analytic Apache, governance commercial). This revisits the earlier "governance skills belong to a solver plugin" call: architecturally one solver, but commercially the governance lobe wants its own licence boundary.
