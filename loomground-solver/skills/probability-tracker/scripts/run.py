#!/usr/bin/env python3
"""Probability tracker — thin wrapper over the installed loomground_solver kernel.

Delegates to a named reasoning method in loomground_solver; it holds no copied
decision logic. Input is a JSON object of the method's keyword arguments, with an
optional "method" override. Fails closed if the kernel is absent.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

DEFAULT_METHOD = "bayesian_update"

def _input(argv):
    text = sys.stdin.read() if (not argv or argv[0] == "-") else Path(argv[0]).read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        payload = _input(argv)
        from loomground_solver import method  # installed kernel; never re-implemented
        name = payload.pop("method", DEFAULT_METHOD)
        result = method(name)(**payload)
    except (ImportError, KeyError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"method": name, "result": result}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
