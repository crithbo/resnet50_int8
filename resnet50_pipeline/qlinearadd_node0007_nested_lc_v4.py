from __future__ import annotations

import hashlib
import json
import struct
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from .hashing import sha256_file
from .ndp_patch_toolchain import (
    NODE0004_ASSUMED_HW_PATCHSET_ID,
    build_patchset_manifest,
)
from .operator_config_evidence_bundle import create_mapping_evidence_bundle
from .operator_config_execplan_evidence import create_execplan_evidence_bundle
from .qlinearadd_node0007_full_e2 import (
    DEQUANT_TEMPLATE_REL,
    LOCAL_BASES,
    NODE_ID,
    ADD_TEMPLATE_REL,
    PATCHSET_REL as FROZEN_PATCHSET_REL,
    ROOT_REL as FROZEN_ROOT_REL,
    TAIL_TEMPLATE_REL,
    _add_config as _frozen_add_config,
    _dequant_config as _frozen_dequant_config,
    _load,
    _record,
    _relocation_pad_config,
    _tail_configs,
    _validate_config,
    _write_json,
    config_bound_simulator as _frozen_numeric_simulator,
    graph_spec,
)


SCHEMA = "qlinearadd-node0007-nested-lc-full-local-e2-v4"
ROOT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-nested-lc-full-e2-v4"
)
CONFIG_REL = Path(
    "configs/native_ndp_sim/qlinearadd_node0007_nested_lc_full_e2_v4"
)
CONTRACT_REL = Path(
    "contracts/operator_config/"
    "qlinearadd_node0007_nested_lc_full_e2_v4.json"
)
PATCHSET_REL = Path(
    "contracts/ndp_patch_toolchain_"
    "qlinearadd_node0007_nested_lc_full_e2_v4.json"
)

SIGNED_FEEDBACK_END_MAX = 32_768
DEQUANT_OUTER = 4
DEQUANT_INNER = 9_408
DEQUANT_READ_OUTER_STRIDE = DEQUANT_INNER * 16
DEQUANT_WRITE_OUTER_STRIDE = DEQUANT_INNER * 64
ADD_OUTER = 8
ADD_INNER = 18_816
ADD_OUTER_STRIDE = ADD_INNER * 16

HARDWARE_RULE_REL = Path(".agents/rules/NDP硬件字段语义.md")
HARDWARE_RULE_SHA256 = (
    "4db23b6019a43a7cc7b30488c549fb9426fe374349e8224ad989cf107c9bd7a1"
)
QADD_RULE_REL = Path(".agents/rules/QLinearAdd算子配置规则.md")
QADD_RULE_SHA256 = (
    "dd4a8122d771ed5f4dbb9995fd6463ba14b179a72a515d2af5e91d30f2c71269"
)


class QLinearAddNode0007NestedLCError(ValueError):
    pass


def _ordered_u32_sha256(values: Iterable[int]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack("<I", value))
    return digest.hexdigest()


def _nested_offsets(outer: int, inner: int, stride: int) -> Iterable[int]:
    for outer_index in range(outer):
        base = outer_index * inner * stride
        for inner_index in range(inner):
            yield base + inner_index * stride


def _flat_offsets(count: int, stride: int) -> Iterable[int]:
    return (index * stride for index in range(count))


def geometry_equivalence_proof() -> dict[str, Any]:
    cases = {
        "dequant_read": (
            37_632,
            16,
            DEQUANT_OUTER,
            DEQUANT_INNER,
        ),
        "dequant_write": (
            37_632,
            64,
            DEQUANT_OUTER,
            DEQUANT_INNER,
        ),
        "fp32_add_read_write": (
            150_528,
            16,
            ADD_OUTER,
            ADD_INNER,
        ),
    }
    records: dict[str, Any] = {}
    for name, (count, stride, outer, inner) in cases.items():
        flat_hash = _ordered_u32_sha256(_flat_offsets(count, stride))
        nested_hash = _ordered_u32_sha256(
            _nested_offsets(outer, inner, stride)
        )
        records[name] = {
            "logical_occurrence_count": count,
            "element_stride_bytes": stride,
            "old_equation": f"flat_index * {stride}",
            "new_equation": (
                f"(outer_index * {inner} + inner_index) * {stride}"
            ),
            "outer_domain": outer,
            "inner_domain": inner,
            "ordered_old_sha256": flat_hash,
            "ordered_new_sha256": nested_hash,
            "ordered_equal": flat_hash == nested_hash,
            "first_offset": 0,
            "last_offset": (count - 1) * stride,
        }
    valid = all(item["ordered_equal"] for item in records.values())
    return {
        "schema": "qlinearadd-node0007-nested-lc-equivalence-v1",
        "valid": valid,
        "numeric_analysis_repeated": False,
        "arithmetic_semantics_changed": False,
        "qparams_changed": False,
        "tail_semantics_changed": False,
        "records": records,
    }


