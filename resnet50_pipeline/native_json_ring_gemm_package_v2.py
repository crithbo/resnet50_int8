"""Four-participant server package for the upstream DeepSeek Ring4 GEMM.

This revision consumes the four per-slice configurations emitted by upstream
``run_all_slices.py``.  It loads each configuration only on its matching slice,
then emits one native ``Start_Comp`` for the complete four-slice communication
domain followed by one same-mask server completion barrier.

The package intentionally uses zero-filled inputs.  That preserves a strict
all-zero output oracle for this unbiased GEMM while isolating configuration and
runtime-control behavior from the external model-weight archive that upstream
does not publish in Git.
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
    _write_text_lf,
    _write_json,
    _write_zero_128bit_binary_text,
)
from .errors import PipelineError


SOURCE_REPO = Path("upstream_recheck_20260722/ndp-sim")
SOURCE_CONFIG = SOURCE_REPO / "jsons/prefill_gemm_ring_4slice.json"
SOURCE_CONFIG_SHA256 = "6a2ca9f2edd2e9c7b8ebbb558a84dd23c8e583781f8a8ac01c213b78c6737e91"
SOURCE_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
SOURCE_BLOB = "a5d9445c06e15e96e820acc908a5c5c751b7c374"
TRACE_RELATIVE_ROOT = SOURCE_REPO / "address_remapping/golden/ring_gemm/M64NB32KA4KB16"
TRACE_NAMES = (
    "bank0_frame.log",
    "bank1_frame.log",
    "bank3_frame.log",
    "local_hub_req_bank0.log",
    "local_hub_req_bank1.log",
    "local_hub_req_bank3.log",
)
ENCODER_WORKTREE = Path("native_ring4_repro_20260722")
ENCODER_RUNS = {
    "run_a": ("generated_jsons", "slices_output"),
    "run_b": ("generated_jsons_b", "slices_output_b"),
}
SLICE_IDS = (0, 1, 2, 3)
SLICE_MASK = 0xF
CONFIG_OP_IDS = tuple(f"cfg-deepseek-ring-s{slice_id}" for slice_id in SLICE_IDS)
RUNTIME_OP_ID = "op-deepseek-ring4-s0-s3"
READBACK_ID = "hwop-deepseek-ring4-gemm"
CONFIG_BASES = (0x00010000, 0x00010400, 0x00010800, 0x00010C00)
EXEC_BASE = 0x00011000
ZERO_REGION_BYTES = 0x8000
OUTPUT_LOCAL_BASE = 0x00004000
OUTPUT_BYTES = 64 * 32 * 2
OUTPUT_BEATS = OUTPUT_BYTES // 16
OUTPUT_SENTINEL_BYTE = 0xA5
ZERO_INPUT_SEGMENTS = (
    ("before_D", 0, OUTPUT_LOCAL_BASE),
    (
        "after_D",
        OUTPUT_LOCAL_BASE + OUTPUT_BYTES,
        ZERO_REGION_BYTES - OUTPUT_LOCAL_BASE - OUTPUT_BYTES,
    ),
)
PACKAGE_SCHEMA = "deepseek-native-json-ring-gemm-hardware-package-0.2"
PACKAGE_KIND = "native_json_ring_gemm_hardware_execplan_package_v2"


class NativeJsonRingGemmPackageV2Error(PipelineError):
    """Raised when the native four-slice Ring4 package is inconsistent."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _physical_addr(slice_id: int, local_addr: int) -> int:
    return (slice_id << 25) | local_addr


def _write_fill_128bit_binary_text(
    destination: Path, size_bytes: int, byte_value: int
) -> int:
    if size_bytes <= 0 or size_bytes % 16 or not 0 <= byte_value <= 0xFF:
        raise NativeJsonRingGemmPackageV2Error("invalid 128-bit fill request")
    line_count = size_bytes // 16
    raw_word = bytes([byte_value]) * 16
    line = f"{int.from_bytes(raw_word, byteorder='little'):0128b}\n"
    _write_text_lf(destination, line * line_count, encoding="ascii")
    return line_count


