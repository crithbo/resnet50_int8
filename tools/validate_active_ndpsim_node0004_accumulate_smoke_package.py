"""Validate the active-ndp-sim node-0004 wave-0 smoke package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SLICE_COUNT = 28
EXPECTED_RAW_BYTES = {"A": 1024, "B": 200704, "C": 64, "D": 200704}
EXPECTED_DTYPES = {"A": "int8", "B": "uint8", "C": "int32", "D": "int32"}
SOURCE_CONFIG_SHA256 = "df73611d0b3141b50a029c002c7ab0e61e8fa5a47bc0a74dcb3446be69e79c16"


class PackageValidationError(RuntimeError):
    """The generated package does not satisfy the smoke-package contract."""


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


def validate(project_root: Path, package_root: Path, data_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    package = package_root.resolve()
    data = data_root.resolve()
    if not package.is_dir() or not data.is_dir():
        raise PackageValidationError("package or same-run input directory is missing")
    if (package / "Bank_data").exists():
        raise PackageValidationError("strict native smoke package must not contain Bank_data")

    source_config = root / "conv_1x1_real.json"
    active_config = root / "ndp-sim/jsons/node0004_accumulate_wave0.json"
    if _sha256(source_config) != SOURCE_CONFIG_SHA256 or _sha256(active_config) != SOURCE_CONFIG_SHA256:
        raise PackageValidationError("existing and active-alias configuration hashes differ")

    graph = _read_json(
        root
        / "ndp-sim/generate_python_golden/model_execplan/op_json/"
        "node0004_accumulate_wave0_graph.json"
    )
    withbase = _read_json(package / "node0004_accumulate_wave0_graph_withbaseaddr.json")
    op = withbase["operators"][0]
    observed_bases = {
        name: spec["base_addr"] for name, spec in op["inputs"].items()
    }
    observed_bases["D"] = op["output"]["base_addr"]
    expected_bases = {
        "A": "0x00000000",
        "B": "0x00000400",
        "B'": "0x00000400",
        "C": "0x00031400",
        "D": "0x00031440",
    }
    if observed_bases != expected_bases:
        raise PackageValidationError(
            f"planned wave-0 addresses differ: {observed_bases}"
        )
    if graph["operators"][0]["type"] != "node0004_accumulate_wave0":
        raise PackageValidationError("graph operator type differs")

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
        raise PackageValidationError("packaged companion paths differ from same-run data")
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
                raise PackageValidationError(
                    f"slice{slice_id:02d} matrix {port} size differs"
                )
            if _binary_line_count(text) != expected_bytes // 16:
                raise PackageValidationError(
                    f"slice{slice_id:02d} matrix {port} line count differs"
                )
            expected_values = expected_bytes // (4 if port in {"C", "D"} else 1)
            decimal_lines = sum(1 for _ in decimal.open("r", encoding="ascii"))
            if decimal_lines != expected_values:
                raise PackageValidationError(
                    f"slice{slice_id:02d} matrix {port} decimal count differs"
                )

    execplan = package / "install/execplan.txt"
    cfg = package / "install/cfg_pkg/op0_node0004_accumulate_wave0_bitstream_128b.bin"
    exec_lines = _binary_line_count(execplan)
    cfg_lines = _binary_line_count(cfg)
    if exec_lines != 69 or cfg_lines != 35:
        raise PackageValidationError(
            f"native control lengths differ: exec={exec_lines}, config={cfg_lines}"
        )

    explained = (package / "instructions_explained.txt").read_text(encoding="utf-8")
    command_counts = {
        "Clock_Enable": len(re.findall(r"\bClock_Enable\b", explained)),
        "Load_Config": len(re.findall(r"\bLoad_Config\b", explained)),
        "Write_Reg": len(re.findall(r"\bWrite_Reg\b", explained)),
        "Start_Comp": len(re.findall(r"\bStart_Comp\b", explained)),
        "Barrier": len(re.findall(r"\bBarrier\b", explained, flags=re.IGNORECASE)),
    }
    if command_counts != {
        "Clock_Enable": 1,
        "Load_Config": 1,
        "Write_Reg": 135,
        "Start_Comp": 1,
        "Barrier": 0,
    }:
        raise PackageValidationError(f"native command mix differs: {command_counts}")

    config_dump = (package / "config/op0/detailed_dump.txt").read_text(encoding="utf-8")
    for base in ("0x0", "0x400", "0x31400", "0x31440"):
        if f"value={base}" not in config_dump:
            raise PackageValidationError(f"encoded config does not contain base {base}")

    input_manifest = _read_json(package / "node0004_accumulate_wave0_input_manifest.json")
    serialized_manifest = json.dumps(input_manifest, ensure_ascii=False)
    if "ndp-sim-ref" not in input_manifest.get("prohibited_sources", []):
        raise PackageValidationError("input manifest does not declare ndp-sim-ref prohibited")
    if "artifacts/w5/" in serialized_manifest.replace("\\", "/"):
        raise PackageValidationError("input manifest unexpectedly references a W5 package")

    report = package / "node0004_accumulate_wave0_validation.json"
    files = sorted(
        path for path in package.rglob("*") if path.is_file() and path != report
    )
    result = {
        "format_version": 1,
        "status": "local_structure_and_provenance_passed_server_not_yet_run",
        "package_root": package.relative_to(root).as_posix(),
        "operator": "node-0004 accumulate wave-0",
        "scope": "single-stage smoke; no requant and no numerical pass claim",
        "active_ndpsim_commit_expected": "ec12424516ae0304228dd2321d4e604fe225e04e",
        "config_source_sha256": SOURCE_CONFIG_SHA256,
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
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path("ndp-sim/model_execplan/output/node0004_accumulate_wave0_graph"),
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(
            "ndp-sim/generate_python_golden/single_op_data/"
            "install_node0004_accumulate_wave0"
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
