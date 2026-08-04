from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import (
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import file_records
from tools import build_gap_node0071_v13_buffer_to_ga_diag_package as base


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v15_feature_enable_rule"
INSTALL_NAME = "r5_n71_gap_v16_stage1_byte_slots"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "97a7366812210840ad67af40b3be3d90f7d7d44b997a29de41d366d877d97811"
)
SERVER_RULE_SHA256 = (
    "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025"
)
BITSTREAM_RELATIVE = (
    "workload/install/cfg_pkg/gap_node0071_sum_s1_128b.bin"
)
NEW_BITSTREAM = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-complete-stage1-byte-slots-local-e2-v2/"
    "install/cfg_pkg/gap_node0071_sum_s1_128b.bin"
)
LOCAL_REBUILD_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-node0071-stage1-byte-slots-v16/local_rebuild_report.json"
)
SUM_CONTRACT = (
    ROOT / "contracts/operator_config/gap_sum_stage1_byte_slots_local_e2_v2.json"
)
COMPLETE_CONTRACT = (
    ROOT / "contracts/operator_config/gap_node0071_stage1_byte_slots_local_e2_v2.json"
)
BYTE_LANE_RULE_ID = "CDA-GAP-8B-READ-BUFFER-BYTE-LANE-COVERAGE-001"
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
    BITSTREAM_RELATIVE,
}
RULES = [
    (
        ".agents/rules/生成前必读索引.md",
        "current generation routing index",
    ),
    (
        ".agents/rules/算子配置规则.md",
        "current common operator materialization rules",
    ),
    (
        ".agents/rules/NDP硬件字段语义.md",
        "current NDP field semantics",
    ),
    (
        ".agents/rules/服务器测试包生成规则.md",
        "current server-package rules",
    ),
    (
        ".agents/rules/GAP_int32_mac_bypass_rules.md",
        "current GAP int32_mac and byte-lane rules",
    ),
    (
        ".agents/rules/GAP_probe_v7_validator_rules.md",
        "current GAP dynamic observer gates",
    ),
    (
        ".agents/rules/精确UINT8量化尾专项规则.md",
        "current exact UINT8 tail family",
    ),
]


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def configure_source() -> None:
    base.SOURCE_NAME = SOURCE_NAME
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.SERVER_RULE_SHA256 = SERVER_RULE_SHA256


def current_rule_receipts() -> list[dict[str, Any]]:
    receipts = []
    for relative, reason in RULES:
        digest = sha256(ROOT / relative)
        receipts.append(
            {
                "path": relative,
                "sha256": digest,
                "reason": reason,
                "current_match": True,
            }
        )
    if receipts[3]["sha256"] != SERVER_RULE_SHA256:
        raise BuildError("current server rule SHA differs")
    return receipts


