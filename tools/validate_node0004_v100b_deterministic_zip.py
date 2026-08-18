#!/usr/bin/env python3
"""Route the deterministic ZIP repack gate to exact serialized v100."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/validate_node0004_v99b_deterministic_zip.py").read_text(encoding="utf-8")
    source = source.replace("r5_n4_hw_v99b_lcdup_guarded", "r5_n4_hw_v100b_lcdup_guardv2")
    source = source.replace("node0004-v99-repack-", "node0004-v100-repack-")
    source = source.replace("node0004-v99b-deterministic-zip-repack-v1", "node0004-v100b-deterministic-zip-repack-v1")
    namespace = {"__name__": "node0004_v100_zip_routed", "__file__": str(ROOT / "tools/validate_node0004_v99b_deterministic_zip.py")}
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
