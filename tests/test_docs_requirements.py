# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Drift test: documented runtime Python versions match runtime-sources.json.

`runtime/runtime-sources.json` is the one source of the supported runtime
Python range. README.md, docs/SUITE.md, docs/INSTALLER.md and llms.txt restate
it for readers. This test parses every Python version those docs state and
fails when one differs from the JSON:

* a lower bound or bare version (`3.12`, `>=3.12`, `<= python` left side,
  a `py312` bundle tag) must equal `python.minimum`;
* an exclusive upper bound (`<3.13`) must equal `python.maximum_exclusive`;
* a `[3, N]` pair must be one of those two bounds.

Two statements are excluded on purpose: the installer CLI's `>=3.11`, which is
checked against `pyproject.toml` `requires-python` instead, and the fenced
block after the "Schema example" label in docs/INSTALLER.md, which shows the
lock shape with illustrative values rather than the supported policy.

G1 (this module's main drift check) sources the numeric range through
`loomground_installer.requirements.supported_runtime_python` -- the real
production loader, driven here via its `start`/`include_packaged`
injection point at a per-root synthetic module path so it resolves each
root's own (possibly temp-copied) `runtime/runtime-sources.json` -- rather
than a second, hand-rolled JSON parse. `runtime_python_label`, the one
short-label formatter also used by `loomground doctor` and the
loomground-suite hook, is checked directly: every doc must mention that
exact short label somewhere.
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loomground_installer.requirements import (  # noqa: E402
    runtime_python_label,
    supported_runtime_python,
)

DOCS = ("README.md", "docs/SUITE.md", "docs/INSTALLER.md", "llms.txt")
RUNTIME_SOURCES = "runtime/runtime-sources.json"
PYPROJECT = "pyproject.toml"
SCHEMA_EXAMPLE_LABEL = "Schema example"

VERSION = re.compile(r"(?P<op>>=|<=|==|<|>)?\s*(?<![\w.])3\.(?P<minor>\d{1,2})(?![\d])(?!\.\d)")
TAG = re.compile(r"\bpy3(?P<minor>\d{2})\b")
PAIR = re.compile(r"\[\s*3\s*,\s*(?P<minor>\d{1,2})\s*\]")


def runtime_range(root: Path) -> tuple[tuple[int, int], tuple[int, int]]:
    """Resolve the supported range for ``root`` via the real production loader.

    Points ``supported_runtime_python``'s ``start`` injection point at a
    synthetic module path under ``root`` so its parent-walk finds
    ``root/runtime/runtime-sources.json`` -- the same file this test's docs
    are checked against -- instead of re-parsing the JSON by hand.
    ``include_packaged=False`` so an installed package's own
    runtime-sources.json (if any) never shadows ``root``'s copy.
    """
    fake_module = root / "_docs_drift_probe" / "module.py"
    range_ = supported_runtime_python(start=fake_module, include_packaged=False)
    assert range_ is not None, f"could not resolve a supported Python range from {root}"
    return range_


def cli_minimum(root: Path) -> tuple[int, int]:
    text = (root / PYPROJECT).read_text(encoding="utf-8")
    match = re.search(r'^requires-python\s*=\s*">=\s*3\.(\d+)"', text, re.MULTILINE)
    assert match, "pyproject.toml requires-python is not a plain >=3.N bound"
    return (3, int(match.group(1)))


def strip_schema_example(text: str) -> tuple[str, bool]:
    """Drop the labelled schema-example fence; report whether one was found."""
    lines = text.splitlines()
    kept: list[str] = []
    index = 0
    found = False
    while index < len(lines):
        line = lines[index]
        if line.startswith(SCHEMA_EXAMPLE_LABEL):
            probe = index + 1
            while probe < len(lines) and not lines[probe].startswith("```"):
                probe += 1
            if probe < len(lines):
                end = probe + 1
                while end < len(lines) and not lines[end].startswith("```"):
                    end += 1
                found = True
                index = end + 1
                continue
        kept.append(line)
        index += 1
    return "\n".join(kept), found


def drift(root: Path) -> list[str]:
    """Return one message per documented version that disagrees with the sources."""
    minimum, maximum = runtime_range(root)
    cli = cli_minimum(root)
    problems: list[str] = []
    for relative in DOCS:
        raw = (root / relative).read_text(encoding="utf-8")
        text, found = strip_schema_example(raw)
        if relative == "docs/INSTALLER.md" and not found:
            problems.append(f"{relative}: labelled schema example block not found")
        runtime_mentions = 0
        for number, line in enumerate(text.splitlines(), 1):
            for match in VERSION.finditer(line):
                op = match.group("op")
                version = (3, int(match.group("minor")))
                where = f"{relative}:{number}: {match.group(0).strip()!r}"
                if op == ">=" and version == cli and version != minimum:
                    continue  # installer CLI requires-python statement
                if op in {"<", ">"}:
                    expected = maximum if op == "<" else None
                    if version != expected:
                        problems.append(f"{where} != exclusive maximum {maximum}")
                    continue
                runtime_mentions += 1
                if version != minimum:
                    problems.append(f"{where} != runtime minimum {minimum}")
            for match in TAG.finditer(line):
                runtime_mentions += 1
                if (3, int(match.group("minor"))) != minimum:
                    problems.append(f"{relative}:{number}: {match.group(0)!r} != runtime minimum {minimum}")
            for match in PAIR.finditer(line):
                if (3, int(match.group("minor"))) not in {minimum, maximum}:
                    problems.append(f"{relative}:{number}: {match.group(0)!r} is not a runtime bound")
        if runtime_mentions == 0:
            problems.append(f"{relative}: states no runtime Python version")
    return problems


def copy_tree(destination: Path) -> None:
    for relative in (*DOCS, RUNTIME_SOURCES, PYPROJECT):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


class DocsRequirementsTests(unittest.TestCase):
    def test_documented_runtime_python_matches_runtime_sources(self):
        self.assertEqual(drift(ROOT), [])

    def test_documented_short_label_matches_the_one_helper(self):
        # Ties every doc directly to runtime_python_label -- the single
        # short-label formatter also used by `loomground doctor` and the
        # loomground-suite hook -- rather than only to the raw
        # minimum/maximum tuple drift() already checks above.
        label = runtime_python_label(runtime_range(ROOT))
        self.assertIsNotNone(label)
        for relative in DOCS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(label, text, f"{relative} does not mention short label {label!r}")

    def test_changed_runtime_range_is_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copy_tree(root)
            self.assertEqual(drift(root), [])
            sources = root / RUNTIME_SOURCES
            data = json.loads(sources.read_text(encoding="utf-8"))
            data["python"] = {"minimum": [3, 13], "maximum_exclusive": [3, 14]}
            sources.write_text(json.dumps(data), encoding="utf-8")
            problems = drift(root)
            for relative in DOCS:
                self.assertTrue(any(p.startswith(relative) for p in problems), (relative, problems))

    def test_changed_documented_range_is_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copy_tree(root)
            readme = root / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace("`>=3.12, <3.13`", "`>=3.12, <3.14`", 1),
                encoding="utf-8",
            )
            problems = drift(root)
            self.assertTrue(any(p.startswith("README.md") and "'<3.14'" in p for p in problems), problems)

    def test_unlabelled_schema_example_is_not_exempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copy_tree(root)
            installer = root / "docs/INSTALLER.md"
            installer.write_text(
                installer.read_text(encoding="utf-8").replace(SCHEMA_EXAMPLE_LABEL, "Example", 1),
                encoding="utf-8",
            )
            problems = drift(root)
            self.assertTrue(any("[3, 15]" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
