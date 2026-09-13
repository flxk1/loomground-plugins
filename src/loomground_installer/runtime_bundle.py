# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Signed offline runtime bundles and transactional target-directory installs."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform as platform_module
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from packaging.markers import default_environment
from packaging.licenses import InvalidLicenseExpression, canonicalize_license_expression
from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

from .bundle import BundleError, canonical_json, dsse_pae

RUNTIME_PAYLOAD_TYPE = "application/vnd.loomground.runtime-bundle.v1+json"
RUNTIME_ENVELOPE_NAME = "runtime-manifest.dsse.json"
RUNTIME_LOCK_NAME = "runtime-lock.json"
RUNTIME_SBOM_NAME = "runtime-sbom.cdx.json"
RUNTIME_STATE_NAME = ".loomground-runtime-install.json"
MAX_ENVELOPE_BYTES = 8 * 1024 * 1024
NAME = re.compile(r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class RuntimePackage:
    name: str
    version: str
    wheel: str
    sha256: str
    license: str
    source: dict


@dataclass(frozen=True)
class VerifiedRuntimeBundle:
    root: Path
    key_id: str
    digest: str
    runtime_name: str
    runtime_version: str
    entry_point: str
    python_minimum: tuple[int, int]
    python_maximum_exclusive: tuple[int, int]
    platforms: tuple[str, ...]
    packages: tuple[RuntimePackage, ...]
    files: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeInstallReceipt:
    status: str
    destination: str
    bundle_digest: str
    runtime: str
    version: str
    python: str
    backup: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def runtime_sbom(lock: dict) -> dict:
    components = []
    for package in sorted(lock["packages"], key=lambda item: normalize_name(item["name"])):
        source = package["source"]
        if source["source"] == "git":
            repository = urlparse(source["url"]).path.removesuffix(".git").strip("/")
            bom_ref = f"pkg:github/{repository}@{source['commit']}"
            properties = [{"name": "loomground:git-commit", "value": source["commit"]}]
        else:
            bom_ref = f"pkg:pypi/{normalize_name(package['name'])}@{package['version']}"
            properties = []
        components.append({
            "type": "library",
            "bom-ref": bom_ref,
            "name": package["name"],
            "version": package["version"],
            "hashes": [{"alg": "SHA-256", "content": package["sha256"]}],
            "licenses": [{"expression": package["license"]}],
            "externalReferences": [{
                "type": "vcs" if source["source"] == "git" else "distribution",
                "url": source["url"],
            }],
            "properties": properties,
        })
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": lock["runtime"]["name"],
                "version": lock["runtime"]["version"],
            }
        },
        "components": components,
    }


def runtime_platform() -> str:
    """Return the concrete kernel/architecture pair used for bundle admission."""
    system = platform_module.system().lower()
    machine = platform_module.machine().lower().replace("x86-64", "x86_64")
    if not system or not machine:
        raise BundleError("cannot determine runtime OS and architecture")
    return f"{system}-{machine}"


