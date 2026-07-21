#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The Loomground Authors
"""Validate a .loom patch with the Loomground reference implementation.

Usage: python3 validate.py PATCH.loom

Prints `WELL-FORMED` and the projection, or `REJECTED (parse|apply): reason`.
The reference implementation is the checker; this script only locates it.
"""
import json
import os
import sys


def _load_impl():
    try:
        import loomground
        return loomground
    except ImportError:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    for rel in ("../loomground-ref", "../../loomground-ref", "loomground-ref"):
        cand = os.path.join(here, rel)
        if os.path.exists(os.path.join(cand, "loomground.py")):
            sys.path.insert(0, cand)
            import loomground
            return loomground
    return None


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 validate.py PATCH.loom")
    L = _load_impl()
    if L is None:
        sys.exit("Loomground reference implementation not found. Put loomground.py "
                 "on PYTHONPATH, or place a loomground-ref checkout beside this skill.")
    src = open(sys.argv[1]).read()
    try:
        patch = L.check(L.parse(src))
    except L.Reject as e:
        print(f"REJECTED ({e.stage}): {e}")
        sys.exit(1)
    print("WELL-FORMED")
    print(json.dumps(L.project(patch), indent=2))


if __name__ == "__main__":
    main()
