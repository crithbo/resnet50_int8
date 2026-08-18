#!/usr/bin/env python3
"""Route the frozen node0004 HDL gate to v102."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/validate_node0004_v101b_lcdup_guardprocfix_hdl.py").read_text(encoding="utf-8")
    source = source.replace("r5_n4_hw_v101b_lcdup_guardprocfix", "r5_n4_hw_v102b_lcdup_guardprocfs")
    source = source.replace("node0004-v101b-lcdup-guardprocfix-hdl-validation-v1", "node0004-v102b-lcdup-guardprocfs-hdl-validation-v1")
    namespace = {"__name__": "node0004_v102_hdl_routed", "__file__": str(ROOT / "tools/validate_node0004_v101b_lcdup_guardprocfix_hdl.py")}
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
