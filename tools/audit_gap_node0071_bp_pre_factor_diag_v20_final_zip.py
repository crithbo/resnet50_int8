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
ROOT_NAME = "r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix"
SOURCE_ROOT = "r5_n71_gap_v19_bp_pre_factor_stage_scope"
SOURCE_SHA256 = (
    "68c9bd007d8dea02a13aefc7ac9ddda3623b1afb83ad9fdb97552940579ce098"
)
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}
REQUIRED_RULE_IDS = {
    "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001",
    "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
    "CDA-GAP-8B-READ-BUFFER-BYTE-LANE-COVERAGE-001",
    "CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001",
}


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
    audit.OUTPUT = (
        PACKAGE_DIR / f"{ROOT_NAME}.final_zip_rule_self_audit.json"
    )
    audit.RUNNER_REPORT = (
        PACKAGE_DIR / f"{ROOT_NAME}.runner_chain_validation.json"
    )
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
            "bp_pre_factor_stage_scope_runnerfix_validator_and_controls",
            ROOT
            / "tools/validate_gap_node0071_bp_pre_factor_diag_v20.py",
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
    result.update(
        {
            "schema":
                "gap-node0071-bp-pre-factor-stage-scope-v20-final-audit-v1",
            "source_v19": source_receipt,
            "quarantine_chain": {
                "v18": {
                    "sha256":
                        "00ca26f5ad7d30507ed7889d5f19f1a1072c948475e1280198a43b98324916c7",
                    "reason":
                        "ordered-stage current-rule drift was material",
                },
                "v19": {
                    "sha256": SOURCE_SHA256,
                    "reason":
                        "EXIT trap finalizer used function-local "
                        "package_manifest under set -u",
                },
            },
            "diagnostic_contract": {
                "test_id":
                    "r5-gap-node0071-v20-bp-pre-factor-stage-scope-runnerfix",
                "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "expected_ordered_stage_list": [
                    "sum_s1",
                    "sum_s2",
                    "sum_s3",
                    "sum_s4",
                    "sum_s5",
                    "sum_s6",
                    "tail_mul",
                    "tail_round",
                ],
                "runner_finalizer_manifest_binding":
                    "$package_root/TEST_PACKAGE_MANIFEST.json",
                "changed_numeric_payloads": [],
                "numeric_analysis_repeated": False,
                "workload_rebuilt": False,
                "config_semantics_rebuilt": False,
                "functional_rtl_modified": False,
                "factor_observer_changed_from_v19": False,
                "canonical_parser_changed_from_v19": False,
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
