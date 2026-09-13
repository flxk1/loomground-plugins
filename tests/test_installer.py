# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
import json
import os
import base64
import hashlib
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loomground_installer.bundle import (
    ENVELOPE_NAME, PAYLOAD_TYPE, BundleError, canonical_json, dsse_pae,
    install_bundle, rollback_install, verify_bundle,
)
from loomground_installer.core import InstallerError, create_plan, doctor, load_profiles, resolve_hosts


def fake_which(*available):
    paths = {name: f"/test/bin/{name}" for name in available}
    return paths.get


def keypair(root):
    private = Ed25519PrivateKey.generate()
    private_path, public_path = root / "private.pem", root / "public.pem"
    private_path.write_bytes(private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    public_path.write_bytes(private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    return private, private_path, public_path


def signed_bundle(root, private, content=b"one", profile="compliance"):
    path = root / "plugins" / "example" / "skills" / "example" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    record = {"path": path.relative_to(root).as_posix(), "size": len(content),
              "sha256": hashlib.sha256(content).hexdigest()}
    payload = canonical_json({"schema_version": 1, "profile": profile, "target": "codex",
                              "key_id": "test-release", "files": [record]})
    signature = private.sign(dsse_pae(PAYLOAD_TYPE, payload))
    envelope = {
        "payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode(),
        "signatures": [{"keyid": "test-release", "sig": base64.b64encode(signature).decode()}],
    }
    (root / ENVELOPE_NAME).write_text(json.dumps(envelope), encoding="utf-8")
    return hashlib.sha256(payload).hexdigest()


class InstallerTests(unittest.TestCase):
    def test_full_profile_is_exact_marketplace(self):
        profiles = load_profiles()["profiles"]
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(set(profiles["full"]), {entry["name"] for entry in marketplace["plugins"]})
        for names in profiles.values():
            self.assertEqual(names, sorted(set(names)))
            self.assertLessEqual(set(names), set(profiles["full"]))

    def test_wheel_metadata_declares_the_cli(self):
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertEqual(metadata["project"]["scripts"]["loomground"], "loomground_installer.cli:main")
        self.assertEqual(metadata["project"]["dependencies"], ["cryptography>=46,<51"])

    def test_auto_detects_hosts_without_executing_them(self):
        self.assertEqual(resolve_hosts(["auto"], fake_which("claude", "codex")), ("claude", "codex"))
        self.assertEqual(resolve_hosts([], fake_which("codex")), ("codex",))
        with self.assertRaisesRegex(InstallerError, "no supported host"):
            resolve_hosts([], fake_which())

    def test_plan_is_explicitly_non_mutating(self):
        plan = create_plan("compliance", ["claude"], fake_which("claude"))
        self.assertFalse(plan.mutates_system)
        self.assertEqual(plan.enforcement_mode, "advisory")
        self.assertEqual(plan.operations[0].kind, "runtime")
        self.assertFalse(any(operation.executable for operation in plan.operations))
        self.assertEqual(
            [operation.kind for operation in plan.operations[1:]],
            ["marketplace"] + ["plugin"] * len(plan.plugins),
        )

    def test_doctor_reads_codex_config_without_changing_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / ".codex" / "config.toml"
            config.parent.mkdir()
            config.write_text('[mcp_servers.loomground]\ncommand = "loomground-mcp"\nargs = ["serve", "--transport", "stdio"]\n')
            before = config.read_bytes()
            checks = doctor(["codex"], fake_which("codex", "loomground-mcp"), environment={}, home=root)
            self.assertEqual({check.name: check.status for check in checks}["codex-mcp"], "ok")
            self.assertEqual(config.read_bytes(), before)

    def test_cli_plan_json_makes_no_home_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = dict(os.environ)
            environment["HOME"] = temporary
            environment["PYTHONPATH"] = str(ROOT / "src")
            result = subprocess.run(
                [sys.executable, "-m", "loomground_installer.cli", "plan", "--profile", "core", "--host", "codex", "--json"],
                cwd=ROOT, env=environment, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(any(Path(temporary).iterdir()))
            self.assertFalse(json.loads(result.stdout)["mutates_system"])

    def test_signed_bundle_verifies_and_tampering_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private, _, public = keypair(root)
            bundle = root / "bundle"
            bundle.mkdir()
            digest = signed_bundle(bundle, private)
            self.assertEqual(verify_bundle(bundle, public).digest, digest)
            skill = bundle / "plugins/example/skills/example/SKILL.md"
            skill.write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(BundleError, "digest mismatch"):
                verify_bundle(bundle, public)

    def test_unsigned_key_id_relabel_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private, _, public = keypair(root)
            bundle = root / "bundle"
            bundle.mkdir()
            signed_bundle(bundle, private)
            envelope_path = bundle / ENVELOPE_NAME
            envelope = json.loads(envelope_path.read_text())
            envelope["signatures"][0]["keyid"] = "attacker-label"
            envelope_path.write_text(json.dumps(envelope))
            with self.assertRaisesRegex(BundleError, "signed key_id"):
                verify_bundle(bundle, public)

    def test_signed_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private, _, public = keypair(root)
            bundle = root / "bundle"
            bundle.mkdir()
            payload = canonical_json({
                "schema_version": 1, "profile": "compliance", "target": "codex",
                "key_id": "test-release",
                "files": [{"path": "../escape", "size": 0, "sha256": hashlib.sha256(b"").hexdigest()}],
            })
            envelope = {
                "payloadType": PAYLOAD_TYPE,
                "payload": base64.b64encode(payload).decode(),
                "signatures": [{
                    "keyid": "test-release",
                    "sig": base64.b64encode(private.sign(dsse_pae(PAYLOAD_TYPE, payload))).decode(),
                }],
            }
            (bundle / ENVELOPE_NAME).write_text(json.dumps(envelope))
            with self.assertRaisesRegex(BundleError, "unsafe bundle path"):
                verify_bundle(bundle, public)

    def test_transaction_is_idempotent_and_rollback_retains_replaced_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private, _, public = keypair(root)
            first, second = root / "first", root / "second"
            first.mkdir(); second.mkdir()
            first_digest = signed_bundle(first, private, b"one")
            signed_bundle(second, private, b"two")
            destination = root / "installed"

            receipt = install_bundle(first, public, destination)
            self.assertEqual(receipt.status, "installed")
            self.assertIsNone(receipt.backup)
            unchanged = install_bundle(first, public, destination)
            self.assertEqual(unchanged.status, "unchanged")

            replaced = install_bundle(second, public, destination)
            self.assertIsNotNone(replaced.backup)
            self.assertEqual((destination / "plugins/example/skills/example/SKILL.md").read_bytes(), b"two")
            rolled = rollback_install(destination, Path(replaced.backup), public)
            self.assertEqual(rolled.status, "rolled-back")
            self.assertEqual(rolled.bundle_digest, first_digest)
            self.assertEqual((destination / "plugins/example/skills/example/SKILL.md").read_bytes(), b"one")
            self.assertTrue(Path(rolled.backup).is_dir())

    def test_invalid_bundle_never_changes_existing_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private, _, public = keypair(root)
            bundle = root / "bundle"
            bundle.mkdir()
            signed_bundle(bundle, private)
            (bundle / "plugins/example/skills/example/SKILL.md").write_text("tampered")
            destination = root / "installed"
            destination.mkdir()
            marker = destination / "keep"
            marker.write_text("original")
            with self.assertRaises(BundleError):
                install_bundle(bundle, public, destination)
            self.assertEqual(marker.read_text(), "original")
            self.assertEqual(list(destination.iterdir()), [marker])

    def test_destination_must_be_explicit_absolute_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private, _, public = keypair(root)
            bundle = root / "bundle"
            bundle.mkdir()
            signed_bundle(bundle, private)
            with self.assertRaisesRegex(BundleError, "explicit absolute"):
                install_bundle(bundle, public, Path("relative"))

    def test_profile_builder_emits_a_verifiable_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, private, public = keypair(root)
            output = root / "compliance-bundle"
            result = subprocess.run([
                sys.executable, "tools/build_profile_bundle.py",
                "--profile", "compliance", "--target", "codex",
                "--output", str(output), "--signing-key", str(private),
                "--key-id", "test-release",
            ], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            verified = verify_bundle(output, public)
            self.assertEqual(verified.profile, "compliance")
            self.assertEqual(verified.target, "codex")
            self.assertEqual(
                {path.name for path in (output / "plugins").iterdir()},
                set(load_profiles()["profiles"]["compliance"]),
            )


if __name__ == "__main__":
    unittest.main()
