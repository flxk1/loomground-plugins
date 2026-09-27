# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Runtime interpreter/tooling checks for ``loomground doctor``.

These checks concern the CPython interpreter and local tooling that the
Loomground *runtime bundle* installs into. The bundle installs into the
interpreter running ``loomground``; no interpreter is itself bundled, so the
version of that running interpreter is what must fall inside the supported
runtime range. This is a distinct question from ``pyproject.toml``'s
``requires-python``, which only governs the installer CLI's own supported
versions.

The supported range has exactly one source of truth on disk:
``runtime/runtime-sources.json`` at the repository root (key ``"python"``,
with ``minimum`` and ``maximum_exclusive`` two-element ``[major, minor]``
lists). This module loads and parses that one file; it never hard-codes a
second literal copy of the range. The same file is reachable in two shapes:

* from a source checkout (editable install or ``PYTHONPATH`` run), by
  walking up from this module's path to find ``runtime/runtime-sources.json``;
* from an installed, non-editable wheel, as package data at
  ``loomground_installer/runtime-sources.json`` — a build-time symlink to the
  single real file (see ``pyproject.toml`` package-data and the symlink
  itself), so the wheel embeds the same bytes without a hand-maintained copy.

If neither can be found or parsed, callers must degrade to an ``"unknown"``
status with a fix line; nothing in this module raises for that condition.

