#!/usr/bin/env python3
"""Route the established tuple10 HDL gate to serialized v101."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/validate_node0004_v100b_lcdup_guardv2_hdl.py").read_text(encoding="utf-8")
    source = source.replace("r5_n4_hw_v100b_lcdup_guardv2", "r5_n4_hw_v101b_lcdup_guardprocfix")
    source = source.replace("node0004-v100-hdl-", "node0004-v101-hdl-")
    source = source.replace("node0004-v100b-lcdup-guardv2-hdl-gate-v1", "node0004-v101b-lcdup-guardprocfix-hdl-gate-v1")
    namespace = {"__name__": "node0004_v101_hdl_routed", "__file__": str(ROOT / "tools/validate_node0004_v100b_lcdup_guardv2_hdl.py")}
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
