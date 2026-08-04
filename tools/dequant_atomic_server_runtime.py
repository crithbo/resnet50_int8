#!/usr/bin/env python3
"""Fail-closed runtime for the Dequant node0077 atomic stock-RTL diagnostic."""

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

# This must precede every package-local import.  __pycache__ and .pyc are not
# manifest exceptions.
sys.dont_write_bytecode = True

try:
    import requant_node0001_server_runtime as infra
except ModuleNotFoundError:
    from tools import requant_node0001_server_runtime as infra


MANIFEST_NAME = "TEST_PACKAGE_MANIFEST.json"
RUNTIME_SCHEMA = "dequant-node0077-atomic-stockrtl-runtime-v2"
RESULT_SCHEMA = "dequant-node0077-atomic-stockrtl-result-v2"
RETURN_SCHEMA = "dequant-node0077-atomic-stockrtl-return-v2"
ACTIVE_SLICES = (0, 1)
SLICE_MASK = 0b11
PRELOAD_COUNT = 4
FORMAL_READBACK_COUNT = 2
EXPECTED_WRITE_COUNT = 8
MAX_RETURN_FILE_BYTES = 512 * 1024
MAX_RETURN_EXTRACTED_BYTES = 4 * 1024 * 1024
MAX_RETURN_ZIP_BYTES = 2 * 1024 * 1024
FORBIDDEN_RETURN_PARTS = {"build", "csrc", "simv.daidir", "waves", "wave"}
FORBIDDEN_RETURN_SUFFIXES = {
    ".zip",
    ".tar",
    ".tgz",
    ".gz",
    ".7z",
    ".vcd",
    ".fsdb",
    ".vpd",
    ".wlf",
    ".sdb",
    ".so",
    ".a",
}


class AtomicDequantRuntimeError(RuntimeError):
    """Raised when the package or a dynamic evidence gate differs."""


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
    result = PurePosixPath(value)
    if (
        result.is_absolute()
        or not result.parts
        or any(part in {"", ".", ".."} for part in result.parts)
    ):
        raise AtomicDequantRuntimeError(f"unsafe relative path: {value}")
    return result


def _inside(root: Path, value: str) -> Path:
    base = root.resolve()
    relative = _safe_relative(value)
    target = base.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise AtomicDequantRuntimeError(f"path escapes root: {value}") from exc
    return target


