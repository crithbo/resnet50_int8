from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5_complete_json_regeneration_v1"
    / "maxpool_uint8"
)
COMPLETE_DIR = OUT / "complete_json"
SOURCE = (
    ROOT
    / "ndp-sim"
    / "jsons"
    / "maxpool_config_16_112_112_stride2_padding1.json"
)
SOURCE_B = (
    ROOT
    / "ndp-sim"
    / "jsons"
    / "maxpool_config_16_16_16_stride2_padding1.json"
)
LOWERING = ROOT / "contracts" / "resnet50_r5_lowering_bundle.json"
CURRENT_ZIP = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5-server-test-packages"
    / "r5_n2_maxpool_ndpsim_native_v5.zip"
)
CURRENT_ROOT = "r5_n2_maxpool_ndpsim_native_v5"
CURRENT_CONFIG_MEMBER = (
    f"{CURRENT_ROOT}/workload/native/jsons/"
    "op0_maxpool_config_16_112_112_stride2_padding1.json"
)
CURRENT_GRAPH_MEMBER = (
    f"{CURRENT_ROOT}/workload/native/"
    "node0002_maxpool_wave0_graph_withbaseaddr.json"
)
CURRENT_MAPPING_MEMBER = (
    f"{CURRENT_ROOT}/workload/native/config/op0/mapping_review.json"
)
CURRENT_BITSTREAM_MEMBER = (
    f"{CURRENT_ROOT}/workload/native/config/op0/"
    "op0_maxpool_config_16_112_112_stride2_padding1_bitstream_128b.bin"
)
CURRENT_EXECPLAN_MEMBER = f"{CURRENT_ROOT}/workload/native/install/execplan.txt"
CURRENT_RETURN_REPORT = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5-maxpool-node0002-ndpsim-native-v5-return-analysis"
    / "report.json"
)
CURRENT_RETURN_TASK = (
    ROOT
    / ".agents"
    / "task_records"
    / "20260803_maxpool_node0002_ndpsim_native_v5_return_analysis.md"
)
CANDIDATE = COMPLETE_DIR / "node0002_hwop-0002-00_maxpool_uint8.json"
PADDING_CONTRACT = ROOT / "contracts/maxpool_node0002_zero_padding_contract.json"
PADDING_POINTER = "/stream_engine/stream0/padding_reg_value"

NDPSIM_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
SOURCE_BLOB = "4e8f7bb8906ab58f54f4c6507d2b94822f71bf04"
SOURCE_B_BLOB = "5281f4f49dfd8290ae339a68c6df111286040698"
RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _strict_candidate_bytes(value: Any) -> bytes:
    """Match the native materialized-consumer JSON text ABI (UTF-8 + CRLF)."""
    rendered = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    return rendered.replace("\n", "\r\n").encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _leaves(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, f"{pointer}/{_escape_pointer(str(key))}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _leaves(child, f"{pointer}/{index}")
        return
    yield pointer or "/", value


def _leaf_map(value: Any) -> dict[str, Any]:
    return dict(_leaves(value))


def _pointer_get(value: Any, pointer: str) -> Any:
    current = value
    for token in pointer.lstrip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def _pointer_set(value: Any, pointer: str, replacement: Any) -> None:
    tokens = pointer.lstrip("/").split("/")
    current = value
    for token in tokens[:-1]:
        token = token.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    last = tokens[-1].replace("~1", "/").replace("~0", "~")
    if isinstance(current, list):
        current[int(last)] = replacement
    else:
        current[last] = replacement


def _run_git(repo: Path, *args: str) -> str:
    command = [
        "git",
        "-c",
        f"safe.directory={repo.as_posix()}",
        "-C",
        str(repo),
        *args,
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _receipt(path: Path, repo: str, commit: str, blob: str | None = None) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
        "source_repo": repo,
        "source_commit": commit,
        "source_blob": blob,
    }


def _git_consumer_receipt(path: Path, repo_root: Path, repo_name: str) -> dict[str, Any]:
    relative = path.relative_to(repo_root).as_posix()
    commit = _run_git(repo_root, "rev-parse", "HEAD")
    stage_line = _run_git(repo_root, "ls-files", "--stage", "--", relative)
    base_blob = stage_line.split()[1] if stage_line else None
    working_blob = _run_git(repo_root, "hash-object", relative)
    dirty = bool(_run_git(repo_root, "status", "--short", "--", relative))
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
        "source_repo": repo_name,
        "base_commit": commit,
        "base_blob": base_blob,
        "working_tree_blob": working_blob,
        "working_tree_dirty": dirty,
    }


