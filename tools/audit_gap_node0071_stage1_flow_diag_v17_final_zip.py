from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import audit_gap_node0071_v13_buffer_to_ga_final_zip as audit


PACKAGE_DIR = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ROOT_NAME = "r5_n71_gap_v17_stage1_flow_diag"
SOURCE_ROOT = "r5_n71_gap_v16_stage1_byte_slots"
SOURCE_SHA256 = (
    "85ee11406a8f7b67d67d7fd3e82705c3c48c12b01e2a155496cbf7b05679cee5"
)
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    OBSERVER_RELATIVE,
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}
FEATURE_RULE_ID = (
    "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001"
)
BYTE_LANE_RULE_ID = "CDA-GAP-8B-READ-BUFFER-BYTE-LANE-COVERAGE-001"


def sha256(path: Path) -> str:
    import hashlib

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
    source_manifest = json.loads(
        (
            PACKAGE_DIR / SOURCE_ROOT / "TEST_PACKAGE_MANIFEST.json"
        ).read_text(encoding="utf-8")
    )
    audit.RULES = {
        item["path"]: sha256(ROOT / item["path"])
        for item in source_manifest[
            "final_zip_rule_self_audit_contract"
        ]["read_receipt"]
    }
    audit.REQUIRED_RULE_IDS = set(audit.REQUIRED_RULE_IDS) | {
        FEATURE_RULE_ID,
        BYTE_LANE_RULE_ID,
    }
    audit.ALLOWED_CHANGED = set(ALLOWED_CHANGED)
    audit.EXPECTED_CHANGED_NUMERIC = set()
    audit.BUFFER_VALIDATOR_EXTRA_ARGS = ["--root-name", ROOT_NAME]
    audit.RUNNER_VALIDATOR_EXTRA_ARGS = ["--root-name", ROOT_NAME]
    audit.EXTRA_VALIDATORS = [
        (
            "stage1_flow_validator_and_controls",
            ROOT / "tools/validate_gap_node0071_stage1_flow_diag_v17.py",
            [str(audit.ZIP), "--root-name", ROOT_NAME],
        ),
    ]


def main() -> int:
    configure()
    result = audit.audit()
    source_receipt = result.pop("source_v12")
    result.update(
        {
            "schema": "gap-node0071-stage1-flow-v17-final-audit-v1",
            "source_v16": source_receipt,
            "diagnostic_contract": {
                "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "changed_numeric_payloads": [],
                "numeric_analysis_repeated": False,
                "workload_rebuilt": False,
                "config_semantics_rebuilt": False,
                "functional_rtl_modified": False,
                "added_records": [
                    "STAGE1_FLOW_COUNTS_V1",
                    "STAGE1_FLOW_STATE_V1",
                ],
                "excluded_from_monotonic_progress": True,
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
