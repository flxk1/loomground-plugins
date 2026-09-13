# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import build_runtime_bundle  # noqa: E402
from loomground_installer.bundle import BundleError  # noqa: E402
from loomground_installer.runtime_bundle import (  # noqa: E402
    install_runtime_bundle,
    rollback_runtime_install,
    validate_runtime_lock,
    verify_runtime_bundle,
)


def keypair(root: Path) -> tuple[Path, Path]:
    private = Ed25519PrivateKey.generate()
    private_path = root / "private.pem"
    public_path = root / "public.pem"
    private_path.write_bytes(private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    public_path.write_bytes(private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    return private_path, public_path


def wheel(
    root: Path,
    name: str = "loomground-mcp",
    version: str = "1.0.0",
    requires: tuple[str, ...] = (),
    server: str = "def main():\n    print('loomground runtime probe')\n    return 0\n",
) -> tuple[str, str]:
    distribution = name.replace("-", "_")
    filename = f"{distribution}-{version}-py3-none-any.whl"
    metadata = ["Metadata-Version: 2.1", f"Name: {name}", f"Version: {version}"]
    metadata.extend(f"Requires-Dist: {requirement}" for requirement in requires)
    dist_info = f"{distribution}-{version}.dist-info"
    with zipfile.ZipFile(root / filename, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("loomground_mcp/__init__.py", "")
        archive.writestr("loomground_mcp/server.py", server)
        archive.writestr(f"{dist_info}/METADATA", "\n".join(metadata) + "\n")
        archive.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: loomground-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        archive.writestr(f"{dist_info}/RECORD", "")
    digest = hashlib.sha256((root / filename).read_bytes()).hexdigest()
    return filename, digest


def lock(filename: str, digest: str, *, version: str = "1.0.0", platforms=None) -> dict:
    return {
        "schema_version": 1,
        "runtime": {
            "name": "loomground-mcp",
            "version": version,
            "entry_point": "loomground_mcp.server:main",
        },
        "python": {"minimum": [3, 11], "maximum_exclusive": [3, 15]},
        "platforms": platforms or ["any"],
        "packages": [{
            "name": "loomground-mcp",
            "version": version,
            "wheel": filename,
            "sha256": digest,
            "source": {
                "source": "git",
                "url": "https://github.com/flxk1/loomground-mcp",
                "commit": "a" * 40,
            },
        }],
    }


class RuntimeBundleTests(unittest.TestCase):
    def _build(self, root: Path, version="1.0.0", requires=(), server=None, platforms=None):
        keys = root / f"keys-{version}"
        keys.mkdir()
        private, public = keypair(keys)
        wheelhouse = root / f"wheels-{version}"
        wheelhouse.mkdir()
        kwargs = {"version": version, "requires": requires}
        if server is not None:
            kwargs["server"] = server
        filename, digest = wheel(wheelhouse, **kwargs)
        lock_path = root / f"lock-{version}.json"
        lock_path.write_text(json.dumps(lock(filename, digest, version=version, platforms=platforms)))
        output = root / f"bundle-{version}"
        build_runtime_bundle.build(lock_path, wheelhouse, output, private, "test-runtime")
        return output, public

    def test_signed_runtime_installs_offline_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, public = self._build(root)
            verified = verify_runtime_bundle(bundle, public)
            self.assertEqual(verified.runtime_name, "loomground-mcp")
            self.assertEqual(len(verified.packages), 1)
            destination = root / "installed"
            receipt = install_runtime_bundle(bundle, public, destination)
            self.assertEqual(receipt.status, "installed")
            self.assertTrue((destination / "bundle/runtime-lock.json").is_file())
            self.assertTrue((destination / "bin/loomground-mcp.cmd").is_file())
            result = subprocess.run(
                [str(destination / "bin/loomground-mcp")], text=True, capture_output=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "loomground runtime probe")
            unchanged = install_runtime_bundle(bundle, public, destination)
            self.assertEqual(unchanged.status, "unchanged")
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(ROOT / "src")
            cli = subprocess.run(
                [
                    sys.executable, "-m", "loomground_installer.cli", "runtime", "verify",
                    str(bundle), "--public-key", str(public),
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )
            self.assertEqual(cli.returncode, 0, cli.stderr)
            self.assertEqual(json.loads(cli.stdout)["runtime"], "loomground-mcp")

    def test_wheel_tampering_and_dependency_omission_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, public = self._build(root, requires=("missing-plane>=1",))
            with self.assertRaisesRegex(BundleError, "omits dependency missing-plane"):
                verify_runtime_bundle(bundle, public)
            wheel_path = next((bundle / "wheels").glob("*.whl"))
            wheel_path.write_bytes(wheel_path.read_bytes() + b"tampered")
            with self.assertRaisesRegex(BundleError, "digest mismatch"):
                verify_runtime_bundle(bundle, public)

    def test_failed_import_probe_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, public = self._build(root, server="import absent_runtime_module\ndef main(): return 0\n")
            destination = root / "installed"
            destination.mkdir()
            marker = destination / "keep"
            marker.write_text("original")
            with self.assertRaisesRegex(BundleError, "import probe failed"):
                install_runtime_bundle(bundle, public, destination)
            self.assertEqual(marker.read_text(), "original")
            self.assertFalse(any(root.glob(".installed.loomground-runtime-stage-*")))

    def test_replacement_and_rollback_reverify_the_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, first_public = self._build(root, "1.0.0")
            second, second_public = self._build(root, "1.1.0")
            destination = root / "installed"
            install_runtime_bundle(first, first_public, destination)
            replaced = install_runtime_bundle(second, second_public, destination)
            self.assertEqual(replaced.version, "1.1.0")
            rolled = rollback_runtime_install(destination, Path(replaced.backup), first_public)
            self.assertEqual(rolled.status, "rolled-back")
            self.assertEqual(rolled.version, "1.0.0")

    def test_incompatible_platform_is_rejected_before_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, public = self._build(root, platforms=["definitely-not-this-platform"])
            with self.assertRaisesRegex(BundleError, "does not support platform"):
                install_runtime_bundle(bundle, public, root / "installed")

    def test_lock_rejects_invalid_versions_and_provenance_urls(self):
        with tempfile.TemporaryDirectory() as temporary:
            wheelhouse = Path(temporary)
            filename, digest = wheel(wheelhouse)
            invalid_version = lock(filename, digest, version="not a version")
            with self.assertRaisesRegex(BundleError, "invalid runtime version"):
                validate_runtime_lock(invalid_version)
            invalid_source = lock(filename, digest)
            invalid_source["packages"][0]["source"]["url"] = "https://user@example.test/repo#ref"
            with self.assertRaisesRegex(BundleError, "provenance must use HTTPS"):
                validate_runtime_lock(invalid_source)


if __name__ == "__main__":
    unittest.main()
