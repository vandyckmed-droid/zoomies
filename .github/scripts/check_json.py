#!/usr/bin/env python3
"""Fail if any tracked JSON file in the repo does not parse.

The generated caches under data/ are committed, so a truncated or half-written
file is a change that CI can catch rather than something index.html discovers.
"""

import json
import pathlib
import sys

SKIP_DIRS = {".git", "node_modules", "__pycache__"}


def main():
    root = pathlib.Path(__file__).resolve().parents[2]
    broken = []
    checked = 0

    for path in sorted(root.rglob("*.json")):
        if SKIP_DIRS.intersection(path.relative_to(root).parts):
            continue
        checked += 1
        try:
            json.loads(path.read_text())
        except (ValueError, OSError) as exc:
            broken.append("%s: %s" % (path.relative_to(root), exc))

    for line in broken:
        print("invalid: %s" % line)
    print("checked %d JSON file(s), %d invalid" % (checked, len(broken)))
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