def _records(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return result


def _validate_128(path: Path, lines: int) -> list[str]:
    raw = path.read_bytes()
    if b"\r" in raw:
        raise AtomicDequantRuntimeError(f"128-bit text contains CR: {path}")
    try:
        values = raw.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise AtomicDequantRuntimeError(f"128-bit text is not ASCII: {path}") from exc
    if (
        len(values) != lines
        or any(len(item) != 128 or set(item) - {"0", "1"} for item in values)
        or raw != ("\n".join(values) + "\n").encode("ascii")
    ):
        raise AtomicDequantRuntimeError(f"128-bit text ABI differs: {path}")
    return values


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AtomicDequantRuntimeError(f"JSON root is not an object: {path}")
    return value


def _payload_local(package: Path, install_name: str, runtime_path: str) -> Path:
    prefix = f"../install/cfg_pkg/{install_name}/"
    if not runtime_path.startswith(prefix):
        raise AtomicDequantRuntimeError("runtime payload escapes unique namespace")
    return _inside(package / "workload/runtime", runtime_path[len(prefix) :])


def preflight_package(package_root: Path, install_name: str) -> dict[str, Any]:
    package = package_root.resolve()
    manifest = _load(package / MANIFEST_NAME)
    if manifest.get("install_name") != install_name:
        raise AtomicDequantRuntimeError("install identity differs")
    if manifest.get("files") != _records(package, exclude_manifest=True):
        raise AtomicDequantRuntimeError("package payload differs from manifest exact set")
    if any(name.startswith("rtl/") or "/rtl/" in name for name in manifest["files"]):
        raise AtomicDequantRuntimeError("functional RTL payload is forbidden")
    for name in manifest["files"]:
        lowered = name.lower()
        if "__pycache__" in lowered or lowered.endswith((".pyc", ".pyo")):
            raise AtomicDequantRuntimeError("Python bytecode payload is forbidden")
    if (
        manifest.get("candidate_release") is not False
        or manifest.get("counts_as_node0077_e4") is not False
        or manifest.get("counts_as_node0077_e5") is not False
    ):
        raise AtomicDequantRuntimeError("diagnostic claim boundary differs")

    runtime = package / "workload/runtime"
    sca_path = runtime / "sca_cfg.json"
    sca_d_path = runtime / "sca_cfg_D.json"
    sca = _load(sca_path)
    sca_d = _load(sca_d_path)
    for path, value in ((sca_path, sca), (sca_d_path, sca_d)):
        if path.read_text(encoding="utf-8") != (
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        ):
            raise AtomicDequantRuntimeError(f"SCA is not pretty LF JSON: {path}")
    expected_sca = {
        "Exec_Base",
        "Exec_Length",
        "Repeat_Num",
        "ExecutionPlan",
        "op0_matrixA_slice0",
        "op0_matrixA_slice1",
        "op0_config",
    }
    if set(sca) != expected_sca or sca.get("Repeat_Num") != 1:
        raise AtomicDequantRuntimeError("atomic SCA exact set or Repeat_Num differs")
    exec_lines = int(sca["Exec_Length"])
    _validate_128(
        _payload_local(package, install_name, sca["ExecutionPlan"]["path"]),
        exec_lines,
    )
    for slice_id in ACTIVE_SLICES:
        entry = sca[f"op0_matrixA_slice{slice_id}"]
        expected_base = slice_id << 25
        if int(entry["base_addr"], 16) != expected_base:
            raise AtomicDequantRuntimeError(f"slice{slice_id} A base differs")
        _validate_128(_payload_local(package, install_name, entry["path"]), 1)
        _validate_128(package / f"golden/slice{slice_id:02d}_128b.txt", 4)
    if int(sca["op0_config"]["base_addr"], 16) != 0x400:
        raise AtomicDequantRuntimeError("config base differs")
    config_path = _payload_local(package, install_name, sca["op0_config"]["path"])
    bitstream_lines = len(config_path.read_text(encoding="ascii").splitlines())
    _validate_128(config_path, bitstream_lines)

    expected_d = {
        "op0_matrixD_slice0": "0x00000010",
        "op0_matrixD_slice1": "0x02000010",
    }
    if set(sca_d) != set(expected_d):
        raise AtomicDequantRuntimeError("SCA_D exact set differs")
    for name, address in expected_d.items():
        if sca_d[name] != {
            "base_addr": address,
            "path": f"sim_results/formal_readback/{name}.txt",
            "length": 4,
        }:
            raise AtomicDequantRuntimeError(f"SCA_D entry differs: {name}")

    lifecycle = _load(package / "validation/lifecycle_contract.json")
    writes = _load(package / "validation/expected_mse4_writes.json")
    config = _load(package / "validation/config.json")
    address_domains = _load(package / "validation/address_domain_contract.json")
    if (
        lifecycle.get("active_slices") != [0, 1]
        or lifecycle.get("repeat_num") != 1
        or lifecycle.get("formal_d_entry_count") != 2
        or writes.get("total_expected_accepted_write_count") != 8
        or writes.get("expected_count_per_slice") != 4
    ):
        raise AtomicDequantRuntimeError("frozen lifecycle/write contract differs")
    group2_row = (
        config.get("buffer_loop_configs", {})
        .get("GROUP2", {})
        .get("ROW_LC", {})
    )
    if (
        group2_row.get("end") != 4
        or group2_row.get("start") != 0
        or group2_row.get("stride") != 1
        or group2_row.get("last_index") != 3
    ):
        raise AtomicDequantRuntimeError(
            "corrected GROUP2.ROW_LC four-row D supply differs"
        )
    if (
        address_domains.get("linear_expected_field") != "word_address_128b"
        or address_domains.get("linear_observed_field") != "linear_addr"
        or address_domains.get("post_remap_observed_field") != "post_remap_addr"
        or address_domains.get("direct_cross_domain_comparison_forbidden") is not True
    ):
        raise AtomicDequantRuntimeError("address-domain contract differs")
    tail = package / "tb_probe/requant_mse4_guard_observer_tail.svh"
    text = tail.read_text(encoding="utf-8")
    active_text = "\n".join(
        line.split("//", 1)[0]
        for line in text.splitlines()
        if not line.lstrip().startswith("//")
    ).lower()
    for forbidden in ("force ", "deposit", "release ", "<="):
        if forbidden in active_text:
            raise AtomicDequantRuntimeError(f"observer contains driver token: {forbidden}")
    if '$test$plusargs("DEQUANT_ATOMIC_PROBE")' not in text:
        raise AtomicDequantRuntimeError("observer is not independently plusarg gated")
    for token in (
        "transfer_addr_nooff",
        "linear_addr=",
        "post_remap_addr=",
        "accepted_write_count=",
        "outstanding_addr_count=",
        "outstanding_data_count=",
    ):
        if token not in text:
            raise AtomicDequantRuntimeError(
                f"observer evidence token is missing: {token}"
            )
    try:
        xmr_elaboration_gate = infra.validate_observer_xmr_elaboration(text)
    except infra.RequantRuntimeError as exc:
        raise AtomicDequantRuntimeError(str(exc)) from exc
    return {
        "schema": RUNTIME_SCHEMA,
        "status": "package_preflight_passed",
        "candidate_release": False,
        "counts_as_node0077_e4": False,
        "counts_as_node0077_e5": False,
        "active_slices": [0, 1],
        "stage_count": 1,
        "repeat_num": 1,
        "preload_count": PRELOAD_COUNT,
        "formal_readback_count": FORMAL_READBACK_COUNT,
        "expected_mse4_write_count": EXPECTED_WRITE_COUNT,
        "execplan_128b_line_count": exec_lines,
        "bitstream_128b_line_count": bitstream_lines,
        "functional_rtl_file_count": 0,
        "observer_xmr_elaboration_gate": xmr_elaboration_gate,
    }


def preflight_installed(
    package_root: Path, ndp_root: Path, install_name: str
) -> dict[str, Any]:
    report = preflight_package(package_root, install_name)
    source = package_root.resolve() / "workload/runtime"
    installed = ndp_root.resolve() / "install/cfg_pkg" / install_name
    if not installed.is_dir() or _records(installed) != _records(source):
        raise AtomicDequantRuntimeError("installed namespace differs byte-for-byte")
    return {**report, "status": "installed_preflight_passed"}


def _simulation_gate(run_dir: Path, install_name: str, run_status: int) -> dict[str, Any]:
    path = run_dir.resolve() / "sim_results/sim.log"
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    markers = {
        "sca": f"../install/cfg_pkg/{install_name}/sca_cfg.json",
        "sca_d": f"../install/cfg_pkg/{install_name}/sca_cfg_D.json",
        "preload": f"JSON config: {PRELOAD_COUNT} matrices loaded",
        "readback": f"JSON_D config: {FORMAL_READBACK_COUNT} matrices dumped",
        "success": "Simulation completed successfully!",
    }
    found = {name: marker in text for name, marker in markers.items()}
    forbidden = [
        marker
        for marker in (
            "Cannot open",
            "skip matrix readback",
            "SIMULATION TIMEOUT",
            "$fatal",
            "Error-[",
        )
        if marker in text
    ]
    passed = (
        path.is_file()
        and run_status == 0
        and all(found.values())
        and text.count("INFO: slice start") == 1
        and text.count("INFO: slice completed after") == 1
        and not forbidden
    )
    return {
        "status": "pass" if passed else "fail",
        "run_exit_status": run_status,
        "required_markers": found,
        "start_count": text.count("INFO: slice start"),
        "completion_count": text.count("INFO: slice completed after"),
        "forbidden_markers": forbidden,
        "sim_log_sha256": _sha256(path) if path.is_file() else None,
    }


def _event_groups(run_dir: Path, event: str) -> list[dict[str, Any]]:
    groups: dict[int, set[int]] = {}
    pattern = re.compile(rf"^\s*(\d+)\s+\|\s+{re.escape(event)}\s+\|")
    for slice_id in ACTIVE_SLICES:
        path = run_dir.resolve() / f"sim_results/sem_events/slice{slice_id}/sem_events.log"
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = pattern.match(line)
            if match:
                groups.setdefault(int(match.group(1)), set()).add(slice_id)
    return [
        {"time": time, "slices": sorted(slices), "mask": sum(1 << item for item in slices)}
        for time, slices in sorted(groups.items())
    ]


def _lifecycle_gate(run_dir: Path) -> dict[str, Any]:
    starts = _event_groups(run_dir, "Start Comp")
    finishes = _event_groups(run_dir, "Comp Finish")
    start_times = {
        slice_id: [
            group["time"]
            for group in starts
            if slice_id in group["slices"]
        ]
        for slice_id in ACTIVE_SLICES
    }
    finish_times = {
        slice_id: [
            group["time"]
            for group in finishes
            if slice_id in group["slices"]
        ]
        for slice_id in ACTIVE_SLICES
    }
    per_slice = {
        str(slice_id): {
            "start_times": start_times[slice_id],
            "finish_times": finish_times[slice_id],
            "natural_order": (
                len(start_times[slice_id]) == 1
                and len(finish_times[slice_id]) == 1
                and finish_times[slice_id][0] > start_times[slice_id][0]
            ),
        }
        for slice_id in ACTIVE_SLICES
    }
    passed = all(item["natural_order"] for item in per_slice.values())
    return {
        "status": "pass" if passed else "fail",
        "start_groups": starts,
        "finish_groups": finishes,
        "per_slice": per_slice,
        "same_cycle_completion_not_required": True,
        "both_slices_naturally_completed": passed,
    }


def _observer_gate(run_dir: Path, package_root: Path) -> dict[str, Any]:
    expected = _load(
        package_root.resolve() / "validation/expected_mse4_writes.json"
    )["writes"]
    pattern = re.compile(
        r"MSE4_WRITE\s+\|.*?cycle=(?P<cycle>\d+).*?"
        r"slice=(?P<slice>\d+).*?local_stage=(?P<stage>\d+).*?"
        r"role=\s*dequantize.*?ch=(?P<channel>\d+).*?"
        r"accepted=1\s+valid=1\s+ready=1\s+"
        r"strobe=(?P<strobe>0x[0-9a-fA-F]+)\s+"
        r"transfer_addr=(?P<transfer>0x[0-9a-fA-F]+)\s+"
        r"linear_addr=(?P<linear>0x[0-9a-fA-F]+)\s+"
        r"post_remap_addr=(?P<post>0x[0-9a-fA-F]+)\s+"
        r"data=(?P<data>0x[0-9a-fA-F]{32})"
    )
    finish_pattern = re.compile(
        r"STAGE_FINISH\s+\|.*?cycle=(?P<cycle>\d+).*?"
        r"slice=(?P<slice>\d+).*?local_stage=(?P<stage>\d+).*?"
        r"accepted_req_count=(?P<requests>\d+)\s+"
        r"accepted_wdata_count=(?P<wdata>\d+)\s+"
        r"accepted_write_count=(?P<writes>\d+)\s+"
        r"outstanding_addr_count=(?P<addresses>\d+)\s+"
        r"outstanding_data_count=(?P<data>\d+)"
    )
    actual: list[dict[str, Any]] = []
    finishes: dict[int, dict[str, Any]] = {}
    errors: list[str] = []
    for slice_id in ACTIVE_SLICES:
        path = (
            run_dir.resolve()
            / f"sim_results/dequant_atomic_probe/slice{slice_id:02d}.log"
        )
        if not path.is_file():
            errors.append(f"missing observer log slice{slice_id}")
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "PROBE_ERROR" in line:
                errors.append(line[-300:])
            match = pattern.search(line)
            if match:
                actual.append(
                    {
                        "cycle": int(match.group("cycle")),
                        "slice_id": int(match.group("slice")),
                        "stage_index": int(match.group("stage")),
                        "channel": int(match.group("channel")),
                        "strobe": match.group("strobe").lower(),
                        "transfer_addr": hex(int(match.group("transfer"), 0)),
                        "linear_addr": hex(int(match.group("linear"), 0)),
                        "post_remap_addr": hex(int(match.group("post"), 0)),
                        "word_address_128b": hex(int(match.group("linear"), 0)),
                        "data": match.group("data").lower(),
                    }
                )
            finish = finish_pattern.search(line)
            if finish:
                parsed = {
                    "cycle": int(finish.group("cycle")),
                    "slice_id": int(finish.group("slice")),
                    "stage_index": int(finish.group("stage")),
                    "accepted_req_count": int(finish.group("requests")),
                    "accepted_wdata_count": int(finish.group("wdata")),
                    "accepted_write_count": int(finish.group("writes")),
                    "outstanding_addr_count": int(finish.group("addresses")),
                    "outstanding_data_count": int(finish.group("data")),
                }
                if parsed["slice_id"] in finishes:
                    errors.append(
                        f"duplicate STAGE_FINISH slice{parsed['slice_id']}"
                    )
                finishes[parsed["slice_id"]] = parsed
    wanted = [
        {
            "slice_id": int(item["slice_id"]),
            "stage_index": int(item["stage_index"]),
            "strobe": str(item["strobe"]).lower(),
            "word_address_128b": hex(int(item["word_address_128b"], 0)),
            "data": str(item["data"]).lower(),
        }
        for item in expected
    ]
    observed = [
        {key: item[key] for key in wanted[0]}
        for item in actual
    ]
    mismatches: list[dict[str, Any]] = []
    for slice_id in ACTIVE_SLICES:
        wanted_slice = [item for item in wanted if item["slice_id"] == slice_id]
        actual_slice = [item for item in observed if item["slice_id"] == slice_id]
        for beat in range(max(len(wanted_slice), len(actual_slice))):
            expected_item = wanted_slice[beat] if beat < len(wanted_slice) else None
            actual_item = actual_slice[beat] if beat < len(actual_slice) else None
            if expected_item != actual_item:
                mismatches.append(
                    {
                        "slice_id": slice_id,
                        "beat_index": beat,
                        "expected": expected_item,
                        "actual": actual_item,
                    }
                )
    unique = len(
        {(item["slice_id"], item["word_address_128b"]) for item in observed}
    )
    per_slice_write_count = {
        str(slice_id): sum(
            1 for item in observed if item["slice_id"] == slice_id
        )
        for slice_id in ACTIVE_SLICES
    }
    finish_per_slice: dict[str, dict[str, Any]] = {}
    for slice_id in ACTIVE_SLICES:
        item = finishes.get(slice_id)
        valid = bool(
            item is not None
            and item["stage_index"] == 0
            and item["accepted_req_count"] == 4
            and item["accepted_wdata_count"] == 4
            and item["accepted_write_count"] == 4
            and item["outstanding_addr_count"] == 0
            and item["outstanding_data_count"] == 0
        )
        finish_per_slice[str(slice_id)] = {
            "status": "pass" if valid else "fail",
            "expected_accepted_count": 4,
            "observed": item,
        }
    finish_pass = all(
        item["status"] == "pass" for item in finish_per_slice.values()
    )
    passed = (
        not errors
        and len(observed) == EXPECTED_WRITE_COUNT
        and unique == EXPECTED_WRITE_COUNT
        and all(value == 4 for value in per_slice_write_count.values())
        and finish_pass
        and not mismatches
    )
    return {
        "status": "pass" if passed else "fail",
        "evidence_kind": "same_clock_read_only_accepted_mse4_write_observer",
        "address_domain": {
            "expected_and_compared": "linear/pre-remap word address",
            "expected_field": "word_address_128b",
            "observed_field": "linear_addr",
            "post_remap_field": "post_remap_addr",
            "post_remap_compared_to_linear": False,
        },
        "expected_write_count": EXPECTED_WRITE_COUNT,
        "actual_write_count": len(observed),
        "per_slice_write_count": per_slice_write_count,
        "unique_slice_address_count": unique,
        "order_address_strobe_data_bit_exact": not mismatches,
        "finish_drain_status": "pass" if finish_pass else "fail",
        "finish_per_slice": finish_per_slice,
        "observed_address_domains": [
            {
                key: item[key]
                for key in (
                    "cycle",
                    "slice_id",
                    "channel",
                    "transfer_addr",
                    "linear_addr",
                    "post_remap_addr",
                )
            }
            for item in actual
        ],
        "errors": errors,
        "first_mismatches": mismatches[:8],
    }


def _formal_gate(run_dir: Path, package_root: Path) -> dict[str, Any]:
    package = package_root.resolve()
    sca_d = _load(package / "workload/runtime/sca_cfg_D.json")
    entries: list[dict[str, Any]] = []
    for slice_id in ACTIVE_SLICES:
        name = f"op0_matrixD_slice{slice_id}"
        item = sca_d[name]
        actual = _inside(run_dir.resolve(), item["path"])
        golden = package / f"golden/slice{slice_id:02d}_128b.txt"
        valid = False
        line_count: int | None = None
        unknown_or_invalid_line_count: int | None = None
        all_lines_non_x = False
        if actual.is_file():
            raw_lines = actual.read_text(
                encoding="ascii", errors="replace"
            ).splitlines()
            line_count = len(raw_lines)
            unknown_or_invalid_line_count = sum(
                1
                for line in raw_lines
                if len(line) != 128 or set(line) - {"0", "1"}
            )
            all_lines_non_x = (
                line_count == 4 and unknown_or_invalid_line_count == 0
            )
            try:
                _validate_128(actual, 4)
                valid = (
                    all_lines_non_x
                    and actual.read_bytes() == golden.read_bytes()
                )
            except (OSError, AtomicDequantRuntimeError):
                valid = False
        entries.append(
            {
                "slice_id": slice_id,
                "path": item["path"],
                "base_addr": item["base_addr"],
                "line_count": line_count,
                "unknown_or_invalid_line_count": unknown_or_invalid_line_count,
                "all_four_lines_non_x": all_lines_non_x,
                "actual_sha256": _sha256(actual) if actual.is_file() else None,
                "golden_sha256": _sha256(golden),
                "bit_exact": valid,
                "status": "pass" if valid else "fail",
            }
        )
    passed = len(entries) == 2 and all(item["status"] == "pass" for item in entries)
    return {
        "status": "pass" if passed else "fail",
        "formal_readback_count": len(entries),
        "total_128bit_lines": 8,
        "all_lines_non_x": all(
            item["all_four_lines_non_x"] for item in entries
        ),
        "all_bit_exact": passed,
        "entries": entries,
    }


def _identity_gate(identity: dict[str, Any]) -> dict[str, Any]:
    focused_rtl = identity.get("focused_rtl")
    support_files = identity.get("support_files")
    expected_phases = [
        "pre_install",
        "post_probe_install",
        "post_compile",
        "post_run",
        "post_restore",
    ]
    passed = (
        identity.get("functional_rtl_unchanged") is True
        and identity.get("tb_probe_transactionally_restored") is True
        and identity.get("tb_probe_verified_immediately_before_compile") is True
        and identity.get("package_manifest_stable") is True
        and identity.get("server_command_stable") is True
        and identity.get("installed_namespace_stable") is True
        and isinstance(focused_rtl, dict)
        and bool(focused_rtl)
        and all(value is True for value in focused_rtl.values())
        and isinstance(support_files, dict)
        and bool(support_files)
        and all(value is True for value in support_files.values())
        and identity.get("phases") == expected_phases
    )
    return {
        "status": "pass" if passed else "fail",
        "reported_status": identity.get("status"),
        "functional_rtl_unchanged": identity.get(
            "functional_rtl_unchanged"
        ),
        "tb_probe_transactionally_restored": identity.get(
            "tb_probe_transactionally_restored"
        ),
        "tb_probe_verified_immediately_before_compile": identity.get(
            "tb_probe_verified_immediately_before_compile"
        ),
        "focused_rtl_all_stable": bool(focused_rtl)
        and all(value is True for value in focused_rtl.values()),
        "support_files_all_stable": bool(support_files)
        and all(value is True for value in support_files.values()),
        "identity_status_string_is_not_a_gate": True,
    }


def analyze(
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    run_status: int,
) -> dict[str, Any]:
    evidence = evidence_root.resolve()
    identity_path = evidence / "stock_rtl_identity_receipt.json"
    identity = _load(identity_path) if identity_path.is_file() else {}
    identity_gate = _identity_gate(identity)
    identity_pass = identity_gate["status"] == "pass"
    simulation = _simulation_gate(run_dir, install_name, run_status)
    lifecycle = _lifecycle_gate(run_dir)
    observer = _observer_gate(run_dir, package_root)
    formal = _formal_gate(run_dir, package_root)
    _write_json(evidence / "LIFECYCLE_RECEIPT.json", lifecycle)
    _write_json(evidence / "MSE4_WRITE_OBSERVER_RECEIPT.json", observer)
    _write_json(evidence / "FORMAL_READBACK_RECEIPT.json", formal)
    passed = (
        simulation["status"] == "pass"
        and lifecycle["status"] == "pass"
        and observer["status"] == "pass"
        and formal["status"] == "pass"
        and identity_pass
    )
    gates = {
        "simulation_and_natural_exit": simulation,
        "two_slice_lifecycle": lifecycle,
        "accepted_mse4_writes": observer,
        "finish_write_and_drain": {
            "status": observer["finish_drain_status"],
            "per_slice": observer["finish_per_slice"],
        },
        "formal_d_readback": formal,
        "stock_rtl_identity": identity_gate,
    }
    return {
        "schema": RESULT_SCHEMA,
        "status": "ATOMIC_DYNAMIC_PASS" if passed else "ATOMIC_DYNAMIC_FAIL_OR_INCOMPLETE",
        "classification": "FIRST_DYNAMIC_RUN" if passed else "FIRST_DYNAMIC_FAILURE",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "install_name": install_name,
        "candidate_release": False,
        "counts_as_node0077_e4": False,
        "counts_as_node0077_e5": False,
        "release_gate_passed": False,
        "evidence_level": "ATOMIC_SERVER_DYNAMIC" if passed else "SERVER_INCOMPLETE",
        "run_exit_status": run_status,
        "gates": gates,
        "remaining_blockers": ["B_DEQUANT_SERVER_E4_E5"],
    }


def _copy_tail(source: Path, target: Path, limit: int = 200_000) -> None:
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes()[-limit:])