def _zip_read(archive: zipfile.ZipFile, member: str) -> bytes:
    names = archive.namelist()
    if names.count(member) != 1:
        raise RuntimeError(f"ZIP member must exist exactly once: {member}")
    return archive.read(member)


def _consumer_equation(pointer: str) -> str:
    top = pointer.split("/")[1] if pointer.startswith("/") else pointer
    equations = {
        "CONFIG": (
            "encoder packs the explicit module-enable mask; disabled instances remain "
            "inactive and cannot inherit values from an absent template field"
        ),
        "dram_loop_configs": (
            "LC emits ordered index=start+n*stride while n is inside end; enable/last/"
            "last_index and selected predecessor backpressure jointly qualify each output"
        ),
        "lc_pe_configs": (
            "LC_PE output is the configured opcode over selected LC/PE inputs; only an "
            "enabled, selected and accepted output may feed an MSE or downstream LC"
        ),
        "buffer_loop_configs": (
            "buffer ROW/COL LC indices form the physical row/column request; address and "
            "lifetime advance only on the corresponding accepted buffer request"
        ),
        "stream_engine": (
            "MSE request address = stream base_addr + accepted selected-index offset; "
            "read/write progress requires qualified queue, memory and buffer handshakes"
        ),
        "buffer_config": (
            "Buffer request is ready only when the addressed active-bank row satisfies "
            "valid/full state; mode/end_row/lifetime own row reuse and terminal ordering"
        ),
        "general_array": (
            "enabled PE captures only selected valid operands; opcode int8_max=11 is "
            "unsigned byte-lane max, while forward progress additionally requires the "
            "active RTL pipeline0 ready/clear and outbuffer accept equations"
        ),
    }
    return equations.get(
        top,
        "field is encoded exactly by the native mapper and consumed only by the "
        "explicitly enabled hardware block selected by the final mapping",
    )


def _source_presence(value: Any) -> str:
    if value is None:
        return "EXPLICIT_NULL_INACTIVE"
    if value == 0 or value is False:
        return "EXPLICIT_ZERO"
    return "SOURCE_VALUE_PRESENT"


