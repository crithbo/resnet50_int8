#!/usr/bin/env python3
"""Route the identity-normalized frozen-surface gate from v101 to v102."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/validate_node0004_v101b_frozen_surface.py").read_text(encoding="utf-8")
    source = source.replace('OLD = "r5_n4_hw_v100b_lcdup_guardv2"', 'OLD = "r5_n4_hw_v101b_lcdup_guardprocfix"')
    source = source.replace('NEW = "r5_n4_hw_v101b_lcdup_guardprocfix"', 'NEW = "r5_n4_hw_v102b_lcdup_guardprocfs"')
    source = source.replace("node0004-v101b-frozen-surface-validation-v1", "node0004-v102b-frozen-surface-validation-v1")
    namespace = {"__name__": "node0004_v102_frozen_routed", "__file__": str(ROOT / "tools/validate_node0004_v101b_frozen_surface.py")}
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
