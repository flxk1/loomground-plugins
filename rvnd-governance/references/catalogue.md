# RVND catalogue — discovery and the live operation surface

The skills speak in ten canonical verbs (see `protocol.md`). This file maps those verbs onto the
operations the RVND server actually exposes, and — more importantly — tells you how to read the
live surface instead of trusting this table. **Discovery over memorisation:** the server's current
tool list is ground truth; this document is a convenience that can drift.

## Discover first

RVND is a governance MCP server. Before driving it, read what it exposes:

1. Read the host's live MCP tool list for the RVND server (`mcp/rvnd.mcp.json` names the server).
   Use the tool names the host reports, not the names written here.
2. Many governance reads and writes go through a single **workflow facade** shaped as
   `{"op": "<operation>", "params": {...}}`. Discover the available `op` values by asking the
   governance interface itself — `governance_chat` can answer "what operations are available for
   this folder" — rather than hardcoding a list.
3. If an operation this plugin references is not present, it is unavailable. Do not emulate it
   locally. Fail closed and say what is missing.

The server may also publish a discovery resource (a catalogue). If your host exposes RVND
resources, read the catalogue resource for the authoritative, versioned surface. If it does not,
fall back to the live tool list plus `governance_chat` discovery above.

## Verb → live operation (as of RVND beta, 2026-07)

These are the real operations named in the RVND server. Treat versions (`/v1`) as part of the
contract and re-check them at discovery time.

**query** — read governed state, all read-only:
- `governance_chat` — answer a governance question, ingest policy text for review, or complete a
  use-case card.
- `governance_map` (`governance_map/v1`) — rules by role, step, and risk.
- `governance_kg` (`governance_kg/v1`) — the same rules as a graph with reasoning paths.
- `loop_graph` (`rvnd/graph-of-loops/v1`) — how execution, oversight, drift, recovery, and policy
  improvement watch or veto one another; reads counts from the signed chain.
- `security_dashboard` (`security/v1`) — security decisions and known limitations.
- `model_capability` — whether the configured local model is available and how the system
  degrades without it.
- `governance_lane_list` — the latest lane per agent.

**propose** — build a request; nothing takes effect here:
- Draft a `governance_lane_register` envelope (a new or widened lane) — hold it as a proposal.
- Draft a policy import via `governance_chat` (policy text in, governance graph out for review).

**validate** — server evaluates the proposal against the lane and rules:
- The action gate runs when a governed action is attempted against a lane; every live action is
  checked against all constrained dimensions (authority, autonomy grade, action class, footprint,
  connectors, policy fingerprint).
- `officer` — preview changes that tighten oversight before they apply.

**apply** — commit through the server:
- `governance_lane_register` (with `approved_by` + `rationale`) — register or version a lane.
  Widening requires a new lane version with a named approver and rationale.
- Policy import confirmation — policy imports require human confirmation before they apply.

**operate** — a live governed action, checked against the lane each time it runs. An agent may
request its assigned grade or a lower one, never a higher one.

**decide / hold** — oversight sign-off and stops:
- Oversight checks each action against the lowest autonomy limit set by the applicable rules and
  against a time-based stop. A task reserved for a person cannot run automatically. Route the
  human approve/hold/deny through the oversight surface the server exposes.

**revoke** — withdraw or erase:
- Erasure is performed with **signed tombstones**: it purges this folder's record and blocks
  re-ingestion. Supersede a lane by registering a narrower version.

**transfer** — custody handoff:
- Environment-level **sessions** (`.rvnd` bundles) carry a governed scope between contexts;
  custody adapters record the handoff. Cross-machine continue is same-key only.

**verify** — audit:
- The per-folder Ed25519-signed hash chain is the source of truth. Verify a receipt against the
  chain; render the signing key and the cited rule.

## Governance controls behind the operations

The server routes compiled policy to concrete controls, and reads/verdicts reflect them:
- Authority → execution.
- Autonomy ceilings and reserved acts → oversight.
- Prohibitions → the recovery breaker.
- Signed configuration → drift monitoring.

`control_bindings` (in `loop_graph`) shows where the compiled policy acts. The projection
distributes controls already compiled into the governance graph; it does not infer new meaning.

## What is NOT on the surface

- There is no host-side verdict. The host never computes allow/hold/deny.
- There are no dials or scores to render — verdicts are discrete lamps.
- There is no way to grant more than the lane allows by asking differently. A grade increase is a
  denial unless it is a new approved lane version.
- Air-gapped folders build no network request; a cloud endpoint is excluded from their governance
  paths. Do not route their work to a cloud model.
