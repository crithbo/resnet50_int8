"""Server control package for the immutable native ResNet-50 MaxPool JSON.

The operator configuration consumed here is the Git-tracked file under
``ndp-sim/jsons``. This module never rewrites that JSON.  It starts every
placement attempt from an empty-cache clone of the locked Git commit, encodes
the chosen exact mapping twice in isolated roots, and runs one real ResNet
channel tile on slice0 and slice1.  Callers may either perform the historical
fresh numeric check or reuse the frozen W3 input/golden under the approved
full-node local-E2 receipt without repeating MaxPool arithmetic.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

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
    _sca_transport_entries,
    _sha256_file,
    _split_sca_d_transfers,
    _split_sca_preload_transfers,
    _validate_immutable_tb_sca_parser_abi,
    _validate_package_text_contract,
    _validate_payload_intervals,
    _validate_runtime_completion_barrier_contract,
    _write_128bit_binary_text,
    _write_json,
    _write_text_lf,
    _write_zero_128bit_binary_text,
)
from .errors import PipelineError


SOURCE_CONFIG = Path("ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json")
PACKAGED_SOURCE_CONFIG_NAME = SOURCE_CONFIG.name + ".original"
SOURCE_CONFIG_SHA256 = "a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1"
SOURCE_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
SOURCE_BLOB = "4e8f7bb8906ab58f54f4c6507d2b94822f71bf04"
SOURCE_REMOTE = "https://github.com/uSFrances/ndp-sim.git"
ENCODER_SEED_ORDER = (42, 20260728, 314159)
ENCODER_ITERATIONS = 10_000
ENCODER_RESTARTS = 2
INPUT_TENSOR_ID = "tensor-f6c1a8fb6fd529e8"
OUTPUT_TENSOR_ID = "tensor-8d2f28c80ac24676"
APPROVED_E2_REPORT = Path(
    "artifacts/operator_config_validation/"
    "maxpool-node0002-config-only-e2-v1/validation_report.json"
)
APPROVED_E2_REPORT_SHA256 = (
    "5fb484e9c1bf40b86d68c21c8837e6a61978e63cac40e9e2f5b3b42ea3dd9a61"
)
SLICE_SHIFT = 25
ROW_BYTES = 1024
ACTIVE_SLICES = (0, 1)
OP_IDS = ("op-native-maxpool-slice0", "op-native-maxpool-slice1")
READBACK_IDS = ("hwop-native-maxpool-slice0", "hwop-native-maxpool-slice1")
LOCAL_INPUT_SHAPE = (112, 112, 16)
LOCAL_OUTPUT_SHAPE = (56, 56, 16)
INPUT_OFFSET = 1024
OUTPUT_OFFSET = 201728
INPUT_BYTES = math.prod(LOCAL_INPUT_SHAPE)
OUTPUT_BYTES = math.prod(LOCAL_OUTPUT_SHAPE)
ALL_ACTIVE_MASK = sum(1 << item for item in ACTIVE_SLICES)


class NativeJsonMaxPoolPackageError(PipelineError):
    """Raised when the immutable native-JSON control package differs."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def _exec_address(slice_id: int, local_offset: int) -> int:
    if slice_id not in ACTIVE_SLICES or not 0 <= local_offset < (1 << SLICE_SHIFT):
        raise NativeJsonMaxPoolPackageError("invalid native MaxPool execution address")
    return (slice_id << SLICE_SHIFT) | local_offset


def _normalize_lf(path: Path) -> None:
    try:
        text = path.read_bytes().decode("ascii")
    except UnicodeDecodeError as error:
        raise NativeJsonMaxPoolPackageError(f"non-ASCII server text: {path}") from error
    _write_text_lf(path, text.replace("\r\n", "\n").replace("\r", "\n"), encoding="ascii")


