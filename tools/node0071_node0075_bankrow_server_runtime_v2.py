#!/usr/bin/env python3
"""Narrow materialized-config consumer wrapper for the bank-row successor."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    base_path = Path(__file__).resolve().with_name("runtime_base.py")
    source = base_path.read_text(encoding="utf-8")
    old = 'sca.get("Exec_Base") != "0x01706400"'
    new = 'sca.get("Exec_Base") != "0x002ACC00"'
    if source.count(old) != 1 or new in source:
        print(
            "NATIVE_ORDERING_RUNTIME_FAIL: exact Exec_Base guard differs",
            file=sys.stderr,
        )
        return 1
    compiled = compile(source.replace(old, new, 1), str(base_path), "exec")
    namespace = {
        "__name__": "node0071_node0075_runtime_base",
        "__file__": str(base_path),
        "__package__": None,
    }
    exec(compiled, namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
