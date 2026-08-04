from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from .gap_d_index_schedule import derive_gap_d_index_config
from .gap_native_package import (
    OP_ID,
    OP_TYPE,
    SLICE_COUNT,
    TRANSPORT_REL,
    validate_gap_native_transport,
)
from .gap_server_workload import (
    SLICE_COMPANION_FILES,
    _install_matrix_companions,
    _sca_references,
    _validate_128bit_lf,
    _validate_slice_companions,
)
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import OperatorConfigValidator
from .stage_operator_semantics_audit import require_gap_d_index_coverage


CONFIG_SCHEMA = "resnet50-gap-d-index-address-bound-config-v2"
WORKLOAD_SCHEMA = "resnet50-gap-repair-workload-v9"
SOURCE_WORKLOAD_REL = Path(
    "artifacts/operator_config_validation/r5-server-workloads/"
    "gap_hwop0071_sum_graph"
)
ADDRESS_BOUND_CONFIG_REL = Path(
    "configs/stage_codegen/hwop-0071-00-d-index-address-bound-v2"
)
ADDRESS_BOUND_CONFIG_PATH = ADDRESS_BOUND_CONFIG_REL / "config.json"
ADDRESS_BOUND_MANIFEST_PATH = ADDRESS_BOUND_CONFIG_REL / "manifest.json"
MAPPING_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-gap-d-index-address-bound-mapping-v2"
)
EXECPLAN_REL = Path(
    "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
    "gap-hwop0071-sum-d-index-v4"
)
RELEASE_GATE_REL = Path(
    "artifacts/operator_config_validation/r5-gap-repair-release-v9/"
    "GAP_REPAIR_RELEASE_GATE.json"
)
DEFAULT_OUTPUT_REL = Path(
    "artifacts/operator_config_validation/r5-server-workloads/"
    "gap_hwop0071_sum_repair_v9"
)
SOURCE_JSON_REL = Path(f"jsons/{OP_ID}_{OP_TYPE}.json")
GRAPH_NAME = "gap_hwop0071_sum_repair_v9_withbaseaddr.json"
PATCHSET_REL = Path("contracts/ndp_patch_toolchain_gap_v1.json")
D_INDEX_CONTRACT_REL = Path("contracts/operator_config/gap_d_index_schedule_v1.json")
SEMANTIC_REL = Path("contracts/gap_hwop0071_sum_d_index_v3_semantic_contract.json")
MANIFEST_NAME = "gap_package_manifest.json"
EXPECTED_TOP_LEVEL = {
    "config",
    "install",
    "jsons",
    MANIFEST_NAME,
    GRAPH_NAME,
    "instructions_explained.txt",
    "sca_cfg.json",
    "sca_cfg_D.json",
}


class GapRepairWorkloadError(ValueError):
    pass


