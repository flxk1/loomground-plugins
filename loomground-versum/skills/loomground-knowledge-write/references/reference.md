# loomground-knowledge-write - reference

## How it runs — wraps the versum/write.py pipeline, never re-implements it

The work is `versum/write.py` (CLI: `python -m versum capture <folder> --profile <p>`),
a deterministic pipeline that needs no model call on the happy path: identity, dedup,
stub+sidecar, index. This skill knows to run the pipeline and how to read its report;
it does not re-implement the logic.

## Inputs

- **source** — an existing local PDF or prepared source-record path.
- **target** — the Versum corpus folder to write into.
- **profile** — the domain profile (`law-eu`, `generic`).

## What it returns

- **urn** — the canonical URN assigned to the source.
- **stub_path** — path to the created house-format stub.
- **dedup_result** — whether a duplicate was found.
- **claim_count** — number of candidate claims extracted.
- **fingerprint** — the source's 5D+nD fingerprint summary.

## Guardrails

- **No in-session fetch.** Never pulls a PDF over the network; binaries arrive out-of-band.
- **Provenance is single-history.** Never rewrites an existing source's URN by hand.
- **Candidate-only.** Never confirms axes or mints concepts — that is the curation step.
- **Domain-agnostic.** All vocabulary and namespace come from the profile.
- **Sit on top, don't duplicate.** Reuses existing stubs/sidecars rather than re-minting.

## Pairing

Adopted by `loomground-editorial` as the write leg of its output contract. Also usable
standalone. Placement decisions come from `loomground-organise`.
