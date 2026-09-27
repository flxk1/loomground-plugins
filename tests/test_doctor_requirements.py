# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Tests for the python/pip/git requirement checks in `loomground doctor`.

`doctor()` (host checks) and `doctor_requirements()` (interpreter/tooling
checks) are deliberately separate functions returning separate tuples --
see `core.py` for the rationale. These tests exercise `doctor_requirements`
directly, plus the `requirements` module's range loader/formatter in
isolation (including a mutation-style test that swaps in a different range
and confirms the verdict follows it).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loomground_installer.core import doctor, doctor_requirements  # noqa: E402
from loomground_installer.requirements import (  # noqa: E402
    format_supported_runtime_python,
    python_runtime_check,
    runtime_python_label,
    runtime_python_range,
    supported_runtime_python,
)


def fake_which(*available):
    paths = {name: f"/test/bin/{name}" for name in available}
    return paths.get


def checks_by_name(checks):
    return {check.name: check for check in checks}


class SupportedRuntimeRangeTests(unittest.TestCase):
    def test_loader_matches_runtime_sources_json_independently(self):
        data = json.loads((ROOT / "runtime" / "runtime-sources.json").read_text(encoding="utf-8"))
        expected = (
            tuple(data["python"]["minimum"][:2]),
            tuple(data["python"]["maximum_exclusive"][:2]),
        )
        self.assertEqual(supported_runtime_python(), expected)
        # runtime_python_range is the public alias other legs/docs should use.
        self.assertEqual(runtime_python_range(), expected)

    def test_loader_resolves_from_installed_package_data_without_source_tree(self):
        # Proves the range is reachable from packaged data alone, not only
        # from a source checkout: the symlinked package-data copy at
        # src/loomground_installer/runtime-sources.json must itself resolve
        # to the same content as the single real file.
        packaged = ROOT / "src" / "loomground_installer" / "runtime-sources.json"
        self.assertTrue(packaged.is_file(), "package-data copy must exist and be readable")
        packaged_data = json.loads(packaged.read_text(encoding="utf-8"))
        source_data = json.loads((ROOT / "runtime" / "runtime-sources.json").read_text(encoding="utf-8"))
        self.assertEqual(packaged_data, source_data)

    def test_formatter_is_human_readable(self):
        text = format_supported_runtime_python(((3, 12), (3, 13)))
        self.assertIn("3.12", text)
        self.assertIn("3.13", text)

    def test_short_label_single_minor(self):
        self.assertEqual(runtime_python_label(((3, 12), (3, 13))), "3.12")

    def test_short_label_same_major_span_uses_en_dash(self):
        self.assertEqual(runtime_python_label(((3, 12), (3, 14))), "3.12–3.13")

    def test_short_label_cross_major_uses_explicit_constraint_string(self):
        self.assertEqual(runtime_python_label(((3, 12), (4, 0))), ">=3.12, <4.0")

    def test_short_label_invalid_or_empty_range_is_none(self):
        self.assertIsNone(runtime_python_label(((3, 13), (3, 12))))  # inverted
        self.assertIsNone(runtime_python_label(((3, 12), (3, 12))))  # empty

    def test_mutation_a_different_range_changes_the_verdict(self):
        # Point python_runtime_check's loader at a different (higher)
        # range and confirm the verdict tracks that data rather than any
        # cached/hard-coded value -- mirrors what a mutated on-disk
        # runtime-sources.json would produce, without needing to fight
        # importlib.resources caching by writing to a real temp file.
        def mutated_loader():
            return ((3, 20), (3, 21))

        below_new_minimum = python_runtime_check((3, 12, 0), loader=mutated_loader)
        self.assertEqual(below_new_minimum.status, "unsupported")
        self.assertIn("3.20", below_new_minimum.detail)

        inside_new_range = python_runtime_check((3, 20, 0), loader=mutated_loader)
        self.assertEqual(inside_new_range.status, "ok")

    def test_mutation_a_different_range_changes_the_verdict_via_real_loader(self):
        # Unlike the lambda-injection test above, this drives the *real*
        # file-finding/parsing path: _candidate_paths()'s parent-walk,
        # load_runtime_sources()'s JSON parsing, and
        # supported_runtime_python()'s range extraction, via a genuine
        # <tmp>/runtime/runtime-sources.json and a genuine
        # <tmp>/a/b/module.py start point -- no lambda/monkeypatched
        # _candidate_paths. It uses the running interpreter's own version so
        # it's meaningful under whatever Python runs the suite: the verdict
        # under the real repo's default range (baseline) must differ from
        # the verdict once the loader is pointed at a temp range file whose
        # bounds are built to bracket the current interpreter exactly.
        current_major, current_minor = sys.version_info[:2]
        baseline = python_runtime_check(sys.version_info, loader=supported_runtime_python)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runtime_dir = tmp_path / "runtime"
            runtime_dir.mkdir()
            different_range = {
                "python": {
                    "minimum": [current_major, current_minor],
                    "maximum_exclusive": [current_major, current_minor + 1],
                }
            }
            (runtime_dir / "runtime-sources.json").write_text(
                json.dumps(different_range), encoding="utf-8"
            )
            fake_module = tmp_path / "a" / "b" / "module.py"

            def file_driven_loader():
                return supported_runtime_python(start=fake_module, include_packaged=False)

            # The real loader must resolve the temp file's range, not the
            # repository's real runtime-sources.json.
            self.assertEqual(
                file_driven_loader(), ((current_major, current_minor), (current_major, current_minor + 1))
            )

            mutated = python_runtime_check(sys.version_info, loader=file_driven_loader)

        self.assertEqual(mutated.status, "ok")
        self.assertNotEqual(mutated.status, baseline.status)


