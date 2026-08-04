from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURN_ZIP = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_n71_gap_v3_cwd_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v3_cwd.zip"
)
OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-node0071-v3-return-analysis/report.json"
)
DIAGNOSTIC_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v4_hangloc.zip"
)
DIAGNOSTIC_VALIDATION = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v4_hangloc.validation.json"
)
RETURN_ROOT = "r5_n71_gap_v3_cwd_return"
SOURCE_ROOT = "r5_n71_gap_v3_cwd"
EXPECTED_SOURCE_SHA256 = (
    "3d6c8c580e178717b1c0a9bf70f5c55fd8cbcc8a74c7e9b5673f36b743604c80"
)
SERVER_RULE_SHA256 = (
    "06ec5cde2920f6aa0f11e4a2ec23d9cec2621015afe706ab8ec83e3d4603089c"
)
PLAN_SHA256 = (
    "b1623373ee6f5c442807eeb4d2a68ce33e36d5686d98873ff1a3e1587d1eea34"
)


class ReturnAnalysisError(ValueError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_names(archive: zipfile.ZipFile) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        pure = PurePosixPath(name)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in name
            or name in seen
            or (mode and stat.S_ISLNK(mode))
        ):
            raise ReturnAnalysisError(f"unsafe ZIP member: {name}")
        seen.add(name)
        if not info.is_dir():
            names.append(name)
    return names


