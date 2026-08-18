#!/usr/bin/env python3
"""Route schema-enabled exact-ZIP release admission preparation to v105."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/prepare_node0004_v103b_release_admission.py").read_text(encoding="utf-8")
    source = source.replace("r5_n4_hw_v103b_lcdup_obsfix", "r5_n4_hw_v105b_lcdup_return2pfix")
    source = source.replace("outputs/conv_node0004_v103b_lcdup_obsfix_release1", "outputs/conv_node0004_v105b_lcdup_return2pfix_release1")
    source = source.replace("node0004-v103b-release-admission-receipt-v1", "node0004-v105b-release-admission-receipt-v1")
    source = source.replace("qualified-counter single-authority observer package", "audited two-phase-return observer package")
    namespace = {
        "__name__": "node0004_v105_release_admission_routed",
        "__file__": str(ROOT / "tools/prepare_node0004_v103b_release_admission.py"),
    }
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
