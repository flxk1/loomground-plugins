# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Signed profile-bundle verification and explicit transactional installation."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ENVELOPE_NAME = "manifest.dsse.json"
STATE_NAME = ".loomground-install.json"
PAYLOAD_TYPE = "application/vnd.loomground.profile-bundle.v1+json"
MAX_ENVELOPE_BYTES = 8 * 1024 * 1024


class BundleError(ValueError):
    """A bundle is unsafe, invalid, untrusted or inconsistent."""


@dataclass(frozen=True)
class VerifiedBundle:
    root: Path
    profile: str
    target: str
    key_id: str
    digest: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class InstallReceipt:
    status: str
    destination: str
    bundle_digest: str
    profile: str
    target: str
    backup: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    kind = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(kind)).encode() + b" " + kind + b" " + str(len(payload)).encode() + b" " + payload


def _safe_relative(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise BundleError(f"invalid bundle path {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise BundleError(f"unsafe bundle path {value!r}")
    if value == ENVELOPE_NAME or value == STATE_NAME:
        raise BundleError(f"reserved bundle path {value!r}")
    return path


def _regular_file(root: Path, relative: PurePosixPath) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise BundleError(f"bundle path contains symlink: {relative}")
    if not current.is_file():
        raise BundleError(f"bundle file is missing or not regular: {relative}")
    return current


def _load_public_key(path: Path) -> Ed25519PublicKey:
    try:
        key = load_pem_public_key(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise BundleError(f"cannot load public key: {exc}") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise BundleError("bundle trust key must be Ed25519")
    return key


def _file_digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def verify_bundle(root: Path, public_key: Path) -> VerifiedBundle:
    root = root.absolute()
    if not root.is_dir() or root.is_symlink():
        raise BundleError("bundle root must be a real directory")
    envelope_path = root / ENVELOPE_NAME
    if not envelope_path.is_file() or envelope_path.is_symlink():
        raise BundleError(f"bundle lacks regular {ENVELOPE_NAME}")
    if envelope_path.stat().st_size > MAX_ENVELOPE_BYTES:
        raise BundleError("bundle envelope exceeds the size limit")
    try:
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
        payload_type = envelope["payloadType"]
        payload = base64.b64decode(envelope["payload"], validate=True)
        signatures = envelope["signatures"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise BundleError(f"invalid DSSE envelope: {exc}") from exc
    if payload_type != PAYLOAD_TYPE or not isinstance(signatures, list) or len(signatures) != 1:
        raise BundleError("bundle must carry the profile-bundle payload type and exactly one signature")
    signature = signatures[0]
    try:
        key_id = signature["keyid"]
        raw_signature = base64.b64decode(signature["sig"], validate=True)
    except (KeyError, TypeError, ValueError) as exc:
        raise BundleError(f"invalid bundle signature record: {exc}") from exc
    if not isinstance(key_id, str) or not key_id:
        raise BundleError("bundle signature keyid is required")
    try:
        _load_public_key(public_key).verify(raw_signature, dsse_pae(payload_type, payload))
    except InvalidSignature as exc:
        raise BundleError("bundle signature is invalid") from exc
    try:
        statement = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"signed payload is not JSON: {exc}") from exc
    if statement.get("schema_version") != 1:
        raise BundleError("unsupported bundle schema_version")
    if statement.get("key_id") != key_id:
        raise BundleError("signature keyid does not match the signed key_id")
    profile, target, records = statement.get("profile"), statement.get("target"), statement.get("files")
    if not isinstance(profile, str) or not profile or target not in {"claude", "codex", "generic"}:
        raise BundleError("signed payload has invalid profile or target")
    if not isinstance(records, list) or not records:
        raise BundleError("signed payload has no files")
    expected: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise BundleError("bundle file record must be an object")
        relative = _safe_relative(record.get("path"))
        value = relative.as_posix()
        if value in expected:
            raise BundleError(f"duplicate bundle path {value}")
        expected.add(value)
        file_path = _regular_file(root, relative)
        size, digest = _file_digest(file_path)
        if record.get("size") != size or record.get("sha256") != digest:
            raise BundleError(f"bundle file digest mismatch: {value}")
    actual: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise BundleError(f"bundle contains symlink: {path.relative_to(root)}")
        if path.is_file() and path.name not in {ENVELOPE_NAME, STATE_NAME}:
            actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise BundleError(f"bundle file set mismatch: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}")
    return VerifiedBundle(
        root=root,
        profile=profile,
        target=target,
        key_id=key_id,
        digest=hashlib.sha256(payload).hexdigest(),
        files=tuple(sorted(expected)),
    )


def _state(path: Path) -> dict | None:
    try:
        return json.loads((path / STATE_NAME).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def install_bundle(bundle_root: Path, public_key: Path, destination: Path) -> InstallReceipt:
    verified = verify_bundle(bundle_root, public_key)
    if not destination.is_absolute() or destination == Path(destination.anchor):
        raise BundleError("destination must be an explicit absolute non-root path")
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise BundleError("destination must be absent or a real directory")
    parent = destination.parent
    if not parent.is_dir() or parent.is_symlink():
        raise BundleError("destination parent must already exist and must not be a symlink")
    existing = _state(destination) if destination.exists() else None
    if existing and existing.get("bundle_digest") == verified.digest:
        return InstallReceipt("unchanged", str(destination), verified.digest, verified.profile, verified.target, None)

    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.loomground-stage-", dir=parent))
    backup: Path | None = None
    moved_existing = False
    try:
        for relative in verified.files:
            source = verified.root / relative
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target, follow_symlinks=False)
        shutil.copyfile(verified.root / ENVELOPE_NAME, stage / ENVELOPE_NAME, follow_symlinks=False)
        staged = verify_bundle(stage, public_key)
        if staged.digest != verified.digest:
            raise BundleError("staged bundle differs from the verified source bundle")
        state = {
            "schema_version": 1,
            "bundle_digest": verified.digest,
            "profile": verified.profile,
            "target": verified.target,
            "key_id": verified.key_id,
        }
        (stage / STATE_NAME).write_bytes(canonical_json(state) + b"\n")
        if destination.exists():
            backup = parent / f".{destination.name}.loomground-backup-{uuid.uuid4().hex}"
            os.replace(destination, backup)
            moved_existing = True
        os.replace(stage, destination)
    except Exception:
        if moved_existing and backup is not None and not destination.exists():
            os.replace(backup, destination)
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return InstallReceipt("installed", str(destination), verified.digest, verified.profile,
                          verified.target, str(backup) if backup else None)


def rollback_install(destination: Path, backup: Path, public_key: Path) -> InstallReceipt:
    if not destination.is_absolute() or not backup.is_absolute() or destination.parent != backup.parent:
        raise BundleError("destination and backup must be absolute siblings")
    if not backup.name.startswith(f".{destination.name}.loomground-backup-"):
        raise BundleError("backup name does not belong to destination")
    verified = verify_bundle(backup, public_key)
    if destination.is_symlink() or not destination.is_dir():
        raise BundleError("current destination must be a real directory")
    displaced = destination.parent / f".{destination.name}.loomground-replaced-{uuid.uuid4().hex}"
    os.replace(destination, displaced)
    try:
        os.replace(backup, destination)
    except Exception:
        os.replace(displaced, destination)
        raise
    return InstallReceipt("rolled-back", str(destination), verified.digest, verified.profile,
                          verified.target, str(displaced))
