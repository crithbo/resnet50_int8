#!/usr/bin/env python3
"""Route v101 release-admission preparation to canonical-guard v102."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/prepare_node0004_v101b_release_admission.py").read_text(encoding="utf-8")
    source = source.replace("r5_n4_hw_v101b_lcdup_guardprocfix", "r5_n4_hw_v102b_lcdup_guardprocfs")
    source = source.replace("outputs/conv_node0004_v101b_lcdup_guardprocfix_release1", "outputs/conv_node0004_v102b_lcdup_guardprocfs_release1")
    source = source.replace("node0004-v101b-release-admission-receipt-v1", "node0004-v102b-release-admission-receipt-v1")
    source = source.replace("guard self-enumerator-fixed observer package", "canonical procfs PID+start_time observer package")
    namespace = {"__name__": "node0004_v102_release_admission_routed", "__file__": str(ROOT / "tools/prepare_node0004_v101b_release_admission.py")}
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
