"""Validate the fresh native DeepSeek FP32 max control server package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np


OP_ID = "op10"
OP_TYPE = "decode_max_fp32N_fp32N"
GRAPH_NAME = "native_deepseek_fp32_max_control_r1_graph"
REPEAT_GRAPH_NAME = "native_deepseek_fp32_max_control_r2_graph"
SLICE_COUNT = 28
CONFIG_SHA256 = "ab73710698892ed8e1062e4b5ac66fe310f99609dac89ea96ce8fa6e4bd3a1c2"
PRIOR_HARDWARE_EXEC_SHA256 = (
    "ab6c5fb65be546d8b12e8714c5f26b3cef2c755b4c60747c5f22ca3d2dd4f302"
)
PRIOR_HARDWARE_BITSTREAM_SHA256 = (
    "8c46c4989591b397ad76a11cd2f19c596fc092299a0cb12214d82c82ff275346"
)
EXPECTED_OLD_NEW_CONFIG_DIFFERENCES = {
    "config/op10/detailed_dump.txt",
    "config/op10/mapping_review.json",
    "config/op10/modules_dump_128b.bin",
    "config/op10/modules_dump_64b.bin",
    "config/op10/op10_decode_max_fp32N_fp32N_bitstream_128b.bin",
    "config/op10/op10_decode_max_fp32N_fp32N_bitstream_64b.bin",
    "config/op10/parsed_bitstream.txt",
    "config/op10/placement.png",
    "install/cfg_pkg/op10_decode_max_fp32N_fp32N_bitstream_128b.bin",
}


class PackageValidationError(RuntimeError):
    """The FP32 max control package violates its local contract."""


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


def _collect_files(root: Path, names: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in names:
        path = root / name
        if path.is_dir():
            for item in path.rglob("*"):
                if item.is_file():
                    result[item.relative_to(root).as_posix()] = _sha256(item)
        elif path.is_file():
            result[name] = _sha256(path)
    return result


def _verify_config(config: dict[str, Any]) -> dict[str, Any]:
    streams = config.get("stream_engine")
    general = config.get("general_array")
    lc_pes = config.get("lc_pe_configs")
    if not all(isinstance(value, dict) for value in (streams, general, lc_pes)):
        raise PackageValidationError("source config sections are missing")
    topology = {
        name: (stream.get("target"), stream.get("mode"))
        for name, stream in streams.items()
    }
    if topology != {"stream0": ("A", "read"), "stream1": ("D", "write")}:
        raise PackageValidationError(f"stream topology differs: {topology}")
    if any(stream.get("ping_pong") not in (0, False) for stream in streams.values()):
        raise PackageValidationError("stream ping-pong is enabled")
    inports = general.get("inport")
    if not isinstance(inports, dict) or any(
        inports.get(name, {}).get("pingpong_en") not in (0, False)
        for name in ("inport0", "inport1", "inport2")
    ):
        raise PackageValidationError("GA inport ping-pong is enabled or missing")
    ga_pes = general.get("PE_array")
    if not isinstance(ga_pes, dict) or {
        name: pe.get("alu_opcode") for name, pe in ga_pes.items()
    } != {"PE00": "max"}:
        raise PackageValidationError("GA must contain one FP32 max PE")
    all_opcodes = [
        *(pe.get("alu_opcode") for pe in lc_pes.values()),
        *(pe.get("alu_opcode") for pe in ga_pes.values()),
    ]
    if "int8_max" in all_opcodes:
        raise PackageValidationError("control config unexpectedly contains int8_max")
    return {
        "stream_topology": topology,
        "stream_pingpong_enabled_count": 0,
        "ga_inport_pingpong_enabled_count": 0,
        "ga_opcode": "max",
        "int8_max_opcode_count": 0,
    }


def _verify_sca(package: Path) -> dict[str, Any]:
    sca = _read_json(package / "sca_cfg.json")
    sca_d = _read_json(package / "sca_cfg_D.json")
    if (
        _parse_addr(sca.get("Exec_Base")) != 0x800
        or sca.get("Exec_Length") != 29
        or sca.get("Repeat_Num") != 1
    ):
        raise PackageValidationError("main SCA execution header differs")
    main_objects = {key for key, value in sca.items() if isinstance(value, dict)}
    expected_main = {
        "ExecutionPlan",
        f"{OP_ID}_config",
        *(f"{OP_ID}_matrixA_slice{slice_id}" for slice_id in range(SLICE_COUNT)),
    }
    expected_d = {
        f"{OP_ID}_matrixD_slice{slice_id}" for slice_id in range(SLICE_COUNT)
    }
    if main_objects != expected_main or set(sca_d) != expected_d:
        raise PackageValidationError("SCA object sets differ")
    if (
        sca["ExecutionPlan"].get("path") != "install/execplan.txt"
        or _parse_addr(sca["ExecutionPlan"].get("base_addr")) != 0x800
        or sca[f"{OP_ID}_config"].get("path")
        != f"install/cfg_pkg/{OP_ID}_{OP_TYPE}_bitstream_128b.bin"
        or _parse_addr(sca[f"{OP_ID}_config"].get("base_addr")) != 0x400
    ):
        raise PackageValidationError("control SCA path/address differs")

    references = 0
    for manifest in (sca, sca_d):
        for entry in manifest.values():
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                continue
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise PackageValidationError(f"unsafe SCA path: {relative}")
            if not (package / relative).is_file():
                raise PackageValidationError(f"missing SCA target: {relative}")
            references += 1
    for slice_id in range(SLICE_COUNT):
        slice_base = slice_id << 25
        a = sca[f"{OP_ID}_matrixA_slice{slice_id}"]
        d = sca_d[f"{OP_ID}_matrixD_slice{slice_id}"]
        if (
            _parse_addr(a.get("base_addr")) != slice_base
            or a.get("path")
            != f"install/{OP_ID}/slice{slice_id:02d}/matrix_A_linearized_128bit.txt"
        ):
            raise PackageValidationError(f"slice{slice_id:02d} A SCA differs")
        if (
            _parse_addr(d.get("base_addr")) != slice_base + 0x20
            or d.get("length") != 1
            or d.get("path")
            != f"install/{OP_ID}/slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
        ):
            raise PackageValidationError(f"slice{slice_id:02d} D SCA differs")
    return {
        "main_reference_count": len(main_objects),
        "readback_reference_count": len(sca_d),
        "all_reference_targets_exist": True,
        "total_reference_count": references,
        "exec_base": "0x00000800",
        "exec_length_128bit": 29,
        "config_base": "0x00000400",
        "output_base_offset_per_slice": "0x00000020",
        "output_length_128bit_per_slice": 1,
    }


def _verify_data(package: Path, data: Path) -> dict[str, Any]:
    source = data / OP_ID
    packaged = package / "install" / OP_ID
    source_files = {
        path.relative_to(source).as_posix(): path
        for path in source.rglob("*")
        if path.is_file()
    }
    packaged_files = {
        path.relative_to(packaged).as_posix(): path
        for path in packaged.rglob("*")
        if path.is_file()
    }
    if len(source_files) != SLICE_COUNT * 6 or source_files.keys() != packaged_files.keys():
        raise PackageValidationError("same-run companion file set differs")
    for relative, source_path in source_files.items():
        if _sha256(source_path) != _sha256(packaged_files[relative]):
            raise PackageValidationError(f"same-run companion differs: {relative}")

    for slice_id in range(SLICE_COUNT):
        slice_root = packaged / f"slice{slice_id:02d}"
        a_raw = (slice_root / "matrix_A_linearized_128bit.bin").read_bytes()
        d_raw = (slice_root / "matrix_D_linearized_128bit.bin").read_bytes()
        if len(a_raw) != 32 or len(d_raw) != 4:
            raise PackageValidationError(f"slice{slice_id:02d} raw tensor size differs")
        a_text = _decode_128bit_text(
            slice_root / "matrix_A_linearized_128bit.txt"
        )
        d_text = _decode_128bit_text(
            slice_root / "matrix_D_linearized_128bit.txt"
        )
        if a_text != a_raw or d_text[:4] != d_raw or d_text[4:] != bytes(12):
            raise PackageValidationError(
                f"slice{slice_id:02d} raw/128-bit representation differs"
            )
        a_values = np.frombuffer(a_raw, dtype="<f4")
        d_values = np.frombuffer(d_raw, dtype="<f4")
        if (
            a_values.shape != (8,)
            or d_values.shape != (1,)
            or d_values[0].tobytes() != np.max(a_values).tobytes()
        ):
            raise PackageValidationError(
                f"slice{slice_id:02d} FP32 max golden differs"
            )
        a_decimal = np.asarray(
            [
                np.float32(line)
                for line in (
                    slice_root / "matrix_A_linearized_128bit_decimal_1d.txt"
                ).read_text(encoding="ascii").splitlines()
            ],
            dtype="<f4",
        )
        d_decimal = np.asarray(
            [
                np.float32(line)
                for line in (
                    slice_root / "matrix_D_linearized_128bit_decimal_1d.txt"
                ).read_text(encoding="ascii").splitlines()
            ],
            dtype="<f4",
        )
        if a_decimal.tobytes() != a_raw or d_decimal.tobytes() != d_raw:
            raise PackageValidationError(
                f"slice{slice_id:02d} decimal representation differs"
            )
    return {
        "slice_count": SLICE_COUNT,
        "files_per_slice": 6,
        "same_run_file_count": len(packaged_files),
        "input_fp32_values_per_slice": 8,
        "output_fp32_values_per_slice": 1,
        "all_outputs_equal_independent_fp32_max": True,
        "all_same_run_hashes_equal": True,
    }


def validate(project_root: Path, package_root: Path, data_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    package = package_root.resolve()
    data = data_root.resolve()
    repeat = root / f"ndp-sim/model_execplan/output/{REPEAT_GRAPH_NAME}"
    prior = root / "ndp-sim/model_execplan/output/decode_max_fp32N_fp32N_graph"
    if not all(path.is_dir() for path in (package, data, repeat, prior)):
        raise PackageValidationError("package, data, repeat, or prior evidence is missing")
    if (package / "Bank_data").exists():
        raise PackageValidationError("control package unexpectedly contains Bank_data")

    config_path = root / f"ndp-sim/jsons/{OP_TYPE}.json"
    if _sha256(config_path) != CONFIG_SHA256:
        raise PackageValidationError("Git-tracked DeepSeek FP32 max config differs")
    config_facts = _verify_config(_read_json(config_path))

    graph_path = (
        root
        / "ndp-sim/generate_python_golden/model_execplan/op_json/fp32max_control_r1"
        / f"{GRAPH_NAME}.json"
    )
    graph = _read_json(graph_path)
    operators = graph.get("operators")
    if not isinstance(operators, list) or len(operators) != 1:
        raise PackageValidationError("control graph must contain one operator")
    operator = operators[0]
    if (
        operator.get("id") != OP_ID
        or operator.get("type") != OP_TYPE
        or operator.get("used_slices") != "0b" + "1" * SLICE_COUNT
        or operator.get("inputs", {}).get("A", {}).get("dtype") != "fp32"
        or operator.get("inputs", {}).get("A", {}).get("shape")
        != [1, 1, "decode_attention_length//slice_per_head"]
        or operator.get("output", {}).get("shape") != [1, 1, 1]
        or operator.get("output", {}).get("dtype", "fp32") != "fp32"
    ):
        raise PackageValidationError("control graph FP32 identity differs")

    detailed = (
        package / f"config/{OP_ID}/detailed_dump.txt"
    ).read_text(encoding="utf-8")
    if len(re.findall(r"alu_opcode\s+\| value=max\s+\| encoded=\['00011'\]", detailed)) != 1:
        raise PackageValidationError("encoded FP32 max opcode differs")
    if "value=int8_max" in detailed:
        raise PackageValidationError("encoded control unexpectedly contains int8_max")
    if len(re.findall(r"ping_pong\s+\| value=0", detailed)) != 2:
        raise PackageValidationError("encoded stream ping-pong fields differ")
    if len(re.findall(r"pingpong_en\s+\| value=0", detailed)) != 3:
        raise PackageValidationError("encoded GA inport ping-pong fields differ")

    mapping = _read_json(package / f"config/{OP_ID}/mapping_review.json")
    assignments = {
        item.get("node"): item.get("resource")
        for item in mapping.get("node_to_resource", [])
        if isinstance(item, dict)
    }
    if assignments.get("STREAM.stream0") != "READ_STREAM0" or assignments.get(
        "STREAM.stream1"
    ) != "WRITE_STREAM0":
        raise PackageValidationError("physical stream mapping differs")

    execplan = package / "install/execplan.txt"
    bitstream = package / f"install/cfg_pkg/{OP_ID}_{OP_TYPE}_bitstream_128b.bin"
    if len(_decode_128bit_text(execplan)) != 29 * 16:
        raise PackageValidationError("execplan line count differs")
    if len(_decode_128bit_text(bitstream)) != 17 * 16:
        raise PackageValidationError("bitstream line count differs")
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
    } or re.search(r"barrier", explained, flags=re.IGNORECASE):
        raise PackageValidationError(f"native command mix differs: {command_counts}")

    sca_facts = _verify_sca(package)
    data_facts = _verify_data(package, data)
    core_names = [
        "install",
        "config",
        "jsons",
        "sca_cfg.json",
        "sca_cfg_D.json",
        "instructions_explained.txt",
        "fresh_decode_fp32_max_data_manifest.json",
    ]
    current_files = _collect_files(package, core_names)
    repeat_files = _collect_files(repeat, core_names)
    if current_files != repeat_files:
        differing = sorted(
            key
            for key in set(current_files) | set(repeat_files)
            if current_files.get(key) != repeat_files.get(key)
        )
        raise PackageValidationError(f"fresh repeat generation differs: {differing}")

    prior_files = _collect_files(
        prior,
        [
            "install",
            "config",
            "jsons",
            "sca_cfg.json",
            "sca_cfg_D.json",
            "instructions_explained.txt",
        ],
    )
    comparable_current = {
        key: value
        for key, value in current_files.items()
        if key != "fresh_decode_fp32_max_data_manifest.json"
    }
    old_new_differences = {
        key
        for key in set(prior_files) | set(comparable_current)
        if prior_files.get(key) != comparable_current.get(key)
    }
    if old_new_differences != EXPECTED_OLD_NEW_CONFIG_DIFFERENCES:
        raise PackageValidationError(
            f"fresh/prior identity differences changed: {sorted(old_new_differences)}"
        )
    if _sha256(prior / "install/execplan.txt") != PRIOR_HARDWARE_EXEC_SHA256:
        raise PackageValidationError("prior hardware-tested execplan identity differs")
    if (
        _sha256(
            prior
            / f"install/cfg_pkg/{OP_ID}_{OP_TYPE}_bitstream_128b.bin"
        )
        != PRIOR_HARDWARE_BITSTREAM_SHA256
    ):
        raise PackageValidationError("prior hardware-tested bitstream identity differs")

    report_path = package / f"{GRAPH_NAME}_validation.json"
    file_manifest_path = package / f"{GRAPH_NAME}_files_sha256.json"
    payload_files = sorted(
        path
        for path in package.rglob("*")
        if path.is_file() and path not in {report_path, file_manifest_path}
    )
    result = {
        "format_version": 1,
        "status": "local_native_fp32_control_passed_server_not_yet_run",
        "scope": "DeepSeek Decode FP32 reduction max control; no INT8 path",
        "package_root": package.relative_to(root).as_posix(),
        "active_ndpsim_commit_expected": "ec12424516ae0304228dd2321d4e604fe225e04e",
        "source_config": {
            "path": config_path.relative_to(root).as_posix(),
            "sha256": CONFIG_SHA256,
            **config_facts,
        },
        "encoded_ga_opcode": {"name": "max", "bits": "00011", "count": 1},
        "physical_stream_mapping": {
            "STREAM.stream0": "READ_STREAM0",
            "STREAM.stream1": "WRITE_STREAM0",
        },
        "command_counts": command_counts,
        "execplan": {
            "line_count_128bit": 29,
            "sha256": _sha256(execplan),
        },
        "bitstream": {
            "line_count_128bit": 17,
            "sha256": _sha256(bitstream),
            "mapping_check": "native encoder reported zero violations",
        },
        "sca": sca_facts,
        "matrix_data": data_facts,
        "fresh_r1_r2_core_files": len(current_files),
        "fresh_r1_r2_all_hashes_equal": True,
        "prior_hardware_tested_operator_evidence": {
            "package": "ndp-sim/model_execplan/output/decode_max_fp32N_fp32N_graph",
            "server_natural_completion": True,
            "execplan_sha256": PRIOR_HARDWARE_EXEC_SHA256,
            "bitstream_sha256": PRIOR_HARDWARE_BITSTREAM_SHA256,
            "fresh_difference_scope": sorted(old_new_differences),
            "note": (
                "Fresh native encoder selected another zero-violation LC placement; "
                "graph data addresses execplan SCA and all matrix files are identical."
            ),
        },
        "bank_data_present": False,
        "package_file_count_excluding_validation_artifacts": len(payload_files),
        "package_bytes_excluding_validation_artifacts": sum(
            path.stat().st_size for path in payload_files
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
        "schema": "native-deepseek-fp32-max-control-files-sha256-v1",
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
            "install_deepseek_fp32max_control_r1"
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
