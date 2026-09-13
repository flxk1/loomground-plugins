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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import build_runtime_bundle  # noqa: E402
from assemble_runtime_release import load_sources, verify_root_pins  # noqa: E402
from generate_ephemeral_release_key import generate  # noqa: E402
from lock_runtime_third_party import validate_hash_lock  # noqa: E402
from loomground_installer.bundle import BundleError  # noqa: E402
from loomground_installer.cli import main as cli_main  # noqa: E402
from loomground_installer.onboarding import onboard  # noqa: E402
from loomground_installer.runtime_bundle import (  # noqa: E402
    install_runtime_bundle,
    rollback_runtime_install,
    runtime_sbom,
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
            "license": "Apache-2.0",
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
            self.assertTrue((bundle / "runtime-sbom.cdx.json").is_file())
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

    def test_onboarding_installs_runtime_and_emits_host_and_maker_handoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, public = self._build(root)
            destination = root / "runtime"
            output = root / "onboarding"
            result = onboard(
                bundle,
                public,
                destination,
                output,
                ["claude", "codex", "cursor"],
                makers=["Legal Plugin", "Continuous Monitoring"],
            )
            self.assertEqual(result.status, "ready")
            manifest = json.loads((output / "onboarding.json").read_text())
            self.assertFalse(manifest["host_configuration_modified"])
            self.assertFalse(manifest["secret_material_included"])
            self.assertEqual([maker["role"] for maker in manifest["makers"]], ["maker", "maker"])
            self.assertTrue((output / "hosts/claude.mcp.json").is_file())
            self.assertTrue((output / "hosts/codex.mcp.toml").is_file())
            self.assertIn(
                str(destination / "bin/loomground-mcp"),
                (output / "hosts/cursor.mcp.json").read_text(),
            )
            self.assertIn("Hard enforcement", (output / "NEXT-STEPS.md").read_text())

    def test_onboarding_rejects_remote_host_without_endpoint_before_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, public = self._build(root)
            destination = root / "runtime"
            with self.assertRaisesRegex(BundleError, "require --server-url"):
                onboard(bundle, public, destination, root / "output", ["openai"])
            self.assertFalse(destination.exists())

    def test_onboarding_remote_handoff_contains_endpoint_but_no_secret(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, public = self._build(root)
            output = root / "output"
            onboard(
                bundle,
                public,
                root / "runtime",
                output,
                ["openai", "n8n"],
                server_url="https://loomground.example/mcp",
            )
            openai = json.loads((output / "hosts/openai.mcp-tool.json").read_text())
            n8n = json.loads((output / "hosts/n8n.mcp-client.json").read_text())
            self.assertEqual(openai["server_url"], "https://loomground.example/mcp")
            self.assertEqual(n8n["parameters"]["SSE Endpoint"], "https://loomground.example/mcp")
            for rendered in (openai, n8n):
                serialized = json.dumps(rendered).casefold()
                self.assertNotIn('"token":', serialized)
                self.assertNotIn('"authorization":', serialized)
                self.assertNotIn("bearer ey", serialized)

    def test_interactive_onboarding_cancel_makes_no_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "runtime"
            output = root / "output"
            answers = [
                str(root / "bundle"),
                str(root / "public.pem"),
                str(destination),
                str(output),
                "claude,cursor",
                "Legal Plugin",
                "no",
            ]
            with (
                patch("loomground_installer.cli.sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=answers),
            ):
                self.assertEqual(cli_main(["onboard"]), 1)
            self.assertFalse(destination.exists())
            self.assertFalse(output.exists())

    def test_onboarding_cli_does_not_overwrite_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, public = self._build(root)
            output = root / "output"
            output.mkdir()
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(ROOT / "src")
            cli = subprocess.run(
                [
                    sys.executable, "-m", "loomground_installer.cli", "onboard",
                    "--bundle", str(bundle), "--public-key", str(public),
                    "--destination", str(root / "runtime"), "--output", str(output),
                    "--host", "claude", "--yes",
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(cli.returncode, 0)
            self.assertIn("must not already exist", cli.stderr)
            self.assertFalse((root / "runtime").exists())

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

    def test_concurrent_identical_installs_serialize_without_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, public = self._build(root)
            destination = root / "installed"
            with ThreadPoolExecutor(max_workers=2) as executor:
                receipts = list(executor.map(
                    lambda _: install_runtime_bundle(bundle, public, destination),
                    range(2),
                ))
            self.assertEqual(sorted(receipt.status for receipt in receipts), ["installed", "unchanged"])
            self.assertTrue(all(receipt.backup is None for receipt in receipts))
            self.assertFalse(any(root.glob(".installed.loomground-runtime-stage-*")))
            self.assertFalse(any(root.glob(".installed.loomground-runtime-backup-*")))
            self.assertEqual(
                verify_runtime_bundle(destination / "bundle", public).digest,
                receipts[0].bundle_digest,
            )

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
            invalid_license = lock(filename, digest)
            invalid_license["packages"][0]["license"] = "not a SPDX license"
            with self.assertRaisesRegex(BundleError, "invalid license expression"):
                validate_runtime_lock(invalid_license)

    def test_committed_release_sources_and_hash_locks_validate_offline(self):
        minimum, maximum, root, sources = load_sources(ROOT / "runtime/runtime-sources.json")
        self.assertEqual((minimum, maximum), ((3, 12), (3, 13)))
        self.assertEqual(root, "loomground-mcp")
        self.assertEqual(len(sources), 32)
        for stem in ("third-party-requirements", "build-requirements"):
            validate_hash_lock(ROOT / f"runtime/{stem}.in", ROOT / f"runtime/{stem}.txt")

    def test_runtime_sbom_is_deterministic_and_github_attest_detectable(self):
        document = runtime_sbom(lock("demo-1.0-py3-none-any.whl", "a" * 64))
        self.assertEqual(document, runtime_sbom(lock("demo-1.0-py3-none-any.whl", "a" * 64)))
        self.assertEqual(document["bomFormat"], "CycloneDX")
        self.assertEqual(document["specVersion"], "1.6")
        self.assertRegex(
            document["serialNumber"],
            r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        )

    def test_root_pin_parity_and_ephemeral_key_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkout = root / "mcp"
            checkout.mkdir()
            checkout.joinpath("requirements-dev.txt").write_text(
                "plane @ git+https://github.com/flxk1/plane@" + "b" * 40 + "\n",
                encoding="utf-8",
            )
            sources = (
                {"name": "loomground-mcp", "url": "https://github.com/flxk1/loomground-mcp.git", "commit": "a" * 40},
                {"name": "plane", "url": "https://github.com/flxk1/plane.git", "commit": "b" * 40},
            )
            verify_root_pins(checkout, sources, "loomground-mcp")
            generated = generate(root, "runtime-test")
            self.assertTrue(Path(generated["private_key"]).is_file())
            self.assertTrue(Path(generated["public_key"]).is_file())
            self.assertTrue(generated["key_id"].startswith("loomground-runtime-ephemeral-"))


if __name__ == "__main__":
    unittest.main()