class DoctorRequirementsPythonCheckTests(unittest.TestCase):
    def test_python_3_10_is_unsupported(self):
        checks = doctor_requirements(fake_which("git"), version_info=(3, 10, 0))
        check = checks_by_name(checks)["python"]
        self.assertEqual(check.status, "unsupported")
        self.assertTrue(check.fix)

    def test_python_3_11_is_unsupported(self):
        checks = doctor_requirements(fake_which("git"), version_info=(3, 11, 0))
        check = checks_by_name(checks)["python"]
        self.assertEqual(check.status, "unsupported")
        self.assertTrue(check.fix)

    def test_python_3_12_is_ok(self):
        checks = doctor_requirements(fake_which("git"), version_info=(3, 12, 0))
        check = checks_by_name(checks)["python"]
        self.assertEqual(check.status, "ok")
        self.assertTrue(check.fix)

    def test_python_3_13_is_unsupported(self):
        checks = doctor_requirements(fake_which("git"), version_info=(3, 13, 0))
        check = checks_by_name(checks)["python"]
        self.assertEqual(check.status, "unsupported")
        self.assertTrue(check.fix)

    def test_unlocatable_range_reports_unknown_never_crashes(self):
        checks = doctor_requirements(fake_which("git"), version_info=(3, 12, 0))
        # Sanity: the real loader currently finds the range in this tree.
        self.assertNotEqual(checks_by_name(checks)["python"].status, "unknown")

        check = python_runtime_check((3, 12, 0), loader=lambda: None)
        self.assertEqual(check.status, "unknown")
        self.assertTrue(check.fix)


class DoctorRequirementsPipCheckTests(unittest.TestCase):
    def test_pip_probe_failing_reports_missing(self):
        checks = doctor_requirements(fake_which("git"), pip_probe=lambda: False)
        check = checks_by_name(checks)["pip"]
        self.assertEqual(check.status, "missing")
        self.assertTrue(check.fix)

    def test_pip_probe_succeeding_reports_ok(self):
        checks = doctor_requirements(fake_which("git"), pip_probe=lambda: True)
        check = checks_by_name(checks)["pip"]
        self.assertEqual(check.status, "ok")
        self.assertTrue(check.fix)


class DoctorRequirementsGitCheckTests(unittest.TestCase):
    def test_missing_git_reports_missing_but_does_not_fail_exit_code(self):
        checks = doctor_requirements(
            fake_which(), version_info=(3, 12, 0), pip_probe=lambda: True,
        )
        check = checks_by_name(checks)["git"]
        self.assertEqual(check.status, "missing")
        self.assertTrue(check.informational)
        self.assertTrue(check.fix)
        # All other checks are healthy; git alone must not flip the exit code.
        self.assertTrue(all(
            c.informational or c.status in {"ok", "unknown"} for c in checks
        ))

    def test_present_git_reports_ok(self):
        checks = doctor_requirements(fake_which("git"))
        check = checks_by_name(checks)["git"]
        self.assertEqual(check.status, "ok")
        self.assertTrue(check.informational)


class DoctorRequirementsJsonOutputTests(unittest.TestCase):
    def test_json_output_includes_new_checks_and_fix_lines(self):
        checks = doctor_requirements(fake_which(), version_info=(3, 10, 0), pip_probe=lambda: False)
        payload = [check.__dict__ for check in checks]
        by_name = {entry["name"]: entry for entry in payload}
        for name in ("python", "pip", "git"):
            self.assertIn(name, by_name)
            self.assertIn("fix", by_name[name])
            self.assertTrue(by_name[name]["fix"])


class DoctorHostAndRequirementChecksAreSeparateTests(unittest.TestCase):
    def test_doctor_does_not_include_requirement_checks(self):
        checks = doctor(["claude"], fake_which("claude"))
        names = {check.name for check in checks}
        self.assertFalse(names & {"python", "pip", "git"})

    def test_doctor_requirements_does_not_include_host_checks(self):
        checks = doctor_requirements(fake_which("git"))
        names = {check.name for check in checks}
        self.assertFalse(any(name.startswith("host-") for name in names))
        self.assertNotIn("runtime", names)


if __name__ == "__main__":
    unittest.main()
