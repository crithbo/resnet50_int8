#!/usr/bin/env python3
"""Route deterministic ZIP repack validation to serialized v101."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/validate_node0004_v99b_deterministic_zip.py").read_text(encoding="utf-8")
    source = source.replace("r5_n4_hw_v99b_lcdup_guarded", "r5_n4_hw_v101b_lcdup_guardprocfix")
    source = source.replace("node0004-v99-repack-", "node0004-v101-repack-")
    source = source.replace("node0004-v99b-deterministic-zip-repack-v1", "node0004-v101b-deterministic-zip-repack-v1")
    source = source.replace("(2026, 8, 16, 0, 0, 0)", "(2026, 8, 17, 0, 0, 0)")
    namespace = {"__name__": "node0004_v101_zip_routed", "__file__": str(ROOT / "tools/validate_node0004_v100b_deterministic_zip.py")}
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
