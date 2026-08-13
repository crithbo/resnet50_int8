#!/usr/bin/env python3
"""Bind the observer catalog to the production compile/source closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
from pathlib import Path


def identity(path: Path) -> dict[str, object]:
    row: dict[str, object] = {"path": str(path), "exists": path.is_file()}
    if path.is_file():
        data = path.read_bytes()
        row.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    return row


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def vcs_argv(log: str) -> list[str]:
    rows = [line.strip() for line in log.splitlines() if re.match(r"^(?:\S*/)?vcs(?:\s|$)", line.strip())]
    if not rows:
        return []
    try:
        return shlex.split(rows[-1], posix=True)
    except ValueError:
        return rows[-1].split()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-root", type=Path, required=True)
    parser.add_argument("--compile-log", type=Path, required=True)
    parser.add_argument("--compile-exit", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.server_root.resolve()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    log = args.compile_log.read_text(encoding="utf-8", errors="replace") if args.compile_log.is_file() else ""
    argv = vcs_argv(log)
    compile_exit = int(args.compile_exit.read_text().strip()) if args.compile_exit.is_file() else 125
    paths = sorted({item["source_path"] for item in contract["signals"]})
    expected = {item["source_path"]: item["source_sha256"] for item in contract["signals"]}
    rows = []
    errors: list[str] = []
    for relative in paths:
        source = root / relative
        row = identity(source)
        row["relative_path"] = relative
        row["expected_sha256"] = expected[relative]
        row["identity_match"] = row.get("sha256") == expected[relative]
        rows.append(row)
        if not row["identity_match"]:
            errors.append(f"actual compiled source mismatch: {relative}")
        if source.is_file():
            destination = args.output_dir / "actual_sources" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
    buffer_source = root / "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv"
    active = re.sub(r"/\*.*?\*/", "", re.sub(r"//.*", "", buffer_source.read_text(encoding="utf-8", errors="replace")), flags=re.S) if buffer_source.is_file() else ""
    vector_driver = re.findall(r"assign\s+mse_buf_queue_bp_pre\s*=\s*(.*?);", active, flags=re.S)
    lane_drivers = re.findall(r"assign\s+mse_buf_queue_bp_pre\s*\[\s*([^]]+)\s*\]\s*=\s*(.*?);", active, flags=re.S)
    driver_complete = len(vector_driver) == 1 or len(lane_drivers) == 2
    if not driver_complete:
        errors.append("actual ACK driver set is neither one vector assignment nor two lane assignments")
    required_names = sorted({item["exact_hierarchy"].rsplit(".", 1)[-1].split("[")[0] for item in contract["signals"]})
    missing_names = []
    for name in required_names:
        if name in {"clk", "rst_n", "slice_rst"}:
            continue
        if not any(name in (root / relative).read_text(encoding="utf-8", errors="replace") for relative in paths if (root / relative).is_file()):
            missing_names.append(name)
    if missing_names:
        errors.append(f"catalog symbols absent from bound source set: {missing_names}")
    includes = [token for token in argv if token.startswith("+incdir+")]
    defines = [token for token in argv if token.startswith("+define+")]
    parameters = [token for token in argv if token.startswith("-pvalue+") or token.startswith("-parameter")]
    filelists = []
    for index, token in enumerate(argv):
        if token in {"-f", "-F"} and index + 1 < len(argv):
            filelists.append(identity(Path(argv[index + 1]) if Path(argv[index + 1]).is_absolute() else root / argv[index + 1]))
    result = {
        "schema": "node0004-observer-actual-source-identity-v1",
        "status": "COMPLETE" if compile_exit == 0 and argv and not errors else "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "compile_exit": compile_exit, "compile_cwd": str(root), "actual_vcs_argv": argv,
        "filelists": filelists, "include_tokens": includes, "define_tokens": defines,
        "parameter_tokens": parameters, "sources": rows,
        "elaborated_ack_driver_set": {
            "method": "ACTUAL_COMPILED_SOURCE_DRIVER_SCAN_BOUND_TO_SUCCESSFUL_PRODUCTION_ELABORATION",
            "vector_equations": [" ".join(item.split()) for item in vector_driver],
            "lane_equations": [{"lane": lane, "equation": " ".join(eq.split())} for lane, eq in lane_drivers],
            "exact_set_complete": driver_complete,
            "retired_buf_idx_queue_bp_pre_comparator_present": "buf_idx_queue_bp_pre" in active,
        },
        "required_catalog_symbol_names": required_names, "missing_catalog_symbol_names": missing_names,
        "errors": errors,
        "claim_boundary": "Actual compile argv/filelist/include/define/parameter and source bytes; no vendor interactive driver-cone claim.",
    }
    write(args.output, result)
    return 0 if result["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