Shipping-mechanism choice (git symlink over a build-time copy step): a
symlink was kept rather than replacing it with a generated/copied file,
because setuptools' sdist/wheel builders copy through a symlink by
dereferencing it (verified: a wheel built from this checkout embeds the
real JSON bytes at ``loomground_installer/runtime-sources.json``, not a
symlink, and an installed copy of that wheel resolves the range correctly
with no source tree present). The one real risk is at *checkout* time, not
build time: on a Windows clone made without symlink support enabled
(``git config core.symlinks`` requires Developer Mode or an elevated
prompt, and is not the Windows default), git materializes the symlink as a
plain text file containing the literal target path string instead of an OS
symlink; a build performed from such a checkout would embed that path
string rather than JSON, and this module would degrade to ``"unknown"``
(it never crashes) rather than resolving the real range. Given this
project's build and CI run on macOS/Linux, that risk is accepted rather
than engineered around; a symlink-free alternative (e.g. a hatchling
``force-include`` mapping, or a small setup.py-based build-time copy hook)
would remove it, but changing the build backend or adding new build
tooling is a repo-wide decision outside a single requirement-check
feature's scope, so it is left for a human maintainer to decide if Windows
checkouts of this repository become a real build target.
"""

from __future__ import annotations

import importlib.util
import json
from importlib import resources
from pathlib import Path
from typing import Callable

RangePart = tuple[int, int]
SupportedRange = tuple[RangePart, RangePart]


def _candidate_paths(start: Path | None = None, include_packaged: bool = True) -> list[Path]:
    """Enumerate places ``runtime-sources.json`` might live, in lookup order.

    ``start`` and ``include_packaged`` are narrow, default-preserving
    injection points for tests: with both left at their defaults this
    behaves byte-for-byte as before (packaged data first, then a parent-walk
    from this module's own path). A test can point ``start`` at a synthetic
    module path to make the parent-walk begin somewhere else (e.g. under a
    ``tmp_path``) and set ``include_packaged=False`` to skip the installed
    package-data candidate, so it can drive the real loader against a
    temporary ``runtime/runtime-sources.json`` instead of the real one -- no
    new environment variable, no monkeypatching of this function itself.
    """
    candidates: list[Path] = []
    if include_packaged:
        try:
            packaged = resources.files("loomground_installer").joinpath("runtime-sources.json")
            if packaged.is_file():
                candidates.append(Path(str(packaged)))
        except (ModuleNotFoundError, FileNotFoundError, TypeError):
            pass
    here = (start if start is not None else Path(__file__)).resolve()
    for parent in here.parents:
        dev_copy = parent / "runtime" / "runtime-sources.json"
        if dev_copy.is_file():
            candidates.append(dev_copy)
            break
    return candidates


def load_runtime_sources(start: Path | None = None, include_packaged: bool = True) -> dict | None:
    """Load ``runtime-sources.json``, or ``None`` if it cannot be found or parsed.

    Never raises: callers degrade to an ``"unknown"`` doctor status instead.
    ``start``/``include_packaged`` are threaded straight through to
    ``_candidate_paths`` -- see its docstring.
    """
    for candidate in _candidate_paths(start=start, include_packaged=include_packaged):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and "python" in data:
            return data
    return None


def supported_runtime_python(start: Path | None = None, include_packaged: bool = True) -> SupportedRange | None:
    """Return ``((min_major, min_minor), (max_major_excl, max_minor_excl))``.

    Derived from the single ``runtime-sources.json`` source. Returns
    ``None`` if that source cannot be located or is malformed. ``start``/
    ``include_packaged`` are threaded straight through to
    ``load_runtime_sources`` -- see ``_candidate_paths`` for what they do.
    """
    data = load_runtime_sources(start=start, include_packaged=include_packaged)
    if not data:
        return None
    python = data.get("python")
    if not isinstance(python, dict):
        return None
    try:
        minimum = tuple(int(part) for part in python["minimum"][:2])
        maximum_exclusive = tuple(int(part) for part in python["maximum_exclusive"][:2])
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    if len(minimum) != 2 or len(maximum_exclusive) != 2:
        return None
    return (minimum, maximum_exclusive)  # type: ignore[return-value]


def format_supported_runtime_python(range_: SupportedRange) -> str:
    """Render a supported range as a human-readable ``"A.B <= python < C.D"`` string."""
    (min_major, min_minor), (max_major, max_minor) = range_
    return f"{min_major}.{min_minor} <= python < {max_major}.{max_minor}"


# Public, stable names other legs/docs/tests can import without reaching into
# doctor-check internals. ``runtime_python_range`` is a plain alias of
# ``supported_runtime_python`` (same single-source-of-truth loader, same
# ``None``-on-not-found contract).
runtime_python_range = supported_runtime_python


def runtime_python_label(range_: SupportedRange | None = None) -> str | None:
    """Render the supported range as a short, human-friendly label.

    This is the *one* short-label formatter for the supported runtime Python
    range: ``loomground doctor``, the loomground-suite SessionStart hook
    (via ``tools/render_suite_hook.py``) and the docs drift test all call
    this function rather than growing a second copy of this logic.

    * a single supported minor within one major, e.g. ``((3, 12), (3, 13))``,
      renders as ``"3.12"``;
    * a same-major span, e.g. ``((3, 12), (3, 14))``, renders as
      ``"3.12–3.13"`` -- minimum through the last supported minor
      (``maximum_exclusive``'s minor minus one), joined with an en dash
      (U+2013);
    * a cross-major range, or one whose upper bound is a bare next major
      (e.g. ``((3, 12), (4, 0))``), has no natural short minor-range form,
      so it renders as the explicit constraint string
      ``">=3.12, <4.0"``;
    * ``range_=None`` resolves the range from ``runtime-sources.json`` via
      ``supported_runtime_python()`` first, same as the other public
      formatters here.

    Returns ``None`` (never raises) if the range cannot be resolved, or is
    empty/invalid (``minimum >= maximum_exclusive``).
    """
    if range_ is None:
        range_ = supported_runtime_python()
    if range_ is None:
        return None
    minimum, maximum_exclusive = range_
    (min_major, min_minor), (max_major, max_minor) = minimum, maximum_exclusive
    if (min_major, min_minor) >= (max_major, max_minor):
        return None
    if min_major == max_major:
        if max_minor - min_minor == 1:
            return f"{min_major}.{min_minor}"
        return f"{min_major}.{min_minor}–{min_major}.{max_minor - 1}"
    return f">={min_major}.{min_minor}, <{max_major}.{max_minor}"


def default_pip_probe() -> bool:
    """Return ``True`` if pip is importable/usable for this interpreter."""
    try:
        return importlib.util.find_spec("pip") is not None
    except (ImportError, ValueError):
        return False


def python_runtime_check(
    version_info: tuple = None,
    loader: Callable[[], "SupportedRange | None"] = supported_runtime_python,
):
    """Diagnose whether the running interpreter can host the runtime bundle.

    ``version_info`` defaults to ``sys.version_info`` at call time (not at
    import time) so tests can inject a fake tuple without patching ``sys``.
    """
    from .core import Check  # deferred import: avoids a core/requirements import cycle

    if version_info is None:
        import sys
        version_info = sys.version_info

    range_ = loader()
    current = (version_info[0], version_info[1])
    if range_ is None:
        return Check(
            "python",
            "unknown",
            "could not locate runtime/runtime-sources.json to determine the supported "
            "Python runtime range",
            fix="reinstall loomground-installer so runtime-sources.json ships as package "
                "data, or run from a checkout that has runtime/runtime-sources.json",
        )
    minimum, maximum_exclusive = range_
    human_range = format_supported_runtime_python(range_)
    label = runtime_python_label(range_)
    if minimum <= current < maximum_exclusive:
        return Check(
            "python",
            "ok",
            f"running Python {current[0]}.{current[1]} is inside the supported runtime "
            f"range ({human_range})",
            fix="no action needed",
        )
    label_hint = f" (Python {label} required)" if label else ""
    return Check(
        "python",
        "unsupported",
        f"running Python {current[0]}.{current[1]} is outside the supported runtime "
        f"range ({human_range})",
        fix=f"install a CPython interpreter satisfying {human_range}{label_hint} and re-run "
            "`loomground onboard` with it",
    )


def pip_runtime_check(pip_probe: Callable[[], bool] = default_pip_probe):
    """Diagnose whether pip is usable for this interpreter."""
    from .core import Check

    try:
        available = bool(pip_probe())
    except Exception:
        available = False
    if available:
        return Check("pip", "ok", "pip is importable for this interpreter", fix="no action needed")
    return Check(
        "pip", "missing", "pip is not importable for this interpreter",
        fix="python -m ensurepip --upgrade",
    )


def git_runtime_check(which: Callable[[str], "str | None"]):
    """Diagnose whether git is on PATH.

    Informational only: git is needed solely for installing from source, so
    a missing git must never flip ``loomground doctor``'s exit code.
    """
    from .core import Check

    executable = which("git")
    if executable:
        return Check("git", "ok", executable, fix="no action needed", informational=True)
    return Check(
        "git", "missing", "git is not on PATH",
        fix="install git only if installing from source",
        informational=True,
    )
