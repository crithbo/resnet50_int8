from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from .gap_native_package import validate_gap_server_candidate
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "resnet50-gap-hwop0071-server-workload-v2"
PACKAGE_NAME = "gap-hwop0071-sum-v1"
GRAPH_NAME = "gap_hwop0071_sum_graph_withbaseaddr.json"
MANIFEST_NAME = "gap_package_manifest.json"
CANDIDATE_REL = Path(
    "artifacts/operator_config_validation/r5-server-candidates/"
    "gap-hwop0071-sum-v1"
)
DEFAULT_OUTPUT_REL = Path(
    "artifacts/operator_config_validation/r5-server-workloads/"
    "gap_hwop0071_sum_graph"
)
REFERENCE_SHAPE_REL = Path(
    "ndp-sim/model_execplan/output/decode_summac_fp32N_fp32N_graph"
)

EXPECTED_TOP_LEVEL = {
    "config",
    "install",
    "jsons",
    MANIFEST_NAME,
    GRAPH_NAME,
    "instructions_explained.txt",
    "sca_cfg.json",
    "sca_cfg_D.json",
}
SLICE_COMPANION_FILES = {
    "matrix_A_linearized_128bit.bin",
    "matrix_A_linearized_128bit.txt",
    "matrix_A_linearized_128bit_decimal_1d.txt",
    "matrix_D_linearized_128bit.bin",
    "matrix_D_linearized_128bit.txt",
    "matrix_D_linearized_128bit_decimal_1d.txt",
}


