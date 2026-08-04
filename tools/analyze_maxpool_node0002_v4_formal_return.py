from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURN_ROOT = "r5_n2_maxpool_native_reuse_v4_return"
SOURCE_ROOT = "r5_n2_maxpool_native_reuse_v4"
INSTALL_NAME = "r5_n2_maxpool_native_reuse_v4"
RETURN_BYTES = 71_129
RETURN_SHA256 = "350be6952bdb0135c9fd3c428494abf5461f9c7195cba662726923be3c1cbce6"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n2_maxpool_native_reuse_v4.zip"
)
SOURCE_BYTES = 1_496_952
SOURCE_SHA256 = "f2df61c2edd9459f872dc930312fa3cecb30d72ecd284760fbbc534d5f5dd6a0"
SOURCE_TASK_RECORD = (
    ROOT / ".agents/task_records/20260802_maxpool_node0002_native_json_reuse_v4_package.md"
)
SOURCE_TASK_RECORD_SHA256 = (
    "e40cf82bd0cd031d31f1d61a6d24c6ed4257a369c9b672889e1b3ac858467935"
)
SOURCE_MACHINE_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/maxpool-node0002-native-reuse-v4/"
    "report.json"
)
SOURCE_MACHINE_REPORT_SHA256 = (
    "ed08a5915497400c32dae152ae56071464313e6bb8aa9f3f7114e25c600bd2c9"
)
PLAN = ROOT / ".agents/plan.md"
PLAN_SHA256 = "11d8a61ae403ad223fe1ab35cd6250d24aafecc0b7c8dab4fc6770aa0d845c94"
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
SERVER_RULE_DISPATCH_SHA256 = (
    "1e0b40589dddee3bf2b4d081936d37d9a25f78ea2ceb98bc08f2dcf813438589"
)
ANALYSIS_OWNER_THREAD = "019fbe9f-3f2d-7071-806c-1ae72ae96391"
RETURN_TARGET_THREAD = "019fbec2-fe93-7e03-9314-cff6f222f33d"
EXPECTED_STAGES = (
    "op-native-maxpool-slice0",
    "op-native-maxpool-slice1",
)


