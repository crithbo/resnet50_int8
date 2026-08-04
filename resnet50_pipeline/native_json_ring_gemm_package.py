"""Control package for the upstream hardware-tested DeepSeek ring GEMM JSON.

The source JSON and its six hardware trace logs were committed together in
``ndp-sim-ref@e299b280``.  The package does not rewrite that JSON.  It runs the
same encoded configuration twice in the order required by the immutable
slice0-start/slice1-finish observer, using zero inputs so the unbiased GEMM
golden is exactly zero independent of tensor relayout.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .conv_execplan_hardware import (
    RUNTIME_BARRIER_OPCODE,
    _build_axi4_4kb_trigger_report,
    _decode_template_state,
    _insert_runtime_completion_barriers,
    _load_execplan_api,
    _normalize_package_text_files,
    _output_hashes,
    _read_128bit_binary_lines,
    _read_json_object,
    _split_sca_d_transfers,
    _split_sca_preload_transfers,
    _validate_immutable_tb_sca_parser_abi,
    _validate_package_text_contract,
    _validate_payload_intervals,
    _validate_runtime_completion_barrier_contract,
    _write_json,
    _write_text_lf,
    _write_zero_128bit_binary_text,
)
from .errors import PipelineError


SOURCE_CONFIG = Path("ndp-sim-ref/jsons/prefill_gemm_ring_4slice.json")
SOURCE_CONFIG_SHA256 = "6a2ca9f2edd2e9c7b8ebbb558a84dd23c8e583781f8a8ac01c213b78c6737e91"
SOURCE_COMMIT = "e299b2804448242d1589b3e58ed7c5a9a5eca09f"
SOURCE_BLOB = "a5d9445c06e15e96e820acc908a5c5c751b7c374"
PACKAGED_SOURCE_CONFIG_NAME = SOURCE_CONFIG.name + ".original"
TRACE_RELATIVE_ROOT = Path(
    "ndp-sim-ref/address_remapping/golden/ring_gemm/M64NB32KA4KB16"
)
TRACE_NAMES = (
    "bank0_frame.log",
    "bank1_frame.log",
    "bank3_frame.log",
    "local_hub_req_bank0.log",
    "local_hub_req_bank1.log",
    "local_hub_req_bank3.log",
)
OP_IDS = ("op-deepseek-ring-s0", "op-deepseek-ring-s1")
READBACK_ID = "hwop-deepseek-ring-gemm"
CONFIG_BASES = (0x00010000, 0x00010400)
EXEC_BASE = 0x00010800
ZERO_REGION_BYTES = 0x8000
SLICE0_ZERO_BASE = 0x00000000
SLICE3_ZERO_BASE = 0x06000000
OUTPUT_BASE = 0x00004000
OUTPUT_BYTES = 64 * 32 * 2
OUTPUT_BEATS = OUTPUT_BYTES // 16


class NativeJsonRingGemmPackageError(PipelineError):
    """Raised when the hardware-tested native ring-GEMM package differs."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _normalize_lf(path: Path) -> None:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if not payload.endswith(b"\n"):
        payload += b"\n"
    path.write_bytes(payload)


