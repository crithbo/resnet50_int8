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
ROOT_NAME = "r5_n71_gap_v23_rd_data_vld_path_rulefix"
SOURCE_ROOT = "r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix"
SOURCE_SHA256 = (
    "a82ac187b46dac4f26a8545bf14bebf5bc5481308791be062ce581a30429bbe3"
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
SIGNAL_REPORT = PACKAGE_DIR / f"{ROOT_NAME}.signal_stub_validation.json"


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
    audit.RUNNER_REPORT = PACKAGE_DIR / f"{ROOT_NAME}.runner_chain_validation.json"
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
            "rd_data_vld_path_validator_and_controls",
            ROOT / "tools/validate_gap_node0071_rd_data_vld_diag_v21.py",
            [
                str(audit.ZIP),
                "--root-name",
                ROOT_NAME,
                "--runner-report",
                str(audit.RUNNER_REPORT),
            ],
        ),
    ]


def main() -> int:
    configure()
    result = audit.audit()
    source_receipt = result.pop("source_v12")
    signal_report = json.loads(SIGNAL_REPORT.read_text(encoding="utf-8"))
    signal_checks = {
        "status_pass": signal_report.get("status") == "PASS",
        "all_base_checks_true": all(
            signal_report.get("checks", {}).values()
        ),
        "all_current_signal_scope_true": all(
            signal_report.get("current_rule_scope", {}).values()
        ),
        "rd_data_feature_all_bound": all(
            signal_report.get("return", {})
            .get("rd_data_vld_path_binding", {})
            .values()
        ),
        "target_zip_exact": (
            signal_report.get("target_zip_sha256")
            == sha256(audit.ZIP)
        ),
    }
    if not all(signal_checks.values()):
        result["errors"].append("safe TERM finalizer revalidation differs")
        result["error_count"] = len(result["errors"])
        result["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] = False
        result["status"] = "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
    result.update(
        {
            "schema": (
                "gap-node0071-v23-rd-data-vld-path-final-audit-v1"
            ),
            "source_v20": source_receipt,
            "quarantine_chain": {
                "v21": {
                    "sha256": (
                        "898fc7ab72a062722c13fefa60a232e1"
                        "bf361b6b799cd9cb1f8c248709b4bde2"
                    ),
                    "reason": (
                        "safe runner finalizer hit unbound "
                        "rd_data_path_ok under set -u"
                    ),
                },
                "v22": {
                    "sha256": (
                        "5e9bf8ae98833a967ae5c9c8a41fb06a"
                        "c91b691afa34dc1cf795f86857d2e821"
                    ),
                    "reason": (
                        "final manifest omitted continuous-closure "
                        "applicable rule ID"
                    ),
                },
            },
            "safe_signal_stub_report": str(SIGNAL_REPORT),
            "safe_signal_stub_report_sha256": sha256(SIGNAL_REPORT),
            "safe_signal_stub_checks": signal_checks,
            "diagnostic_contract": {
                "test_id": (
                    "r5-gap-node0071-v23-rd-data-vld-path-rulefix"
                ),
                "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "last_proven_good": (
                    "sum_s1 GA/MSE4 activity before read-data-valid loss"
                ),
                "first_divergence": (
                    "RD_DATA_CHANNEL_DATA_VLD_ABSENT_AFTER_INITIAL_"
                    "SUM_S1_PROGRESS"
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
                "server_command": (
                    "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
                ),
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