class AnalysisError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(path: Path, expected_root: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    total_uncompressed = 0
    member_count = 0
    directory_count = 0
    with zipfile.ZipFile(path) as archive:
        bad_crc = archive.testzip()
        if bad_crc is not None:
            raise AnalysisError(f"ZIP CRC differs: {bad_crc}")
        prefix = f"{expected_root}/"
        for info in archive.infolist():
            member_count += 1
            pure = PurePosixPath(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
            ):
                raise AnalysisError(f"unsafe ZIP member: {info.filename}")
            if info.is_dir():
                directory_count += 1
                continue
            if not info.filename.startswith(prefix):
                raise AnalysisError(f"member outside bound root: {info.filename}")
            relative = info.filename[len(prefix) :]
            if not relative or relative in files:
                raise AnalysisError(f"empty/duplicate ZIP member: {info.filename}")
            payload = archive.read(info)
            if len(payload) != info.file_size:
                raise AnalysisError(f"member size differs: {info.filename}")
            files[relative] = payload
            total_uncompressed += len(payload)
    if roots != {expected_root}:
        raise AnalysisError(f"ZIP root exact-set differs: {sorted(roots)}")
    return files, {
        "crc_valid": True,
        "single_exact_root": True,
        "root": expected_root,
        "archive_member_count": member_count,
        "directory_member_count": directory_count,
        "file_count": len(files),
        "uncompressed_bytes": total_uncompressed,
        "duplicate_member_count": 0,
        "symlink_member_count": 0,
        "unsafe_path_count": 0,
    }


def json_object(files: dict[str, bytes], path: str) -> dict[str, Any]:
    try:
        value = json.loads(files[path])
    except KeyError as exc:
        raise AnalysisError(f"required ZIP member missing: {path}") from exc
    if not isinstance(value, dict):
        raise AnalysisError(f"{path} is not a JSON object")
    return value


def text(files: dict[str, bytes], path: str) -> str:
    try:
        return files[path].decode("utf-8", errors="replace")
    except KeyError as exc:
        raise AnalysisError(f"required ZIP member missing: {path}") from exc


def parse_int_file(files: dict[str, bytes], path: str) -> int:
    return int(text(files, path).strip())


def parse_fields(line: str) -> dict[str, str]:
    return dict(re.findall(r"\b([A-Za-z0-9_]+)=([^\s|]+)", line))


def manifest_audit(
    returned: dict[str, bytes],
    return_manifest: dict[str, Any],
    source_manifest: dict[str, Any],
) -> dict[str, Any]:
    records = return_manifest.get("files")
    if not isinstance(records, list):
        raise AnalysisError("RETURN_MANIFEST files is not a list")
    expected_records: dict[str, dict[str, Any]] = {}
    record_errors: list[str] = []
    for item in records:
        if not isinstance(item, dict):
            record_errors.append("non-object return record")
            continue
        path = str(item.get("path", ""))
        if not path or path in expected_records:
            record_errors.append(f"empty/duplicate return record: {path}")
            continue
        expected_records[path] = item
        payload = returned.get(path)
        if payload is None:
            record_errors.append(f"returned record missing: {path}")
            continue
        if len(payload) != item.get("size_bytes"):
            record_errors.append(f"returned size differs: {path}")
        if sha256_bytes(payload) != item.get("sha256"):
            record_errors.append(f"returned SHA differs: {path}")
    exact_expected = {"RETURN_MANIFEST.json", *expected_records}
    exact_observed = set(returned)
    allowlist = source_manifest.get("return_allowlist")
    if not isinstance(allowlist, list):
        raise AnalysisError("source return allowlist missing")
    allowlist_records = {
        str(item["target_path"]): item
        for item in allowlist
        if isinstance(item, dict) and "target_path" in item
    }
    required_targets = {
        path for path, item in allowlist_records.items() if item.get("required") is True
    }
    returned_targets = set(expected_records)
    required_missing = sorted(required_targets - returned_targets)
    manifest_required_missing = sorted(return_manifest.get("required_missing", []))
    return {
        "status": return_manifest.get("status"),
        "allowlist_only": return_manifest.get("allowlist_only"),
        "record_count": len(expected_records),
        "record_errors": record_errors,
        "exact_set_valid": exact_expected == exact_observed,
        "missing_from_exact_set": sorted(exact_expected - exact_observed),
        "extra_in_exact_set": sorted(exact_observed - exact_expected),
        "all_returned_targets_allowlisted": returned_targets <= set(allowlist_records),
        "required_target_count": len(required_targets),
        "required_missing_computed": required_missing,
        "required_missing_manifest": manifest_required_missing,
        "required_missing_exact": required_missing == manifest_required_missing,
        "valid": (
            not record_errors
            and exact_expected == exact_observed
            and returned_targets <= set(allowlist_records)
            and required_missing == manifest_required_missing
            and return_manifest.get("allowlist_only") is True
        ),
    }


def analyze(return_zip: Path) -> dict[str, Any]:
    errors: list[str] = []
    if return_zip.stat().st_size != RETURN_BYTES:
        errors.append("return ZIP byte count differs")
    if sha256_file(return_zip) != RETURN_SHA256:
        errors.append("return ZIP SHA256 differs")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES:
        errors.append("source ZIP byte count differs")
    if sha256_file(SOURCE_ZIP) != SOURCE_SHA256:
        errors.append("source ZIP SHA256 differs")
    if sha256_file(SOURCE_TASK_RECORD) != SOURCE_TASK_RECORD_SHA256:
        errors.append("source task record SHA256 differs")
    if sha256_file(SOURCE_MACHINE_REPORT) != SOURCE_MACHINE_REPORT_SHA256:
        errors.append("source machine report SHA256 differs")
    if sha256_file(PLAN) != PLAN_SHA256:
        errors.append("mutable plan receipt differs from dispatch")

    returned, return_zip_audit = read_zip(return_zip, RETURN_ROOT)
    source, source_zip_audit = read_zip(SOURCE_ZIP, SOURCE_ROOT)
    return_manifest = json_object(returned, "RETURN_MANIFEST.json")
    returned_package_manifest = returned["package/TEST_PACKAGE_MANIFEST.json"]
    source_package_manifest = source["TEST_PACKAGE_MANIFEST.json"]
    source_manifest = json.loads(source_package_manifest)
    if not isinstance(source_manifest, dict):
        raise AnalysisError("source package manifest is not an object")
    manifest_check = manifest_audit(returned, return_manifest, source_manifest)
    if not manifest_check["valid"]:
        errors.append("return manifest/allowlist audit failed")
    if returned_package_manifest != source_package_manifest:
        errors.append("returned package manifest differs from frozen source")

    package_preflight = json_object(returned, "evidence/package_preflight.json")
    installed_preflight = json_object(returned, "evidence/installed_preflight.json")
    observer_binding = json_object(returned, "evidence/observer_binding.json")
    gate = json_object(returned, "evidence/SERVER_RESULT_GATE.json")
    fallback_canonical = json_object(
        returned, "evidence/CANONICAL_PROGRESS_DECISION.json"
    )
    compile_status = parse_int_file(
        returned, "evidence/compile_exit_status.txt"
    )
    sim_status = parse_int_file(returned, "evidence/sim_exit_status.txt")
    run_status = parse_int_file(returned, "evidence/run_exit_status.txt")
    signal = text(returned, "evidence/termination_signal.txt").strip()
    actual_compile = text(returned, "evidence/actual_compile_argv.txt")
    actual_sim = text(returned, "evidence/simulator_argv.txt")
    observer_text = text(returned, "logs/return_observer.log")
    sim_text = text(returned, "logs/sim.log")
    host_text = text(returned, "logs/host_progress.log")
    runner = text(source, "PREPARE_AND_RUN.sh")
    observer_source = source["tb_probe/native_return_observer.svh"]
    runner_contract = json_object(source, "workload/runtime/runner_contract.json")

    source_binding = source_manifest.get("observer_binding_four_way", {})
    source_sha = sha256_bytes(observer_source)
    time0_count = observer_text.count("[MAXPOOL_RETURN_OBSERVER] enabled")
    observer_binding_computed = {
        "source_present": True,
        "source_sha256": source_sha,
        "source_sha_matches_manifest": source_sha
        == source_binding.get("source_sha256"),
        "package_local_incdir_present": "+incdir+" in actual_compile
        and "/tb_probe" in actual_compile,
        "compile_enable_present": "+define+NATIVE_RETURN_OBSERVER_ENABLE"
        in actual_compile,
        "runtime_enable_present": "+RETURN_OBSERVER" in actual_sim,
        "runtime_output_present": "+RETURN_OBS_FILE=" in actual_sim,
        "time0_marker_count": time0_count,
        "observer_returned": "logs/return_observer.log" in returned,
        "return_trap_declared": all(
            token in runner for token in ("EXIT", "HUP", "INT", "TERM")
        ),
    }
    observer_binding_computed["valid"] = all(
        (
            observer_binding_computed["source_sha_matches_manifest"],
            observer_binding_computed["package_local_incdir_present"],
            observer_binding_computed["compile_enable_present"],
            observer_binding_computed["runtime_enable_present"],
            observer_binding_computed["runtime_output_present"],
            time0_count == 1,
            observer_binding_computed["observer_returned"],
            observer_binding_computed["return_trap_declared"],
        )
    )

    starts: list[dict[str, Any]] = []
    finishes: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    canonical_lines: list[str] = []
    for line_number, line in enumerate(observer_text.splitlines(), start=1):
        fields = parse_fields(line)
        if "| MAXPOOL_EXEC_START_V1 |" in line:
            starts.append({"line": line_number, **fields})
        elif "| MAXPOOL_STAGE_FINISH_V1 |" in line:
            finishes.append({"line": line_number, **fields})
        elif "| MAXPOOL_PROGRESS_WINDOW_V1 |" in line:
            windows.append({"line": line_number, **fields})
        elif "| CANONICAL_MAXPOOL_DIAG_DECISION_V1 |" in line:
            canonical_lines.append(line)
    if not windows:
        errors.append("no progress window returned")
    last_window = windows[-1] if windows else {}
    expected_stage_list = (
        runner_contract.get("execution", {})
        .get("completion_gate", {})
        .get("expected_runtime_sequence", [])
    )
    if expected_stage_list != list(EXPECTED_STAGES):
        errors.append("source expected ordered stage list differs")
    observed_start_slices = [int(item["slice"]) for item in starts if "slice" in item]
    observed_finish_slices = [
        int(item["slice"]) for item in finishes if "slice" in item
    ]
    canonical_stage_scope_valid = False
    canonical_stage_scope_error = (
        "canonical record absent and observer records do not bind expected ordered "
        "stage identities"
    )
    natural_markers = (
        sim_text.count("Simulation completed successfully!"),
        sim_text.count("INFO: slice completed after"),
    )
    natural_terminal = (
        compile_status == 0
        and sim_status == 0
        and run_status == 0
        and not signal
        and natural_markers[0] > 0
        and len(finishes) == len(EXPECTED_STAGES)
        and observed_finish_slices == [0, 1]
        and canonical_stage_scope_valid
    )

    progress_numeric = {
        key: int(last_window[key])
        for key in (
            "active_cycles",
            "sim_time",
            "clk_sg_edges",
            "progress",
            "delta",
            "req",
            "rdata",
            "wdata",
            "p0_capture",
            "ga_output",
            "finish",
        )
        if key in last_window
    }
    capture_advancing_window_count = sum(
        1 for item in windows if int(item.get("delta", "0")) > 0
    )
    if windows and capture_advancing_window_count != len(windows):
        errors.append("unexpected zero-delta progress window")

    host_samples: list[dict[str, Any]] = []
    for line in host_text.splitlines():
        fields = parse_fields(line)
        if "utc" in fields and "observer_bytes" in fields:
            host_samples.append(
                {
                    "utc": fields["utc"],
                    "observer_bytes": int(fields["observer_bytes"]),
                }
            )
    wall_seconds = None
    if len(host_samples) >= 2:
        first = datetime.fromisoformat(host_samples[0]["utc"].replace("Z", "+00:00"))
        last = datetime.fromisoformat(host_samples[-1]["utc"].replace("Z", "+00:00"))
        wall_seconds = (last - first).total_seconds()

    readback = gate.get("formal_readback", {})
    slices = readback.get("slices", [])
    expected_d = sum(int(item.get("expected_segment_count", 0)) for item in slices)
    observed_d = sum(int(item.get("observed_segment_count", 0)) for item in slices)
    missing_d = sum(len(item.get("missing_paths", [])) for item in slices)
    mismatch = readback.get("total_byte_mismatch_count")

    finalizer_artifacts = {
        "termination_signal_returned": bool(signal),
        "compile_status_returned": "evidence/compile_exit_status.txt" in returned,
        "sim_status_returned": "evidence/sim_exit_status.txt" in returned,
        "run_status_returned": "evidence/run_exit_status.txt" in returned,
        "result_gate_returned": "evidence/SERVER_RESULT_GATE.json" in returned,
        "return_manifest_returned": "RETURN_MANIFEST.json" in returned,
        "observer_returned": "logs/return_observer.log" in returned,
        "host_progress_returned": "logs/host_progress.log" in returned,
        "outer_shell_or_finalizer_exit_returned": False,
        "runner_stderr_returned": False,
    }
    finalizer_artifacts["partial_collection_executed"] = all(
        value
        for key, value in finalizer_artifacts.items()
        if key
        not in {
            "outer_shell_or_finalizer_exit_returned",
            "runner_stderr_returned",
        }
    )

    source_identity = {
        "returned_manifest_byte_equal": returned_package_manifest
        == source_package_manifest,
        "returned_manifest_sha256": sha256_bytes(returned_package_manifest),
        "install_name": source_manifest.get("install_name"),
        "return_root": RETURN_ROOT,
        "return_manifest_install_name": return_manifest.get("install_name"),
        "expected_return": source_manifest.get("expected_return"),
        "server_command": return_manifest.get("server_command"),
        "package_install_run_return_identity_valid": (
            source_manifest.get("install_name") == INSTALL_NAME
            and return_manifest.get("install_name") == INSTALL_NAME
            and source_manifest.get("expected_return") == f"{INSTALL_NAME}_return.zip"
            and RETURN_ROOT == f"{INSTALL_NAME}_return"
            and f"/run_{INSTALL_NAME}" in actual_sim
            and f"/install/cfg_pkg/{INSTALL_NAME}/" in actual_sim
        ),
    }
    preflight = {
        "package_valid": package_preflight.get("valid") is True,
        "installed_valid": installed_preflight.get("valid") is True,
        "package_tree_immutable": package_preflight.get("package_tree_immutable")
        is True,
        "runtime_d_initially_absent": installed_preflight.get(
            "formal_readback_targets_absent"
        )
        is True,
        "server_source_files_inspected": bool(
            package_preflight.get("server_source_files_inspected")
            or installed_preflight.get("server_source_files_inspected")
        ),
    }

    first_divergence = (
        "QUALIFIED_GA_PIPELINE0_CAPTURE_TO_GA_OUTBUFFER_WRITE_ABSENT"
    )
    hang_root_cause = (
        "UNRESOLVED_WITHIN_GA_PIPELINE0_CAPTURE_TO_GA_OUTBUFFER_WRITE"
    )
    e3 = natural_terminal
    e4 = bool(
        e3
        and readback.get("all_readbacks_present") is True
        and readback.get("all_readbacks_format_valid") is True
        and mismatch == 0
        and gate.get("server_source_identity_bound") is True
    )
    e5 = False
    if compile_status != 0:
        errors.append("compile did not succeed")
    if not manifest_check["valid"]:
        errors.append("return exact-set is invalid")
    if not source_identity["package_install_run_return_identity_valid"]:
        errors.append("package/install/run/return identity differs")
    if not all(
        (
            preflight["package_valid"],
            preflight["installed_valid"],
            preflight["package_tree_immutable"],
            preflight["runtime_d_initially_absent"],
        )
    ):
        errors.append("preflight contract differs")
    if not observer_binding_computed["valid"]:
        errors.append("observer binding differs")

    server_rule_finish_sha = sha256_file(SERVER_RULE)
    report = {
        "schema": "maxpool-node0002-v4-formal-return-analysis-v1",
        "status": "FORMAL_RETURN_ANALYZED_FAIL_CLOSED",
        "provenance": {
            "analysis_owner_thread": ANALYSIS_OWNER_THREAD,
            "return_target_thread": RETURN_TARGET_THREAD,
        },
        "scope": {
            "receipt_only": True,
            "numeric_analysis_repeated": False,
            "w3_analysis_repeated": False,
            "config_mapper_bitstream_execplan_sca_analysis_repeated": False,
            "package_generated": False,
            "server_action": False,
            "plan_rules_rtl_modified": False,
        },
        "control_receipts": {
            "plan_mutable_sha256": sha256_file(PLAN),
            "server_rule_dispatch_sha256": SERVER_RULE_DISPATCH_SHA256,
            "server_rule_finish_observed_sha256": server_rule_finish_sha,
            "server_rule_drift_observed": server_rule_finish_sha
            != SERVER_RULE_DISPATCH_SHA256,
            "source_task_record_sha256": sha256_file(SOURCE_TASK_RECORD),
            "source_machine_report_sha256": sha256_file(SOURCE_MACHINE_REPORT),
            "source_task_record_embedded_old_machine_sha_not_reused": True,
        },
        "transport": {
            "return_zip": str(return_zip),
            "return_bytes": return_zip.stat().st_size,
            "return_sha256": sha256_file(return_zip),
            "adjacent_sidecar_present": False,
            "user_attested_no_sidecar_rule_applied": True,
            "internal_gates_relaxed": False,
        },
        "return_zip_audit": return_zip_audit,
        "source_zip": {
            "path": str(SOURCE_ZIP),
            "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": sha256_file(SOURCE_ZIP),
            "audit": source_zip_audit,
        },
        "return_manifest_audit": manifest_check,
        "source_identity": source_identity,
        "preflight": preflight,
        "observer_binding": {
            "returned_receipt": observer_binding,
            "independent": observer_binding_computed,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": sim_status,
            "run_status_receipt": run_status,
            "termination_signal": signal,
            "simulation_started": "INFO: slice start" in sim_text,
            "sca_echo_observed": gate.get("sca_echo_observed"),
            "sca_d_echo_observed": gate.get("sca_d_echo_observed"),
            "natural_completion_markers": {
                "simulation_completed_successfully": natural_markers[0],
                "slice_completed_after": natural_markers[1],
            },
            "natural_terminal": natural_terminal,
            "host_progress_sample_count": len(host_samples),
            "host_sample_span_seconds": wall_seconds,
            "sim_interrupt_ps": int(
                re.findall(r"Interrupt at time (\d+)", sim_text)[-1]
            )
            if re.findall(r"Interrupt at time (\d+)", sim_text)
            else None,
        },
        "signal_finalizer": {
            "artifacts": finalizer_artifacts,
            "adjudication": (
                "PARTIAL_COLLECTION_EXECUTED_BUT_OUTER_SHELL_EXIT_AND_STDERR_UNBOUND"
            ),
            "sentinel_status_warning": (
                "INT trap ran before sim_status/run_status assignment completed; "
                "returned 125 receipts are initialized sentinels, not the outer "
                "shell/finalizer exit status"
            ),
        },
        "ordered_stage_scope": {
            "expected_stages": list(EXPECTED_STAGES),
            "expected_stage_source": "workload/runtime/runner_contract.json",
            "observer_exec_start_count": len(starts),
            "observer_exec_start_slices": observed_start_slices,
            "observer_finish_count": len(finishes),
            "observer_finish_slices": observed_finish_slices,
            "canonical_candidate_count": len(canonical_lines),
            "canonical_stage_scope_valid": canonical_stage_scope_valid,
            "error": canonical_stage_scope_error,
            "fallback_canonical": fallback_canonical,
            "early_stage_finish_misclassified_as_terminal": False,
            "final_stage_completed": False,
        },
        "qualified_dynamic_chain": {
            "progress_window_count": len(windows),
            "all_windows_have_positive_reported_delta": (
                capture_advancing_window_count == len(windows)
            ),
            "last_window": progress_numeric,
            "last_proven_good": (
                "stage0 command/slice start; qualified MSE request and read data; "
                "qualified GA pipeline0 capture"
            ),
            "first_divergence": first_divergence,
            "downstream_absent": [
                "GA outbuffer write",
                "D write data",
                "slice finish",
                "stage1 start",
                "natural terminal",
            ],
            "progress_sum_limitation": (
                "repeated upstream pipeline0 captures dominate monotonic progress "
                "while every downstream completion counter remains zero"
            ),
        },
        "formal_readback": {
            "expected_segments": expected_d,
            "present_segments": observed_d,
            "missing_segments": missing_d,
            "mismatch_byte_count": mismatch,
            "mismatch_evaluable": mismatch is not None,
            "all_readbacks_present": readback.get("all_readbacks_present"),
            "all_readbacks_format_valid": readback.get(
                "all_readbacks_format_valid"
            ),
        },
        "last_proven_good": (
            "compile/elaboration, 11 matrix preload, Reg Started, stage0 slice "
            "start, MSE request/read-data, and GA pipeline0 capture"
        ),
        "first_divergence": first_divergence,
        "hang_root_cause": hang_root_cause,
        "hang_claim_boundary": (
            "dynamic interval only; observer does not expose a unique config or "
            "RTL leaf inside pipeline0 capture to outbuffer write"
        ),
        "e3_e4_e5": {"E3": e3, "E4": e4, "E5": e5},
        "result_gate": {
            "returned": gate.get("result_gate_conjunction"),
            "independent_all_terms_true": bool(
                compile_status == 0
                and sim_status == 0
                and run_status == 0
                and not signal
                and natural_terminal
                and expected_d == observed_d
                and missing_d == 0
                and mismatch == 0
            ),
        },
        "blocker_delta": {
            "B_GA_INT8_MAX_FLOW": (
                "KEEP_OPEN_DYNAMIC_STALL_CONFIRMED_AT_PIPELINE0_CAPTURE_TO_"
                "GA_OUTBUFFER_WRITE"
            ),
            "B_GA_INT8_MAX_NUMERIC": (
                "KEEP_OPEN_UNEVALUABLE_NO_FORMAL_D_OUTPUT"
            ),
            "B_MAXPOOL_SERVER_E4_E5": (
                "KEEP_OPEN_SIGNAL_NO_NATURAL_TERMINAL_D_0_OF_4"
            ),
            "package_diagnostic_contract": [
                "PACKAGE_DIAGNOSTIC_DECISION_FINAL_STAGE_SCOPE_CONTRACT_MISSING",
                "PACKAGE_SIGNAL_FINALIZER_SHELL_EXIT_STATUS_UNRETURNED",
                "PACKAGE_PROGRESS_SUM_DOMINATED_BY_REPEATED_UPSTREAM_CAPTURE",
            ],
        },
        "rule_delta_proposal": [],
        "successor_proposal": None,
        "package_release": {
            "new_package": False,
            "status": "NONE",
            "v4_disposition": "RETURN_CONSUMED_FAIL_CLOSED_DO_NOT_RERUN",
        },
        "errors": errors,
        "analysis_valid": not errors,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = analyze(args.return_zip.resolve())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["analysis_valid"] else 1
    except Exception as exc:
        print(f"MaxPool node0002 v4 return analysis failed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
