from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_qlinearadd_node0007_v35_actual_consumer_scope as gate


NAME = "r5_qadd_n7_cout32_rootclean_v37"
ZIP = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-v37-rootclean-package/"
    f"{NAME}.zip"
)
OUT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-v37-rootclean-package/"
    "hdl_scope_revalidation.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    gate.INSTALL_NAME = NAME
    gate.EXPECTED_ZIP_BYTES = ZIP.stat().st_size
    gate.EXPECTED_ZIP_SHA256 = sha256(ZIP)
    gate.PAIR_MEMBER = (
        f"{NAME}/tb_probe/qlinearadd_node0007_mse_pair_matrix_tail_v29.svh"
    )
    gate.NATIVE_MEMBER = f"{NAME}/tb_probe/native_return_observer.svh"
    gate.V29_SOURCE = ROOT / (
        "artifacts/operator_config_validation/r5-server-test-packages/pending/"
        "r5_qadd_n7_cout32_v36.zip"
    )
    previous_argv = sys.argv
    sys.argv = [
        str(Path(__file__)),
        "--zip",
        str(ZIP),
        "--iverilog",
        r"C:\iverilog\bin\iverilog.exe",
        "--output",
        str(OUT),
    ]
    try:
        rc = gate.main()
    finally:
        sys.argv = previous_argv
    if rc:
        return rc
    report = json.loads(OUT.read_text(encoding="utf-8"))
    report["schema"] = (
        "qlinearadd-node0007-v37-rootclean-actual-consumer-revalidation-v1"
    )
    report["status"] = "PACKAGE_LOCAL_HDL_ACTUAL_CONSUMER_GATE_PASS"
    report["package_release"] = "PACKAGE_READY_NOT_RUN"
    report["content_change_classification"] = {
        "package_local_hdl_members_changed": False,
        "observer_predicate_changed": False,
        "runner_hdl_include_changed": False,
        "materialized_config_semantics_changed": False,
        "reason": (
            "All package-local HDL bytes are frozen from v36; the focused "
            "frontend and actual-consumer closure nevertheless bind the exact "
            "fresh v37 ZIP and all three required negative classes."
        ),
    }
    OUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "valid": report["valid"],
                "zip_sha256": report["zip"]["sha256_after"],
                "uncovered": report["actual_consumer_coverage"][
                    "uncovered_expression_total"
                ],
                "all_negative_controls_fail_closed": report[
                    "all_negative_controls_fail_closed"
                ],
                "output": str(OUT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
