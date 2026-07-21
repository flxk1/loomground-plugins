#!/usr/bin/env python3
"""reason-governance-rules — verify a reasoning request through the installed kernel.

Passes a provider-neutral reasoning request to loomground_solver's service and returns
its verdict (PASS/VIOLATION/ESCALATE) and decision space. No copied reasoner.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

def _input(argv):
    text = sys.stdin.read() if (not argv or argv[0] == "-") else Path(argv[0]).read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object (a reasoning request)")
    return value

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        request = _input(argv)
        from loomground_solver import default_service
        result = default_service().verify(request)
    except (ImportError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
