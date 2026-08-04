from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .hashing import sha256_file
from .ndp_patch_toolchain import (
    NODE0004_ASSUMED_HW_PATCHSET_ID,
    build_patchset_manifest,
)
from .operator_config_evidence_bundle import create_mapping_evidence_bundle
from .operator_config_execplan_evidence import create_execplan_evidence_bundle
from .qlinearadd_node0007_d_buffer_supply_v15 import (
    CONFIG_REL as SOURCE_CONFIG_REL,
    FIXED_STAGES,
    ROOT_REL as SOURCE_ROOT_REL,
    build_configs as build_source_configs,
    graph_spec,
)
from .qlinearadd_node0007_nested_lc_v4 import (
    ROOT_REL as NUMERIC_SOURCE_ROOT_REL,
)


ROOT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-d-buffer-column-pair-v18"
)
CONFIG_REL = Path(
    "configs/native_ndp_sim/qlinearadd_node0007_d_buffer_column_pair_v18"
)
PATCHSET_REL = Path(
    "contracts/ndp_patch_toolchain_"
    "qlinearadd_node0007_d_buffer_column_pair_v18.json"
)
SOURCE_SIMULATOR_REL = NUMERIC_SOURCE_ROOT_REL / "config_bound_simulator.json"
NATIVE_FP32_WRITE_ORACLE = Path(
    "ndp-sim/jsons/decode_add_fp32N_fp32N_fp32N.json"
)


class QLinearAddNode0007DBufferColumnPairError(ValueError):
    pass


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _transaction_bytes(stream: dict[str, Any]) -> int:
    value = 1
    for encoded in stream["idx_size"]:
        value *= 1 if encoded is None else int(encoded) + 1
    return value


def build_configs(root: Path) -> dict[str, dict[str, Any]]:
    configs = copy.deepcopy(build_source_configs(root))
    for stage in FIXED_STAGES:
        config = configs[stage]
        stream = config["stream_engine"]["stream2"]
        transaction_bytes = _transaction_bytes(stream)
        read_bytes = int(stream["buf_spatial_size"])
        if transaction_bytes != 32 or read_bytes != 16:
            raise QLinearAddNode0007DBufferColumnPairError(
                f"{stage}: expected frozen 32B transaction / 16B MSE read"
            )
        row = config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]
        col = config["buffer_loop_configs"]["GROUP2"]["COL_LC"]
        row.update({"start": 0, "end": 1, "stride": 1})
        col.update({"start": 0, "end": transaction_bytes, "stride": read_bytes})
        config["buffer_config"]["buffer5"]["buf_end_row_addr"] = 0
    validate_d_buffer_column_pair(configs)
    return configs


def validate_d_buffer_column_pair(
    configs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records: dict[str, Any] = {}
    errors: list[str] = []
    for stage in FIXED_STAGES:
        config = configs[stage]
        stream = config["stream_engine"]["stream2"]
        transaction_bytes = _transaction_bytes(stream)
        read_bytes = int(stream["buf_spatial_size"])
        row = config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]
        col = config["buffer_loop_configs"]["GROUP2"]["COL_LC"]
        rows = list(range(int(row["start"]), int(row["end"]), int(row["stride"])))
        cols = list(range(int(col["start"]), int(col["end"]), int(col["stride"])))
        windows = [
            {
                "row": row_index,
                "col_start": col_index,
                "col_end_exclusive": col_index + read_bytes,
            }
            for row_index in rows
            for col_index in cols
        ]
        covered = [
            byte
            for window in windows
            for byte in range(window["col_start"], window["col_end_exclusive"])
        ]
        end_row = int(config["buffer_config"]["buffer5"]["buf_end_row_addr"])
        valid = (
            rows == [0]
            and cols == [0, 16]
            and covered == list(range(transaction_bytes))
            and end_row == 0
        )
        if not valid:
            errors.append(f"{stage}: row/column 16B window partition differs")
        records[stage] = {
            "buffer_physical_row_bytes": 32,
            "buffer_physical_row_equation": "8 banks * 4 bytes",
            "mse_read_bytes": read_bytes,
            "transaction_bytes": transaction_bytes,
            "row_indices": rows,
            "column_indices": cols,
            "read_windows": windows,
            "covered_byte_offsets": covered,
            "buffer5_end_row_addr": end_row,
            "exact_partition_valid": valid,
        }
    if errors:
        raise QLinearAddNode0007DBufferColumnPairError(errors[0])
    return {
        "schema": "qlinearadd-node0007-d-buffer-column-pair-proof-v1",
        "valid": True,
        "old_scalar_formula_refuted": True,
        "old_formula": (
            "transaction_bytes = trip_count(GROUP2.ROW_LC) * "
            "stream2.buf_spatial_size"
        ),
        "replacement_formula": (
            "transaction byte coverage = disjoint union over paired "
            "(ROW_LC, COL_LC) windows; each MSE read window has "
            "stream2.buf_spatial_size bytes"
        ),
        "rtl_width_receipt": {
            "buffer_row_bytes": 32,
            "buffer_bank_count": 8,
            "buffer_bank_bytes": 4,
            "mse_request_lanes": 16,
            "mse_lane_bytes": 1,
        },
        "native_oracle": NATIVE_FP32_WRITE_ORACLE.as_posix(),
        "records": records,
    }


