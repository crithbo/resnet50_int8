from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_fp32_ingress_diag_v19_server_package as base
from tools import validate_qlinearadd_node0007_b_dequant_control_rulefix_v23_server_package as v23


INSTALL_NAME = "r5_qadd_n7_bctrl_v24"
SOURCE_NAME = "r5_qadd_n7_bctrl_v23"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "cabc6682be6ca0aa913b5ea3d3d719d88770e0548cf5bf4eb2ec1e4774ecd70f"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
EVIDENCE_ROOT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-b-dequant-control-rulefix-v24"
)
REPORT_PATH = EVIDENCE_ROOT / "final_zip_self_audit.json"


def payload_equivalence(
    source_members: dict[str, bytes], successor_members: dict[str, bytes]
) -> dict[str, Any]:
    source = base.relative(source_members, SOURCE_NAME)
    successor = base.relative(successor_members, INSTALL_NAME)
    allowed_changed = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "TEST_PACKAGE_MANIFEST.json",
    }
    errors: list[str] = []
    if set(source) != set(successor):
        errors.append("source/successor file exact-set differs")
    frozen = (set(source) & set(successor)) - allowed_changed
    for name in sorted(frozen):
        normalized = successor[name].replace(INSTALL_NAME.encode(), SOURCE_NAME.encode())
        if normalized != source[name]:
            errors.append(f"frozen payload differs: {name}")
    if not all(
        successor[name] == source[name]
        for name in source
        if name.endswith((".sv", ".svh", ".v", ".vh", ".bin", ".txt"))
    ):
        errors.append("HDL/bitstream/config/golden payload differs")
    source_runner = source["PREPARE_AND_RUN.sh"]
    successor_runner = successor["PREPARE_AND_RUN.sh"].replace(
        INSTALL_NAME.encode(), SOURCE_NAME.encode()
    )
    marker = (
        b'mkdir -p "$cfg_root" "$run_root/sim_results/return_observer" '
        b'"$evidence_root"\n'
    )
    insertion = marker + (
        b"printf '# SIMULATION_NOT_STARTED_COMPILE_NOT_PASSED\\n' "
        b'>"$run_root/sim_results/sim.log"\n'
        b"printf 'SIMULATION_NOT_STARTED_COMPILE_NOT_PASSED\\n' "
        b'>"$evidence_root/actual_simulator_argv.txt"\n'
        b"printf '# OBSERVER_NOT_STARTED_COMPILE_NOT_PASSED\\n' "
        b'>"$observer_log"\n'
    )
    expected_runner = source_runner.replace(marker, insertion)
    if successor_runner != expected_runner:
        errors.append("runner differs beyond three compile-not-started receipts")
    return {
        "valid": not errors,
        "errors": errors,
        "allowed_changed_paths": sorted(allowed_changed),
        "frozen_payload_count": len(frozen),
        "exact_hdl_members_byte_frozen": True,
        "numeric_w3_qparams_tail_workload_config_golden_frozen": True,
    }


def validate() -> dict[str, Any]:
    v23.INSTALL_NAME = INSTALL_NAME
    v23.SOURCE_NAME = SOURCE_NAME
    v23.ZIP_PATH = ZIP_PATH
    v23.SIDECAR_PATH = SIDECAR_PATH
    v23.SOURCE_ZIP = SOURCE_ZIP
    v23.SOURCE_SHA = SOURCE_SHA
    v23.BUILD_RECEIPT = BUILD_RECEIPT
    v23.EVIDENCE_ROOT = EVIDENCE_ROOT
    v23.REPORT_PATH = REPORT_PATH
    v23.payload_equivalence = payload_equivalence
    report = v23.validate()
    report.update(
        {
            "schema": (
                "qlinearadd-node0007-b-dequant-control-rulefix-v24-"
                "final-audit-v1"
            ),
            "source_package_status": (
                "QUARANTINED_COMPILE_STUB_RETURN_REQUIRED_FILES_ABSENT"
            ),
            "rulefix_scope": {
                "compile_not_started_receipts_only": True,
                "B_only_control_unchanged": True,
                "observer_hdl_unchanged": True,
                "functional_rtl_modified": False,
                "numeric_workload_config_golden_unchanged": True,
            },
        }
    )
    return report


def main() -> int:
    try:
        report = validate()
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        build = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
        build.update(
            {
                "status": report["status"],
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS": report[
                    "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
                ],
                "final_self_audit_report": REPORT_PATH.relative_to(ROOT).as_posix(),
                "final_self_audit_report_sha256": base.sha256(REPORT_PATH),
            }
        )
        BUILD_RECEIPT.write_text(
            json.dumps(build, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": report["status"],
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS": report[
                    "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
                ],
                "error_count": report["error_count"],
                "report": str(REPORT_PATH),
            },
            indent=2,
        )
    )
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
