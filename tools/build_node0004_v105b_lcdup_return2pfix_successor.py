#!/usr/bin/env python3
"""Route the audited two-phase builder to fresh serialized Conv v105."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/build_node0004_v104b_lcdup_return2p_successor.py").read_text(encoding="utf-8")
    source = source.replace("conv_node0004_v104b_lcdup_return2p_release1", "conv_node0004_v105b_lcdup_return2pfix_release1")
    source = source.replace("mainline_conv_serialized_v104_mode_authority", "mainline_conv_serialized_v105_mode_authority")
    source = source.replace("r5_n4_hw_v104b_lcdup_return2p", "r5_n4_hw_v105b_lcdup_return2pfix")
    source = source.replace("node0004-v104b", "node0004-v105b")
    namespace = {
        "__name__": "node0004_v105_two_phase_builder_routed",
        "__file__": str(ROOT / "tools/build_node0004_v104b_lcdup_return2p_successor.py"),
    }
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
