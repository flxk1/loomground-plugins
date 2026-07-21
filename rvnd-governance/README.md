# rvnd-governance

The RVND governance layer as skills: how an AI host drives the **RVND governance MCP server**
safely. RVND (reeve + nD) is a local-first governance system that sits between an agent and what it
acts on and decides what may happen. These skills do not decide anything — **the server decides and
the host renders** — they teach the host the discipline that keeps a request from ever being shown
as a grant.

## The cycle

Every consequential interaction runs one loop: **discover → query → propose → validate → preview →
confirm → apply → display**. Reads grant nothing; writes are fail-closed. The one rule the whole
plugin exists to enforce: never present requested state as granted.

The shared contract lives in `references/protocol.md` (the eight steps, identity resolution,
tightening vs loosening, Sign routing) and `references/catalogue.md` (the ten canonical verbs
mapped onto the server's real operations, and how to discover the live tool surface instead of
hardcoding it).

## Grounding

A skill is grounded in Loomground only when it produces or consumes typed governance objects — not
when it merely prompts a model to "apply governance". The spine of that is the typed **proposal
envelope** (`schemas/proposal.schema.json`): the skill assembles intent, scope, and runtime
bindings and asks RVND to generate and validate the Loomground constructs; it never writes `.lg`.
Every governance meaning is either a real construct or a visible **residual** — nothing in between
is invented. `references/grounding.md` sets out the six grounding links (source, object, language,
runtime, evidence, version) and the residual ledger; `references/vocabulary.md` pins the real
`loomground-language` **0.8.0a1** constructs the skills are allowed to handle; `references/corpus.md`
is the acceptance corpus, headed by the equivalence test (chat / CLI / sheet / `.lg` → one canonical
observation). Each skill carries a `manifest.yaml` declaring the constructs it may read and propose.

## The five skills

- **rvnd-govern** — the core cycle: put a consequential action through query → validate → confirm
  → apply → display.
- **rvnd-decide** — the human oversight sign-off: approve / hold / deny, with the named approver
  and rationale a loosening needs.
- **rvnd-audit** — verify a receipt against the per-folder Ed25519-signed hash chain; attributed,
  not asserted; honest about the chain's limits.
- **rvnd-incident** — freeze, revoke (signed tombstone), seal to air-gap, or transfer custody;
  tightening is immediate, loosening back needs approval.
- **rvnd-build-surface** — compose and lint the MCP App surface (the five cards) so a built surface
  cannot show a request as a grant. The one skill that drives no server.

## Structure

- `mcp/` — how to connect the RVND governance server (`rvnd.mcp.json`). RVND runs locally; this
  plugin names it, it does not ship it.
- `apps/` — the five MCP App card specs: context, proposal, patch, decision, receipt.
- `schemas/` — the surface-card and composition schemas the linter enforces.
- `references/` — the shared protocol and catalogue.
- `skills/` — the five composable skills, each lean SKILL.md + references/ pair.

## Relationship to the kernel

This is **not** a set of kernel wrappers. It drives the RVND server, which is itself built on the
Loomground language and the `loomground-solver` kernel. RVND supplies the policy, corpus, custody
and audit adapters; the Solver has no RVND dependency. (The previous 0.1.x version of this plugin
wrapped the kernel directly — a mis-layering — and is superseded by this MCP-driver design.)

## Licence

The commercial (RVND) tier of the open-core split. RVND itself is source-available: non-commercial
use under the Rvnd Research and Community Licence, commercial use under a separate paid licence.
These driver skills are distributed as the RVND tier, distinct from the Apache-2.0 loomground
engines and free skills. Set the licence deliberately before distribution.
