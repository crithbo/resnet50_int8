#!/usr/bin/env python3
"""Route deterministic exact-ZIP reproduction to serialized v105."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/validate_node0004_v103b_deterministic_zip.py").read_text(encoding="utf-8")
    source = source.replace("r5_n4_hw_v103b_lcdup_obsfix", "r5_n4_hw_v105b_lcdup_return2pfix")
    source = source.replace("node0004-v103-repack-", "node0004-v105-repack-")
    source = source.replace("node0004-v103b-deterministic-zip-repack-v1", "node0004-v105b-deterministic-zip-repack-v1")
    namespace = {
        "__name__": "node0004_v105_deterministic_routed",
        "__file__": str(ROOT / "tools/validate_node0004_v103b_deterministic_zip.py"),
    }
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