def _safe_relative(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise BundleError(f"invalid runtime bundle path {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise BundleError(f"unsafe runtime bundle path {value!r}")
    if value in {RUNTIME_ENVELOPE_NAME, RUNTIME_STATE_NAME}:
        raise BundleError(f"reserved runtime bundle path {value!r}")
    return path


def _regular_file(root: Path, relative: PurePosixPath) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise BundleError(f"runtime bundle path contains symlink: {relative}")
    if not current.is_file():
        raise BundleError(f"runtime bundle file is missing or not regular: {relative}")
    return current


def _file_digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _public_key(path: Path) -> Ed25519PublicKey:
    try:
        key = load_pem_public_key(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise BundleError(f"cannot load runtime trust key: {exc}") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise BundleError("runtime trust key must be Ed25519")
    return key


def _version_pair(value: object, field: str) -> tuple[int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not isinstance(item, int) or item < 0 for item in value)
    ):
        raise BundleError(f"runtime lock {field} must be [major, minor]")
    return value[0], value[1]


def validate_runtime_lock(lock: object) -> tuple[
    str, str, str, tuple[int, int], tuple[int, int], tuple[str, ...], tuple[RuntimePackage, ...]
]:
    if not isinstance(lock, dict) or lock.get("schema_version") != 1:
        raise BundleError("unsupported runtime lock schema_version")
    runtime = lock.get("runtime")
    python = lock.get("python")
    platforms = lock.get("platforms")
    raw_packages = lock.get("packages")
    if not isinstance(runtime, dict) or set(runtime) != {"name", "version", "entry_point"}:
        raise BundleError("runtime lock runtime must contain name, version and entry_point")
    name = runtime["name"]
    version = runtime["version"]
    entry_point = runtime["entry_point"]
    if name != "loomground-mcp" or not isinstance(version, str) or not version:
        raise BundleError("runtime lock must select a versioned loomground-mcp")
    try:
        Version(version)
    except InvalidVersion as exc:
        raise BundleError("runtime lock has an invalid runtime version") from exc
    if entry_point != "loomground_mcp.server:main":
        raise BundleError("runtime lock has an unsupported entry point")
    if not isinstance(python, dict) or set(python) != {"minimum", "maximum_exclusive"}:
        raise BundleError("runtime lock python range is invalid")
    minimum = _version_pair(python["minimum"], "python.minimum")
    maximum = _version_pair(python["maximum_exclusive"], "python.maximum_exclusive")
    if minimum >= maximum:
        raise BundleError("runtime lock Python range is empty")
    if (
        not isinstance(platforms, list)
        or not platforms
        or any(not isinstance(item, str) or not item for item in platforms)
        or len(set(platforms)) != len(platforms)
    ):
        raise BundleError("runtime lock platforms must be unique non-empty strings")
    if not isinstance(raw_packages, list) or not raw_packages:
        raise BundleError("runtime lock must contain packages")

    packages: list[RuntimePackage] = []
    names: set[str] = set()
    wheels: set[str] = set()
    for raw in raw_packages:
        if not isinstance(raw, dict) or set(raw) != {
            "name", "version", "wheel", "sha256", "license", "source",
        }:
            raise BundleError(
                "each runtime package must contain name, version, wheel, sha256, license and source"
            )
        package_name = raw["name"]
        wheel = raw["wheel"]
        source = raw["source"]
        if not isinstance(package_name, str) or not NAME.fullmatch(package_name):
            raise BundleError(f"invalid runtime package name {package_name!r}")
        normalized = normalize_name(package_name)
        if normalized in names:
            raise BundleError(f"duplicate runtime package {normalized}")
        names.add(normalized)
        if not isinstance(raw["version"], str) or not raw["version"]:
            raise BundleError(f"runtime package {package_name} has no version")
        try:
            Version(raw["version"])
        except InvalidVersion as exc:
            raise BundleError(f"runtime package {package_name} has an invalid version") from exc
        if (
            not isinstance(wheel, str)
            or not wheel.endswith(".whl")
            or PurePosixPath(wheel).name != wheel
            or wheel in wheels
        ):
            raise BundleError(f"runtime package {package_name} has an invalid wheel filename")
        wheels.add(wheel)
        if not isinstance(raw["sha256"], str) or not SHA256.fullmatch(raw["sha256"]):
            raise BundleError(f"runtime package {package_name} has an invalid sha256")
        if not isinstance(raw["license"], str):
            raise BundleError(f"runtime package {package_name} has an invalid license expression")
        try:
            license_expression = canonicalize_license_expression(raw["license"])
        except InvalidLicenseExpression as exc:
            raise BundleError(f"runtime package {package_name} has an invalid license expression") from exc
        if license_expression != raw["license"]:
            raise BundleError(f"runtime package {package_name} license expression is not canonical")
        if not isinstance(source, dict):
            raise BundleError(f"runtime package {package_name} has no source provenance")
        source_type = source.get("source")
        source_url = source.get("url")
        if source_type == "git":
            if set(source) != {"source", "url", "commit"}:
                raise BundleError(f"runtime package {package_name} has invalid git provenance")
            if not isinstance(source.get("commit"), str) or not GIT_SHA.fullmatch(source["commit"]):
                raise BundleError(f"runtime package {package_name} has an invalid source commit")
        elif source_type == "index":
            if set(source) != {"source", "url"}:
                raise BundleError(f"runtime package {package_name} has invalid index provenance")
        else:
            raise BundleError(f"runtime package {package_name} has an unsupported provenance type")
        parsed_source = urlparse(source_url) if isinstance(source_url, str) else None
        if (
            parsed_source is None
            or parsed_source.scheme != "https"
            or not parsed_source.netloc
            or parsed_source.username
            or parsed_source.password
            or parsed_source.fragment
        ):
            raise BundleError(f"runtime package {package_name} provenance must use HTTPS")
        packages.append(RuntimePackage(
            package_name,
            raw["version"],
            wheel,
            raw["sha256"],
            license_expression,
            source,
        ))
    if "loomground-mcp" not in names:
        raise BundleError("runtime lock does not contain loomground-mcp")
    root = next(package for package in packages if normalize_name(package.name) == "loomground-mcp")
    if root.version != version:
        raise BundleError("runtime version differs from the loomground-mcp wheel version")
    return name, version, entry_point, minimum, maximum, tuple(platforms), tuple(packages)


def _wheel_metadata(path: Path) -> tuple[str, str, tuple[str, ...]]:
    try:
        with zipfile.ZipFile(path) as wheel:
            metadata_paths = [
                name for name in wheel.namelist()
                if name.count("/") == 1 and name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_paths) != 1:
                raise BundleError(f"wheel must contain exactly one METADATA file: {path.name}")
            for member in wheel.infolist():
                relative = PurePosixPath(member.filename)
                if relative.is_absolute() or ".." in relative.parts or "\\" in member.filename:
                    raise BundleError(f"wheel contains unsafe path: {path.name}")
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise BundleError(f"wheel contains symlink: {path.name}")
            if len(wheel.namelist()) != len(set(wheel.namelist())):
                raise BundleError(f"wheel contains duplicate paths: {path.name}")
            metadata = BytesParser().parsebytes(wheel.read(metadata_paths[0]))
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise BundleError(f"invalid wheel {path.name}: {exc}") from exc
    name, version = metadata.get("Name"), metadata.get("Version")
    if not name or not version:
        raise BundleError(f"wheel metadata lacks Name or Version: {path.name}")
    return name, version, tuple(metadata.get_all("Requires-Dist", []))


def _verify_dependency_closure(metadata: dict[str, tuple[str, tuple[str, ...]]]) -> None:
    environment = default_environment()
    environment["extra"] = ""
    for owner, (_, requirements) in metadata.items():
        for value in requirements:
            try:
                requirement = Requirement(value)
            except InvalidRequirement as exc:
                raise BundleError(f"wheel {owner} has an invalid Requires-Dist: {value}") from exc
            if requirement.marker and not requirement.marker.evaluate(environment):
                continue
            dependency = normalize_name(requirement.name)
            if dependency not in metadata:
                raise BundleError(f"runtime lock omits dependency {dependency} required by {owner}")
            try:
                installed_version = Version(metadata[dependency][0])
            except InvalidVersion as exc:
                raise BundleError(f"runtime package {dependency} has an invalid version") from exc
            if requirement.specifier and installed_version not in requirement.specifier:
                raise BundleError(
                    f"runtime lock has {dependency} {installed_version}, outside {requirement.specifier} required by {owner}"
                )


def verify_runtime_bundle(root: Path, public_key: Path) -> VerifiedRuntimeBundle:
    root = root.absolute()
    if not root.is_dir() or root.is_symlink():
        raise BundleError("runtime bundle root must be a real directory")
    envelope_path = root / RUNTIME_ENVELOPE_NAME
    if not envelope_path.is_file() or envelope_path.is_symlink():
        raise BundleError(f"runtime bundle lacks regular {RUNTIME_ENVELOPE_NAME}")
    if envelope_path.stat().st_size > MAX_ENVELOPE_BYTES:
        raise BundleError("runtime bundle envelope exceeds the size limit")
    try:
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
        payload_type = envelope["payloadType"]
        payload = base64.b64decode(envelope["payload"], validate=True)
        signatures = envelope["signatures"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise BundleError(f"invalid runtime DSSE envelope: {exc}") from exc
    if payload_type != RUNTIME_PAYLOAD_TYPE or not isinstance(signatures, list) or len(signatures) != 1:
        raise BundleError("runtime bundle must carry its payload type and exactly one signature")
    try:
        key_id = signatures[0]["keyid"]
        signature = base64.b64decode(signatures[0]["sig"], validate=True)
    except (KeyError, TypeError, ValueError) as exc:
        raise BundleError(f"invalid runtime signature record: {exc}") from exc
    if not isinstance(key_id, str) or not key_id:
        raise BundleError("runtime signature keyid is required")
    try:
        _public_key(public_key).verify(signature, dsse_pae(payload_type, payload))
    except InvalidSignature as exc:
        raise BundleError("runtime bundle signature is invalid") from exc
    try:
        statement = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"signed runtime payload is not JSON: {exc}") from exc
    if statement.get("schema_version") != 1 or statement.get("key_id") != key_id:
        raise BundleError("runtime statement schema or signed key_id is invalid")
    if payload != canonical_json(statement):
        raise BundleError("signed runtime statement is not canonical JSON")
    lock = statement.get("lock")
    name, version, entry_point, minimum, maximum, platforms, packages = validate_runtime_lock(lock)
    lock_path = root / RUNTIME_LOCK_NAME
    if not lock_path.is_file() or lock_path.is_symlink():
        raise BundleError(f"runtime bundle lacks regular {RUNTIME_LOCK_NAME}")
    if lock_path.read_bytes() != canonical_json(lock) + b"\n":
        raise BundleError("runtime lock file differs from signed lock")
    sbom_path = root / RUNTIME_SBOM_NAME
    if not sbom_path.is_file() or sbom_path.is_symlink():
        raise BundleError(f"runtime bundle lacks regular {RUNTIME_SBOM_NAME}")
    if sbom_path.read_bytes() != canonical_json(runtime_sbom(lock)) + b"\n":
        raise BundleError("runtime SBOM differs from signed lock")

    records = statement.get("files")
    if not isinstance(records, list) or not records:
        raise BundleError("signed runtime statement has no files")
    expected: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise BundleError("runtime file record must be an object")
        relative = _safe_relative(record.get("path"))
        value = relative.as_posix()
        if value in expected:
            raise BundleError(f"duplicate runtime bundle path {value}")
        expected.add(value)
        size, digest = _file_digest(_regular_file(root, relative))
        if record.get("size") != size or record.get("sha256") != digest:
            raise BundleError(f"runtime bundle file digest mismatch: {value}")
    required = {RUNTIME_LOCK_NAME, RUNTIME_SBOM_NAME} | {
        f"wheels/{package.wheel}" for package in packages
    }
    if expected != required:
        raise BundleError(f"runtime bundle records differ from lock: missing={sorted(required - expected)}, extra={sorted(expected - required)}")
    actual: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise BundleError(f"runtime bundle contains symlink: {path.relative_to(root)}")
        if path.is_file() and path.relative_to(root).as_posix() != RUNTIME_ENVELOPE_NAME:
            actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise BundleError(f"runtime bundle file set mismatch: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}")
    package_metadata: dict[str, tuple[str, tuple[str, ...]]] = {}
    for package in packages:
        wheel = root / "wheels" / package.wheel
        _, digest = _file_digest(wheel)
        if digest != package.sha256:
            raise BundleError(f"runtime lock digest mismatch: {package.wheel}")
        metadata_name, metadata_version, requirements = _wheel_metadata(wheel)
        if normalize_name(metadata_name) != normalize_name(package.name) or metadata_version != package.version:
            raise BundleError(f"runtime wheel metadata mismatch: {package.wheel}")
        package_metadata[normalize_name(package.name)] = (metadata_version, requirements)
    _verify_dependency_closure(package_metadata)
    return VerifiedRuntimeBundle(
        root, key_id, hashlib.sha256(payload).hexdigest(), name, version, entry_point,
        minimum, maximum, platforms, packages, tuple(sorted(expected)),
    )


def _runtime_state(path: Path) -> dict | None:
    try:
        return json.loads((path / RUNTIME_STATE_NAME).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _check_destination(destination: Path) -> None:
    if not destination.is_absolute() or destination == Path(destination.anchor):
        raise BundleError("runtime destination must be an explicit absolute non-root path")
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise BundleError("runtime destination must be absent or a real directory")
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise BundleError("runtime destination parent must be a real existing directory")


@contextmanager
def _runtime_destination_lock(destination: Path):
    """Serialize installation and rollback for one destination across processes."""
    lock_path = destination.parent / f".{destination.name}.loomground-runtime.lock"
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise BundleError(f"cannot open runtime destination lock: {exc}") from exc
    stream = os.fdopen(descriptor, "r+b", buffering=0)
    try:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"\0")
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        stream.close()


def _check_compatibility(bundle: VerifiedRuntimeBundle) -> None:
    current = sys.version_info[:2]
    if not bundle.python_minimum <= current < bundle.python_maximum_exclusive:
        raise BundleError(
            f"runtime requires Python {bundle.python_minimum}..< {bundle.python_maximum_exclusive}; found {current}"
        )
    platform = runtime_platform()
    if "any" not in bundle.platforms and platform not in bundle.platforms:
        raise BundleError(f"runtime bundle does not support platform {platform}")


def _write_launcher(stage: Path) -> None:
    launcher = stage / "bin" / "loomground-mcp"
    launcher.parent.mkdir(parents=True)
    source = (
        f"#!{sys.executable}\n"
        "import site\n"
        "from pathlib import Path\n"
        "site.addsitedir(str(Path(__file__).resolve().parents[1] / 'lib'))\n"
        "from loomground_mcp.server import main\n"
        "raise SystemExit(main())\n"
    )
    launcher.write_text(source, encoding="utf-8")
    launcher.chmod(0o755)
    windows = stage / "bin" / "loomground-mcp.cmd"
    windows.write_text(
        f'@"{sys.executable}" "%~dp0loomground-mcp" %*\r\n', encoding="utf-8"
    )


def _install_runtime_bundle_unlocked(
    bundle_root: Path, public_key: Path, destination: Path
) -> RuntimeInstallReceipt:
    verified = verify_runtime_bundle(bundle_root, public_key)
    _check_compatibility(verified)
    _check_destination(destination)
    existing = _runtime_state(destination) if destination.exists() else None
    if existing and existing.get("bundle_digest") == verified.digest:
        installed = verify_runtime_bundle(destination / "bundle", public_key)
        launcher = destination / "bin" / "loomground-mcp"
        if installed.digest != verified.digest or not launcher.is_file() or launcher.is_symlink():
            raise BundleError("installed runtime state does not match its signed bundle or launcher")
        return RuntimeInstallReceipt(
            "unchanged", str(destination), verified.digest, verified.runtime_name,
            verified.runtime_version, existing.get("python", sys.executable), None,
        )

    parent = destination.parent
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.loomground-runtime-stage-", dir=parent))
    backup: Path | None = None
    moved_existing = False
    try:
        shutil.copytree(verified.root, stage / "bundle")
        staged = verify_runtime_bundle(stage / "bundle", public_key)
        if staged.digest != verified.digest:
            raise BundleError("staged runtime bundle differs from verified source")
        wheels = [str(stage / "bundle" / "wheels" / package.wheel) for package in verified.packages]
        environment = dict(os.environ)
        environment.update({
            "PIP_NO_INDEX": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PYTHONNOUSERSITE": "1",
        })
        result = subprocess.run(
            [
                sys.executable, "-m", "pip", "install", "--no-input", "--no-index",
                "--no-deps", "--no-compile", "--no-warn-script-location",
                "--target", str(stage / "lib"), *wheels,
            ],
            text=True,
            capture_output=True,
            env=environment,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout)[-4000:]
            raise BundleError(f"offline runtime installation failed: {detail.strip()}")
        probe = subprocess.run(
            [
                sys.executable, "-I", "-c",
                f"import site; site.addsitedir({str(stage / 'lib')!r}); from loomground_mcp.server import main; assert callable(main)",
            ],
            text=True,
            capture_output=True,
            env=environment,
        )
        if probe.returncode:
            detail = (probe.stderr or probe.stdout)[-4000:]
            raise BundleError(f"installed runtime import probe failed: {detail.strip()}")
        _write_launcher(stage)
        state = {
            "schema_version": 1,
            "bundle_digest": verified.digest,
            "key_id": verified.key_id,
            "runtime": verified.runtime_name,
            "version": verified.runtime_version,
            "python": sys.executable,
        }
        (stage / RUNTIME_STATE_NAME).write_bytes(canonical_json(state) + b"\n")
        if destination.exists():
            backup = parent / f".{destination.name}.loomground-runtime-backup-{uuid.uuid4().hex}"
            os.replace(destination, backup)
            moved_existing = True
        os.replace(stage, destination)
    except Exception:
        if moved_existing and backup is not None and not destination.exists():
            os.replace(backup, destination)
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return RuntimeInstallReceipt(
        "installed", str(destination), verified.digest, verified.runtime_name,
        verified.runtime_version, sys.executable, str(backup) if backup else None,
    )


def install_runtime_bundle(
    bundle_root: Path, public_key: Path, destination: Path
) -> RuntimeInstallReceipt:
    _check_destination(destination)
    with _runtime_destination_lock(destination):
        return _install_runtime_bundle_unlocked(bundle_root, public_key, destination)


def _rollback_runtime_install_unlocked(
    destination: Path, backup: Path, public_key: Path
) -> RuntimeInstallReceipt:
    if not destination.is_absolute() or not backup.is_absolute() or destination.parent != backup.parent:
        raise BundleError("runtime destination and backup must be absolute siblings")
    if not backup.name.startswith(f".{destination.name}.loomground-runtime-backup-"):
        raise BundleError("runtime backup name does not belong to destination")
    verified = verify_runtime_bundle(backup / "bundle", public_key)
    backup_state = _runtime_state(backup)
    if not backup_state or backup_state.get("bundle_digest") != verified.digest:
        raise BundleError("runtime backup state does not match its signed bundle")
    if destination.is_symlink() or not destination.is_dir():
        raise BundleError("current runtime destination must be a real directory")
    displaced = destination.parent / f".{destination.name}.loomground-runtime-replaced-{uuid.uuid4().hex}"
    os.replace(destination, displaced)
    try:
        os.replace(backup, destination)
    except Exception:
        os.replace(displaced, destination)
        raise
    state = _runtime_state(destination) or {}
    return RuntimeInstallReceipt(
        "rolled-back", str(destination), verified.digest, verified.runtime_name,
        verified.runtime_version, state.get("python", sys.executable), str(displaced),
    )


def rollback_runtime_install(
    destination: Path, backup: Path, public_key: Path
) -> RuntimeInstallReceipt:
    if not destination.is_absolute() or not destination.parent.is_dir():
        raise BundleError("runtime destination must be absolute below an existing parent")
    with _runtime_destination_lock(destination):
        return _rollback_runtime_install_unlocked(destination, backup, public_key)