_DERIVED_CONFIG_CACHE: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GapRepairWorkloadError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _files(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        if path.is_symlink():
            raise GapRepairWorkloadError(f"workload contains symlink: {relative}")
        records[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return records


def _tree_sha256(records: Mapping[str, Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(records.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _normalized_lf_bytes(path: Path) -> bytes:
    return (
        path.read_text(encoding="utf-8")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .encode("utf-8")
    )


def _copy_128bit_lf(source: Path, destination: Path) -> None:
    raw = _normalized_lf_bytes(source)
    lines = raw.splitlines()
    if not lines or any(
        len(line) != 128 or set(line) - {ord("0"), ord("1")} for line in lines
    ):
        raise GapRepairWorkloadError(f"invalid rebuilt 128-bit payload: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"\n".join(lines) + b"\n")


def _leaf_differences(
    before: Any, after: Any, path: str = "$"
) -> list[dict[str, Any]]:
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        if set(before) != set(after):
            return [{"json_path": path, "before": before, "after": after}]
        result: list[dict[str, Any]] = []
        for key in sorted(before):
            result.extend(_leaf_differences(before[key], after[key], f"{path}.{key}"))
        return result
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return [{"json_path": path, "before": before, "after": after}]
        result = []
        for index, (left, right) in enumerate(zip(before, after)):
            result.extend(_leaf_differences(left, right, f"{path}[{index}]"))
        return result
    if before == after:
        return []
    return [{"json_path": path, "before": before, "after": after}]


def derive_address_bound_d_index_config(
    project_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = project_root.resolve()
    cache_key = root.as_posix()
    cached = _DERIVED_CONFIG_CACHE.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached[0]), copy.deepcopy(cached[1])
    source = _load(root / SOURCE_WORKLOAD_REL / SOURCE_JSON_REL)
    unbound, request, _ = derive_gap_d_index_config(root)
    if (
        source["stream_engine"]["stream0"].get("base_addr") != "0x0"
        or source["stream_engine"]["stream1"].get("base_addr") != "0x18840"
    ):
        raise GapRepairWorkloadError("source server address binding differs")
    derived = copy.deepcopy(source)
    derived["dram_loop_configs"]["LC2"] = copy.deepcopy(
        unbound["dram_loop_configs"]["LC2"]
    )
    differences = _leaf_differences(source, derived)
    expected_paths = [
        "$.dram_loop_configs.LC2.end",
        "$.dram_loop_configs.LC2.last_index",
        "$.dram_loop_configs.LC2.outmost_loop",
        "$.dram_loop_configs.LC2.src_id",
    ]
    if [item["json_path"] for item in differences] != expected_paths:
        raise GapRepairWorkloadError(
            f"address-bound D-index patch differs: {differences}"
        )
    expected_values = {
        "$.dram_loop_configs.LC2.end": (1, 256),
        "$.dram_loop_configs.LC2.last_index": (1, 0),
        "$.dram_loop_configs.LC2.outmost_loop": (0, 1),
        "$.dram_loop_configs.LC2.src_id": ("DRAM_LC.LC0", None),
    }
    actual_values = {
        item["json_path"]: (item["before"], item["after"]) for item in differences
    }
    if actual_values != expected_values:
        raise GapRepairWorkloadError(f"LC2 exact values differ: {actual_values}")
    report = OperatorConfigValidator().validate(
        derived,
        source=ADDRESS_BOUND_CONFIG_PATH.as_posix(),
        development_mode=True,
    ).to_dict()
    if report.get("valid") is not True or report["facts"].get("issue_count") != 0:
        raise GapRepairWorkloadError(
            f"address-bound D-index config rejected: {report.get('first_error')}"
        )
    coverage = require_gap_d_index_coverage(derived, request)
    if (
        coverage.get("classification") != "RTL_PROVEN"
        or coverage.get("derived_distinct_transaction_bases") != 256
    ):
        raise GapRepairWorkloadError("address-bound D-index coverage differs")
    analysis = {
        "semantic_patches": differences,
        "coverage": coverage,
        "strict_validation": report,
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
    }
    _DERIVED_CONFIG_CACHE[cache_key] = (copy.deepcopy(derived), copy.deepcopy(analysis))
    return derived, analysis


def build_address_bound_d_index_config(
    project_root: Path, output_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise GapRepairWorkloadError(f"config output must be fresh: {output}")
    derived, analysis = derive_address_bound_d_index_config(root)
    output.mkdir(parents=True)
    config_path = output / "config.json"
    _write_json(config_path, derived)
    source_path = root / SOURCE_WORKLOAD_REL / SOURCE_JSON_REL
    manifest: dict[str, Any] = {
        "schema": CONFIG_SCHEMA,
        "status": "address_bound_d_index_config_ready_for_mapping",
        "request_id": analysis["request_id"],
        "request_sha256": analysis["request_sha256"],
        "source": {
            "path": (SOURCE_WORKLOAD_REL / SOURCE_JSON_REL).as_posix(),
            "sha256": sha256_file(source_path),
        },
        "config": {
            "path": ADDRESS_BOUND_CONFIG_PATH.as_posix(),
            "sha256": sha256_file(config_path),
            "canonical_sha256": sha256_bytes(canonical_json_bytes(derived)),
        },
        "semantic_patches": analysis["semantic_patches"],
        "d_index_coverage": analysis["coverage"],
        "strict_validation": {
            "valid": True,
            "issue_count": 0,
            "development_mode": True,
        },
        "preserved_address_binding": {
            "stream0": "0x0",
            "stream1": "0x18840",
        },
        "source_reference_modified": False,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    _write_json(output / "manifest.json", manifest)
    return manifest


def validate_address_bound_d_index_config(
    project_root: Path, output_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    manifest = _load(output / "manifest.json")
    receipt = manifest.pop("manifest_sha256", None)
    if receipt != sha256_bytes(canonical_json_bytes(manifest)):
        raise GapRepairWorkloadError("address-bound config manifest differs")
    manifest["manifest_sha256"] = receipt
    derived, analysis = derive_address_bound_d_index_config(root)
    if _load(output / "config.json") != derived:
        raise GapRepairWorkloadError("address-bound config content differs")
    if (
        manifest.get("schema") != CONFIG_SCHEMA
        or manifest.get("semantic_patches") != analysis["semantic_patches"]
        or manifest.get("d_index_coverage") != analysis["coverage"]
        or manifest.get("config", {}).get("sha256")
        != sha256_file(output / "config.json")
    ):
        raise GapRepairWorkloadError("address-bound config binding differs")
    return manifest


def _release_gate(root: Path) -> dict[str, Any]:
    from .gap_repair_release import validate_gap_repair_release_gate

    path = root / RELEASE_GATE_REL
    gate = _load(path)
    validate_gap_repair_release_gate(root, gate, execplan_root=root / EXECPLAN_REL)
    return gate


def _source_control_bindings(root: Path) -> dict[str, dict[str, Any]]:
    pipeline = root / EXECPLAN_REL / "pipeline_output"
    graph_paths = list(pipeline.glob("*_withbaseaddr.json"))
    if len(graph_paths) != 1:
        raise GapRepairWorkloadError("rebuilt execplan graph identity differs")
    paths = {
        "graph_withbaseaddr": graph_paths[0],
        "instructions_explained": pipeline / "instructions_explained.txt",
        "sca_cfg": pipeline / "sca_cfg.json",
        "sca_cfg_D": pipeline / "sca_cfg_D.json",
        "execplan": pipeline / "install" / "execplan.txt",
        "execplan_op0": pipeline / "install" / "execplan_op0.txt",
        "runtime_bitstream": (
            pipeline
            / "install"
            / "cfg_pkg"
            / f"{OP_ID}_{OP_TYPE}_bitstream_128b.bin"
        ),
        "pipeline_config": pipeline / SOURCE_JSON_REL,
    }
    for name, path in paths.items():
        if not path.is_file():
            raise GapRepairWorkloadError(f"rebuilt control file missing: {name}: {path}")
    return {
        name: {
            "source_path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for name, path in paths.items()
    }


def _verify_control_copy(root: Path, workload: Path) -> dict[str, dict[str, Any]]:
    source = _source_control_bindings(root)
    destinations = {
        "graph_withbaseaddr": workload / GRAPH_NAME,
        "instructions_explained": workload / "instructions_explained.txt",
        "sca_cfg": workload / "sca_cfg.json",
        "sca_cfg_D": workload / "sca_cfg_D.json",
        "execplan": workload / "install" / "execplan.txt",
        "execplan_op0": workload / "install" / "execplan_op0.txt",
        "runtime_bitstream": (
            workload
            / "install"
            / "cfg_pkg"
            / f"{OP_ID}_{OP_TYPE}_bitstream_128b.bin"
        ),
        "pipeline_config": workload / SOURCE_JSON_REL,
    }
    normalized_names = {"execplan", "execplan_op0", "runtime_bitstream"}
    result: dict[str, dict[str, Any]] = {}
    for name, destination in destinations.items():
        actual = sha256_file(destination)
        source_path = root / source[name]["source_path"]
        expected = (
            hashlib.sha256(_normalized_lf_bytes(source_path)).hexdigest()
            if name in normalized_names
            else source[name]["sha256"]
        )
        if actual != expected:
            raise GapRepairWorkloadError(f"rebuilt control copy differs: {name}")
        result[name] = {
            **source[name],
            "installed_path": destination.relative_to(workload).as_posix(),
            "installed_sha256": actual,
            "normalization": (
                "CRLF_or_LF_to_LF_only" if name in normalized_names else "none"
            ),
        }
    source_pipeline = root / EXECPLAN_REL / "pipeline_output"
    for directory in ("config", "jsons"):
        source_records = _files(source_pipeline / directory)
        installed_records = _files(workload / directory)
        if source_records != installed_records:
            raise GapRepairWorkloadError(
                f"rebuilt control directory copy differs: {directory}"
            )
    return result


def build_gap_repair_workload(
    project_root: Path, output_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise GapRepairWorkloadError(f"workload output must be fresh: {output}")
    validate_address_bound_d_index_config(root, root / ADDRESS_BOUND_CONFIG_REL)
    gate = _release_gate(root)
    transport = validate_gap_native_transport(root, root / TRANSPORT_REL)
    pipeline = root / EXECPLAN_REL / "pipeline_output"
    graph_paths = list(pipeline.glob("*_withbaseaddr.json"))
    if len(graph_paths) != 1:
        raise GapRepairWorkloadError("rebuilt execplan graph identity differs")

    output.mkdir(parents=True)
    shutil.copytree(pipeline / "config", output / "config")
    shutil.copytree(pipeline / "jsons", output / "jsons")
    shutil.copytree(pipeline / "install", output / "install")
    _copy_128bit_lf(
        pipeline / "install" / "execplan.txt",
        output / "install" / "execplan.txt",
    )
    _copy_128bit_lf(
        pipeline / "install" / "execplan_op0.txt",
        output / "install" / "execplan_op0.txt",
    )
    bitstream_name = f"{OP_ID}_{OP_TYPE}_bitstream_128b.bin"
    _copy_128bit_lf(
        pipeline / "install" / "cfg_pkg" / bitstream_name,
        output / "install" / "cfg_pkg" / bitstream_name,
    )
    shutil.copy2(graph_paths[0], output / GRAPH_NAME)
    shutil.copy2(
        pipeline / "instructions_explained.txt",
        output / "instructions_explained.txt",
    )
    shutil.copy2(pipeline / "sca_cfg.json", output / "sca_cfg.json")
    shutil.copy2(pipeline / "sca_cfg_D.json", output / "sca_cfg_D.json")

    matrix_records: dict[str, dict[str, Any]] = {}
    for record in transport["records"]:
        slice_id = int(record["slice_id"])
        destination = output / "install" / OP_ID / f"slice{slice_id:02d}"
        for tensor in ("A", "D"):
            source = root / TRANSPORT_REL / str(record[tensor]["path"])
            installed = destination / source.name
            matrix_records[installed.relative_to(output).as_posix()] = (
                _install_matrix_companions(source, installed, port=tensor)
            )

    controls = _verify_control_copy(root, output)
    sca = _load(output / "sca_cfg.json")
    sca_d = _load(output / "sca_cfg_D.json")
    references = _sca_references(output, sca) + _sca_references(output, sca_d)
    if len(references) != 34:
        raise GapRepairWorkloadError("repair workload SCA reference count differs")
    line_counts = {
        relative: _validate_128bit_lf(path) for _, relative, path in references
    }
    if (
        sca.get("Exec_Length")
        != line_counts.get(str(sca.get("ExecutionPlan", {}).get("path")))
        or _validate_slice_companions(output) != SLICE_COUNT
    ):
        raise GapRepairWorkloadError("repair workload SCA/matrix contract differs")

    records = _files(output)
    manifest: dict[str, Any] = {
        "schema": WORKLOAD_SCHEMA,
        "status": "server_test_workload_ready_dynamic_release_pending",
        "candidate_release": False,
        "package_name": "gap-hwop0071-sum-repair-v9",
        "full_rebuild": {
            "source_execplan_evidence": EXECPLAN_REL.as_posix(),
            "source_execplan_manifest_sha256": sha256_file(
                root / EXECPLAN_REL / "bundle_manifest.json"
            ),
            "release_gate": RELEASE_GATE_REL.as_posix(),
            "release_gate_sha256": sha256_file(root / RELEASE_GATE_REL),
            "planner_encoder_bitstream_execplan_sca_regenerated": True,
            "double_run_equal": True,
            "controls": controls,
        },
        "d_index_config": {
            "path": ADDRESS_BOUND_CONFIG_PATH.as_posix(),
            "sha256": sha256_file(root / ADDRESS_BOUND_CONFIG_PATH),
            "manifest_sha256": sha256_file(root / ADDRESS_BOUND_MANIFEST_PATH),
            "contract_sha256": sha256_file(root / D_INDEX_CONTRACT_REL),
            "lc2_exact_four_field_diff": gate["config_semantics"][
                "lc2_exact_four_field_diff"
            ],
            "distinct_32byte_transaction_bases_per_slice": 256,
            "expected_unique_128bit_write_addresses_per_slice": 512,
        },
        "matrix_payloads": {
            "transport_manifest_sha256": sha256_file(
                root / TRANSPORT_REL / "manifest.json"
            ),
            "records": matrix_records,
            "slice_count": SLICE_COUNT,
            "formal_d_lines_per_slice": 512,
            "independent_golden_mismatch_count": 0,
        },
        "server_bindings": {
            "sca_cfg": "sca_cfg.json",
            "sca_cfg_D": "sca_cfg_D.json",
        },
        "dynamic_release_pending": gate["remaining_blockers"],
        "source_reference_modified": False,
        "file_count": len(records),
        "tree_sha256": _tree_sha256(records),
        "files": records,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    _write_json(output / MANIFEST_NAME, manifest)
    validate_gap_repair_workload(root, output)
    return manifest


def validate_gap_repair_workload(
    project_root: Path, output_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    manifest = _load(output / MANIFEST_NAME)
    receipt = manifest.pop("manifest_sha256", None)
    if receipt != sha256_bytes(canonical_json_bytes(manifest)):
        raise GapRepairWorkloadError("repair workload manifest receipt differs")
    manifest["manifest_sha256"] = receipt
    if (
        manifest.get("schema") != WORKLOAD_SCHEMA
        or manifest.get("candidate_release") is not False
        or {path.name for path in output.iterdir()} != EXPECTED_TOP_LEVEL
    ):
        raise GapRepairWorkloadError("repair workload identity/shape differs")
    gate = _release_gate(root)
    if (
        manifest.get("full_rebuild", {}).get("release_gate_sha256")
        != sha256_file(root / RELEASE_GATE_REL)
        or manifest.get("dynamic_release_pending") != gate["remaining_blockers"]
    ):
        raise GapRepairWorkloadError("repair workload release-gate binding differs")
    validate_address_bound_d_index_config(root, root / ADDRESS_BOUND_CONFIG_REL)
    validate_gap_native_transport(root, root / TRANSPORT_REL)
    _verify_control_copy(root, output)
    actual = _files(output, exclude_manifest=True)
    if (
        manifest.get("files") != actual
        or manifest.get("file_count") != len(actual)
        or manifest.get("tree_sha256") != _tree_sha256(actual)
    ):
        raise GapRepairWorkloadError("repair workload tree receipt differs")
    if _load(output / SOURCE_JSON_REL) != _load(root / ADDRESS_BOUND_CONFIG_PATH):
        raise GapRepairWorkloadError("repair workload D-index config differs")
    sca = _load(output / "sca_cfg.json")
    sca_d = _load(output / "sca_cfg_D.json")
    references = _sca_references(output, sca) + _sca_references(output, sca_d)
    if len(references) != 34:
        raise GapRepairWorkloadError("repair workload SCA references differ")
    counts = {relative: _validate_128bit_lf(path) for _, relative, path in references}
    if (
        sca.get("Exec_Length")
        != counts.get(str(sca.get("ExecutionPlan", {}).get("path")))
        or _validate_slice_companions(output) != SLICE_COUNT
    ):
        raise GapRepairWorkloadError("repair workload installed payload differs")
    for slice_id in range(SLICE_COUNT):
        key = f"{OP_ID}_matrixD_slice{slice_id}"
        if sca_d.get(key, {}).get("length") != 512:
            raise GapRepairWorkloadError(
                f"repair workload D readback length differs: slice {slice_id}"
            )
        source = (
            root
            / TRANSPORT_REL
            / "data"
            / OP_ID
            / f"slice{slice_id:02d}"
            / "matrix_D_linearized_128bit.txt"
        )
        installed = (
            output
            / "install"
            / OP_ID
            / f"slice{slice_id:02d}"
            / "matrix_D_linearized_128bit.txt"
        )
        if source.read_bytes() != installed.read_bytes():
            raise GapRepairWorkloadError(
                f"repair workload D golden differs: slice {slice_id}"
            )
    forbidden = [
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if (
            path.name == "Bank_data"
            or path.suffix.lower() == ".zip"
            or "overlay" in path.name.lower()
            or "runner" in path.name.lower()
        )
    ]
    if forbidden:
        raise GapRepairWorkloadError(
            f"repair workload contains forbidden artifact: {forbidden[0]}"
        )
    return manifest


__all__ = [
    "ADDRESS_BOUND_CONFIG_REL",
    "DEFAULT_OUTPUT_REL",
    "EXECPLAN_REL",
    "GapRepairWorkloadError",
    "MAPPING_REL",
    "RELEASE_GATE_REL",
    "SOURCE_WORKLOAD_REL",
    "build_address_bound_d_index_config",
    "build_gap_repair_workload",
    "derive_address_bound_d_index_config",
    "validate_address_bound_d_index_config",
    "validate_gap_repair_workload",
]
