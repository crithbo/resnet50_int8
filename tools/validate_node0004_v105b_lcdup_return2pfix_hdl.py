#!/usr/bin/env python3
"""Route the exact node0004 HDL frontend gate to v105."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/validate_node0004_v104b_lcdup_return2p_hdl.py").read_text(encoding="utf-8")
    source = source.replace("r5_n4_hw_v104b_lcdup_return2p", "r5_n4_hw_v105b_lcdup_return2pfix")
    source = source.replace("node0004-v104b", "node0004-v105b")
    namespace = {
        "__name__": "node0004_v105_hdl_routed",
        "__file__": str(ROOT / "tools/validate_node0004_v104b_lcdup_return2p_hdl.py"),
    }
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
