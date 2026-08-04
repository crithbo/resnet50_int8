from __future__ import annotations

import hashlib
import json
import shutil
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from tools.generate_active_ndpsim_node0004_accumulate_smoke_inputs import (
    _load_w3_bundle,
)

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_package_validator import OperatorConfigPackageValidator
from .operator_config_validator import OperatorConfigValidator, TargetProfile
from .typed_config_parameters import validate_typed_config_parameter_contract
from .w5_conv_preflight import _record_by_hw_op


NODE_ID = "node-0004"
HW_OP_ID = "hwop-0004-00"
REQUANT_HW_OP_ID = "hwop-0004-01"
WAVE_SAMPLES = (
    (0, 3, 6, 8, 10, 12, 14),
    (1, 4, 7, 9, 11, 13, 15),
    (2, 5),
)
WAVE_SLICE_COUNTS = (28, 28, 8)
WEIGHT_BYTES = 1024
ACTIVATION_BYTES = 200704
BIAS_BYTES = 64
ACCUMULATOR_BYTES = 200704
OP_ALLOCATION_BYTES = (
    WEIGHT_BYTES + ACTIVATION_BYTES + BIAS_BYTES + ACCUMULATOR_BYTES
)

TYPED_REL = Path("contracts/typed_config_parameter_contract.json")
SOURCE_CONFIG_REL = Path(
    "configs/native_ndp_sim/"
    "node0004_accumulate_wave0_nopp_r1_strict_v1/config.json"
)
CONFIG_ROOT_REL = Path("configs/native_ndp_sim/node0004_conv_three_wave_v1")
TRANSPORT_REL = Path(
    "artifacts/operator_config_validation/r5-node0004-conv-native-inputs-v1"
)
PATCHSET_REL = Path("contracts/ndp_patch_toolchain_conv_v1.json")
EXECPLAN_REL = Path(
    "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
    "node0004-conv-three-wave-v1"
)
SEMANTIC_REL = Path(
    "contracts/node0004_conv_three_wave_semantic_contract.json"
)
CANDIDATE_REL = Path(
    "artifacts/operator_config_validation/r5-server-candidates/"
    "node0004-conv-three-wave-v1"
)


class ConvNativePackageError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConvNativePackageError(f"cannot parse JSON: {path}") from error
    if not isinstance(value, dict):
        raise ConvNativePackageError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_128bit_text(path: Path, payload: bytes) -> dict[str, Any]:
    if not payload or len(payload) % 16:
        raise ConvNativePackageError(
            "Conv physical payload must be a non-empty 16-byte multiple"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        f"{int.from_bytes(payload[offset:offset + 16], 'little'):0128b}\n"
        for offset in range(0, len(payload), 16)
    )
    path.write_text(text, encoding="ascii", newline="\n")
    return {
        "path": path.as_posix(),
        "payload_bytes": len(payload),
        "line_count": len(payload) // 16,
        "sha256": sha256_file(path),
    }


def _mask(slice_count: int) -> str:
    return "0b" + "0" * (28 - slice_count) + "1" * slice_count


def operator_type(wave_index: int) -> str:
    if not 0 <= wave_index < 3:
        raise ConvNativePackageError(f"invalid Conv wave: {wave_index}")
    return f"resnet50_conv_node0004_wave{wave_index}"


def op_id(wave_index: int) -> str:
    return f"op_w{wave_index}"


