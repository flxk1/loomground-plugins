#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Generate and enforce the ecosystem CI parity matrix.

One row per repository declared in ecosystem/manifest.json (exactly 41), with
four columns derived from the repositories' own authoritative surfaces:

  mcp_tool          -- ecosystem/vendor/catalogue.json (pinned copy of the
                        "loomground" repository's CATALOGUE.json)
  installable_skill -- ecosystem/vendor/skills-index.json, the PUBLIC
                        projection at the loomground-mcp pinned commit: the
                        upstream skills/index.json also carries skill records
                        for repositories outside the 41 public inventory,
                        which are dropped before vendoring so this public
                        repository never carries their names, descriptions,
                        paths, commit SHAs, or blob URLs. It is not a
                        byte-for-byte copy of the upstream file; see
                        ecosystem/vendor/PINS.json. The generator still
                        filters defensively (repo public and in the 41) so a
                        future re-vendor that reintroduces a private record
                        fails closed instead of silently leaking again.
  plugin_source     -- .claude-plugin/marketplace.json, this repository's own
                        committed, release_gate-enforced marketplace manifest
  agent_role        -- ecosystem/vendor/a2a-compliance-roles/*.json (pinned
                        copies of the eight a2a-compliance role manifests),
                        resolved through the same catalogue.json tool/skill
                        declarations rather than a second parallel mapping

A blank cell never means "no data was found here" by omission: every cell
carries present/value/reason, and an absent value always carries a reason.
A repository referenced by a source surface but outside the 41, or a
resolution that leaves a repository unassigned or double-assigned, fails
closed rather than silently producing a gap.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ecosystem_certify  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "ecosystem/manifest.json"
RUNTIME_SOURCES_PATH = ROOT / "runtime/runtime-sources.json"
CATALOGUE_PATH = ROOT / "ecosystem/vendor/catalogue.json"
SKILLS_INDEX_PATH = ROOT / "ecosystem/vendor/skills-index.json"
ROLES_DIR = ROOT / "ecosystem/vendor/a2a-compliance-roles"
MARKETPLACE_PATH = ROOT / ".claude-plugin/marketplace.json"
OUTPUT_JSON = ROOT / "ecosystem/parity-matrix.json"
OUTPUT_MD = ROOT / "ecosystem/parity-matrix.md"
SCHEMA_PATH = ROOT / "schemas/parity-matrix.schema.json"

CATALOGUE_SOURCE_REPO = "loomground"
SKILLS_INDEX_SOURCE_REPO = "loomground-mcp"
ROLES_SOURCE_REPO = "a2a-compliance"
ROLE_IDS = (
    "assurance-recorder",
    "conductor",
    "decision-verifier",
    "evidence-grounder",
    "language-panel",
    "oversight-assessor",
    "policy-compiler",
    "runtime-controller",
)
CAPABILITY_KINDS = {"contract", "distribution", "tool", "skill"}


class ParityError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def cell(present: bool, value: object = None, reason: str | None = None) -> dict:
    if present:
        if reason is not None:
            raise ParityError("a present cell must not carry a reason")
        return {"present": True, "value": value, "reason": None}
    if value is not None:
        raise ParityError("an absent cell must not carry a value")
    if not reason:
        raise ParityError("an absent cell must carry a non-empty reason")
    return {"present": False, "value": None, "reason": reason}


def load_manifest() -> dict:
    manifest = ecosystem_certify.validate_manifest(
        ecosystem_certify.load_json(MANIFEST_PATH),
        ecosystem_certify.load_json(RUNTIME_SOURCES_PATH),
    )
    return manifest


def manifest_names(manifest: dict) -> list[str]:
    names = sorted(repo["name"] for repo in manifest["repositories"])
    if len(names) != 41 or len(set(names)) != 41:
        raise ParityError(f"expected exactly 41 uniquely named repositories, found {len(names)}")
    return names


def manifest_pin(manifest: dict, repo_name: str) -> str:
    for repo in manifest["repositories"]:
        if repo["name"] == repo_name:
            return repo["revision"]
    raise ParityError(f"{repo_name} is not declared in ecosystem/manifest.json")


# --- MCP tool -----------------------------------------------------------

def load_catalogue() -> dict:
    catalogue = ecosystem_certify.load_json(CATALOGUE_PATH)
    if catalogue.get("family") != "Loomground" or not isinstance(catalogue.get("repos"), list):
        raise ParityError("vendored catalogue.json has an unexpected shape")
    for entry in catalogue["repos"]:
        if not isinstance(entry.get("repo"), str) or not isinstance(entry.get("tools"), list):
            raise ParityError("vendored catalogue.json entry is missing repo or tools")
        if not isinstance(entry.get("skills"), list):
            raise ParityError("vendored catalogue.json entry is missing skills")
    return catalogue


def catalogue_repo_tools(catalogue: dict, names: list[str]) -> dict[str, list[str]]:
    names_set = set(names)
    cat_repos = [entry["repo"] for entry in catalogue["repos"]]
    if len(cat_repos) != len(set(cat_repos)):
        raise ParityError("vendored catalogue.json repeats a repository")
    if set(cat_repos) != names_set:
        extra = sorted(set(cat_repos) - names_set)
        missing = sorted(names_set - set(cat_repos))
        raise ParityError(f"catalogue.json repositories differ from the ecosystem inventory: extra={extra} missing={missing}")
    return {entry["repo"]: sorted(set(entry["tools"])) for entry in catalogue["repos"]}


def catalogue_repo_skills(catalogue: dict) -> dict[str, list[str]]:
    return {entry["repo"]: sorted(set(entry["skills"])) for entry in catalogue["repos"]}


def mcp_tool_cells(repo_tools: dict[str, list[str]]) -> dict[str, dict]:
    cells = {}
    for name, tools in repo_tools.items():
        if tools:
            cells[name] = cell(True, value=tools)
        else:
            cells[name] = cell(False, reason="no MCP tool is declared for this repository in CATALOGUE.json")
    return cells


# --- installable skill ---------------------------------------------------

def load_skills_index() -> list[dict]:
    entries = ecosystem_certify.load_json(SKILLS_INDEX_PATH)
    if not isinstance(entries, list):
        raise ParityError("vendored skills-index.json must be a list")
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("repo"), str) or not isinstance(entry.get("name"), str):
            raise ParityError("vendored skills-index.json entry is missing repo or name")
    return entries


def installable_skill_cells(entries: list[dict], names: list[str]) -> dict[str, dict]:
    names_set = set(names)
    public_by_repo: dict[str, list[str]] = {name: [] for name in names}
    for entry in entries:
        repo = entry["repo"]
        private = bool(entry.get("private", False))
        if repo not in names_set:
            if not private:
                raise ParityError(f"skills-index.json has a public entry for an unknown repository: {repo}")
            continue
        if private:
            raise ParityError(f"skills-index.json marks a 41-inventory repository private: {repo}")
        public_by_repo[repo].append(entry["name"])
    cells = {}
    for name in names:
        skills = sorted(set(public_by_repo[name]))
        if skills:
            cells[name] = cell(True, value=skills)
        else:
            cells[name] = cell(False, reason="no public installable skill is indexed for this repository in loomground-mcp's skills/index.json")
    return cells


# --- plugin source ---------------------------------------------------

def load_marketplace() -> dict:
    marketplace = ecosystem_certify.load_json(MARKETPLACE_PATH)
    if not isinstance(marketplace.get("plugins"), list):
        raise ParityError("marketplace.json must declare a plugins array")
    return marketplace


def plugin_source_cells(marketplace: dict, names: list[str]) -> dict[str, dict]:
    names_set = set(names)
    pinned: dict[str, dict] = {}
    for entry in marketplace["plugins"]:
        name = entry.get("name")
        source = entry.get("source")
        if not isinstance(source, dict):
            continue  # a repository-local composed plugin (e.g. loomground-suite), not an external repo pin
        if name not in names_set:
            raise ParityError(f"marketplace.json pins an external plugin source outside the ecosystem inventory: {name}")
        pinned[name] = source
    cells = {}
    for name in names:
        if name in pinned:
            cells[name] = cell(True, value=pinned[name])
        else:
            cells[name] = cell(False, reason="not listed as a pinned external plugin source in .claude-plugin/marketplace.json")
    return cells


# --- agent / role ---------------------------------------------------

def load_roles() -> dict[str, dict]:
    roles = {}
    found = sorted(path.stem for path in ROLES_DIR.glob("*.json"))
    if found != sorted(ROLE_IDS):
        raise ParityError(f"expected exactly the eight declared roles, found {found}")
    for role_id in ROLE_IDS:
        role = ecosystem_certify.load_json(ROLES_DIR / f"{role_id}.json")
        if role.get("id") != role_id or not isinstance(role.get("allowed_capabilities"), list):
            raise ParityError(f"vendored role manifest is malformed: {role_id}")
        roles[role_id] = role
    return roles


def build_tool_and_skill_maps(catalogue: dict) -> tuple[dict[str, str], dict[str, set[str]]]:
    tool_to_repo: dict[str, set[str]] = {}
    skill_to_repos: dict[str, set[str]] = {}
    for entry in catalogue["repos"]:
        repo = entry["repo"]
        for tool in entry["tools"]:
            tool_to_repo.setdefault(tool, set()).add(repo)
        for skill in entry["skills"]:
            skill_to_repos.setdefault(skill, set()).add(repo)
    collisions = {tool: sorted(repos) for tool, repos in tool_to_repo.items() if len(repos) > 1}
    if collisions:
        raise ParityError(f"catalogue.json assigns one tool to more than one repository: {collisions}")
    return {tool: next(iter(repos)) for tool, repos in tool_to_repo.items()}, skill_to_repos


def agent_role_cells(roles: dict[str, dict], catalogue: dict, names: list[str]) -> dict[str, dict]:
    names_set = set(names)
    tool_to_repo, skill_to_repos = build_tool_and_skill_maps(catalogue)
    assigned: dict[str, str] = {}
    for role_id, role in roles.items():
        resolved: set[str] = set()
        for capability in role["allowed_capabilities"]:
            kind, sep, value = capability.partition(":")
            if not sep or kind not in CAPABILITY_KINDS:
                raise ParityError(f"role {role_id} declares an unrecognised capability kind: {capability!r}")
            if kind in ("contract", "distribution"):
                if value not in names_set:
                    raise ParityError(f"role {role_id} declares {capability!r} outside the ecosystem inventory")
                resolved.add(value)
            elif kind == "tool":
                repo = tool_to_repo.get(value)
                if repo is not None:
                    resolved.add(repo)
            elif kind == "skill":
                resolved |= skill_to_repos.get(value, set())
        for repo in resolved:
            if repo not in names_set:
                raise ParityError(f"role {role_id} resolves to a repository outside the ecosystem inventory: {repo}")
            if repo in assigned and assigned[repo] != role_id:
                raise ParityError(f"repository {repo} is assigned to more than one role: {assigned[repo]}, {role_id}")
            assigned[repo] = role_id
    if set(assigned) != names_set:
        missing = sorted(names_set - set(assigned))
        extra = sorted(set(assigned) - names_set)
        raise ParityError(f"a2a-compliance roles do not exactly cover the ecosystem inventory: missing={missing} extra={extra}")
    return {name: cell(True, value=assigned[name]) for name in names}


# --- assembly ---------------------------------------------------

def vendor_file_source(source_repo: str, source_path: Path, manifest_repo: str, manifest: dict, vendored_path: str) -> dict:
    return {
        "source_repo": source_repo,
        "source_commit": manifest_pin(manifest, manifest_repo),
        "vendored_path": vendored_path,
        "vendored_sha256": sha256_file(source_path),
    }


def vendor_dir_sha256(directory: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(directory.glob("*.json")):
        hasher.update(path.name.encode())
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def build_matrix() -> dict:
    manifest = load_manifest()
    names = manifest_names(manifest)

    catalogue = load_catalogue()
    repo_tools = catalogue_repo_tools(catalogue, names)
    mcp_cells = mcp_tool_cells(repo_tools)

    skills_index = load_skills_index()
    skill_cells = installable_skill_cells(skills_index, names)

    marketplace = load_marketplace()
    plugin_cells = plugin_source_cells(marketplace, names)

    roles = load_roles()
    role_cells = agent_role_cells(roles, catalogue, names)

    rows = [
        {
            "name": name,
            "mcp_tool": mcp_cells[name],
            "installable_skill": skill_cells[name],
            "plugin_source": plugin_cells[name],
            "agent_role": role_cells[name],
        }
        for name in names
    ]

    sources = {
        "ecosystem_manifest_sha256": sha256_file(MANIFEST_PATH),
        "catalogue": vendor_file_source(
            CATALOGUE_SOURCE_REPO, CATALOGUE_PATH, CATALOGUE_SOURCE_REPO, manifest, "ecosystem/vendor/catalogue.json"
        ),
        "skills_index": vendor_file_source(
            SKILLS_INDEX_SOURCE_REPO, SKILLS_INDEX_PATH, SKILLS_INDEX_SOURCE_REPO, manifest, "ecosystem/vendor/skills-index.json"
        ),
        "roles": {
            "source_repo": ROLES_SOURCE_REPO,
            "source_commit": manifest_pin(manifest, ROLES_SOURCE_REPO),
            "vendored_dir": "ecosystem/vendor/a2a-compliance-roles",
            "vendored_sha256": vendor_dir_sha256(ROLES_DIR),
        },
        "marketplace": {
            "path": ".claude-plugin/marketplace.json",
            "sha256": sha256_file(MARKETPLACE_PATH),
        },
    }

    matrix = {
        "schema_version": 1,
        "kind": "loomground-ecosystem-parity-matrix",
        "row_count": len(rows),
        "sources": sources,
        "rows": rows,
    }
    matrix["matrix_sha256"] = ecosystem_certify.digest(matrix)
    return matrix


def validate_matrix_schema(matrix: dict) -> None:
    schema = ecosystem_certify.load_json(SCHEMA_PATH)
    errors = sorted(Draft202012Validator(schema).iter_errors(matrix), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ParityError(f"parity matrix failed schema validation: {details}")


def render_markdown(matrix: dict) -> str:
    def fmt(field: dict) -> str:
        if field["present"]:
            value = field["value"]
            if isinstance(value, list):
                return ", ".join(value)
            if isinstance(value, dict):
                return value.get("url", value.get("source", str(value)))
            return str(value)
        return f"— ({field['reason']})"

    lines = [
        "<!-- generated by tools/ecosystem_parity_matrix.py; do not hand-edit -->",
        "# Loomground ecosystem CI parity matrix",
        "",
        f"One row per one of the {matrix['row_count']} public repositories declared in "
        "`ecosystem/manifest.json`. `—` marks a repository legitimately absent from that "
        "column, always with a reason; it never means the column was not checked.",
        "",
        "| repository | MCP tool | installable skill | plugin source | agent / role |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in matrix["rows"]:
        lines.append(
            f"| {row['name']} | {fmt(row['mcp_tool'])} | {fmt(row['installable_skill'])} | "
            f"{fmt(row['plugin_source'])} | {fmt(row['agent_role'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="regenerate and diff against the committed artifact; exit non-zero on drift")
    parser.add_argument("--output", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--markdown", type=Path, default=OUTPUT_MD)
    args = parser.parse_args()
    try:
        matrix = build_matrix()
        validate_matrix_schema(matrix)
        payload = ecosystem_certify.canonical_json(matrix) + b"\n"
        markdown = render_markdown(matrix)
        if args.check:
            if not args.output.is_file():
                raise ParityError(f"committed parity matrix is missing: {args.output}")
            committed = args.output.read_bytes()
            if committed != payload:
                raise ParityError(f"committed parity matrix is stale: {args.output} differs from a fresh regeneration")
            if not args.markdown.is_file() or args.markdown.read_text(encoding="utf-8") != markdown:
                raise ParityError(f"committed parity matrix markdown is stale: {args.markdown}")
            print(f"ECOSYSTEM PARITY MATRIX CHECK PASS: {matrix['row_count']}/41 repositories, matrix current")
            return 0
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
        args.markdown.write_text(markdown, encoding="utf-8")
        print(f"ECOSYSTEM PARITY MATRIX GENERATED: {matrix['row_count']}/41 repositories")
        return 0
    except (ParityError, ecosystem_certify.CertificationError, OSError) as exc:
        print(f"ECOSYSTEM PARITY MATRIX FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
