#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Render (or check) the label line embedded in the loomground-suite hook.

``plugins/loomground-suite/hooks/session-start.sh`` is a POSIX ``sh``
SessionStart hook that has no Python dependency at run time (Python's
absence is one of the conditions it reports), so it cannot itself parse
``runtime/runtime-sources.json`` or import
``loomground_installer.requirements``. Instead, this script generates its
``PYTHON_RANGE_LABEL="..."`` line -- naming the whole supported range, not
just its lower bound -- from
``loomground_installer.requirements.runtime_python_label`` -- the single
short-label formatter also used by ``loomground doctor`` and
``tests/test_docs_requirements.py`` -- so there is exactly one place that
formats that label.

Usage::

    tools/render_suite_hook.py [--runtime-sources PATH] [--hook PATH]
    tools/render_suite_hook.py --check [--runtime-sources PATH] [--hook PATH]

Without ``--check``, the hook file at ``--hook`` is rewritten in place with
its label line brought in sync with ``--runtime-sources``. With ``--check``,
nothing is written; the script exits ``0`` if the hook's label line already
matches, and ``1`` (with a message on stderr) if it does not.

Both paths default to this repository's real files, so plain
``tools/render_suite_hook.py --check`` is what CI/tests run against the
committed hook. Tests exercise both flags against temporary copies (a temp
``runtime-sources.json`` and a temp copy of the hook script) to drive the
real generation path without touching the committed files.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loomground_installer.requirements import (  # noqa: E402
    runtime_python_label,
    supported_runtime_python,
)

DEFAULT_RUNTIME_SOURCES = ROOT / "runtime" / "runtime-sources.json"
DEFAULT_HOOK = ROOT / "plugins" / "loomground-suite" / "hooks" / "session-start.sh"

LABEL_LINE_RE = re.compile(r'^PYTHON_RANGE_LABEL="[^"]*"$', re.MULTILINE)


def label_for_runtime_sources(runtime_sources: Path) -> str:
    """Resolve the short label straight from an arbitrary runtime-sources.json.

    Reuses the production loader (``supported_runtime_python``) rather than
    parsing the JSON a second time: its ``start`` injection point is pointed
    at a synthetic module path one level under the directory that contains
    the ``runtime/`` folder holding ``runtime_sources``, so the loader's own
    parent-walk finds that exact file. ``include_packaged=False`` so an
    installed package's own ``runtime-sources.json`` never shadows the one
    the caller asked for.
    """
    runtime_sources = runtime_sources.resolve()
    runtime_dir = runtime_sources.parent
    if runtime_dir.name != "runtime":
        raise ValueError(
            f"expected a '.../runtime/runtime-sources.json' path, got {runtime_sources}"
        )
    base = runtime_dir.parent
    fake_module = base / "_render_suite_hook_probe" / "module.py"
    range_ = supported_runtime_python(start=fake_module, include_packaged=False)
    if range_ is None:
        raise ValueError(f"could not resolve a supported Python range from {runtime_sources}")
    label = runtime_python_label(range_)
    if label is None:
        raise ValueError(f"runtime_python_label returned None for range {range_}")
    return label


def render(hook_text: str, label: str) -> str:
    """Return ``hook_text`` with its label line set to ``label``."""
    new_line = f'PYTHON_RANGE_LABEL="{label}"'
    new_text, count = LABEL_LINE_RE.subn(new_line, hook_text)
    if count != 1:
        raise ValueError(
            'expected exactly one PYTHON_RANGE_LABEL="..." line in the hook script, '
            f"found {count}"
        )
    return new_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-sources", type=Path, default=DEFAULT_RUNTIME_SOURCES)
    parser.add_argument("--hook", type=Path, default=DEFAULT_HOOK)
    parser.add_argument(
        "--check", action="store_true",
        help="verify the hook's label line is in sync without writing; exit 1 on drift",
    )
    args = parser.parse_args(argv)

    label = label_for_runtime_sources(args.runtime_sources)
    current_text = args.hook.read_text(encoding="utf-8")
    rendered = render(current_text, label)

    if args.check:
        if rendered != current_text:
            print(
                f"{args.hook}: PYTHON_RANGE_LABEL is out of sync with "
                f"{args.runtime_sources} (expected label {label!r})",
                file=sys.stderr,
            )
            return 1
        return 0

    args.hook.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
