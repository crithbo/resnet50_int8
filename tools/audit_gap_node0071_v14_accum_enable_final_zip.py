from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import audit_gap_node0071_v13_buffer_to_ga_final_zip as base


PACKAGE_DIR = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
ROOT_NAME = "r5_n71_gap_v14_accum_enable"
SOURCE_ROOT = "r5_n71_gap_v13_buffer_to_ga_diag"
ZIP = PACKAGE_DIR / f"{ROOT_NAME}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
OUTPUT = PACKAGE_DIR / f"{ROOT_NAME}.final_zip_rule_self_audit.json"
RUNNER_REPORT = PACKAGE_DIR / f"{ROOT_NAME}.runner_chain_validation.json"
SOURCE_ZIP = PACKAGE_DIR / f"{SOURCE_ROOT}.zip"
SOURCE_SHA256 = "88715902dd818b488990521bcdfa9d9be24f3195e0371c9c25a664a17fc76131"
SERVER_RULE_SHA256 = (
    "88fcc7e87da9d92d281b8096389e31f1735b0e99ce3b13dd37635a8b96c0a7c6"
)
TRANSPORT_RULE_ID = "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001"
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
    base.REQUIRED_RULE_IDS.add(TRANSPORT_RULE_ID)
    base.BUFFER_VALIDATOR_EXTRA_ARGS = ["--root-name", ROOT_NAME]
    base.RUNNER_VALIDATOR_EXTRA_ARGS = ["--root-name", ROOT_NAME]


def main() -> int:
    configure()
    result = base.audit()
    extra_script = ROOT / "tools/validate_gap_node0071_v14_accum_enable.py"
    receipt, stdout = base.common.run_command(
        "accum_enable_validator_and_controls",
        [sys.executable, str(extra_script), str(ZIP)],
        ROOT,
    )
    extra = json.loads(stdout)
    result["command_receipts"].append(receipt)
    result["validator_report_sha256"][receipt["name"]] = receipt[
        "stdout_sha256"
    ]
    extra_valid = (
        receipt["exit_code"] == 0
        and extra.get("status") == "PASS"
        and extra.get("all_negative_controls_fail_closed") is True
    )
    if not extra_valid:
        result["errors"].append("accumulator-enable validator differs")
    result["schema"] = "gap-node0071-v14-final-zip-rule-self-audit-v1"
    result["source_v13"] = result.pop("source_v12")
    result["source_v13"]["superseded_for_next_run"] = True
    result["frozen_reuse_boundary"][
        "observer_algorithm_tree_equal"
    ] = True
    result["rule_checks"][
        "accumulator_runtime_enable_validated"
    ] = extra_valid
    result["error_count"] = len(result["errors"])
    passed = (
        result["FINAL_ZIP_RULE_SELF_AUDIT_PASS"]
        and extra_valid
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