def collect_return(
    ndp_root: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    run_status: int,
    server_command: str,
) -> dict[str, Any]:
    root = ndp_root.resolve()
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    run = run_dir.resolve()
    return_name = f"{install_name}_return"
    staging = root / return_name
    zip_path = root / f"{return_name}.zip"
    sidecar = root / f"{return_name}.zip.sha256"
    for target in (staging, zip_path, sidecar):
        if target.exists():
            raise AtomicDequantRuntimeError(f"fresh return target required: {target}")
    staging.mkdir(parents=True)
    records: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    def add(source: Path, relative_value: str, role: str, required: bool = True) -> None:
        relative = _safe_relative(relative_value)
        if set(part.lower() for part in relative.parts) & FORBIDDEN_RETURN_PARTS:
            raise AtomicDequantRuntimeError(f"forbidden return path: {relative}")
        if relative.suffix.lower() in FORBIDDEN_RETURN_SUFFIXES:
            raise AtomicDequantRuntimeError(f"forbidden return suffix: {relative}")
        if not source.is_file() or source.stat().st_size > MAX_RETURN_FILE_BYTES:
            if required:
                missing.append({"path": relative.as_posix(), "role": role})
            return
        target = _inside(staging, relative.as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        records.append(
            {
                "path": relative.as_posix(),
                "role": role,
                "size_bytes": target.stat().st_size,
                "sha256": _sha256(target),
            }
        )

    add(package / MANIFEST_NAME, f"package/{MANIFEST_NAME}", "package_identity")
    for name in (
        "package_preflight.json",
        "installed_preflight.json",
        "tb_probe_install_receipt.json",
        "tb_probe_precompile_receipt.json",
        "server_identity_pre_install.json",
        "server_identity_post_probe_install.json",
        "server_identity_post_compile.json",
        "server_identity_post_run.json",
        "server_identity_post_restore.json",
        "stock_rtl_identity_receipt.json",
        "LIFECYCLE_RECEIPT.json",
        "MSE4_WRITE_OBSERVER_RECEIPT.json",
        "FORMAL_READBACK_RECEIPT.json",
        "SERVER_RESULT_GATE.json",
        "server_command.txt",
        "compile_exit_status.txt",
        "sim_exit_status.txt",
        "run_exit_status.txt",
        "termination_signal.txt",
    ):
        add(
            evidence / name,
            f"evidence/{name}",
            "identity_gate_or_receipt",
            name != "termination_signal.txt",
        )
    add(
        root / f"install/cfg_pkg/{install_name}/sca_cfg.json",
        "config/sca_cfg.json",
        "runtime_sca",
    )
    add(
        root / f"install/cfg_pkg/{install_name}/sca_cfg_D.json",
        "config/sca_cfg_D.json",
        "runtime_sca_d",
    )
    for slice_id in ACTIVE_SLICES:
        add(
            run / f"sim_results/dequant_atomic_probe/slice{slice_id:02d}.log",
            f"raw_observer/slice{slice_id:02d}.log",
            "accepted_write_observer",
            False,
        )
        add(
            run / f"sim_results/sem_events/slice{slice_id}/sem_events.log",
            f"raw_lifecycle/slice{slice_id:02d}.log",
            "slice_lifecycle",
            False,
        )
        add(
            run / f"sim_results/formal_readback/op0_matrixD_slice{slice_id}.txt",
            f"raw_formal_readback/op0_matrixD_slice{slice_id}.txt",
            "formal_d_readback",
            False,
        )
    for source, name in (
        (run / "sim_results/compile.log", "compile_tail.log"),
        (run / "sim_results/compile_driver.log", "compile_driver_tail.log"),
        (run / "sim_results/sim.log", "sim_tail.log"),
    ):
        _copy_tail(source, staging / f"logs/{name}")
        if (staging / f"logs/{name}").is_file():
            path = staging / f"logs/{name}"
            records.append(
                {
                    "path": f"logs/{name}",
                    "role": "bounded_log_tail",
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    gate_path = evidence / "SERVER_RESULT_GATE.json"
    gate = _load(gate_path) if gate_path.is_file() else {}
    receipt = {
        "schema": RETURN_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if not missing else "incomplete",
        "server_result_status": gate.get("status", "missing"),
        "classification": gate.get("classification", "FIRST_DYNAMIC_FAILURE"),
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "install_name": install_name,
        "candidate_release": False,
        "counts_as_node0077_e4": False,
        "counts_as_node0077_e5": False,
        "run_exit_status": run_status,
        "server_command": server_command,
        "allowlist_only": True,
        "waveforms_included": False,
        "build_tree_included": False,
        "nested_archive_included": False,
        "required_missing": missing,
        "files": sorted(records, key=lambda item: item["path"]),
    }
    _write_json(staging / "RETURN_RECEIPT.json", receipt)
    extracted = sum(path.stat().st_size for path in staging.rglob("*") if path.is_file())
    if extracted > MAX_RETURN_EXTRACTED_BYTES:
        raise AtomicDequantRuntimeError("return extracted size exceeds 4 MiB")
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
    if zip_path.stat().st_size > MAX_RETURN_ZIP_BYTES:
        raise AtomicDequantRuntimeError("return ZIP exceeds 2 MiB")
    digest = _sha256(zip_path)
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    return {
        **receipt,
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": sidecar.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("preflight-package")
    preflight.add_argument("--package-root", type=Path, required=True)
    preflight.add_argument("--install-name", required=True)
    preflight.add_argument("--output", type=Path, required=True)
    installed = sub.add_parser("preflight-installed")
    installed.add_argument("--package-root", type=Path, required=True)
    installed.add_argument("--ndp-root", type=Path, required=True)
    installed.add_argument("--install-name", required=True)
    installed.add_argument("--output", type=Path, required=True)
    analyze_parser = sub.add_parser("analyze")
    analyze_parser.add_argument("--package-root", type=Path, required=True)
    analyze_parser.add_argument("--install-name", required=True)
    analyze_parser.add_argument("--evidence-root", type=Path, required=True)
    analyze_parser.add_argument("--run-dir", type=Path, required=True)
    analyze_parser.add_argument("--run-status", type=int, required=True)
    analyze_parser.add_argument("--output", type=Path, required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--ndp-root", type=Path, required=True)
    collect.add_argument("--package-root", type=Path, required=True)
    collect.add_argument("--install-name", required=True)
    collect.add_argument("--evidence-root", type=Path, required=True)
    collect.add_argument("--run-dir", type=Path, required=True)
    collect.add_argument("--run-status", type=int, required=True)
    collect.add_argument("--server-command", required=True)
    args = parser.parse_args()
    try:
        if args.command == "preflight-package":
            report = preflight_package(args.package_root, args.install_name)
            _write_json(args.output, report)
        elif args.command == "preflight-installed":
            report = preflight_installed(
                args.package_root, args.ndp_root, args.install_name
            )
            _write_json(args.output, report)
        elif args.command == "analyze":
            report = analyze(
                args.package_root,
                args.install_name,
                args.evidence_root,
                args.run_dir,
                args.run_status,
            )
            _write_json(args.output, report)
            if report["status"] != "ATOMIC_DYNAMIC_PASS":
                return 7
        else:
            report = collect_return(
                args.ndp_root,
                args.package_root,
                args.install_name,
                args.evidence_root,
                args.run_dir,
                args.run_status,
                args.server_command,
            )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Dequant atomic runtime failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
