from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (
    build_qlinearadd_node0007_nested_lc_progress_canonical_v7_server_package
    as v7,
)
from tools import build_qlinearadd_node0007_server_package as implementation
from tools.qlinearadd_node0007_server_runtime import (
    file_records,
    preflight as runtime_preflight,
)


INSTALL_NAME = "r5_qadd_n7_progress_canon_v8"
SOURCE_INSTALL_NAME = "r5_qadd_n7_progress_canon_v7"
SOURCE_ZIP_SHA256 = (
    "1ed2ed3cb1015e62b585a77dbff0b82b45e592a27695ddd9331b47eb1196df1f"
)
CONTRACT_REL = Path(
    "contracts/operator_config/"
    "qlinearadd_node0007_nested_lc_progress_canonical_diagnostic_v8.json"
)
TASK_RECORD_REL = Path(
    ".agents/task_records/"
    "20260730_qlinearadd_node0007_v6_canonical_decision_audit.md"
)
INDEX_REL = Path(".agents/rules/生成前必读索引.md")
INDEX_SHA256 = (
    "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
)
SERVER_RULE_REL = Path(".agents/rules/服务器测试包生成规则.md")
SERVER_RULE_SHA256 = (
    "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa"
)
QADD_RULE_REL = Path(".agents/rules/QLinearAdd算子配置规则.md")
QADD_RULE_SHA256 = (
    "fea780962c9029e589ece90de2af8c70058aee25cffaf9822f1e16f28ff2ecba"
)


def _rule_ids(path: Path) -> list[str]:
    return re.findall(
        r"规则 ID：`([^`]+)`",
        path.read_text(encoding="utf-8"),
    )


_BASE_BUILD_DIRECTORY = v7._build_directory


def _build_directory(destination: Path) -> Path:
    package = _BASE_BUILD_DIRECTORY(destination)
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = implementation.load_json(manifest_path)
    manifest.update(
        {
            "schema": (
                "qlinearadd-node0007-nested-lc-progress-canonical-"
                "server-package-v8"
            ),
            "superseded_diagnostic": {
                "zip": (
                    "artifacts/operator_config_validation/"
                    "r5-server-test-packages/"
                    f"{SOURCE_INSTALL_NAME}.zip"
                ),
                "sha256": SOURCE_ZIP_SHA256,
                "status": (
                    "QUARANTINED_NOT_RUN_ACTIVE_RULE_DRIFT_AFTER_BUILD"
                ),
                "functional_workload_unchanged": True,
            },
            "final_zip_rule_self_audit": {
                "rule_id": "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
                "rule_receipts": {
                    "generation_index": {
                        "path": INDEX_REL.as_posix(),
                        "sha256": INDEX_SHA256,
                        "current_match": True,
                    },
                    "server_package_rule": {
                        "path": SERVER_RULE_REL.as_posix(),
                        "sha256": SERVER_RULE_SHA256,
                        "current_match": True,
                    },
                    "qlinearadd_rule": {
                        "path": QADD_RULE_REL.as_posix(),
                        "sha256": QADD_RULE_SHA256,
                        "current_match": True,
                    },
                },
                "applicable_server_rule_ids": _rule_ids(
                    ROOT / SERVER_RULE_REL
                ),
                "applicable_qlinearadd_rule_ids": _rule_ids(
                    ROOT / QADD_RULE_REL
                ),
                "direct_final_zip_and_sidecar_validation_required": True,
                "all_required_negative_controls_required": True,
                "pass_field": "FINAL_ZIP_RULE_SELF_AUDIT_PASS",
                "errors_must_equal": 0,
                "validator": (
                    "tools/"
                    "validate_qlinearadd_node0007_progress_canonical_v8.py"
                ),
                "report": (
                    "artifacts/operator_config_validation/"
                    "r5-qlinearadd-node0007-progress-canonical-v8/"
                    "report.json"
                ),
            },
        }
    )
    manifest["provenance"]["server_package_rule"] = {
        "path": SERVER_RULE_REL.as_posix(),
        "sha256": SERVER_RULE_SHA256,
    }
    manifest["files"] = file_records(package)
    implementation.write_json(manifest_path, manifest)
    runtime_preflight(package)
    return package


def configure() -> None:
    v7.INSTALL_NAME = INSTALL_NAME
    v7.CONTRACT_REL = CONTRACT_REL
    v7.TASK_RECORD_REL = TASK_RECORD_REL
    v7.SERVER_RULE_REL = SERVER_RULE_REL
    v7.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    v7.configure()

    implementation.INSTALL_NAME = INSTALL_NAME
    implementation.MANIFEST_SCHEMA = (
        "qlinearadd-node0007-nested-lc-progress-canonical-server-package-v8"
    )
    implementation.PACKAGE_DESCRIPTION = (
        "ResNet50 node0007 canonical progress diagnostic with final-ZIP audit"
    )
    implementation.GENERATOR_REL = (
        "tools/"
        "build_qlinearadd_node0007_nested_lc_progress_canonical_v8_"
        "server_package.py"
    )
    implementation.CONTRACT_REL = CONTRACT_REL
    implementation.TASK_RECORD_REL = TASK_RECORD_REL
    implementation.SERVER_RULE_REL = SERVER_RULE_REL
    implementation.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    implementation.SUPERSEDED_IDENTITY = {
        "zip": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_INSTALL_NAME}.zip"
        ),
        "sha256": SOURCE_ZIP_SHA256,
        "reason": (
            "v7 was built before the final-ZIP rule self-audit receipt became "
            "an active package-manifest requirement"
        ),
        "functional_workload_unchanged": True,
    }
    implementation._return_allowlist = v7._return_allowlist
    implementation.run_script = v7._run_script
    implementation.build_directory = _build_directory


def main() -> int:
    configure()
    result = implementation.main()
    if result:
        return result
    validation_path = (
        implementation.OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json"
    )
    report = json.loads(validation_path.read_text(encoding="utf-8"))
    report.update(
        {
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "functional_fix": False,
            "source_v7_quarantined": True,
            "final_zip_rule_self_audit_contract_bound": True,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
        }
    )
    implementation.write_json(validation_path, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