def graph_spec() -> dict[str, Any]:
    operators = []
    for wave_index, slice_count in enumerate(WAVE_SLICE_COUNTS):
        operators.append(
            {
                "id": op_id(wave_index),
                "type": operator_type(wave_index),
                "used_slices": _mask(slice_count),
                "inputs": {
                    "A": {
                        "shape": [1, 1, WEIGHT_BYTES],
                        "dtype": "int8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                    "B": {
                        "shape": [1, 1, ACTIVATION_BYTES],
                        "dtype": "uint8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                    "C": {
                        "shape": [1, 1, BIAS_BYTES // 4],
                        "dtype": "int32",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                },
                "output": {
                    "shape": [1, 1, ACCUMULATOR_BYTES // 4],
                    "dtype": "int32",
                    "bank_interleave": 1,
                    "remapping": None,
                },
            }
        )
    return {
        "params": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "wave_count": 3,
            "source": (
                "W3 signed-A Conv28 physical bundle; complete batch16 "
                "three-wave dispatch"
            ),
        },
        "used_slices": _mask(28),
        "operators": operators,
    }


def _stream_by_target(config: Mapping[str, Any], target: str) -> dict[str, Any]:
    streams = config.get("stream_engine")
    if not isinstance(streams, Mapping):
        raise ConvNativePackageError("Conv source config has no stream engine")
    matches = [
        value
        for value in streams.values()
        if isinstance(value, dict) and value.get("target") == target
    ]
    if len(matches) != 1:
        raise ConvNativePackageError(
            f"Conv source config must contain one {target} stream"
        )
    return matches[0]


def build_strict_configs(
    project_root: Path,
    *,
    source_config_rel: Path = SOURCE_CONFIG_REL,
    reuse_wave_addresses: bool = False,
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    root = project_root.resolve()
    source_path = root / source_config_rel
    source = _load(source_path)
    configs: dict[int, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    offsets = {
        "A": 0,
        "B": WEIGHT_BYTES,
        "C": WEIGHT_BYTES + ACTIVATION_BYTES,
        "D": WEIGHT_BYTES + ACTIVATION_BYTES + BIAS_BYTES,
    }
    for wave_index in range(3):
        config = deepcopy(source)
        op_base = 0 if reuse_wave_addresses else wave_index * OP_ALLOCATION_BYTES
        addresses = {
            target: op_base + offset for target, offset in offsets.items()
        }
        if any(
            isinstance(stream, Mapping) and stream.get("target") == "B'"
            for stream in config.get("stream_engine", {}).values()
        ):
            addresses["B'"] = addresses["B"]
        for target, address in addresses.items():
            _stream_by_target(config, target)["base_addr"] = f"0x{address:08X}"
        report = OperatorConfigValidator().validate(
            config, source=f"{SOURCE_CONFIG_REL.as_posix()}#wave{wave_index}"
        )
        if not report.valid:
            first = report.issues[0]
            raise ConvNativePackageError(
                f"derived Conv config is not strict-valid: "
                f"{first.code} at {first.path}: {first.message}"
            )
        configs[wave_index] = config
        records.append(
            {
                "wave_index": wave_index,
                "operator_type": operator_type(wave_index),
                "op_id": op_id(wave_index),
                "active_slice_count": WAVE_SLICE_COUNTS[wave_index],
                "sample_ids": list(WAVE_SAMPLES[wave_index]),
                "stream_base_addresses": {
                    key: f"0x{value:08X}" for key, value in addresses.items()
                },
                "canonical_config_sha256": sha256_bytes(
                    canonical_json_bytes(config)
                ),
            }
        )
    return configs, {
        "schema": "resnet50-node0004-conv-three-wave-config-set-v1",
        "source": {
                "path": source_config_rel.as_posix(),
            "sha256": sha256_file(source_path),
            "policy": (
                "strict source with MSE0/SA-inport0 matched A ping-pong; "
                "address-only three-wave specialization"
            ),
        },
        "operator_allocation_bytes": OP_ALLOCATION_BYTES,
        "wave_address_policy": (
            "reuse_same_local_allocation"
            if reuse_wave_addresses
            else "disjoint_flat_allocations"
        ),
        "records": records,
    }


def _typed_stages(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    typed = _load(root / TYPED_REL)
    validate_typed_config_parameter_contract(typed)
    conv = _record_by_hw_op(typed, HW_OP_ID)
    requant = _record_by_hw_op(typed, REQUANT_HW_OP_ID)
    if (
        conv.get("node_id") != NODE_ID
        or conv.get("stage") != "accumulate"
        or conv.get("hw_op_type") != "ConvInt32Accumulate"
        or requant.get("predecessor_hw_op_ids") != [HW_OP_ID]
    ):
        raise ConvNativePackageError("node-0004 typed Conv identity differs")
    return conv, requant


def write_conv_native_inputs(
    project_root: Path,
    output_root: Path,
    config_root: Path,
    *,
    source_config_rel: Path = SOURCE_CONFIG_REL,
    w3_bundle_loader: Any = _load_w3_bundle,
    reuse_wave_addresses: bool = False,
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    config_output = config_root.resolve()
    if output.exists() or config_output.exists():
        raise ConvNativePackageError(
            "Conv config/transport outputs must both be fresh paths"
        )
    configs, config_manifest = build_strict_configs(
        root,
        source_config_rel=source_config_rel,
        reuse_wave_addresses=reuse_wave_addresses,
    )
    config_output.mkdir(parents=True)
    for wave_index, config in sorted(configs.items()):
        _write_json(config_output / f"wave-{wave_index}.json", config)
    _write_json(config_output / "manifest.json", config_manifest)

    spec, bundle, runtime_manifest, subop_manifest = w3_bundle_loader(root)
    if bundle.plan.storage_sample_count != 3:
        raise ConvNativePackageError("Conv28 bundle must carry three sample slots")
    expected = {
        "A": ACTIVATION_BYTES * 3,
        "B": WEIGHT_BYTES,
        "bias": BIAS_BYTES,
        "P": ACCUMULATOR_BYTES * 3,
    }
    observed = {
        name: bundle.plan.port(name).payload_bytes for name in expected
    }
    if observed != expected:
        raise ConvNativePackageError(
            f"Conv28 physical port sizes differ: {observed}"
        )

    output.mkdir(parents=True)
    graph_path = output / "graph.json"
    _write_json(graph_path, graph_spec())
    records: list[dict[str, Any]] = []
    for wave_index, (samples, slice_count) in enumerate(
        zip(WAVE_SAMPLES, WAVE_SLICE_COUNTS, strict=True)
    ):
        for slice_id in range(slice_count):
            region = bundle.region("A", slice_id)
            group_id = region.group_id
            if (
                group_id is None
                or group_id < 0
                or group_id >= len(samples)
            ):
                raise ConvNativePackageError(
                    f"slice {slice_id} has no wave-{wave_index} group"
                )
            relative_root = (
                Path(op_id(wave_index)) / f"slice{slice_id:02d}"
            )
            slice_root = output / relative_root
            slot_a = bundle.read("A", slice_id)[
                wave_index * ACTIVATION_BYTES:
                (wave_index + 1) * ACTIVATION_BYTES
            ]
            slot_p = bundle.read("P", slice_id)[
                wave_index * ACCUMULATOR_BYTES:
                (wave_index + 1) * ACCUMULATOR_BYTES
            ]
            payloads = {
                "A": bundle.read("B", slice_id),
                "B": slot_a,
                "C": bundle.read("bias", slice_id),
                "D": slot_p,
            }
            matrices: dict[str, Any] = {}
            for tensor, payload in payloads.items():
                path = (
                    slice_root
                    / f"matrix_{tensor}_linearized_128bit.txt"
                )
                item = _write_128bit_text(path, payload)
                item["path"] = path.relative_to(output).as_posix()
                matrices[tensor] = item
            records.append(
                {
                    "wave_index": wave_index,
                    "op_id": op_id(wave_index),
                    "operator_type": operator_type(wave_index),
                    "slice_id": slice_id,
                    "group_id": group_id,
                    "owner_step": region.owner_step,
                    "sample_id": samples[group_id],
                    "local_sample_slot": wave_index,
                    "matrices": matrices,
                }
            )
    matrix_count = sum(len(item["matrices"]) for item in records)
    if len(records) != 64 or matrix_count != 256:
        raise ConvNativePackageError(
            f"full Conv dispatch differs: records={len(records)}, "
            f"matrices={matrix_count}"
        )
    conv_stage, _ = _typed_stages(root)
    manifest: dict[str, Any] = {
        "schema": "resnet50-node0004-conv-native-transport-v1",
        "graph": {
            "path": "graph.json",
            "sha256": sha256_file(graph_path),
        },
        "config_set": {
            "path": config_output.relative_to(root).as_posix(),
            "manifest_sha256": sha256_file(config_output / "manifest.json"),
        },
        "typed_identity": {
            "typed_contract_sha256": sha256_file(root / TYPED_REL),
            "typed_stage_sha256": sha256_bytes(
                canonical_json_bytes(conv_stage)
            ),
        },
        "sources": {
            "runtime_manifest_sha256": sha256_file(
                root / "artifacts/w3/golden_batch16/manifest.json"
            ),
            "subop_manifest_sha256": sha256_file(
                root / "artifacts/w3/subop_batch16/manifest.json"
            ),
            "conv_instance_node_id": spec.node_id,
            "physical_layout_validation": "Conv28PhysicalBundle.validate passed",
        },
        "dispatch": {
            "wave_samples": [list(item) for item in WAVE_SAMPLES],
            "wave_active_slice_counts": list(WAVE_SLICE_COUNTS),
            "operator_count": 3,
            "operator_slice_record_count": len(records),
            "matrix_file_count": matrix_count,
            "covered_samples": sorted(
                {sample for wave in WAVE_SAMPLES for sample in wave}
            ),
        },
        "numeric_evidence": {
            "source": (
                "locked W3 ConvInt32Accumulate tensor; this transport step "
                "does not claim an NDP-Sim numeric execution"
            ),
            "server_numeric_pass_claim": False,
        },
        "records": records,
    }
    manifest["manifest_sha256"] = sha256_bytes(
        canonical_json_bytes(manifest)
    )
    _write_json(output / "manifest.json", manifest)
    return manifest


def _parameter(stage: Mapping[str, Any], name: str) -> dict[str, Any]:
    matches = [
        item
        for item in stage.get("parameters", [])
        if isinstance(item, Mapping) and item.get("name") == name
    ]
    if len(matches) != 1 or matches[0].get("resolution") != "derived":
        raise ConvNativePackageError(f"typed Conv parameter differs: {name}")
    return deepcopy(dict(matches[0]["value"]))


def _stable_request_proof_sha256(proof: Mapping[str, Any]) -> str:
    stable = deepcopy(dict(proof))
    stable.pop("graph_root", None)
    facts = stable.get("facts")
    if isinstance(facts, dict):
        facts.pop("graph", None)
    return sha256_bytes(canonical_json_bytes(stable))


def build_conv_semantic_contract(
    project_root: Path,
    *,
    graph_withbaseaddr: Path,
    execplan_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    graph_path = graph_withbaseaddr.resolve()
    exec_root = execplan_root.resolve()
    graph = _load(graph_path)
    conv_stage, requant_stage = _typed_stages(root)
    proof = _load(exec_root / "request_address_validation_report.json")
    transport = _load(root / TRANSPORT_REL / "manifest.json")
    operators = graph.get("operators")
    if not isinstance(operators, list) or len(operators) != 3:
        raise ConvNativePackageError("Conv graph must contain three waves")
    if (
        proof.get("valid") is not True
        or proof.get("facts", {}).get("graph_sha256")
        != sha256_file(graph_path)
        or proof.get("facts", {}).get("operator_count") != 3
        or proof.get("facts", {}).get("issue_count") != 0
        or transport.get("dispatch", {}).get("matrix_file_count") != 256
    ):
        raise ConvNativePackageError("Conv request/transport proof differs")

    typed_stage_sha = sha256_bytes(canonical_json_bytes(conv_stage))
    source = f"typed_config_parameter_contract:{HW_OP_ID}@{typed_stage_sha}"
    w_scale = _parameter(requant_stage, "w_scale")
    x_scale = _parameter(requant_stage, "x_scale")
    w_zero = _parameter(conv_stage, "w_zero_point")
    x_zero = _parameter(conv_stage, "x_zero_point")
    semantic_ops: dict[str, Any] = {}
    mapping_receipts: dict[str, str] = {}
    for wave_index, operator in enumerate(operators):
        current_id = op_id(wave_index)
        if (
            operator.get("id") != current_id
            or operator.get("type") != operator_type(wave_index)
            or set(operator.get("inputs", {})) != {"A", "B", "C"}
            or operator["inputs"]["A"].get("shape")
            != [1, 1, WEIGHT_BYTES]
            or operator["inputs"]["B"].get("shape")
            != [1, 1, ACTIVATION_BYTES]
            or operator["inputs"]["C"].get("shape")
            != [1, 1, BIAS_BYTES // 4]
            or operator.get("output", {}).get("shape")
            != [1, 1, ACCUMULATOR_BYTES // 4]
        ):
            raise ConvNativePackageError(
                f"Conv graph ABI differs: {current_id}"
            )
        mapping_root = exec_root / "mapping_evidence" / current_id
        mapping_manifest = _load(mapping_root / "bundle_manifest.json")
        if (
            mapping_manifest.get("summary", {}).get("valid") is not True
            or mapping_manifest.get("summary", {}).get("penalty") != 0.0
            or mapping_manifest.get("summary", {}).get("fallback_used")
            is not False
        ):
            raise ConvNativePackageError(
                f"Conv mapping differs: {current_id}"
            )
        mapping_receipts[current_id] = sha256_file(
            mapping_root / "bundle_manifest.json"
        )
        semantic_ops[current_id] = {
            "op_type": operator["type"],
            "layouts": {
                "A": (
                    "signed INT8 Conv28 weight tile; local K16 x C64; "
                    "K-major/C-minor"
                ),
                "B": (
                    "UINT8 Conv28 activation tile; one storage sample slot; "
                    "HWC64"
                ),
                "C": "INT32 local K16 bias vector",
                "D": "INT32 local K16 partial-sum tile; HWK16",
            },
            "qparams": {
                "policy": "explicit",
                "bindings": {
                    "A": {
                        "scale": deepcopy(w_scale),
                        "zero_point": deepcopy(w_zero),
                        "source": source,
                    },
                    "B": {
                        "scale": deepcopy(x_scale),
                        "zero_point": deepcopy(x_zero),
                        "source": source,
                    },
                },
            },
            "stage": {
                "role": (
                    "QLinearConv INT32 accumulate complete dispatch; "
                    "MSE0/SA-inport0 matched A ping-pong config"
                ),
                "wave_index": wave_index,
                "sample_ids": list(WAVE_SAMPLES[wave_index]),
                "dependencies": [],
            },
            "tail": {"policy": "exact", "padding": None},
            "provenance": {
                "source_config": {
                    "artifact": (
                        f"mapping_evidence/{current_id}/source_config.json"
                    ),
                    "sha256": sha256_file(
                        mapping_root / "source_config.json"
                    ),
                },
                "mapping_evidence": {
                    "artifact": (
                        f"mapping_evidence/{current_id}/mapping_evidence.json"
                    ),
                    "sha256": sha256_file(
                        mapping_root / "mapping_evidence.json"
                    ),
                },
            },
        }
    contract: dict[str, Any] = {
        "schema": "operator-config-semantic-contract-v1",
        "graph_sha256": sha256_file(graph_path),
        "target_profile": asdict(TargetProfile()),
        "candidate_scope": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "operator_count": 3,
            "wave_count": 3,
            "formal_target_config": False,
            "server_execution_claim": False,
            "purpose": (
                "complete node-0004 Conv accumulate native package; "
                "three-wave batch16 dispatch"
            ),
            "unresolved_semantic_gates": [
                "B_LAYOUT_APPROVAL",
                "B_CONV_INT8_SA",
                "B_CONV_BIAS_PSUM",
            ],
        },
        "source_identities": {
            "typed_config_parameter_contract_sha256": sha256_file(
                root / TYPED_REL
            ),
            "typed_stage_sha256": typed_stage_sha,
            "patchset_sha256": sha256_file(root / PATCHSET_REL),
            "transport_manifest_sha256": sha256_file(
                root / TRANSPORT_REL / "manifest.json"
            ),
            "request_proof_content_sha256": _stable_request_proof_sha256(
                proof
            ),
            "mapping_bundle_manifest_sha256": mapping_receipts,
        },
        "operators": semantic_ops,
    }
    contract["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(contract)
    )
    return contract


def _candidate_files(
    root: Path, *, exclude_manifest: bool = False
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == "candidate_manifest.json":
            continue
        if path.is_symlink():
            raise ConvNativePackageError(
                f"Conv candidate contains a symlink: {path}"
            )
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def _tree_sha256(files: Mapping[str, Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(files.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode(
                "utf-8"
            )
        )
    return digest.hexdigest()


def build_conv_server_candidate(
    project_root: Path, output_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise ConvNativePackageError(
            f"Conv candidate output must be fresh: {output}"
        )
    exec_root = root / EXECPLAN_REL
    transport_root = root / TRANSPORT_REL
    pipeline_graphs = list(
        (exec_root / "pipeline_output").glob("*_withbaseaddr.json")
    )
    if len(pipeline_graphs) != 1:
        raise ConvNativePackageError(
            "Conv execplan must contain one withbaseaddr graph"
        )
    semantic = build_conv_semantic_contract(
        root,
        graph_withbaseaddr=pipeline_graphs[0],
        execplan_root=exec_root,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(exec_root / "pipeline_output", output)
    copied_graph = output / pipeline_graphs[0].name
    copied_graph.rename(output / "graph_withbaseaddr.json")
    shutil.copytree(
        exec_root / "mapping_evidence", output / "mapping_evidence"
    )
    _write_json(output / "semantic_contract.json", semantic)
    evidence = output / "evidence"
    evidence.mkdir()
    for name in (
        "bundle_manifest.json",
        "double_run_comparison.json",
        "execplan_validation_report.json",
        "request_address_validation_report.json",
        "native_source_manifest.json",
        "patchset_manifest.json",
    ):
        shutil.copy2(exec_root / name, evidence / name)
    shutil.copy2(
        transport_root / "manifest.json",
        evidence / "transport_manifest.json",
    )
    transport = _load(transport_root / "manifest.json")
    matrix_count = 0
    for record in transport["records"]:
        destination = (
            output
            / "install"
            / str(record["op_id"])
            / f"slice{int(record['slice_id']):02d}"
        )
        destination.mkdir(parents=True, exist_ok=True)
        for tensor in ("A", "B", "C", "D"):
            source = transport_root / str(
                record["matrices"][tensor]["path"]
            )
            shutil.copy2(source, destination / source.name)
            matrix_count += 1
    if matrix_count != 256:
        raise ConvNativePackageError(
            "Conv candidate must contain 256 matrix files"
        )
    report = OperatorConfigPackageValidator().validate(
        output,
        graph_path=output / "graph_withbaseaddr.json",
        semantic_contract=semantic,
        require_matrix_files=True,
        provenance_root=output,
    ).to_dict()
    if not report["valid"]:
        raise ConvNativePackageError(
            "matrix-complete Conv package rejected: "
            f"{report.get('first_error')}"
        )
    _write_json(
        evidence / "matrix_complete_package_validation_report.json",
        report,
    )
    request = _load(
        exec_root / "request_address_validation_report.json"
    )
    request_count = request["facts"]["request_count_with_multiplicity"]
    files = _candidate_files(output)
    manifest: dict[str, Any] = {
        "schema": "resnet50-node0004-conv-server-candidate-v1",
        "status": (
            "local_full_three_wave_native_package_valid_"
            "server_and_semantic_gates_pending"
        ),
        "candidate_scope": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "operator_count": 3,
            "wave_count": 3,
            "covered_sample_count": 16,
            "formal_target_config": False,
            "server_execution_claim": False,
            "numeric_hardware_pass_claim": False,
            "successor_requant_execution_included": False,
        },
        "execution_payload": {
            "execplan_sha256": sha256_file(
                output / "install/execplan.txt"
            ),
            "graph_sha256": sha256_file(
                output / "graph_withbaseaddr.json"
            ),
            "matrix_file_count": matrix_count,
            "config_bitstream_count": len(
                list((output / "install/cfg_pkg").glob("*.bin"))
            ),
        },
        "local_validation": {
            "matrix_complete_package_valid": True,
            "request_address_valid": True,
            "request_count_with_multiplicity": request_count,
            "mapping_penalty": 0.0,
            "three_wave_dispatch_complete": True,
            "w3_physical_layout_valid": True,
        },
        "remaining_gates": {
            "semantic": [
                "B_LAYOUT_APPROVAL",
                "B_CONV_INT8_SA",
                "B_CONV_BIAS_PSUM",
            ],
            "hardware": ["E4 run1", "E5 run2"],
        },
        "payload_file_count": len(files),
        "payload_tree_sha256": _tree_sha256(files),
        "files": files,
    }
    _write_json(output / "candidate_manifest.json", manifest)
    return manifest


__all__ = [
    "CANDIDATE_REL",
    "CONFIG_ROOT_REL",
    "EXECPLAN_REL",
    "PATCHSET_REL",
    "SEMANTIC_REL",
    "TRANSPORT_REL",
    "ConvNativePackageError",
    "WAVE_SAMPLES",
    "WAVE_SLICE_COUNTS",
    "build_conv_semantic_contract",
    "build_conv_server_candidate",
    "build_strict_configs",
    "graph_spec",
    "op_id",
    "operator_type",
    "write_conv_native_inputs",
]