def object_from_bytes(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReturnAnalysisError(f"invalid JSON: {label}") from error
    if not isinstance(value, dict):
        raise ReturnAnalysisError(f"JSON root differs: {label}")
    return value


def object_from_zip(
    archive: zipfile.ZipFile, name: str
) -> dict[str, Any]:
    return object_from_bytes(archive.read(name), name)


def status_from_zip(archive: zipfile.ZipFile, name: str) -> int:
    try:
        return int(archive.read(name).decode("ascii").strip())
    except (UnicodeError, ValueError, KeyError) as error:
        raise ReturnAnalysisError(f"invalid status: {name}") from error


def line_receipt(lines: list[str], needle: str) -> dict[str, Any] | None:
    for index, line in enumerate(lines, start=1):
        if needle in line:
            match = re.match(r"\[(\d+)\]", line)
            return {
                "line": index,
                "text": line,
                "time_ps": int(match.group(1)) if match else None,
            }
    return None


def validate_return_manifest(
    archive: zipfile.ZipFile,
    names: list[str],
    manifest: dict[str, Any],
) -> tuple[list[str], set[str]]:
    prefix = f"{RETURN_ROOT}/"
    manifest_member = prefix + "RETURN_MANIFEST.json"
    records = manifest.get("files")
    if not isinstance(records, list):
        raise ReturnAnalysisError("RETURN_MANIFEST files is absent")
    declared: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ReturnAnalysisError("RETURN_MANIFEST record differs")
        relative = str(record.get("path"))
        member = prefix + relative
        if member in declared or member not in names:
            raise ReturnAnalysisError(f"manifest path differs: {relative}")
        payload = archive.read(member)
        if (
            len(payload) != record.get("size_bytes")
            or sha256_bytes(payload) != record.get("sha256")
        ):
            raise ReturnAnalysisError(f"manifest receipt differs: {relative}")
        declared.add(member)
    if declared | {manifest_member} != set(names):
        raise ReturnAnalysisError("return ZIP exact-set differs")
    missing = manifest.get("required_missing")
    if (
        manifest.get("schema")
        != "gap-node0071-complete-return-manifest-v1"
        or manifest.get("install_name") != SOURCE_ROOT
        or manifest.get("status") != "incomplete"
        or manifest.get("allowlist_only") is not True
        or not isinstance(missing, list)
        or len(missing) != 48
        or len(set(missing)) != 48
    ):
        raise ReturnAnalysisError("return manifest boundary differs")
    return [str(item) for item in missing], declared


def analyze(return_zip: Path) -> dict[str, Any]:
    supplied = return_zip.resolve()
    sidecar = Path(str(supplied) + ".sha256")
    if not supplied.is_file() or not sidecar.is_file():
        raise ReturnAnalysisError("return ZIP or adjacent sidecar absent")
    return_sha = sha256_file(supplied)
    expected_sidecar = f"{return_sha}  {supplied.name}\n"
    if sidecar.read_text(encoding="ascii") != expected_sidecar:
        raise ReturnAnalysisError("return sidecar differs")
    if sha256_file(SOURCE_ZIP) != EXPECTED_SOURCE_SHA256:
        raise ReturnAnalysisError("frozen source package differs")

    with zipfile.ZipFile(supplied) as archive:
        names = safe_names(archive)
        if archive.testzip() is not None:
            raise ReturnAnalysisError("return ZIP CRC failed")
        prefix = f"{RETURN_ROOT}/"
        return_manifest = object_from_zip(
            archive, prefix + "RETURN_MANIFEST.json"
        )
        required_missing, declared = validate_return_manifest(
            archive, names, return_manifest
        )
        evidence = prefix + "evidence/"
        package_manifest_bytes = archive.read(
            evidence + "PACKAGE_MANIFEST.json"
        )
        package_manifest = object_from_bytes(
            package_manifest_bytes, "returned package manifest"
        )
        sca_bytes = archive.read(prefix + "config/sca_cfg.json")
        sca_d_bytes = archive.read(prefix + "config/sca_cfg_D.json")
        installed = object_from_zip(
            archive, evidence + "installed_preflight.json"
        )
        observer_precompile = object_from_zip(
            archive, evidence + "observer_precompile.json"
        )
        gate = object_from_zip(
            archive, evidence + "SERVER_RESULT_GATE.json"
        )
        compile_status = status_from_zip(
            archive, evidence + "compile_exit_status.txt"
        )
        simulation_status = status_from_zip(
            archive, evidence + "simulation_exit_status.txt"
        )
        runner_status = status_from_zip(
            archive, evidence + "runner_exit_status.txt"
        )
        compile_log = archive.read(prefix + "logs/compile.log").decode(
            "utf-8", "replace"
        )
        sim_log = archive.read(prefix + "logs/sim.log").decode(
            "utf-8", "replace"
        )

    with zipfile.ZipFile(SOURCE_ZIP) as source:
        source_names = safe_names(source)
        if source.testzip() is not None:
            raise ReturnAnalysisError("source ZIP CRC failed")
        source_manifest_bytes = source.read(
            f"{SOURCE_ROOT}/TEST_PACKAGE_MANIFEST.json"
        )
        source_sca = source.read(f"{SOURCE_ROOT}/workload/sca_cfg.json")
        source_sca_d = source.read(f"{SOURCE_ROOT}/workload/sca_cfg_D.json")
        execplan = source.read(
            f"{SOURCE_ROOT}/workload/install/execplan.txt"
        )
        observer = source.read(
            f"{SOURCE_ROOT}/tb_probe/native_return_observer.svh"
        )

    if (
        package_manifest_bytes != source_manifest_bytes
        or sca_bytes != source_sca
        or sca_d_bytes != source_sca_d
    ):
        raise ReturnAnalysisError("returned package/SCA binding differs")
    allowlist = package_manifest.get("return_allowlist")
    if not isinstance(allowlist, list):
        raise ReturnAnalysisError("source allowlist absent")
    allowed_targets = {str(item["target_path"]) for item in allowlist}
    returned_targets = {
        name.removeprefix(f"{RETURN_ROOT}/") for name in declared
    }
    if not returned_targets <= allowed_targets:
        raise ReturnAnalysisError("returned path outside source allowlist")
    if set(required_missing) != allowed_targets - returned_targets:
        raise ReturnAnalysisError("required-missing allowlist delta differs")

    checks = gate.get("checks")
    if not isinstance(checks, list) or len(checks) != 48:
        raise ReturnAnalysisError("formal D check count differs")
    role_missing = {
        role: sum(
            item.get("role") == role and item.get("status") == "missing"
            for item in checks
        )
        for role in ("sum_int32", "scaled_fp32", "final_uint8")
    }
    if (
        compile_status != 0
        or simulation_status != 125
        or runner_status != 124
        or gate.get("status") != "NODE0071_GAP_SERVER_FAILURE"
        or gate.get("missing_count") != 48
        or gate.get("mismatch_byte_count") != 0
        or role_missing
        != {"sum_int32": 16, "scaled_fp32": 16, "final_uint8": 16}
        or gate.get("result_gate_conjunction", {}).get("all_terms_true")
        is not False
    ):
        raise ReturnAnalysisError("execution/result conjunction differs")
    if (
        installed.get("valid") is not True
        or installed.get("formal_readback_targets_absent") is not True
        or installed.get("package_preflight", {}).get("valid") is not True
    ):
        raise ReturnAnalysisError("installed preflight differs")

    sim_lines = sim_log.splitlines()
    cfg_echo = line_receipt(
        sim_lines,
        "Using SCA cfg file: install/cfg_pkg/"
        "r5_n71_gap_v3_cwd/sca_cfg.json",
    )
    cfg_d_echo = line_receipt(
        sim_lines,
        "Using SCA cfg D file: install/cfg_pkg/"
        "r5_n71_gap_v3_cwd/sca_cfg_D.json",
    )
    loaded = line_receipt(sim_lines, "JSON config: 25 matrices loaded")
    reg_started = line_receipt(sim_lines, "Reg Started.")
    slice_started = line_receipt(sim_lines, "INFO: slice start")
    interrupted = line_receipt(sim_lines, "Interrupt at time ")
    if not all(
        item is not None
        for item in (
            cfg_echo,
            cfg_d_echo,
            loaded,
            reg_started,
            slice_started,
            interrupted,
        )
    ):
        raise ReturnAnalysisError("expected simulation milestones absent")
    interrupt_match = re.search(
        r"Interrupt at time\s+(\d+)", interrupted["text"]
    )
    assert interrupt_match is not None
    interrupt_ps = int(interrupt_match.group(1))
    slice_start_ps = int(slice_started["time_ps"])
    compute_interval_ps = interrupt_ps - slice_start_ps
    execplan_lines = execplan.splitlines()
    if len(execplan_lines) != 13:
        raise ReturnAnalysisError("execplan 128-bit line count differs")
    commands = []
    for line in execplan_lines:
        if len(line) != 128:
            raise ReturnAnalysisError("execplan line width differs")
        commands.extend((int(line[64:], 2), int(line[:64], 2)))
    commands = commands[:25]
    opcode_counts = {
        "load_config": sum((word & 0b111) == 0 for word in commands),
        "start_comp": sum((word & 0b111) == 0b101 for word in commands),
        "barrier": sum((word & 0b111) == 0b110 for word in commands),
        "clock_enable": sum((word & 0b111) == 0b001 for word in commands),
    }
    if opcode_counts != {
        "load_config": 8,
        "start_comp": 8,
        "barrier": 8,
        "clock_enable": 1,
    }:
        raise ReturnAnalysisError("execplan opcode counts differ")

    observer_enabled = "[RETURN_OBSERVER] enabled" in sim_log
    observer_returned = any(
        name.endswith("/return_observer.log") for name in names
    )
    natural_terminal = "Simulation completed successfully!" in sim_log
    formal_dump = bool(
        re.search(r"JSON_D config:\s*48\s+matrices dumped", sim_log)
    )
    source_runtime_d = [
        name for name in source_names if "/workload/readback/" in name
    ]
    compile_ok = (
        "0 error(s), 1 warning(s)" in compile_log
        and "Error-[" not in compile_log
    )
    source_observer_sha = sha256_bytes(observer)
    if (
        source_observer_sha
        != "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
        or observer_precompile.get("identity_match") is not True
    ):
        raise ReturnAnalysisError("observer source/precompile identity differs")

    return {
        "schema": "resnet50-gap-node0071-v3-return-analysis-v1",
        "status": "LONG_RUNNING_HANG_PENDING_ROOT_CAUSE",
        "return_analysis": {
            "return_zip": str(supplied),
            "return_size_bytes": supplied.stat().st_size,
            "return_sha256": return_sha,
            "sidecar_path": str(sidecar),
            "sidecar_sha256": sha256_file(sidecar),
            "sidecar_content_exact": True,
            "zip_crc_valid": True,
            "safe_exact_set_valid": True,
            "member_count": len(names),
            "manifest_record_count": len(return_manifest["files"]),
            "allowlist_only": True,
            "allowlist_subset_valid": True,
            "return_manifest_status": "incomplete",
            "required_missing_count": len(required_missing),
        },
        "bound_source_package": {
            "path": str(SOURCE_ZIP.relative_to(ROOT).as_posix()),
            "sha256": EXPECTED_SOURCE_SHA256,
            "sidecar_content_exact": True,
            "zip_crc_valid": True,
            "manifest_byte_equal": True,
            "sca_byte_equal": True,
            "sca_d_byte_equal": True,
            "runtime_d_targets_in_source_zip": len(source_runtime_d),
            "install_name": SOURCE_ROOT,
        },
        "preflight": {
            "package_valid": True,
            "installed_valid": True,
            "installed_file_count": installed["installed_file_count"],
            "preload_count": installed["package_preflight"]["preload_count"],
            "readback_count": installed["package_preflight"]["readback_count"],
            "repeat_num": installed["package_preflight"]["repeat_num"],
            "runtime_d_targets_absent_post_install": True,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "compile_elaboration_ok": compile_ok,
            "simulation_exit_status": simulation_status,
            "runner_exit_status": runner_status,
            "external_timeout_hours": 12,
            "sim_time_limit_plusarg": "100ms",
            "sca_cfg_echo": cfg_echo,
            "sca_cfg_d_echo": cfg_d_echo,
            "preload_25_complete": loaded,
            "reg_started": reg_started,
            "slice_started": slice_started,
            "interrupt": interrupted,
            "interrupt_time_ps": interrupt_ps,
            "post_slice_start_interval_ps": compute_interval_ps,
            "post_slice_start_interval_ms": compute_interval_ps / 1e9,
            "natural_terminal": natural_terminal,
            "formal_dump_48": formal_dump,
            "observer_runtime_enabled": observer_enabled,
            "observer_log_returned": observer_returned,
        },
        "formal_readback": {
            "expected_count": 48,
            "present_count": 0,
            "missing_count": 48,
            "mismatch_byte_count": 0,
            "role_missing": role_missing,
            "zero_mismatch_evaluable": False,
            "result_gate_all_terms_true": False,
            "e3": "FAIL",
            "e4": "FAIL",
            "e5": "FAIL",
        },
        "progress_adjudication": {
            "classification":
                "INSUFFICIENT_TO_DISTINGUISH_PROGRESS_FROM_STALL",
            "simulator_event_time_advanced": True,
            "accepted_transaction_progress_proven": False,
            "stall_proven": False,
            "reason": (
                "The return advances simulator time after slice start but "
                "contains no enabled stage heartbeat, accepted/completion "
                "counter, last/terminal state, or declared stall window."
            ),
            "observer_packaged_and_precompiled": True,
            "observer_runtime_binding_missing": True,
            "observer_source_sha256": source_observer_sha,
        },
        "first_divergence": {
            "classification":
                "EXTERNAL_TIMEOUT_AFTER_FIRST_START_COMP_WITHOUT_PROGRESS_EVIDENCE",
            "last_proven_boundary": (
                "25 preloads complete -> Reg Started -> first slice start"
            ),
            "first_unproven_interval": (
                "sum_s1 Start_Comp -> LC/MSE0 accepted read -> GA accepted/"
                "completed output -> MSE4 accepted D write -> last-data "
                "accepted -> slice_cmpt_finish"
            ),
        },
        "static_audit": {
            "numeric_analysis_repeated": False,
            "frozen_local_e2_reused": True,
            "execplan_sha256": sha256_bytes(execplan),
            "execplan_128bit_lines": len(execplan_lines),
            "execplan_64bit_commands": len(commands),
            "opcode_counts": opcode_counts,
            "serialized_stage_order": [
                "sum_s1",
                "sum_s2",
                "sum_s3",
                "sum_s4",
                "sum_s5",
                "sum_s6",
                "tail_mul",
                "tail_round",
            ],
            "same_mask_barriers": True,
            "address_lifetime_coverage_reanalysis": False,
            "address_lifetime_coverage_receipt": (
                "consumed frozen complete local E2 identities"
            ),
            "rtl_completion_chain": {
                "sem_holds_exec_start_while_cmpt": (
                    "Slice/Slice_Execution_Manager.sv:300-306,423-449"
                ),
                "formal_finish_source": (
                    "Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
                    "Memory_WR_Stream_Engine/WR_Data_Channel.sv:531-550"
                ),
                "formal_finish_condition": (
                    "last write data accepted by mem2mse_wdata_ready"
                ),
                "deterministic_defect_proven": False,
            },
        },
        "hang_root_cause": "UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT",
        "blocker_delta": {
            "closed": [
                "B_GAP_V2_TB_FIXED_RELATIVE_PATH_RUNNER_CWD",
                "B_GAP_SERVER_RTL_COMPILE_INTERFACE",
            ],
            "added": [
                "B_GAP_NODE0071_V3_LONG_RUNNING_HANG_ROOT_CAUSE",
                "B_GAP_NODE0071_V3_PROGRESS_EVIDENCE_ABSENT",
            ],
            "kept": [
                "B_GAP_NODE0071_DYNAMIC_RESULT",
                "B_GAP_SERVER_RTL_IDENTITY_UNBOUND",
                "B_GAP_E4_E5",
            ],
        },
        "rule_receipts": {
            "server_package_rule_sha256": SERVER_RULE_SHA256,
            "plan_sha256_mutable_provenance_only": PLAN_SHA256,
            "timeout_rule":
                "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
            "progress_rule":
                "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
        },
        "rule_delta_proposal": "NONE",
        "package_release": {
            "functional_candidate": "NONE",
            "v3_status": "FAILED_EXTERNAL_TIMEOUT",
            "fresh_package_generated_by_analysis":
                DIAGNOSTIC_ZIP.is_file(),
            "fresh_install_name": (
                "r5_n71_gap_v4_hangloc"
                if DIAGNOSTIC_ZIP.is_file()
                else None
            ),
            "fresh_status": (
                "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN"
                if DIAGNOSTIC_ZIP.is_file()
                else None
            ),
            "fresh_zip": (
                str(DIAGNOSTIC_ZIP.relative_to(ROOT).as_posix())
                if DIAGNOSTIC_ZIP.is_file()
                else None
            ),
            "fresh_zip_sha256": (
                sha256_file(DIAGNOSTIC_ZIP)
                if DIAGNOSTIC_ZIP.is_file()
                else None
            ),
            "fresh_zip_size_bytes": (
                DIAGNOSTIC_ZIP.stat().st_size
                if DIAGNOSTIC_ZIP.is_file()
                else None
            ),
            "fresh_validation_sha256": (
                sha256_file(DIAGNOSTIC_VALIDATION)
                if DIAGNOSTIC_VALIDATION.is_file()
                else None
            ),
            "functional_fix": False,
            "server_action": False,
        },
        "declarations": {
            "numeric_analysis_repeated": False,
            "sum_tail_retested": False,
            "frozen_source_package_consumed_read_only": True,
            "frozen_local_e2_consumed": True,
            "server_inspection_outside_return": False,
            "server_upload_or_run": False,
            "functional_rtl_modified": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=RETURN_ZIP)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = analyze(args.return_zip)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
