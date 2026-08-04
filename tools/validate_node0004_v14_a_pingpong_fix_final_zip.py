from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v13_final_zip_rule_self_audit as common  # noqa: E402
from resnet50_pipeline.conv_sa_contract import (  # noqa: E402
    validate_first_conv_signed_a_local_contract,
)


PLAN_SHA256 = "68cf915698b905c24f8e346dca0fac7b2012df3eaf18e563c9799685e9043025"
FRESH_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-a-pingpong-fix-c0-v2"
)
FRESH_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/node0004_a_pingpong_fix_c0_v2/"
    "accumulate_waves/wave-0.json"
)
FROZEN_CONFIG = (
    ROOT
    / "artifacts/operator_config_validation/r5-node0004-assumed-hardware-v1/"
    "mapping/conv/op_w0/source_config.json"
)
SOURCE_V13 = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v13_abpe_boundary.zip"
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _entries(path: Path) -> tuple[str, dict[str, bytes]]:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        infos = [item for item in archive.infolist() if not item.is_dir()]
        roots = {PurePosixPath(item.filename).parts[0] for item in infos}
        if len(roots) != 1:
            raise ValueError("ZIP must have exactly one root")
        root = next(iter(roots))
        return root, {
            PurePosixPath(*PurePosixPath(item.filename).parts[1:]).as_posix():
            archive.read(item)
            for item in infos
        }


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _leaf_diff(left: Any, right: Any, prefix: str = "") -> list[dict[str, Any]]:
    if isinstance(left, dict) and isinstance(right, dict):
        result: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in left:
                result.append({"path": child, "old": None, "new": right[key]})
            elif key not in right:
                result.append({"path": child, "old": left[key], "new": None})
            else:
                result.extend(_leaf_diff(left[key], right[key], child))
        return result
    if isinstance(left, list) and isinstance(right, list):
        result = []
        for index in range(max(len(left), len(right))):
            child = f"{prefix}[{index}]"
            if index >= len(left):
                result.append({"path": child, "old": None, "new": right[index]})
            elif index >= len(right):
                result.append({"path": child, "old": left[index], "new": None})
            else:
                result.extend(_leaf_diff(left[index], right[index], child))
        return result
    return [] if left == right else [{"path": prefix, "old": left, "new": right}]


