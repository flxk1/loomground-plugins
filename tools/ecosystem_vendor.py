#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Re-vendor the pinned upstream artifacts under ecosystem/vendor/.

Three artifacts are vendored at the commits pinned in ecosystem/manifest.json:

  ecosystem/vendor/catalogue.json               -- byte copy of the "loomground"
                                                    repository's CATALOGUE.json
  ecosystem/vendor/a2a-compliance-roles/*.json   -- byte copies of the eight
                                                    a2a-compliance role manifests
  ecosystem/vendor/skills-index.json             -- the PUBLIC projection of
                                                    loomground-mcp's
                                                    src/loomground_mcp/skills/index.json:
                                                    every record whose repository is
                                                    private, or outside the 41-repo
                                                    ecosystem/manifest.json inventory,
                                                    is dropped before it is written.

ecosystem/vendor/PINS.json documents the source repository and path for each
vendored artifact; this tool is its only writer.

A Fetcher is any callable `fetch(repo: str, commit: str, path: str) -> bytes`.
The default fetcher reads raw.githubusercontent.com; tests inject a fixture
fetcher so the suite runs fully offline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ecosystem_certify  # noqa: E402
import ecosystem_parity_matrix as parity  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "ecosystem/manifest.json"
RUNTIME_SOURCES_PATH = ROOT / "runtime/runtime-sources.json"
VENDOR_DIR = ROOT / "ecosystem/vendor"
CATALOGUE_PATH = VENDOR_DIR / "catalogue.json"
SKILLS_INDEX_PATH = VENDOR_DIR / "skills-index.json"
ROLES_DIR = VENDOR_DIR / "a2a-compliance-roles"
PINS_PATH = VENDOR_DIR / "PINS.json"

OWNER = "flxk1"
CATALOGUE_SOURCE_REPO = "loomground"
CATALOGUE_SOURCE_PATH = "CATALOGUE.json"
SKILLS_INDEX_SOURCE_REPO = "loomground-mcp"
SKILLS_INDEX_SOURCE_PATH = "src/loomground_mcp/skills/index.json"
ROLES_SOURCE_REPO = "a2a-compliance"
ROLES_SOURCE_DIR = "a2a_compliance/roles"
ROLE_IDS = parity.ROLE_IDS

Fetcher = Callable[[str, str, str], bytes]


class VendorError(ValueError):
    pass


def canonical_json_bytes(value: object) -> bytes:
    return ecosystem_certify.canonical_json(value)


def pretty_json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class GitHubRawFetcher:
    """Default online fetcher: raw.githubusercontent.com at an exact commit."""

    def __init__(self, owner: str = OWNER, timeout: float = 20.0) -> None:
        self.owner = owner
        self.timeout = timeout

    def __call__(self, repo: str, commit: str, path: str) -> bytes:
        url = f"https://raw.githubusercontent.com/{self.owner}/{repo}/{commit}/{path}"
        request = urllib.request.Request(url, headers={"User-Agent": "ecosystem-vendor"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                return response.read()
        except OSError as exc:
            raise VendorError(f"failed to fetch {self.owner}/{repo}@{commit}:{path}: {exc}") from exc


def load_manifest() -> dict:
    return ecosystem_certify.validate_manifest(
        ecosystem_certify.load_json(MANIFEST_PATH),
        ecosystem_certify.load_json(RUNTIME_SOURCES_PATH),
    )


def manifest_names(manifest: dict) -> set[str]:
    return {repo["name"] for repo in manifest["repositories"]}


def manifest_pin(manifest: dict, repo_name: str) -> str:
    return parity.manifest_pin(manifest, repo_name)


def fetch_json(fetcher: Fetcher, repo: str, commit: str, path: str) -> object:
    return _parse_json(fetcher(repo, commit, path), repo, commit, path)


def _parse_json(raw: bytes, repo: str, commit: str, path: str) -> object:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VendorError(f"{repo}:{path}@{commit} is not valid JSON: {exc}") from exc


def build_catalogue_artifact(manifest: dict, fetcher: Fetcher) -> bytes:
    commit = manifest_pin(manifest, CATALOGUE_SOURCE_REPO)
    raw = fetcher(CATALOGUE_SOURCE_REPO, commit, CATALOGUE_SOURCE_PATH)
    document = _parse_json(raw, CATALOGUE_SOURCE_REPO, commit, CATALOGUE_SOURCE_PATH)
    if document.get("family") != "Loomground" or not isinstance(document.get("repos"), list):
        raise VendorError("fetched catalogue.json has an unexpected shape")
    return raw  # byte copy: validated, never re-serialised


def build_role_artifacts(manifest: dict, fetcher: Fetcher) -> dict[str, bytes]:
    commit = manifest_pin(manifest, ROLES_SOURCE_REPO)
    artifacts = {}
    for role_id in ROLE_IDS:
        path = f"{ROLES_SOURCE_DIR}/{role_id}.json"
        raw = fetcher(ROLES_SOURCE_REPO, commit, path)
        document = _parse_json(raw, ROLES_SOURCE_REPO, commit, path)
        if document.get("id") != role_id or not isinstance(document.get("allowed_capabilities"), list):
            raise VendorError(f"fetched role manifest is malformed: {role_id}")
        artifacts[f"{role_id}.json"] = raw  # byte copy: validated, never re-serialised
    return artifacts


def public_projection(entries: Iterable[dict], names: set[str]) -> list[dict]:
    projected = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("repo"), str):
            raise VendorError("upstream skills index entry is missing repo")
        if entry.get("private", False):
            continue
        if entry["repo"] not in names:
            continue
        projected.append(entry)
    projected.sort(key=lambda entry: (entry["repo"], entry.get("name", "")))
    return projected


def build_skills_index_artifact(manifest: dict, fetcher: Fetcher) -> bytes:
    commit = manifest_pin(manifest, SKILLS_INDEX_SOURCE_REPO)
    document = fetch_json(fetcher, SKILLS_INDEX_SOURCE_REPO, commit, SKILLS_INDEX_SOURCE_PATH)
    if not isinstance(document, list):
        raise VendorError("upstream skills index must be a JSON array")
    projected = public_projection(document, manifest_names(manifest))
    for entry in projected:
        if entry.get("private"):
            raise VendorError("public projection retained a private entry")
        if entry["repo"] not in manifest_names(manifest):
            raise VendorError("public projection retained an out-of-inventory entry")
    return pretty_json_bytes(projected)


def build_pins_document() -> bytes:
    document = {
        "schema_version": 1,
        "sources": [
            {
                "vendored_path": "ecosystem/vendor/catalogue.json",
                "source_repo": CATALOGUE_SOURCE_REPO,
                "source_path": CATALOGUE_SOURCE_PATH,
                "note": (
                    "source_commit is not repeated here; it is read from "
                    "ecosystem/manifest.json's own revision pin for source_repo, "
                    "which is already validated by ecosystem_certify.validate_manifest. "
                    "Duplicating the commit here would create a second pin to drift "
                    "out of sync."
                ),
            },
            {
                "vendored_path": "ecosystem/vendor/skills-index.json",
                "source_repo": SKILLS_INDEX_SOURCE_REPO,
                "source_path": SKILLS_INDEX_SOURCE_PATH,
                "note": (
                    "NOT a byte-for-byte copy of the upstream file: the upstream index "
                    "also carries skill records for private repositories outside the 41 "
                    "public ecosystem/manifest.json inventory. Vendoring those into this "
                    "public repository would leak private-repo names, descriptions, paths, "
                    "commit SHAs, and blob URLs. This file is the public projection at the "
                    "pinned commit: every record marked private, or whose repo is outside "
                    "the 41-repo inventory, is dropped before it is committed here, not "
                    "merely filtered downstream. tests/test_ecosystem_parity_matrix.py "
                    "asserts zero such records remain and that no known private repo name "
                    "appears anywhere under ecosystem/vendor/."
                ),
            },
            {
                "vendored_path": "ecosystem/vendor/a2a-compliance-roles/*.json",
                "source_repo": ROLES_SOURCE_REPO,
                "source_path": f"{ROLES_SOURCE_DIR}/*.json",
                "note": "eight role manifests, copied verbatim.",
            },
        ],
    }
    return pretty_json_bytes(document)


def build_artifacts(manifest: dict, fetcher: Fetcher) -> dict[Path, bytes]:
    artifacts: dict[Path, bytes] = {
        CATALOGUE_PATH: build_catalogue_artifact(manifest, fetcher),
        SKILLS_INDEX_PATH: build_skills_index_artifact(manifest, fetcher),
        PINS_PATH: build_pins_document(),
    }
    for filename, content in build_role_artifacts(manifest, fetcher).items():
        artifacts[ROLES_DIR / filename] = content
    return artifacts


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def run(fetcher: Fetcher, check: bool) -> int:
    try:
        manifest = load_manifest()
        artifacts = build_artifacts(manifest, fetcher)
    except (VendorError, ecosystem_certify.CertificationError) as exc:
        print(f"ECOSYSTEM VENDOR FAIL: {exc}")
        return 1

    if check:
        stale = []
        for path, content in sorted(artifacts.items()):
            if not path.is_file():
                stale.append(f"{_display(path)} (missing)")
                continue
            if sha256_bytes(path.read_bytes()) != sha256_bytes(content):
                stale.append(f"{_display(path)} (sha256 mismatch)")
        extra_roles = sorted(
            path.name for path in ROLES_DIR.glob("*.json")
            if (ROLES_DIR / path.name) not in artifacts
        ) if ROLES_DIR.is_dir() else []
        if extra_roles:
            stale.append(f"unexpected role files present: {extra_roles}")
        if stale:
            print("ECOSYSTEM VENDOR CHECK FAIL: " + "; ".join(stale))
            return 1
        print(f"ECOSYSTEM VENDOR CHECK PASS: {len(artifacts)} artifacts current")
        return 0

    for path, content in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    # Remove role files that are no longer part of the pinned role set.
    if ROLES_DIR.is_dir():
        for existing in ROLES_DIR.glob("*.json"):
            if existing not in artifacts:
                existing.unlink()
    print(f"ECOSYSTEM VENDOR GENERATED: {len(artifacts)} artifacts")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare sha256 against pinned upstream without writing")
    args = parser.parse_args()
    return run(GitHubRawFetcher(), args.check)


if __name__ == "__main__":
    raise SystemExit(main())