class GapServerWorkloadError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GapServerWorkloadError(f"cannot parse JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise GapServerWorkloadError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _relative_files(
    root: Path, *, exclude_manifest: bool = False
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        if path.is_symlink():
            raise GapServerWorkloadError(f"workload contains a symlink: {relative}")
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def _tree_sha256(files: Mapping[str, Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(files.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _decode_128bit_text(source: Path) -> tuple[list[bytes], bytes]:
    raw = source.read_bytes()
    lines = raw.splitlines()
    if not lines:
        raise GapServerWorkloadError(f"128-bit payload is empty: {source}")
    for index, line in enumerate(lines, start=1):
        if len(line) != 128 or set(line) - {ord("0"), ord("1")}:
            raise GapServerWorkloadError(
                f"invalid 128-bit payload line: {source}:{index}"
            )
    payload = b"".join(
        int(line, 2).to_bytes(16, byteorder="little") for line in lines
    )
    return lines, payload


def _install_matrix_companions(
    source: Path, destination_txt: Path, *, port: str
) -> dict[str, Any]:
    lines, payload = _decode_128bit_text(source)
    destination_txt.parent.mkdir(parents=True, exist_ok=True)
    destination_txt.write_bytes(b"\n".join(lines) + b"\n")

    destination_bin = destination_txt.with_suffix(".bin")
    destination_decimal = destination_txt.with_name(
        f"{destination_txt.stem}_decimal_1d.txt"
    )
    destination_bin.write_bytes(payload)
    if port == "A":
        values = [str(value) for value in payload]
        dtype = "uint8"
    elif port == "D":
        if len(payload) % 4:
            raise GapServerWorkloadError(
                f"INT32 D payload byte count is not divisible by 4: {source}"
            )
        values = [
            str(
                int.from_bytes(
                    payload[offset : offset + 4],
                    byteorder="little",
                    signed=True,
                )
            )
            for offset in range(0, len(payload), 4)
        ]
        dtype = "int32"
    else:
        raise GapServerWorkloadError(f"unsupported GAP matrix port: {port}")
    destination_decimal.write_text(
        "\n".join(values) + "\n", encoding="ascii", newline="\n"
    )
    return {
        "source_sha256": sha256_file(source),
        "installed_text_sha256": sha256_file(destination_txt),
        "installed_binary_sha256": sha256_file(destination_bin),
        "installed_decimal_sha256": sha256_file(destination_decimal),
        "dtype": dtype,
        "element_count": len(values),
        "line_count_128bit": len(lines),
        "line_width_bits": 128,
        "line_ending": "LF",
    }


def _copy_128bit_lf(source: Path, destination: Path) -> dict[str, Any]:
    lines, _ = _decode_128bit_text(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"\n".join(lines) + b"\n")
    return {
        "source_sha256": sha256_file(source),
        "installed_sha256": sha256_file(destination),
        "line_count": len(lines),
        "line_width_bits": 128,
        "line_ending": "LF",
    }


def _sca_references(
    workload_root: Path, sca: Mapping[str, Any]
) -> list[tuple[str, str, Path]]:
    result: list[tuple[str, str, Path]] = []
    for key, item in sca.items():
        if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
            continue
        relative = str(item["path"])
        path = workload_root / relative
        try:
            path.resolve().relative_to(workload_root.resolve())
        except ValueError as error:
            raise GapServerWorkloadError(
                f"SCA path escapes workload root: {key}: {relative}"
            ) from error
        result.append((str(key), relative, path))
    return result


def _validate_128bit_lf(path: Path) -> int:
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or b"\r" in raw:
        raise GapServerWorkloadError(f"payload is not LF-only: {path}")
    lines = raw[:-1].split(b"\n")
    if not lines:
        raise GapServerWorkloadError(f"payload is empty: {path}")
    for index, line in enumerate(lines, start=1):
        if len(line) != 128 or set(line) - {ord("0"), ord("1")}:
            raise GapServerWorkloadError(
                f"invalid installed 128-bit line: {path}:{index}"
            )
    return len(lines)


def _validate_slice_companions(workload: Path) -> int:
    slice_root = workload / "install" / "op0"
    slices = sorted(path for path in slice_root.iterdir() if path.is_dir())
    if [path.name for path in slices] != [f"slice{index:02d}" for index in range(16)]:
        raise GapServerWorkloadError("GAP workload must contain slices 00 through 15")
    for path in slices:
        names = {item.name for item in path.iterdir() if item.is_file()}
        if names != SLICE_COMPANION_FILES:
            raise GapServerWorkloadError(
                f"slice companion file set differs: {path.name}: "
                f"{sorted(names ^ SLICE_COMPANION_FILES)}"
            )
        for port in ("A", "D"):
            text_path = path / f"matrix_{port}_linearized_128bit.txt"
            binary_path = path / f"matrix_{port}_linearized_128bit.bin"
            _, decoded = _decode_128bit_text(text_path)
            if binary_path.read_bytes() != decoded:
                raise GapServerWorkloadError(
                    f"binary/text companion mismatch: {binary_path}"
                )
            decimal_path = (
                path / f"matrix_{port}_linearized_128bit_decimal_1d.txt"
            )
            actual_decimal = decimal_path.read_text(encoding="ascii").splitlines()
            if port == "A":
                expected_decimal = [str(value) for value in decoded]
            else:
                expected_decimal = [
                    str(
                        int.from_bytes(
                            decoded[offset : offset + 4],
                            byteorder="little",
                            signed=True,
                        )
                    )
                    for offset in range(0, len(decoded), 4)
                ]
            if actual_decimal != expected_decimal:
                raise GapServerWorkloadError(
                    f"decimal/binary companion mismatch: {decimal_path}"
                )
    return len(slices)


def validate_gap_server_workload(
    project_root: Path, workload_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    workload = workload_root.resolve()
    manifest_path = workload / MANIFEST_NAME
    manifest = _load(manifest_path)
    if manifest.get("schema") != SCHEMA or manifest.get("package_name") != PACKAGE_NAME:
        raise GapServerWorkloadError("GAP server workload identity differs")

    top_level = {path.name for path in workload.iterdir()}
    if top_level != EXPECTED_TOP_LEVEL:
        raise GapServerWorkloadError(
            f"top-level reference shape differs: {sorted(top_level ^ EXPECTED_TOP_LEVEL)}"
        )

    candidate = root / CANDIDATE_REL
    candidate_result = validate_gap_server_candidate(root, candidate)
    candidate_manifest = candidate / "candidate_manifest.json"
    source = manifest.get("source_candidate")
    if (
        not isinstance(source, Mapping)
        or source.get("manifest_sha256") != sha256_file(candidate_manifest)
        or source.get("payload_tree_sha256")
        != candidate_result["payload_tree_sha256"]
    ):
        raise GapServerWorkloadError("source candidate binding differs")

    actual = _relative_files(workload, exclude_manifest=True)
    if (
        manifest.get("files") != actual
        or manifest.get("file_count") != len(actual)
        or manifest.get("tree_sha256") != _tree_sha256(actual)
    ):
        raise GapServerWorkloadError("server workload tree receipt differs")

    sca = _load(workload / "sca_cfg.json")
    sca_d = _load(workload / "sca_cfg_D.json")
    references = _sca_references(workload, sca) + _sca_references(workload, sca_d)
    if len(references) != 34:
        raise GapServerWorkloadError(
            f"GAP workload must contain 34 SCA payload references, found {len(references)}"
        )
    missing = [relative for _, relative, path in references if not path.is_file()]
    if missing:
        raise GapServerWorkloadError(f"SCA payload is missing: {missing[0]}")

    line_counts = {
        relative: _validate_128bit_lf(path) for _, relative, path in references
    }
    exec_relative = str(sca.get("ExecutionPlan", {}).get("path"))
    if (
        sca.get("Exec_Length") != line_counts.get(exec_relative)
        or sca.get("Repeat_Num") != 1
    ):
        raise GapServerWorkloadError("Exec_Length/Repeat_Num differs from installed plan")
    if len([key for key in sca if key.startswith("op0_matrixA_slice")]) != 16:
        raise GapServerWorkloadError("GAP workload must preload 16 A matrices")
    if len([key for key in sca_d if key.startswith("op0_matrixD_slice")]) != 16:
        raise GapServerWorkloadError("GAP workload must read back 16 D matrices")

    slice_count = _validate_slice_companions(workload)
    forbidden = [
        path.relative_to(workload).as_posix()
        for path in workload.rglob("*")
        if (
            path.name == "Bank_data"
            or path.suffix.lower() == ".zip"
            or "overlay" in path.name.lower()
            or "runner" in path.name.lower()
            or path.name in {"evidence", "mapping_evidence"}
        )
    ]
    if forbidden:
        raise GapServerWorkloadError(
            f"forbidden non-server-folder artifact: {forbidden[0]}"
        )

    bindings = manifest.get("server_bindings")
    if (
        not isinstance(bindings, Mapping)
        or bindings.get("sca_cfg") != "sca_cfg.json"
        or bindings.get("sca_cfg_D") != "sca_cfg_D.json"
    ):
        raise GapServerWorkloadError("server SCA bindings differ")

    return {
        "valid": True,
        "file_count": len(actual),
        "tree_sha256": _tree_sha256(actual),
        "sca_reference_count": len(references),
        "execplan_line_count": line_counts[exec_relative],
        "matrix_file_count": slice_count * 6,
        "slice_count": slice_count,
        "top_level_entries": sorted(top_level),
    }


def build_gap_server_workload(
    project_root: Path, output_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise GapServerWorkloadError(f"output must be a fresh path: {output}")

    candidate = root / CANDIDATE_REL
    candidate_result = validate_gap_server_candidate(root, candidate)
    candidate_manifest_path = candidate / "candidate_manifest.json"
    candidate_manifest = _load(candidate_manifest_path)
    sca = _load(candidate / "sca_cfg.json")
    sca_d = _load(candidate / "sca_cfg_D.json")
    references = _sca_references(candidate, sca) + _sca_references(candidate, sca_d)
    if len(references) != 34:
        raise GapServerWorkloadError("source GAP candidate SCA reference count differs")

    output.mkdir(parents=True)
    shutil.copytree(candidate / "config", output / "config")
    shutil.copytree(candidate / "jsons", output / "jsons")
    shutil.copy2(
        candidate / "graph_withbaseaddr.json",
        output / GRAPH_NAME,
    )
    shutil.copy2(
        candidate / "instructions_explained.txt",
        output / "instructions_explained.txt",
    )

    normalization: dict[str, dict[str, Any]] = {}
    matrix_companions: dict[str, dict[str, Any]] = {}
    for key, relative, source in references:
        destination = output / relative
        if "matrixA" in key:
            matrix_companions[relative] = _install_matrix_companions(
                source, destination, port="A"
            )
        elif "matrixD" in key:
            matrix_companions[relative] = _install_matrix_companions(
                source, destination, port="D"
            )
        elif relative not in normalization:
            normalization[relative] = _copy_128bit_lf(source, destination)

    source_execplan_op0 = candidate / "install" / "execplan_op0.txt"
    normalization["install/execplan_op0.txt"] = _copy_128bit_lf(
        source_execplan_op0,
        output / "install" / "execplan_op0.txt",
    )
    _write_json(output / "sca_cfg.json", sca)
    _write_json(output / "sca_cfg_D.json", sca_d)

    files = _relative_files(output)
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "server_folder_ready_local_validation_only",
        "package_name": PACKAGE_NAME,
        "purpose": (
            "server-consumed GAP folder shaped like the locally generated and "
            "server-passed decode_summac_fp32N_fp32N_graph directory"
        ),
        "reference_shape": {
            "path": REFERENCE_SHAPE_REL.as_posix(),
            "usage": "structure_and_file_classes_only_no_payload_copied",
            "top_level_entries": sorted(EXPECTED_TOP_LEVEL - {MANIFEST_NAME})
            + ["<operator>_package_manifest.json"],
            "slice_companion_files": sorted(SLICE_COMPANION_FILES),
            "reference_slice_count": 28,
            "target_active_slice_count": 16,
        },
        "source_candidate": {
            "path": CANDIDATE_REL.as_posix(),
            "manifest_sha256": sha256_file(candidate_manifest_path),
            "payload_tree_sha256": candidate_result["payload_tree_sha256"],
            "candidate_status": candidate_manifest["status"],
        },
        "contents": {
            "native_ndpsim_control_and_data": True,
            "active_slice_count": 16,
            "matrix_companion_file_count": 96,
            "sca_reference_count": 34,
            "custom_runner": False,
            "overlay": False,
            "zip": False,
            "barrier": False,
            "bank_data": False,
            "diagnostic_evidence_directories": False,
        },
        "payload_normalization": {
            "policy": "mechanical_CRLF_or_LF_to_LF_without_128bit_changes",
            "records": normalization,
        },
        "matrix_companions": {
            "policy": (
                "decode each native 128-bit text word as 16 little-endian bytes; "
                "emit raw binary and typed decimal views"
            ),
            "records": matrix_companions,
        },
        "server_bindings": {
            "package_root": ".",
            "sca_cfg": "sca_cfg.json",
            "sca_cfg_D": "sca_cfg_D.json",
            "note": (
                "bind both paths explicitly when invoking the existing server "
                "testbench; this manifest does not invent a server runner"
            ),
        },
        "file_count": len(files),
        "tree_sha256": _tree_sha256(files),
        "files": files,
    }
    payload["manifest_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    _write_json(output / MANIFEST_NAME, payload)
    validate_gap_server_workload(root, output)
    return payload


__all__ = [
    "GapServerWorkloadError",
    "build_gap_server_workload",
    "validate_gap_server_workload",
]