def _nested_dequant_config(
    template: dict[str, Any], *, scale_bits: str, zero_point: int, name: str
) -> dict[str, Any]:
    config = _frozen_dequant_config(
        template,
        scale_bits=scale_bits,
        zero_point=zero_point,
        name=name,
    )
    config["dram_loop_configs"]["LC0"].update(
        {"start": 0, "end": DEQUANT_OUTER, "stride": 1, "last_index": 0}
    )
    for key in ("LC1", "LC3"):
        config["dram_loop_configs"][key]["end"] = DEQUANT_INNER
    config["stream_engine"]["stream0"]["dim_stride"] = [
        16,
        16,
        DEQUANT_READ_OUTER_STRIDE,
    ]
    config["stream_engine"]["stream2"]["dim_stride"] = [
        64,
        64,
        DEQUANT_WRITE_OUTER_STRIDE,
    ]
    _validate_config(config, f"{name}_nested_lc")
    return config


def _nested_add_config(template: dict[str, Any]) -> dict[str, Any]:
    config = _frozen_add_config(template)
    config["dram_loop_configs"]["LC0"]["end"] = ADD_OUTER
    for key in ("LC1", "LC2", "LC3"):
        config["dram_loop_configs"][key]["end"] = ADD_INNER
    for stream in config["stream_engine"].values():
        stream["dim_stride"] = [16, ADD_OUTER_STRIDE, None]
    _validate_config(config, "fp32_add_nested_lc")
    return config


def build_configs(root: Path) -> dict[str, dict[str, Any]]:
    record = _record(root)
    qparams = record["qparams"]
    dequant_template = _load(root / DEQUANT_TEMPLATE_REL)
    add_template = _load(root / ADD_TEMPLATE_REL)
    tail_template = _load(root / TAIL_TEMPLATE_REL)
    tail_mul, tail_round = _tail_configs(tail_template)
    configs = {
        "op_a_dequant": _nested_dequant_config(
            dequant_template,
            scale_bits=qparams["a_scale"]["float32_bits"],
            zero_point=int(qparams["a_zero_point"]["value"]),
            name="a_dequant",
        ),
        "op_b_dequant": _nested_dequant_config(
            dequant_template,
            scale_bits=qparams["b_scale"]["float32_bits"],
            zero_point=int(qparams["b_zero_point"]["value"]),
            name="b_dequant",
        ),
        "op_relocation_pad": _relocation_pad_config(tail_template),
        "op_fp32_add": _nested_add_config(add_template),
        "op_tail_mul": tail_mul,
        "op_tail_round": tail_round,
    }
    for op_id, config in configs.items():
        for stream in config["stream_engine"].values():
            target = stream["target"]
            if target in LOCAL_BASES[op_id]:
                stream["base_addr"] = f"0x{LOCAL_BASES[op_id][target]:08x}"
        _validate_config(config, f"{op_id}_nested_lc_address_bound_static")
    validate_signed_feedback_bounds(configs)
    return configs


