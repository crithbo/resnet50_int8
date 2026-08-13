#!/usr/bin/env python3
"""Package-local runtime for the node0071 -> node0075 diagnostic package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

sys.dont_write_bytecode = True

MANIFEST_NAME = "TEST_PACKAGE_MANIFEST.json"
BITS128 = re.compile(rb"[01]{128}")
A_EVENT_RE = re.compile(
    r"^N75_A_REQ_V1 stage=(\d+) pass=(\d+) slice=(\d+) "
    r"channel=(\d+) ordinal=(\d+) addr=0x([0-9a-fA-F]+)$"
)
CANONICAL_RE = re.compile(
    r"^N75_CANONICAL_DECISION_V2 decision=(\S+) reason=(\S+) boundary=(\S+) "
    r"sample_begin=(\d+) sample_end=(\d+) stage_start=(\d+) stage_finish=(\d+) "
    r"slice_finish_total=(\d+) producer_req=(\d+) producer_wdata=(\d+) "
    r"producer_finish=(\d+) first_a_cycle=(\d+) first_a_order_ok=(\d+) "
    r"a_req=(\d+) a_data=(\d+) a_event_lines=(\d+)$"
)


class RuntimeErrorIntegration(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeErrorIntegration(f"cannot parse JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeErrorIntegration(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_relative(raw: str, label: str) -> PurePosixPath:
    posix = PurePosixPath(raw)
    windows = PureWindowsPath(raw)
    if (
        not raw
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.anchor)
        or "\\" in raw
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise RuntimeErrorIntegration(f"unsafe {label}: {raw!r}")
    return posix


def resolve_inside(root: Path, raw: str, label: str) -> Path:
    relative = safe_relative(raw, label)
    target = root.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeErrorIntegration(f"{label} escapes root: {raw}") from exc
    return target


def file_records(root: Path, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = exclude or set()
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeErrorIntegration(f"symlink forbidden: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        records.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return records


def _record_map(records: Any, label: str) -> dict[str, tuple[int, str]]:
    if not isinstance(records, list):
        raise RuntimeErrorIntegration(f"{label} is not a list")
    result: dict[str, tuple[int, str]] = {}
    for item in records:
        if not isinstance(item, dict):
            raise RuntimeErrorIntegration(f"{label} record is not an object")
        raw = str(item.get("path", ""))
        safe_relative(raw, f"{label} path")
        size = item.get("size_bytes")
        digest = str(item.get("sha256", ""))
        if (
            raw in result
            or not isinstance(size, int)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise RuntimeErrorIntegration(f"invalid {label} record: {raw}")
        result[raw] = (size, digest)
    return result


def _validate_records(
    root: Path,
    records: Any,
    label: str,
    extra: set[str] | None = None,
) -> None:
    expected = _record_map(records, label)
    actual = {
        item["path"]: (item["size_bytes"], item["sha256"])
        for item in file_records(root, exclude=extra)
    }
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        differing = sorted(
            path
            for path in set(actual) & set(expected)
            if actual[path] != expected[path]
        )
        raise RuntimeErrorIntegration(
            f"{label} exact tree differs: missing={missing[:4]} "
            f"unexpected={unexpected[:4]} differing={differing[:4]}"
        )


def _return_allowlist_records(
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    contract = manifest.get("return_allowlist")
    if (
        not isinstance(contract, dict)
        or contract.get("schema")
        != "node0071-node0075-native-ordering-return-allowlist-v1"
        or contract.get("generated_members")
        != ["RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"]
        or not isinstance(contract.get("records"), list)
        or len(contract["records"]) != 162
    ):
        raise RuntimeErrorIntegration("return allowlist contract differs")
    destinations: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(contract["records"]):
        if not isinstance(raw, dict) or set(raw) != {
            "destination",
            "source_scope",
            "source_path",
            "required",
            "max_bytes",
            "missing_semantics",
            "copy_mode",
        }:
            raise RuntimeErrorIntegration(
                f"return allowlist record schema differs: {index}"
            )
        destination = safe_relative(
            str(raw["destination"]), "return destination"
        ).as_posix()
        source_path = safe_relative(
            str(raw["source_path"]), "return source"
        ).as_posix()
        if (
            destination in destinations
            or raw["source_scope"]
            not in {"package", "evidence", "run", "server"}
            or not isinstance(raw["required"], bool)
            or not isinstance(raw["max_bytes"], int)
            or raw["max_bytes"] <= 0
            or not isinstance(raw["missing_semantics"], str)
            or not raw["missing_semantics"]
            or raw["copy_mode"] not in {"exact", "head_tail"}
        ):
            raise RuntimeErrorIntegration(
                f"return allowlist record invalid: {index}"
            )
        destinations.add(destination)
        normalized.append(
            {
                **raw,
                "destination": destination,
                "source_path": source_path,
            }
        )
    if sum(item["source_scope"] == "server" for item in normalized) != 144:
        raise RuntimeErrorIntegration("formal D return allowlist count differs")
    return normalized


def _validate_128bit_text(path: Path, expected_lines: int | None = None) -> int:
    count = 0
    with path.open("rb") as stream:
        for count, raw in enumerate(stream, 1):
            if not raw.endswith(b"\n") or not BITS128.fullmatch(raw[:-1]):
                raise RuntimeErrorIntegration(
                    f"invalid 128-bit text ABI: {path}:{count}"
                )
    if count == 0 or (expected_lines is not None and count != expected_lines):
        raise RuntimeErrorIntegration(f"128-bit line count differs: {path}: {count}")
    return count


def _installed_payload(package_root: Path, manifest: dict[str, Any], raw: str) -> Path:
    relative = safe_relative(raw, "SCA installed path")
    marker = ("install", "cfg_pkg", str(manifest["install_name"]))
    if tuple(relative.parts[:3]) != marker:
        raise RuntimeErrorIntegration(f"SCA namespace differs: {raw}")
    return package_root / "workload" / Path(*relative.parts[3:])


def preflight(package_root: Path) -> dict[str, Any]:
    package_root = package_root.resolve()
    manifest = load_json(package_root / MANIFEST_NAME)
    if (
        manifest.get("status") != "PACKAGE_READY_NOT_RUN"
        or manifest.get("candidate_release") is not False
        or manifest.get("functional_rtl_modified") is not False
        or manifest.get("functional_rtl_file_count") != 0
        or manifest.get("diagnostic_only") is not True
        or manifest.get("explicit_barrier_claim") is not False
    ):
        raise RuntimeErrorIntegration("package release boundary differs")
    _validate_records(
        package_root,
        manifest.get("files"),
        "package files",
        {MANIFEST_NAME},
    )
    if any(
        path.name == "__pycache__" or path.suffix == ".pyc"
        for path in package_root.rglob("*")
    ):
        raise RuntimeErrorIntegration("Python bytecode forbidden in package")
    _validate_records(
        package_root / "workload",
        manifest.get("workload_files"),
        "workload files",
    )
    observer = package_root / str(manifest["observer"]["path"])
    if (
        not observer.is_file()
        or observer.stat().st_size != manifest["observer"]["size_bytes"]
        or sha256(observer) != manifest["observer"]["sha256"]
    ):
        raise RuntimeErrorIntegration("observer identity differs")
    runner = (package_root / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    required_runner_tokens = [
        "export PYTHONDONTWRITEBYTECODE=1",
        "+define+NATIVE_RETURN_OBSERVER_ENABLE",
        "+incdir+$package_root/obs",
        "+RETURN_OBSERVER",
        "+N75_NATIVE_ORDERING",
        "+N75_A_EVENT_LIMIT=9000",
        "+SCA_CFG=install/cfg_pkg/$install_name/sca_cfg.json",
        "+SCA_CFG_D=install/cfg_pkg/$install_name/sca_cfg_D.json",
    ]
    if not all(token in runner for token in required_runner_tokens):
        raise RuntimeErrorIntegration("runner binding token missing")
    forbidden_runner_tokens = [
        "git rev-parse",
        "README_HARDWARE",
        "rtl/filelists",
        "tb_NDP_Top_new_phy.sv",
    ]
    if any(token in runner for token in forbidden_runner_tokens):
        raise RuntimeErrorIntegration("runner performs server-source preflight")
    return_allowlist = _return_allowlist_records(manifest)
    for item in return_allowlist:
        if item["source_scope"] != "package":
            continue
        source = resolve_inside(
            package_root, item["source_path"], "package return source"
        )
        if (
            not source.is_file()
            or source.stat().st_size > int(item["max_bytes"])
        ):
            raise RuntimeErrorIntegration(
                "package return allowlist source differs"
            )

    workload = package_root / "workload"
    sca = load_json(workload / "sca_cfg.json")
    sca_d = load_json(workload / "sca_cfg_D.json")
    if (
        sca.get("Exec_Base") != "0x01706400"
        or sca.get("Exec_Length") != 518
        or sca.get("Repeat_Num") != 32
    ):
        raise RuntimeErrorIntegration("SCA execution counts differ")
    dynamic = {
        key: value
        for key, value in sca.items()
        if key not in {"Exec_Base", "Exec_Length", "Repeat_Num", "ExecutionPlan"}
    }
    inputs = [key for key in dynamic if key.startswith("n71_i")]
    configs = [key for key in dynamic if key.endswith("_cfg")]
    b_items = [key for key in dynamic if key.startswith("n75_b")]
    a_items = [
        key
        for key in dynamic
        if "matrixa" in key.lower()
        or key.lower().startswith("n75_a_preload")
    ]
    if (
        len(inputs) != 16
        or len(configs) != 32
        or len(b_items) != 128
        or a_items
        or len(sca_d) != 144
    ):
        raise RuntimeErrorIntegration("SCA transfer cardinality differs")
    for key, item in {**dynamic, "ExecutionPlan": sca["ExecutionPlan"]}.items():
        if not isinstance(item, dict) or set(item) != {"base_addr", "path"}:
            raise RuntimeErrorIntegration(f"SCA leaf differs: {key}")
        payload = _installed_payload(package_root, manifest, str(item["path"]))
        if not payload.is_file():
            raise RuntimeErrorIntegration(f"SCA payload missing: {key}")
        if key.startswith("n75_b"):
            _validate_128bit_text(payload, 16384)
    runtime_prefix = f"run_{manifest['install_name']}/formal_d/"
    for key, item in sca_d.items():
        if set(item) != {"base_addr", "length", "path"}:
            raise RuntimeErrorIntegration(f"SCA_D leaf differs: {key}")
        expected_length = 128 if key.startswith("n71_d") else 8
        if item["length"] != expected_length:
            raise RuntimeErrorIntegration(f"SCA_D length differs: {key}")
        raw = str(item["path"])
        if not raw.startswith(runtime_prefix):
            raise RuntimeErrorIntegration(f"SCA_D runtime namespace differs: {raw}")
        if (package_root / raw).exists():
            raise RuntimeErrorIntegration("runtime D target is preseeded")

    checks = manifest.get("readback_checks")
    if not isinstance(checks, list) or len(checks) != 144:
        raise RuntimeErrorIntegration("formal readback contract count differs")
    runtime_paths: set[str] = set()
    for item in checks:
        raw_runtime = str(item["runtime_path"])
        if raw_runtime in runtime_paths or not raw_runtime.startswith(runtime_prefix):
            raise RuntimeErrorIntegration("readback runtime path collision")
        runtime_paths.add(raw_runtime)
        golden = resolve_inside(package_root, str(item["golden_path"]), "golden")
        if (
            golden.stat().st_size != item["size_bytes"]
            or sha256(golden) != item["sha256"]
        ):
            raise RuntimeErrorIntegration("golden identity differs")
        _validate_128bit_text(golden, int(item["line_count_128bit"]))
    return {
        "status": "PACKAGE_PREFLIGHT_PASS",
        "package_manifest_sha256": sha256(package_root / MANIFEST_NAME),
        "package_file_count": len(manifest["files"]) + 1,
        "workload_file_count": len(manifest["workload_files"]),
        "external_input_count": len(inputs),
        "config_preload_count": len(configs),
        "b_preload_destination_count": len(b_items),
        "a_preload_count": len(a_items),
        "formal_readback_count": len(sca_d),
        "return_allowlist_record_count": len(return_allowlist),
        "runtime_d_absent": True,
    }


def verify_install(
    package_root: Path,
    cfg_root: Path,
) -> dict[str, Any]:
    package_root = package_root.resolve()
    cfg_root = cfg_root.resolve()
    manifest = load_json(package_root / MANIFEST_NAME)
    _validate_records(
        cfg_root,
        manifest.get("workload_files"),
        "installed workload",
    )
    sca = load_json(cfg_root / "sca_cfg.json")
    for key, item in sca.items():
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        relative = PurePosixPath(item["path"]).relative_to(
            "install", "cfg_pkg", manifest["install_name"]
        )
        expected = cfg_root.joinpath(*relative.parts)
        if not expected.is_file():
            raise RuntimeErrorIntegration(
                f"installed SCA payload missing: {key}: {expected}"
            )
    return {
        "status": "INSTALLED_WORKLOAD_PREFLIGHT_PASS",
        "installed_file_count": len(manifest["workload_files"]),
        "installed_exact_tree": True,
    }


def prepare_run(
    package_root: Path,
    server_root: Path,
    run_root: Path,
) -> dict[str, Any]:
    package_root = package_root.resolve()
    server_root = server_root.resolve()
    run_root = run_root.resolve()
    manifest = load_json(package_root / MANIFEST_NAME)
    targets: list[str] = []
    for item in manifest["readback_checks"]:
        target = resolve_inside(server_root, str(item["runtime_path"]), "runtime D")
        try:
            target.relative_to(run_root)
        except ValueError as exc:
            raise RuntimeErrorIntegration("runtime D target escapes run root") from exc
        if target.exists():
            raise RuntimeErrorIntegration(f"runtime D target is preseeded: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        targets.append(str(target))
    return {
        "status": "RUNTIME_D_ABSENT_PRE_SIM_PASS",
        "target_count": len(targets),
        "all_absent": True,
        "targets_sha256": canonical_sha256(targets),
    }


def _status(path: Path) -> int:
    try:
        return int(path.read_text(encoding="ascii").strip())
    except Exception:
        return 125


def _parse_canonical(observer: str) -> tuple[dict[str, Any] | None, int]:
    records: list[dict[str, Any]] = []
    names = (
        "sample_begin",
        "sample_end",
        "stage_start",
        "stage_finish",
        "slice_finish_total",
        "producer_req",
        "producer_wdata",
        "producer_finish",
        "first_a_cycle",
        "first_a_order_ok",
        "a_req",
        "a_data",
        "a_event_lines",
    )
    lines = observer.splitlines()
    candidate_indexes: list[int] = []
    for line_index, line in enumerate(lines):
        if line.startswith("N75_CANONICAL_DECISION_V2 "):
            candidate_indexes.append(line_index)
        match = CANONICAL_RE.fullmatch(line)
        if not match:
            continue
        values = match.groups()
        record: dict[str, Any] = {
            "decision": values[0],
            "reason": values[1],
            "boundary": values[2],
        }
        record.update(
            {name: int(value) for name, value in zip(names, values[3:])}
        )
        records.append(record)
    late_summary = bool(
        candidate_indexes
        and any(
            line.startswith("N75_SNAPSHOT_V2 kind=FINAL_SUMMARY ")
            for line in lines[candidate_indexes[-1] + 1 :]
        )
    )
    candidate_count = len(candidate_indexes) + int(late_summary)
    unique = (
        len(candidate_indexes) == 1
        and len(records) == 1
        and not late_summary
    )
    return (records[0] if unique else None), candidate_count


def _analyze_a_events(
    observer: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    events: list[dict[str, int]] = []
    for line in observer.splitlines():
        match = A_EVENT_RE.fullmatch(line)
        if not match:
            continue
        stage, pass_index, slice_id, channel, ordinal, address = match.groups()
        events.append(
            {
                "stage": int(stage),
                "pass_index": int(pass_index),
                "slice_id": int(slice_id),
                "channel": int(channel),
                "ordinal": int(ordinal),
                "address": int(address, 16),
            }
        )
    expected = manifest["a_coverage"]["passes"]
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for pass_index in range(8):
        expected_pass = expected[pass_index]
        for slice_id in range(16):
            subset = [
                item
                for item in events
                if item["pass_index"] == pass_index and item["slice_id"] == slice_id
            ]
            addresses = [item["address"] for item in subset]
            byte_set = sorted(
                {
                    byte
                    for address in addresses
                    for byte in range(address, address + 32)
                }
            )
            expected_slice = expected_pass["slice_records"][slice_id]
            ordered_hash = canonical_sha256(addresses)
            byte_set_hash = canonical_sha256(byte_set)
            if len(subset) != 64:
                errors.append(f"pass{pass_index:02d}/slice{slice_id:02d}:count")
            if ordered_hash != expected_slice["ordered_address_sha256"]:
                errors.append(f"pass{pass_index:02d}/slice{slice_id:02d}:order")
            if byte_set_hash != expected_slice["read_byte_set_sha256"]:
                errors.append(f"pass{pass_index:02d}/slice{slice_id:02d}:byteset")
            records.append(
                {
                    "pass_index": pass_index,
                    "slice_id": slice_id,
                    "event_count": len(subset),
                    "ordered_address_sha256": ordered_hash,
                    "read_byte_set_sha256": byte_set_hash,
                    "first_address": (
                        f"0x{addresses[0]:08x}" if addresses else None
                    ),
                    "last_address": (
                        f"0x{addresses[-1]:08x}" if addresses else None
                    ),
                }
            )
    unique_bytes = {
        byte
        for item in events
        for byte in range(item["address"], item["address"] + 32)
    }
    return {
        "event_count": len(events),
        "accepted_traffic_bytes": len(events) * 32,
        "unique_byte_count": len(unique_bytes),
        "pass_slice_record_count": len(records),
        "records": records,
        "errors": errors,
        "passed": (
            len(events) == 8192
            and len(unique_bytes) == 32768
            and len(records) == 128
            and not errors
        ),
    }


def analyze(
    package_root: Path,
    server_root: Path,
    run_root: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    package_root = package_root.resolve()
    server_root = server_root.resolve()
    run_root = run_root.resolve()
    evidence_root = evidence_root.resolve()
    manifest = load_json(package_root / MANIFEST_NAME)
    compile_status = _status(evidence_root / "compile_exit_status.txt")
    run_status = _status(evidence_root / "run_exit_status.txt")
    signal = (
        (evidence_root / "signal_status.txt").read_text(encoding="ascii").strip()
        if (evidence_root / "signal_status.txt").is_file()
        else "MISSING"
    )
    sim_log_path = run_root / "sim.log"
    observer_path = run_root / "return_observer.log"
    sim_log = (
        sim_log_path.read_text(encoding="utf-8", errors="replace")
        if sim_log_path.is_file()
        else ""
    )
    observer = (
        observer_path.read_text(encoding="utf-8", errors="replace")
        if observer_path.is_file()
        else ""
    )
    cfg_rel = f"install/cfg_pkg/{manifest['install_name']}"
    canonical, canonical_count = _parse_canonical(observer)
    a_events = _analyze_a_events(observer, manifest)
    observer_gate = bool(
        canonical
        and canonical["decision"] == "EXPECTED_32_STAGE_NATIVE_ORDER_COMPLETE"
        and canonical["reason"] == "all_required_qualified_counts_exact"
        and canonical["boundary"]
        == "node0071_stage08_hub_accept_to_node0075_pass00_first_read"
        and canonical["stage_start"] == 32
        and canonical["stage_finish"] == 32
        and canonical["slice_finish_total"] == 512
        and canonical["producer_req"] == 1024
        and canonical["producer_wdata"] == 1024
        and canonical["producer_finish"] == 16
        and canonical["first_a_order_ok"] == 1
        and canonical["a_req"] == 8192
        and canonical["a_data"] == 8192
        and canonical["a_event_lines"] == 8192
    )
    marker_checks = {
        "sca_echo": f"Using SCA cfg file: {cfg_rel}/sca_cfg.json" in sim_log,
        "sca_d_echo": f"Using SCA cfg D file: {cfg_rel}/sca_cfg_D.json" in sim_log,
        "natural_terminal": "Simulation completed successfully!" in sim_log,
        "formal_dump_count": bool(
            re.search(r"JSON_D config:\s*144 matrices dumped", sim_log)
        ),
        "no_timeout": "Simulation aborted due to timeout!" not in sim_log,
        "no_sca_open_failure": (
            "Cannot open" not in sim_log and "skip matrix readback" not in sim_log
        ),
        "observer_enabled": (
            "N75_FEATURE_ENABLE_V2 feature=NATIVE_ORDERING enabled=1" in observer
        ),
        "canonical_unique": canonical_count == 1,
        "observer_gate": observer_gate,
        "a_event_gate": a_events["passed"],
    }

    missing: list[str] = []
    mismatches: list[str] = []
    actual_records: list[dict[str, Any]] = []
    for item in manifest["readback_checks"]:
        runtime_path = resolve_inside(
            server_root, str(item["runtime_path"]), "runtime D"
        )
        golden = resolve_inside(package_root, str(item["golden_path"]), "golden")
        if not runtime_path.is_file():
            missing.append(str(item["runtime_path"]))
            continue
        try:
            lines = _validate_128bit_text(
                runtime_path, int(item["line_count_128bit"])
            )
        except RuntimeErrorIntegration:
            mismatches.append(str(item["runtime_path"]) + ":ABI")
            continue
        if runtime_path.read_bytes() != golden.read_bytes():
            mismatches.append(str(item["runtime_path"]))
        actual_records.append(
            {
                "runtime_path": str(item["runtime_path"]),
                "size_bytes": runtime_path.stat().st_size,
                "sha256": sha256(runtime_path),
                "line_count_128bit": lines,
            }
        )
    conjunction = (
        compile_status == 0
        and run_status == 0
        and signal == "NONE"
        and all(marker_checks.values())
        and not missing
        and not mismatches
        and len(actual_records) == 144
    )
    result = {
        "schema": "node0071-node0075-native-ordering-server-result-gate-v1",
        "status": (
            "SERVER_DYNAMIC_DIAGNOSTIC_PASS"
            if conjunction
            else "SERVER_DYNAMIC_FAIL_OR_INCOMPLETE"
        ),
        "passed": conjunction,
        "candidate_release": False,
        "diagnostic_only": True,
        "explicit_barrier_claim": False,
        "compile_exit_status": compile_status,
        "run_exit_status": run_status,
        "signal_status": signal,
        "marker_checks": marker_checks,
        "canonical_record_count": canonical_count,
        "canonical_record": canonical,
        "a_consumer_actual_acceptance": a_events,
        "formal_readback_expected_count": 144,
        "formal_readback_actual_count": len(actual_records),
        "missing_count": len(missing),
        "mismatch_count": len(mismatches),
        "missing": missing,
        "mismatches": mismatches,
        "actual_readbacks": actual_records,
        "server_source_identity_bound": False,
        "evidence_level_if_passed": (
            "DYNAMIC_DIAGNOSTIC_ONLY_NO_EXPLICIT_BARRIER_NO_SERVER_SOURCE_IDENTITY"
        ),
        "failure_classification": (
            None
            if conjunction
            else "INSTANCE_SCHEDULING_OR_ORDERING_FIRST_NOT_AUTOMATIC_RTL"
        ),
        "result_gate_conjunction": conjunction,
    }
    write_json(evidence_root / "SERVER_RESULT_GATE.json", result)
    return result


def _copy_limited(source: Path, target: Path, limit: int) -> bool:
    if not source.is_file():
        return False
    payload = source.read_bytes()
    if len(payload) > limit:
        half = max(1, (limit - 64) // 2)
        payload = (
            payload[:half]
            + b"\n...TRUNCATED_HEAD_TAIL...\n"
            + payload[-half:]
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return True


def _deterministic_zip(root: Path, destination: Path) -> None:
    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = f"{root.name}/{path.relative_to(root).as_posix()}"
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


def collect(
    package_root: Path,
    server_root: Path,
    run_root: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    package_root = package_root.resolve()
    server_root = server_root.resolve()
    run_root = run_root.resolve()
    evidence_root = evidence_root.resolve()
    manifest = load_json(package_root / MANIFEST_NAME)
    return_root = server_root / str(manifest["return_directory"])
    return_zip = server_root / str(manifest["return_zip"])
    sidecar = Path(str(return_zip) + ".sha256")
    if return_root.exists() or return_zip.exists() or sidecar.exists():
        raise RuntimeErrorIntegration("return namespace must be fresh")
    return_root.mkdir(parents=True)

    copied: list[str] = []
    readback_count = 0
    source_roots = {
        "package": package_root,
        "evidence": evidence_root,
        "run": run_root,
        "server": server_root,
    }
    allowlist = _return_allowlist_records(manifest)
    for item in allowlist:
        source = resolve_inside(
            source_roots[str(item["source_scope"])],
            str(item["source_path"]),
            "allowlisted return source",
        )
        if not source.is_file():
            if item["required"]:
                raise RuntimeErrorIntegration(
                    "required return source missing: "
                    + str(item["source_path"])
                )
            continue
        target = resolve_inside(
            return_root,
            str(item["destination"]),
            "allowlisted return destination",
        )
        if item["copy_mode"] == "head_tail":
            _copy_limited(source, target, int(item["max_bytes"]))
        else:
            if source.stat().st_size > int(item["max_bytes"]):
                raise RuntimeErrorIntegration(
                    "allowlisted return source exceeds budget: "
                    + str(item["source_path"])
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        copied.append(str(item["destination"]))
        if item["source_scope"] == "server":
            readback_count += 1

    write_json(
        return_root / "RETURN_ALLOWLIST.json",
        {
            "schema": "node0071-node0075-native-ordering-return-allowlist-v1",
            "copied_exact_set": sorted(copied),
            "formal_readback_count": readback_count,
            "manifest_allowlist_record_count": len(allowlist),
            "forbidden": [
                "csrc",
                "simv",
                "simv.daidir",
                "waveform",
                "nested archive",
            ],
        },
    )
    return_manifest = {
        "schema": "node0071-node0075-native-ordering-return-manifest-v1",
        "source_package_manifest_sha256": sha256(package_root / MANIFEST_NAME),
        "files": file_records(return_root, {"RETURN_MANIFEST.json"}),
    }
    write_json(return_root / "RETURN_MANIFEST.json", return_manifest)
    _deterministic_zip(return_root, return_zip)
    digest = sha256(return_zip)
    sidecar.write_text(
        f"{digest}  {return_zip.name}\n",
        encoding="ascii",
        newline="\n",
    )
    return {
        "status": "RETURN_PACKAGE_CREATED",
        "return_zip": str(return_zip),
        "return_zip_sha256": digest,
        "sidecar": str(sidecar),
        "file_count": len(return_manifest["files"]) + 1,
        "formal_readback_count": readback_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("preflight")
    command.add_argument("--package-root", type=Path, required=True)
    command = sub.add_parser("verify-install")
    command.add_argument("--package-root", type=Path, required=True)
    command.add_argument("--cfg-root", type=Path, required=True)
    command = sub.add_parser("prepare-run")
    command.add_argument("--package-root", type=Path, required=True)
    command.add_argument("--server-root", type=Path, required=True)
    command.add_argument("--run-root", type=Path, required=True)
    command = sub.add_parser("analyze")
    command.add_argument("--package-root", type=Path, required=True)
    command.add_argument("--server-root", type=Path, required=True)
    command.add_argument("--run-root", type=Path, required=True)
    command.add_argument("--evidence-root", type=Path, required=True)
    command = sub.add_parser("collect")
    command.add_argument("--package-root", type=Path, required=True)
    command.add_argument("--server-root", type=Path, required=True)
    command.add_argument("--run-root", type=Path, required=True)
    command.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            result = preflight(args.package_root)
        elif args.command == "verify-install":
            result = verify_install(args.package_root, args.cfg_root)
        elif args.command == "prepare-run":
            result = prepare_run(args.package_root, args.server_root, args.run_root)
        elif args.command == "analyze":
            result = analyze(
                args.package_root,
                args.server_root,
                args.run_root,
                args.evidence_root,
            )
        else:
            result = collect(
                args.package_root,
                args.server_root,
                args.run_root,
                args.evidence_root,
            )
    except Exception as exc:
        print(f"NATIVE_ORDERING_RUNTIME_FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if args.command == "analyze" and not result.get("passed", False):
        return 20
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
