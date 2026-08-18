#!/usr/bin/env python3
"""Route the v103 observer/runtime frozen gate to v106."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/validate_node0004_v103b_lcdup_obsfix.py").read_text(encoding="utf-8")
    source = source.replace("conv_node0004_v103b_lcdup_obsfix_release1", "conv_node0004_v106b_lcdup_return2pflight_release1")
    source = source.replace("r5_n4_hw_v103b_lcdup_obsfix", "r5_n4_hw_v106b_lcdup_return2pflight")
    source = source.replace("r5_n4_hw_v102b_lcdup_guardprocfs", "r5_n4_hw_v103b_lcdup_obsfix")
    source = source.replace("node0004-v103b-lcdup-obsfix-validation-v1", "node0004-v106b-observer-runtime-frozen-validation-v1")
    namespace = {"__name__": "node0004_v106_observer_runtime_routed", "__file__": str(ROOT / "tools/validate_node0004_v103b_lcdup_obsfix.py")}
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
