<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->

# Loomground Suite

`loomground-suite` is the single host-facing entry point for the public
Loomground family. It installs one control skill and registers one
`loomground-mcp` server. The server exposes the pinned family catalogue, 26
skill bodies and 55 plane functions.

It does not recursively install 13 plugin cards or clone 30+ repositories.
That would duplicate source and let package versions drift. The runtime consumes
the family at release pins; `loomground_catalogue`, `loomground_releases` and
`loomground_skill` expose the resolved map to the host.

## Current installation

Claude Code:

```text
/plugin marketplace add flxk1/loomground-plugins
/plugin install loomground-suite@loomground
```

Codex from a checkout of this repository:

```bash
codex plugin marketplace add /absolute/path/to/loomground-plugins
codex plugin add loomground-suite@loomground
```

Start a new task after installation so the host discovers the new skill and MCP
server.

The current plugin assumes that the `loomground-mcp` executable is already on
`PATH`. Run `loomground doctor --host claude` or `--host codex` before relying
on it. The public planes are not all released on a package index, so the
repository does not offer an unpinned network bootstrap. A plugin installation
that succeeds while `loomground-mcp` is absent has installed the interface, not
the executable runtime.

## External skills and agents

A Legal, continuous-monitoring or department-operations plugin remains the
maker. It can use its own prompts, data sources and domain tools. Before a
privileged effect, it emits an action intent matching
`plugins/loomground-suite/schemas/action-intent.schema.json`.

The Loomground control path is:

```text
maker intent
  -> policy/privacy/lane/drift preflight
  -> A2A plan and admission preview
  -> host enforcement adapter
  -> external effect
  -> effect receipt and reconciliation
  -> evidence/certification, when explicitly produced
```

The enforcement adapter must own the only credential or transport capable of
the effect. It checks an expiring, single-use decision against the exact action
and policy digests immediately before acting. A maker with another route to the
API can bypass Loomground; that deployment is advisory, not enforced.

Determinism applies to canonical inputs, pinned component versions, policy
digests, pure plane evaluations and receipt verification. It does not make LLM
prose deterministic. Free-form model output is input to the control path, never
the authorization token.

## Policy graph is not policy activation

Ingesting a policy into Versum records claims, source spans, provenance and a
queryable graph. It does not activate or enforce the policy. Real-time
enforcement additionally requires an authorized activation record for one
immutable compiled policy digest, a policy-decision check on every governed
action, and an enforcement adapter that exclusively owns the action transport.

A policy update creates a new digest. It must invalidate or re-evaluate affected
leases before later effects; an old admission cannot silently inherit the new
policy. Continuous monitoring supplies events and drift readings, but the same
action boundary still performs the final check. Without that boundary, graph
and monitoring results are advisory signals.

## One-install completion boundary

A genuine self-contained installation additionally requires a signed runtime
artifact containing `loomground-mcp` and every first-party wheel at the release
pins, plus a host adapter that installs or selects that artifact transactionally.
Until that artifact exists, the suite is a normal plugin installation for its
skill and MCP registration, but not a self-contained runtime installation.

The committed enforcement-receipt schema is the target host boundary. The
current MCP functions plan, evaluate and preview; they do not mint production
authorization receipts and do not perform maker actions.
