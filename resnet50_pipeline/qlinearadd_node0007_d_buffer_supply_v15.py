from __future__ import annotations

import copy
import hashlib
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
from .qlinearadd_node0007_nested_lc_v4 import (
    CONFIG_REL as SOURCE_CONFIG_REL,
    ROOT_REL as SOURCE_ROOT_REL,
    build_configs as build_source_configs,
    graph_spec,
)


ROOT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-d-buffer-supply-v15"
)
CONFIG_REL = Path(
    "configs/native_ndp_sim/qlinearadd_node0007_d_buffer_supply_v15"
)
PATCHSET_REL = Path(
    "contracts/ndp_patch_toolchain_"
    "qlinearadd_node0007_d_buffer_supply_v15.json"
)
SOURCE_SIMULATOR_REL = SOURCE_ROOT_REL / "config_bound_simulator.json"
FIXED_STAGES = ("op_relocation_pad", "op_tail_mul", "op_tail_round")


class QLinearAddNode0007DBufferSupplyError(ValueError):
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
        transaction_bytes = _transaction_bytes(
            config["stream_engine"]["stream2"]
        )
        spatial_bytes = int(
            config["stream_engine"]["stream2"]["buf_spatial_size"]
        )
        if transaction_bytes % spatial_bytes:
            raise QLinearAddNode0007DBufferSupplyError(
                f"{stage}: transaction/spatial bytes are not integral"
            )
        row_trips = transaction_bytes // spatial_bytes
        config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["end"] = row_trips
        config["buffer_config"]["buffer5"]["buf_end_row_addr"] = row_trips - 1
    validate_d_buffer_supply(configs)
    return configs


def validate_d_buffer_supply(
    configs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records: dict[str, Any] = {}
    errors: list[str] = []
    for stage, config in configs.items():
        stream = config["stream_engine"]["stream2"]
        transaction_bytes = _transaction_bytes(stream)
        spatial_bytes = int(stream["buf_spatial_size"])
        row = config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]
        start = int(row["start"])
        end = int(row["end"])
        stride = int(row["stride"])
        row_trips = len(range(start, end, stride))
        supplied_bytes = row_trips * spatial_bytes
        buffer_end_row = int(
            config["buffer_config"]["buffer5"]["buf_end_row_addr"]
        )
        valid = (
            supplied_bytes == transaction_bytes
            and buffer_end_row == row_trips - 1
        )
        records[stage] = {
            "transaction_equation": "product(idx_size[j] + 1), null => 1",
            "idx_size": stream["idx_size"],
            "transaction_bytes": transaction_bytes,
            "buffer_bytes_per_row": spatial_bytes,
            "group2_row_lc": {
                "start": start,
                "end": end,
                "stride": stride,
                "trip_count": row_trips,
            },
            "supplied_bytes": supplied_bytes,
            "buffer5_end_row_addr": buffer_end_row,
            "conservation_valid": valid,
        }
        if not valid:
            errors.append(
                f"{stage}: transaction={transaction_bytes}, "
                f"supply={supplied_bytes}, end_row={buffer_end_row}"
            )
    if errors:
        raise QLinearAddNode0007DBufferSupplyError(errors[0])
    return {
        "schema": "qlinearadd-node0007-d-buffer-supply-proof-v1",
        "valid": True,
        "rule_basis": [
            "CDA-QADD-COMPOSITE-BACKEND-001 occurrence conservation",
            "NDP hardware cross-unit coverage gate",
        ],
        "records": records,
    }


def _leaf_diffs(before: Any, after: Any, prefix: str = "") -> list[dict[str, Any]]:
    if isinstance(before, dict) and isinstance(after, dict):
        result: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in before or key not in after:
                result.append(
                    {
                        "path": child,
                        "old": before.get(key),
                        "new": after.get(key),
                    }
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
    if before != after:
        return [{"path": prefix, "old": before, "new": after}]
    return []


def materialize_local_inputs(
    root: Path, output_root: Path, config_root: Path
) -> dict[str, Any]:
    output = output_root.resolve()
    configs_root = config_root.resolve()
    patchset = (root / PATCHSET_REL).resolve()
    if output.exists() or configs_root.exists() or patchset.exists():
        raise QLinearAddNode0007DBufferSupplyError(
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
    diffs = {
        stage: _leaf_diffs(source[stage], configs[stage])
        for stage in configs
    }
    expected_paths = {
        "buffer_config.buffer5.buf_end_row_addr",
        "buffer_loop_configs.GROUP2.ROW_LC.end",
    }
    for stage, stage_diffs in diffs.items():
        paths = {item["path"] for item in stage_diffs}
        if stage in FIXED_STAGES:
            if paths != expected_paths:
                raise QLinearAddNode0007DBufferSupplyError(
                    f"{stage}: unexpected leaf delta {sorted(paths)}"
                )
        elif paths:
            raise QLinearAddNode0007DBufferSupplyError(
                f"{stage}: unrelated leaf delta {sorted(paths)}"
            )
    source_simulator = root / SOURCE_SIMULATOR_REL
    receipt = {
        "schema": "qlinearadd-node0007-d-buffer-supply-local-input-v1",
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
                "sha256": sha256_file(source_simulator),
                "reused_without_recomputation": True,
            },
        },
        "authorized_config_leaf_deltas": diffs,
        "d_buffer_supply_proof": validate_d_buffer_supply(configs),
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
            raise QLinearAddNode0007DBufferSupplyError(
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
        raise QLinearAddNode0007DBufferSupplyError(
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
    "validate_d_buffer_supply",
]
