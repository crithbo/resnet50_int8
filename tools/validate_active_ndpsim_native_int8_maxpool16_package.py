"""Validate the active-ndp-sim native UINT8 MaxPool 16x16 server package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np


OP_TYPE = "maxpool_config_16_16_16_stride2_padding1"
GRAPH_NAME = "native_int8_maxpool16_r1_graph"
SLICE_COUNT = 28
CONFIG_SHA256 = "624d675ddde6f386474289d473d1c69559691794f3c1ea775dfc99325cc8f072"
INPUT_SHAPE = (16, 16, 16)
OUTPUT_SHAPE = (8, 8, 16)
INPUT_PREFIX_BYTES = 68
INPUT_PAYLOAD_BYTES = 4096
INPUT_SUFFIX_BYTES = 12
INPUT_ALLOCATION_BYTES = 4176
OUTPUT_BYTES = 1024


class PackageValidationError(RuntimeError):
    """The generated package violates the native INT8 MaxPool contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PackageValidationError(f"JSON root is not an object: {path}")
    return value


def _parse_addr(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return int(value.replace("_", ""), 0)
    raise PackageValidationError(f"invalid address: {value!r}")


def _decode_128bit_text(path: Path) -> bytes:
    lines = path.read_text(encoding="ascii").splitlines()
    if not lines or any(len(line) != 128 or set(line) - {"0", "1"} for line in lines):
        raise PackageValidationError(f"invalid 128-bit text: {path}")
    return b"".join(int(line, 2).to_bytes(16, byteorder="little") for line in lines)


def _decode_decimal(path: Path) -> bytes:
    try:
        values = [int(line) for line in path.read_text(encoding="ascii").splitlines()]
        return bytes(values)
    except ValueError as error:
        raise PackageValidationError(f"invalid byte decimal file: {path}") from error


def _unpack_c4hwc4(payload: bytes, shape: tuple[int, int, int]) -> np.ndarray:
    height, width, channels = shape
    if channels % 4 or len(payload) != height * width * channels:
        raise PackageValidationError("invalid C4HWC4 payload shape")
    return (
        np.frombuffer(payload, dtype=np.uint8)
        .reshape(channels // 4, height, width, 4)
        .transpose(1, 2, 0, 3)
        .reshape(height, width, channels)
        .copy()
    )


def _logical_input(slice_id: int) -> np.ndarray:
    row = np.arange(INPUT_SHAPE[0], dtype=np.uint16)[:, None, None]
    col = np.arange(INPUT_SHAPE[1], dtype=np.uint16)[None, :, None]
    channel = np.arange(INPUT_SHAPE[2], dtype=np.uint16)[None, None, :]
    return np.ascontiguousarray(
        (slice_id * 17 + row * 29 + col * 11 + channel * 7 + 3) % 256,
        dtype=np.uint8,
    )


def _maxpool(value: np.ndarray) -> np.ndarray:
    padded = np.pad(value, ((1, 1), (1, 1), (0, 0)), constant_values=0)
    windows = [
        padded[row : row + 16 : 2, col : col + 16 : 2, :]
        for row in range(3)
        for col in range(3)
    ]
    return np.ascontiguousarray(np.maximum.reduce(windows), dtype=np.uint8)


def _verify_source_config(config: dict[str, Any]) -> dict[str, Any]:
    streams = config.get("stream_engine")
    general_array = config.get("general_array")
    if not isinstance(streams, dict) or not isinstance(general_array, dict):
        raise PackageValidationError("source stream/general-array sections are missing")
    if {
        name: (stream.get("target"), stream.get("mode"))
        for name, stream in streams.items()
    } != {
        "stream0": ("A", "read"),
        "stream1": ("D", "write"),
    }:
        raise PackageValidationError("source stream topology differs")
    if any(stream.get("ping_pong") not in (0, False) for stream in streams.values()):
        raise PackageValidationError("source stream ping-pong is enabled")

    inport_config = general_array.get("inport")
    if not isinstance(inport_config, dict):
        raise PackageValidationError("GA inport section is missing")
    inports = [inport_config.get(name) for name in ("inport0", "inport1", "inport2")]
    if not all(isinstance(inport, dict) for inport in inports):
        raise PackageValidationError("GA inports are missing")
    if any(inport.get("pingpong_en") not in (0, False) for inport in inports):
        raise PackageValidationError("GA inport ping-pong is enabled")

    pe_array = general_array.get("PE_array")
    if not isinstance(pe_array, dict):
        raise PackageValidationError("GA PE array is missing")
    opcodes = {name: pe.get("alu_opcode") for name, pe in pe_array.items()}
    if len(opcodes) != 8 or set(opcodes.values()) != {"int8_max"}:
        raise PackageValidationError(f"GA PE opcodes differ: {opcodes}")
    return {
        "stream_topology": {
            name: {"target": stream["target"], "mode": stream["mode"]}
            for name, stream in streams.items()
        },
        "stream_pingpong_enabled_count": 0,
        "ga_inport_pingpong_enabled_count": 0,
        "ga_pe_count": len(opcodes),
        "ga_pe_opcodes": opcodes,
    }


def _verify_sca(package: Path) -> dict[str, Any]:
    sca = _read_json(package / "sca_cfg.json")
    sca_d = _read_json(package / "sca_cfg_D.json")
    if (
        _parse_addr(sca.get("Exec_Base")) != 0x1C00
        or sca.get("Exec_Length") != 29
        or sca.get("Repeat_Num") != 1
    ):
        raise PackageValidationError("execution plan SCA header differs")

    expected_main_keys = {
        "ExecutionPlan",
        "op0_config",
        *(f"op0_matrixA_slice{slice_id}" for slice_id in range(SLICE_COUNT)),
    }
    actual_main_keys = {key for key, value in sca.items() if isinstance(value, dict)}
    if actual_main_keys != expected_main_keys:
        raise PackageValidationError("main SCA reference set differs")
    expected_d_keys = {
        f"op0_matrixD_slice{slice_id}" for slice_id in range(SLICE_COUNT)
    }
    if set(sca_d) != expected_d_keys:
        raise PackageValidationError("SCA_D reference set differs")

    expected_config_path = (
        f"install/cfg_pkg/op0_{OP_TYPE}_bitstream_128b.bin"
    )
    if (
        sca["ExecutionPlan"].get("path") != "install/execplan.txt"
        or _parse_addr(sca["ExecutionPlan"].get("base_addr")) != 0x1C00
        or sca["op0_config"].get("path") != expected_config_path
        or _parse_addr(sca["op0_config"].get("base_addr")) != 0x1800
    ):
        raise PackageValidationError("control SCA path/address differs")

    referenced: list[Path] = []
    for manifest in (sca, sca_d):
        for entry in manifest.values():
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                continue
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise PackageValidationError(f"unsafe SCA path: {relative}")
            target = package / relative
            if not target.is_file():
                raise PackageValidationError(f"missing SCA target: {target}")
            referenced.append(target)

    for slice_id in range(SLICE_COUNT):
        slice_base = slice_id << 25
        a = sca[f"op0_matrixA_slice{slice_id}"]
        d = sca_d[f"op0_matrixD_slice{slice_id}"]
        if (
            _parse_addr(a.get("base_addr")) != slice_base
            or a.get("path")
            != f"install/op0/slice{slice_id:02d}/matrix_A_linearized_128bit.txt"
        ):
            raise PackageValidationError(f"slice{slice_id:02d} input SCA differs")
        if (
            _parse_addr(d.get("base_addr")) != slice_base + 0x1050
            or d.get("length") != OUTPUT_BYTES // 16
            or d.get("path")
            != f"install/op0/slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
        ):
            raise PackageValidationError(f"slice{slice_id:02d} readback SCA differs")

    return {
        "main_reference_count": len(actual_main_keys),
        "readback_reference_count": len(sca_d),
        "all_reference_targets_exist": True,
        "exec_base": "0x00001C00",
        "exec_length_128bit": 29,
        "config_base": "0x00001800",
        "output_base_offset_per_slice": "0x00001050",
        "output_length_128bit_per_slice": OUTPUT_BYTES // 16,
        "unique_referenced_file_count": len(set(referenced)),
    }


def _verify_slice_files(package: Path, data: Path) -> dict[str, Any]:
    packaged = package / "install/op0"
    same_run = data / "op0"
    source_files = sorted(path for path in same_run.rglob("*") if path.is_file())
    packaged_files = sorted(path for path in packaged.rglob("*") if path.is_file())
    if len(source_files) != SLICE_COUNT * 6 or len(packaged_files) != len(source_files):
        raise PackageValidationError("same-run companion file count differs")
    source_by_relative = {path.relative_to(same_run): path for path in source_files}
    packaged_by_relative = {path.relative_to(packaged): path for path in packaged_files}
    if source_by_relative.keys() != packaged_by_relative.keys():
        raise PackageValidationError("same-run companion path set differs")
    for relative, source in source_by_relative.items():
        if _sha256(source) != _sha256(packaged_by_relative[relative]):
            raise PackageValidationError(f"same-run companion differs: {relative}")

    for slice_id in range(SLICE_COUNT):
        slice_root = packaged / f"slice{slice_id:02d}"
        payloads: dict[str, bytes] = {}
        for port, expected_size in (("A", INPUT_ALLOCATION_BYTES), ("D", OUTPUT_BYTES)):
            stem = f"matrix_{port}_linearized_128bit"
            raw_path = slice_root / f"{stem}.bin"
            text_path = slice_root / f"{stem}.txt"
            decimal_path = slice_root / f"{stem}_decimal_1d.txt"
            raw = raw_path.read_bytes()
            if len(raw) != expected_size:
                raise PackageValidationError(
                    f"slice{slice_id:02d} {port} raw size differs"
                )
            if _decode_128bit_text(text_path) != raw:
                raise PackageValidationError(
                    f"slice{slice_id:02d} {port} 128-bit text differs from raw"
                )
            if _decode_decimal(decimal_path) != raw:
                raise PackageValidationError(
                    f"slice{slice_id:02d} {port} decimal differs from raw"
                )
            payloads[port] = raw

        input_raw = payloads["A"]
        if (
            input_raw[:INPUT_PREFIX_BYTES] != bytes(INPUT_PREFIX_BYTES)
            or input_raw[-INPUT_SUFFIX_BYTES:] != bytes(INPUT_SUFFIX_BYTES)
        ):
            raise PackageValidationError(f"slice{slice_id:02d} input guard differs")
        logical_input = _unpack_c4hwc4(
            input_raw[
                INPUT_PREFIX_BYTES : INPUT_PREFIX_BYTES + INPUT_PAYLOAD_BYTES
            ],
            INPUT_SHAPE,
        )
        expected_input = _logical_input(slice_id)
        if not np.array_equal(logical_input, expected_input):
            raise PackageValidationError(
                f"slice{slice_id:02d} logical input formula differs"
            )
        logical_output = _unpack_c4hwc4(payloads["D"], OUTPUT_SHAPE)
        if not np.array_equal(logical_output, _maxpool(expected_input)):
            raise PackageValidationError(
                f"slice{slice_id:02d} independent MaxPool golden differs"
            )

    return {
        "slice_count": SLICE_COUNT,
        "files_per_slice": 6,
        "same_run_file_count": len(packaged_files),
        "all_same_run_hashes_equal": True,
        "all_raw_128bit_decimal_representations_equal": True,
        "all_logical_inputs_match_formula": True,
        "all_outputs_match_independent_uint8_maxpool": True,
        "input_bytes_per_slice": INPUT_ALLOCATION_BYTES,
        "output_bytes_per_slice": OUTPUT_BYTES,
    }


def validate(project_root: Path, package_root: Path, data_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    package = package_root.resolve()
    data = data_root.resolve()
    if not package.is_dir() or not data.is_dir():
        raise PackageValidationError("package or same-run data root is missing")
    if (package / "Bank_data").exists():
        raise PackageValidationError("native package unexpectedly contains Bank_data")

    config_path = root / f"ndp-sim/jsons/{OP_TYPE}.json"
    if _sha256(config_path) != CONFIG_SHA256:
        raise PackageValidationError("Git-tracked upstream config identity differs")
    config_facts = _verify_source_config(_read_json(config_path))

    graph = _read_json(
        root
        / "ndp-sim/generate_python_golden/model_execplan/op_json"
        / f"{GRAPH_NAME}.json"
    )
    withbase = _read_json(package / f"{GRAPH_NAME}_withbaseaddr.json")
    for candidate, needs_bases in ((graph, False), (withbase, True)):
        operators = candidate.get("operators")
        if not isinstance(operators, list) or len(operators) != 1:
            raise PackageValidationError("graph must contain exactly one operator")
        operator = operators[0]
        if (
            operator.get("id") != "op0"
            or operator.get("type") != OP_TYPE
            or operator.get("used_slices") != "0b" + "1" * SLICE_COUNT
            or operator.get("inputs", {}).get("A", {}).get("shape")
            != [1, 1, INPUT_ALLOCATION_BYTES]
            or operator.get("inputs", {}).get("A", {}).get("dtype") != "uint8"
            or operator.get("output", {}).get("shape") != list(OUTPUT_SHAPE)
            or operator.get("output", {}).get("dtype") != "uint8"
        ):
            raise PackageValidationError("single-op UINT8 graph identity differs")
        if needs_bases and (
            _parse_addr(operator["inputs"]["A"].get("base_addr")) != 0
            or _parse_addr(operator["output"].get("base_addr")) != 0x1050
        ):
            raise PackageValidationError("planned graph addresses differ")

    packaged_config = _read_json(package / f"jsons/op0_{OP_TYPE}.json")
    source_config = _read_json(config_path)
    for stream_name in ("stream0", "stream1"):
        source_config["stream_engine"][stream_name]["base_addr"] = (
            packaged_config["stream_engine"][stream_name]["base_addr"]
        )
    if packaged_config != source_config:
        raise PackageValidationError(
            "planner-derived config differs beyond native stream base-address binding"
        )

    detailed = (
        package / "config/op0/detailed_dump.txt"
    ).read_text(encoding="utf-8")
    if len(re.findall(r"alu_opcode\s+\| value=int8_max\s+\| encoded=\['01011'\]", detailed)) != 8:
        raise PackageValidationError("encoded INT8_MAX opcode count/value differs")
    if len(re.findall(r"ping_pong\s+\| value=0", detailed)) != 2:
        raise PackageValidationError("encoded stream ping-pong fields differ")
    if len(re.findall(r"pingpong_en\s+\| value=0", detailed)) != 3:
        raise PackageValidationError("encoded GA inport ping-pong fields differ")

    mapping = _read_json(package / "config/op0/mapping_review.json")
    assignments = {
        entry.get("node"): entry.get("resource")
        for entry in mapping.get("node_to_resource", [])
        if isinstance(entry, dict)
    }
    expected_stream_mapping = {
        "STREAM.stream0": "READ_STREAM0",
        "STREAM.stream1": "WRITE_STREAM0",
    }
    if {
        name: assignments.get(name) for name in expected_stream_mapping
    } != expected_stream_mapping:
        raise PackageValidationError("physical stream mapping differs")

    execplan = package / "install/execplan.txt"
    bitstream = package / f"install/cfg_pkg/op0_{OP_TYPE}_bitstream_128b.bin"
    if len(_decode_128bit_text(execplan)) != 29 * 16:
        raise PackageValidationError("execplan line count differs")
    if len(_decode_128bit_text(bitstream)) != 30 * 16:
        raise PackageValidationError("bitstream line count differs")
    config_copy = package / f"config/op0/op0_{OP_TYPE}_bitstream_128b.bin"
    if _sha256(bitstream) != _sha256(config_copy):
        raise PackageValidationError("installed bitstream differs from encoder output")

    explained = (package / "instructions_explained.txt").read_text(encoding="utf-8")
    command_counts = {
        name: len(re.findall(rf"\b{name}\b", explained))
        for name in ("Clock_Enable", "Load_Config", "Write_Reg", "Start_Comp")
    }
    if command_counts != {
        "Clock_Enable": 1,
        "Load_Config": 1,
        "Write_Reg": 54,
        "Start_Comp": 1,
    }:
        raise PackageValidationError(f"native command mix differs: {command_counts}")
    if re.search(r"barrier", explained, flags=re.IGNORECASE):
        raise PackageValidationError("unexpected barrier in single-operator execplan")

    manifest = _read_json(package / "native_int8_maxpool16_input_manifest.json")
    if (
        manifest.get("forbidden_source") != "ndp-sim-ref"
        or manifest.get("source_config", {}).get("sha256") != CONFIG_SHA256
        or manifest.get("generated_matrix_file_count") != SLICE_COUNT * 6
    ):
        raise PackageValidationError("input provenance manifest differs")

    sca_facts = _verify_sca(package)
    slice_facts = _verify_slice_files(package, data)
    report_path = package / "native_int8_maxpool16_r1_validation.json"
    file_manifest_path = package / "native_int8_maxpool16_r1_files_sha256.json"
    files = sorted(
        path
        for path in package.rglob("*")
        if path.is_file() and path not in {report_path, file_manifest_path}
    )
    result = {
        "format_version": 1,
        "status": "local_native_structure_data_and_golden_passed_server_not_yet_run",
        "scope": (
            "upstream UINT8 3x3 stride-2 pad-1 MaxPool; "
            "GA INT8_MAX backpressure discriminator"
        ),
        "package_root": package.relative_to(root).as_posix(),
        "active_ndpsim_commit_expected": "ec12424516ae0304228dd2321d4e604fe225e04e",
        "source_config": {
            "path": config_path.relative_to(root).as_posix(),
            "sha256": CONFIG_SHA256,
            **config_facts,
        },
        "physical_stream_mapping": expected_stream_mapping,
        "encoded_ga_opcode": {
            "name": "int8_max",
            "bits": "01011",
            "count": 8,
        },
        "planned_addresses_slice0": {"A": "0x00000000", "D": "0x00001050"},
        "command_counts": command_counts,
        "execplan": {
            "line_count_128bit": 29,
            "sha256": _sha256(execplan),
        },
        "bitstream": {
            "line_count_128bit": 30,
            "sha256": _sha256(bitstream),
        },
        "sca": sca_facts,
        "matrix_data": slice_facts,
        "bank_data_present": False,
        "package_file_count_excluding_validation_artifacts": len(files),
        "package_bytes_excluding_validation_artifacts": sum(
            path.stat().st_size for path in files
        ),
        "complete_file_manifest": file_manifest_path.name,
        "server_plusargs_required": [
            f"+SCA_CFG=install/cfg_pkg/{GRAPH_NAME}/sca_cfg.json",
            f"+SCA_CFG_D=install/cfg_pkg/{GRAPH_NAME}/sca_cfg_D.json",
        ],
        "server_completion_claim": False,
    }
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifested_files = sorted(
        path
        for path in package.rglob("*")
        if path.is_file() and path != file_manifest_path
    )
    file_manifest = {
        "schema": "native-int8-maxpool16-package-files-sha256-v1",
        "note": "Every package file except this self-referential manifest.",
        "package_root": package.relative_to(root).as_posix(),
        "file_count_excluding_this_manifest": len(manifested_files),
        "bytes_excluding_this_manifest": sum(
            path.stat().st_size for path in manifested_files
        ),
        "files": [
            {
                "path": path.relative_to(package).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in manifested_files
        ],
    }
    file_manifest_path.write_text(
        json.dumps(file_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(f"ndp-sim/model_execplan/output/{GRAPH_NAME}"),
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(
            "ndp-sim/generate_python_golden/single_op_data/"
            "install_native_int8_maxpool16_r1"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    package = args.package_root if args.package_root.is_absolute() else root / args.package_root
    data = args.data_root if args.data_root.is_absolute() else root / args.data_root
    result = validate(root, package, data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
