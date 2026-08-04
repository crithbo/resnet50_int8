#!/usr/bin/env python3
"""Fail-closed runtime for the Requant node0001 atomic two-stage diagnostic."""

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

# Must precede every package-local import. The exact-set gate deliberately does
# not allow __pycache__ or .pyc side effects.
sys.dont_write_bytecode = True

try:
    import requant_node0001_server_runtime as common
except ModuleNotFoundError:  # Repository import; packaged execution uses the local name.
    from tools import requant_node0001_server_runtime as common


MANIFEST_NAME = "TEST_PACKAGE_MANIFEST.json"
RUNTIME_SCHEMA = "requant-node0001-atomic-stockrtl-firstdynamic-runtime-v1"
RESULT_SCHEMA = "requant-node0001-atomic-stockrtl-firstdynamic-result-v1"
RETURN_SCHEMA = "requant-node0001-atomic-stockrtl-firstdynamic-return-v1"
ACTIVE_SLICES = (0, 1)
SLICE_MASK = 0b11
STAGE_COUNT = 2
EXEC_LINES = 6
PRELOAD_COUNT = 6
FORMAL_READBACK_COUNT = 4
EXPECTED_WRITE_COUNT = 20
MAX_RETURN_FILE_BYTES = 512 * 1024
MAX_RETURN_EXTRACTED_BYTES = 4 * 1024 * 1024
MAX_RETURN_ZIP_BYTES = 2 * 1024 * 1024
FORBIDDEN_SUFFIXES = {
    ".zip",
    ".tar",
    ".tgz",
    ".gz",
    ".7z",
    ".vcd",
    ".fsdb",
    ".vpd",
    ".wlf",
}
FORBIDDEN_RETURN_PARTS = {"build", "csrc", "simv.daidir", "waves", "wave"}


class AtomicRuntimeError(RuntimeError):
    """Raised when an atomic package, run, or return fails closed."""


