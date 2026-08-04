from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ROOT_NAME = "r5_n71_gap_v16_stage1_byte_slots"
SOURCE_NAME = "r5_n71_gap_v15_feature_enable_rule"
PACKAGE_DIR = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = PACKAGE_DIR / f"{SOURCE_NAME}.zip"
BITSTREAM_RELATIVE = (
    "workload/install/cfg_pkg/gap_node0071_sum_s1_128b.bin"
)
RULE_ID = "CDA-GAP-8B-READ-BUFFER-BYTE-LANE-COVERAGE-001"
EXPECTED_DIFF = [
    {
        "path": "buffer_loop_configs.GROUP0.COL_LC.end",
        "old": 32,
        "new": 4,
    },
    {
        "path": "buffer_loop_configs.GROUP0.COL_LC.stride",
        "old": 4,
        "new": 1,
    },
    {
        "path": "buffer_loop_configs.GROUP1.COL_LC.end",
        "old": 32,
        "new": 4,
    },
    {
        "path": "buffer_loop_configs.GROUP1.COL_LC.stride",
        "old": 4,
        "new": 1,
    },
]


class ValidationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def zip_payload(path: Path, root_name: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValidationError(f"ZIP CRC differs: {bad}")
        prefix = f"{root_name}/"
        for info in archive.infolist():
            if info.is_dir():
                continue
            if not info.filename.startswith(prefix):
                raise ValidationError(f"ZIP root differs: {info.filename}")
            relative = info.filename[len(prefix):]
            if relative in files:
                raise ValidationError(f"duplicate member: {relative}")
            files[relative] = archive.read(info)
    return files


def validate_payload(
    files: dict[str, bytes], source: dict[str, bytes]
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    declared = manifest.get("files", {})
    if set(files) != set(declared) | {"TEST_PACKAGE_MANIFEST.json"}:
        errors.append("manifest exact-set differs")
    for relative, receipt in declared.items():
        payload = files.get(relative)
        if (
            payload is None
            or len(payload) != receipt.get("size_bytes")
            or sha256_bytes(payload) != receipt.get("sha256")
        ):
            errors.append(f"manifest receipt differs: {relative}")
    contract = manifest.get("stage1_buffer_byte_lane_fix_contract", {})
    if (
        manifest.get("install_name") != ROOT_NAME
        or manifest.get("claim")
        != "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
        or manifest.get("functional_fix") is not True
    ):
        errors.append("package identity/classification differs")
    if (
        contract.get("rule_id") != RULE_ID
        or contract.get("root_cause")
        != "STAGE1_8B_READ_REPEATS_BUFFER_BYTE_LANE_ZERO"
        or contract.get("changed_config_leaves") != EXPECTED_DIFF
        or contract.get("required_col_values") != [0, 1, 2, 3]
        or contract.get("transactions_per_full_row") != 4
        or contract.get("all_banks_all_byte_lanes_exact_once") is not True
    ):
        errors.append("stage1 byte-lane semantic contract differs")
    bitstream = files.get(BITSTREAM_RELATIVE, b"")
    old_bitstream = source.get(BITSTREAM_RELATIVE, b"")
    if (
        not bitstream
        or bitstream == old_bitstream
        or sha256_bytes(bitstream)
        != contract.get("new_stage1_bitstream_sha256")
        or sha256_bytes(old_bitstream)
        != contract.get("old_stage1_bitstream_sha256")
    ):
        errors.append("stage1 bitstream replacement differs")
    applicable = manifest.get(
        "final_zip_rule_self_audit_contract", {}
    ).get("applicable_rule_ids", [])
    if RULE_ID not in applicable:
        errors.append("byte-lane rule ID absent")
    frozen = set(files) - {
        "TEST_PACKAGE_MANIFEST.json",
        "README.md",
        "PREPARE_AND_RUN.sh",
        "workload/sca_cfg.json",
        "workload/sca_cfg_D.json",
        BITSTREAM_RELATIVE,
    }
    if set(source) != set(files):
        errors.append("relative file set differs")
    elif any(source[path] != files[path] for path in frozen):
        errors.append("unrelated frozen payload differs")
    return not errors, errors


def validate(target: Path, root_name: str) -> dict[str, Any]:
    files = zip_payload(target, root_name)
    source = zip_payload(SOURCE_ZIP, SOURCE_NAME)
    valid, errors = validate_payload(files, source)
    if not valid:
        raise ValidationError("; ".join(errors))
    controls: dict[str, Any] = {}

    def control(name: str, mutated: dict[str, bytes]) -> None:
        passed, observed = validate_payload(mutated, source)
        controls[name] = {
            "failed_closed": not passed,
            "errors": observed,
        }
        if passed:
            raise ValidationError(f"negative control did not fail: {name}")

    old_payload = dict(files)
    old_payload[BITSTREAM_RELATIVE] = source[BITSTREAM_RELATIVE]
    control("old_stage1_bitstream_restored", old_payload)

    missing_leaf = dict(files)
    manifest = json.loads(missing_leaf["TEST_PACKAGE_MANIFEST.json"])
    manifest["stage1_buffer_byte_lane_fix_contract"][
        "changed_config_leaves"
    ] = EXPECTED_DIFF[:-1]
    missing_leaf["TEST_PACKAGE_MANIFEST.json"] = json.dumps(manifest).encode()
    control("one_fix_leaf_removed", missing_leaf)

    old_cols = dict(files)
    manifest = json.loads(old_cols["TEST_PACKAGE_MANIFEST.json"])
    manifest["stage1_buffer_byte_lane_fix_contract"][
        "required_col_values"
    ] = [0, 4, 8, 12]
    old_cols["TEST_PACKAGE_MANIFEST.json"] = json.dumps(manifest).encode()
    control("old_repeated_byte_lane_schedule", old_cols)

    mislabeled = dict(files)
    manifest = json.loads(mislabeled["TEST_PACKAGE_MANIFEST.json"])
    manifest["claim"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    manifest["functional_fix"] = False
    mislabeled["TEST_PACKAGE_MANIFEST.json"] = json.dumps(manifest).encode()
    control("functional_fix_mislabeled", mislabeled)

    missing_rule = dict(files)
    manifest = json.loads(missing_rule["TEST_PACKAGE_MANIFEST.json"])
    applicable = manifest["final_zip_rule_self_audit_contract"][
        "applicable_rule_ids"
    ]
    manifest["final_zip_rule_self_audit_contract"][
        "applicable_rule_ids"
    ] = [item for item in applicable if item != RULE_ID]
    missing_rule["TEST_PACKAGE_MANIFEST.json"] = json.dumps(manifest).encode()
    control("byte_lane_rule_id_removed", missing_rule)

    return {
        "schema": "gap-node0071-stage1-byte-slots-v16-validation-v1",
        "status": "PASS",
        "target_zip": str(target),
        "target_zip_sha256": sha256_bytes(target.read_bytes()),
        "rule_id": RULE_ID,
        "old_stage1_bitstream_sha256":
            sha256_bytes(source[BITSTREAM_RELATIVE]),
        "new_stage1_bitstream_sha256":
            sha256_bytes(files[BITSTREAM_RELATIVE]),
        "changed_config_leaves": EXPECTED_DIFF,
        "required_col_values": [0, 1, 2, 3],
        "all_banks_all_byte_lanes_exact_once": True,
        "negative_controls": controls,
        "all_negative_controls_fail_closed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target_zip", type=Path)
    parser.add_argument("--root-name", default=ROOT_NAME)
    args = parser.parse_args()
    try:
        result = validate(args.target_zip.resolve(), args.root_name)
    except Exception as error:
        print(f"stage1 byte-slot validation failed: {error}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
