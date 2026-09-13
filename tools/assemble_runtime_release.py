#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Build all pinned Loomground wheels and assemble one signed runtime release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import build_runtime_bundle  # noqa: E402
from loomground_installer.bundle import BundleError, canonical_json  # noqa: E402
from loomground_installer.runtime_bundle import (  # noqa: E402
    _wheel_metadata,
    normalize_name,
    runtime_platform,
    verify_runtime_bundle,
)

NAME = re.compile(r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _run(command: list[str], *, cwd: Path | None = None, environment: dict | None = None) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode:
        detail = result.stdout[-8000:].strip()
        raise BundleError(f"command failed ({' '.join(command[:4])}): {detail}")


def _https_source(value: object) -> str:
    if not isinstance(value, str):
        raise BundleError("runtime source URL must be a string")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.query
    ):
        raise BundleError(f"runtime source must be a credential-free HTTPS URL: {value!r}")
    return value


def load_sources(path: Path) -> tuple[tuple[int, int], tuple[int, int], str, tuple[dict, ...]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"cannot read runtime sources: {exc}") from exc
    if not isinstance(document, dict) or set(document) != {
        "schema_version", "python", "root", "packages",
    } or document["schema_version"] != 1:
        raise BundleError("unsupported runtime sources schema")
    python = document["python"]
    if not isinstance(python, dict) or set(python) != {"minimum", "maximum_exclusive"}:
        raise BundleError("runtime source Python range is invalid")
    pairs = []
    for field in ("minimum", "maximum_exclusive"):
        value = python[field]
        if not isinstance(value, list) or len(value) != 2 or any(
            not isinstance(item, int) or item < 0 for item in value
        ):
            raise BundleError(f"runtime source python.{field} must be [major, minor]")
        pairs.append((value[0], value[1]))
    minimum, maximum = pairs
    if minimum >= maximum:
        raise BundleError("runtime source Python range is empty")
    root = document["root"]
    packages = document["packages"]
    if root != "loomground-mcp" or not isinstance(packages, list) or not packages:
        raise BundleError("runtime sources require loomground-mcp and a non-empty package list")
    names = set()
    validated = []
    for package in packages:
        if not isinstance(package, dict) or set(package) != {"name", "url", "commit"}:
            raise BundleError("runtime source entries require name, url and commit")
        name = package["name"]
        commit = package["commit"]
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise BundleError(f"invalid runtime source name {name!r}")
        normalized = normalize_name(name)
        if normalized in names:
            raise BundleError(f"duplicate runtime source {normalized}")
        names.add(normalized)
        if not isinstance(commit, str) or not GIT_SHA.fullmatch(commit):
            raise BundleError(f"runtime source {name} requires a full lowercase commit")
        validated.append({"name": name, "url": _https_source(package["url"]), "commit": commit})
    if root not in names:
        raise BundleError("runtime root is absent from sources")
    return minimum, maximum, root, tuple(validated)


