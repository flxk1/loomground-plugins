#!/usr/bin/env python3
"""Validate portable package metadata and build platform distributions."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
TARGETS = ("claude", "codex", "generic")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CAPABILITY = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
EXTERNAL_KINDS = ("package", "plugin")
MCP_SERVERS = {"loomground": {"command": "loomground-mcp", "args": ["serve", "--transport", "stdio"]}}
SCHEMA = json.loads((ROOT / "schemas" / "loomground-package.schema.json").read_text(encoding="utf-8"))
SCHEMA_VALIDATOR = Draft202012Validator(SCHEMA)


class PackageError(ValueError):
    pass


def validate_marketplace_source(source: object, path: Path) -> None:
    """Require remote plugin sources to resolve to one immutable Git commit."""
    if isinstance(source, str):
        if not source.startswith("./"):
            raise PackageError(f"{path}: marketplaceSource path must start with ./")
        return
    if not isinstance(source, dict):
        raise PackageError(f"{path}: marketplaceSource must be a relative path or source object")
    source_type = source.get("source")
    if source_type not in {"github", "url", "git-subdir"}:
        raise PackageError(f"{path}: unsupported marketplaceSource type {source_type!r}")
    sha = source.get("sha")
    if not isinstance(sha, str) or not GIT_SHA.fullmatch(sha):
        raise PackageError(
            f"{path}: remote marketplaceSource must include a full 40-character lowercase commit sha"
        )


def load_package(package_dir: Path) -> dict:
    path = package_dir / "package.json"
    if not path.is_file():
        raise PackageError(f"missing {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    schema_errors = sorted(SCHEMA_VALIDATOR.iter_errors(data), key=lambda error: list(error.path))
    if schema_errors:
        details = "; ".join(error.message for error in schema_errors)
        raise PackageError(f"{path}: schema validation failed: {details}")
    required = {"schemaVersion", "name", "version", "description", "author", "skills", "capabilities", "runtime", "adapters"}
    missing = required - data.keys()
    if missing:
        raise PackageError(f"{path}: missing {', '.join(sorted(missing))}")
    if data["schemaVersion"] != 1:
        raise PackageError(f"{path}: unsupported schemaVersion")
    if not NAME.fullmatch(data["name"]) or len(data["name"]) > 64:
        raise PackageError(f"{path}: invalid package name")
    if package_dir.name != data["name"]:
        raise PackageError(f"{path}: directory and package name differ")
    if not SEMVER.fullmatch(data["version"]):
        raise PackageError(f"{path}: version must be strict semver")
    if data["author"] != {"name": "Loomground Contributors"}:
        raise PackageError(f"{path}: author must be Loomground Contributors")
    if not isinstance(data["skills"], list) or not data["skills"]:
        raise PackageError(f"{path}: at least one skill is required")
    provided = set()
    for skill in data["skills"]:
        skill_dir = package_dir / skill["path"]
        if not NAME.fullmatch(skill["name"]):
            raise PackageError(f"{path}: invalid skill name {skill['name']!r}")
        if not (skill_dir / "SKILL.md").is_file():
            raise PackageError(f"{path}: missing {skill['path']}/SKILL.md")
        for capability in skill["provides"]:
            if not CAPABILITY.fullmatch(capability):
                raise PackageError(f"{path}: invalid capability {capability!r}")
            provided.add(capability)
    if provided != set(data["capabilities"]):
        raise PackageError(f"{path}: provided capabilities and capability declarations differ")
    if set(data["adapters"]) != set(TARGETS):
        raise PackageError(f"{path}: adapters must declare claude, codex, and generic")
    for config in data["runtime"]["config"]:
        if not (package_dir / config).is_file():
            raise PackageError(f"{path}: missing config file {config}")
    return data


def reset_output(target: str, name: str) -> Path:
    output = DIST / target / name
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    return output


def reset_targets(targets: tuple[str, ...]) -> None:
    """Remove complete target trees so deleted packages cannot survive a full build."""
    for target in targets:
        output = DIST / target
        if output.exists():
            shutil.rmtree(output)


def copy_shared(package_dir: Path, output: Path) -> None:
    ignore = shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc", ".pytest_cache")
    shutil.copytree(package_dir / "skills", output / "skills", ignore=ignore)
    # Optional plugin-level directories carried verbatim into the distribution
    # when a package uses them (e.g. an MCP-driver plugin ships mcp/, apps/,
    # references/, schemas/ alongside skills/). Absent dirs are skipped.
    for dirname in ("mcp", "apps", "references", "schemas"):
        source = package_dir / dirname
        if source.is_dir():
            shutil.copytree(source, output / dirname, ignore=ignore)
    for filename in ("README.md", "package.json"):
        source = package_dir / filename
        if source.is_file():
            shutil.copy2(source, output / filename)


def clean_generated_metadata() -> None:
    if not DIST.exists():
        return
    for path in DIST.rglob(".DS_Store"):
        path.unlink(missing_ok=True)
    for path in DIST.rglob("__pycache__"):
        shutil.rmtree(path, ignore_errors=True)


def claude_manifest(data: dict) -> dict:
    return {
        "name": data["name"],
        "version": data["version"],
        "description": data["description"],
        "author": data["author"],
        "keywords": data.get("keywords", []),
        "mcpServers": MCP_SERVERS,
    }


def marketplace_entry(data: dict, source: object) -> dict:
    return {
        "name": data["name"],
        "source": source,
        "description": data["description"],
        "version": data["version"],
        "author": data["author"],
        "keywords": data.get("keywords", []),
    }


def marketplace_manifest(packages: list[dict], sources: dict[str, object], plugins: list[dict] = ()) -> dict:
    return {
        "name": "loomground",
        "owner": {"name": "Loomground Contributors"},
        "metadata": {
            "description": "Universal Loomground skill packages, installable on Claude, Codex, and generic skill hosts.",
            "version": "0.1.0",
        },
        # Immutable release pins live in this marketplace repository.
        # A source package cannot embed its own commit without changing
        # that commit, so package-local metadata is not the lock authority.
        "plugins": sorted(
            [marketplace_entry(data, sources.get(data["name"], f"./{data['name']}")) for data in packages]
            + [marketplace_entry(data, sources[data["name"]]) for data in plugins],
            key=lambda entry: entry["name"],
        ),
    }


def sync_claude_source_tree() -> None:
    """Write the committed Claude artifacts into the source tree.

    Claude Code installs marketplaces and plugins from the committed repository,
    not from dist/, so every canonical package carries .claude-plugin/plugin.json
    and the repository root carries .claude-plugin/marketplace.json. Codex and
    generic hosts keep consuming the built distributions under dist/.
    """
    directories = package_dirs([])
    packages = [load_package(directory) for directory in directories]
    for directory, data in zip(directories, packages):
        write_json(directory / ".claude-plugin" / "plugin.json", claude_manifest(data))
    plugins = external_plugin_manifests()
    write_json(
        ROOT / ".claude-plugin" / "marketplace.json",
        marketplace_manifest(packages, external_marketplace_sources(), plugins),
    )
    print(
        f"synced .claude-plugin/marketplace.json ({len(packages) + len(plugins)} plugins) "
        "and per-package plugin.json"
    )


def codex_manifest(data: dict) -> dict:
    return {
        "name": data["name"],
        "version": data["version"],
        "description": data["description"],
        "author": data["author"],
        "keywords": data.get("keywords", []),
        "skills": "./skills/",
        "interface": data["adapters"]["codex"]["interface"],
    }


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build(package_dir: Path, data: dict, target: str) -> Path:
    output = reset_output(target, data["name"])
    copy_shared(package_dir, output)
    if target == "claude":
        write_json(output / ".claude-plugin" / "plugin.json", claude_manifest(data))
    elif target == "codex":
        write_json(output / ".codex-plugin" / "plugin.json", codex_manifest(data))
    else:
        install = (
            f"# Install {data['name']} on a generic skill host\n\n"
            "Copy each directory under `skills/` into the host's skill directory. The host must "
            "support Markdown `SKILL.md` discovery and local Python execution. Review `package.json` "
            "for capabilities, runtime requirements, and configuration files. Platform-specific "
            "marketplaces, hooks, tool aliases, and multi-agent behavior are intentionally excluded.\n"
        )
        (output / "INSTALL.md").write_text(install, encoding="utf-8")
    return output


def external_config() -> dict[str, dict]:
    path = ROOT / "externals.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    config = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise PackageError(f"external package {name}: expected path and immutable source")
        if entry.get("kind", "package") not in EXTERNAL_KINDS:
            raise PackageError(f"external package {name}: kind must be one of {', '.join(EXTERNAL_KINDS)}")
        validate_marketplace_source(entry.get("source"), path)
        config[name] = entry
    return config


def external_kind(entry: dict) -> str:
    return entry.get("kind", "package")


def external_marketplace_sources() -> dict[str, object]:
    return {name: entry["source"] for name, entry in external_config().items()}


def external_package_dirs() -> dict[str, Path]:
    """Canonical packages that live in their tool repositories (sibling checkouts).

    externals.json maps package name to a path relative to this repository. The
    siblings are required for a full build: failing loudly beats silently dropping
    a package from the marketplace.
    """
    dirs = {}
    for name, entry in sorted(external_config().items()):
        if external_kind(entry) != "package":
            continue
        rel = entry["path"]
        directory = (ROOT / rel).resolve()
        if not (directory / "package.json").is_file():
            raise PackageError(f"external package {name}: no package.json at {rel} (sibling checkout required)")
        dirs[name] = directory
    return dirs


def load_plugin_manifest(name: str, directory: Path) -> dict:
    """A plugin-kind external ships only its committed Claude manifest; carry it as-is."""
    path = directory / ".claude-plugin" / "plugin.json"
    if not path.is_file():
        raise PackageError(f"external plugin {name}: no .claude-plugin/plugin.json (sibling checkout required)")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("name") != name:
        raise PackageError(f"{path}: manifest name {data.get('name')!r} differs from external {name!r}")
    if not isinstance(data.get("version"), str) or not SEMVER.fullmatch(data["version"]):
        raise PackageError(f"{path}: version must be strict semver")
    if not isinstance(data.get("description"), str) or not data["description"]:
        raise PackageError(f"{path}: description is required")
    if data.get("author") != {"name": "Loomground Contributors"}:
        raise PackageError(f"{path}: author must be Loomground Contributors")
    return data


def external_plugin_manifests() -> list[dict]:
    manifests = []
    for name, entry in sorted(external_config().items()):
        if external_kind(entry) == "plugin":
            manifests.append(load_plugin_manifest(name, (ROOT / entry["path"]).resolve()))
    return manifests


def package_dirs(names: list[str]) -> list[Path]:
    externals = external_package_dirs()
    if names:
        return [externals.get(name, ROOT / name) for name in names]
    local = [path.parent for path in ROOT.glob("*/package.json") if path.parent.parent == ROOT]
    return sorted(local + list(externals.values()), key=lambda path: path.name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packages", nargs="*", help="package directory names; default: all canonical packages")
    parser.add_argument("--target", choices=("all",) + TARGETS, default="all")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    targets = TARGETS if args.target == "all" else (args.target,)
    try:
        dirs = package_dirs(args.packages)
        if not dirs:
            raise PackageError("no canonical packages found")
        packages = [(directory, load_package(directory)) for directory in dirs]
        for _, data in packages:
            print(f"validated {data['name']} {data['version']}")
        if not args.packages:
            for data in external_plugin_manifests():
                print(f"validated {data['name']} {data['version']} (plugin manifest)")
        if not args.validate_only:
            if not args.packages:
                reset_targets(targets)
            for directory, data in packages:
                for target in targets:
                    output = build(directory, data, target)
                    print(f"built {output.relative_to(ROOT)}")
            sync_claude_source_tree()
        clean_generated_metadata()
    except (OSError, json.JSONDecodeError, KeyError, TypeError, PackageError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