def _bit_text_identity(path: Path, width: int) -> dict[str, Any]:
    lines = [line.strip() for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
    if not lines or any(len(line) != width or set(line) - {"0", "1"} for line in lines):
        raise NativeJsonRingGemmPackageV2Error(f"invalid {width}-bit text: {path}")
    logical = ("\n".join(lines) + "\n").encode("ascii")
    return {
        "raw_size_bytes": path.stat().st_size,
        "raw_sha256": _sha256_file(path),
        "logical_size_bytes": len(logical),
        "logical_sha256": _sha256_bytes(logical),
        "line_count": len(lines),
        "line_width_bits": width,
    }


def _encoder_paths(root: Path, run_name: str, slice_id: int) -> dict[str, Path]:
    generated_dir, output_dir = ENCODER_RUNS[run_name]
    stem = f"prefill_gemm_ring_4slice_slice{slice_id}"
    output = root / ENCODER_WORKTREE / output_dir / stem
    return {
        "config": root / ENCODER_WORKTREE / generated_dir / f"{stem}.json",
        "bitstream": output / "modules_dump_128b.bin",
        "parsed": output / "parsed_bitstream.txt",
        "mapping": output / "mapping_review.json",
        "terminal": output / "terminal.log",
    }


def _encoder_evidence(root: Path) -> dict[str, Any]:
    runs: dict[str, Any] = {}
    for run_name in ENCODER_RUNS:
        slices: dict[str, Any] = {}
        for slice_id in SLICE_IDS:
            paths = _encoder_paths(root, run_name, slice_id)
            missing = [name for name, path in paths.items() if not path.is_file()]
            if missing:
                raise NativeJsonRingGemmPackageV2Error(
                    f"upstream encoder evidence is missing for {run_name}/slice{slice_id}: {missing}"
                )
            terminal = paths["terminal"].read_text(encoding="utf-8")
            if "[✓] Mapping successful with zero violations" not in terminal:
                raise NativeJsonRingGemmPackageV2Error(
                    f"upstream encoder did not prove zero violations: {paths['terminal']}"
                )
            slices[f"slice{slice_id}"] = {
                "generated_config_sha256": _sha256_file(paths["config"]),
                "bitstream_128b": _bit_text_identity(paths["bitstream"], 128),
                "parsed_bitstream_sha256": _sha256_file(paths["parsed"]),
                "mapping_review_sha256": _sha256_file(paths["mapping"]),
                "zero_violation_marker": True,
            }
        runs[run_name] = slices
    if runs["run_a"] != runs["run_b"]:
        raise NativeJsonRingGemmPackageV2Error("upstream Ring4 encoder A/B evidence differs")
    return {
        "status": "two_upstream_run_all_slices_outputs_identical",
        "source_script": f"{ENCODER_WORKTREE.as_posix()}/run_all_slices.py",
        "slice_count": len(SLICE_IDS),
        "runs": runs,
    }


def _trace_evidence(root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    shape = config.get("gemm_shape")
    pe = config.get("lc_pe_configs")
    if not isinstance(shape, Mapping) or not isinstance(pe, Mapping):
        raise NativeJsonRingGemmPackageV2Error("ring-GEMM source shape is missing")
    derived = {
        "M": int(shape["M"]),
        "NB": int(shape["N"]),
        "KA": int(pe["PE0"]["inport1"]["constant"]) // 2,
        "KB": int(pe["PE1"]["inport1"]["constant"]) // 2,
        "N_full": int(shape["N"]) * 4,
    }
    if derived != {"M": 64, "NB": 32, "KA": 4, "KB": 16, "N_full": 128}:
        raise NativeJsonRingGemmPackageV2Error(f"ring-GEMM trace dimensions differ: {derived}")
    trace_root = root / TRACE_RELATIVE_ROOT
    records = []
    completion_cycles = set()
    for name in TRACE_NAMES:
        path = trace_root / name
        payload = path.read_text(encoding="utf-8")
        starts = re.findall(r"INFO: slice start \(cycle=(\d+)\)", payload)
        finishes = re.findall(r"INFO: slice completed \(cycle=(\d+)\)", payload)
        if starts != ["0"] or finishes != ["819"]:
            raise NativeJsonRingGemmPackageV2Error(f"hardware trace completion differs: {name}")
        completion_cycles.add(int(finishes[0]))
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
                "start_cycle": 0,
                "completion_cycle": 819,
            }
        )
    writes: list[tuple[int, str]] = []
    started = False
    for line in (trace_root / "bank3_frame.log").read_text(encoding="utf-8").splitlines():
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
        raise NativeJsonRingGemmPackageV2Error("hardware trace full writeback differs")
    return {
        "status": "target_hardware_completed_full_writeback",
        "evidence_boundary": (
            "proves the upstream four-slice configuration completed and wrote every output word; "
            "the committed trace does not preserve input tensors for a bit-exact replay"
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
        "runtime_stage_count": 1,
        "final_pair_finishes_at_stage": 0,
        "all_prior_stages_barrier_ordered": True,
        "final_stage_slice_mask": "0x000000F",
        "final_stage_is_finish_slice_only": False,
        "final_stage_is_full_mask_ring_group": True,
        "final_stage_completion_barrier_mask": "0x000000F",
        "readback_after_final_finish_is_full_mask_completion_safe": True,
        "pairs": [{"pair_index": 0, "slice0_start_stage": 0, "slice1_finish_stage": 0}],
    }


def _copy_encoder_evidence(root: Path, destination: Path) -> None:
    for run_name in ENCODER_RUNS:
        for slice_id in SLICE_IDS:
            paths = _encoder_paths(root, run_name, slice_id)
            target = destination / "encoder_evidence" / run_name / f"slice{slice_id:02d}"
            target.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(paths["bitstream"], target / "modules_dump_128b.bin")
            shutil.copyfile(paths["parsed"], target / "parsed_bitstream.txt")
            shutil.copyfile(paths["mapping"], target / "mapping_review.json")
            if run_name == "run_a":
                source_target = destination / "source_config" / f"prefill_gemm_ring_4slice_slice{slice_id}.json"
                source_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(paths["config"], source_target)


def _build_native_execplan(root: Path, config_sources: list[Path], parsed_sources: list[Path]) -> tuple[Any, Any, list[Any]]:
    api = _load_execplan_api(root)
    config_operators = [
        api["OperatorSpec"](
            op_id=op_id,
            op_type="prefill_gemm_ring_4slice",
            used_slices=1 << slice_id,
            inputs={},
            output=api["TensorSpec"]((1, 64, 32), dtype="fp16"),
            instance_id="deepseek:prefill-gemm-ring:M64N128K16",
            stage="ring4_config",
            attributes={"slice_id": slice_id, "runtime_partition": "configuration_only"},
        )
        for slice_id, op_id in zip(SLICE_IDS, CONFIG_OP_IDS, strict=True)
    ]
    config_lengths = [len(_read_128bit_binary_lines(path)) * 2 for path in config_sources]
    if set(config_lengths) != {60}:
        raise NativeJsonRingGemmPackageV2Error(f"upstream Ring4 config lengths differ: {config_lengths}")
    address_plan = api["AddressPlan"](
        operator_config_base_addresses=dict(zip(CONFIG_OP_IDS, CONFIG_BASES, strict=True)),
        operator_config_lengths=dict(zip(CONFIG_OP_IDS, config_lengths, strict=True)),
    )
    templates = {
        op_id: api["OperatorTemplate"](
            op_type="prefill_gemm_ring_4slice",
            config_length=config_length,
            config_bitstream_path=str(bitstream),
            should_update_control_registers=False,
        )
        for op_id, config_length, bitstream, _parsed in zip(
            CONFIG_OP_IDS, config_lengths, config_sources, parsed_sources, strict=True
        )
    }
    config_input = api["ExecutionPlanInput"](
        used_slices=SLICE_MASK,
        operators=config_operators,
        schema_version="deepseek-native-ring4-config-load-0.2",
        plan_id="deepseek-ring4-config-load-v2",
    )
    generated = api["InstructionGenerator"]().generate(config_input, address_plan, templates)
    opcodes = [int(command) & 0x7 for command in generated.commands]
    if Counter(opcodes) != Counter({0b001: 1, 0b000: 4, 0b101: 4}):
        raise NativeJsonRingGemmPackageV2Error(f"native config-load command set differs: {Counter(opcodes)}")

    runtime_operator = api["OperatorSpec"](
        op_id=RUNTIME_OP_ID,
        op_type="prefill_gemm_ring_4slice",
        used_slices=SLICE_MASK,
        inputs={},
        output=api["TensorSpec"]((1, 64, 32), dtype="fp16"),
        instance_id="deepseek:prefill-gemm-ring:M64N128K16",
        stage="ring4_compute",
        attributes={
            "selected_slices": list(SLICE_IDS),
            "runtime_partition": "full_ring_group",
            "source_config_sha256": SOURCE_CONFIG_SHA256,
        },
    )
    runtime_input = api["ExecutionPlanInput"](
        used_slices=SLICE_MASK,
        operators=[runtime_operator],
        schema_version="deepseek-native-ring4-runtime-0.2",
        plan_id="deepseek-ring4-runtime-v2",
    )
    runtime_generated = api["InstructionGenerator"]().generate(
        runtime_input,
        api["AddressPlan"](),
        {RUNTIME_OP_ID: api["OperatorTemplate"](op_type="prefill_gemm_ring_4slice", config_length=0)},
    )
    runtime_starts = [
        (command, explanation)
        for command, explanation in zip(
            runtime_generated.commands, runtime_generated.command_explanations, strict=True
        )
        if (int(command) & 0x7) == 0b101
    ]
    if len(runtime_starts) != 1 or ((int(runtime_starts[0][0]) >> 3) & ((1 << 28) - 1)) != SLICE_MASK:
        raise NativeJsonRingGemmPackageV2Error("native full-mask Start_Comp generation differs")

    commands: list[int] = []
    explanations: list[str] = []
    for command, explanation in zip(generated.commands, generated.command_explanations, strict=True):
        if (int(command) & 0x7) == 0b101:
            continue
        commands.append(int(command))
        explanations.append(str(explanation))
    commands.append(int(runtime_starts[0][0]))
    explanations.append(str(runtime_starts[0][1]))
    metadata = dict(generated.metadata)
    metadata.update(
        {
            "load_config_count": "4",
            "start_comp_count": "1",
            "configuration_only_operator_count": "4",
            "runtime_operator_count": "1",
            "runtime_slice_mask": f"0x{SLICE_MASK:07X}",
            "note": (
                "Four upstream per-slice configurations are loaded independently; "
                "one native full-Ring4 Start_Comp follows all loads."
            ),
        }
    )
    artifact = api["ExecutionPlanArtifact"](
        commands=commands,
        command_explanations=explanations,
        metadata=metadata,
    )
    artifact = _insert_runtime_completion_barriers(api, artifact, [runtime_operator])
    final_opcodes = Counter(int(command) & 0x7 for command in artifact.commands)
    if final_opcodes != Counter({0b001: 1, 0b000: 4, 0b101: 1, RUNTIME_BARRIER_OPCODE: 1}):
        raise NativeJsonRingGemmPackageV2Error(f"final Ring4 execplan command set differs: {final_opcodes}")
    return api, artifact, [runtime_operator]


def generate_native_json_ring_gemm_package_v2(project_root: Path, output_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    destination = output_root.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise NativeJsonRingGemmPackageV2Error(f"refusing to mix package evidence: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    source_path = root / SOURCE_CONFIG
    source_bytes = source_path.read_bytes()
    if _sha256_bytes(source_bytes) != SOURCE_CONFIG_SHA256:
        raise NativeJsonRingGemmPackageV2Error("fresh upstream Ring4 JSON identity differs")
    config = json.loads(source_bytes.decode("utf-8"))
    n2n = config.get("n2n", {}).get("neighbor_stream0", {})
    if n2n != {"mem_loop": 4, "src_slice_sel": 1, "dst_slice_sel": 1, "ping_pong": 1}:
        raise NativeJsonRingGemmPackageV2Error(f"fresh upstream Ring4 communication domain differs: {n2n}")
    output_base_bits = (
        config.get("stream_engine", {}).get("stream2", {}).get("base_addr")
    )
    try:
        output_base = int(str(output_base_bits).replace("_", ""), 2)
    except ValueError as error:
        raise NativeJsonRingGemmPackageV2Error(
            "fresh upstream Ring4 output address is malformed"
        ) from error
    if output_base != OUTPUT_LOCAL_BASE:
        raise NativeJsonRingGemmPackageV2Error(
            f"fresh upstream Ring4 output base differs: 0x{output_base:08X}"
        )
    encoder = _encoder_evidence(root)
    trace = _trace_evidence(root, config)

    source_copy = destination / "source_config" / "prefill_gemm_ring_4slice.json.original"
    source_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, source_copy)
    trace_copy_root = destination / "hardware_trace"
    trace_copy_root.mkdir(parents=True, exist_ok=True)
    for name in TRACE_NAMES:
        shutil.copyfile(root / TRACE_RELATIVE_ROOT / name, trace_copy_root / name)
    _copy_encoder_evidence(root, destination)

    config_sources = [
        destination / "encoder_evidence" / "run_a" / f"slice{slice_id:02d}" / "modules_dump_128b.bin"
        for slice_id in SLICE_IDS
    ]
    parsed_sources = [
        destination / "encoder_evidence" / "run_a" / f"slice{slice_id:02d}" / "parsed_bitstream.txt"
        for slice_id in SLICE_IDS
    ]
    api, artifact, runtime_operators = _build_native_execplan(root, config_sources, parsed_sources)
    exec_path, explanation_path = api["write_instruction_outputs"](artifact, destination)

    installed_configs: list[Path] = []
    for slice_id, source in zip(SLICE_IDS, config_sources, strict=True):
        installed = destination / "install/cfg_pkg" / f"prefill_gemm_ring_4slice_slice{slice_id}_bitstream_128b.bin"
        installed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, installed)
        installed_configs.append(installed)

    zero_inputs: dict[tuple[int, str], Path] = {}
    zero_line_counts: dict[tuple[int, str], int] = {}
    output_sentinels: list[Path] = []
    sentinel_line_counts: list[int] = []
    for slice_id in SLICE_IDS:
        for segment_name, _local_base, size_bytes in ZERO_INPUT_SEGMENTS:
            path = (
                destination
                / "install/control_input"
                / f"slice{slice_id:02d}_zero_{segment_name}_{size_bytes // 1024}KiB.txt"
            )
            zero_inputs[(slice_id, segment_name)] = path
            zero_line_counts[(slice_id, segment_name)] = (
                _write_zero_128bit_binary_text(path, size_bytes)
            )
        sentinel = (
            destination
            / "install/control_input"
            / f"slice{slice_id:02d}_D_sentinel_4KiB.txt"
        )
        output_sentinels.append(sentinel)
        sentinel_line_counts.append(
            _write_fill_128bit_binary_text(
                sentinel, OUTPUT_BYTES, OUTPUT_SENTINEL_BYTE
            )
        )
    golden = destination / "golden/ring_D_zero.txt"
    golden_lines = _write_zero_128bit_binary_text(golden, OUTPUT_BYTES)

    sca: dict[str, Any] = {
        "Exec_Base": f"0x{EXEC_BASE:08X}",
        "Exec_Length": len(_read_128bit_binary_lines(exec_path)),
        "Repeat_Num": 1,
        "ExecutionPlan": {
            "base_addr": f"0x{EXEC_BASE:08X}",
            "path": exec_path.relative_to(destination).as_posix(),
        },
    }
    for slice_id, op_id, config_base, installed in zip(
        SLICE_IDS, CONFIG_OP_IDS, CONFIG_BASES, installed_configs, strict=True
    ):
        sca[f"{op_id}_config"] = {
            "base_addr": f"0x{config_base:08X}",
            "path": installed.relative_to(destination).as_posix(),
        }
        before = zero_inputs[(slice_id, "before_D")]
        after = zero_inputs[(slice_id, "after_D")]
        sca[f"ring_zero_before_D_slice{slice_id}"] = {
            "base_addr": f"0x{_physical_addr(slice_id, 0):08X}",
            "path": before.relative_to(destination).as_posix(),
        }
        sca[f"ring_D_sentinel_slice{slice_id}"] = {
            "base_addr": f"0x{_physical_addr(slice_id, OUTPUT_LOCAL_BASE):08X}",
            "path": output_sentinels[slice_id].relative_to(destination).as_posix(),
        }
        sca[f"ring_zero_after_D_slice{slice_id}"] = {
            "base_addr": (
                f"0x{_physical_addr(slice_id, OUTPUT_LOCAL_BASE + OUTPUT_BYTES):08X}"
            ),
            "path": after.relative_to(destination).as_posix(),
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
            bank_export_path,
            destination / "Bank_data",
            line_width_bits=32,
            output_format="binary",
        )
    finally:
        bank_export_path.unlink(missing_ok=True)

    semantic_sca_d = {
        f"deepseek_ring_D_slice{slice_id}": {
            "base_addr": f"0x{_physical_addr(slice_id, OUTPUT_LOCAL_BASE):08X}",
            "length": OUTPUT_BEATS,
            "path": f"install/{READBACK_ID}/slice{slice_id:02d}/matrix_D_linearized_128bit.txt",
        }
        for slice_id in SLICE_IDS
    }
    sca_d = _split_sca_d_transfers(semantic_sca_d)
    _write_json(destination / "sca_cfg_D.json", sca_d)
    axi_report = _build_axi4_4kb_trigger_report(destination, preload_segments, semantic_sca_d, sca_d)
    _write_json(destination / "axi4_4kb_report.json", axi_report)

    observer = _observer()
    golden_records = [
        {
            "slice_id": slice_id,
            "base_addr": f"0x{_physical_addr(slice_id, OUTPUT_LOCAL_BASE):08X}",
            "semantic_path": semantic_sca_d[f"deepseek_ring_D_slice{slice_id}"]["path"],
            "golden_path": golden.relative_to(destination).as_posix(),
            "line_count_128bit": golden_lines,
            "text_sha256": _sha256_file(golden),
            "expected_first_128bit": "0x" + "0" * 32,
        }
        for slice_id in SLICE_IDS
    ]
    _write_json(
        destination / "dump_contract.json",
        {
            "schema_version": "deepseek-native-json-ring-gemm-dump-0.2",
            "operator": "prefill_gemm_ring_4slice",
            "semantic_regions": golden_records,
            "comparison": "all four fp16 outputs against the zero-input unbiased-GEMM invariant",
            "pre_execution_output_sentinel_byte": f"0x{OUTPUT_SENTINEL_BYTE:02X}",
        },
    )
    runner_contract = {
        "schema_version": "deepseek-native-json-ring-gemm-runner-0.2",
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
                "expected_runtime_stage_count": 1,
                "expected_testbench_repeat_num": 1,
                "testbench_observer_mode": observer["mode"],
                "expected_start_comp_count": 1,
                "expected_completion_barrier_count": 1,
                "completion_barrier_opcode": f"0b{RUNTIME_BARRIER_OPCODE:03b}",
                "expected_runtime_sequence": [RUNTIME_OP_ID],
                "required_markers": [
                    "INFO: slice start",
                    "INFO: slice completed after",
                    "Simulation completed successfully!",
                ],
                "testbench_observer": observer,
            },
        },
        "post_run_dump": {
            "sca_cfg": "sca_cfg_D.json",
            "contract": "dump_contract.json",
            "semantic_region_count": len(golden_records),
            "transport_region_count": len(sca_d),
        },
        "required_return_metadata": [
            "server_run_id",
            "execution_environment",
            "board_version",
            "firmware_version",
            "isa_contract",
            "server_source_provenance",
        ],
        "comparison_command": (
            "python tools/analyze_native_json_ring_gemm_return.py <zip> "
            "--package artifacts/w5/deepseek_ring_gemm_control/v2/hardware_execplan_package"
        ),
    }
    _write_json(destination / "runner_contract.json", runner_contract)

    freeze_manifest = {
        "schema_version": "deepseek-native-json-ring-gemm-freeze-0.2",
        "identity": {
            "operator": "prefill_gemm_ring_4slice",
            "source_config_path": SOURCE_CONFIG.as_posix(),
            "source_config_sha256": SOURCE_CONFIG_SHA256,
            "source_config_blob": SOURCE_BLOB,
            "source_commit": SOURCE_COMMIT,
        },
        "hardware_trace": trace,
        "encoder": encoder,
        "runtime_topology": {
            "logical_ring_order": list(SLICE_IDS),
            "clock_mask": f"0x{SLICE_MASK:07X}",
            "start_mask": f"0x{SLICE_MASK:07X}",
            "completion_barrier_mask": f"0x{SLICE_MASK:07X}",
            "per_slice_config_count": 4,
        },
        "zero_input_invariant": {
            "bias_enable": False,
            "input_regions": [
                {
                    "slice_id": slice_id,
                    "segment": segment_name,
                    "base_addr": f"0x{_physical_addr(slice_id, local_base):08X}",
                    "size_bytes": size_bytes,
                    "line_count_128bit": zero_line_counts[(slice_id, segment_name)],
                }
                for slice_id in SLICE_IDS
                for segment_name, local_base, size_bytes in ZERO_INPUT_SEGMENTS
            ],
            "pre_execution_output_sentinels": [
                {
                    "slice_id": slice_id,
                    "base_addr": f"0x{_physical_addr(slice_id, OUTPUT_LOCAL_BASE):08X}",
                    "size_bytes": OUTPUT_BYTES,
                    "fill_byte": f"0x{OUTPUT_SENTINEL_BYTE:02X}",
                    "line_count_128bit": sentinel_line_counts[slice_id],
                }
                for slice_id in SLICE_IDS
            ],
            "expected_output_all_zero": True,
            "unmodified_output_cannot_pass": True,
        },
    }
    _write_json(destination / "freeze_manifest.json", freeze_manifest)

    text_paths = sorted([*_normalize_package_text_files(destination), "manifest.json"])
    freeze_manifest_sha256 = _sha256_file(destination / "freeze_manifest.json")
    bitstream_records = []
    freeze_material = [freeze_manifest_sha256, SOURCE_CONFIG_SHA256]
    for slice_id, op_id, config_base, installed in zip(
        SLICE_IDS, CONFIG_OP_IDS, CONFIG_BASES, installed_configs, strict=True
    ):
        installed_identity = _bit_text_identity(installed, 128)
        source_evidence = destination / "encoder_evidence" / "run_a" / f"slice{slice_id:02d}" / "modules_dump_128b.bin"
        source_identity = _bit_text_identity(source_evidence, 128)
        if installed_identity["logical_sha256"] != source_identity["logical_sha256"]:
            raise NativeJsonRingGemmPackageV2Error(f"installed slice{slice_id} config differs")
        generated_config = destination / "source_config" / f"prefill_gemm_ring_4slice_slice{slice_id}.json"
        freeze_material.append(installed_identity["logical_sha256"])
        bitstream_records.append(
            {
                "binding_id": op_id,
                "role": "upstream_run_all_slices_ring4_member",
                "slice_id": slice_id,
                "base_config_sha256": SOURCE_CONFIG_SHA256,
                "generated_config": {
                    "path": generated_config.relative_to(destination).as_posix(),
                    "size_bytes": generated_config.stat().st_size,
                    "sha256": _sha256_file(generated_config),
                },
                "official_encoder": source_identity,
                "parsed_evidence": {
                    "path": f"encoder_evidence/run_a/slice{slice_id:02d}/parsed_bitstream.txt",
                    "sha256": _sha256_file(
                        destination / "encoder_evidence" / "run_a" / f"slice{slice_id:02d}" / "parsed_bitstream.txt"
                    ),
                },
                "config_base_addr": f"0x{config_base:08X}",
                "load_slice_mask": f"0x{1 << slice_id:07X}",
                "install": {"path": installed.relative_to(destination).as_posix(), **installed_identity},
            }
        )
    freeze_id = _sha256_bytes("".join(freeze_material).encode("ascii"))
    runtime_operator = runtime_operators[0]
    manifest = {
        "schema_version": PACKAGE_SCHEMA,
        "kind": PACKAGE_KIND,
        "status": "hardware_execplan_package_validated",
        "node_id": "deepseek-ring-gemm-control-v2",
        "hwop_id": "deepseek-prefill-gemm-ring-4slice-v2",
        "freeze_id": freeze_id,
        "freeze_manifest_sha256": freeze_manifest_sha256,
        "source_config_path": SOURCE_CONFIG.as_posix(),
        "source_config_sha256": SOURCE_CONFIG_SHA256,
        "source_config_rewritten": False,
        "hardware_trace_validation": trace,
        "runtime_operator_count": 1,
        "runtime_sequence": [RUNTIME_OP_ID],
        "runtime_operators": [
            {
                "operator_id": runtime_operator.op_id,
                "operator_type": runtime_operator.op_type,
                "stage": runtime_operator.stage,
                "instance_id": runtime_operator.instance_id,
                "slice_mask": f"0x{runtime_operator.used_slices:07X}",
                "attributes": dict(runtime_operator.attributes),
            }
        ],
        "testbench_observer": observer,
        "runtime_serialization": {
            "strategy": "post_start_same_mask_barrier",
            "barrier_opcode": f"0b{RUNTIME_BARRIER_OPCODE:03b}",
            "barrier_count": 1,
            "placement": "immediately_after_the_single_full_mask_Start_Comp",
            "configuration_strategy": (
                "four_independent_config_loads_then_one_full_ring4_start"
            ),
        },
        "config_lengths_64bit_words": {op_id: 60 for op_id in CONFIG_OP_IDS},
        "config_base_addresses": {
            op_id: f"0x{address:08X}"
            for op_id, address in zip(CONFIG_OP_IDS, CONFIG_BASES, strict=True)
        },
        "exec_base_address": f"0x{EXEC_BASE:08X}",
        "exec_128bit_line_count": int(sca["Exec_Length"]),
        "instruction_metadata": dict(artifact.metadata),
        "preloaded_input_count": 8,
        "preloaded_runtime_scratch_count": 12,
        "preloaded_golden_or_output_count": 0,
        "preload_transfer_segment_count": parser_transfer_count,
        "semantic_dump_region_count": len(golden_records),
        "sca_d_transfer_segment_count": len(sca_d),
        "bank_data_file_count": len(bank_paths),
        "bitstream_bindings": {
            "status": "fresh_upstream_json_run_all_slices_ab_freeze_install_bound",
            "record_count": len(bitstream_records),
            "records": bitstream_records,
        },
        "numeric_validation": {
            "status": "zero_input_unbiased_gemm_overwrites_nonzero_output_sentinel",
            "hardware_trace_numeric_boundary": trace["evidence_boundary"],
            "expected_output_all_zero": True,
            "output_slice_count": 4,
            "pre_execution_output_sentinel_byte": f"0x{OUTPUT_SENTINEL_BYTE:02X}",
            "unmodified_output_cannot_pass": True,
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
            "schema_version": "deepseek-package-text-abi-0.2",
            "encoding": "utf-8_or_ascii",
            "line_ending": "lf",
            "carriage_return_byte_allowed": False,
            "paths": text_paths,
        },
        "files": _output_hashes(destination),
    }
    _write_json(destination / "manifest.json", manifest)
    return validate_native_json_ring_gemm_package_v2(destination)


