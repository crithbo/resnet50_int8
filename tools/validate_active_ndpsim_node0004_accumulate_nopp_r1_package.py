"""Validate the node-0004 wave-0 zero-ping-pong smoke revision."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SLICE_COUNT = 28
OP_TYPE = "node0004_accumulate_wave0_nopp_r1"
GRAPH_NAME = f"{OP_TYPE}_graph"
EXPECTED_RAW_BYTES = {"A": 1024, "B": 200704, "C": 64, "D": 200704}
EXPECTED_DTYPES = {"A": "int8", "B": "uint8", "C": "int32", "D": "int32"}
FAILED_CONFIG_SHA256 = "df73611d0b3141b50a029c002c7ab0e61e8fa5a47bc0a74dcb3446be69e79c16"
FAILED_EXECPLAN_SHA256 = "d61253c090d812e7ecb22e2520c840165d880e49ac300d20a4b2058b8cac3c57"
FAILED_BITSTREAM_SHA256 = "a7296e83dee267c0ad23f8d914dd02af39f3a7ad2e732e15636d9ab033088992"


class PackageValidationError(RuntimeError):
    """The generated package violates the zero-ping-pong smoke contract."""


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


def _binary_line_count(path: Path, expected_width: int = 128) -> int:
    lines = path.read_text(encoding="ascii").splitlines()
    if not lines or any(len(line) != expected_width or set(line) - {"0", "1"} for line in lines):
        raise PackageValidationError(f"invalid {expected_width}-bit text: {path}")
    return len(lines)


def _verify_failed_revision_immutable(root: Path) -> dict[str, Any]:
    failed = root / "ndp-sim/model_execplan/output/node0004_accumulate_wave0_graph"
    paths = {
        "source_config": root / "conv_1x1_real.json",
        "active_config_alias": root / "ndp-sim/jsons/node0004_accumulate_wave0.json",
        "execplan": failed / "install/execplan.txt",
        "bitstream": failed
        / "install/cfg_pkg/op0_node0004_accumulate_wave0_bitstream_128b.bin",
    }
    expected = {
        "source_config": FAILED_CONFIG_SHA256,
        "active_config_alias": FAILED_CONFIG_SHA256,
        "execplan": FAILED_EXECPLAN_SHA256,
        "bitstream": FAILED_BITSTREAM_SHA256,
    }
    observed = {name: _sha256(path) for name, path in paths.items()}
    if observed != expected:
        raise PackageValidationError(
            f"failed revision was modified instead of preserved: {observed}"
        )
    failed_files = sorted(path for path in failed.rglob("*") if path.is_file())
    tree_digest = hashlib.sha256()
    for path in failed_files:
        relative = path.relative_to(failed).as_posix()
        tree_digest.update(relative.encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(str(path.stat().st_size).encode("ascii"))
        tree_digest.update(b"\0")
        tree_digest.update(_sha256(path).encode("ascii"))
        tree_digest.update(b"\n")
    return {
        "package_root": failed.relative_to(root).as_posix(),
        "status": "preserved_failed_deadlock_evidence",
        "critical_sha256": observed,
        "tree_snapshot": {
            "file_count": len(failed_files),
            "bytes": sum(path.stat().st_size for path in failed_files),
            "sha256_of_relative_path_size_and_file_sha256": tree_digest.hexdigest(),
        },
    }


def _verify_config(config: dict[str, Any]) -> dict[str, Any]:
    streams = config.get("stream_engine")
    groups = config.get("buffer_loop_configs")
    special = config.get("special_array")
    buffers = config.get("buffer_config")
    if not all(isinstance(value, dict) for value in (streams, groups, special, buffers)):
        raise PackageValidationError("derived config sections are missing")

    observed_streams = {
        key: (value.get("target"), value.get("mode"))
        for key, value in streams.items()
    }
    expected_streams = {
        "stream0": ("A", "read"),
        "stream1": ("B", "read"),
        "stream3": ("C", "read"),
        "stream4": ("D", "write"),
    }
    if observed_streams != expected_streams:
        raise PackageValidationError(f"stream topology differs: {observed_streams}")
    for name, stream in streams.items():
        if stream.get("ping_pong") not in (0, False):
            raise PackageValidationError(f"{name} ping_pong is enabled")
        if stream.get("pingpong_last_index") is not None:
            raise PackageValidationError(f"{name} pingpong_last_index is not null")

    if "GROUP2" in groups or {v.get("target") for v in groups.values()} != {"A", "B", "C", "D"}:
        raise PackageValidationError("B-prime buffer-loop branch still exists")
    for name in ("inport0", "inport1", "inport2"):
        inport = special.get(name)
        if not isinstance(inport, dict):
            raise PackageValidationError(f"missing {name}")
        if inport.get("pingpong_en") not in (0, False):
            raise PackageValidationError(f"{name} ping-pong is enabled")
        if inport.get("pingpong_last_index") is not None:
            raise PackageValidationError(f"{name} pingpong_last_index is not null")
        if inport.get("nbr_enable") not in (0, False):
            raise PackageValidationError(f"{name} neighbor input is enabled")
    if special.get("outport", {}).get("mode") != "col":
        raise PackageValidationError("native GEMM outport label is not col")
    for name in ("buffer0", "buffer1", "buffer2", "buffer3", "buffer4", "buffer5"):
        if buffers.get(name, {}).get("nbr_enable") not in (0, False):
            raise PackageValidationError(f"{name} neighbor producer is enabled")

    return {
        "stream_targets": observed_streams,
        "sa_pingpong_enabled_count": 0,
        "stream_pingpong_enabled_count": 0,
        "neighbor_enabled_count": 0,
        "removed_branch": "B-prime / READ_STREAM2 / GROUP2",
        "outport_label": "col",
    }


def _verify_mapping(mapping: dict[str, Any]) -> dict[str, str]:
    assignments = mapping.get("node_to_resource")
    if not isinstance(assignments, list):
        raise PackageValidationError("mapping review has no node_to_resource list")
    by_node = {
        entry["node"]: entry["resource"]
        for entry in assignments
        if isinstance(entry, dict) and "node" in entry and "resource" in entry
    }
    expected = {
        "STREAM.stream0": "READ_STREAM0",
        "STREAM.stream1": "READ_STREAM1",
        "STREAM.stream3": "READ_STREAM3",
        "STREAM.stream4": "WRITE_STREAM0",
    }
    observed = {name: by_node.get(name) for name in expected}
    if observed != expected:
        raise PackageValidationError(f"physical stream mapping differs: {observed}")
    if any(resource == "READ_STREAM2" for resource in by_node.values()):
        raise PackageValidationError("READ_STREAM2 remains assigned")
    return observed


def validate(project_root: Path, package_root: Path, data_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    package = package_root.resolve()
    data = data_root.resolve()
    if not package.is_dir() or not data.is_dir():
        raise PackageValidationError("package or same-run input directory is missing")
    if (package / "Bank_data").exists():
        raise PackageValidationError("smoke package must not contain Bank_data")

    failed_identity = _verify_failed_revision_immutable(root)
    active_config_path = root / f"ndp-sim/jsons/{OP_TYPE}.json"
    config = _read_json(active_config_path)
    topology = _verify_config(config)

    graph_path = (
        root
        / "ndp-sim/generate_python_golden/model_execplan/op_json"
        / f"{GRAPH_NAME}.json"
    )
    graph = _read_json(graph_path)
    graph_op = graph["operators"][0]
    if graph_op.get("type") != OP_TYPE or set(graph_op.get("inputs", {})) != {"A", "B", "C"}:
        raise PackageValidationError("zero-ping-pong graph topology differs")

    withbase = _read_json(package / f"{GRAPH_NAME}_withbaseaddr.json")
    op = withbase["operators"][0]
    observed_bases = {name: spec["base_addr"] for name, spec in op["inputs"].items()}
    observed_bases["D"] = op["output"]["base_addr"]
    expected_bases = {
        "A": "0x00000000",
        "B": "0x00000400",
        "C": "0x00031400",
        "D": "0x00031440",
    }
    if observed_bases != expected_bases:
        raise PackageValidationError(f"planned addresses differ: {observed_bases}")

    mapping = _read_json(package / "config/op0/mapping_review.json")
    physical_stream_mapping = _verify_mapping(mapping)
    detailed_dump = (package / "config/op0/detailed_dump.txt").read_text(encoding="utf-8")
    if len(re.findall(r"pingpong_en\s+\| value=0", detailed_dump)) != 3:
        raise PackageValidationError("encoded SA ping-pong fields are not all zero")
    if len(re.findall(r"ping_pong\s+\| value=0", detailed_dump)) != 4:
        raise PackageValidationError("encoded stream ping-pong fields are not all zero")
    if not re.search(r"mode\s+\| value=col\s+\| encoded=\['0'\]", detailed_dump):
        raise PackageValidationError("encoded GEMM outport is not native col/bit0")

    sca = _read_json(package / "sca_cfg.json")
    sca_d = _read_json(package / "sca_cfg_D.json")
    referenced_paths: list[Path] = []
    for manifest in (sca, sca_d):
        for value in manifest.values():
            if not isinstance(value, dict) or not isinstance(value.get("path"), str):
                continue
            relative = Path(value["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise PackageValidationError(f"unsafe SCA path: {relative}")
            target = package / relative
            if not target.is_file():
                raise PackageValidationError(f"missing SCA file: {target}")
            referenced_paths.append(target)
    if len(referenced_paths) != 86 + 28:
        raise PackageValidationError(
            f"expected 114 main/readback references, found {len(referenced_paths)}"
        )

    source_files = sorted(path for path in (data / "op0").rglob("*") if path.is_file())
    packaged_files = sorted(path for path in (package / "install/op0").rglob("*") if path.is_file())
    if len(source_files) != SLICE_COUNT * 12 or len(packaged_files) != len(source_files):
        raise PackageValidationError("same-run companion file coverage differs")
    source_by_rel = {path.relative_to(data / "op0"): path for path in source_files}
    packaged_by_rel = {path.relative_to(package / "install/op0"): path for path in packaged_files}
    if source_by_rel.keys() != packaged_by_rel.keys():
        raise PackageValidationError("packaged companion paths differ")
    for relative, source in source_by_rel.items():
        if _sha256(source) != _sha256(packaged_by_rel[relative]):
            raise PackageValidationError(f"packaged companion differs: {relative}")

    for slice_id in range(SLICE_COUNT):
        slice_root = package / "install/op0" / f"slice{slice_id:02d}"
        for port, expected_bytes in EXPECTED_RAW_BYTES.items():
            stem = f"matrix_{port}_linearized_128bit"
            raw = slice_root / f"{stem}.bin"
            text = slice_root / f"{stem}.txt"
            decimal = slice_root / f"{stem}_decimal_1d.txt"
            if raw.stat().st_size != expected_bytes:
                raise PackageValidationError(f"slice{slice_id:02d} {port} size differs")
            if _binary_line_count(text) != expected_bytes // 16:
                raise PackageValidationError(f"slice{slice_id:02d} {port} line count differs")
            expected_values = expected_bytes // (4 if port in {"C", "D"} else 1)
            if sum(1 for _ in decimal.open("r", encoding="ascii")) != expected_values:
                raise PackageValidationError(f"slice{slice_id:02d} {port} decimal count differs")

    execplan = package / "install/execplan.txt"
    cfg = package / f"install/cfg_pkg/op0_{OP_TYPE}_bitstream_128b.bin"
    exec_lines = _binary_line_count(execplan)
    cfg_lines = _binary_line_count(cfg)
    explained = (package / "instructions_explained.txt").read_text(encoding="utf-8")
    command_counts = {
        "Clock_Enable": len(re.findall(r"\bClock_Enable\b", explained)),
        "Load_Config": len(re.findall(r"\bLoad_Config\b", explained)),
        "Write_Reg": len(re.findall(r"\bWrite_Reg\b", explained)),
        "Start_Comp": len(re.findall(r"\bStart_Comp\b", explained)),
        "Barrier": len(re.findall(r"\bBarrier\b", explained, flags=re.IGNORECASE)),
    }
    if (
        command_counts["Clock_Enable"] != 1
        or command_counts["Load_Config"] != 1
        or command_counts["Start_Comp"] != 1
        or command_counts["Barrier"] != 0
        or command_counts["Write_Reg"] <= 0
    ):
        raise PackageValidationError(f"native command mix differs: {command_counts}")

    input_manifest_path = package / f"{OP_TYPE}_input_manifest.json"
    input_manifest = _read_json(input_manifest_path)
    serialized_manifest = json.dumps(input_manifest, ensure_ascii=False).replace("\\", "/")
    prohibited = input_manifest.get("prohibited_sources", [])
    if "ndp-sim-ref" not in prohibited or "artifacts/w5/" in serialized_manifest:
        raise PackageValidationError("input provenance boundary differs")
    if input_manifest.get("operator_type") != OP_TYPE:
        raise PackageValidationError("input manifest operator identity differs")

    report = package / f"{OP_TYPE}_validation.json"
    files = sorted(path for path in package.rglob("*") if path.is_file() and path != report)
    result = {
        "format_version": 1,
        "status": "local_zero_pingpong_structure_and_provenance_passed_server_not_yet_run",
        "package_root": package.relative_to(root).as_posix(),
        "operator": "node-0004 accumulate wave-0 zero-ping-pong revision 1",
        "scope": "single-stage smoke; no requant and no numerical pass claim",
        "active_ndpsim_commit_expected": "ec12424516ae0304228dd2321d4e604fe225e04e",
        "failed_revision_preservation": failed_identity,
        "config": {
            "path": active_config_path.relative_to(root).as_posix(),
            "sha256": _sha256(active_config_path),
            "topology": topology,
            "physical_stream_mapping": physical_stream_mapping,
        },
        "producer_closure": {
            "SA.inport0.source0": "READ_STREAM0 -> buffer0 (A)",
            "SA.inport1.source0": "READ_STREAM1 -> buffer2 (B)",
            "SA.inport2.source0": "READ_STREAM3 -> buffer4 (C)",
            "WRITE_STREAM0": "buffer5 -> D",
            "unused": ["buffer1", "buffer3", "READ_STREAM2"],
        },
        "address_plan_slice0": observed_bases,
        "command_counts": command_counts,
        "execplan": {
            "path": execplan.relative_to(package).as_posix(),
            "line_count_128bit": exec_lines,
            "sha256": _sha256(execplan),
        },
        "bitstream": {
            "path": cfg.relative_to(package).as_posix(),
            "line_count_128bit": cfg_lines,
            "sha256": _sha256(cfg),
        },
        "slice_count": SLICE_COUNT,
        "files_per_slice": 12,
        "matrix_raw_bytes_per_slice": EXPECTED_RAW_BYTES,
        "matrix_dtypes": EXPECTED_DTYPES,
        "sca_main_tensor_references": 84,
        "sca_d_readback_references": 28,
        "same_run_companion_files": len(packaged_files),
        "bank_data_present": False,
        "package_file_count_excluding_report": len(files),
        "package_bytes_excluding_report": sum(path.stat().st_size for path in files),
    }
    report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
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
            f"install_{OP_TYPE}"
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