def _checkout(package: dict, destination: Path) -> int:
    _run(["git", "init", "-q", str(destination)])
    _run(["git", "-C", str(destination), "remote", "add", "origin", package["url"]])
    _run([
        "git", "-C", str(destination), "fetch", "-q", "--depth", "1", "origin", package["commit"],
    ])
    _run(["git", "-C", str(destination), "checkout", "-q", "--detach", "FETCH_HEAD"])
    head = subprocess.run(
        ["git", "-C", str(destination), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if head != package["commit"]:
        raise BundleError(f"checkout for {package['name']} resolved to {head}, not its pin")
    timestamp = subprocess.run(
        ["git", "-C", str(destination), "show", "-s", "--format=%ct", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    return int(timestamp)


def _canonical_git_url(value: str) -> str:
    return value.removeprefix("git+").removesuffix(".git").rstrip("/")


def verify_root_pins(root_checkout: Path, sources: tuple[dict, ...], root_name: str) -> None:
    requirements = root_checkout / "requirements-dev.txt"
    try:
        lines = requirements.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BundleError(f"runtime root lacks requirements-dev.txt: {exc}") from exc
    declared = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            requirement = Requirement(line)
        except InvalidRequirement as exc:
            raise BundleError(f"invalid root requirement: {line}") from exc
        if not requirement.url:
            continue
        try:
            url, commit = requirement.url.rsplit("@", 1)
        except ValueError as exc:
            raise BundleError(f"unpinned root VCS requirement: {line}") from exc
        declared[normalize_name(requirement.name)] = (_canonical_git_url(url), commit)
    expected = {
        normalize_name(package["name"]): (_canonical_git_url(package["url"]), package["commit"])
        for package in sources
        if normalize_name(package["name"]) != normalize_name(root_name)
    }
    if declared != expected:
        missing = sorted(set(expected) - set(declared))
        extra = sorted(set(declared) - set(expected))
        changed = sorted(name for name in set(expected) & set(declared) if expected[name] != declared[name])
        raise BundleError(
            f"runtime sources differ from loomground-mcp pins: missing={missing}, extra={extra}, changed={changed}"
        )


def _build_source_wheel(source: Path, wheelhouse: Path, timestamp: int) -> Path:
    before = set(wheelhouse.glob("*.whl"))
    environment = dict(os.environ)
    environment.update({"PYTHONHASHSEED": "0", "SOURCE_DATE_EPOCH": str(timestamp)})
    _run([
        sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
        "--disable-pip-version-check", "--wheel-dir", str(wheelhouse), str(source),
    ], environment=environment)
    created = set(wheelhouse.glob("*.whl")) - before
    if len(created) != 1:
        raise BundleError(f"source build produced {len(created)} new wheels for {source.name}")
    return created.pop()


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _download_third_party(requirements: Path, wheelhouse: Path) -> None:
    _run([
        sys.executable, "-m", "pip", "download", "--require-hashes", "--only-binary=:all:",
        "--disable-pip-version-check", "--dest", str(wheelhouse), "-r", str(requirements),
    ])


def locked_requirement_names(
    requirements: Path,
    environment: dict[str, str] | None = None,
) -> tuple[set[str], set[str]]:
    """Return every locked name and the subset active on the target runner."""
    resolved_environment = environment or default_environment()
    pins = [
        Requirement(line.split(" \\", 1)[0])
        for line in requirements.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith(("#", " "))
    ]
    all_names = {normalize_name(pin.name) for pin in pins}
    active_names = {
        normalize_name(pin.name)
        for pin in pins
        if pin.marker is None or pin.marker.evaluate(resolved_environment)
    }
    return all_names, active_names


def load_licenses(path: Path) -> dict[str, str]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"cannot read runtime licenses: {exc}") from exc
    if not isinstance(document, dict) or set(document) != {"schema_version", "licenses"}:
        raise BundleError("unsupported runtime licenses schema")
    licenses = document["licenses"]
    if document["schema_version"] != 1 or not isinstance(licenses, dict) or not licenses:
        raise BundleError("runtime licenses must contain a non-empty versioned map")
    return {normalize_name(name): value for name, value in licenses.items()}


def assemble(
    sources_path: Path,
    requirements: Path,
    output: Path,
    signing_key: Path,
    public_key: Path,
    key_id: str,
    expected_version: str | None = None,
    licenses_path: Path | None = None,
) -> Path:
    minimum, maximum, root_name, sources = load_sources(sources_path)
    current = sys.version_info[:2]
    if not minimum <= current < maximum:
        raise BundleError(f"release requires Python {minimum}..< {maximum}; found {current}")
    if output.exists() or output.is_symlink():
        raise BundleError(f"runtime release output already exists: {output}")
    if not output.is_absolute() or not output.parent.is_dir():
        raise BundleError("runtime release output must be absolute below an existing parent")

    with tempfile.TemporaryDirectory(prefix="loomground-runtime-release-") as temporary:
        stage = Path(temporary)
        wheelhouse = stage / "wheelhouse"
        source_root = stage / "sources"
        wheelhouse.mkdir()
        source_root.mkdir()
        provenance = {}
        root_checkout = None
        for index, package in enumerate(sources):
            checkout = source_root / f"{index:02d}-{normalize_name(package['name'])}"
            timestamp = _checkout(package, checkout)
            if normalize_name(package["name"]) == normalize_name(root_name):
                root_checkout = checkout
            wheel = _build_source_wheel(checkout, wheelhouse, timestamp)
            metadata_name, version, _ = _wheel_metadata(wheel)
            if normalize_name(metadata_name) != normalize_name(package["name"]):
                raise BundleError(
                    f"source {package['name']} built unexpected distribution {metadata_name}"
                )
            provenance[normalize_name(metadata_name)] = {
                "version": version,
                "source": {"source": "git", "url": package["url"], "commit": package["commit"]},
            }
        if root_checkout is None:
            raise BundleError("runtime root checkout was not built")
        verify_root_pins(root_checkout, sources, root_name)
        _download_third_party(requirements, wheelhouse)

        third_party_names, active_third_party_names = locked_requirement_names(requirements)
        licenses = load_licenses(
            licenses_path or ROOT / "runtime" / "third-party-licenses.json"
        )
        if set(licenses) != third_party_names:
            raise BundleError(
                "runtime license map differs from third-party lock: "
                f"missing={sorted(third_party_names - set(licenses))}, "
                f"extra={sorted(set(licenses) - third_party_names)}"
            )
        packages = []
        for wheel in sorted(wheelhouse.glob("*.whl")):
            metadata_name, version, _ = _wheel_metadata(wheel)
            normalized = normalize_name(metadata_name)
            record = provenance.get(normalized)
            if record:
                if record["version"] != version:
                    raise BundleError(f"duplicate version for first-party package {normalized}")
                source = record["source"]
                license_expression = "Apache-2.0"
            else:
                source = {
                    "source": "index",
                    "url": f"https://pypi.org/project/{metadata_name}/{version}/",
                }
                license_expression = licenses[normalized]
            packages.append({
                "name": metadata_name,
                "version": version,
                "wheel": wheel.name,
                "sha256": _digest(wheel),
                "license": license_expression,
                "source": source,
            })
        if {normalize_name(item["name"]) for item in packages} != (
            set(provenance) | active_third_party_names
        ):
            raise BundleError("built wheel set differs from pinned first- and third-party packages")
        root_record = next(
            item for item in packages if normalize_name(item["name"]) == normalize_name(root_name)
        )
        if expected_version is not None and root_record["version"] != expected_version:
            raise BundleError(
                f"runtime version {root_record['version']} differs from requested release {expected_version}"
            )
        platform = runtime_platform()
        runtime_lock = {
            "schema_version": 1,
            "runtime": {
                "name": root_name,
                "version": root_record["version"],
                "entry_point": "loomground_mcp.server:main",
            },
            "python": {
                "minimum": list(minimum),
                "maximum_exclusive": list(maximum),
            },
            "platforms": [platform],
            "packages": sorted(packages, key=lambda item: normalize_name(item["name"])),
        }
        lock_path = stage / "runtime-lock.json"
        lock_path.write_bytes(canonical_json(runtime_lock) + b"\n")
        build_runtime_bundle.build(lock_path, wheelhouse, output, signing_key, key_id)
    verify_runtime_bundle(output, public_key)
    archive = shutil.make_archive(str(output), "zip", root_dir=output)
    print(json.dumps({
        "bundle": str(output),
        "archive": archive,
        "runtime": root_record["version"],
        "platform": platform,
        "packages": len(packages),
        "sha256": _digest(Path(archive)),
    }, indent=2))
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, default=ROOT / "runtime" / "runtime-sources.json")
    parser.add_argument(
        "--third-party",
        type=Path,
        default=ROOT / "runtime" / "third-party-requirements.txt",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--signing-key", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--expected-version")
    parser.add_argument(
        "--licenses",
        type=Path,
        default=ROOT / "runtime" / "third-party-licenses.json",
    )
    args = parser.parse_args()
    try:
        assemble(
            args.sources,
            args.third_party,
            args.output,
            args.signing_key,
            args.public_key,
            args.key_id,
            args.expected_version,
            args.licenses,
        )
    except (OSError, ValueError, BundleError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
