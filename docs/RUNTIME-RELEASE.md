<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->

# Runtime release and verification

## Trust model

The manually dispatched `runtime-release` workflow builds six Python 3.12
artifacts: Linux x86-64/ARM64, macOS Intel/ARM64 and Windows x86-64/ARM64. It
accepts only the 32 Git commits in `runtime/runtime-sources.json` and the wheel
archives allowed by the committed PyPI hash locks.

Each matrix job creates a new Ed25519 key, signs its internal runtime manifest,
deletes the private key and publishes the matching public key beside the ZIP.
GitHub Actions then issues SLSA provenance attestations for the ZIP, checksum,
public key and installer wheel using its short-lived OIDC/Sigstore identity. No
long-lived signing key or repository secret exists. Every bundle also carries a
CycloneDX 1.6 SBOM generated from the signed package names, versions, hashes,
SPDX license expressions and source URLs; GitHub binds that SBOM to the ZIP with
a separate SBOM attestation.

The draft release becomes public only after all six builds, internal
verification and GitHub attestations succeed. The `runtime-release` environment
is the host-owned approval boundary for the final publish job.

## User verification

For release `0.1.0`, download the ZIP, its `.sha256` file, its matching
`-public.pem` file and `loomground_installer-0.4.0-py3-none-any.whl` from the
GitHub release. Verify every downloaded executable input against the repository
and the exact release workflow:

```bash
gh attestation verify loomground-runtime-0.1.0-<platform>-py312.zip \
  --repo flxk1/loomground-plugins \
  --signer-workflow flxk1/loomground-plugins/.github/workflows/runtime-release.yml \
  --source-ref refs/heads/main
gh attestation verify loomground-runtime-0.1.0-<platform>-py312-public.pem \
  --repo flxk1/loomground-plugins \
  --signer-workflow flxk1/loomground-plugins/.github/workflows/runtime-release.yml \
  --source-ref refs/heads/main
gh attestation verify loomground_installer-0.4.0-py3-none-any.whl \
  --repo flxk1/loomground-plugins \
  --signer-workflow flxk1/loomground-plugins/.github/workflows/runtime-release.yml \
  --source-ref refs/heads/main
```

Verify the checksum, extract the ZIP and keep the Python 3.12 environment: the
installed runtime launcher deliberately uses that interpreter.

```bash
shasum -a 256 -c loomground-runtime-0.1.0-<platform>-py312.sha256
unzip loomground-runtime-0.1.0-<platform>-py312.zip -d runtime-bundle
python3.12 -m venv "$HOME/.local/share/loomground/python312"
"$HOME/.local/share/loomground/python312/bin/pip" install \
  --no-index --find-links runtime-bundle/wheels \
  ./loomground_installer-0.4.0-py3-none-any.whl
"$HOME/.local/share/loomground/python312/bin/loomground" runtime install runtime-bundle \
  --public-key loomground-runtime-0.1.0-<platform>-py312-public.pem \
  --destination "$HOME/.local/share/loomground/runtime"
```

On Windows, use `py -3.12 -m venv`, the environment's `Scripts\pip.exe` and
`Scripts\loomground.exe`, and an absolute `%LOCALAPPDATA%\Loomground\runtime`
destination. The verification sequence and artifacts are otherwise identical.

The GitHub attestation establishes who built the ZIP and public key. The
internal Ed25519 signature and runtime lock then establish that extraction and
installation still contain the same complete wheel set. Host MCP registration
is a separate explicit adapter step.

## Release operation

From the repository's Actions page, run `runtime-release` on `main` with the
exact `loomground-mcp` version. The workflow creates a draft tag
`loomground-runtime-v<version>`, uploads only attested assets and publishes only
after the complete matrix succeeds. A failed run leaves a draft for inspection;
it never publishes a partial platform set.
