#!/usr/bin/env python3
"""Server-side preflight, result adjudication, and bounded return collection.

This helper is intentionally standard-library only because it is copied into
the server test package and must run with the server's Python 3.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA = "resnet50-gap-int32-mac-onecmd-runtime-v2"
RESULT_SCHEMA = "resnet50-gap-int32-mac-server-result-gate-v2"
RETURN_SCHEMA = "resnet50-gap-int32-mac-server-return-v2"
MANIFEST_NAME = "TEST_PACKAGE_MANIFEST.json"
EXPECTED_STAGE_READ_LINES = [8192, 8192, 4096, 2048, 1024, 512]
EXPECTED_STAGE_INPUT_BASE_WORDS = [0x0000, 0x4000, 0x8000, 0xA000, 0xB000, 0xB800]
EXPECTED_STAGE_INPUT_WIDTHS = [64, 32, 16, 8, 4, 2]
EXPECTED_STAGE_ADDRESS_DELTAS = [0x2000, 0x2, 0x2, 0x2, 0x2, 0x2]
MAX_TEXT_BYTES = 8 * 1024 * 1024
MAX_EXTRACTED_BYTES = 32 * 1024 * 1024
MAX_ZIP_BYTES = 16 * 1024 * 1024
FORBIDDEN_SUFFIXES = {
    ".fsdb",
    ".vcd",
    ".vpd",
    ".fst",
    ".wlf",
    ".shm",
    ".zip",
    ".tar",
    ".tgz",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
}
FORBIDDEN_PARTS = {
    "csrc",
    "simv.daidir",
    "work",
    "archive",
    "__pycache__",
}
RTL_SUFFIXES = {".v", ".sv", ".vh", ".svh"}


class RuntimeErrorGate(ValueError):
    """Raised when package/runtime evidence violates a fail-closed contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _safe_relative(value: str) -> PurePosixPath:
    relative = PurePosixPath(value.replace("\\", "/"))
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise RuntimeErrorGate(f"unsafe relative path: {value!r}")
    return relative


def _inside(root: Path, relative: PurePosixPath) -> Path:
    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*relative.parts).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeErrorGate(
            f"path escapes root {resolved_root}: {relative}"
        ) from exc
    return candidate


