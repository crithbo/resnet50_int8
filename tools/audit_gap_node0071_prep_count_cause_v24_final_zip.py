from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import audit_gap_node0071_v13_buffer_to_ga_final_zip as audit


PACKAGE_DIR = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ROOT_NAME = "r5_n71_gap_v24_prep_count_cause_diag"
SOURCE_ROOT = "r5_n71_gap_v23_rd_data_vld_path_rulefix"
SOURCE_SHA256 = (
    "07ea69a9b647542751c3e47b192d5d1ddb497dad97801e75c9fe002331244c19"
)
ALLOWED_CHANGED = {
    "PREPARE_AND_RUN.sh",
    "README.md",
    "TEST_PACKAGE_MANIFEST.json",
    "tb_probe/native_return_observer.svh",
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}
REQUIRED_RULE_IDS = {
    "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
    "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001",
    "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
    "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
    "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
    "CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001",
    "CDA-GAP-8B-READ-BUFFER-BYTE-LANE-COVERAGE-001",
}
RUNNER_REPORT = PACKAGE_DIR / f"{ROOT_NAME}.runner.json"
SIGNAL_REPORT = PACKAGE_DIR / f"{ROOT_NAME}.signal_stub.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def configure() -> None:
    audit.ROOT_NAME = ROOT_NAME
    audit.SOURCE_ROOT = SOURCE_ROOT
    audit.ZIP = PACKAGE_DIR / f"{ROOT_NAME}.zip"
    audit.SOURCE_ZIP = PACKAGE_DIR / f"{SOURCE_ROOT}.zip"
    audit.SIDECAR = Path(str(audit.ZIP) + ".sha256")
    audit.OUTPUT = PACKAGE_DIR / f"{ROOT_NAME}.final_zip_rule_self_audit.json"
    audit.RUNNER_REPORT = RUNNER_REPORT
    audit.SOURCE_SHA256 = SOURCE_SHA256
    manifest = json.loads(
        (
            PACKAGE_DIR / ROOT_NAME / "TEST_PACKAGE_MANIFEST.json"
        ).read_text(encoding="utf-8")
    )
    audit.RULES = {
        item["path"]: sha256(ROOT / item["path"])
        for item in manifest[
            "final_zip_rule_self_audit_contract"
        ]["read_receipt"]
    }
    audit.REQUIRED_RULE_IDS = set(audit.REQUIRED_RULE_IDS) | REQUIRED_RULE_IDS
    audit.ALLOWED_CHANGED = set(ALLOWED_CHANGED)
    audit.EXPECTED_CHANGED_NUMERIC = set()
    audit.BUFFER_VALIDATOR_EXTRA_ARGS = ["--root-name", ROOT_NAME]
    audit.RUNNER_VALIDATOR_EXTRA_ARGS = ["--root-name", ROOT_NAME]
    audit.EXTRA_VALIDATORS = [
        (
            "prepared_count_cause_validator_and_controls",
            ROOT / "tools/validate_gap_node0071_prep_count_cause_v24.py",
            [
                str(audit.ZIP),
                "--root-name",
                ROOT_NAME,
                "--runner-report",
                str(RUNNER_REPORT),
            ],
        ),
    ]


def main() -> int:
    configure()
    result = audit.audit()
    source_receipt = result.pop("source_v12")
    signal = json.loads(SIGNAL_REPORT.read_text(encoding="utf-8"))
    runner = json.loads(RUNNER_REPORT.read_text(encoding="utf-8"))
    signal_checks = {
        "status_pass": signal.get("status") == "PASS",
        "all_base_checks_true": all(signal.get("checks", {}).values()),
        "all_signal_scope_true": all(
            signal.get("current_rule_scope", {}).values()
        ),
        "prepared_count_feature_all_bound": all(
            signal.get("return", {})
            .get("prepared_count_cause_binding", {})
            .values()
        ),
        "target_zip_exact":
            signal.get("target_zip_sha256") == sha256(audit.ZIP),
    }
    runner_checks = {
        "valid": runner.get("valid") is True,
        "positive_compile_reached":
            runner.get("positive_compile_reached") is True,
        "compile_stub_exit_86":
            runner.get("compile_stub_unique_expected_exit_code") == 86,
        "wrong_identity_failed_before_compile":
            runner.get("wrong_identity_failed_before_compile") is True,
        "all_negatives_fail_closed":
            runner.get("all_negative_controls_fail_closed") is True,
        "target_zip_exact":
            runner.get("target_zip_sha256") == sha256(audit.ZIP),
    }
    if not all(signal_checks.values()):
        result["errors"].append("safe TERM finalizer revalidation differs")
    if not all(runner_checks.values()):
        result["errors"].append("safe EXIT/compile runner revalidation differs")
    if result["errors"]:
        result["error_count"] = len(result["errors"])
        result["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] = False
        result["status"] = "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
    result.update(
        {
            "schema":
                "gap-node0071-v24-prepared-count-cause-final-audit-v1",
            "source_v23": source_receipt,
            "safe_signal_stub_report": str(SIGNAL_REPORT),
            "safe_signal_stub_report_sha256": sha256(SIGNAL_REPORT),
            "safe_signal_stub_checks": signal_checks,
            "safe_runner_report": str(RUNNER_REPORT),
            "safe_runner_report_sha256": sha256(RUNNER_REPORT),
            "safe_runner_checks": runner_checks,
            "diagnostic_contract": {
                "test_id":
                    "r5-gap-node0071-v24-prep-count-cause-diagnostic",
                "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "last_proven_good": (
                    "MSE0/MSE3 memory-return 5,5/5,5 and prepared "
                    "writes 6/10"
                ),
                "first_divergence": (
                    "MSE3_PREPARED_DATA_COUNT_NOT_RETAINED_AFTER_"
                    "QUALIFIED_WRITES"
                ),
                "changed_numeric_payloads": [],
                "numeric_analysis_repeated": False,
                "workload_rebuilt": False,
                "config_semantics_rebuilt": False,
                "functional_rtl_modified": False,
            },
            "package_release": {
                "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "status": (
                    "PACKAGE_READY_NOT_RUN"
                    if result["FINAL_ZIP_RULE_SELF_AUDIT_PASS"]
                    else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
                ),
                "server_command":
                    "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
                "expected_return": [f"{ROOT_NAME}_return.zip"],
            },
        }
    )
    audit.OUTPUT.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
