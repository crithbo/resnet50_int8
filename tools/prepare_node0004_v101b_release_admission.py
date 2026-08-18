#!/usr/bin/env python3
"""Route v100 release-admission preparation to serialized v101."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/prepare_node0004_v100b_release_admission.py").read_text(encoding="utf-8")
    source = source.replace("r5_n4_hw_v100b_lcdup_guardv2", "r5_n4_hw_v101b_lcdup_guardprocfix")
    source = source.replace("outputs/conv_node0004_v100b_lcdup_guardv2_release1", "outputs/conv_node0004_v101b_lcdup_guardprocfix_release1")
    source = source.replace("node0004-v100b-release-admission-receipt-v1", "node0004-v101b-release-admission-receipt-v1")
    source = source.replace("operational guard-v2 observer package", "guard self-enumerator-fixed observer package")
    namespace = {"__name__": "node0004_v101_release_admission_routed", "__file__": str(ROOT / "tools/prepare_node0004_v100b_release_admission.py")}
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