def _prefixed_sca(path: Path, install_name: str) -> bytes:
    value = _json(path)
    prefix = f"install/cfg_pkg/{install_name}/runs/c0/"
    for item in value.values():
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            item["path"] = prefix + item["path"]
    return (
        json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _validate_config_fix(
    entries: dict[str, bytes], manifest: dict[str, Any]
) -> tuple[bool, list[str], dict[str, Any]]:
    errors: list[str] = []
    expected_diff = [
        {
            "path": "stream_engine.stream0.ping_pong",
            "old": 0,
            "new": 1,
        },
        {
            "path": "stream_engine.stream0.pingpong_last_index",
            "old": None,
            "new": 4,
        },
    ]
    frozen = _json(FROZEN_CONFIG)
    fresh = _json(FRESH_CONFIG)
    diff = _leaf_diff(frozen, fresh)
    if diff != expected_diff:
        errors.append(f"fresh logical leaf diff differs: {diff}")
    try:
        contract = validate_first_conv_signed_a_local_contract(fresh)
    except ValueError as error:
        contract = {"error": str(error)}
        errors.append(f"fresh signed-A contract failed: {error}")

    fix = manifest.get("configuration_fix", {})
    if (
        manifest.get("classification")
        != "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
        or manifest.get("status") != "PACKAGE_READY_NOT_RUN"
        or fix.get("leaf_changes") != expected_diff
    ):
        errors.append("manifest configuration-fix identity differs")

    pipeline = FRESH_ROOT / "execplan_conv/wave-0/pipeline_output"
    physical_pairs = {
        (
            "workload/runtime/runs/c0/install/cfg_pkg/"
            "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
        ): (
            pipeline
            / "install/cfg_pkg/"
            "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
        ).read_bytes(),
        "workload/runtime/runs/c0/install/execplan.txt": (
            pipeline / "install/execplan.txt"
        ).read_bytes(),
        "workload/runtime/runs/c0/install/execplan_op_w0.txt": (
            pipeline / "install/execplan_op_w0.txt"
        ).read_bytes(),
        "workload/runtime/runs/c0/sca_cfg.json": _prefixed_sca(
            pipeline / "sca_cfg.json", manifest["install_name"]
        ),
        "workload/runtime/runs/c0/sca_cfg_D.json": _prefixed_sca(
            pipeline / "sca_cfg_D.json", manifest["install_name"]
        ),
    }
    for relative, expected in physical_pairs.items():
        if entries.get(relative) != expected:
            errors.append(f"final ZIP physical asset differs: {relative}")

    _, source_entries = _entries(SOURCE_V13)
    frozen_matrix_paths = sorted(
        name
        for name in entries
        if name.startswith("workload/runtime/runs/c0/install/op_w0/")
        and "/matrix_" in name
        and name.endswith("_linearized_128bit.txt")
    )
    for relative in frozen_matrix_paths:
        if entries[relative] != source_entries.get(relative):
            errors.append(f"frozen C0 matrix differs: {relative}")
    if len(frozen_matrix_paths) != 84:
        errors.append(
            f"frozen C0 A/B/C matrix count is {len(frozen_matrix_paths)}; expected 84"
        )

    return (
        not errors,
        errors,
        {
            "logical_leaf_diff": diff,
            "signed_a_contract": contract,
            "physical_asset_count": len(physical_pairs),
            "frozen_matrix_count": len(frozen_matrix_paths),
            "fresh_bitstream_sha256": _sha256_bytes(
                physical_pairs[
                    "workload/runtime/runs/c0/install/cfg_pkg/"
                    "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
                ]
            ),
        },
    )


def _negative_controls(
    entries: dict[str, bytes], manifest: dict[str, Any]
) -> dict[str, Any]:
    records: dict[str, Any] = {}
    bitstream_key = (
        "workload/runtime/runs/c0/install/cfg_pkg/"
        "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    )
    _, source_entries = _entries(SOURCE_V13)
    changed = dict(entries)
    changed[bitstream_key] = source_entries[bitstream_key]
    valid, errors, _ = _validate_config_fix(changed, manifest)
    records["old_bitstream_reintroduced"] = {
        "failed_closed": not valid,
        "errors": errors,
    }

    bad_config = copy.deepcopy(_json(FRESH_CONFIG))
    bad_config["stream_engine"]["stream0"]["ping_pong"] = 0
    try:
        validate_first_conv_signed_a_local_contract(bad_config)
        config_failed = False
        config_error = None
    except ValueError as error:
        config_failed = True
        config_error = str(error)
    records["unilateral_a_pingpong"] = {
        "failed_closed": config_failed,
        "error": config_error,
    }

    bad_manifest = copy.deepcopy(manifest)
    bad_manifest.pop("configuration_fix", None)
    valid, errors, _ = _validate_config_fix(entries, bad_manifest)
    records["missing_fix_manifest"] = {
        "failed_closed": not valid,
        "errors": errors,
    }

    missing = dict(entries)
    missing.pop(bitstream_key)
    valid, errors, _ = _validate_config_fix(missing, manifest)
    records["missing_rebuilt_bitstream"] = {
        "failed_closed": not valid,
        "errors": errors,
    }
    records["all_failed_closed"] = all(
        item["failed_closed"]
        for key, item in records.items()
        if key != "all_failed_closed"
    )
    return records


def audit(
    project_root: Path,
    zip_path: Path,
    sidecar: Path,
    python: Path,
    builder: Path,
) -> dict[str, Any]:
    common.PLAN_SHA256 = PLAN_SHA256
    raw = common.audit(project_root, zip_path, sidecar, python, builder)
    _, entries = _entries(zip_path)
    manifest = json.loads(entries["package_manifest.json"])
    valid, fix_errors, detail = _validate_config_fix(entries, manifest)
    negatives = _negative_controls(entries, manifest)

    allowed_base_errors = {
        "check failed: diagnostic_only",
        "check failed: frozen_workload_provenance",
        "rule failed: CDA-SERVER-WORKLOAD-PROVENANCE-001",
    }
    unexpected_base_errors = [
        item for item in raw["errors"] if item not in allowed_base_errors
    ]
    errors = list(unexpected_base_errors)
    errors.extend(f"CONFIG_FIX: {item}" for item in fix_errors)
    if not negatives["all_failed_closed"]:
        errors.append("configuration-fix negative control did not fail closed")

    raw["checks"].pop("diagnostic_only", None)
    raw["checks"].pop("frozen_workload_provenance", None)
    raw["checks"]["config_functional_fix_classification"] = (
        manifest.get("classification")
        == "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
    )
    raw["checks"]["configuration_rebuild_provenance"] = valid
    raw["applicable_rule_ids"]["CDA-SERVER-WORKLOAD-PROVENANCE-001"] = valid
    raw["not_applicable"]["diagnostic_only_frozen_workload_equality"] = (
        "not applicable because two authorized config leaves and their "
        "derived bitstream/execplan/SCA were intentionally rebuilt"
    )
    raw["not_applicable"]["CDA-SERVER-RESULT-GATE-CONJUNCTION-001"] = (
        "package is not a dynamic PASS; future return must satisfy the full "
        "compile/run/terminal/formal-D conjunction"
    )
    all_negatives = (
        raw["all_required_negative_controls_fail_closed"]
        and negatives["all_failed_closed"]
    )
    passed = not errors and all_negatives and valid
    raw.update(
        {
            "schema": "node0004-v14-a-pingpong-fix-final-zip-audit-v1",
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
            "status": (
                "PACKAGE_READY_NOT_RUN"
                if passed
                else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
            ),
            "errors": errors,
            "error_count": len(errors),
            "all_required_negative_controls_fail_closed": all_negatives,
            "configuration_fix_validation": {
                "valid": valid,
                "errors": fix_errors,
                "detail": detail,
                "negative_controls": negatives,
            },
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": True,
        }
    )
    return raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--builder", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        args.project_root.resolve(),
        args.zip.resolve(),
        args.sidecar.resolve(),
        args.python.resolve(),
        args.builder.resolve(),
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
