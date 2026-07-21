#!/usr/bin/env python3
"""compile-loomground-policy — validate a Loomground .lg policy through the installed kernel.

Input JSON: {"source": "<.lg text>", "transport": {optional observation}}.
With a transport it evaluates the policy against it (reason); without, it parses and
validates the policy graph. Delegates to loomground_solver; never re-implements the parser.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

def _input(argv):
    text = sys.stdin.read() if (not argv or argv[0] == "-") else Path(argv[0]).read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict) or "source" not in value:
        raise ValueError('input must be a JSON object with a "source" .lg program')
    return value

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        payload = _input(argv)
        source = payload["source"]
        transport = payload.get("transport")
        from loomground_solver import parse_loomground, reason_loomground
        if transport is not None:
            result = reason_loomground(source, transport)
        else:
            parsed = parse_loomground(source)
            result = {"validated": True, "program": repr(parsed)[:2000]}
    except (ImportError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
