#!/usr/bin/env python3
"""Route the independent v103 counter/return audit to exact v105."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/audit_node0004_v103b_lcdup_obsfix_first_fresh.py").read_text(encoding="utf-8")
    source = source.replace("r5_n4_hw_v103b_lcdup_obsfix", "r5_n4_hw_v105b_lcdup_return2pfix")
    source = source.replace("node0004-v103", "node0004-v105")
    namespace = {
        "__name__": "node0004_v105_first_fresh_routed",
        "__file__": str(ROOT / "tools/audit_node0004_v103b_lcdup_obsfix_first_fresh.py"),
    }
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
