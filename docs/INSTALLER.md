<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->

# Loomground installer contract

The `loomground` command separates read-only planning and adapter rendering from
explicit signed-bundle installation. `plan`, `doctor` and `adapter` do not
change host state. Profile and runtime installs require an explicit absolute
destination and independently obtained Ed25519 public key.

```bash
python3 -m pip install .
loomground plan --profile compliance --host auto
loomground doctor --host auto
```

Profiles select task-level plugins, not separate copies of their runtime
dependencies:

- `compliance` (default): A2A Compliance, policy, evidence, privacy,
  governance and solver.
- `core`: language planes, governance, ingest and solver.
- `knowledge`: ingest, Versum, factual/epistemic language and solver.
- `full`: all 13 marketplace plugins.

## Signed bundles and transactional installation

A release operator builds a profile bundle with an Ed25519 key supplied from
outside the repository:

```bash
python3 tools/build_profile_bundle.py \
  --profile compliance --target codex \
  --output /absolute/path/loomground-compliance \
  --signing-key /secure/path/release-private.pem \
  --key-id loomground-release-2026
```

The private key is neither generated nor stored by the builder. A user obtains
the trusted public key through an independent release channel, verifies the
bundle, and chooses an explicit installation destination:

```bash
loomground bundle verify /path/to/bundle --public-key /path/to/release-public.pem
loomground bundle install /path/to/bundle \
  --public-key /path/to/release-public.pem \
  --destination /absolute/path/chosen/by/user
```

Installation verifies the DSSE/Ed25519 signature, every file path, the complete
file set, byte sizes and SHA-256 digests before staging. It then swaps the staged
tree atomically. An existing destination is retained as a uniquely named sibling
backup. Reinstalling the same digest is a no-op. Rollback also verifies the
backup before swapping it back:

```bash
loomground bundle rollback \
  --destination /absolute/path/chosen/by/user \
  --backup /absolute/path/.chosen.by.user.loomground-backup-… \
  --public-key /path/to/release-public.pem
```

Safety invariants:

1. `plan` and `doctor` never write files or run discovered executables.
2. Bundle installation writes only below an explicit absolute destination and
   its existing parent; it never edits host configuration.
3. Signature and content verification finish before staging or replacement.
4. Existing installs are retained for rollback; failed replacement restores
   the original tree.
5. The reported enforcement mode is always `advisory`.
6. Missing published runtime distributions are reported as blockers, not
   replaced with mutable installs from repository heads.
7. No approval, dispatch or host permission is requested.

This installs a verified skill/profile tree, not the Loomground runtime and not
host registration. Those remain separate until a signed runtime artifact and
host-specific configuration adapters have their own rollback-tested contracts.

## Signed offline runtime

Release builders assemble already-built wheels under one lock. Every lock entry
contains the distribution name, version, wheel filename, SHA-256 digest and
source provenance. The lock must contain `loomground-mcp`; its entry point is
fixed to `loomground_mcp.server:main`.

Releases publish a signed bundle for each required OS/architecture and Python
compatibility range. A pure-Python `any` bundle may cover multiple systems;
platform-specific wheels must be locked in separate compatible bundles. The
installer selects nothing dynamically and rejects a non-matching bundle.

```json
{
  "schema_version": 1,
  "runtime": {
    "name": "loomground-mcp",
    "version": "<released-version>",
    "entry_point": "loomground_mcp.server:main"
  },
  "python": {
    "minimum": [3, 11],
    "maximum_exclusive": [3, 15]
  },
  "platforms": ["macosx-15.0-arm64"],
  "packages": [
    {
      "name": "loomground-mcp",
      "version": "<released-version>",
      "wheel": "<exact-wheel-filename>.whl",
      "sha256": "<64 lowercase hex characters>",
      "source": {
        "source": "git",
        "url": "https://github.com/flxk1/loomground-mcp",
        "commit": "<40 lowercase hex characters>"
      }
    }
  ]
}
```

The release key stays outside the repository:

```bash
python3 tools/build_runtime_bundle.py \
  --lock /path/to/runtime-lock.json \
  --wheelhouse /path/to/wheelhouse \
  --output /absolute/path/loomground-runtime \
  --signing-key /secure/path/release-private.pem \
  --key-id loomground-runtime-2026 \
  --verify-with /independent/path/release-public.pem
```

Users verify and install without an index or repository checkout:

```bash
loomground runtime verify /path/to/loomground-runtime \
  --public-key /path/to/release-public.pem
loomground runtime install /path/to/loomground-runtime \
  --public-key /path/to/release-public.pem \
  --destination /absolute/path/loomground-runtime
```

The installer verifies the DSSE/Ed25519 envelope, canonical lock, complete file
set, wheel hashes and wheel Name/Version metadata. It rejects incompatible
Python or platform locks. Installation uses only the signed wheels with
`pip --no-index --no-deps` below an adjacent staging directory. It probes
`loomground_mcp.server:main`, writes a relative launcher, then atomically swaps
the stage into place. The prior install remains an absolute sibling backup:

```bash
loomground runtime rollback \
  --destination /absolute/path/loomground-runtime \
  --backup /absolute/path/.loomground-runtime.loomground-runtime-backup-… \
  --public-key /path/to/release-public.pem
```

The executable is `<destination>/bin/loomground-mcp`. Host registration remains
separate so installing a runtime cannot silently edit Codex or Claude settings.
No production runtime artifact or release trust key is committed here.

## Host adapters

`loomground adapter` renders registration material to stdout and never changes a
host file. Local Claude, Codex, Cursor and generic MCP clients point at the
absolute launcher installed above. Remote OpenAI clients and n8n point at an
already-running authenticated HTTP/SSE service:

```bash
loomground adapter --host cursor \
  --runtime-destination /absolute/path/loomground-runtime

loomground adapter --host openai \
  --server-url https://loomground.example/mcp

loomground adapter --host n8n \
  --server-url https://loomground.example/sse
```

The OpenAI object defaults `require_approval` to `always`. The n8n descriptor
selects only the control-path tools and requires a bearer credential stored by
n8n. Rendered output never includes secret material. Non-loopback remote URLs
must use HTTPS and may not contain URL credentials.

Rendering is deliberately separate from applying: each host owns configuration
merge rules, user consent and credential storage. A future host-specific
transaction may consume the rendered object, but the generic installer must not
overwrite `.mcp.json`, `$CODEX_HOME/config.toml`, `.cursor/mcp.json` or an n8n
workflow database.
