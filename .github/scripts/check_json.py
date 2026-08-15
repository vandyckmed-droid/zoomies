#!/usr/bin/env python3
"""Fail if any tracked JSON file in the repo does not parse.

The universe cache under data/ is committed, so a truncated or half-written
file is a change that CI can catch rather than something index.html discovers.
The generated .js payloads are covered by the node --check step in ci.yml.

Tracked means tracked: the file list comes from git, so an untracked scratch
file cannot fail a local run in a way CI would never reproduce.
"""

import json
import pathlib
import subprocess
import sys


def tracked_json(root):
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "*.json"],
        capture_output=True, text=True, check=True,
    ).stdout
    return sorted(root / name for name in out.split("\0") if name)


def main():
    root = pathlib.Path(__file__).resolve().parents[2]
    try:
        paths = tracked_json(root)
    except (OSError, subprocess.CalledProcessError) as exc:
        print("cannot list tracked files (need a git checkout): %s" % exc)
        return 1

    broken = []
    checked = 0

    for path in paths:
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
