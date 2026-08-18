#!/usr/bin/env python3
"""Extract only registered source-bound observer rows without copying sim.log."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prefix", default="CODEX_PROBE_V1")
    parser.add_argument("--max-bytes", type=int, required=True)
    args = parser.parse_args()
    temporary = args.output.with_name(f".{args.output.name}.tmp.{os.getpid()}")
    written = 0
    with args.source.open("rb") as source, temporary.open("wb") as target:
        for line in source:
            if args.prefix.encode("ascii") not in line:
                continue
            if written + len(line) > args.max_bytes:
                target.flush()
                os.fsync(target.fileno())
                temporary.unlink(missing_ok=True)
                raise SystemExit("source-bound filtered log exceeds operational limit")
            target.write(line)
            written += len(line)
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
