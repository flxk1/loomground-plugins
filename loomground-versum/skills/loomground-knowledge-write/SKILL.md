---
name: loomground-knowledge-write
description: The single write path into a Loomground Versum knowledge graph. Use when an approved local PDF or prepared source record should be added to the graph. Resolves the known-correct citation, computes the canonical URN, checks for duplicates, writes the house-format stub plus a metadata sidecar, and indexes any locally-present PDF into candidate claims. It NEVER fetches binaries from within a session — acquisition and preparation are out-of-band. Domain-general via profiles; the Digital Law Sources corpus is the default target. Standalone, and adoptable by loomground-editorial as its post-approval write router.
---

# loomground-knowledge-write

The one sanctioned way to write into a Loomground Versum graph — the **guard at the
door**. Nothing else writes to the graph; every addition passes the same identity,
dedup, and indexing discipline. Invoke it directly, or let `loomground-editorial` call
it after its Approval Gate.

## How it runs — a deterministic Python pipeline, not an LLM

The work is done by `versum/write.py` (CLI: `python -m versum capture <folder>
--profile <p>`), a **deterministic** pipeline that needs **no model call** on the happy
path: identity → dedup → stub+sidecar → index. This skill is a thin wrapper — it *knows*
to run the pipeline and how to read its report; it does not re-implement the logic.

- **No-LLM by default.** Identity comes from filename patterns (CELEX / arXiv / DOI) and
  PDF metadata; dedup from a content hash and the source registry; claims from the
  deterministic extractor.
- **Ladder, local model first.** Only when deterministic identity resolution bottoms out
  at a bare path-slug does the pipeline consult an optional `resolver` — wired to a
  **local** model first, a hosted model only after. The ladder is injected, never
  imported; if none is wired, the pipeline still runs (path-slug identity).
- **Single doc or whole folder.** `capture_file` admits one source; `capture_folder`
  walks an existing folder and admits everything not already in the registry.
- **Idempotent / auto-on-add.** Re-running after a document is dropped in admits only the
  new one (content-hash dedup). `python -m versum watch <folder>` polls and re-captures
  on any change; on-device, wire it to an OS watcher (launchd / fswatch) or a scheduled
  task for true auto-indexing.
- **Persists on disk.** The whole graph lives in `<folder>/.versum/`
  (`source_registry.csv`, `claims.csv`, `sources.csv`, `fingerprints.json`,
  `concepts.csv`, `semantic_edges.csv`, `stubs/`) and survives across runs; curation
  output is never clobbered.

## When to use

- The editorial pipeline showed sources and the user approved one or more for the graph.
- The user supplies a local PDF or prepared source record to capture.
- The user drops a PDF and says "add this to the knowledge graph / KG / Versum."

Do NOT use it to invent or guess a citation, and do NOT confirm concepts — this skill
writes the provenance + candidate-claim layers only; concept links are curation.

## Inputs

- **source** — an existing local PDF or prepared source-record path. URLs, DOI/CELEX/arXiv
  identifiers, and citation strings are context for resolving identity, but are not accepted as
  paths by `capture_file`; prepare the local record out-of-band before invoking the pipeline.
- **target** — the Versum corpus folder to write into. Default: the Digital Law Sources
  KG inbox. Any folder that has (or should have) a `.versum/` index is valid.
- **profile** — the domain profile (`law-eu` for the legal corpus, `generic` otherwise).
  Determines the URN namespace and the claim vocabulary.

## Steps

1. **Resolve the citation.** Use the known-correct citation from the local record. For a PDF,
   read its metadata / first page. If the user supplied only a URL or identifier, stop and ask
   for a local file or prepared record; never pass it to `capture_file` as though it were a path.
2. **Compute the canonical URN.** Prefer a canonical identifier embedded in the record —
   `urn:dls:celex:...`, `urn:dls:doi:...`, `urn:dls:arxiv:...`. Fall back to a
   path/title slug `urn:<namespace>:source:<slug>`. (The folder indexer uses the slug
   form; a canonical identifier, when known, is authoritative and recorded in the
   sidecar so `generate_index` honours it.)
3. **Dedup.** Check the source registry for a match by URN, by identifier, and by title.
   On a hit, report the existing entry and stop rather than double-writing.
4. **Write the house record.** Create the house-format stub `YYYY-author-title.md` and a
   `.md.metadata.json` sidecar carrying the resolved citation, the canonical URN, the
   verification level, and (if applicable) the `sidecar_canonical` override.
5. **PDF placement — never fetched in-session.** If a PDF is already present locally,
   copy it into the inbox next to the stub. If only a URL/identifier is known, do not invoke
   the write pipeline yet: leave acquisition or preparation to an out-of-band path and resume
   after a local PDF or prepared source record exists.
6. **Index (only what's on disk).** Run `python -m versum index <target> --profile
   <profile>` over the local inbox so any present PDFs get candidate claims and a
   fingerprint. Sources with no local PDF yet stay at the provenance layer until their
   binary arrives. Claims are `verification: candidate`; curation-only axes unspecified.
7. **Report.** Return the URN, the stub path, dedup result, claim count, and the
   fingerprint summary. Note that concept links are pending curation.

## Guardrails

- Provenance is single-history: never rewrite an existing source's URN by hand; a URN
  change is a deliberate sidecar override, cascaded by re-indexing.
- Candidate-only: this skill never confirms axes or mints concepts — that is the
  curation step.
- Domain-agnostic: all vocabulary and the namespace come from the profile; this skill
  hardcodes no domain value.
- No in-session fetching: never pull a PDF (or any binary) over the network from within
  a session — no curl / urllib / web-fetch bypass. Binaries arrive out-of-band only.
- Sit on top of the existing KG, don't duplicate it: where a Digital Law Sources stub /
  sidecar / registry already exists for a source, consume it — reuse its URN and
  sidecar rather than re-minting a parallel provenance record.

## Relationship to loomground-editorial

`loomground-editorial` adopts this skill as the write leg of its output contract: after
the Approval Gate, approved sources are handed here. It is also fully usable on its own,
independent of the editorial pipeline.