def _runtime_profile(package: Path) -> dict[str, Any]:
    path = package.resolve() / "validation/diagnostic_profile.json"
    if path.is_file():
        profile = _load_json(path)
        required = {
            "mode",
            "stage_count",
            "exec_lines",
            "exec_word_count",
            "preload_count",
            "formal_readback_count",
            "expected_write_count",
            "observer_plusarg",
            "observer_log_dir",
        }
        if not isinstance(profile, dict) or not required.issubset(profile):
            raise AtomicRuntimeError("diagnostic runtime profile is incomplete")
        return profile
    return {
        "mode": "atomic_two_stage",
        "stage_count": STAGE_COUNT,
        "exec_lines": EXEC_LINES,
        "exec_word_count": 12,
        "preload_count": PRELOAD_COUNT,
        "formal_readback_count": FORMAL_READBACK_COUNT,
        "expected_write_count": EXPECTED_WRITE_COUNT,
        "observer_plusarg": "REQUANT_ATOMIC_PROBE",
        "observer_log_dir": "requant_atomic_probe",
    }


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


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _safe_relative(value: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise AtomicRuntimeError(f"unsafe relative path: {value!r}")
    return relative


def _inside(root: Path, value: str | PurePosixPath) -> Path:
    relative = _safe_relative(value) if isinstance(value, str) else value
    base = root.resolve()
    target = base.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise AtomicRuntimeError(f"path escapes root: {relative}") from exc
    return target


def _validate_pretty_json(path: Path) -> Any:
    value = _load_json(path)
    expected = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.read_text(encoding="utf-8") != expected:
        raise AtomicRuntimeError(f"JSON is not canonical pretty LF: {path}")
    return value


def _validate_128bit_text(path: Path, expected_lines: int) -> list[str]:
    raw = path.read_bytes()
    if b"\r" in raw:
        raise AtomicRuntimeError(f"128-bit text contains CR: {path}")
    lines = raw.decode("ascii").splitlines()
    if len(lines) != expected_lines:
        raise AtomicRuntimeError(
            f"128-bit line count differs: {path}: {len(lines)} != {expected_lines}"
        )
    if any(len(line) != 128 or set(line) - {"0", "1"} for line in lines):
        raise AtomicRuntimeError(f"invalid 128-bit text: {path}")
    if raw != ("\n".join(lines) + "\n").encode("ascii"):
        raise AtomicRuntimeError(f"128-bit text is not canonical LF: {path}")
    return lines


def _exec_words(path: Path, expected_lines: int = EXEC_LINES) -> list[int]:
    words: list[int] = []
    for line in _validate_128bit_text(path, expected_lines):
        words.extend((int(line[64:], 2), int(line[:64], 2)))
    if words and words[-1] == 0:
        words.pop()
    return words


def _payload_local(package: Path, install_name: str, runtime_path: str) -> Path:
    prefix = f"../install/cfg_pkg/{install_name}/"
    if not runtime_path.startswith(prefix):
        raise AtomicRuntimeError(
            f"runtime payload is outside the unique namespace: {runtime_path}"
        )
    return _inside(package / "workload/runtime", runtime_path[len(prefix) :])


def _manifest(package: Path, install_name: str) -> dict[str, Any]:
    manifest = _load_json(package / MANIFEST_NAME)
    if manifest.get("install_name") != install_name:
        raise AtomicRuntimeError("install name differs")
    if manifest.get("files") != _records(package, exclude_manifest=True):
        raise AtomicRuntimeError("package payload differs from manifest exact set")
    return manifest


def preflight_package(package_root: Path, install_name: str) -> dict[str, Any]:
    package = package_root.resolve()
    manifest = _manifest(package, install_name)
    profile = _runtime_profile(package)
    stage_count = int(profile["stage_count"])
    exec_lines = int(profile["exec_lines"])
    exec_word_count = int(profile["exec_word_count"])
    preload_count = int(profile["preload_count"])
    formal_readback_count = int(profile["formal_readback_count"])
    expected_write_count = int(profile["expected_write_count"])
    if (
        manifest.get("candidate_release") is not False
        or manifest.get("counts_as_node0001_e4") is not False
        or manifest.get("counts_as_node0001_e5") is not False
        or manifest.get("dynamic_baseline") != "NO_DYNAMIC_BASELINE"
        or manifest.get("run_kind") != "FIRST_DYNAMIC_DIAGNOSTIC"
    ):
        raise AtomicRuntimeError("diagnostic claim boundary differs")
    for relative in manifest["files"]:
        parts = {part.lower() for part in PurePosixPath(relative).parts}
        suffix = PurePosixPath(relative).suffix.lower()
        if "rtl" in parts:
            raise AtomicRuntimeError(f"rtl/ payload is forbidden: {relative}")
        if "__pycache__" in parts or suffix in {".pyc", ".pyo"}:
            raise AtomicRuntimeError(
                f"Python bytecode payload is forbidden: {relative}"
            )
        if suffix in FORBIDDEN_SUFFIXES:
            raise AtomicRuntimeError(f"archive or waveform payload is forbidden: {relative}")

    runtime = package / "workload/runtime"
    sca = _validate_pretty_json(runtime / "sca_cfg.json")
    sca_d = _validate_pretty_json(runtime / "sca_cfg_D.json")
    lifecycle = _validate_pretty_json(
        package / "validation/lifecycle_contract.json"
    )
    expected_writes = _validate_pretty_json(
        package / "validation/expected_mse4_writes.json"
    )
    if (
        sca.get("Exec_Base") != "0x0180_0C00"
        or sca.get("Exec_Length") != exec_lines
        or sca.get("Repeat_Num") != stage_count
    ):
        raise AtomicRuntimeError("Exec_Base/Exec_Length/Repeat_Num differs")
    payloads = {
        name: value
        for name, value in sca.items()
        if isinstance(value, dict) and "path" in value
    }
    if len(payloads) != preload_count:
        raise AtomicRuntimeError(f"SCA preload count differs: {len(payloads)}")
    if any("round_matrixA" in name for name in payloads):
        raise AtomicRuntimeError("round input must not be externally preloaded")
    if len([name for name in payloads if "sfu_config" in name]) != 1:
        raise AtomicRuntimeError("RequantGuard must be loaded exactly once")
    for name, value in payloads.items():
        target = _payload_local(package, install_name, value["path"])
        if not target.is_file():
            raise AtomicRuntimeError(f"missing SCA payload: {name}")
    words = _exec_words(
        _payload_local(package, install_name, sca["ExecutionPlan"]["path"]),
        exec_lines,
    )
    opcodes = [word & 0x7 for word in words]
    starts = [
        (word >> 3) & ((1 << 28) - 1)
        for word in words
        if (word & 0x7) == 0b101
    ]
    barriers = [
        (word >> 3) & ((1 << 28) - 1)
        for word in words
        if (word & 0x7) == 0b110
    ]
    if (
        len(words) != exec_word_count
        or starts != [SLICE_MASK] * stage_count
        or barriers != [SLICE_MASK] * stage_count
        or opcodes[-1] != 0b110
    ):
        raise AtomicRuntimeError("same-mask completion execplan differs")

    expected_d = {
        "op_w0_s00_guard_matrixD_slice0": ("0x00800000", 8),
        "op_w0_s00_guard_matrixD_slice1": ("0x02800000", 8),
    }
    if stage_count == 2:
        expected_d.update(
            {
                "op_w0_s00_round_matrixD_slice0": ("0x01000000", 2),
                "op_w0_s00_round_matrixD_slice1": ("0x03000000", 2),
            }
        )
    if set(sca_d) != set(expected_d):
        raise AtomicRuntimeError("SCA_D exact set differs")
    for name, (address, length) in expected_d.items():
        entry = sca_d[name]
        if (
            entry != {
                "base_addr": address,
                "path": f"sim_results/formal_readback/{name}.txt",
                "length": length,
            }
        ):
            raise AtomicRuntimeError(f"SCA_D entry differs: {name}")
    if (
        lifecycle.get("active_slices") != [0, 1]
        or lifecycle.get("repeat_num") != stage_count
        or lifecycle.get("stock_tb_completion_observer", {}).get(
            "required_sampled_slices_enabled"
        )
        is not True
        or expected_writes.get("total_expected_accepted_write_count")
        != expected_write_count
    ):
        raise AtomicRuntimeError("v2 lifecycle/write contract differs")

    for slice_id in ACTIVE_SLICES:
        _validate_128bit_text(
            runtime
            / f"payloads/inputs/op_w0_s00_guard/slice{slice_id:02d}/"
            "matrix_A_linearized_128bit.txt",
            8,
        )
        _validate_128bit_text(
            package / f"golden/guard_slice{slice_id:02d}_128b.txt", 8
        )
        if stage_count == 2:
            _validate_128bit_text(
                package / f"golden/final_slice{slice_id:02d}_128b.txt", 2
            )

    tail_name = str(
        profile.get("observer_tail", "requant_mse4_guard_observer_tail.svh")
    )
    tail = package / "tb_probe" / tail_name
    if not tail.is_file() or tail.stat().st_size > 48 * 1024:
        raise AtomicRuntimeError("read-only atomic observer tail is missing or oversized")
    tail_text = tail.read_text(encoding="utf-8")
    active_lines = [
        line.split("//", 1)[0]
        for line in tail_text.splitlines()
        if not line.lstrip().startswith("//")
    ]
    active_text = "\n".join(active_lines).lower()
    for forbidden in ("force ", "deposit", "release ", "<="):
        if forbidden in active_text:
            raise AtomicRuntimeError(f"observer contains a driving token: {forbidden}")
    if (
        f'+{profile["observer_plusarg"]}'
        not in tail_text
    ):
        raise AtomicRuntimeError("observer is not plusarg gated")
    try:
        xmr_elaboration_gate = common.validate_observer_xmr_elaboration(tail_text)
    except common.RequantRuntimeError as exc:
        raise AtomicRuntimeError(str(exc)) from exc

    return {
        "schema": RUNTIME_SCHEMA,
        "status": "package_preflight_passed",
        "candidate_release": False,
        "counts_as_node0001_e4": False,
        "counts_as_node0001_e5": False,
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "active_slices": list(ACTIVE_SLICES),
        "logical_occurrence_count": 1,
        "physical_slice_instance_count": 2,
        "diagnostic_mode": profile["mode"],
        "stage_count": stage_count,
        "start_comp_count": stage_count,
        "same_mask_fence_count": stage_count,
        "preload_count": preload_count,
        "formal_readback_count": formal_readback_count,
        "expected_mse4_write_count": expected_write_count,
        "functional_rtl_file_count": 0,
        "observer_file_count": 1,
        "observer_xmr_elaboration_gate": xmr_elaboration_gate,
    }


def preflight_installed(
    package_root: Path, ndp_root: Path, install_name: str
) -> dict[str, Any]:
    report = preflight_package(package_root, install_name)
    source = package_root.resolve() / "workload/runtime"
    installed = ndp_root.resolve() / "install/cfg_pkg" / install_name
    if not installed.is_dir() or _records(installed) != _records(source):
        raise AtomicRuntimeError("installed namespace differs from packaged runtime")
    return {
        **report,
        "status": "installed_preflight_passed",
        "installed_file_count": len(_records(installed)),
        "installed_namespace": installed.as_posix(),
    }


def _simulation_gate(
    run_dir: Path,
    install_name: str,
    run_status: int,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = profile or {
        "stage_count": STAGE_COUNT,
        "preload_count": PRELOAD_COUNT,
        "formal_readback_count": FORMAL_READBACK_COUNT,
    }
    stage_count = int(profile["stage_count"])
    path = run_dir.resolve() / "sim_results/sim.log"
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    required = {
        "sca_path": f"../install/cfg_pkg/{install_name}/sca_cfg.json",
        "sca_d_path": f"../install/cfg_pkg/{install_name}/sca_cfg_D.json",
        "preload_count": (
            f"JSON config: {int(profile['preload_count'])} matrices loaded"
        ),
        "readback_count": (
            "JSON_D config: "
            f"{int(profile['formal_readback_count'])} matrices dumped"
        ),
        "success": "Simulation completed successfully!",
    }
    found = {name: marker in text for name, marker in required.items()}
    first_sfu = text.find("RequantGuard.txt")
    first_start = text.find("INFO: slice start")
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
    start_count = text.count("INFO: slice start")
    finish_count = text.count("INFO: slice completed after")
    sfu_count = text.count("RequantGuard.txt ->")
    passed = (
        path.is_file()
        and run_status == 0
        and all(found.values())
        and start_count == stage_count
        and finish_count == stage_count
        and sfu_count == 1
        and first_sfu >= 0
        and first_start > first_sfu
        and not forbidden
    )
    return {
        "status": "pass" if passed else "fail",
        "run_exit_status": run_status,
        "required_markers": found,
        "start_count": start_count,
        "completion_count": finish_count,
        "requant_guard_load_count": sfu_count,
        "requant_guard_loaded_before_first_start": first_sfu >= 0
        and first_start > first_sfu,
        "forbidden_markers": forbidden,
        "sim_log_sha256": _sha256(path) if path.is_file() else None,
    }


def _sem_groups(run_dir: Path, event: str) -> list[dict[str, Any]]:
    groups: dict[int, set[int]] = {}
    pattern = re.compile(rf"^\s*(\d+)\s+\|\s+{re.escape(event)}\s+\|")
    for slice_id in ACTIVE_SLICES:
        path = (
            run_dir.resolve()
            / f"sim_results/sem_events/slice{slice_id}/sem_events.log"
        )
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = pattern.match(line)
            if match:
                groups.setdefault(int(match.group(1)), set()).add(slice_id)
    return [
        {
            "time": time,
            "slices": sorted(slices),
            "mask": sum(1 << slice_id for slice_id in slices),
        }
        for time, slices in sorted(groups.items())
    ]


def _lifecycle_gate(
    run_dir: Path, stage_count: int = STAGE_COUNT
) -> dict[str, Any]:
    starts = _sem_groups(run_dir, "Start Comp")
    finishes = _sem_groups(run_dir, "Comp Finish")
    fences: list[dict[str, Any]] = []
    for stage in range(stage_count):
        start = starts[stage] if stage < len(starts) else {}
        finish = finishes[stage] if stage < len(finishes) else {}
        passed = (
            start.get("mask") == SLICE_MASK
            and finish.get("mask") == SLICE_MASK
            and isinstance(start.get("time"), int)
            and isinstance(finish.get("time"), int)
            and finish["time"] > start["time"]
            and (
                stage == stage_count - 1
                or stage + 1 >= len(starts)
                or starts[stage + 1]["time"] >= finish["time"]
            )
        )
        fences.append(
            {
                "stage_index": stage,
                "role": "guard" if stage == 0 else "round_saturate",
                "expected_mask": "0b0000000000000000000000000011",
                "start_mask": (
                    f"0b{start['mask']:028b}" if "mask" in start else None
                ),
                "finish_mask": (
                    f"0b{finish['mask']:028b}" if "mask" in finish else None
                ),
                "start_time": start.get("time"),
                "finish_time": finish.get("time"),
                "same_mask_completion_fence": passed,
            }
        )
    passed = (
        len(starts) == stage_count
        and len(finishes) == stage_count
        and all(item["same_mask_completion_fence"] for item in fences)
    )
    return {
        "status": "pass" if passed else "fail",
        "start_group_count": len(starts),
        "finish_group_count": len(finishes),
        "same_mask_fence_pass_count": sum(
            item["same_mask_completion_fence"] for item in fences
        ),
        "all_stages_naturally_completed": passed,
        "fences": fences,
    }


def _observer_gate(
    run_dir: Path,
    package_root: Path,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    package = package_root.resolve()
    profile = profile or _runtime_profile(package)
    expected_doc = _load_json(
        package / "validation/expected_mse4_writes.json"
    )
    expected: list[dict[str, Any]] = []
    for stage in expected_doc["stages"]:
        expected.extend(stage["writes"])
    pattern = re.compile(
        r"MSE4_WRITE\s+\|.*slice=(\d+).*local_stage=(\d+).*"
        r"role=\s*(guard|round_saturate)\b.*ch=(\d+).*accepted=1\s+valid=1\s+"
        r"ready=1\s+strobe=(0x[0-9a-fA-F]+)\s+"
        r"(?:req_txn_id=(-?\d+)\s+wdata_txn_id=(\d+)\s+"
        r"paired_req_valid=([01])\s+)?"
        r"(?:transfer_addr=0x[0-9a-fA-F]+\s+"
        r"linear_addr=0x[0-9a-fA-F]+\s+)?"
        r"addr=(0x[0-9a-fA-F]+)\s+"
        r"data=(0x[0-9a-fA-F]{32})"
    )
    actual: list[dict[str, Any]] = []
    raw_mse4_marker_count = 0
    errors: list[str] = []
    stage_events: list[dict[str, Any]] = []
    event_pattern = re.compile(
        r"(STAGE_START|STAGE_FINISH)\s+\|.*cycle=(\d+).*slice=(\d+).*"
        r"local_stage=(\d+)"
    )
    for slice_id in ACTIVE_SLICES:
        path = (
            run_dir.resolve()
            / "sim_results"
            / str(profile["observer_log_dir"])
            / f"slice{slice_id:02d}.log"
        )
        if not path.is_file():
            errors.append(f"missing observer log slice{slice_id}")
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "MSE4_WRITE" in line:
                raw_mse4_marker_count += 1
            if "PROBE_ERROR" in line:
                errors.append(line[-300:])
            event = event_pattern.search(line)
            if event:
                stage_events.append(
                    {
                        "event": event.group(1),
                        "cycle": int(event.group(2)),
                        "slice_id": int(event.group(3)),
                        "stage_index": int(event.group(4)),
                    }
                )
            match = pattern.search(line)
            if match:
                actual.append(
                    {
                        "slice_id": int(match.group(1)),
                        "stage_index": int(match.group(2)),
                        "role": match.group(3),
                        "channel": int(match.group(4)),
                        "strobe": match.group(5).lower(),
                        "request_transaction_id": (
                            int(match.group(6))
                            if match.group(6) is not None
                            else None
                        ),
                        "write_data_transaction_id": (
                            int(match.group(7))
                            if match.group(7) is not None
                            else None
                        ),
                        "paired_request_valid": (
                            bool(int(match.group(8)))
                            if match.group(8) is not None
                            else None
                        ),
                        "post_remap_request_address_128b": match.group(9).lower(),
                        "data": match.group(10).lower(),
                    }
                )

    raw_parse_count_consistent = raw_mse4_marker_count == len(actual)
    if not raw_parse_count_consistent:
        errors.append(
            "raw MSE4 marker count does not equal parsed accepted-write count: "
            f"raw={raw_mse4_marker_count} parsed={len(actual)}"
        )
    expected_keys = [
        {
            "slice_id": int(item["slice_id"]),
            "stage_index": int(item["stage_index"]),
            "role": str(item["role"]),
            "strobe": str(item["strobe"]).lower(),
            "data": str(item["data"]).lower(),
        }
        for item in expected
    ]
    actual_keys = [
        {key: item[key] for key in expected_keys[0]}
        for item in actual
    ]
    mismatches: list[dict[str, Any]] = []
    groups = sorted(
        {
            (int(item["stage_index"]), int(item["slice_id"]))
            for item in expected_keys
        }
    )
    for stage_index, slice_id in groups:
        wanted_group = [
            item
            for item in expected_keys
            if item["stage_index"] == stage_index and item["slice_id"] == slice_id
        ]
        observed_group = [
            item
            for item in actual_keys
            if item["stage_index"] == stage_index and item["slice_id"] == slice_id
        ]
        for beat_index in range(max(len(wanted_group), len(observed_group))):
            wanted = (
                wanted_group[beat_index]
                if beat_index < len(wanted_group)
                else None
            )
            observed = (
                observed_group[beat_index]
                if beat_index < len(observed_group)
                else None
            )
            if wanted != observed:
                mismatches.append(
                    {
                        "stage_index": stage_index,
                        "slice_id": slice_id,
                        "beat_index": beat_index,
                        "expected": wanted,
                        "actual": observed,
                    }
                )
                if len(mismatches) >= 8:
                    break
        if len(mismatches) >= 8:
            break
    unique = len(
        {
            (
                item["slice_id"],
                item["stage_index"],
                item["post_remap_request_address_128b"],
            )
            for item in actual
        }
    )
    passed = (
        not errors
        and raw_parse_count_consistent
        and raw_mse4_marker_count == int(profile["expected_write_count"])
        and len(actual_keys) == int(profile["expected_write_count"])
        and not mismatches
    )
    role_counts = {
        role: sum(item["role"] == role for item in actual_keys)
        for role in ("guard", "round_saturate")
    }
    return {
        "status": "pass" if passed else "fail",
        "evidence_kind": "same_clock_read_only_accepted_mse4_write_observer",
        "expected_write_count": int(profile["expected_write_count"]),
        "raw_mse4_marker_count": raw_mse4_marker_count,
        "parsed_mse4_write_count": len(actual_keys),
        "raw_count_receipt_consistent": raw_parse_count_consistent,
        "actual_write_count": len(actual_keys),
        "post_remap_unique_slice_stage_address_count": unique,
        "paired_request_count": sum(
            item["paired_request_valid"] is True for item in actual
        ),
        "unpaired_write_data_count": sum(
            item["paired_request_valid"] is False for item in actual
        ),
        "temporal_pairing_status": (
            "pass"
            if all(
                item["paired_request_valid"] is not False for item in actual
            )
            else "observer_temporal_evidence_incomplete"
        ),
        "address_comparison_valid": False,
        "address_domain_note": (
            "expected_mse4_writes.json is linear/pre-remap while this legacy "
            "observer field is the post-remap local request address; addresses "
            "are deliberately excluded from this payload/order gate"
        ),
        "role_counts": role_counts,
        "order_and_payload_bit_exact": not mismatches
        and len(actual_keys) == int(profile["expected_write_count"]),
        "errors": errors[:16],
        "first_mismatches": mismatches,
        "stage_events": stage_events,
    }


def _guard_checkpoint_gate(
    run_dir: Path, profile: dict[str, Any]
) -> dict[str, Any]:
    capture_edge_safe = bool(profile.get("capture_edge_safe", False))
    exact_expected_counts = {
        str(key): int(value)
        for key, value in profile.get("checkpoint_expected_counts", {}).items()
    }
    observation_only = {
        str(value)
        for value in profile.get("checkpoint_observation_only", [])
    }
    expected_counts: dict[str, int | None] = {
        **exact_expected_counts,
        **{name: None for name in observation_only},
    }
    raw_counts = {name: 0 for name in expected_counts}
    parsed_counts = {name: 0 for name in expected_counts}
    zero_counts = {name: 0 for name in expected_counts}
    nonzero_counts = {name: 0 for name in expected_counts}
    samples: dict[str, list[dict[str, Any]]] = {
        name: [] for name in expected_counts
    }
    readiness_field_names = {
        "PE_POST_REGISTER": ("post_valid", "matched", "output_valid"),
        "SFU_OPCODE_READY": ("opcode", "sfu_valid", "compute_en"),
        "SFU_GROUP_COMPUTE_VALID": ("compute_valid",),
        "SFU_LUT_INIT": ("init_en", "init_addr", "end_addr", "slice_rst"),
        "SFU_PREPROCESS0": ("enable", "valid"),
    }
    readiness_fields: dict[str, dict[str, dict[str, Any]]] = {
        boundary: {
            field: {
                "seen_count": 0,
                "asserted_count": 0,
                "zero_count": 0,
                "minimum": None,
                "maximum": None,
                "value_counts": {},
            }
            for field in fields
        }
        for boundary, fields in readiness_field_names.items()
        if boundary in expected_counts
    }
    errors: list[str] = []
    for slice_id in ACTIVE_SLICES:
        path = (
            run_dir.resolve()
            / "sim_results"
            / str(profile["observer_log_dir"])
            / f"slice{slice_id:02d}.log"
        )
        if not path.is_file():
            errors.append(f"missing guard path observer log slice{slice_id}")
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "GUARD_PATH" not in line:
                continue
            fields: dict[str, str] = {}
            for token in line.split():
                if "=" in token:
                    key, value = token.split("=", 1)
                    fields[key] = value
            boundary = fields.get("boundary")
            if boundary not in expected_counts:
                errors.append(f"unknown or missing guard path boundary: {line[-240:]}")
                continue
            raw_counts[boundary] += 1
            if fields.get("slice") != str(slice_id):
                errors.append(f"guard path slice identity differs: {line[-240:]}")
                continue
            if boundary == "MSE4_REQ" and not {
                "linear_addr",
                "post_remap_addr",
            }.issubset(fields):
                errors.append(f"MSE4 request address domains missing: {line[-240:]}")
                continue
            if capture_edge_safe and fields.get("witness") is None:
                errors.append(
                    f"capture-edge witness kind is missing: {line[-240:]}"
                )
                continue
            data = fields.get("data")
            if boundary not in {"MSE0_REQ", "MSE4_REQ"} and data is None:
                errors.append(f"guard path data field missing: {line[-240:]}")
                continue
            if data is not None and re.fullmatch(r"0x[0-9a-fA-F]+", data) is None:
                errors.append(f"guard path data is malformed: {line[-240:]}")
                continue
            parsed_counts[boundary] += 1
            for field, summary in readiness_fields.get(boundary, {}).items():
                raw_value = fields.get(field)
                if raw_value is None or re.fullmatch(
                    r"(?:0x[0-9a-fA-F]+|[0-9]+)", raw_value
                ) is None:
                    errors.append(
                        f"{boundary} readiness field {field} is missing or "
                        f"malformed: {line[-240:]}"
                    )
                    continue
                value = int(raw_value, 0)
                summary["seen_count"] += 1
                summary["asserted_count"] += int(value != 0)
                summary["zero_count"] += int(value == 0)
                summary["minimum"] = (
                    value
                    if summary["minimum"] is None
                    else min(summary["minimum"], value)
                )
                summary["maximum"] = (
                    value
                    if summary["maximum"] is None
                    else max(summary["maximum"], value)
                )
                value_key = str(value)
                summary["value_counts"][value_key] = (
                    int(summary["value_counts"].get(value_key, 0)) + 1
                )
            if data is not None:
                if int(data, 16) == 0:
                    zero_counts[boundary] += 1
                else:
                    nonzero_counts[boundary] += 1
            if len(samples[boundary]) < 8:
                samples[boundary].append(fields)

    count_checks = {
        name: {
            "expected": expected_counts[name],
            "raw": raw_counts[name],
            "parsed": parsed_counts[name],
            "raw_equals_parsed": raw_counts[name] == parsed_counts[name],
            "exact_count": (
                True
                if expected_counts[name] is None
                else parsed_counts[name] == expected_counts[name]
            ),
            "observation_only": expected_counts[name] is None,
        }
        for name in expected_counts
    }
    passed = (
        not errors
        and all(item["raw_equals_parsed"] for item in count_checks.values())
        and all(item["exact_count"] for item in count_checks.values())
    )
    return {
        "status": "pass" if passed else "fail",
        "evidence_kind": (
            "capture_edge_read_only_numeric_payload_witnesses"
            if capture_edge_safe
            else "same_clock_read_only_guard_path_checkpoints"
        ),
        "capture_edge_safe": capture_edge_safe,
        "status_summary_mislabeled_as_numeric_payload": False,
        "address_domains": {
            "linear_addr": (
                "pre-remap WR_Memory_AG.transfer_addr_nooff plus the stream "
                "base, comparable to expected_mse4_writes word_address_128b"
            ),
            "post_remap_addr": (
                "accepted local_req_addr after mse_map_matrix_b; not directly "
                "compared with linear expected addresses"
            ),
        },
        "count_checks": count_checks,
        "zero_data_counts": zero_counts,
        "nonzero_data_counts": nonzero_counts,
        "first_samples": samples,
        "readiness_field_semantics": readiness_fields,
        "errors": errors[:32],
    }


def _formal_gate(
    run_dir: Path,
    package_root: Path,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    package = package_root.resolve()
    profile = profile or _runtime_profile(package)
    sca_d = _load_json(package / "workload/runtime/sca_cfg_D.json")
    entries: list[dict[str, Any]] = []
    for name, item in sca_d.items():
        match = re.fullmatch(
            r"op_w0_s00_(guard|round)_matrixD_slice([01])", name
        )
        if match is None:
            raise AtomicRuntimeError(f"unexpected formal readback key: {name}")
        role_text, slice_text = match.groups()
        role = "guard" if role_text == "guard" else "round_saturate"
        slice_id = int(slice_text)
        golden = package / (
            f"golden/guard_slice{slice_id:02d}_128b.txt"
            if role == "guard"
            else f"golden/final_slice{slice_id:02d}_128b.txt"
        )
        actual = _inside(run_dir.resolve(), item["path"])
        passed = actual.is_file() and actual.read_bytes() == golden.read_bytes()
        entries.append(
            {
                "name": name,
                "role": role,
                "slice_id": slice_id,
                "base_addr": item["base_addr"],
                "line_count": item["length"] if actual.is_file() else None,
                "actual_sha256": _sha256(actual) if actual.is_file() else None,
                "expected_sha256": _sha256(golden),
                "status": "pass" if passed else "fail",
            }
        )
    role_counts = {
        role: sum(item["role"] == role for item in entries)
        for role in ("guard", "round_saturate")
    }
    expected_roles = (
        {"guard": 2, "round_saturate": 0}
        if profile["mode"] == "guard_only"
        else {"guard": 2, "round_saturate": 2}
    )
    passed = (
        len(entries) == int(profile["formal_readback_count"])
        and role_counts == expected_roles
        and all(item["status"] == "pass" for item in entries)
    )
    return {
        "status": "pass" if passed else "fail",
        "formal_readback_count": len(entries),
        "role_counts": role_counts,
        "all_bit_exact": passed,
        "entries": entries,
    }


def _first_divergence(
    simulation: dict[str, Any],
    lifecycle: dict[str, Any],
    observer: dict[str, Any],
    formal: dict[str, Any],
) -> dict[str, Any]:
    if (
        simulation["status"] == "pass"
        and lifecycle["status"] == "pass"
        and observer["status"] == "pass"
        and formal["status"] == "pass"
    ):
        return {
            "classification": "ATOMIC_COMBINED_DIAGNOSTIC_PASS",
            "first_divergence": None,
            "enable_only": None,
            "additional_atomic_contracts_remain_disabled": True,
        }
    guard_actual = observer["role_counts"].get("guard", 0)
    round_actual = observer["role_counts"].get("round_saturate", 0)
    guard_mismatch = next(
        (
            item
            for item in observer["first_mismatches"]
            if item.get("stage_index") == 0
        ),
        None,
    )
    stage0 = lifecycle["fences"][0]
    stage1 = lifecycle["fences"][1]
    if lifecycle["start_group_count"] == 0 and guard_actual == 0:
        return {
            "classification": "SERVER_INFRASTRUCTURE_OR_PRE_START_FAILURE",
            "first_divergence": "simulation did not produce the first guard start",
            "enable_only": None,
        }
    if guard_actual != 16 or guard_mismatch is not None or stage0["finish_time"] is None:
        return {
            "classification": "GUARD_ACCEPTED_WRITE_OR_COMPLETION_DIVERGENCE",
            "first_divergence": (
                "guard accepted write/data or guard completion"
            ),
            "enable_only": "guard-only",
        }
    if (
        stage1["start_time"] is None
        or stage1["start_time"] < stage0["finish_time"]
        or any(
            item["role"] == "guard" and item["status"] != "pass"
            for item in formal["entries"]
        )
    ):
        return {
            "classification": "ALIAS_LIFETIME_OR_BARRIER_DIVERGENCE",
            "first_divergence": (
                "guard completion to round start, same-address visibility, "
                "or stage1 external-preload isolation"
            ),
            "enable_only": "alias-lifetime",
        }
    if round_actual != 4 or observer["status"] != "pass":
        return {
            "classification": "ROUND_ACCEPTED_WRITE_OR_DATA_DIVERGENCE",
            "first_divergence": "round accepted write/data after round has started",
            "enable_only": "round-only",
        }
    if stage1["finish_time"] is None:
        return {
            "classification": "CORRECT_WRITES_BUT_COMPLETION_MISSING",
            "first_divergence": "both write stages matched but completion is missing",
            "enable_only": None,
            "retain_combined_completion_evidence": True,
        }
    return {
        "classification": "FORMAL_READBACK_OR_NATURAL_EXIT_DIVERGENCE",
        "first_divergence": "accepted writes completed but formal readback or natural exit failed",
        "enable_only": None,
    }


def _sfu_readiness_route(
    simulation: dict[str, Any],
    lifecycle: dict[str, Any],
    checkpoints: dict[str, Any],
    observer: dict[str, Any],
    formal: dict[str, Any],
) -> dict[str, Any]:
    orthogonal = {
        "mse4_observer_status": observer.get("status"),
        "formal_d_status": formal.get("status"),
    }

    def route(name: str, reason: str, **extra: Any) -> dict[str, Any]:
        return {
            "classification": "SFU_READINESS_NARROW_DIAGNOSTIC",
            "diagnostic_route": name,
            "first_divergence": reason,
            "enable_only": "guard-only",
            "responsibility_unresolved": [
                "CONFIG_CONSUMPTION",
                "RTL_CONTROL",
                "OBSERVER_EVIDENCE",
            ],
            "mse4_and_formal_d_orthogonal": orthogonal,
            **extra,
        }

    if simulation["status"] != "pass" or lifecycle["start_group_count"] == 0:
        return route(
            "OBSERVER_GAP",
            "simulation/lifecycle did not provide a started guard stage",
        )
    count_checks = checkpoints.get("count_checks", {})
    if checkpoints.get("errors") or any(
        item.get("raw_equals_parsed") is not True
        for item in count_checks.values()
    ):
        return route(
            "OBSERVER_GAP",
            "readiness log has a raw/parsed or field-semantic gap",
            errors=checkpoints.get("errors", []),
        )
    fields = checkpoints.get("readiness_field_semantics", {})
    required = {
        "SFU_OPCODE_READY": ("opcode", "sfu_valid", "compute_en"),
        "SFU_GROUP_COMPUTE_VALID": ("compute_valid",),
        "SFU_LUT_INIT": ("init_en", "init_addr", "end_addr", "slice_rst"),
        "SFU_PREPROCESS0": ("enable", "valid"),
    }
    missing = [
        f"{boundary}.{field}"
        for boundary, names in required.items()
        for field in names
        if fields.get(boundary, {}).get(field, {}).get("seen_count", 0) == 0
    ]
    if missing:
        return route(
            "OBSERVER_GAP",
            "one or more required readiness fields were never sampled",
            missing_fields=missing,
        )
    opcode = fields["SFU_OPCODE_READY"]
    opcode_value_counts = opcode["opcode"].get("value_counts", {})
    exact_sfu_activation_count = int(opcode_value_counts.get("24", 0))
    unexpected_nonzero_opcode_counts = {
        key: count
        for key, count in opcode_value_counts.items()
        if int(key) not in {0, 24}
    }
    if (
        opcode["sfu_valid"]["asserted_count"] == 0
        or exact_sfu_activation_count == 0
        or unexpected_nonzero_opcode_counts
    ):
        return route(
            "OPCODE_CONFIG_CONSUMPTION",
            "odd-PE runtime opcode did not exclusively select the exact "
            "sfu_activation encoding decimal 24 / 0x18",
            opcode_fields=opcode,
            exact_sfu_activation_encoding={
                "decimal": 24,
                "hex": "0x18",
                "sample_count": exact_sfu_activation_count,
            },
            unexpected_nonzero_opcode_value_counts=(
                unexpected_nonzero_opcode_counts
            ),
        )
    lut = fields["SFU_LUT_INIT"]
    group = fields["SFU_GROUP_COMPUTE_VALID"]["compute_valid"]
    if (
        lut["init_en"]["asserted_count"] == 0
        or lut["end_addr"]["asserted_count"] == 0
        or group["asserted_count"] == 0
    ):
        return route(
            "LUT_READINESS",
            "LUT initialization/end or group compute-valid never asserted",
            lut_fields=lut,
            group_compute_valid=group,
        )
    post = fields["PE_POST_REGISTER"]
    pre0 = fields["SFU_PREPROCESS0"]
    if opcode["compute_en"]["asserted_count"] == 0:
        return route(
            "LUT_READINESS",
            "SFU opcode and LUT readiness asserted but compute_en did not",
            opcode_fields=opcode,
            group_compute_valid=group,
        )
    if any(pre0[name]["asserted_count"] == 0 for name in ("enable", "valid")):
        return route(
            "PE_REGISTER_MATCH",
            "SFU preprocess0 did not capture a valid item",
            pe_post_fields=post,
            preprocess0_fields=pre0,
        )
    post_observer_gaps = [
        f"PE_POST_REGISTER.{name}"
        for name in ("post_valid", "matched", "output_valid")
        if post.get(name, {}).get("asserted_count", 0) == 0
    ]
    if (
        lifecycle.get("status") == "pass"
        and observer.get("status") == "pass"
        and formal.get("status") == "pass"
    ):
        return {
            "classification": "GUARD_ONLY_DIAGNOSTIC_PASS",
            "diagnostic_route": None,
            "first_divergence": None,
            "enable_only": None,
            "responsibility_unresolved": [],
            "exact_sfu_activation_encoding": {
                "decimal": 24,
                "hex": "0x18",
                "sample_count": exact_sfu_activation_count,
            },
            "unexpected_nonzero_opcode_value_counts": {},
            "mse4_and_formal_d_orthogonal": orthogonal,
            "observer_only_gaps": post_observer_gaps,
            "last_proven_good": "SFU_PREPROCESS0_VALID",
        }
    return route(
        "SFU_NUMERIC_PIPELINE_UNOBSERVED",
        "SFU preprocess0 captured valid items, but the numeric SFU/ALU/"
        "normal-outbuffer path was not payload-observed before bad MSE4/formal D",
        exact_sfu_activation_encoding={
            "decimal": 24,
            "hex": "0x18",
            "sample_count": exact_sfu_activation_count,
        },
        unexpected_nonzero_opcode_value_counts={},
        observer_only_gaps=post_observer_gaps,
        last_proven_good="SFU_PREPROCESS0_VALID",
        first_unobserved="SFU_PREPROCESS0_PAYLOAD_TO_SFU_RESULT",
        downstream_bad="MSE4_WDATA_OR_FORMAL_D",
    )


def _guard_only_first_divergence(
    simulation: dict[str, Any],
    lifecycle: dict[str, Any],
    checkpoints: dict[str, Any],
    observer: dict[str, Any],
    formal: dict[str, Any],
    checkpoint_order: list[str] | tuple[str, ...] | None = None,
    diagnostic_submode: str | None = None,
) -> dict[str, Any]:
    if diagnostic_submode == "sfu_readiness":
        return _sfu_readiness_route(
            simulation, lifecycle, checkpoints, observer, formal
        )
    if simulation["status"] != "pass" or lifecycle["start_group_count"] == 0:
        return {
            "classification": "SERVER_INFRASTRUCTURE_OR_PRE_START_FAILURE",
            "first_divergence": "guard-only simulation did not naturally start",
            "enable_only": "guard-only",
        }
    default_order = (
        "MSE0_RDATA",
        "MSE0_TO_BUFFER",
        "GA_INPORT_CONFIG",
        "GA_INPORT_IB",
        "GA_CONVERT_INPUT",
        "GA_CONVERT_REGISTERED",
        "GA_INPORT_FINAL",
        "PE_SELECTED_INPUT",
        "SFU_INPUT",
        "SFU_COMPUTE",
        "SFU_LUT",
        "SFU_ALU",
        "SFU_OUTPUT",
        "NORMAL_OUTBUFFER_WRITE",
        "MSE4_WDATA",
    )
    ordered = tuple(checkpoint_order or default_order)
    previous = "NONZERO_INPUT_PRELOAD"
    pending_observer_gaps: list[dict[str, str]] = []
    upstream_observer_gaps: list[dict[str, str]] = []
    for boundary in ordered:
        count_check = checkpoints["count_checks"].get(boundary, {})
        raw = count_check.get("raw", 0)
        count = count_check.get("parsed", 0)
        expected = count_check.get("expected", 0)
        nonzero = checkpoints["nonzero_data_counts"].get(boundary, 0)
        responsibility = [
            "CONFIG_CONSUMPTION",
            "RTL_CONTROL",
            "OBSERVER_EVIDENCE",
        ]
        if count_check.get("raw_equals_parsed") is not True:
            return {
                "classification": f"{boundary}_PARSER_DIVERGENCE",
                "first_divergence": (
                    f"{boundary} raw/parsed checkpoint count differs "
                    f"({raw}/{count}) after {previous}"
                ),
                "boundary": boundary,
                "enable_only": "guard-only",
                "evidence_state": "RAW_PARSED_DIVERGENCE",
                "responsibility_unresolved": responsibility,
            }
        if count == 0:
            pending_observer_gaps.append(
                {
                    "boundary": boundary,
                    "evidence_state": "UNOBSERVED_NOT_ZERO",
                }
            )
            continue
        if expected and count != expected:
            pending_observer_gaps.append(
                {
                    "boundary": boundary,
                    "evidence_state": "PARTIAL_COVERAGE",
                    "coverage": f"{count}/{expected}",
                }
            )
            continue
        if count and nonzero == 0:
            if pending_observer_gaps:
                first_gap = pending_observer_gaps[0]["boundary"]
                return {
                    "classification": (
                        f"{first_gap}_UNOBSERVED_AFTER_{previous}"
                        f"_BEFORE_{boundary}_ALL_ZERO"
                    ),
                    "first_divergence": (
                        f"{previous} is the last observed nonzero boundary; "
                        f"{first_gap} through the boundary before {boundary} "
                        "are not fully observed, while the later "
                        f"{boundary} payload is captured all-zero"
                    ),
                    "boundary": first_gap,
                    "downstream_bad_boundary": boundary,
                    "enable_only": "guard-only",
                    "evidence_state": (
                        "BOUNDED_UNOBSERVED_INTERVAL_WITH_DOWNSTREAM_ZERO"
                    ),
                    "observer_only_gaps_before_last_proven_good": (
                        upstream_observer_gaps
                    ),
                    "bounded_observer_gaps": pending_observer_gaps,
                    "responsibility_unresolved": responsibility,
                }
            return {
                "classification": f"{boundary}_PAYLOAD_ALL_ZERO",
                "first_divergence": (
                    f"{boundary} is the first observed all-zero checkpoint "
                    f"after {previous}"
                ),
                "boundary": boundary,
                "enable_only": "guard-only",
                "evidence_state": "CAPTURED_ALL_ZERO",
                "responsibility_unresolved": responsibility,
            }
        if nonzero:
            if pending_observer_gaps:
                upstream_observer_gaps.extend(pending_observer_gaps)
                pending_observer_gaps = []
            previous = boundary
    if pending_observer_gaps:
        first_gap = pending_observer_gaps[0]["boundary"]
        return {
            "classification": f"{first_gap}_UNOBSERVED_AFTER_{previous}",
            "first_divergence": (
                f"{first_gap} produced no complete checkpoint after {previous}; "
                "absence is unobserved evidence, not an all-zero payload"
            ),
            "boundary": first_gap,
            "enable_only": "guard-only",
            "evidence_state": "UNOBSERVED_NOT_ZERO",
            "observer_only_gaps_before_last_proven_good": upstream_observer_gaps,
            "bounded_observer_gaps": pending_observer_gaps,
            "responsibility_unresolved": [
                "CONFIG_CONSUMPTION",
                "RTL_CONTROL",
                "OBSERVER_EVIDENCE",
            ],
        }
    if observer["status"] != "pass":
        return {
            "classification": "MSE4_ACCEPTED_WRITE_PAYLOAD_OR_ORDER_DIVERGENCE",
            "first_divergence": (
                "guard path remained nonzero but accepted MSE4 write did not "
                "match the frozen guard golden"
            ),
            "enable_only": "guard-only",
        }
    if formal["status"] != "pass":
        return {
            "classification": "GUARD_FORMAL_READBACK_DIVERGENCE",
            "first_divergence": (
                "accepted guard writes matched but end-of-run formal D did not"
            ),
            "enable_only": "guard-only",
        }
    if lifecycle["status"] != "pass":
        return {
            "classification": "GUARD_NATURAL_COMPLETION_DIVERGENCE",
            "first_divergence": "guard writes completed but guard stage did not finish",
            "enable_only": "guard-only",
        }
    return {
        "classification": "GUARD_ONLY_DIAGNOSTIC_PASS",
        "first_divergence": None,
        "enable_only": None,
    }


def analyze(
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    run_status: int,
) -> dict[str, Any]:
    package = package_root.resolve()
    profile = _runtime_profile(package)
    guard_only = profile["mode"] == "guard_only"
    evidence = evidence_root.resolve()
    identity_path = evidence / "stock_rtl_identity_receipt.json"
    identity = _load_json(identity_path) if identity_path.is_file() else {}
    identity_pass = (
        identity.get("status")
        == "stock_rtl_and_transactional_tb_probe_verified"
        and identity.get("functional_rtl_unchanged") is True
        and identity.get("tb_probe_transactionally_restored") is True
    )
    simulation = _simulation_gate(run_dir, install_name, run_status, profile)
    lifecycle = _lifecycle_gate(run_dir, int(profile["stage_count"]))
    observer = _observer_gate(run_dir, package, profile)
    formal = _formal_gate(run_dir, package, profile)
    checkpoints = (
        _guard_checkpoint_gate(run_dir, profile) if guard_only else None
    )
    divergence = (
        _guard_only_first_divergence(
            simulation,
            lifecycle,
            checkpoints,
            observer,
            formal,
            profile.get("checkpoint_order"),
            profile.get("diagnostic_submode"),
        )
        if guard_only
        else _first_divergence(simulation, lifecycle, observer, formal)
    )
    passed = (
        run_status == 0
        and simulation["status"] == "pass"
        and lifecycle["status"] == "pass"
        and observer["status"] == "pass"
        and formal["status"] == "pass"
        and (checkpoints is None or checkpoints["status"] == "pass")
        and identity_pass
    )
    _write_json(evidence / "LIFECYCLE_RECEIPT.json", lifecycle)
    _write_json(evidence / "MSE4_WRITE_OBSERVER_RECEIPT.json", observer)
    if checkpoints is not None:
        _write_json(evidence / "GUARD_PATH_CHECKPOINT_RECEIPT.json", checkpoints)
    _write_json(evidence / "FORMAL_READBACK_RECEIPT.json", formal)
    _write_json(evidence / "FIRST_DIVERGENCE_ROUTING.json", divergence)
    return {
        "schema": RESULT_SCHEMA,
        "status": (
            (
                "GUARD_ONLY_DIAGNOSTIC_PASS"
                if guard_only
                else "ATOMIC_COMBINED_DIAGNOSTIC_PASS"
            )
            if passed
            else (
                "GUARD_ONLY_DIAGNOSTIC_FAIL_OR_INCOMPLETE"
                if guard_only
                else "ATOMIC_COMBINED_DIAGNOSTIC_FAIL_OR_INCOMPLETE"
            )
        ),
        "classification": (
            "FIRST_DYNAMIC_RUN" if passed else "FIRST_DYNAMIC_FAILURE"
        ),
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "candidate_release": False,
        "counts_as_node0001_e4": False,
        "counts_as_node0001_e5": False,
        "formal_target_instance_allowed": False,
        "release_gate_passed": False,
        "run_exit_status": run_status,
        "gates": {
            "simulation_and_natural_exit": simulation,
            "two_stage_same_mask_lifecycle": lifecycle,
            "accepted_mse4_write_observer": observer,
            "guard_path_checkpoints": checkpoints,
            "formal_guard_and_final_readback": formal,
            "stock_rtl_and_transactional_observer_identity": {
                "status": "pass" if identity_pass else "fail",
                "functional_rtl_unchanged": identity_pass,
            },
        },
        "first_divergence_routing": divergence,
        "remaining_blockers": [
            "B_REQUANT_SERVER_E4_E5",
            "B_REQUANT_GUARD_DYNAMIC_DATA_PATH",
        ],
        "next_action": (
            (
                "guard-only localized the data path; do not enable another "
                "atomic contract without a matching adjudication"
                if guard_only
                else "keep guard-only, round-only and alias-lifetime disabled"
            )
            if passed
            else (
                f"only {divergence['enable_only']} may be considered next"
                if divergence.get("enable_only")
                else "retain the combined evidence and classify infrastructure/readback"
            )
        ),
    }


def _copy_tail(source: Path, destination: Path, limit: int = 160_000) -> None:
    if not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes()[-limit:])


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
            raise AtomicRuntimeError(f"fresh return target required: {target}")
    staging.mkdir(parents=True)
    records: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    def add(source: Path, relative_value: str, role: str, required: bool = True) -> None:
        relative = _safe_relative(relative_value)
        if set(part.lower() for part in relative.parts) & FORBIDDEN_RETURN_PARTS:
            raise AtomicRuntimeError(f"forbidden return path: {relative}")
        if relative.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise AtomicRuntimeError(f"forbidden return suffix: {relative}")
        if not source.is_file() or source.stat().st_size > MAX_RETURN_FILE_BYTES:
            if required:
                missing.append({"path": relative.as_posix(), "role": role})
            return
        target = _inside(staging, relative)
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
        "GUARD_PATH_CHECKPOINT_RECEIPT.json",
        "FORMAL_READBACK_RECEIPT.json",
        "FIRST_DIVERGENCE_ROUTING.json",
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
            name
            not in {
                "termination_signal.txt",
                "GUARD_PATH_CHECKPOINT_RECEIPT.json",
            },
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
    profile = _runtime_profile(package)
    for slice_id in ACTIVE_SLICES:
        add(
            run
            / "sim_results"
            / str(profile["observer_log_dir"])
            / f"slice{slice_id:02d}.log",
            f"raw_observer/slice{slice_id:02d}.log",
            "small_same_clock_observer",
            False,
        )
        add(
            run / f"sim_results/sem_events/slice{slice_id}/sem_events.log",
            f"raw_lifecycle/slice{slice_id:02d}.log",
            "small_lifecycle_log",
            False,
        )
    sca_d = _load_json(package / "workload/runtime/sca_cfg_D.json")
    for name, item in sca_d.items():
        add(
            _inside(run, item["path"]),
            f"raw_formal_readback/{name}.txt",
            "small_formal_readback",
            False,
        )
    _copy_tail(run / "sim_results/compile.log", staging / "logs/compile_tail.log")
    _copy_tail(
        run / "sim_results/compile_driver.log",
        staging / "logs/compile_driver_tail.log",
    )
    _copy_tail(run / "sim_results/sim.log", staging / "logs/sim_tail.log")
    for name in ("compile_tail.log", "compile_driver_tail.log", "sim_tail.log"):
        path = staging / "logs" / name
        if path.is_file():
            records.append(
                {
                    "path": f"logs/{name}",
                    "role": "bounded_log_tail",
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )

    gate_path = evidence / "SERVER_RESULT_GATE.json"
    gate = _load_json(gate_path) if gate_path.is_file() else {}
    receipt = {
        "schema": RETURN_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if not missing else "incomplete",
        "server_result_status": gate.get("status", "missing"),
        "classification": gate.get("classification", "FIRST_DYNAMIC_FAILURE"),
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "install_name": install_name,
        "candidate_release": False,
        "counts_as_node0001_e4": False,
        "counts_as_node0001_e5": False,
        "run_exit_status": run_status,
        "server_command": server_command,
        "allowlist_only": True,
        "small_raw_observer_and_formal_readback_included": True,
        "waveforms_included": False,
        "build_tree_included": False,
        "nested_archive_included": False,
        "required_missing": missing,
        "payload_file_count": len(records),
        "payload_size_bytes": sum(item["size_bytes"] for item in records),
        "files": sorted(records, key=lambda item: item["path"]),
    }
    _write_json(staging / "RETURN_RECEIPT.json", receipt)
    extracted = sum(path.stat().st_size for path in staging.rglob("*") if path.is_file())
    if extracted > MAX_RETURN_EXTRACTED_BYTES:
        raise AtomicRuntimeError("return extracted size exceeds 4 MiB")
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
        raise AtomicRuntimeError("return ZIP exceeds 2 MiB")
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
    package_parser = sub.add_parser("preflight-package")
    package_parser.add_argument("--package-root", type=Path, required=True)
    package_parser.add_argument("--install-name", required=True)
    package_parser.add_argument("--output", type=Path, required=True)
    installed_parser = sub.add_parser("preflight-installed")
    installed_parser.add_argument("--package-root", type=Path, required=True)
    installed_parser.add_argument("--ndp-root", type=Path, required=True)
    installed_parser.add_argument("--install-name", required=True)
    installed_parser.add_argument("--output", type=Path, required=True)
    analyze_parser = sub.add_parser("analyze")
    analyze_parser.add_argument("--package-root", type=Path, required=True)
    analyze_parser.add_argument("--install-name", required=True)
    analyze_parser.add_argument("--evidence-root", type=Path, required=True)
    analyze_parser.add_argument("--run-dir", type=Path, required=True)
    analyze_parser.add_argument("--run-status", type=int, required=True)
    analyze_parser.add_argument("--output", type=Path, required=True)
    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("--ndp-root", type=Path, required=True)
    collect_parser.add_argument("--package-root", type=Path, required=True)
    collect_parser.add_argument("--install-name", required=True)
    collect_parser.add_argument("--evidence-root", type=Path, required=True)
    collect_parser.add_argument("--run-dir", type=Path, required=True)
    collect_parser.add_argument("--run-status", type=int, required=True)
    collect_parser.add_argument("--server-command", required=True)
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
            if report["status"] not in {
                "ATOMIC_COMBINED_DIAGNOSTIC_PASS",
                "GUARD_ONLY_DIAGNOSTIC_PASS",
            }:
                print(json.dumps(report, ensure_ascii=False, indent=2))
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
        print(f"Requant atomic runtime failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
