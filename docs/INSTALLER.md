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
canonical SPDX license expression plus source provenance. The lock must contain
`loomground-mcp`; its entry point is fixed to `loomground_mcp.server:main`.

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
  "platforms": ["darwin-arm64"],
  "packages": [
    {
      "name": "loomground-mcp",
      "version": "<released-version>",
      "wheel": "<exact-wheel-filename>.whl",
      "sha256": "<64 lowercase hex characters>",
      "license": "Apache-2.0",
      "source": {
        "source": "git",
        "url": "https://github.com/flxk1/loomground-mcp",
        "commit": "<40 lowercase hex characters>"
      }
    }
  ]
}
```

For an offline/manual build, the release key stays outside the repository:

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

The installer verifies the DSSE/Ed25519 envelope, canonical lock, generated
CycloneDX SBOM, complete file set, canonical SPDX licenses, wheel hashes and
wheel Name/Version metadata. It rejects incompatible Python or platform locks.
Installation uses only the signed wheels with
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

## Guided onboarding

`loomground onboard` asks for the signed runtime directory, its independently
attested public key, a new runtime destination, a new onboarding-pack directory,
the target hosts and optional existing agent/skill names. It shows the write
targets and requires confirmation before installation. The non-interactive form
is explicit and suitable for managed deployment:

```bash
loomground onboard \
  --bundle /downloads/loomground-runtime-0.1.0-darwin-arm64-py312 \
  --public-key /downloads/loomground-runtime-0.1.0-darwin-arm64-py312-public.pem \
  --destination /opt/loomground/runtime \
  --output /opt/loomground/onboarding \
  --host claude --host codex --host cursor \
  --maker "Legal Plugin" --maker "Continuous Monitoring" \
  --yes
```

The output contains `onboarding.json`, `NEXT-STEPS.md` and one merge-ready file
plus a full adapter descriptor per selected host. Neither output nor runtime
contains credentials. Existing host files are never opened or changed, and the
output directory must be new, so the user reviews every host merge.

Claude and Codex users then install the `loomground-suite` plugin normally; the
runtime and plugin remain separate trust surfaces. Existing skills and agents
remain installed in their native host and act as Makers: they submit normalized
action intents to Loomground, consume policy/admission decisions, dispatch only
the admitted digest through the credential-owning adapter, then reconcile the
effect and evidence. Naming a Maker in the wizard records this contract; it does
not rewrite or sandbox that external agent. Enforcement is hard only when the
agent has no direct target credential or alternate execution path.

Official GitHub releases do not use a permanent release key. Each platform job
creates a one-artifact Ed25519 key, deletes the private half and publishes the
public half together with GitHub OIDC/Sigstore attestations. Users first verify
the ZIP and public key against the exact workflow identity, then pass that
public key to this installer. See `docs/RUNTIME-RELEASE.md`.

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