def _exactness_axes(address: bool) -> dict[str, bool]:
    return {
        "op": True,
        "dtype": True,
        "shape": True,
        "layout": True,
        "qparams": True,
        "padding_tail": True,
        "dag": True,
        "lifetime": True,
        "address": address,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    COMPLETE_DIR.mkdir(parents=True, exist_ok=True)

    source_bytes = SOURCE.read_bytes()
    source = json.loads(source_bytes.decode("utf-8"))
    lowering = _load_json(LOWERING)
    request = next(
        item for item in lowering["requests"] if item["request_id"] == "r5:hwop-0002-00"
    )
    dag = next(item for item in lowering["node_stage_dags"] if item["node_id"] == "node-0002")
    resolution = next(
        item
        for item in lowering["effective_resolutions"]
        if item["request_id"] == "r5:hwop-0002-00"
    )

    with zipfile.ZipFile(CURRENT_ZIP) as archive:
        current_config_bytes = _zip_read(archive, CURRENT_CONFIG_MEMBER)
        current_config = json.loads(current_config_bytes.decode("utf-8"))
        graph_bytes = _zip_read(archive, CURRENT_GRAPH_MEMBER)
        graph = json.loads(graph_bytes.decode("utf-8"))
        mapping_bytes = _zip_read(archive, CURRENT_MAPPING_MEMBER)
        bitstream_bytes = _zip_read(archive, CURRENT_BITSTREAM_MEMBER)
        execplan_bytes = _zip_read(archive, CURRENT_EXECPLAN_MEMBER)

    operator = graph["operators"][0]
    candidate = deepcopy(source)
    address_derivations = {
        "/stream_engine/stream0/base_addr": hex(
            int(operator["inputs"]["A"]["base_addr"], 16)
        ),
        "/stream_engine/stream1/base_addr": hex(int(operator["output"]["base_addr"], 16)),
    }
    for pointer, target in address_derivations.items():
        _pointer_set(candidate, pointer, target)
    _pointer_set(candidate, PADDING_POINTER, 0)
    candidate_bytes = _strict_candidate_bytes(candidate)
    CANDIDATE.write_bytes(candidate_bytes)

    source_leaves = _leaf_map(source)
    candidate_leaves = _leaf_map(candidate)
    current_leaves = _leaf_map(current_config)
    if set(source_leaves) != set(candidate_leaves) or set(candidate_leaves) != set(current_leaves):
        raise RuntimeError("source/candidate/current leaf pointer set differs")
    source_candidate_diff = [
        pointer
        for pointer in sorted(candidate_leaves)
        if source_leaves[pointer] != candidate_leaves[pointer]
    ]
    expected_source_candidate_diff = sorted([*address_derivations, PADDING_POINTER])
    if source_candidate_diff != expected_source_candidate_diff:
        raise RuntimeError(f"unexpected source/candidate differences: {source_candidate_diff}")
    candidate_current_diff = [
        pointer
        for pointer in sorted(candidate_leaves)
        if candidate_leaves[pointer] != current_leaves[pointer]
    ]
    if candidate_current_diff != [PADDING_POINTER]:
        raise RuntimeError(f"unexpected candidate/current differences: {candidate_current_diff}")

    ndpsim = ROOT / "ndp-sim"
    actual_ndpsim_commit = _run_git(ndpsim, "rev-parse", "HEAD")
    actual_source_blob = _run_git(
        ndpsim,
        "rev-parse",
        "HEAD:jsons/maxpool_config_16_112_112_stride2_padding1.json",
    )
    if actual_ndpsim_commit != NDPSIM_COMMIT or actual_source_blob != SOURCE_BLOB:
        raise RuntimeError("upstream ndp-sim source identity drifted")

    rtl = ROOT / "Trassic2.0_RTL"
    actual_rtl_commit = _run_git(rtl, "rev-parse", "HEAD")
    if actual_rtl_commit != RTL_COMMIT:
        raise RuntimeError("current RTL identity drifted")

    encoder_files = [
        ROOT / "ndp-sim/bitstream/config/loop.py",
        ROOT / "ndp-sim/bitstream/config/stream.py",
        ROOT / "ndp-sim/bitstream/config/buffer.py",
        ROOT / "ndp-sim/bitstream/config/general.py",
        ROOT / "ndp-sim/bitstream/config/mapper.py",
        ROOT / "ndp-sim/model_execplan/src/execution_plan_generator/output_writer.py",
        ROOT / "ndp-sim/model_execplan/src/execution_plan_generator/control_registers.py",
        ROOT / "ndp-sim/model_execplan/src/execution_plan_generator/instruction_generator.py",
        ROOT / "ndp-sim/model_execplan/config/operator_base_info.json",
    ]
    rtl_files = [
        ROOT / "Trassic2.0_RTL/code/NDP_rtl/Slice/Index_Generation_Array/IGA_LC/IGA_LC_Config.sv",
        ROOT / "Trassic2.0_RTL/code/NDP_rtl/Slice/Index_Generation_Array/IGA_PE/IGA_PE_Config.sv",
        ROOT / "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/Stream_Engine/Stream_Engine_Config.sv",
        ROOT / "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster_Config.sv",
        ROOT / "Trassic2.0_RTL/code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Config.sv",
        ROOT / "Trassic2.0_RTL/code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv",
        ROOT / "Trassic2.0_RTL/code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv",
    ]
    encoder_receipts = [
        _git_consumer_receipt(path, ndpsim, "ndp-sim") for path in encoder_files
    ]
    rtl_receipts = [
        _git_consumer_receipt(path, rtl, "Trassic2.0_RTL") for path in rtl_files
    ]

    stage_record = {
        "node_id": dag["node_id"],
        "stage_id": dag["stage_ids"][0],
        "request_id": request["request_id"],
        "ordinal": request["ordinal"],
        "materialized_consumer_signature": {
            "op": request["identity"]["hw_op_type"],
            "onnx_op": request["identity"]["onnx_op_type"],
            "stage": request["identity"]["stage"],
            "dtype": {
                "inputs": request["logical_geometry"]["input_dtypes"],
                "outputs": request["logical_geometry"]["output_dtypes"],
            },
            "shape": {
                "inputs": request["logical_geometry"]["input_shapes"],
                "outputs": request["logical_geometry"]["output_shapes"],
            },
            "layout": {
                "logical": "NCHW",
                "native_per_slice": "HWC with C=16",
                "slices": 28,
                "input_native": [112, 112, 16],
                "output_native": [56, 56, 16],
            },
            "qparams": {
                "typed_parameters": request["typed_parameters"],
                "relationship": "same_qdomain_passthrough",
                "source_absence": "SOURCE_ABSENT_NOT_APPLICABLE",
            },
            "padding_tail": {
                "kernel": [3, 3],
                "strides": [2, 2],
                "pads": [1, 1, 1, 1],
                "auto_pad": "NOTSET",
                "ceil_mode": 0,
                "storage_order": 0,
                "spatial_padding_value": 0,
                "channel_tail": "none_for_native_C16_per_slice",
            },
            "dag": {
                "stage_ids": dag["stage_ids"],
                "internal_edges": dag["internal_edges"],
                "predecessor_hw_op_ids": request["predecessor_hw_op_ids"],
            },
            "lifetime": {
                "input_owner": "upstream tensor / graph storage planner",
                "output_owner": "node0002 output / graph storage planner",
                "config_owner": "per-operator config scheduler",
                "json_owner": "exact upstream template except planned base addresses",
            },
            "addresses": {
                "input_A": operator["inputs"]["A"]["base_addr"],
                "output_D": operator["output"]["base_addr"],
                "owner": "address planner; only stream0/stream1 base_addr leaves",
            },
        },
        "equivalence_class": "maxpool_uint8_nchw16x64x112x112_k3s2p1_native_c16",
        "current_resolution": resolution,
    }

    applicability = {
        "schema": "maxpool-complete-json-reference-applicability-v1",
        "family": "maxpool_uint8",
        "target_hw_op_types": ["MaxPoolUint8"],
        "target_stage_count": 1,
        "equivalence_class_count": 1,
        "target_stages": [stage_record],
        "template_classes": {
            "A_exact_replay": [
                {
                    **_receipt(SOURCE, "ndp-sim", NDPSIM_COMMIT, SOURCE_BLOB),
                    "grade": "A",
                    "applicability": (
                        "EXACT_FULL_OPERATOR_SOURCE_INSTANCE_WITH_ONE_HASH_BOUND_"
                        "STRICT_NORMALIZATION"
                    ),
                    "exactness_axes": _exactness_axes(address=False),
                    "address_exception": (
                        "upstream placeholder/local addresses are replaced only by "
                        "planner-owned graph addresses"
                    ),
                    "strict_normalization_exception": {
                        "json_pointer": PADDING_POINTER,
                        "before": None,
                        "after": 0,
                        "contract_path": PADDING_CONTRACT.relative_to(ROOT).as_posix(),
                        "contract_sha256": _sha256_file(PADDING_CONTRACT),
                    },
                }
            ],
            "B_same_primitive_shape_differs": [
                {
                    **_receipt(SOURCE_B, "ndp-sim", NDPSIM_COMMIT, SOURCE_B_BLOB),
                    "grade": "B",
                    "applicability": "REFERENCE_ONLY_NO_GENERALIZATION_AUTHORITY",
                    "difference": "native H/W 16x16 instead of 112x112",
                }
            ],
            "C_same_block_numeric_or_dtype_differs": [],
            "D_project_added_or_untracked": [],
        },
        "source_absence_semantics": {
            "qparams": "SOURCE_ABSENT_NOT_APPLICABLE",
            "second_or_auxiliary_input": "SOURCE_ABSENT_NOT_APPLICABLE",
            "specialized_array": "SOURCE_ABSENT_NOT_APPLICABLE",
            "unknown_target_shape_fields": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
            "null_leaf_policy": "EXPLICIT_NULL_INACTIVE",
            "zero_leaf_policy": "EXPLICIT_ZERO",
            "planned_base_address_policy": "TARGET_REQUIRED_DERIVED",
        },
        "authority_boundary": (
            "Only tracked ndp-sim JSON blobs are upstream authority. Project-added strict/"
            "guarded JSONs are evidence or historical candidates, never source authority."
        ),
    }
    for config_path in sorted(
        (ROOT / "configs/native_ndp_sim").glob(
            "maxpool_config_16_112_112_stride2_padding1*/config.json"
        )
    ):
        manifest_path = config_path.parent / "manifest.json"
        applicability["template_classes"]["D_project_added_or_untracked"].append(
            {
                **_receipt(config_path, "project-working-tree", "not-upstream-authority"),
                "manifest_path": manifest_path.relative_to(ROOT).as_posix(),
                "manifest_sha256": _sha256_file(manifest_path),
                "grade": "D",
                "applicability": "NOT_AUTHORITY",
            }
        )
    _write_json(OUT / "reference_applicability.json", applicability)

    handler_capability = {
        "schema": "maxpool-complete-json-handler-capability-v1",
        "family": "maxpool_uint8",
        "target_hw_op_types": ["MaxPoolUint8"],
        "operator_type": "maxpool_config_16_112_112_stride2_padding1",
        "registry_entry_present": False,
        "operator_specific_control_handler_present": False,
        "evidence": {
            "operator_base_info": encoder_receipts[-1],
            "control_registers": encoder_receipts[-3],
            "output_writer": encoder_receipts[-4],
        },
        "capabilities": {
            "exact_replay": {
                "status": "SUPPORTED_WITH_ONE_HASH_BOUND_STRICT_NORMALIZATION",
                "basis": (
                    "tracked JSON is loaded before planner base-address patch; enabled "
                    "UINT8 spatial padding additionally requires the authorized null->0 "
                    "strict materialization"
                ),
            },
            "shape": {
                "status": "UNSUPPORTED_FOR_DERIVATION",
                "basis": "no MaxPool registry entry or operator-specific shape handler",
                "absent_semantics": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
            },
            "dtype": {
                "status": "UNSUPPORTED_FOR_DERIVATION",
                "basis": "no dtype-aware MaxPool handler",
            },
            "qparam": {
                "status": "NOT_APPLICABLE",
                "basis": "same-qdomain MaxPool has no typed qparams",
                "absent_semantics": "SOURCE_ABSENT_NOT_APPLICABLE",
            },
            "layout": {
                "status": "EXACT_REPLAY_ONLY",
                "basis": "native C16 per-slice layout is embedded in the exact template",
            },
            "address": {
                "status": "SUPPORTED",
                "basis": "output_writer patches only selected stream base_addr leaves from address_plan",
            },
            "cross_stage_schedule": {
                "status": "NOT_APPLICABLE_SINGLE_STAGE",
                "basis": "node0002 stage DAG has one stage and no internal edge",
            },
        },
        "claim_boundary": (
            "Presence of JSON/mapper/registry infrastructure does not establish shape, "
            "dtype or layout generalization. Only this exact source instance is replayable."
        ),
    }
    _write_json(OUT / "handler_capability.json", handler_capability)

    ledger_entries: list[dict[str, Any]] = []
    for pointer in sorted(candidate_leaves):
        source_value = source_leaves[pointer]
        target_value = candidate_leaves[pointer]
        is_address = pointer in address_derivations
        is_padding_normalization = pointer == PADDING_POINTER
        ledger_entries.append(
            {
                "json_pointer": pointer,
                "target_value": target_value,
                "origin": (
                    "ADDRESS_PLANNER_DERIVED"
                    if is_address
                    else "RTL_DERIVED"
                    if is_padding_normalization
                    else "REFERENCE_EXACT"
                ),
                "source": {
                    "repo": "ndp-sim",
                    "commit": NDPSIM_COMMIT,
                    "blob": SOURCE_BLOB,
                    "path": SOURCE.relative_to(ROOT / "ndp-sim").as_posix(),
                    "json_pointer": pointer,
                    "value": source_value,
                },
                "applicability": (
                    "exact operator/dtype/shape/layout/padding/lifetime leaf; address "
                    "rebound by the target graph planner"
                    if is_address
                    else "exact source instance with hash-bound UINT8 zero-padding normalization"
                    if is_padding_normalization
                    else "exact operator/dtype/shape/layout/padding/lifetime leaf"
                ),
                "exactness_axes": {
                    **_exactness_axes(address=not is_address),
                    "padding_tail": not is_padding_normalization,
                },
                "derivation": (
                    {
                        "kind": "TARGET_REQUIRED_DERIVED",
                        "owner": "address planner",
                        "graph_member": CURRENT_GRAPH_MEMBER,
                        "graph_sha256": _sha256_bytes(graph_bytes),
                        "equation": (
                            "stream0.base_addr = graph.inputs.A.base_addr"
                            if pointer.endswith("stream0/base_addr")
                            else "stream1.base_addr = graph.output.base_addr"
                        ),
                    }
                    if is_address
                    else {
                        "kind": "TARGET_REQUIRED_DERIVED",
                        "owner": "UINT8 MaxPool zero-padding semantic contract",
                        "contract_path": PADDING_CONTRACT.relative_to(ROOT).as_posix(),
                        "contract_sha256": _sha256_file(PADDING_CONTRACT),
                        "equation": (
                            "enabled excluded spatial border byte = UINT8 max identity 0; "
                            "RTL padding mask selects mse_padding_reg_value"
                        ),
                    }
                    if is_padding_normalization
                    else {
                        "kind": _source_presence(source_value),
                        "equation": "target leaf = exact tracked source leaf",
                    }
                ),
                "current_consumer_equation": _consumer_equation(pointer),
                "status": "RESOLVED",
            }
        )
    ledger = {
        "schema": "maxpool-complete-json-field-provenance-ledger-v1",
        "family": "maxpool_uint8",
        "target_hw_op_types": ["MaxPoolUint8"],
        "node_id": "node-0002",
        "stage_id": "hwop-0002-00",
        "complete_json": CANDIDATE.relative_to(ROOT).as_posix(),
        "complete_json_sha256": _sha256_bytes(candidate_bytes),
        "leaf_count": len(ledger_entries),
        "origin_counts": {
            "REFERENCE_EXACT": sum(
                item["origin"] == "REFERENCE_EXACT" for item in ledger_entries
            ),
            "ADDRESS_PLANNER_DERIVED": sum(
                item["origin"] == "ADDRESS_PLANNER_DERIVED" for item in ledger_entries
            ),
            "RTL_DERIVED": sum(item["origin"] == "RTL_DERIVED" for item in ledger_entries),
            "UNRESOLVED": sum(item["origin"] == "UNRESOLVED" for item in ledger_entries),
        },
        "consumer_receipts": {
            "encoder": encoder_receipts,
            "rtl": rtl_receipts,
        },
        "entries": ledger_entries,
    }
    _write_json(OUT / "field_provenance_ledger.json", ledger)

    current_return = _load_json(CURRENT_RETURN_REPORT)
    diff = {
        "schema": "maxpool-complete-json-current-test-diff-v1",
        "family": "maxpool_uint8",
        "target_hw_op_types": ["MaxPoolUint8"],
        "current_test_identity": CURRENT_ROOT,
        "source_zip": {
            "path": CURRENT_ZIP.relative_to(ROOT).as_posix(),
            "bytes": CURRENT_ZIP.stat().st_size,
            "sha256": _sha256_file(CURRENT_ZIP),
        },
        "actual_consumed_artifacts": {
            "final_json": {
                "member": CURRENT_CONFIG_MEMBER,
                "bytes": len(current_config_bytes),
                "sha256": _sha256_bytes(current_config_bytes),
            },
            "graph_withbaseaddr": {
                "member": CURRENT_GRAPH_MEMBER,
                "bytes": len(graph_bytes),
                "sha256": _sha256_bytes(graph_bytes),
            },
            "mapping_review": {
                "member": CURRENT_MAPPING_MEMBER,
                "bytes": len(mapping_bytes),
                "sha256": _sha256_bytes(mapping_bytes),
            },
            "bitstream_128b": {
                "member": CURRENT_BITSTREAM_MEMBER,
                "bytes": len(bitstream_bytes),
                "sha256": _sha256_bytes(bitstream_bytes),
            },
            "execplan": {
                "member": CURRENT_EXECPLAN_MEMBER,
                "bytes": len(execplan_bytes),
                "sha256": _sha256_bytes(execplan_bytes),
                "line_count": len(
                    [line for line in execplan_bytes.decode("utf-8").splitlines() if line]
                ),
            },
        },
        "candidate_vs_upstream": {
            "same": len(candidate_leaves) - len(source_candidate_diff),
            "intentional_derivation": [
                {
                    "pointer": pointer,
                    "source_value": source_leaves[pointer],
                    "candidate_value": candidate_leaves[pointer],
                    "reason": (
                        "hash-bound UINT8 zero-padding strict normalization"
                        if pointer == PADDING_POINTER
                        else "planner-owned base address"
                    ),
                }
                for pointer in source_candidate_diff
            ],
            "suspected_current_defect": [],
            "new_candidate_defect": [],
            "dynamic_only": [],
        },
        "candidate_vs_current_consumed_final_json": {
            "same": len(candidate_leaves) - len(candidate_current_diff),
            "intentional_derivation": [
                {
                    "pointer": PADDING_POINTER,
                    "current_value": current_leaves[PADDING_POINTER],
                    "candidate_value": candidate_leaves[PADDING_POINTER],
                    "reason": "hash-bound UINT8 zero-padding strict normalization",
                }
            ],
            "suspected_current_defect": [
                {
                    "pointer": PADDING_POINTER,
                    "classification": "LEGACY_NULL_IN_ENABLED_PADDING_FIELD",
                    "strict_schema_effect": "current consumed JSON fails closed",
                    "encoded_bitstream_effect": (
                        "expected neutral; must be confirmed by native encoder replay"
                    ),
                    "dynamic_hang_explanation": False,
                }
            ],
            "new_candidate_defect": [],
            "dynamic_only": [
                {
                    "classification": current_return["root_cause_adjudication"][
                        "classification"
                    ],
                    "last_proven_good": current_return["last_proven_good"],
                    "first_divergence": current_return["first_divergence"],
                    "natural_terminal": current_return["execution"]["natural_terminal"],
                    "formal_d_present": current_return["formal_readback"]["present_count"],
                    "formal_d_expected": current_return["formal_readback"]["expected_count"],
                    "config_difference_can_explain": False,
                    "reason": (
                        "the only candidate/current difference is explicit padding zero "
                        "materialization; native encoder replay must prove it is bitstream "
                        "neutral before excluding it from the dynamic stop"
                    ),
                }
            ],
        },
        "known_non_config_blockers": {
            "B_GA_INT8_MAX_NUMERIC": {
                "current_status": "LOCAL_SOURCE_PASS",
                "configuration_explanation": False,
            },
            "B_GA_INT8_MAX_FLOW": {
                "current_status": "CDA-GA-INT8-MAX-PIPE-001=CONTRADICTED",
                "configuration_explanation": False,
                "equation": (
                    "alu_pipeline0_bp_post includes INT32 and FP32 branches but no INT8 "
                    "branch in current GA_PE_Inbuffer RTL"
                ),
            },
        },
        "claim_boundary": (
            "This comparison proves exact configuration replay and excludes a JSON "
            "difference as the cause of the current v5 stop. It does not establish "
            "dynamic hardware correctness, E3, E4 or E5."
        ),
    }
    _write_json(OUT / "current_test_diff.json", diff)

    report = {
        "schema": "maxpool-complete-json-regeneration-report-v1",
        "family": "maxpool_uint8",
        "target_hw_op_types": ["MaxPoolUint8"],
        "status": "STRICT_COMPLETE_JSON_MATERIALIZED_PENDING_UNIFIED_GATE",
        "analysis_owner_thread": "019fbe9f-3f2d-7071-806c-1ae72ae96391",
        "upstream_task": "019fd276-14c5-7800-94db-87ebfb9ce632",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "hard_boundary": {
            "server_package_generated_or_modified": False,
            "server_action": False,
            "functional_rtl_modified": False,
            "plan_or_public_rules_modified": False,
            "numeric_or_golden_repeated": False,
        },
        "coverage": {
            "target_stage_count": 1,
            "equivalence_class_count": 1,
            "json_leaf_count": len(candidate_leaves),
            "unresolved_count": ledger["origin_counts"]["UNRESOLVED"],
        },
        "complete_json": {
            "path": CANDIDATE.relative_to(ROOT).as_posix(),
            "bytes": len(candidate_bytes),
            "sha256": _sha256_bytes(candidate_bytes),
            "byte_equal_to_current_consumed_final_json": candidate_bytes
            == current_config_bytes,
            "semantic_equal_to_current_consumed_final_json": candidate
            == current_config,
        },
        "source_authority": {
            **_receipt(SOURCE, "ndp-sim", NDPSIM_COMMIT, SOURCE_BLOB),
            "classification": "A_EXACT_REPLAY",
            "source_file_modified": False,
        },
        "address_derivation_count": len(address_derivations),
        "reference_exact_count": ledger["origin_counts"]["REFERENCE_EXACT"],
        "rtl_derived_count": ledger["origin_counts"]["RTL_DERIVED"],
        "handler_capability": handler_capability["capabilities"],
        "current_test_adjudication": {
            "suspected_current_config_defect_count": 1,
            "new_candidate_defect_count": 0,
            "dynamic_only_count": 1,
            "config_difference_explains_current_stop": False,
            "latest_return_classification": current_return["root_cause_adjudication"][
                "classification"
            ],
        },
        "current_receipts": {
            "lowering_bundle": _receipt(
                LOWERING, "project-working-tree", _run_git(ROOT, "rev-parse", "HEAD")
            ),
            "current_return_report": _receipt(
                CURRENT_RETURN_REPORT, "project-working-tree", "current"
            ),
            "current_return_task": _receipt(
                CURRENT_RETURN_TASK, "project-working-tree", "current"
            ),
            "operator_rule": _receipt(
                ROOT / ".agents/rules/算子配置规则.md",
                "project-working-tree",
                "current",
            ),
            "ndp_field_rule": _receipt(
                ROOT / ".agents/rules/NDP硬件字段语义.md",
                "project-working-tree",
                "current",
            ),
        },
        "rule_delta_proposal": [
            {
                "proposal": "REFRESH_MAXPOOL_PADDING_RTL_EVIDENCE_CURRENT_IDENTITY",
                "reason": (
                    "the hash-bound padding contract still names the pre-sync "
                    "RD_Data_Channel SHA; current RTL changes queue depth 32->128 only "
                    "and preserves the padding replacement equation"
                ),
                "candidate_leaf_error": False,
                "public_rule_modified_here": False,
            }
        ],
        "rule_confirmation": [
            "CDA-NATIVE-REFERENCE-FIELD-APPLICABILITY-001",
            "CDA-NATIVE-HANDLER-CAPABILITY-MATRIX-001",
            "CDA-NATIVE-COMPOSITION-BOUNDARY-001",
        ],
        "claim_boundary": (
            "CONFIG_COMPLETE_LOCAL_ONLY. The strict JSON has no unresolved leaf. It "
            "differs from the current consumed JSON only by the authorized padding "
            "null->0 normalization; encoder replay must confirm bitstream neutrality. "
            "Current dynamic failure and GA INT8 pipeline flow remain outside this "
            "configuration-only claim."
        ),
        "errors": [],
    }
    _write_json(OUT / "report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