def _leaf_diffs(before: Any, after: Any, prefix: str = "") -> list[dict[str, Any]]:
    if isinstance(before, dict) and isinstance(after, dict):
        result: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in before or key not in after:
                result.append(
                    {"path": child, "old": before.get(key), "new": after.get(key)}
                )
            else:
                result.extend(_leaf_diffs(before[key], after[key], child))
        return result
    if isinstance(before, list) and isinstance(after, list):
        result = []
        for index in range(max(len(before), len(after))):
            child = f"{prefix}[{index}]"
            old = before[index] if index < len(before) else None
            new = after[index] if index < len(after) else None
            result.extend(_leaf_diffs(old, new, child))
        return result
    return [{"path": prefix, "old": before, "new": after}] if before != after else []


def materialize_local_inputs(
    root: Path, output_root: Path, config_root: Path
) -> dict[str, Any]:
    output = output_root.resolve()
    configs_root = config_root.resolve()
    patchset = (root / PATCHSET_REL).resolve()
    if output.exists() or configs_root.exists() or patchset.exists():
        raise QLinearAddNode0007DBufferColumnPairError(
            "fresh output/config/patchset paths required"
        )
    source = build_source_configs(root)
    configs = build_configs(root)
    output.mkdir(parents=True)
    configs_root.mkdir(parents=True)
    for stage, config in configs.items():
        _write_json(configs_root / f"{stage}.json", config)
    _write_json(output / "graph.json", graph_spec())
    _write_json(
        patchset,
        build_patchset_manifest(
            root / "ndp-sim",
            patchset_id=NODE0004_ASSUMED_HW_PATCHSET_ID,
        ),
    )
    expected_paths = {
        "buffer_config.buffer5.buf_end_row_addr",
        "buffer_loop_configs.GROUP2.COL_LC.end",
        "buffer_loop_configs.GROUP2.COL_LC.stride",
        "buffer_loop_configs.GROUP2.ROW_LC.end",
    }
    diffs = {
        stage: _leaf_diffs(source[stage], configs[stage]) for stage in configs
    }
    for stage, stage_diffs in diffs.items():
        paths = {item["path"] for item in stage_diffs}
        if stage in FIXED_STAGES:
            if paths != expected_paths:
                raise QLinearAddNode0007DBufferColumnPairError(
                    f"{stage}: unexpected leaf delta {sorted(paths)}"
                )
        elif paths:
            raise QLinearAddNode0007DBufferColumnPairError(
                f"{stage}: unrelated leaf delta {sorted(paths)}"
            )
    receipt = {
        "schema": "qlinearadd-node0007-d-buffer-column-pair-local-input-v1",
        "status": "LOCAL_INPUTS_MATERIALIZED",
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "config_numeric_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "functional_rtl_modified": False,
        "frozen_semantics": {
            "w3_qparams_tail_workload_golden_changed": False,
            "source_config_root": SOURCE_CONFIG_REL.as_posix(),
            "source_local_e2_root": SOURCE_ROOT_REL.as_posix(),
            "source_config_bound_simulator": {
                "path": SOURCE_SIMULATOR_REL.as_posix(),
                "sha256": sha256_file(root / SOURCE_SIMULATOR_REL),
                "reused_without_recomputation": True,
            },
        },
        "authorized_config_leaf_deltas": diffs,
        "d_buffer_column_pair_proof": validate_d_buffer_column_pair(configs),
        "configs": {
            stage: {
                "path": (CONFIG_REL / f"{stage}.json").as_posix(),
                "sha256": sha256_file(configs_root / f"{stage}.json"),
            }
            for stage in configs
        },
        "graph": {
            "path": (ROOT_REL / "graph.json").as_posix(),
            "sha256": sha256_file(output / "graph.json"),
        },
    }
    _write_json(output / "local_input_receipt.json", receipt)
    return receipt


def materialize_mapping_and_execplan(
    root: Path,
    output_root: Path,
    config_root: Path,
    python_executable: Path,
) -> dict[str, Any]:
    output = output_root.resolve()
    configs_root = config_root.resolve()
    mapping: dict[str, Path] = {}
    for op in graph_spec()["operators"]:
        op_id = op["id"]
        bundle = output / "mapping" / op_id
        if bundle.exists():
            raise QLinearAddNode0007DBufferColumnPairError(
                f"empty mapping state required: {bundle}"
            )
        create_mapping_evidence_bundle(
            ndp_sim_root=root / "ndp-sim",
            config_path=configs_root / f"{op_id}.json",
            output_dir=bundle,
            python_executable=python_executable,
            patchset_manifest_path=root / PATCHSET_REL,
            heuristic_iterations=2_000,
            heuristic_restarts=4,
            timeout_seconds=600,
        )
        mapping[op_id] = bundle
    execplan = output / "execplan"
    if execplan.exists():
        raise QLinearAddNode0007DBufferColumnPairError(
            f"empty execplan state required: {execplan}"
        )
    create_execplan_evidence_bundle(
        ndp_sim_root=root / "ndp-sim",
        graph_path=output / "graph.json",
        mapping_bundles=mapping,
        output_dir=execplan,
        python_executable=python_executable,
        patchset_manifest_path=root / PATCHSET_REL,
        timeout_seconds=900,
    )
    result = {
        "mapping_count": len(mapping),
        "mapping_initial_state": "EMPTY",
        "execplan_initial_state": "EMPTY",
        "execplan_bundle": execplan.relative_to(root).as_posix(),
        "execplan_bundle_manifest_sha256": sha256_file(
            execplan / "bundle_manifest.json"
        ),
    }
    _write_json(output / "native_chain_receipt.json", result)
    return result


__all__ = [
    "CONFIG_REL",
    "FIXED_STAGES",
    "PATCHSET_REL",
    "ROOT_REL",
    "build_configs",
    "materialize_local_inputs",
    "materialize_mapping_and_execplan",
    "validate_d_buffer_column_pair",
]