def validate_native_json_ring_gemm_package_v2(output_root: Path) -> dict[str, Any]:
    root = output_root.resolve()
    manifest = _read_json_object(root / "manifest.json")
    if (
        manifest.get("schema_version") != PACKAGE_SCHEMA
        or manifest.get("kind") != PACKAGE_KIND
        or manifest.get("status") != "hardware_execplan_package_validated"
        or manifest.get("source_config_sha256") != SOURCE_CONFIG_SHA256
        or manifest.get("source_config_rewritten") is not False
    ):
        raise NativeJsonRingGemmPackageV2Error("native Ring4 v2 package identity differs")
    source_copy = root / "source_config/prefill_gemm_ring_4slice.json.original"
    if _sha256_file(source_copy) != SOURCE_CONFIG_SHA256:
        raise NativeJsonRingGemmPackageV2Error("packaged fresh upstream Ring4 JSON differs")
    if _sha256_file(root / "freeze_manifest.json") != manifest.get("freeze_manifest_sha256"):
        raise NativeJsonRingGemmPackageV2Error("native Ring4 v2 freeze identity differs")
    if _output_hashes(root) != manifest.get("files"):
        raise NativeJsonRingGemmPackageV2Error("native Ring4 v2 package exact file set differs")
    text_count = _validate_package_text_contract(root, manifest["text_file_contract"])
    sca = _read_json_object(root / "sca_cfg.json")
    sca_d = _read_json_object(root / "sca_cfg_D.json")
    runner = _read_json_object(root / "runner_contract.json")
    if sca.get("Repeat_Num") != 1:
        raise NativeJsonRingGemmPackageV2Error("native Ring4 v2 Repeat_Num differs")
    transfer_count = _validate_immutable_tb_sca_parser_abi(root / "sca_cfg.json", sca)
    if transfer_count != manifest.get("preload_transfer_segment_count"):
        raise NativeJsonRingGemmPackageV2Error("native Ring4 v2 preload count differs")
    _validate_payload_intervals(sca, root)
    if len(sca_d) != manifest.get("sca_d_transfer_segment_count"):
        raise NativeJsonRingGemmPackageV2Error("native Ring4 v2 readback count differs")
    _validate_runtime_completion_barrier_contract(root, manifest, sca, runner)

    bindings = manifest.get("bitstream_bindings")
    if not isinstance(bindings, Mapping) or bindings.get("record_count") != 4:
        raise NativeJsonRingGemmPackageV2Error("native Ring4 v2 bitstream binding count differs")
    observed_slices = set()
    logical_hashes = set()
    for record in bindings["records"]:
        slice_id = int(record.get("slice_id", -1))
        observed_slices.add(slice_id)
        if record.get("load_slice_mask") != f"0x{1 << slice_id:07X}":
            raise NativeJsonRingGemmPackageV2Error(f"slice{slice_id} config load mask differs")
        install = record.get("install")
        if not isinstance(install, Mapping):
            raise NativeJsonRingGemmPackageV2Error("native Ring4 v2 install binding differs")
        installed_path = root / str(install["path"])
        actual_identity = _bit_text_identity(installed_path, 128)
        expected_identity = {key: value for key, value in install.items() if key != "path"}
        if actual_identity != expected_identity:
            raise NativeJsonRingGemmPackageV2Error(f"slice{slice_id} installed bitstream differs")
        logical_hashes.add(actual_identity["logical_sha256"])
    if observed_slices != set(SLICE_IDS) or len(logical_hashes) != 4:
        raise NativeJsonRingGemmPackageV2Error("native Ring4 v2 per-slice config coverage differs")

    runtime_operators = manifest.get("runtime_operators")
    if (
        not isinstance(runtime_operators, list)
        or len(runtime_operators) != 1
        or runtime_operators[0].get("slice_mask") != "0x000000F"
        or runtime_operators[0].get("attributes", {}).get("runtime_partition") != "full_ring_group"
    ):
        raise NativeJsonRingGemmPackageV2Error("native Ring4 v2 runtime topology differs")
    golden = root / "golden/ring_D_zero.txt"
    if any(set(line) != {"0"} for line in _read_128bit_binary_lines(golden)):
        raise NativeJsonRingGemmPackageV2Error("native Ring4 v2 zero golden differs")
    sentinel_word = int.from_bytes(
        bytes([OUTPUT_SENTINEL_BYTE]) * 16, byteorder="little"
    )
    for slice_id in SLICE_IDS:
        sentinel = (
            root
            / "install/control_input"
            / f"slice{slice_id:02d}_D_sentinel_4KiB.txt"
        )
        lines = _read_128bit_binary_lines(sentinel)
        if len(lines) != OUTPUT_BEATS or any(int(line, 2) != sentinel_word for line in lines):
            raise NativeJsonRingGemmPackageV2Error(
                f"native Ring4 v2 slice{slice_id} output sentinel differs"
            )
    numeric = manifest.get("numeric_validation")
    if (
        not isinstance(numeric, Mapping)
        or numeric.get("status")
        != "zero_input_unbiased_gemm_overwrites_nonzero_output_sentinel"
        or numeric.get("unmodified_output_cannot_pass") is not True
    ):
        raise NativeJsonRingGemmPackageV2Error(
            "native Ring4 v2 writeback-proof contract differs"
        )
    trace = manifest.get("hardware_trace_validation")
    if not isinstance(trace, Mapping) or trace.get("status") != "target_hardware_completed_full_writeback":
        raise NativeJsonRingGemmPackageV2Error("native Ring4 v2 hardware trace evidence differs")
    return {
        "status": "hardware_execplan_package_validated",
        "kind": manifest["kind"],
        "source_config_sha256": SOURCE_CONFIG_SHA256,
        "source_config_rewritten": False,
        "hardware_trace_status": trace["status"],
        "hardware_completion_cycle": trace["completion_cycle"],
        "hardware_writeback_words": trace["writeback"]["observed_unique_128bit_addresses"],
        "runtime_operator_count": manifest["runtime_operator_count"],
        "runtime_slice_mask": "0x000000F",
        "exec_128bit_line_count": manifest["exec_128bit_line_count"],
        "preload_transfer_count": transfer_count,
        "readback_transfer_count": len(sca_d),
        "bank_data_file_count": manifest["bank_data_file_count"],
        "bitstream_binding_count": bindings["record_count"],
        "checked_file_count": len(manifest["files"]),
        "text_file_count": text_count,
    }
