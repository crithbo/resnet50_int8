from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import audit_gap_node0071_v13_buffer_to_ga_final_zip as base


PACKAGE_DIR = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ROOT_NAME = "r5_n71_gap_v15_feature_enable_rule"
SOURCE_ROOT = "r5_n71_gap_v14_accum_enable"
ZIP = PACKAGE_DIR / f"{ROOT_NAME}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
OUTPUT = PACKAGE_DIR / f"{ROOT_NAME}.final_zip_rule_self_audit.json"
RUNNER_REPORT = PACKAGE_DIR / f"{ROOT_NAME}.runner_chain_validation.json"
SOURCE_ZIP = PACKAGE_DIR / f"{SOURCE_ROOT}.zip"
SOURCE_SHA256 = "98ef0a67d09f6790c2dfa8fb7445b6535ae605fc92c9455e5513b21210f5271b"
SERVER_RULE_SHA256 = (
    "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025"
)
FEATURE_RULE_ID = (
    "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001"
)
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}


def configure() -> None:
    base.ROOT_NAME = ROOT_NAME
    base.SOURCE_ROOT = SOURCE_ROOT
    base.ZIP = ZIP
    base.SIDECAR = SIDECAR
    base.OUTPUT = OUTPUT
    base.RUNNER_REPORT = RUNNER_REPORT
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.ALLOWED_CHANGED = ALLOWED_CHANGED
    server_path = next(
        path for path in base.RULES if "服务器测试包生成规则" in path
    )
    base.RULES[server_path] = SERVER_RULE_SHA256
    base.REQUIRED_RULE_IDS.add(FEATURE_RULE_ID)
    base.BUFFER_VALIDATOR_EXTRA_ARGS = ["--root-name", ROOT_NAME]
    base.RUNNER_VALIDATOR_EXTRA_ARGS = ["--root-name", ROOT_NAME]


def main() -> int:
    configure()
    result = base.audit()
    script = ROOT / "tools/validate_gap_node0071_v15_feature_enable_rule.py"
    receipt, stdout = base.common.run_command(
        "feature_enable_rule_validator_and_controls",
        [sys.executable, str(script), str(ZIP)],
        ROOT,
    )
    feature = json.loads(stdout)
    result["command_receipts"].append(receipt)
    result["validator_report_sha256"][receipt["name"]] = receipt[
        "stdout_sha256"
    ]
    feature_valid = (
        receipt["exit_code"] == 0
        and feature.get("status") == "PASS"
        and feature.get("rule_id") == FEATURE_RULE_ID
        and feature.get("all_negative_controls_fail_closed") is True
        and all(feature.get("three_way_binding", {}).values())
    )
    if not feature_valid:
        result["errors"].append("feature-enable rule validator differs")
    result["schema"] = "gap-node0071-v15-final-zip-rule-self-audit-v1"
    result["source_v14"] = result.pop("source_v12")
    result["source_v14"]["superseded_for_next_run"] = True
    result["frozen_reuse_boundary"]["observer_algorithm_tree_equal"] = True
    result["rule_checks"]["diagnostic_feature_runtime_enable_rule_validated"] = (
        feature_valid
    )
    result["error_count"] = len(result["errors"])
    passed = (
        result["FINAL_ZIP_RULE_SELF_AUDIT_PASS"]
        and feature_valid
        and not result["errors"]
    )
    result["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] = passed
    result["status"] = (
        "PACKAGE_READY_NOT_RUN"
        if passed
        else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
    )
    result["package_release"]["expected_return"] = [
        f"{ROOT_NAME}_return.zip",
        f"{ROOT_NAME}_return.zip.sha256",
    ]
    OUTPUT.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