def _records(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        records[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return records


def _nonempty_line_count(path: Path) -> int:
    return sum(bool(line.strip()) for line in path.read_text(encoding="ascii").splitlines())


def _validate_128bit_text(path: Path, *, expected_lines: int | None = None) -> int:
    lines = path.read_text(encoding="ascii").splitlines()
    if expected_lines is not None and len(lines) != expected_lines:
        raise RuntimeErrorGate(
            f"{path} has {len(lines)} lines, expected {expected_lines}"
        )
    if not lines or any(len(line) != 128 or set(line) - {"0", "1"} for line in lines):
        raise RuntimeErrorGate(f"invalid 128-bit text payload: {path}")
    if path.read_bytes().replace(b"\n", b"").replace(b"0", b"").replace(b"1", b""):
        raise RuntimeErrorGate(f"payload is not LF-only binary text: {path}")
    return len(lines)


def preflight_package(package_root: Path, install_name: str) -> dict[str, Any]:
    package = package_root.resolve()
    manifest_path = package / MANIFEST_NAME
    if not package.is_dir() or not manifest_path.is_file():
        raise RuntimeErrorGate(f"missing package or manifest: {package}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        package.name != install_name
        or manifest.get("install_name") != install_name
        or manifest.get("candidate_release") is not False
        or manifest.get("evidence_level") != "E2_LOCAL_ONLY"
    ):
        raise RuntimeErrorGate("package identity or release boundary differs")
    actual = _records(package, exclude_manifest=True)
    if manifest.get("files") != actual:
        raise RuntimeErrorGate("package exact file/hash set differs from manifest")
    forbidden_rtl = [
        relative for relative in actual if Path(relative).suffix.lower() in RTL_SUFFIXES
    ]
    if forbidden_rtl:
        raise RuntimeErrorGate(f"package contains RTL files: {forbidden_rtl}")
    forbidden_archives = [
        relative
        for relative in actual
        if Path(relative).suffix.lower() in FORBIDDEN_SUFFIXES
    ]
    if forbidden_archives:
        raise RuntimeErrorGate(f"package contains nested/archive evidence: {forbidden_archives}")

    workload = package / "workload"
    sca_path = workload / "sca_cfg.json"
    sca_d_path = workload / "sca_cfg_D.json"
    sca = json.loads(sca_path.read_text(encoding="utf-8"))
    sca_d = json.loads(sca_d_path.read_text(encoding="utf-8"))
    if sca_path.read_text(encoding="utf-8") != json.dumps(
        sca, ensure_ascii=False, indent=2
    ) + "\n":
        raise RuntimeErrorGate("SCA is not canonical pretty JSON")
    if sca_d_path.read_text(encoding="utf-8") != json.dumps(
        sca_d, ensure_ascii=False, indent=2
    ) + "\n":
        raise RuntimeErrorGate("SCA_D is not canonical pretty JSON")
    if sca.get("Repeat_Num") != 6:
        raise RuntimeErrorGate("Repeat_Num must equal six Start_Comp commands")
    execplan_rel = _safe_relative(sca["ExecutionPlan"]["path"])
    prefix = PurePosixPath("install", "cfg_pkg", install_name)
    if execplan_rel.parts[: len(prefix.parts)] != prefix.parts:
        raise RuntimeErrorGate("execplan path is outside the unique namespace")
    execplan_local = workload.joinpath(*execplan_rel.parts[len(prefix.parts) :])
    if not execplan_local.is_file():
        raise RuntimeErrorGate("SCA execplan target is missing")
    if sca.get("Exec_Length") != _nonempty_line_count(execplan_local):
        raise RuntimeErrorGate("Exec_Length differs from execplan line count")
    if len(sca_d) != 16:
        raise RuntimeErrorGate("SCA_D must contain exactly 16 formal readbacks")
    for entry_name, entry in sca_d.items():
        if (
            not isinstance(entry, dict)
            or set(entry) != {"base_addr", "path", "length"}
            or entry.get("length") != 512
        ):
            raise RuntimeErrorGate(
                f"SCA_D readback must contain base_addr/path/length=512: "
                f"{entry_name}"
            )

    sca_payload_count = 0
    for entry_name, entry in [*sca.items(), *sca_d.items()]:
        if not isinstance(entry, dict) or "path" not in entry:
            continue
        relative = _safe_relative(entry["path"])
        if relative.parts[: len(prefix.parts)] != prefix.parts:
            raise RuntimeErrorGate(f"SCA path escapes namespace: {entry_name}")
        local = workload.joinpath(*relative.parts[len(prefix.parts) :])
        if entry_name in sca_d:
            if local.exists():
                raise RuntimeErrorGate("formal readback target must be fresh before run")
            continue
        if not local.is_file():
            raise RuntimeErrorGate(f"SCA payload is missing: {entry_name}")
        if local.suffix in {".txt", ".bin"}:
            _validate_128bit_text(local)
        sca_payload_count += 1
    for slice_id in range(16):
        _validate_128bit_text(
            workload / f"golden/slice{slice_id:02d}/matrix_D_128bit.txt",
            expected_lines=512,
        )
    if "rtl_patch" in package.as_posix().lower():
        raise RuntimeErrorGate("package path unexpectedly identifies an RTL patch")
    return {
        "schema": SCHEMA,
        "status": "package_preflight_passed",
        "install_name": install_name,
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "file_count_excluding_manifest": len(actual),
        "functional_rtl_file_count": 0,
        "sca_payload_count": sca_payload_count,
        "sca_d_readback_count": len(sca_d),
        "repeat_num": sca["Repeat_Num"],
        "exec_length": sca["Exec_Length"],
    }


def preflight_installed(
    package_root: Path, ndp_root: Path, install_name: str
) -> dict[str, Any]:
    package_report = preflight_package(package_root, install_name)
    root = ndp_root.resolve()
    cfg_root = root / "install" / "cfg_pkg" / install_name
    if not cfg_root.is_dir():
        raise RuntimeErrorGate(f"installed namespace is missing: {cfg_root}")
    source_records = _records(package_root.resolve() / "workload")
    installed_records = _records(cfg_root)
    if source_records != installed_records:
        raise RuntimeErrorGate("installed workload differs byte-for-byte")
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        document = json.loads((cfg_root / name).read_text(encoding="utf-8"))
        for entry in document.values():
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                continue
            target = _inside(root, _safe_relative(entry["path"]))
            if name == "sca_cfg.json" and not target.is_file():
                raise RuntimeErrorGate(f"installed SCA target is missing: {target}")
    return {
        **package_report,
        "status": "installed_preflight_passed",
        "ndp_relative_namespace": f"install/cfg_pkg/{install_name}",
        "installed_file_count": len(installed_records),
        "installed_tree_exact": True,
        "all_sca_paths_resolve_from_ndp_root": True,
    }


def observer_check(ndp_root: Path) -> dict[str, Any]:
    root = ndp_root.resolve()
    tb = root / "tb_NDP_Top_new_phy.sv"
    observer = root / "native_return_observer.svh"
    makefile = root / "Makefile.tb_NDP_Top_new_phy"
    required = [tb, observer, makefile, root / "rtl/filelists/NDP_Top_phy_filelist.f"]
    missing = [path.as_posix() for path in required if not path.is_file()]
    include_present = (
        tb.is_file()
        and '`include "native_return_observer.svh"' in tb.read_text(
            encoding="utf-8", errors="replace"
        )
    )
    make_forwards_extra = (
        makefile.is_file()
        and "$(VCS_EXTRA_OPTS)" in makefile.read_text(
            encoding="utf-8", errors="replace"
        )
    )
    observer_text = (
        observer.read_text(encoding="utf-8", errors="replace")
        if observer.is_file()
        else ""
    )
    required_observer_markers = [
        "RETURN_OBS_DEEP",
        "RETURN_OBS_ACCUM_STATE",
        "GA_ACCUM_STATE",
        "EXEC_START",
        "COMP_FINISH",
    ]
    missing_observer_markers = [
        marker for marker in required_observer_markers if marker not in observer_text
    ]
    report = {
        "schema": SCHEMA,
        "status": (
            "observer_preflight_passed"
            if (
                not missing
                and include_present
                and make_forwards_extra
                and not missing_observer_markers
            )
            else "observer_preflight_failed"
        ),
        "missing": missing,
        "tb_include_present": include_present,
        "makefile_forwards_vcs_extra_opts": make_forwards_extra,
        "required_observer_markers": required_observer_markers,
        "missing_observer_markers": missing_observer_markers,
        "functional_rtl_modified_by_package": False,
        "observer_is_preexisting_server_tb_asset": True,
        "observer_sha256": _sha256(observer) if observer.is_file() else None,
    }
    if report["status"] != "observer_preflight_passed":
        raise RuntimeErrorGate(json.dumps(report, ensure_ascii=False))
    return report


def _indexed_readbacks(sca_d: dict[str, Any]) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for key, entry in sca_d.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise RuntimeErrorGate(f"invalid SCA_D entry: {key}")
        match = re.search(r"(?:^|/)readback/slice(\d{2})/", entry["path"])
        if match is None:
            raise RuntimeErrorGate(f"SCA_D readback path lacks slice identity: {key}")
        slice_id = int(match.group(1))
        if slice_id in indexed:
            raise RuntimeErrorGate(f"duplicate SCA_D slice identity: {slice_id}")
        indexed[slice_id] = entry
    if set(indexed) != set(range(16)):
        raise RuntimeErrorGate(
            f"SCA_D slice identity set differs: {sorted(indexed)}"
        )
    return indexed


def _expected_stage_log_addresses(stage_index: int) -> tuple[list[int], list[int]]:
    if not 0 <= stage_index < 6:
        raise RuntimeErrorGate(f"invalid stage index: {stage_index}")
    base = EXPECTED_STAGE_INPUT_BASE_WORDS[stage_index]
    width = EXPECTED_STAGE_INPUT_WIDTHS[stage_index]
    pair_count = width // 2
    a_addresses: list[int] = []
    c_addresses: list[int] = []
    for block in range(256):
        if stage_index == 0:
            for pair in range(pair_count):
                address = base + block * pair_count + pair
                a_addresses.append(address)
                c_addresses.append(address + EXPECTED_STAGE_ADDRESS_DELTAS[stage_index])
            continue
        for pair in range(pair_count):
            left = base + (block * width + 2 * pair) * 2
            a_addresses.extend((left, left + 1))
            c_addresses.extend((left + 2, left + 3))
    return a_addresses, c_addresses


def _ordered_int_sha256(values: list[int]) -> str:
    payload = json.dumps(values, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _parse_request_log(path: Path) -> tuple[list[list[dict[str, int]]], dict[str, Any]]:
    segments: list[list[dict[str, int]]] = []
    current: list[dict[str, int]] | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "INFO: slice start" in line:
            current = []
            segments.append(current)
            continue
        if not line.strip() or line.lstrip().startswith("#") or "INFO:" in line:
            continue
        fields = [field.strip() for field in line.split("|")]
        if len(fields) != 8:
            continue
        if current is None:
            current = []
            segments.append(current)
        try:
            current.append(
                {
                    "time": int(fields[0]),
                    "channel": int(fields[1]),
                    "address": int(fields[2], 16),
                    "rw": int(fields[6]),
                    "occurrence": int(fields[7]),
                }
            )
        except ValueError:
            continue
    return segments, {
        "path": path.as_posix(),
        "exists": path.is_file(),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "segment_count": len(segments),
        "segment_line_counts": [len(segment) for segment in segments],
    }


def _dual_mse_gate(root: Path, evidence: Path, sim_log_text: str) -> dict[str, Any]:
    slice_reports: dict[str, Any] = {}
    all_pass = True
    any_nonzero_skew = False
    any_resume_gap = False
    start_epoch_path = evidence / "run_started_epoch.txt"
    try:
        run_started_epoch = int(start_epoch_path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        run_started_epoch = -1
    for slice_id in range(16):
        local = root / f"sim_results/local/slice{slice_id}"
        mse0_path = local / "local_mse0_req.log"
        mse3_path = local / "local_mse3_req.log"
        if not mse0_path.is_file() or not mse3_path.is_file():
            slice_reports[f"slice{slice_id:02d}"] = {
                "status": "missing",
                "mse0_exists": mse0_path.is_file(),
                "mse3_exists": mse3_path.is_file(),
            }
            all_pass = False
            continue
        mse0, mse0_identity = _parse_request_log(mse0_path)
        mse3, mse3_identity = _parse_request_log(mse3_path)
        log_creation_markers = {
            "mse0": (
                f"Created request log: sim_results/local/slice{slice_id}/"
                "local_mse0_req.log"
            )
            in sim_log_text,
            "mse3": (
                f"Created request log: sim_results/local/slice{slice_id}/"
                "local_mse3_req.log"
            )
            in sim_log_text,
        }
        log_freshness = {
            "mse0": run_started_epoch >= 0
            and int(mse0_path.stat().st_mtime) >= run_started_epoch - 1,
            "mse3": run_started_epoch >= 0
            and int(mse3_path.stat().st_mtime) >= run_started_epoch - 1,
        }
        stage_reports = []
        slice_pass = (
            len(mse0) == 6
            and len(mse3) == 6
            and all(log_creation_markers.values())
            and all(log_freshness.values())
        )
        for stage in range(6):
            left = mse0[stage] if stage < len(mse0) else []
            right = mse3[stage] if stage < len(mse3) else []
            expected = EXPECTED_STAGE_READ_LINES[stage]
            delta = EXPECTED_STAGE_ADDRESS_DELTAS[stage]
            expected_left, expected_right = _expected_stage_log_addresses(stage)
            paired = len(left) == len(right)
            address_pairing = paired and all(
                ((r["address"] - l["address"]) & ((1 << 21) - 1)) == delta
                for l, r in zip(left, right)
            )
            read_only = all(item["rw"] == 0 for item in [*left, *right])
            counts_exact = len(left) == expected and len(right) == expected
            left_addresses = [item["address"] for item in left]
            right_addresses = [item["address"] for item in right]
            exact_absolute_addresses = (
                left_addresses == expected_left and right_addresses == expected_right
            )
            continuous_occurrence = all(
                later["occurrence"] == earlier["occurrence"] + 1
                for segment in (left, right)
                for earlier, later in zip(segment, segment[1:])
            )
            channel_matches_address = all(
                item["channel"] == (item["address"] & 1)
                for item in [*left, *right]
            )
            skews = [r["time"] - l["time"] for l, r in zip(left, right)]
            nonzero_skew = any(value != 0 for value in skews)
            any_nonzero_skew = any_nonzero_skew or nonzero_skew
            combined_times = sorted(item["time"] for item in [*left, *right])
            positive_gaps = [
                later - earlier
                for earlier, later in zip(combined_times, combined_times[1:])
                if later > earlier
            ]
            resume_gap = (
                len(positive_gaps) >= 2
                and max(positive_gaps) > min(positive_gaps)
            )
            any_resume_gap = any_resume_gap or resume_gap
            stage_pass = (
                paired
                and address_pairing
                and read_only
                and counts_exact
                and exact_absolute_addresses
                and continuous_occurrence
                and channel_matches_address
            )
            slice_pass = slice_pass and stage_pass
            stage_reports.append(
                {
                    "stage": stage + 1,
                    "expected_read_lines_each": expected,
                    "mse0_read_lines": len(left),
                    "mse3_read_lines": len(right),
                    "expected_c_minus_a_address": delta,
                    "ordered_address_pairing": address_pairing,
                    "exact_absolute_address_sequence": exact_absolute_addresses,
                    "mse0_ordered_address_sha256": _ordered_int_sha256(left_addresses),
                    "mse3_ordered_address_sha256": _ordered_int_sha256(right_addresses),
                    "expected_mse0_ordered_address_sha256": _ordered_int_sha256(
                        expected_left
                    ),
                    "expected_mse3_ordered_address_sha256": _ordered_int_sha256(
                        expected_right
                    ),
                    "continuous_occurrence": continuous_occurrence,
                    "channel_matches_address_low_bit": channel_matches_address,
                    "read_only": read_only,
                    "nonzero_issue_skew_observed": nonzero_skew,
                    "resume_after_larger_gap_observed": resume_gap,
                    "max_abs_pair_skew": max((abs(value) for value in skews), default=0),
                    "status": "pass" if stage_pass else "fail",
                }
            )
        slice_reports[f"slice{slice_id:02d}"] = {
            "status": "pass" if slice_pass else "fail",
            "mse0_log": mse0_identity,
            "mse3_log": mse3_identity,
            "current_run_log_creation_markers": log_creation_markers,
            "current_run_log_mtime_after_start": log_freshness,
            "stages": stage_reports,
        }
        all_pass = all_pass and slice_pass
    return {
        "status": "pass" if all_pass else "fail",
        "rule_id": "CDA-GAP-INT32MAC-DUAL-INPUT-001",
        "all_16_slices_exact_occurrence_and_address_pairing": all_pass,
        "first_occurrence_covered": all_pass,
        "natural_nonzero_skew_observed": any_nonzero_skew,
        "natural_stall_resume_gap_observed": any_resume_gap,
        "forced_stall_injected": False,
        "run_started_epoch": run_started_epoch,
        "stale_root_local_logs_rejected": all_pass,
        "slices": slice_reports,
    }


def _formal_d_gate(root: Path, cfg_root: Path, package_root: Path) -> dict[str, Any]:
    sca_d = json.loads((cfg_root / "sca_cfg_D.json").read_text(encoding="utf-8"))
    indexed = _indexed_readbacks(sca_d)
    entries = []
    all_pass = len(indexed) == 16
    total_lines = 0
    total_mismatches = 0
    for slice_id in range(16):
        entry = indexed[slice_id]
        actual = _inside(root, _safe_relative(entry["path"]))
        golden = package_root / f"workload/golden/slice{slice_id:02d}/matrix_D_128bit.txt"
        actual_lines = []
        exact_text_format = False
        if actual.is_file():
            try:
                _validate_128bit_text(actual, expected_lines=512)
                exact_text_format = actual.stat().st_size == 512 * 129
                actual_lines = actual.read_text(encoding="ascii").splitlines()
            except (OSError, UnicodeError, RuntimeErrorGate):
                actual_lines = actual.read_text(
                    encoding="ascii", errors="replace"
                ).splitlines()
        golden_lines = golden.read_text(encoding="ascii").splitlines()
        mismatch_indices = [
            index
            for index in range(max(len(actual_lines), len(golden_lines)))
            if (actual_lines[index] if index < len(actual_lines) else None)
            != (golden_lines[index] if index < len(golden_lines) else None)
        ]
        valid_format = (
            exact_text_format
            and len(actual_lines) == 512
            and all(len(line) == 128 and not (set(line) - {"0", "1"}) for line in actual_lines)
        )
        passed = valid_format and not mismatch_indices
        all_pass = all_pass and passed
        total_lines += len(actual_lines)
        total_mismatches += len(mismatch_indices)
        entries.append(
            {
                "slice": slice_id,
                "path": entry["path"],
                "exists": actual.is_file(),
                "line_count": len(actual_lines),
                "expected_line_count": 512,
                "size_bytes": actual.stat().st_size if actual.is_file() else None,
                "expected_size_bytes": 512 * 129,
                "lf_only_exact_size": exact_text_format,
                "format_valid": valid_format,
                "mismatch_count": len(mismatch_indices),
                "first_mismatch_line": (
                    mismatch_indices[0] + 1 if mismatch_indices else None
                ),
                "actual_sha256": _sha256(actual) if actual.is_file() else None,
                "golden_sha256": _sha256(golden),
                "status": "pass" if passed else "fail",
            }
        )
    return {
        "status": "pass" if all_pass else "fail",
        "rule_id": "CDA-GAP-D-READBACK-COVERAGE-001",
        "slice_count": len(entries),
        "total_actual_lines": total_lines,
        "expected_total_lines": 16 * 512,
        "total_mismatch_lines": total_mismatches,
        "all_16x512_lines_exact_golden": all_pass,
        "slices": entries,
    }


def _simulation_log_gate(
    root: Path,
    install_name: str,
    expected_preload_count: int,
) -> tuple[dict[str, Any], str]:
    sim_log = root / f"run_{install_name}/sim_results/sim.log"
    text = (
        sim_log.read_text(encoding="utf-8", errors="replace")
        if sim_log.is_file()
        else ""
    )
    expected_sca = f"install/cfg_pkg/{install_name}/sca_cfg.json"
    expected_sca_d = f"install/cfg_pkg/{install_name}/sca_cfg_D.json"
    checks = {
        "sim_log_exists": sim_log.is_file(),
        "sca_echo_exact": text.count(f"Using SCA cfg file: {expected_sca}") == 1,
        "sca_d_echo_exact": text.count(
            f"Using SCA cfg D file: {expected_sca_d}"
        )
        == 1,
        "preload_count_exact": bool(
            re.search(
                rf"JSON config:\s*{expected_preload_count}\s+matrices loaded",
                text,
            )
        ),
        "formal_dump_count_exact": bool(
            re.search(r"JSON_D config:\s*16\s+matrices dumped", text)
        ),
        "natural_completion_marker": "Simulation completed successfully!" in text,
        "no_cannot_open": "Cannot open" not in text,
        "no_skip_matrix_readback": "skip matrix readback" not in text,
        "no_softmax_default": "sca_cfg_D_softmax.json" not in text,
    }
    passed = all(checks.values())
    return (
        {
            "status": "pass" if passed else "fail",
            "sim_log": sim_log.as_posix(),
            "expected_sca": expected_sca,
            "expected_sca_d": expected_sca_d,
            "expected_preload_count": expected_preload_count,
            **checks,
        },
        text,
    )


def _observer_gates(observer_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    text = (
        observer_path.read_text(encoding="utf-8", errors="replace")
        if observer_path.is_file()
        else ""
    )
    exec_start = len(re.findall(r"\|\s*EXEC_START\s*\|", text))
    comp_finish = len(re.findall(r"\|\s*COMP_FINISH\s*\|", text))
    stall_events = len(re.findall(r"\|\s*STALL\s*\|", text))
    ga_lines = [line for line in text.splitlines() if "| GA_ACCUM_STATE |" in line]
    parsed = []
    for line in ga_lines:
        values = {
            key: value
            for key, value in re.findall(r"([A-Za-z0-9_]+)=([^\s]+)", line)
        }
        try:
            parsed.append(
                {
                    "opcode": int(values.get("opcode", "-1"), 0),
                    "matched": int(values.get("matched", "-1"), 0),
                    "trans_init": int(values.get("trans_init", "-1"), 0),
                    "calc": int(values.get("calc", "-1"), 0),
                    "calc_reg": int(values.get("calc_reg", "-1"), 0),
                    "ob_count": int(values.get("ob_count", "-1"), 0),
                }
            )
        except ValueError:
            continue
    sample_safe = bool(parsed) and all(
        item["opcode"] == 0xE
        and item["matched"] == 1
        and item["trans_init"] == 0
        and item["calc"] == 0
        and item["calc_reg"] == 0
        and 0 <= item["ob_count"] <= 2
        for item in parsed
    )
    lifecycle = {
        "status": (
            "pass"
            if observer_path.is_file()
            and exec_start == 6
            and comp_finish == 6
            and stall_events == 0
            else "fail"
        ),
        "rule_ids": [
            "CDA-GAP-INT32MAC-STAGE-MEMORY-001",
            "CDA-GAP-INT32MAC-TREE-001",
        ],
        "observer_exists": observer_path.is_file(),
        "exec_start_count": exec_start,
        "comp_finish_count": comp_finish,
        "expected_each": 6,
        "stall_event_count": stall_events,
        "six_stage_start_finish_sequence_observed": (
            exec_start == 6 and comp_finish == 6
        ),
        "barrier_drain_and_write_visibility_proven": False,
        "claim_boundary": (
            "the observer proves six start/finish events; it does not directly "
            "sample each execplan Barrier drain or scratch-write visibility edge"
        ),
    }
    fifo = {
        "status": "sample_pass_full_cycle_pending" if sample_safe else "fail",
        "rule_id": "CDA-GAP-INT32MAC-NORMAL-FIFO-001",
        "sample_count": len(parsed),
        "sampled_accepted_inputs_safe": sample_safe,
        "count_outside_0_to_2": sum(
            not (0 <= item["ob_count"] <= 2) for item in parsed
        ),
        "count_equal_3": sum(item["ob_count"] == 3 for item in parsed),
        "nontransout_opcode14_only": bool(parsed)
        and all(item["opcode"] == 0xE for item in parsed),
        "transout_state_inactive": bool(parsed)
        and all(
            item["trans_init"] == 0
            and item["calc"] == 0
            and item["calc_reg"] == 0
            for item in parsed
        ),
        "all_cycle_occupancy_proven": False,
        "claim_boundary": (
            "the pre-existing observer samples accepted inputs; it does not "
            "prove every clk_sg cycle, so the full-cycle FIFO release gate remains open"
        ),
    }
    return lifecycle, fifo


def analyze_server_result(
    *,
    ndp_root: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_status: int,
) -> dict[str, Any]:
    root = ndp_root.resolve()
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    cfg_root = root / "install" / "cfg_pkg" / install_name
    formal_d = _formal_d_gate(root, cfg_root, package)
    package_preflight_path = evidence / "package_preflight.json"
    package_preflight = (
        json.loads(package_preflight_path.read_text(encoding="utf-8"))
        if package_preflight_path.is_file()
        else {}
    )
    sim_log_gate, sim_log_text = _simulation_log_gate(
        root,
        install_name,
        int(package_preflight.get("sca_payload_count", -1)),
    )
    dual_mse = _dual_mse_gate(root, evidence, sim_log_text)
    lifecycle, normal_fifo = _observer_gates(evidence / "return_observer.log")
    receipt_path = evidence / "stock_rtl_identity_receipt.json"
    receipt = (
        json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt_path.is_file()
        else {}
    )
    rtl_identity_pass = (
        receipt.get("functional_rtl_unchanged") is True
        and receipt.get("status") == "rtl_unchanged"
    )
    core_dynamic_pass = (
        run_status == 0
        and sim_log_gate["status"] == "pass"
        and formal_d["status"] == "pass"
        and dual_mse["status"] == "pass"
        and lifecycle["status"] == "pass"
        and normal_fifo["status"] != "fail"
        and rtl_identity_pass
    )
    report = {
        "schema": RESULT_SCHEMA,
        "status": (
            "server_core_dynamic_pass_full_cycle_and_e5_pending"
            if core_dynamic_pass
            else "server_dynamic_failure_or_incomplete"
        ),
        "install_name": install_name,
        "candidate_release": False,
        "release_gate_passed": False,
        "evidence_level": (
            "SERVER_EVIDENCE_PENDING_FULL_CYCLE_AND_E5"
            if core_dynamic_pass
            else "SERVER_EVIDENCE_FAILED_OR_INCOMPLETE"
        ),
        "run_exit_status": run_status,
        "orthogonal_adjudication": {
            "CONFIG_SEMANTICS": {
                "route": "six_stage_int32_mac_A_times_1_plus_C",
                "server_core_dynamic_pass": core_dynamic_pass,
                "original_int32_sum_transout_route_exercised": False,
            },
            "RTL_CONTROL": {
                "server_stock_functional_rtl_unchanged": rtl_identity_pass,
                "historical_B_GAP_GA_ACCUM_STATE_cleared": False,
                "claim": (
                    "this package bypasses the int32_sum transout path and "
                    "cannot clear the historical RTL blocker"
                ),
            },
        },
        "gates": {
            "simulation_loader_and_completion": sim_log_gate,
            "formal_d_readback": formal_d,
            "dual_mse_occurrence_address_pairing": dual_mse,
            "stage_barrier_lifecycle": lifecycle,
            "normal_outbuffer_fifo": normal_fifo,
            "stock_rtl_identity": {
                "status": "pass" if rtl_identity_pass else "fail",
                "functional_rtl_unchanged": rtl_identity_pass,
                "receipt_sha256": _sha256(receipt_path)
                if receipt_path.is_file()
                else None,
            },
        },
        "remaining_release_gates": [
            "normal FIFO occupancy over every clk_sg cycle",
            "forced dual-stream skew/stall/resume if natural coverage is absent",
            "independent repeated E5 server run",
        ],
    }
    return report


def _forbidden_return(relative: PurePosixPath) -> str | None:
    lower_parts = {part.lower() for part in relative.parts}
    forbidden_parts = sorted(lower_parts & FORBIDDEN_PARTS)
    if forbidden_parts:
        return f"forbidden directory: {forbidden_parts[0]}"
    if relative.suffix.lower() in FORBIDDEN_SUFFIXES:
        return f"forbidden suffix: {relative.suffix.lower()}"
    return None


def collect_return(
    *,
    ndp_root: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    output_dir: Path,
    run_status: int,
    server_command: str,
) -> dict[str, Any]:
    root = ndp_root.resolve()
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    run = run_dir.resolve()
    output = output_dir.resolve()
    return_name = f"{install_name}_return"
    staging = output / return_name
    zip_path = output / f"{return_name}.zip"
    sha_path = output / f"{return_name}.zip.sha256"
    for target in (staging, zip_path, sha_path):
        if target.exists():
            raise RuntimeErrorGate(f"return target must be fresh: {target}")
    staging.mkdir(parents=True)
    records: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    skipped: list[dict[str, Any]] = []

    def add(source: Path, relative_value: str, role: str, *, required: bool = True) -> None:
        relative = _safe_relative(relative_value)
        reason = _forbidden_return(relative)
        if reason:
            raise RuntimeErrorGate(f"{relative}: {reason}")
        if not source.is_file():
            if required:
                missing.append(
                    {"path": relative.as_posix(), "source": source.as_posix(), "role": role}
                )
            return
        size = source.stat().st_size
        if size > MAX_TEXT_BYTES:
            skipped.append(
                {
                    "path": relative.as_posix(),
                    "source": source.as_posix(),
                    "role": role,
                    "size_bytes": size,
                    "reason": "individual_file_budget_exceeded",
                }
            )
            if required:
                missing.append(
                    {"path": relative.as_posix(), "source": source.as_posix(), "role": role}
                )
            return
        destination = _inside(staging, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append(
            {
                "path": relative.as_posix(),
                "role": role,
                "size_bytes": size,
                "sha256": _sha256(destination),
            }
        )

    add(package / MANIFEST_NAME, f"package/{MANIFEST_NAME}", "package_identity")
    for name in (
        "package_preflight.json",
        "installed_preflight.json",
        "observer_preflight.json",
        "server_identity_pre_install.json",
        "server_identity_post_install.json",
        "server_identity_post_run.json",
        "server_identity_post_restore.json",
        "stock_rtl_identity_receipt.json",
        "server_command.txt",
        "run_started_epoch.txt",
        "compile_exit_status.txt",
        "sim_exit_status.txt",
        "run_exit_status.txt",
        "SERVER_RESULT_GATE.json",
    ):
        add(evidence / name, f"evidence/{name}", "run_and_identity_evidence")
    add(evidence / "return_observer.log", "logs/return_observer.log", "bounded_tb_observer")
    add(run / "sim_results/compile.log", "logs/compile.log", "compile_log")
    add(run / "sim_results/sim.log", "logs/sim.log", "simulation_log")
    cfg_root = root / "install" / "cfg_pkg" / install_name
    add(cfg_root / "sca_cfg.json", "config/sca_cfg.json", "runtime_sca")
    add(cfg_root / "sca_cfg_D.json", "config/sca_cfg_D.json", "runtime_sca_d")
    sca_d = json.loads((cfg_root / "sca_cfg_D.json").read_text(encoding="utf-8"))
    indexed_readbacks = _indexed_readbacks(sca_d)
    for slice_id in range(16):
        entry = indexed_readbacks[slice_id]
        add(
            _inside(root, _safe_relative(entry["path"])),
            f"readback/slice{slice_id:02d}/matrix_D_128bit.txt",
            "formal_d_readback",
        )
    for mse in (0, 3):
        add(
            root / f"sim_results/local/slice0/local_mse{mse}_req.log",
            f"logs/local/slice0/local_mse{mse}_req.log",
            "representative_dual_mse_raw_request_log",
            required=False,
        )

    return_manifest = {
        "schema": RETURN_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if not missing else "incomplete",
        "install_name": install_name,
        "candidate_release": False,
        "run_exit_status": run_status,
        "server_command": server_command,
        "allowlist_only": True,
        "waveforms_included": False,
        "build_tree_included": False,
        "nested_archive_included": False,
        "required_missing": missing,
        "oversize_skipped": skipped,
        "payload_file_count": len(records),
        "payload_size_bytes": sum(item["size_bytes"] for item in records),
        "files": sorted(records, key=lambda item: item["path"]),
    }
    _write_json(staging / "RETURN_MANIFEST.json", return_manifest)
    extracted_size = sum(
        path.stat().st_size for path in staging.rglob("*") if path.is_file()
    )
    if extracted_size > MAX_EXTRACTED_BYTES:
        raise RuntimeErrorGate(f"return extracted size exceeds limit: {extracted_size}")
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in staging.rglob("*") if item.is_file()):
            relative = f"{return_name}/{path.relative_to(staging).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    if zip_path.stat().st_size > MAX_ZIP_BYTES:
        raise RuntimeErrorGate(f"return ZIP exceeds limit: {zip_path.stat().st_size}")
    digest = _sha256(zip_path)
    sha_path.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    return {
        **return_manifest,
        "directory": staging.as_posix(),
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sha256_file": sha_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    package_parser = subparsers.add_parser("preflight-package")
    package_parser.add_argument("--package-root", type=Path, required=True)
    package_parser.add_argument("--install-name", required=True)
    package_parser.add_argument("--output", type=Path)

    installed_parser = subparsers.add_parser("preflight-installed")
    installed_parser.add_argument("--package-root", type=Path, required=True)
    installed_parser.add_argument("--ndp-root", type=Path, required=True)
    installed_parser.add_argument("--install-name", required=True)
    installed_parser.add_argument("--output", type=Path)

    observer_parser = subparsers.add_parser("observer-check")
    observer_parser.add_argument("--ndp-root", type=Path, required=True)
    observer_parser.add_argument("--output", type=Path)

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--ndp-root", type=Path, required=True)
    analyze_parser.add_argument("--package-root", type=Path, required=True)
    analyze_parser.add_argument("--install-name", required=True)
    analyze_parser.add_argument("--evidence-root", type=Path, required=True)
    analyze_parser.add_argument("--run-status", type=int, required=True)
    analyze_parser.add_argument("--output", type=Path, required=True)

    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--ndp-root", type=Path, required=True)
    collect_parser.add_argument("--package-root", type=Path, required=True)
    collect_parser.add_argument("--install-name", required=True)
    collect_parser.add_argument("--evidence-root", type=Path, required=True)
    collect_parser.add_argument("--run-dir", type=Path, required=True)
    collect_parser.add_argument("--output-dir", type=Path, required=True)
    collect_parser.add_argument("--run-status", type=int, required=True)
    collect_parser.add_argument("--server-command", required=True)

    args = parser.parse_args()
    try:
        if args.command == "preflight-package":
            report = preflight_package(args.package_root, args.install_name)
        elif args.command == "preflight-installed":
            report = preflight_installed(
                args.package_root, args.ndp_root, args.install_name
            )
        elif args.command == "observer-check":
            report = observer_check(args.ndp_root)
        elif args.command == "analyze":
            report = analyze_server_result(
                ndp_root=args.ndp_root,
                package_root=args.package_root,
                install_name=args.install_name,
                evidence_root=args.evidence_root,
                run_status=args.run_status,
            )
        else:
            report = collect_return(
                ndp_root=args.ndp_root,
                package_root=args.package_root,
                install_name=args.install_name,
                evidence_root=args.evidence_root,
                run_dir=args.run_dir,
                output_dir=args.output_dir,
                run_status=args.run_status,
                server_command=args.server_command,
            )
    except Exception as error:
        print(f"GAP int32_mac runtime failed: {error}", file=sys.stderr)
        return 1
    if getattr(args, "output", None):
        _write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.command == "collect" and report["required_missing"]:
        return 5
    if args.command == "analyze" and report["status"] == "server_dynamic_failure_or_incomplete":
        return 6
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
