#!/usr/bin/env python3
"""Provider-neutral CLI for Solver's deterministic add-on advisor."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _input(argv: list[str]) -> dict:
    if len(argv) > 1:
        raise ValueError("usage: advise.py [INPUT.json]")
    text = Path(argv[0]).read_text(encoding="utf-8") if argv else sys.stdin.read()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def main(argv=None) -> int:
    try:
        from loomground_solver.addons import advise
        result = advise(_input(list(sys.argv[1:] if argv is None else argv)))
    except (ImportError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
