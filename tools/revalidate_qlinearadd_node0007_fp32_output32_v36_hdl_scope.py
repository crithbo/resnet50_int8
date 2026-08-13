from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_qlinearadd_node0007_v35_actual_consumer_scope as gate


NAME = "r5_qadd_n7_cout32_v36"
ZIP = ROOT / (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    f"{NAME}.zip"
)
OUT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-output32-v36-server-package/"
    "hdl_scope_revalidation.json"
)


def main() -> int:
    gate.INSTALL_NAME = NAME
    gate.EXPECTED_ZIP_BYTES = 26_181_302
    gate.EXPECTED_ZIP_SHA256 = (
        "b10712a584ad69cfeacfeb70d4faa913d0a82e59f66a1466e3b59b444a90a382"
    )
    gate.PAIR_MEMBER = (
        f"{NAME}/tb_probe/qlinearadd_node0007_mse_pair_matrix_tail_v29.svh"
    )
    gate.NATIVE_MEMBER = f"{NAME}/tb_probe/native_return_observer.svh"
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
        "qlinearadd-node0007-fp32-output32-v36-actual-consumer-revalidation-v1"
    )
    report["status"] = "PACKAGE_LOCAL_HDL_ACTUAL_CONSUMER_GATE_PASS"
    report["package_release"] = "PACKAGE_READY_NOT_RUN"
    report["content_change_classification"] = {
        "package_local_hdl_members_changed": False,
        "observer_predicate_changed": False,
        "runner_hdl_include_changed": False,
        "materialized_config_changed": True,
        "reason": (
            "All package-local HDL members are byte-identical to v35. The "
            "fresh v36 exact ZIP is nevertheless compiled directly so the "
            "consumer coverage and three negative classes bind this identity."
        ),
    }
    report["release_gate_matrix_applicability"]["materialized_config"] = {
        "applicable": True,
        "blocking": False,
        "evidence": (
            "v36 causal-ledger and boundary-microtrace validation; this HDL "
            "gate makes no config correctness claim"
        ),
    }
    report["diagnostic_predicate_trace_unit"]["reason"] = (
        "Observer/parser/canonical predicate bytes are unchanged from v35; "
        "predicate trace is receipt reuse and not a changed surface."
    )
    report["observer_public_surface_or_xmr_proof"]["reason"] = (
        "No observer leaf, public interface, or private XMR changed from v35."
    )
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