def update_manifest(
    package: Path, source_manifest: dict[str, Any]
) -> None:
    manifest = base.replace_identity(source_manifest)
    receipts = current_rule_receipts()
    receipt_by_path = {item["path"]: item["sha256"] for item in receipts}
    plan_sha = sha256(ROOT / ".agents/plan.md")
    rebuild = json.loads(LOCAL_REBUILD_REPORT.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "gap-node0071-stage1-byte-slots-server-package-v16",
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",
            "package_class": "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",
            "claim_boundary": (
                "stage1 8B read byte-lane coverage config fix; frozen W3, "
                "golden, tail, stages2-6, execplan and functional RTL reused; "
                "server natural terminal and 48-D comparison still required"
            ),
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": SOURCE_SHA256,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "source_numeric_payload_reused_without_rebuild": True,
            "functional_fix": True,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
        }
    )
    applicable = list(
        manifest["final_zip_rule_self_audit_contract"]["applicable_rule_ids"]
    )
    if BYTE_LANE_RULE_ID not in applicable:
        applicable.append(BYTE_LANE_RULE_ID)
    manifest["final_zip_rule_self_audit_contract"].update(
        {
            "read_receipt": receipts,
            "applicable_rule_ids": applicable,
            "all_current_match": True,
            "plan_sha256_mutable_provenance_only": plan_sha,
            "final_zip_independent_validator_required": True,
            "final_zip_rule_self_audit_pass":
                "PENDING_EXTERNAL_RELEASE_REPORT",
        }
    )
    manifest["rule_receipts"].update(
        {
            "generation_index_sha256": receipt_by_path[RULES[0][0]],
            "common_operator_rule_sha256": receipt_by_path[RULES[1][0]],
            "ndp_field_rule_sha256": receipt_by_path[RULES[2][0]],
            "server_rule_sha256": receipt_by_path[RULES[3][0]],
            "gap_int32_rule_sha256": receipt_by_path[RULES[4][0]],
            "gap_probe_rule_sha256": receipt_by_path[RULES[5][0]],
            "exact_uint8_tail_rule_sha256": receipt_by_path[RULES[6][0]],
            "current_match": True,
            "plan_sha256_mutable_provenance_only": plan_sha,
        }
    )
    manifest["stage1_buffer_byte_lane_fix_contract"] = {
        "rule_id": BYTE_LANE_RULE_ID,
        "root_cause": "STAGE1_8B_READ_REPEATS_BUFFER_BYTE_LANE_ZERO",
        "classification": "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",
        "changed_config_leaves": rebuild["minimal_config_diff"],
        "old_stage1_bitstream_sha256":
            rebuild["sum_bitstreams"][0]["old_sha256"],
        "new_stage1_bitstream_sha256":
            rebuild["sum_bitstreams"][0]["new_sha256"],
        "packaged_stage1_bitstream": BITSTREAM_RELATIVE,
        "rtl_equations": rebuild["rtl_equation"],
        "transactions_per_full_row": 4,
        "required_col_values": [0, 1, 2, 3],
        "all_banks_all_byte_lanes_exact_once": True,
        "sum_contract": str(SUM_CONTRACT.relative_to(ROOT)).replace("\\", "/"),
        "sum_contract_sha256": sha256(SUM_CONTRACT),
        "complete_contract":
            str(COMPLETE_CONTRACT.relative_to(ROOT)).replace("\\", "/"),
        "complete_contract_sha256": sha256(COMPLETE_CONTRACT),
        "local_rebuild_report":
            str(LOCAL_REBUILD_REPORT.relative_to(ROOT)).replace("\\", "/"),
        "local_rebuild_report_sha256": sha256(LOCAL_REBUILD_REPORT),
        "numeric_golden_regenerated": False,
        "functional_rtl_modified": False,
        "dynamic_return_required": True,
    }
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_stage1_byte_slots_v16_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": True,
            "diagnostic_only": False,
            "package_side_change": (
                "fresh identity plus one rebuilt stage1 config bitstream; "
                "GROUP0/GROUP1 COL end/stride change 32/4 to 4/1"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    if not NEW_BITSTREAM.is_file():
        raise BuildError("rebuilt stage1 bitstream absent")
    package = base.extract_source(destination)
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    source_records = file_records(package, exclude_manifest=False)
    base.rewrite_identity(package)
    target_bitstream = package / BITSTREAM_RELATIVE
    target_bitstream.write_bytes(NEW_BITSTREAM.read_bytes())
    (package / "README.md").write_text(
        "# GAP node0071 v16 stage1 byte-slot fix\n\n"
        "This package is `CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`. "
        "It fixes the stage1 8B-read Buffer byte-lane schedule: GROUP0 and "
        "GROUP1 COL now emit 0,1,2,3 so every enabled bank receives byte "
        "lanes 0/1/2/3 exactly once. Stages2-6, UINT8 tail, W3 inputs, "
        "golden, execplan, observer and functional RTL are unchanged.\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest)
    final_records = file_records(package, exclude_manifest=False)
    changed = {
        path
        for path in set(source_records) & set(final_records)
        if source_records[path] != final_records[path]
    }
    if set(source_records) != set(final_records):
        raise BuildError("relative file set changed")
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path set differs: {sorted(changed)}")
    if sha256(target_bitstream) != sha256(NEW_BITSTREAM):
        raise BuildError("packaged stage1 bitstream differs")
    for relative in set(final_records) - ALLOWED_CHANGED:
        if final_records[relative] != source_records[relative]:
            raise BuildError(f"frozen payload drifted: {relative}")
    return package, {
        "source_v15_zip_sha256": SOURCE_SHA256,
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
        "old_stage1_bitstream_sha256":
            source_records[BITSTREAM_RELATIVE]["sha256"],
        "new_stage1_bitstream_sha256":
            final_records[BITSTREAM_RELATIVE]["sha256"],
        "all_other_payloads_frozen_after_identity_normalization": True,
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_sha = sha256(zip_path)
    first_tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(prefix="gap-node0071-v16-repeat-") as tmp:
        repeated, _ = build_directory(Path(tmp))
        repeated_zip = Path(tmp) / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeated, repeated_zip, archive_root=INSTALL_NAME)
        if sha256(repeated_zip) != first_sha:
            raise BuildError("repeat ZIP differs")
        if file_records(repeated, exclude_manifest=False) != first_tree:
            raise BuildError("repeat package tree differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PACKAGE_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package, zip_path, sidecar, validation):
        if path.exists():
            print(f"refusing to overwrite: {path}")
            return 1
    try:
        package, proof = build_directory(output_root)
        repeated = repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        result = {
            "schema": "gap-node0071-stage1-byte-slots-v16-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "claim": "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",
            "package": str(package),
            "zip": str(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_sha256": digest,
            "sidecar": str(sidecar),
            "sidecar_sha256": sha256(sidecar),
            "source_zip": str(SOURCE_ZIP),
            **proof,
            "repeat_build": repeated,
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "config_semantics_rebuilt": True,
            "functional_rtl_modified": False,
            "server_action": False,
        }
        write_json(validation, result)
    except Exception as error:
        print(f"GAP v16 package build failed: {error}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