def _bit_text_identity(path: Path, width: int) -> dict[str, Any]:
    lines = [line.strip() for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
    if not lines or any(len(line) != width or set(line) - {"0", "1"} for line in lines):
        raise NativeJsonRingGemmPackageError(f"invalid {width}-bit text: {path}")
    logical = ("\n".join(lines) + "\n").encode("ascii")
    return {
        "raw_size_bytes": path.stat().st_size,
        "raw_sha256": _sha256_file(path),
        "logical_size_bytes": len(logical),
        "logical_sha256": _sha256_bytes(logical),
        "line_count": len(lines),
        "line_width_bits": width,
    }


def _encoder_evidence(project_root: Path) -> dict[str, Any]:
    base = project_root / "artifacts/w5/deepseek_ring_gemm_control/v1"
    records: dict[str, Any] = {}
    for run_name in ("encoder_run_a", "encoder_run_b"):
        run = base / run_name
        bitstream = run / "modules_dump_128b.bin"
        parsed = run / "parsed_bitstream.txt"
        records[run_name] = {
            "bitstream_128b": _bit_text_identity(bitstream, 128),
            "parsed_bitstream": {
                "size_bytes": parsed.stat().st_size,
                "sha256": _sha256_file(parsed),
            },
            "mapping_review_sha256": _sha256_file(run / "mapping_review.json"),
        }
    if records["encoder_run_a"] != records["encoder_run_b"]:
        raise NativeJsonRingGemmPackageError("official ring-GEMM encoder A/B differs")
    return {
        "status": "two_independent_official_encoder_runs_identical",
        "seed": 42,
        "runs": records,
    }


def _trace_evidence(project_root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    shape = config.get("gemm_shape")
    pe = config.get("lc_pe_configs")
    if not isinstance(shape, Mapping) or not isinstance(pe, Mapping):
        raise NativeJsonRingGemmPackageError("ring-GEMM source shape is missing")
    derived = {
        "M": int(shape["M"]),
        "NB": int(shape["N"]),
        "KA": int(pe["PE0"]["inport1"]["constant"]) // 2,
        "KB": int(pe["PE1"]["inport1"]["constant"]) // 2,
        "N_full": int(shape["N"]) * 4,
    }
    if derived != {"M": 64, "NB": 32, "KA": 4, "KB": 16, "N_full": 128}:
        raise NativeJsonRingGemmPackageError(f"ring-GEMM trace dimensions differ: {derived}")
    root = project_root / TRACE_RELATIVE_ROOT
    records = []
    completion_cycles = set()
    for name in TRACE_NAMES:
        path = root / name
        payload = path.read_text(encoding="utf-8")
        starts = re.findall(r"INFO: slice start \(cycle=(\d+)\)", payload)
        finishes = re.findall(r"INFO: slice completed \(cycle=(\d+)\)", payload)
        if starts != ["0"] or finishes != ["819"]:
            raise NativeJsonRingGemmPackageError(f"hardware trace completion differs: {name}")
        completion_cycles.add(int(finishes[0]))
        records.append(
            {
                "path": path.relative_to(project_root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
                "start_cycle": 0,
                "completion_cycle": 819,
            }
        )
    bank3 = (root / "bank3_frame.log").read_text(encoding="utf-8").splitlines()
    started = False
    writes: list[tuple[int, str]] = []
    for line in bank3:
        if "INFO: slice start" in line:
            started = True
        if started and "| 1(W) |" in line:
            fields = [item.strip() for item in line.split("|")]
            if len(fields) >= 9:
                writes.append((int(fields[-1], 16), fields[-2]))
    counts = Counter(address for address, _ in writes)
    if (
        len(counts) != OUTPUT_BEATS
        or min(counts) != 0
        or max(counts) != OUTPUT_BEATS - 1
        or any("x" in data[2:].lower() for _, data in writes)
    ):
        raise NativeJsonRingGemmPackageError("hardware trace full writeback differs")
    return {
        "status": "target_hardware_completed_full_writeback",
        "evidence_boundary": (
            "proves start-to-completion and complete known-value writeback; "
            "does not claim a stored bit-exact numeric comparison"
        ),
        "source_commit": SOURCE_COMMIT,
        "case": {**derived, "slice_count": 4},
        "completion_cycle": completion_cycles.pop(),
        "writeback": {
            "dtype": "fp16",
            "expected_unique_128bit_words": OUTPUT_BEATS,
            "observed_unique_128bit_addresses": len(counts),
            "address_min": "0x00000000",
            "address_max": f"0x{OUTPUT_BEATS - 1:08X}",
            "unknown_data_word_count": 0,
        },
        "records": records,
    }


def _observer() -> dict[str, Any]:
    return {
        "mode": "fixed_slice0_start_slice1_finish",
        "start_slice_id": 0,
        "finish_slice_id": 1,
        "repeat_num": 1,
        "runtime_stage_count": 2,
        "final_pair_finishes_at_stage": 1,
        "all_prior_stages_barrier_ordered": True,
        "final_stage_slice_mask": "0x0000002",
        "final_stage_is_finish_slice_only": True,
        "all_other_final_shard_slices_barrier_completed_before_final_stage": True,
        "readback_after_final_finish_is_full_mask_completion_safe": True,
        "pairs": [{"pair_index": 0, "slice0_start_stage": 0, "slice1_finish_stage": 1}],
    }


def generate_native_json_ring_gemm_package(project_root: Path, output_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    destination = output_root.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise NativeJsonRingGemmPackageError(f"refusing to mix package evidence: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    source_path = root / SOURCE_CONFIG
    source_bytes = source_path.read_bytes()
    if _sha256_bytes(source_bytes) != SOURCE_CONFIG_SHA256:
        raise NativeJsonRingGemmPackageError("native ring-GEMM source JSON identity differs")
    config = json.loads(source_bytes.decode("utf-8"))
    encoder = _encoder_evidence(root)
    trace = _trace_evidence(root, config)
    source_copy = destination / "source_config" / PACKAGED_SOURCE_CONFIG_NAME
    source_copy.parent.mkdir(parents=True)
    shutil.copyfile(source_path, source_copy)
    trace_copy_root = destination / "hardware_trace"
    trace_copy_root.mkdir(parents=True)
    for name in TRACE_NAMES:
        shutil.copyfile(root / TRACE_RELATIVE_ROOT / name, trace_copy_root / name)

    api = _load_execplan_api(root)
    operators = []
    assignments: dict[str, Any] = {}
    io_map: dict[str, str] = {}
    for slice_id, op_id in zip((0, 1), OP_IDS, strict=True):
        partition = "non_observer_slices" if slice_id == 0 else "finish_slice_only"
        operators.append(
            api["OperatorSpec"](
                op_id=op_id,
                op_type="prefill_gemm_ring_4slice",
                used_slices=1 << slice_id,
                inputs={},
                output=api["TensorSpec"]((1, 64, 64), dtype="fp16"),
                instance_id="deepseek:prefill-gemm-ring:M64N128K16",
                stage="ring_gemm",
                attributes={
                    "slice_id": slice_id,
                    "source_config_sha256": SOURCE_CONFIG_SHA256,
                    "runtime_partition": partition,
                    "shard_index": 0,
                },
            )
        )
        tensor_name = f"ring.D.stage{slice_id}"
        assignments[tensor_name] = api["AddressAssignment"](
            tensor_name=tensor_name,
            base_address=OUTPUT_BASE,
            per_slice_addresses={slice_id: OUTPUT_BASE},
            size_bytes=OUTPUT_BYTES,
            shape=(1, 64, 64),
        )
        io_map[f"{op_id}.output.D"] = tensor_name

    execution_input = api["ExecutionPlanInput"](
        used_slices=0x3,
        operators=operators,
        schema_version="deepseek-native-json-ring-gemm-control-0.1",
        plan_id="deepseek-ring-gemm-hardware-control-v1",
    )
    bitstream_source = root / "artifacts/w5/deepseek_ring_gemm_control/v1/encoder_run_a/modules_dump_128b.bin"
    parsed_source = root / "artifacts/w5/deepseek_ring_gemm_control/v1/encoder_run_a/parsed_bitstream.txt"
    config_length = len(_read_128bit_binary_lines(bitstream_source)) * 2
    address_plan = api["AddressPlan"](
        assignments=assignments,
        operator_io_to_tensor=io_map,
        operator_config_base_addresses=dict(zip(OP_IDS, CONFIG_BASES, strict=True)),
        operator_config_lengths={op_id: config_length for op_id in OP_IDS},
    )
    original_values, enabled_addresses = _decode_template_state(api, root, parsed_source)
    templates = {
        op_id: api["OperatorTemplate"](
            op_type="prefill_gemm_ring_4slice",
            config_length=config_length,
            config_bitstream_path=str(bitstream_source),
            should_update_control_registers=False,
            original_register_values=original_values,
            enabled_register_addresses=enabled_addresses,
        )
        for op_id in OP_IDS
    }
    artifact = api["InstructionGenerator"]().generate(execution_input, address_plan, templates)
    artifact = _insert_runtime_completion_barriers(api, artifact, operators)
    if artifact.metadata.get("start_comp_count") != "2" or artifact.metadata.get("barrier_count") != "2":
        raise NativeJsonRingGemmPackageError(f"ring-GEMM execplan metadata differs: {artifact.metadata}")
    exec_path, explanation_path = api["write_instruction_outputs"](artifact, destination)

    installed_bitstream = destination / "install/cfg_pkg/prefill_gemm_ring_4slice_bitstream_128b.bin"
    installed_bitstream.parent.mkdir(parents=True)
    shutil.copyfile(bitstream_source, installed_bitstream)
    _normalize_lf(installed_bitstream)
    zero0 = destination / "install/control_input/slice00_zero_32KiB.txt"
    zero3 = destination / "install/control_input/slice03_zero_32KiB.txt"
    zero0_lines = _write_zero_128bit_binary_text(zero0, ZERO_REGION_BYTES)
    zero3_lines = _write_zero_128bit_binary_text(zero3, ZERO_REGION_BYTES)
    golden = destination / "golden/ring_D_zero.txt"
    golden_lines = _write_zero_128bit_binary_text(golden, OUTPUT_BYTES)
    semantic_output = f"install/{READBACK_ID}/slice00/matrix_D_linearized_128bit.txt"

    sca: dict[str, Any] = {
        "Exec_Base": f"0x{EXEC_BASE:08X}",
        "Exec_Length": len(_read_128bit_binary_lines(exec_path)),
        "Repeat_Num": 1,
        "ExecutionPlan": {"base_addr": f"0x{EXEC_BASE:08X}", "path": exec_path.relative_to(destination).as_posix()},
        f"{OP_IDS[0]}_config": {"base_addr": f"0x{CONFIG_BASES[0]:08X}", "path": installed_bitstream.relative_to(destination).as_posix()},
        f"{OP_IDS[1]}_config": {"base_addr": f"0x{CONFIG_BASES[1]:08X}", "path": installed_bitstream.relative_to(destination).as_posix()},
        "ring_zero_slice0": {"base_addr": f"0x{SLICE0_ZERO_BASE:08X}", "path": zero0.relative_to(destination).as_posix()},
        "ring_zero_slice3": {"base_addr": f"0x{SLICE3_ZERO_BASE:08X}", "path": zero3.relative_to(destination).as_posix()},
    }
    sca, preload_segments, bank_export_sca = _split_sca_preload_transfers(sca, destination)
    sca_path = destination / "sca_cfg.json"
    _write_json(sca_path, sca)
    sca = _read_json_object(sca_path)
    _validate_payload_intervals(sca, destination)
    parser_transfer_count = _validate_immutable_tb_sca_parser_abi(sca_path, sca)
    bank_export_path = destination / "sca_cfg.bank-export.json"
    _write_json(bank_export_path, bank_export_sca)
    try:
        bank_paths = api["export_bank_data"](
            bank_export_path, destination / "Bank_data", line_width_bits=32, output_format="binary"
        )
    finally:
        bank_export_path.unlink(missing_ok=True)

    semantic_sca_d = {
        "deepseek_ring_D": {
            "base_addr": f"0x{OUTPUT_BASE:08X}",
            "length": OUTPUT_BEATS,
            "path": semantic_output,
        }
    }
    sca_d = _split_sca_d_transfers(semantic_sca_d)
    _write_json(destination / "sca_cfg_D.json", sca_d)
    axi_report = _build_axi4_4kb_trigger_report(destination, preload_segments, semantic_sca_d, sca_d)
    _write_json(destination / "axi4_4kb_report.json", axi_report)

    observer = _observer()
    runtime_operators = []
    for slice_id, op_id in zip((0, 1), OP_IDS, strict=True):
        runtime_operators.append(
            {
                "operator_id": op_id,
                "operator_type": "prefill_gemm_ring_4slice",
                "stage": "ring_gemm",
                "instance_id": "deepseek:prefill-gemm-ring:M64N128K16",
                "slice_mask": f"0x{1 << slice_id:07X}",
                "attributes": {
                    "slice_id": slice_id,
                    "source_config_sha256": SOURCE_CONFIG_SHA256,
                    "runtime_partition": "non_observer_slices" if slice_id == 0 else "finish_slice_only",
                    "shard_index": 0,
                },
            }
        )
    golden_record = {
        "slice_id": 0,
        "base_addr": f"0x{OUTPUT_BASE:08X}",
        "semantic_path": semantic_output,
        "golden_path": golden.relative_to(destination).as_posix(),
        "line_count_128bit": golden_lines,
        "text_sha256": _sha256_file(golden),
        "expected_first_128bit": "0x" + "0" * 32,
    }
    _write_json(
        destination / "dump_contract.json",
        {
            "schema_version": "deepseek-native-json-ring-gemm-dump-0.1",
            "operator": "prefill_gemm_ring_4slice",
            "semantic_regions": [golden_record],
            "comparison": "full fp16 physical payload against the zero-input unbiased-GEMM invariant",
        },
    )
    runner_contract = {
        "schema_version": "deepseek-native-json-ring-gemm-runner-0.1",
        "preload": {
            "preferred_source": "sca_cfg.json",
            "rule": "load every immutable-parser transfer and require exact PASS accounting",
            "slice_count": 4,
            "sca_cfg": {
                "source": "sca_cfg.json",
                "data_format": "128-bit binary text",
                "line_regex": "^[01]{128}$",
                "word_byte_order": "little-endian",
                "immutable_tb_parser_abi": {
                    "name": "line-oriented-json-close-resets-entry-v1",
                    "validated_transfer_count": parser_transfer_count,
                },
            },
            "readback_gate": {"required": True, "probe_count": parser_transfer_count},
        },
        "execution": {
            "exec_base": f"0x{EXEC_BASE:08X}",
            "exec_length_128bit_beats": int(sca["Exec_Length"]),
            "execplan_path": "install/execplan.txt",
            "completion_gate": {
                "expected_runtime_stage_count": 2,
                "expected_testbench_repeat_num": 1,
                "testbench_observer_mode": observer["mode"],
                "expected_start_comp_count": 2,
                "expected_completion_barrier_count": 2,
                "completion_barrier_opcode": f"0b{RUNTIME_BARRIER_OPCODE:03b}",
                "expected_runtime_sequence": list(OP_IDS),
                "required_markers": ["INFO: slice start", "INFO: slice completed after", "Simulation completed successfully!"],
                "testbench_observer": observer,
            },
        },
        "post_run_dump": {
            "sca_cfg": "sca_cfg_D.json",
            "contract": "dump_contract.json",
            "semantic_region_count": 1,
            "transport_region_count": len(sca_d),
        },
        "required_return_metadata": [
            "server_run_id", "execution_environment", "board_version", "firmware_version", "isa_contract", "server_source_provenance"
        ],
        "comparison_command": "python tools/analyze_native_json_ring_gemm_return.py <zip>",
    }
    _write_json(destination / "runner_contract.json", runner_contract)

    freeze_manifest = {
        "schema_version": "deepseek-native-json-ring-gemm-freeze-0.1",
        "identity": {
            "operator": "prefill_gemm_ring_4slice",
            "source_config_path": SOURCE_CONFIG.as_posix(),
            "source_config_sha256": SOURCE_CONFIG_SHA256,
            "source_config_blob": SOURCE_BLOB,
            "source_commit": SOURCE_COMMIT,
        },
        "hardware_trace": trace,
        "encoder": encoder,
        "zero_input_invariant": {
            "bias_enable": False,
            "input_regions": [
                {"base_addr": f"0x{SLICE0_ZERO_BASE:08X}", "size_bytes": ZERO_REGION_BYTES, "line_count_128bit": zero0_lines},
                {"base_addr": f"0x{SLICE3_ZERO_BASE:08X}", "size_bytes": ZERO_REGION_BYTES, "line_count_128bit": zero3_lines},
            ],
            "expected_output_all_zero": True,
        },
    }
    _write_json(destination / "freeze_manifest.json", freeze_manifest)
    freeze_manifest_sha256 = _sha256_file(destination / "freeze_manifest.json")
    installed_identity = _bit_text_identity(installed_bitstream, 128)
    source_identity = _bit_text_identity(bitstream_source, 128)
    freeze_id = _sha256_bytes((freeze_manifest_sha256 + SOURCE_CONFIG_SHA256 + installed_identity["logical_sha256"]).encode("ascii"))
    bitstream_records = [
        {
            "binding_id": op_id,
            "role": "hardware_tested_deepseek_ring_gemm",
            "slice_id": slice_id,
            "config_sha256": SOURCE_CONFIG_SHA256,
            "source_config": {
                "path": source_copy.relative_to(destination).as_posix(),
                "size_bytes": source_copy.stat().st_size,
                "sha256": _sha256_file(source_copy),
            },
            "official_encoder": source_identity,
            "parsed_evidence": encoder["runs"]["encoder_run_a"]["parsed_bitstream"],
            "config_base_addr": f"0x{config_base:08X}",
            "install": {"path": installed_bitstream.relative_to(destination).as_posix(), **installed_identity},
        }
        for slice_id, op_id, config_base in zip((0, 1), OP_IDS, CONFIG_BASES, strict=True)
    ]
    text_paths = sorted([*_normalize_package_text_files(destination), "manifest.json"])
    manifest = {
        "schema_version": "deepseek-native-json-ring-gemm-hardware-package-0.1",
        "kind": "native_json_ring_gemm_hardware_execplan_package",
        "status": "hardware_execplan_package_validated",
        "node_id": "deepseek-ring-gemm-control",
        "hwop_id": "deepseek-prefill-gemm-ring-4slice",
        "freeze_id": freeze_id,
        "freeze_manifest_sha256": freeze_manifest_sha256,
        "source_config_path": SOURCE_CONFIG.as_posix(),
        "source_config_sha256": SOURCE_CONFIG_SHA256,
        "source_config_rewritten": False,
        "hardware_trace_validation": trace,
        "runtime_operator_count": 2,
        "runtime_sequence": list(OP_IDS),
        "runtime_operators": runtime_operators,
        "testbench_observer": observer,
        "runtime_serialization": {
            "strategy": "post_start_same_mask_barrier",
            "barrier_opcode": f"0b{RUNTIME_BARRIER_OPCODE:03b}",
            "barrier_count": 2,
            "placement": "immediately_after_each Start_Comp",
        },
        "config_lengths_64bit_words": {op_id: config_length for op_id in OP_IDS},
        "config_base_addresses": {op_id: f"0x{address:08X}" for op_id, address in zip(OP_IDS, CONFIG_BASES, strict=True)},
        "exec_base_address": f"0x{EXEC_BASE:08X}",
        "exec_128bit_line_count": int(sca["Exec_Length"]),
        "instruction_metadata": dict(artifact.metadata),
        "preloaded_input_count": 2,
        "preloaded_runtime_scratch_count": 1,
        "preloaded_golden_or_output_count": 0,
        "preload_transfer_segment_count": parser_transfer_count,
        "semantic_dump_region_count": 1,
        "sca_d_transfer_segment_count": len(sca_d),
        "bank_data_file_count": len(bank_paths),
        "bitstream_bindings": {
            "status": "hardware_trace_json_official_encoder_freeze_install_bound",
            "record_count": len(bitstream_records),
            "records": bitstream_records,
        },
        "numeric_validation": {
            "status": "zero_input_unbiased_gemm_invariant",
            "hardware_trace_numeric_boundary": trace["evidence_boundary"],
            "expected_output_all_zero": True,
        },
        "axi4_4kb": {
            "report_path": "axi4_4kb_report.json",
            "report_sha256": _sha256_file(destination / "axi4_4kb_report.json"),
            "status": axi_report["status"],
            "semantic_transfer_count": axi_report["semantic_transfer_count"],
            "triggered_transfer_count": axi_report["triggered_transfer_count"],
        },
        "entry_files": {
            "execplan": exec_path.relative_to(destination).as_posix(),
            "instructions_explained": explanation_path.relative_to(destination).as_posix(),
            "sca_cfg": "sca_cfg.json",
            "sca_cfg_D": "sca_cfg_D.json",
            "dump_contract": "dump_contract.json",
            "runner_contract": "runner_contract.json",
        },
        "text_file_contract": {
            "schema_version": "deepseek-package-text-abi-0.1",
            "encoding": "utf-8_or_ascii",
            "line_ending": "lf",
            "carriage_return_byte_allowed": False,
            "paths": text_paths,
        },
        "files": _output_hashes(destination),
    }
    _write_json(destination / "manifest.json", manifest)
    return validate_native_json_ring_gemm_package(destination)


def validate_native_json_ring_gemm_package(output_root: Path) -> dict[str, Any]:
    root = output_root.resolve()
    manifest = _read_json_object(root / "manifest.json")
    if (
        manifest.get("schema_version") != "deepseek-native-json-ring-gemm-hardware-package-0.1"
        or manifest.get("kind") != "native_json_ring_gemm_hardware_execplan_package"
        or manifest.get("status") != "hardware_execplan_package_validated"
        or manifest.get("source_config_sha256") != SOURCE_CONFIG_SHA256
        or manifest.get("source_config_rewritten") is not False
    ):
        raise NativeJsonRingGemmPackageError("native ring-GEMM package identity differs")
    source_copy = root / "source_config" / PACKAGED_SOURCE_CONFIG_NAME
    if _sha256_file(source_copy) != SOURCE_CONFIG_SHA256:
        raise NativeJsonRingGemmPackageError("packaged native ring-GEMM JSON differs")
    if _sha256_file(root / "freeze_manifest.json") != manifest.get("freeze_manifest_sha256"):
        raise NativeJsonRingGemmPackageError("native ring-GEMM freeze identity differs")
    if _output_hashes(root) != manifest.get("files"):
        raise NativeJsonRingGemmPackageError("native ring-GEMM package exact file set differs")
    text_count = _validate_package_text_contract(root, manifest["text_file_contract"])
    sca = _read_json_object(root / "sca_cfg.json")
    sca_d = _read_json_object(root / "sca_cfg_D.json")
    runner = _read_json_object(root / "runner_contract.json")
    if sca.get("Repeat_Num") != 1:
        raise NativeJsonRingGemmPackageError("native ring-GEMM Repeat_Num differs")
    transfer_count = _validate_immutable_tb_sca_parser_abi(root / "sca_cfg.json", sca)
    if transfer_count != manifest.get("preload_transfer_segment_count"):
        raise NativeJsonRingGemmPackageError("native ring-GEMM preload count differs")
    _validate_payload_intervals(sca, root)
    if len(sca_d) != manifest.get("sca_d_transfer_segment_count"):
        raise NativeJsonRingGemmPackageError("native ring-GEMM readback count differs")
    _validate_runtime_completion_barrier_contract(root, manifest, sca, runner)
    bindings = manifest.get("bitstream_bindings")
    if not isinstance(bindings, Mapping) or bindings.get("record_count") != 2:
        raise NativeJsonRingGemmPackageError("native ring-GEMM bitstream binding count differs")
    for record in bindings["records"]:
        if record.get("config_sha256") != SOURCE_CONFIG_SHA256:
            raise NativeJsonRingGemmPackageError("native ring-GEMM bitstream source differs")
        install = record.get("install")
        if not isinstance(install, Mapping):
            raise NativeJsonRingGemmPackageError("native ring-GEMM install binding differs")
        installed_path = root / str(install["path"])
        if _bit_text_identity(installed_path, 128) != {key: value for key, value in install.items() if key != "path"}:
            raise NativeJsonRingGemmPackageError("native ring-GEMM installed bitstream differs")
    golden = root / "golden/ring_D_zero.txt"
    if any(set(line) != {"0"} for line in _read_128bit_binary_lines(golden)):
        raise NativeJsonRingGemmPackageError("native ring-GEMM zero golden differs")
    trace = manifest.get("hardware_trace_validation")
    if not isinstance(trace, Mapping) or trace.get("status") != "target_hardware_completed_full_writeback":
        raise NativeJsonRingGemmPackageError("native ring-GEMM hardware trace evidence differs")
    return {
        "status": "hardware_execplan_package_validated",
        "kind": manifest["kind"],
        "source_config_sha256": SOURCE_CONFIG_SHA256,
        "source_config_rewritten": False,
        "hardware_trace_status": trace["status"],
        "hardware_completion_cycle": trace["completion_cycle"],
        "hardware_writeback_words": trace["writeback"]["observed_unique_128bit_addresses"],
        "runtime_operator_count": manifest["runtime_operator_count"],
        "exec_128bit_line_count": manifest["exec_128bit_line_count"],
        "preload_transfer_count": transfer_count,
        "readback_transfer_count": len(sca_d),
        "bank_data_file_count": manifest["bank_data_file_count"],
        "bitstream_binding_count": bindings["record_count"],
        "checked_file_count": len(manifest["files"]),
        "text_file_count": text_count,
    }
