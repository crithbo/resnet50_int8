from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import audit_gap_node0071_v13_buffer_to_ga_final_zip as audit


PACKAGE_DIR = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ROOT_NAME = "r5_n71_gap_v16_stage1_byte_slots"
SOURCE_ROOT = "r5_n71_gap_v15_feature_enable_rule"
BITSTREAM_RELATIVE = (
    "workload/install/cfg_pkg/gap_node0071_sum_s1_128b.bin"
)
FEATURE_RULE_ID = (
    "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001"
)
BYTE_LANE_RULE_ID = "CDA-GAP-8B-READ-BUFFER-BYTE-LANE-COVERAGE-001"


def configure() -> None:
    audit.ROOT_NAME = ROOT_NAME
    audit.SOURCE_ROOT = SOURCE_ROOT
    audit.ZIP = PACKAGE_DIR / f"{ROOT_NAME}.zip"
    audit.SOURCE_ZIP = PACKAGE_DIR / f"{SOURCE_ROOT}.zip"
    audit.SIDECAR = Path(str(audit.ZIP) + ".sha256")
    audit.OUTPUT = PACKAGE_DIR / f"{ROOT_NAME}.final_zip_rule_self_audit.json"
    audit.RUNNER_REPORT = PACKAGE_DIR / f"{ROOT_NAME}.runner_chain_validation.json"
    audit.SOURCE_SHA256 = (
        "97a7366812210840ad67af40b3be3d90f7d7d44b997a29de41d366d877d97811"
    )
    audit.RULES = {
        ".agents/rules/生成前必读索引.md":
            "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
        ".agents/rules/算子配置规则.md":
            "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
        ".agents/rules/NDP硬件字段语义.md":
            "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
        ".agents/rules/服务器测试包生成规则.md":
            "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025",
        ".agents/rules/GAP_int32_mac_bypass_rules.md":
            "4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b",
        ".agents/rules/GAP_probe_v7_validator_rules.md":
            "4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf",
        ".agents/rules/精确UINT8量化尾专项规则.md":
            "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    }
    audit.REQUIRED_RULE_IDS = set(audit.REQUIRED_RULE_IDS) | {
        FEATURE_RULE_ID,
        BYTE_LANE_RULE_ID,
    }
    audit.ALLOWED_CHANGED = {
        "TEST_PACKAGE_MANIFEST.json",
        "README.md",
        "PREPARE_AND_RUN.sh",
        "workload/sca_cfg.json",
        "workload/sca_cfg_D.json",
        BITSTREAM_RELATIVE,
    }
    audit.EXPECTED_CHANGED_NUMERIC = {BITSTREAM_RELATIVE}
    audit.BUFFER_VALIDATOR_EXTRA_ARGS = ["--root-name", ROOT_NAME]
    audit.RUNNER_VALIDATOR_EXTRA_ARGS = ["--root-name", ROOT_NAME]
    audit.EXTRA_VALIDATORS = [
        (
            "feature_runtime_enable_validator_and_controls",
            ROOT / "tools/validate_gap_node0071_v15_feature_enable_rule.py",
            [str(audit.ZIP), "--root-name", ROOT_NAME],
        ),
        (
            "stage1_byte_slots_validator_and_controls",
            ROOT / "tools/validate_gap_node0071_stage1_byte_slots_v16.py",
            [str(audit.ZIP), "--root-name", ROOT_NAME],
        ),
    ]


def main() -> int:
    configure()
    result = audit.audit()
    result.update(
        {
            "schema": "gap-node0071-stage1-byte-slots-v16-final-audit-v1",
            "source_v15": result.pop("source_v12"),
            "functional_fix_contract": {
                "classification":
                    "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",
                "changed_numeric_payloads": [BITSTREAM_RELATIVE],
                "stage1_byte_lane_rule_id": BYTE_LANE_RULE_ID,
                "numeric_analysis_repeated": False,
                "workload_rebuilt": False,
                "config_semantics_rebuilt": True,
                "functional_rtl_modified": False,
            },
            "package_release": {
                "claim":
                    "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",
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