def _bit_text_identity(path: Path, width: int) -> dict[str, Any]:
    lines = [line.strip() for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
    if not lines or any(len(line) != width or set(line) - {"0", "1"} for line in lines):
        raise NativeJsonMaxPoolPackageError(f"invalid {width}-bit encoder output: {path}")
    logical = ("\n".join(lines) + "\n").encode("ascii")
    return {
        "raw_size_bytes": path.stat().st_size,
        "raw_sha256": _sha256_file(path),
        "logical_size_bytes": len(logical),
        "logical_sha256": _sha256_bytes(logical),
        "line_count": len(lines),
        "line_width_bits": width,
    }


def _git(project_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    repository = project_root / "ndp-sim"
    command = [
        "git",
        "-c",
        f"safe.directory={repository.as_posix()}",
        "-c",
        f"safe.directory={(repository / '.git').as_posix()}",
        *arguments,
    ]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _clone_locked_tool(project_root: Path, destination: Path) -> None:
    repository = project_root / "ndp-sim"
    origin = _git(
        project_root,
        "-C",
        str(repository),
        "remote",
        "get-url",
        "origin",
    )
    if origin.returncode or origin.stdout.strip() != SOURCE_REMOTE:
        raise NativeJsonMaxPoolPackageError("ndp-sim GitHub origin identity differs")
    completed = _git(
        project_root,
        "clone",
        "--local",
        "--no-hardlinks",
        str(repository),
        str(destination),
    )
    if completed.returncode:
        raise NativeJsonMaxPoolPackageError(
            f"locked ndp-sim clone failed: {completed.stderr.strip()}"
        )
    safe = destination.as_posix()
    head = subprocess.run(
        ["git", "-c", f"safe.directory={safe}", "-C", str(destination), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    tracked = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={safe}",
            "-C",
            str(destination),
            "ls-files",
            "--stage",
            "--",
            "jsons/maxpool_config_16_112_112_stride2_padding1.json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if (
        head.returncode
        or head.stdout.strip() != SOURCE_COMMIT
        or tracked.returncode
        or not tracked.stdout.startswith(f"100644 {SOURCE_BLOB} 0\t")
    ):
        raise NativeJsonMaxPoolPackageError("locked GitHub MaxPool source identity differs")
    cache = destination / "bitstream/config/mapping_cache"
    cache.mkdir(parents=True, exist_ok=True)
    if any(cache.iterdir()):
        raise NativeJsonMaxPoolPackageError("fresh encoder clone contains a mapping cache")


def _run_encoder_attempt(
    project_root: Path,
    attempt_root: Path,
    seed: int,
) -> tuple[Path | None, dict[str, Any]]:
    tool = attempt_root / "tool"
    output = attempt_root / "output"
    _clone_locked_tool(project_root, tool)
    source = tool / "jsons/maxpool_config_16_112_112_stride2_padding1.json"
    if _sha256_file(source) != SOURCE_CONFIG_SHA256:
        raise NativeJsonMaxPoolPackageError("cloned MaxPool source bytes differ")
    command = [
        str(project_root / ".venv/Scripts/python.exe"),
        str(tool / "bitstream/main.py"),
        "-c",
        str(source),
        "-o",
        str(output),
        "--seed",
        str(seed),
        "--heuristic-iterations",
        str(ENCODER_ITERATIONS),
        "--heuristic-restarts",
        str(ENCODER_RESTARTS),
        "-q",
    ]
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONHASHSEED"] = "0"
    completed = subprocess.run(
        command,
        cwd=tool,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=180,
    )
    stdout_path = attempt_root / "stdout.log"
    stderr_path = attempt_root / "stderr.log"
    _write_text_lf(stdout_path, completed.stdout)
    _write_text_lf(stderr_path, completed.stderr)
    exact = (
        completed.returncode == 0
        and "[✓] Mapping successful with zero violations" in completed.stdout
        and (output / "mapping_review.json").is_file()
        and (output / "modules_dump_128b.bin").is_file()
    )
    exact = (
        completed.returncode == 0
        and "Mapping successful with zero violations" in completed.stdout
        and (output / "mapping_review.json").is_file()
        and (output / "modules_dump_128b.bin").is_file()
    )
    receipt = {
        "seed": seed,
        "iterations": ENCODER_ITERATIONS,
        "internal_restarts": ENCODER_RESTARTS,
        "mapping_cache_initial_file_count": 0,
        "command": (
            "python <clean-clone>/bitstream/main.py "
            "-c <clean-clone>/jsons/maxpool_config_16_112_112_stride2_padding1.json "
            "-o <fresh-output> "
            f"--seed {seed} --heuristic-iterations {ENCODER_ITERATIONS} "
            f"--heuristic-restarts {ENCODER_RESTARTS} -q"
        ),
        "exit_code": completed.returncode,
        "penalty": 0 if exact else None,
        "fallback_used": False,
        "exact_mapping": exact,
        "stdout_packaged": False,
        "stderr_packaged": False,
    }
    return (output if exact else None), receipt


def _encoder_run_identity(run: Path) -> dict[str, Any]:
    mapping = _read_json_object(run / "mapping_review.json")
    if mapping.get("summary", {}).get("connections") != 26:
        raise NativeJsonMaxPoolPackageError("fresh MaxPool mapping connection count differs")
    return {
        "bitstream_128b": _bit_text_identity(run / "modules_dump_128b.bin", 128),
        "bitstream_64b": _bit_text_identity(run / "modules_dump_64b.bin", 64),
        "parsed_bitstream": {
            "size_bytes": (run / "parsed_bitstream.txt").stat().st_size,
            "sha256": _sha256_file(run / "parsed_bitstream.txt"),
        },
        "mapping_review": {
            "size_bytes": (run / "mapping_review.json").stat().st_size,
            "sha256": _sha256_file(run / "mapping_review.json"),
        },
        "detailed_dump": {
            "size_bytes": (run / "detailed_dump.txt").stat().st_size,
            "sha256": _sha256_file(run / "detailed_dump.txt"),
        },
        "penalty": 0,
        "fallback_used": False,
    }


def _encoder_evidence(
    project_root: Path, work_root: Path, destination: Path
) -> tuple[dict[str, Any], Path]:
    sweep: list[dict[str, Any]] = []
    selected_seed: int | None = None
    for index, seed in enumerate(ENCODER_SEED_ORDER):
        output, receipt = _run_encoder_attempt(
            project_root, work_root / f"sweep-{index:02d}-seed-{seed}", seed
        )
        sweep.append(receipt)
        if output is not None:
            selected_seed = seed
            break
    if selected_seed is None:
        raise NativeJsonMaxPoolPackageError(
            "fresh empty-cache seed sweep found no exact MaxPool placement"
        )

    runs: dict[str, Any] = {}
    selected_output: Path | None = None
    for label in ("encoder_run_a", "encoder_run_b"):
        output, receipt = _run_encoder_attempt(
            project_root, work_root / f"release-{label}", selected_seed
        )
        if output is None:
            raise NativeJsonMaxPoolPackageError(
                f"isolated fresh MaxPool encoder run failed: {label}"
            )
        target = destination / label
        shutil.copytree(output, target)
        identity = _encoder_run_identity(target)
        identity["receipt"] = receipt
        runs[label] = identity
        if selected_output is None:
            selected_output = target
    semantic_names = (
        "mapping_review.json",
        "parsed_bitstream.txt",
        "modules_dump_64b.bin",
        "modules_dump_128b.bin",
        "detailed_dump.txt",
    )
    mismatches = [
        name
        for name in semantic_names
        if _sha256_file(destination / "encoder_run_a" / name)
        != _sha256_file(destination / "encoder_run_b" / name)
    ]
    if mismatches:
        raise NativeJsonMaxPoolPackageError(
            f"fresh isolated encoder semantic outputs differ: {mismatches}"
        )
    return (
        {
            "command_template": (
                "python bitstream/main.py -c <clean-clone>/jsons/"
                "maxpool_config_16_112_112_stride2_padding1.json -o <fresh-output> "
                f"--seed <seed> --heuristic-iterations {ENCODER_ITERATIONS} "
                f"--heuristic-restarts {ENCODER_RESTARTS} -q"
            ),
            "seed_order": list(ENCODER_SEED_ORDER),
            "sweep": sweep,
            "selected_seed": selected_seed,
            "selected_by": "first exact penalty=0 and fallback=false in declared seed order",
            "deterministic_repeat_count": 2,
            "semantic_outputs_compared": list(semantic_names),
            "semantic_mismatch_paths": [],
            "runs": runs,
        },
        selected_output,
    )


def _load_real_tiles(project_root: Path) -> tuple[list[np.ndarray], list[np.ndarray], dict[str, Any]]:
    tensor_root = project_root / "artifacts/w3/golden_batch16/tensors"
    input_path = tensor_root / f"{INPUT_TENSOR_ID}.npy"
    activation = np.load(input_path, allow_pickle=False)
    if activation.dtype != np.uint8 or activation.shape != (16, 64, 112, 112):
        raise NativeJsonMaxPoolPackageError("real ResNet MaxPool input tensor differs")
    inputs = [
        np.ascontiguousarray(activation[0, start : start + 16].transpose(1, 2, 0))
        for start in (0, 16)
    ]
    outputs = []
    for value in inputs:
        padded = np.pad(value, ((1, 1), (1, 1), (0, 0)), constant_values=0)
        windows = [
            padded[row : row + 112 : 2, column : column + 112 : 2, :]
            for row in range(3)
            for column in range(3)
        ]
        outputs.append(np.ascontiguousarray(np.maximum.reduce(windows), dtype=np.uint8))
    return inputs, outputs, {
        "input_path": input_path.relative_to(project_root).as_posix(),
        "input_npy_sha256": _sha256_file(input_path),
        "output_tensor_read": False,
        "golden_generator": "independent numpy maximum.reduce over nine padded windows",
        "golden_source": "freshly derived from formal node0002 input tensor only",
    }


def _load_reused_e2_tiles(
    project_root: Path,
) -> tuple[list[np.ndarray], list[np.ndarray], dict[str, Any], list[dict[str, Any]]]:
    """Load frozen W3 input/golden bytes under the approved full-node E2 receipt.

    This path deliberately performs no MaxPool arithmetic and does not invoke
    the functional model.  It is used when a server package is materialized
    under the reuse-first rule.
    """

    report_path = project_root / APPROVED_E2_REPORT
    if _sha256_file(report_path) != APPROVED_E2_REPORT_SHA256:
        raise NativeJsonMaxPoolPackageError("approved MaxPool E2 receipt differs")
    report = _read_json_object(report_path)
    simulator = report.get("config_bound_simulator")
    if (
        report.get("valid") is not True
        or report.get("evidence_level") != "E2"
        or not isinstance(simulator, Mapping)
        or simulator.get("logical_mismatch_count") != 0
        or simulator.get("physical_mismatch_count") != 0
        or simulator.get("physical_occurrence_count") != 64
    ):
        raise NativeJsonMaxPoolPackageError("approved MaxPool E2 receipt is not reusable")

    tensor_root = project_root / "artifacts/w3/golden_batch16/tensors"
    input_path = tensor_root / f"{INPUT_TENSOR_ID}.npy"
    output_path = tensor_root / f"{OUTPUT_TENSOR_ID}.npy"
    activation = np.load(input_path, allow_pickle=False)
    golden = np.load(output_path, allow_pickle=False)
    if activation.dtype != np.uint8 or activation.shape != (16, 64, 112, 112):
        raise NativeJsonMaxPoolPackageError("reused MaxPool input tensor differs")
    if golden.dtype != np.uint8 or golden.shape != (16, 64, 56, 56):
        raise NativeJsonMaxPoolPackageError("reused MaxPool golden tensor differs")

    inputs = [
        np.ascontiguousarray(activation[0, start : start + 16].transpose(1, 2, 0))
        for start in (0, 16)
    ]
    outputs = [
        np.ascontiguousarray(golden[0, start : start + 16].transpose(1, 2, 0))
        for start in (0, 16)
    ]
    records = [
        {
            "slice_id": slice_id,
            "input_sha256": _sha256_bytes(value.tobytes(order="C")),
            "golden_sha256": _sha256_bytes(expected.tobytes(order="C")),
            "element_count": int(expected.size),
            "mismatch_count": 0,
            "evidence_source": "approved_full_node_local_e2_reuse",
            "numeric_analysis_repeated": False,
        }
        for slice_id, (value, expected) in enumerate(zip(inputs, outputs, strict=True))
    ]
    return inputs, outputs, {
        "input_path": input_path.relative_to(project_root).as_posix(),
        "input_npy_sha256": _sha256_file(input_path),
        "output_path": output_path.relative_to(project_root).as_posix(),
        "output_npy_sha256": _sha256_file(output_path),
        "output_tensor_read": True,
        "golden_source": "frozen W3 tensor under approved full-node local E2",
        "approved_e2_report": APPROVED_E2_REPORT.as_posix(),
        "approved_e2_report_sha256": APPROVED_E2_REPORT_SHA256,
        "reuse_class": "EXACT_FULL_OPERATOR",
        "numeric_analysis_repeated": False,
    }, records


def _validate_local_numeric(
    project_root: Path,
    source_config: Mapping[str, Any],
    inputs: list[np.ndarray],
    outputs: list[np.ndarray],
) -> list[dict[str, Any]]:
    ndp_root = project_root / "NDPFuncModel"
    if str(ndp_root) not in sys.path:
        sys.path.insert(0, str(ndp_root))
    from component.GeneralPEA import GeneralPEA

    expected = {
        "channels": 16,
        "height": 112,
        "width": 112,
        "kernel_shape": [3, 3],
        "strides": [2, 2],
        "pads": [1, 1, 1, 1],
        "dilations": [1, 1],
        "output_height": 56,
        "output_width": 56,
        "input_offset": INPUT_OFFSET,
        "output_offset": OUTPUT_OFFSET,
    }
    stream0 = source_config["stream_engine"]["stream0"]
    stream1 = source_config["stream_engine"]["stream1"]
    source_shape_fields = {
        "input_base_addr": stream0["base_addr"],
        "input_dim_stride": stream0["dim_stride"],
        "input_padding_low": stream0["idx_padding_range"]["low_bound"],
        "input_padding_high": stream0["idx_padding_range"]["up_bound"],
        "output_base_addr": stream1["base_addr"],
        "output_dim_stride": stream1["dim_stride"],
        "height_loop_end": source_config["dram_loop_configs"]["LC1"]["end"],
        "output_height_loop_end": source_config["dram_loop_configs"]["LC6"]["end"],
        "channel_loop_end": source_config["dram_loop_configs"]["LC5"]["end"],
    }
    expected_source_shape_fields = {
        "input_base_addr": INPUT_OFFSET,
        "input_dim_stride": [4, 448, 50176],
        "input_padding_low": [1, 1, None],
        "input_padding_high": [112, 112, None],
        "output_base_addr": OUTPUT_OFFSET,
        "output_dim_stride": [12544, 224, 32],
        "height_loop_end": 112,
        "output_height_loop_end": 56,
        "channel_loop_end": 16,
    }
    if source_shape_fields != expected_source_shape_fields:
        raise NativeJsonMaxPoolPackageError(
            f"native MaxPool JSON shape fields differ: {source_shape_fields}"
        )
    pea = GeneralPEA.from_target_config(dict(source_config))
    records = []
    for slice_id, (value, golden) in enumerate(zip(inputs, outputs, strict=True)):
        actual = pea.maxpool2d_nhwc(
            value,
            kernel_shape=(3, 3),
            strides=(2, 2),
            pads=(1, 1, 1, 1),
            dilations=(1, 1),
            padding_value=0,
        )
        mismatches = int(np.count_nonzero(actual != golden))
        if mismatches:
            raise NativeJsonMaxPoolPackageError(
                f"native MaxPool JSON differs from W3 golden on slice {slice_id}: {mismatches}"
            )
        records.append(
            {
                "slice_id": slice_id,
                "input_sha256": _sha256_bytes(value.tobytes(order="C")),
                "golden_sha256": _sha256_bytes(golden.tobytes(order="C")),
                "element_count": int(golden.size),
                "mismatch_count": 0,
            }
        )
    return records


def _write_raw_and_text(array: np.ndarray, raw_path: Path, text_path: Path) -> dict[str, Any]:
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(np.ascontiguousarray(array).tobytes(order="C"))
    line_count, first_word = _write_128bit_binary_text(raw_path, text_path)
    return {
        "raw_sha256": _sha256_file(raw_path),
        "text_sha256": _sha256_file(text_path),
        "line_count_128bit": line_count,
        "expected_first_128bit": first_word,
    }


def _text_paths(root: Path) -> list[str]:
    result = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        try:
            payload = path.read_bytes()
            payload.decode("ascii")
        except UnicodeDecodeError:
            continue
        if b"\r" not in payload and payload.endswith(b"\n"):
            result.append(path.relative_to(root).as_posix())
    return result


def generate_native_json_maxpool_package(
    project_root: Path,
    output_root: Path,
    *,
    reuse_approved_e2: bool = False,
) -> dict[str, Any]:
    root = project_root.resolve()
    destination = output_root.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise NativeJsonMaxPoolPackageError(f"refusing to mix package evidence: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    source_path = root / SOURCE_CONFIG
    source_bytes = source_path.read_bytes()
    if _sha256_bytes(source_bytes) != SOURCE_CONFIG_SHA256:
        raise NativeJsonMaxPoolPackageError("native MaxPool source JSON identity differs")
    source_config = json.loads(source_bytes.decode("utf-8"))
    with tempfile.TemporaryDirectory(prefix="maxpool-fresh-encoder-") as temporary:
        encoder, encoder_run = _encoder_evidence(
            root,
            Path(temporary),
            destination / "evidence/fresh_encoder",
        )
    if reuse_approved_e2:
        inputs, goldens, tensor_sources, numeric_records = _load_reused_e2_tiles(root)
    else:
        inputs, goldens, tensor_sources = _load_real_tiles(root)
        numeric_records = _validate_local_numeric(root, source_config, inputs, goldens)

    # The tracked JSON uses its original repository newline convention. Keep an
    # exact byte-for-byte evidence copy outside the package LF-normalization set.
    source_copy = destination / "source_config" / PACKAGED_SOURCE_CONFIG_NAME
    source_copy.parent.mkdir(parents=True)
    shutil.copyfile(source_path, source_copy)
    api = _load_execplan_api(root)
    external = api["InputSource"](api["InputSourceType"].EXTERNAL)
    operators = []
    assignments: dict[str, Any] = {}
    io_map: dict[str, str] = {}
    for slice_id, op_id in zip(ACTIVE_SLICES, OP_IDS, strict=True):
        runtime_partition = "non_observer_slices" if slice_id == 0 else "finish_slice_only"
        operators.append(
            api["OperatorSpec"](
                op_id=op_id,
                op_type="resnet_maxpool_uint8_native_json",
                used_slices=1 << slice_id,
                inputs={"A": api["TensorSpec"](LOCAL_INPUT_SHAPE, dtype="uint8", source=external)},
                output=api["TensorSpec"](LOCAL_OUTPUT_SHAPE, dtype="uint8"),
                instance_id="resnet50:node-0002:native-json-control",
                stage="maxpool",
                attributes={
                    "slice_id": slice_id,
                    "source_config_sha256": SOURCE_CONFIG_SHA256,
                    "runtime_partition": runtime_partition,
                    "shard_index": 0,
                },
            )
        )
        a_name = f"native.A.slice-{slice_id:02d}"
        d_name = f"native.D.slice-{slice_id:02d}"
        assignments[a_name] = api["AddressAssignment"](
            tensor_name=a_name,
            base_address=INPUT_OFFSET,
            per_slice_addresses={slice_id: _exec_address(slice_id, INPUT_OFFSET)},
            size_bytes=INPUT_BYTES,
            shape=LOCAL_INPUT_SHAPE,
        )
        assignments[d_name] = api["AddressAssignment"](
            tensor_name=d_name,
            base_address=OUTPUT_OFFSET,
            per_slice_addresses={slice_id: _exec_address(slice_id, OUTPUT_OFFSET)},
            size_bytes=OUTPUT_BYTES,
            shape=LOCAL_OUTPUT_SHAPE,
        )
        io_map[f"{op_id}.input.A"] = a_name
        io_map[f"{op_id}.output.D"] = d_name

    execution_input = api["ExecutionPlanInput"](
        used_slices=ALL_ACTIVE_MASK,
        operators=operators,
        schema_version="resnet50-native-json-maxpool-control-0.1",
        plan_id="node-0002-native-json-maxpool-control-v1",
    )
    bitstream_source = encoder_run / "modules_dump_128b.bin"
    parsed_source = encoder_run / "parsed_bitstream.txt"
    config_length = len(_read_128bit_binary_lines(bitstream_source)) * 2
    config_start = _align_up(OUTPUT_OFFSET + OUTPUT_BYTES, ROW_BYTES)
    config_bases = [config_start + index * ROW_BYTES for index in range(len(operators))]
    exec_base = config_start + len(operators) * ROW_BYTES
    address_plan = api["AddressPlan"](
        assignments=assignments,
        operator_io_to_tensor=io_map,
        operator_config_base_addresses=dict(zip(OP_IDS, config_bases, strict=True)),
        operator_config_lengths={op_id: config_length for op_id in OP_IDS},
    )
    original_values, enabled_addresses = _decode_template_state(api, root, parsed_source)
    templates = {
        op_id: api["OperatorTemplate"](
            op_type="resnet_maxpool_uint8_native_json",
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
        raise NativeJsonMaxPoolPackageError(f"native MaxPool execplan metadata differs: {artifact.metadata}")
    exec_path, explanation_path = api["write_instruction_outputs"](artifact, destination)
    sca_path = api["write_install_manifest"](
        execution_input,
        address_plan,
        templates,
        artifact,
        destination,
        exec_base_addr=exec_base,
    )

    input_records = []
    golden_records = []
    for slice_id, op_id, readback_id, value, golden in zip(
        ACTIVE_SLICES, OP_IDS, READBACK_IDS, inputs, goldens, strict=True
    ):
        slice_dir = f"slice{slice_id:02d}"
        input_text = destination / f"install/{op_id}/{slice_dir}/matrix_A_linearized_128bit.txt"
        input_raw = destination / f"evidence/input/{slice_dir}.bin"
        input_records.append(
            {
                "slice_id": slice_id,
                "base_addr": f"0x{_exec_address(slice_id, INPUT_OFFSET):08X}",
                "path": input_text.relative_to(destination).as_posix(),
                **_write_raw_and_text(value, input_raw, input_text),
            }
        )
        golden_text = destination / f"golden/{slice_dir}.txt"
        golden_raw = destination / f"evidence/golden/{slice_dir}.bin"
        golden_records.append(
            {
                "slice_id": slice_id,
                "base_addr": f"0x{_exec_address(slice_id, OUTPUT_OFFSET):08X}",
                "semantic_path": (
                    f"install/{readback_id}/{slice_dir}/matrix_D_linearized_128bit.txt"
                ),
                "golden_path": golden_text.relative_to(destination).as_posix(),
                **_write_raw_and_text(golden, golden_raw, golden_text),
            }
        )

    official_sca = _read_json_object(sca_path)
    sca: dict[str, Any] = {
        "Exec_Base": official_sca["Exec_Base"],
        "Exec_Length": official_sca["Exec_Length"],
        "Repeat_Num": 1,
        "ExecutionPlan": official_sca["ExecutionPlan"],
    }
    for key, value in official_sca.items():
        if key.endswith("_config") or "_matrixA_" in key:
            sca[key] = value
    scratch_entries = []
    for slice_id, op_id in zip(ACTIVE_SLICES, OP_IDS, strict=True):
        path = destination / f"install/runtime_scratch/{op_id}/slice-{slice_id:02d}.txt"
        length = _write_zero_128bit_binary_text(path, OUTPUT_BYTES)
        key = f"runtime_scratch_D_slice{slice_id}"
        sca[key] = {
            "base_addr": f"0x{_exec_address(slice_id, OUTPUT_OFFSET):08X}",
            "path": path.relative_to(destination).as_posix(),
        }
        scratch_entries.append({"key": key, "line_count_128bit": length})
    sca, preload_segments, bank_export_sca = _split_sca_preload_transfers(sca, destination)
    _write_json(sca_path, sca)
    # Bind the parser check to the exact serialized object. Some source manifest
    # values retain non-canonical mapping subclasses in memory even though their
    # JSON representation is canonical.
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

    semantic_sca_d = _read_json_object(destination / "sca_cfg_D.json")
    for value in semantic_sca_d.values():
        if not isinstance(value, Mapping) or not isinstance(value.get("path"), str):
            continue
        for op_id, readback_id in zip(OP_IDS, READBACK_IDS, strict=True):
            old_prefix = f"install/{op_id}/"
            if value["path"].startswith(old_prefix):
                value["path"] = f"install/{readback_id}/" + value["path"][len(old_prefix) :]
                break
    sca_d = _split_sca_d_transfers(semantic_sca_d)
    _write_json(destination / "sca_cfg_D.json", sca_d)
    axi_report = _build_axi4_4kb_trigger_report(destination, preload_segments, semantic_sca_d, sca_d)
    _write_json(destination / "axi4_4kb_report.json", axi_report)
    for path in (destination / "install").rglob("*"):
        if path.is_file():
            _normalize_lf(path)
    installed_bitstream = destination / "install/cfg_pkg" / bitstream_source.name
    installed_identity = _bit_text_identity(installed_bitstream, 128)
    source_identity = _bit_text_identity(bitstream_source, 128)

    observer = {
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
    runtime_operators = [
        {
            "operator_id": op_id,
            "operator_type": "resnet_maxpool_uint8_native_json",
            "stage": "maxpool",
            "instance_id": "resnet50:node-0002:native-json-control",
            "slice_mask": f"0x{1 << slice_id:07X}",
            "attributes": {
                "slice_id": slice_id,
                "source_config_sha256": SOURCE_CONFIG_SHA256,
                "runtime_partition": (
                    "non_observer_slices" if slice_id == 0 else "finish_slice_only"
                ),
                "shard_index": 0,
            },
        }
        for slice_id, op_id in zip(ACTIVE_SLICES, OP_IDS, strict=True)
    ]
    _write_json(
        destination / "dump_contract.json",
        {
            "schema_version": "resnet50-native-json-maxpool-dump-0.1",
            "operator": "MaxPoolUint8",
            "semantic_regions": golden_records,
            "comparison": "full uint8 physical payload, including every output byte",
        },
    )
    runner_contract = {
        "schema_version": "resnet50-native-json-maxpool-runner-0.1",
        "preload": {
            "preferred_source": "sca_cfg.json",
            "rule": "load every immutable-parser transfer and require exact PASS accounting",
            "slice_count": 2,
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
            "exec_base": f"0x{exec_base:08X}",
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
            "semantic_region_count": len(semantic_sca_d),
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
        "comparison_command": "python tools/analyze_native_json_maxpool_return.py <zip>",
    }
    _write_json(destination / "runner_contract.json", runner_contract)
    freeze_manifest = {
        "schema_version": "resnet50-native-json-maxpool-freeze-0.1",
        "identity": {
            "node_id": "node-0002",
            "hwop_id": "hwop-0002-00",
            "operator": "MaxPoolUint8",
            "source_config_path": SOURCE_CONFIG.as_posix(),
            "source_config_sha256": SOURCE_CONFIG_SHA256,
            "source_git_remote": SOURCE_REMOTE,
            "source_git_commit": SOURCE_COMMIT,
            "source_git_blob": SOURCE_BLOB,
            "source_json_rewritten": False,
        },
        "real_resnet_tensors": tensor_sources,
        "numeric_validation": numeric_records,
        "encoder": encoder,
        "input_records": input_records,
        "golden_records": golden_records,
    }
    _write_json(destination / "freeze_manifest.json", freeze_manifest)
    freeze_manifest_sha256 = _sha256_file(destination / "freeze_manifest.json")
    freeze_id = _sha256_bytes(
        (freeze_manifest_sha256 + SOURCE_CONFIG_SHA256 + installed_identity["logical_sha256"]).encode("ascii")
    )
    bitstream_records = []
    for slice_id, op_id, config_base in zip(ACTIVE_SLICES, OP_IDS, config_bases, strict=True):
        bitstream_records.append(
            {
                "binding_id": op_id,
                "role": "native_maxpool",
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
                "install": {
                    "path": installed_bitstream.relative_to(destination).as_posix(),
                    **installed_identity,
                },
            }
        )
    text_paths = sorted([*_normalize_package_text_files(destination), "manifest.json"])
    manifest = {
        "schema_version": "resnet50-native-json-maxpool-hardware-package-0.1",
        "kind": "native_json_maxpool_hardware_execplan_package",
        "status": "hardware_execplan_package_validated",
        "node_id": "node-0002",
        "hwop_id": "hwop-0002-00",
        "freeze_id": freeze_id,
        "freeze_manifest_sha256": freeze_manifest_sha256,
        "source_config_path": SOURCE_CONFIG.as_posix(),
        "source_config_sha256": SOURCE_CONFIG_SHA256,
        "source_config_rewritten": False,
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
        "config_base_addresses": {
            op_id: f"0x{address:08X}" for op_id, address in zip(OP_IDS, config_bases, strict=True)
        },
        "exec_base_address": f"0x{exec_base:08X}",
        "exec_128bit_line_count": int(sca["Exec_Length"]),
        "instruction_metadata": dict(artifact.metadata),
        "preloaded_input_count": len(input_records),
        "preloaded_runtime_scratch_count": len(scratch_entries),
        "preloaded_golden_or_output_count": 0,
        "preload_transfer_segment_count": parser_transfer_count,
        "semantic_dump_region_count": len(semantic_sca_d),
        "sca_d_transfer_segment_count": len(sca_d),
        "bank_data_file_count": len(bank_paths),
        "bitstream_bindings": {
            "status": "json_official_encoder_freeze_install_bound",
            "record_count": len(bitstream_records),
            "records": bitstream_records,
        },
        "numeric_validation": {
            "status": "passed",
            "source": (
                "approved full-node local E2 and frozen W3 input/golden reuse"
                if reuse_approved_e2
                else (
                    "formal W3 node0002 input plus independent NumPy maxpool golden "
                    "vs config-bound NDP GeneralPEA"
                )
            ),
            "formal_output_tensor_read": reuse_approved_e2,
            "numeric_analysis_repeated": not reuse_approved_e2,
            "records": numeric_records,
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
            "schema_version": "resnet50-package-text-abi-0.1",
            "encoding": "utf-8_or_ascii",
            "line_ending": "lf",
            "carriage_return_byte_allowed": False,
            "paths": text_paths,
        },
        "files": _output_hashes(destination),
    }
    _write_json(destination / "manifest.json", manifest)
    return validate_native_json_maxpool_package(destination)


def validate_native_json_maxpool_package(output_root: Path) -> dict[str, Any]:
    root = output_root.resolve()
    manifest = _read_json_object(root / "manifest.json")
    if (
        manifest.get("schema_version") != "resnet50-native-json-maxpool-hardware-package-0.1"
        or manifest.get("kind") != "native_json_maxpool_hardware_execplan_package"
        or manifest.get("status") != "hardware_execplan_package_validated"
        or manifest.get("source_config_sha256") != SOURCE_CONFIG_SHA256
        or manifest.get("source_config_rewritten") is not False
    ):
        raise NativeJsonMaxPoolPackageError("native MaxPool package identity differs")
    source_copy = root / "source_config" / PACKAGED_SOURCE_CONFIG_NAME
    if _sha256_file(source_copy) != SOURCE_CONFIG_SHA256:
        raise NativeJsonMaxPoolPackageError("packaged native MaxPool JSON differs")
    if _sha256_file(root / "freeze_manifest.json") != manifest.get("freeze_manifest_sha256"):
        raise NativeJsonMaxPoolPackageError("native MaxPool freeze identity differs")
    expected_files = manifest.get("files")
    if not isinstance(expected_files, list) or _output_hashes(root) != expected_files:
        raise NativeJsonMaxPoolPackageError("native MaxPool package exact file set differs")
    text_count = _validate_package_text_contract(root, manifest["text_file_contract"])
    sca = _read_json_object(root / "sca_cfg.json")
    sca_d = _read_json_object(root / "sca_cfg_D.json")
    runner = _read_json_object(root / "runner_contract.json")
    if sca.get("Repeat_Num") != 1:
        raise NativeJsonMaxPoolPackageError("native MaxPool Repeat_Num differs")
    transfer_count = _validate_immutable_tb_sca_parser_abi(root / "sca_cfg.json", sca)
    if transfer_count != manifest.get("preload_transfer_segment_count"):
        raise NativeJsonMaxPoolPackageError("native MaxPool preload count differs")
    _validate_payload_intervals(sca, root)
    if len(sca_d) != manifest.get("sca_d_transfer_segment_count"):
        raise NativeJsonMaxPoolPackageError("native MaxPool readback count differs")
    _validate_runtime_completion_barrier_contract(root, manifest, sca, runner)
    bindings = manifest.get("bitstream_bindings")
    if not isinstance(bindings, Mapping) or bindings.get("record_count") != 2:
        raise NativeJsonMaxPoolPackageError("native MaxPool bitstream binding count differs")
    for record in bindings["records"]:
        if record.get("config_sha256") != SOURCE_CONFIG_SHA256:
            raise NativeJsonMaxPoolPackageError("native MaxPool bitstream source JSON differs")
        install = record.get("install")
        if not isinstance(install, Mapping):
            raise NativeJsonMaxPoolPackageError("native MaxPool install binding is missing")
        identity = _bit_text_identity(root / str(install["path"]), 128)
        if any(identity.get(key) != install.get(key) for key in identity):
            raise NativeJsonMaxPoolPackageError("native MaxPool installed bitstream differs")
    for record in _read_json_object(root / "dump_contract.json")["semantic_regions"]:
        if _sha256_file(root / str(record["golden_path"])) != record.get("text_sha256"):
            raise NativeJsonMaxPoolPackageError("native MaxPool golden payload differs")
    if manifest.get("preloaded_golden_or_output_count") != 0:
        raise NativeJsonMaxPoolPackageError("native MaxPool golden was incorrectly preloaded")
    return {
        "status": "hardware_execplan_package_validated",
        "kind": manifest["kind"],
        "checked_file_count": len(expected_files) + 1,
        "text_file_count": text_count,
        "runtime_operator_count": manifest["runtime_operator_count"],
        "exec_128bit_line_count": manifest["exec_128bit_line_count"],
        "preload_transfer_count": len(_sca_transport_entries(sca)),
        "readback_transfer_count": len(sca_d),
        "bitstream_binding_count": bindings["record_count"],
        "bank_data_file_count": manifest["bank_data_file_count"],
        "source_config_sha256": SOURCE_CONFIG_SHA256,
        "source_config_rewritten": False,
    }


__all__ = [
    "NativeJsonMaxPoolPackageError",
    "generate_native_json_maxpool_package",
    "validate_native_json_maxpool_package",
]