def validate_signed_feedback_bounds(
    configs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for op_id, config in configs.items():
        for name, loop in sorted(config["dram_loop_configs"].items()):
            start = int(loop["start"])
            end = int(loop["end"])
            stride = int(loop["stride"])
            record = {
                "operator_id": op_id,
                "loop": name,
                "start": start,
                "end": end,
                "stride": stride,
                "positive_stride": stride > 0,
                "signed_feedback_end_legal": (
                    stride <= 0 or end <= SIGNED_FEEDBACK_END_MAX
                ),
            }
            records.append(record)
            if stride > 0 and end > SIGNED_FEEDBACK_END_MAX:
                errors.append(f"{op_id}.{name}.end={end} exceeds 32768")
    if errors:
        raise QLinearAddNode0007NestedLCError(errors[0])
    return {
        "rule_id": "CDA-IGA-LC-SIGNED-FEEDBACK-END-BOUND-001",
        "valid": True,
        "maximum_positive_stride_end": max(
            item["end"] for item in records if item["positive_stride"]
        ),
        "records": records,
    }


def config_bound_simulator(
    root: Path, configs: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    active = configs or build_configs(root)
    bounds = validate_signed_feedback_bounds(active)
    geometry = geometry_equivalence_proof()
    if not geometry["valid"]:
        raise QLinearAddNode0007NestedLCError(
            "nested LC ordered occurrence proof differs"
        )
    numeric = _frozen_numeric_simulator(root)
    return {
        **numeric,
        "simulator": (
            "nested-LC final-config geometry binding plus frozen five-stage "
            "W3 config-bound comparison"
        ),
        "numeric_analysis_repeated": False,
        "frozen_numeric_verification_replayed": True,
        "signed_feedback_bounds": bounds,
        "nested_lc_ordered_equivalence": geometry,
        "configuration_sha256": {
            op_id: hashlib.sha256(
                json.dumps(
                    config,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            for op_id, config in active.items()
        },
    }


def materialize_local_inputs(
    root: Path, output_root: Path, config_root: Path
) -> dict[str, Any]:
    root = root.resolve()
    output = output_root.resolve()
    configs_root = config_root.resolve()
    if output.exists() or configs_root.exists() or (root / PATCHSET_REL).exists():
        raise QLinearAddNode0007NestedLCError(
            "fresh output/config/patchset paths required"
        )
    if sha256_file(root / HARDWARE_RULE_REL) != HARDWARE_RULE_SHA256:
        raise QLinearAddNode0007NestedLCError("hardware rule SHA drifted")
    if sha256_file(root / QADD_RULE_REL) != QADD_RULE_SHA256:
        raise QLinearAddNode0007NestedLCError("QLinearAdd rule SHA drifted")
    output.mkdir(parents=True)
    configs_root.mkdir(parents=True)
    configs = build_configs(root)
    for op_id, config in configs.items():
        _write_json(configs_root / f"{op_id}.json", config)
    graph = graph_spec()
    _write_json(output / "graph.json", graph)
    _write_json(
        root / PATCHSET_REL,
        build_patchset_manifest(
            root / "ndp-sim",
            patchset_id=NODE0004_ASSUMED_HW_PATCHSET_ID,
        ),
    )
    geometry = geometry_equivalence_proof()
    bounds = validate_signed_feedback_bounds(configs)
    simulator = config_bound_simulator(root, configs)
    frozen_scalar = root / FROZEN_ROOT_REL / "scalar_tail_proof.json"
    scalar_tail = _load(frozen_scalar)
    _write_json(output / "nested_lc_equivalence_proof.json", geometry)
    _write_json(output / "signed_feedback_bound_report.json", bounds)
    _write_json(output / "config_bound_simulator.json", simulator)
    receipt = {
        "schema": SCHEMA,
        "status": "LOCAL_INPUTS_MATERIALIZED",
        "node_id": NODE_ID,
        "hw_op_id": "hwop-0007-00",
        "numeric_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "frozen_stage0_and_tail_semantics_changed": False,
        "frozen_scalar_tail_proof": {
            "path": frozen_scalar.relative_to(root).as_posix(),
            "sha256": sha256_file(frozen_scalar),
            "result": scalar_tail,
        },
        "superseded_unsafe_schedule": {
            "root": FROZEN_ROOT_REL.as_posix(),
            "patchset": FROZEN_PATCHSET_REL.as_posix(),
            "server_package_v3_status": "QUARANTINED_NOT_RUN_NO_FUNCTIONAL_FIX",
        },
        "configs": {
            op_id: {
                "path": (CONFIG_REL / f"{op_id}.json").as_posix(),
                "sha256": sha256_file(configs_root / f"{op_id}.json"),
            }
            for op_id in configs
        },
        "graph": {
            "path": (ROOT_REL / "graph.json").as_posix(),
            "sha256": sha256_file(output / "graph.json"),
        },
        "nested_lc_equivalence": geometry,
        "signed_feedback_bounds": bounds,
        "config_bound_simulator": simulator,
        "rule_receipts": {
            "hardware": {
                "path": HARDWARE_RULE_REL.as_posix(),
                "sha256": HARDWARE_RULE_SHA256,
            },
            "qlinearadd": {
                "path": QADD_RULE_REL.as_posix(),
                "sha256": QADD_RULE_SHA256,
            },
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
    root = root.resolve()
    output = output_root.resolve()
    configs_root = config_root.resolve()
    mapping: dict[str, Path] = {}
    for op in graph_spec()["operators"]:
        op_id = op["id"]
        bundle = output / "mapping" / op_id
        if bundle.exists():
            raise QLinearAddNode0007NestedLCError(
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
        raise QLinearAddNode0007NestedLCError(
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
    "CONTRACT_REL",
    "PATCHSET_REL",
    "ROOT_REL",
    "QLinearAddNode0007NestedLCError",
    "build_configs",
    "config_bound_simulator",
    "geometry_equivalence_proof",
    "materialize_local_inputs",
    "materialize_mapping_and_execplan",
    "validate_signed_feedback_bounds",
]
