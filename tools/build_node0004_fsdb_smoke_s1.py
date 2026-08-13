#!/usr/bin/env python3
"""Build the serialized-Conv FSDB-only v3 smoke package.

This builder deliberately imports only the frozen v88b workload payload.  All
runtime, observer, waveform, query and return surfaces are generated fresh so
the retired ACK comparator cannot enter the smoke package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s1"
OLD_ID = "r5_n4_hw_v88b_portvcd"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_serialized_node0004/r5_n4_hw_v88b_portvcd/r5_n4_hw_v88b_portvcd.zip"
OUT = ROOT / "outputs/conv_node0004_fsdb_smoke_s1_release1"
BUILD_ROOT = OUT / "build" / PACKAGE_ID
FINAL_ZIP = OUT / f"{PACKAGE_ID}.zip"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_identity(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data), "sha256": sha(data)}


def write_text(relative: str, text: str, executable: bool = False) -> None:
    path = BUILD_ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_json(relative: str, value: object) -> None:
    write_text(relative, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def safe_member(name: str) -> PurePosixPath:
    value = PurePosixPath(name)
    if value.is_absolute() or ".." in value.parts or "\\" in name:
        raise ValueError(f"unsafe source ZIP member: {name}")
    return value


def import_frozen_workload() -> dict[str, object]:
    prefix = f"{OLD_ID}/workload/runtime/"
    old_rows: list[dict[str, object]] = []
    new_rows: list[dict[str, object]] = []
    replaced: list[str] = []
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise ValueError("frozen v88b source ZIP fails CRC")
        for info in archive.infolist():
            safe_member(info.filename)
            if info.is_dir() or not info.filename.startswith(prefix):
                continue
            relative = info.filename[len(prefix):]
            if not relative:
                continue
            raw = archive.read(info)
            old_rows.append({"path": relative, "bytes": len(raw), "sha256": sha(raw)})
            cooked = raw
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                pass
            else:
                if OLD_ID in text:
                    text = text.replace(OLD_ID, PACKAGE_ID)
                    cooked = text.encode("utf-8")
                    replaced.append(relative)
            target = BUILD_ROOT / "workload/runtime" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(cooked)
            new_rows.append({"path": relative, "bytes": len(cooked), "sha256": sha(cooked)})
    if not old_rows:
        raise ValueError("frozen v88b workload is absent")
    return {
        "schema": "node0004-fsdb-smoke-frozen-workload-import-v1",
        "source_zip": file_identity(SOURCE_ZIP),
        "source_package_id": OLD_ID,
        "destination_package_id": PACKAGE_ID,
        "source_member_count": len(old_rows),
        "destination_member_count": len(new_rows),
        "identity_only_text_relocations": sorted(replaced),
        "source_members": old_rows,
        "destination_members": new_rows,
        "functional_payload_frozen": True,
        "claim_boundary": "Only package-identity relocation in UTF-8 path strings; binary/config/numeric/workload semantics are frozen from exact tested v88b ZIP.",
    }


def deterministic_zip(source: Path, target: Path) -> None:
    temporary = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            relative = path.relative_to(source.parent).as_posix()
            info = zipfile.ZipInfo(relative, (2026, 8, 12, 0, 0, 0))
            mode = 0o755 if os.access(path, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise ValueError("generated ZIP fails CRC")
    os.replace(temporary, target)


def file_map() -> list[dict[str, object]]:
    rows = []
    for path in sorted(item for item in BUILD_ROOT.rglob("*") if item.is_file()):
        data = path.read_bytes()
        rows.append({"path": path.relative_to(BUILD_ROOT).as_posix(), "bytes": len(data), "sha256": sha(data)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUT)
    args = parser.parse_args()
    if args.output_root.resolve() != OUT.resolve():
        raise ValueError(f"this release builder is bound to {OUT}")
    if OUT.exists():
        raise ValueError(f"fresh output already exists: {OUT}")
    BUILD_ROOT.mkdir(parents=True)
    frozen = import_frozen_workload()
    write_json("provenance/frozen_v88b_workload_import.json", frozen)

    shared = {
        "package_tools/server_package_runtime_layout.py": ROOT / "tools/server_package_runtime_layout.py",
        "package_tools/server_post_sim_return.py": ROOT / "tools/server_post_sim_return.py",
        "package_tools/server_waveform_mandatory_return.py": ROOT / "tools/server_waveform_mandatory_return.py",
    }
    for relative, source in shared.items():
        target = BUILD_ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    write_text("package_tools/fsdb_smoke_runtime.py", RUNTIME_HELPER, executable=True)
    write_text("package_tools/fsdb_smoke_event_parser.py", EVENT_PARSER, executable=True)
    write_text("tb_probe/fsdb_smoke_event_probe.svh", EVENT_PROBE)
    write_text("PREPARE_AND_RUN.sh", RUNNER, executable=True)
    write_text("README.md", README)

    profile = {
        "schema": "node0004-fsdb-smoke-query-profile-v1",
        "profile_id": "serialized_conv_fsdb_smoke_time_progress_v1",
        "package_id": PACKAGE_ID,
        "timescale": "1ps",
        "event_prefix": "CODEX_FSDB_SMOKE_EVENT_V1",
        "summary_prefix": "CODEX_FSDB_SMOKE_SUMMARY_V1",
        "candidates": [
            {"candidate_id": "time_zero_marker", "hierarchical_path": "tb_NDP_Top_new_phy.u_codex_fsdb_smoke_probe.time_zero_marker", "width": 1},
            {"candidate_id": "time_progress_marker", "hierarchical_path": "tb_NDP_Top_new_phy.u_codex_fsdb_smoke_probe.time_progress_marker", "width": 1},
            {"candidate_id": "top_rst_n", "hierarchical_path": "tb_NDP_Top_new_phy.rst_n", "width": 1},
        ],
        "requirements": {
            "contiguous_sequence": True,
            "all_4state_transitions": True,
            "time_zero_marker_required": True,
            "time_greater_than_zero_required": True,
            "no_byte_limit": True,
            "no_event_limit": True,
            "sampling": False,
            "truncation": False,
        },
        "claim_boundary": "Package-owned smoke markers and top reset only; no ACK, functional RTL, natural-terminal or formal-D adjudication.",
    }
    write_json("contracts/fsdb_smoke_query_profile.json", profile)
    probe_data = (BUILD_ROOT / "tb_probe/fsdb_smoke_event_probe.svh").read_bytes()
    write_json("diagnostics/fsdb_smoke_query_source_report.json", {
        "schema": "node0004-fsdb-smoke-query-source-report-v1",
        "package_id": PACKAGE_ID,
        "source": {"path": "tb_probe/fsdb_smoke_event_probe.svh", "bytes": len(probe_data), "sha256": sha(probe_data)},
        "profile": {"path": "contracts/fsdb_smoke_query_profile.json", "bytes": len(json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True).encode()) + 1, "sha256": sha((BUILD_ROOT / "contracts/fsdb_smoke_query_profile.json").read_bytes())},
        "writer_count": 1,
        "writer_owner": "package_tools/dump_waveform.tcl",
        "retired_ack_comparator_present": False,
        "claim_boundary": "Source identity for the non-driving smoke event observer only.",
    })

    plan = {
        "schema": "server-waveform-mandatory-plan-v3",
        "package_id": PACKAGE_ID,
        "family": "conv_serialized_fsdb_smoke",
        "dump": {
            "format": "FSDB",
            "make_arguments": {"DUMP_VCD": "0", "DUMP_FSDB": "1", "TB_DUMP_FSDB": "0"},
            "tb_top": "tb_NDP_Top_new_phy",
            "hierarchy_depth": 0,
            "scope_mode": "FULL_HIERARCHY",
            "included_scopes": ["tb_NDP_Top_new_phy"],
            "excluded_scopes": [],
            "runtime_search_roots": ["run/sim_results"],
            "waveform_name_patterns": ["wave.fsdb", "wave.fsdb.*"],
        },
        "return_policy": {
            "required_when_simulation_started": True,
            "compile_not_started_omission_allowed": True,
            "collect_all_matching": True,
            "archive_prefix": "waveforms",
            "manifest_archive_path": "waveforms/WAVEFORM_RUNTIME_RECEIPT.json",
            "hard_limit_bytes": None,
            "truncation_allowed": False,
            "sampling_allowed": False,
            "size_based_deletion_allowed": False,
        },
        "integration": {
            "plan_member": "contracts/server_waveform_mandatory_plan.json",
            "runner_member": "PREPARE_AND_RUN.sh",
            "return_request_member": "contracts/server_post_sim_return_request.json",
            "dump_control_member": "package_tools/dump_waveform.tcl",
            "tool_member": "package_tools/server_waveform_mandatory_return.py",
        },
        "claim_boundary": "Authoritative package-owned full-hierarchy depth-0 FSDB smoke capture only; no DUT or formal result claim.",
    }
    write_json("contracts/server_waveform_mandatory_plan.json", plan)
    # Exact plan-derived control. CODEX_WAVE_PATH is assigned by the attempt-local runner wrapper.
    from server_waveform_mandatory_return import render_dump_control
    write_text("package_tools/dump_waveform.tcl", render_dump_control(plan))

    request = post_request()
    write_json("contracts/server_post_sim_return_request.json", request)
    write_json("contracts/server_post_sim_return_contract.json", {
        "schema": "server-post-sim-return-contract-v1",
        "package_id": PACKAGE_ID,
        "helper_member": "package_tools/server_post_sim_return.py",
        "helper_sha256": sha((BUILD_ROOT / "package_tools/server_post_sim_return.py").read_bytes()),
        "request_member": "contracts/server_post_sim_return_request.json",
        "request_sha256": sha((BUILD_ROOT / "contracts/server_post_sim_return_request.json").read_bytes()),
        "runner_member": "PREPARE_AND_RUN.sh",
        "invocation_mode": "JSON_REQUEST_ONLY_NO_POSITIONAL_COLLECTOR",
        "sim_exit_persisted_before_plugins": True,
        "plugin_failure_blocks_core_return": False,
        "required_scenarios": ["natural_success", "natural_success_plugin_failure", "simulation_nonzero", "idempotent_reentry"],
        "partial_exit_live_causal_record": {"enforcement": "required_next_fresh", "final_block_ring_sole_input_forbidden": True, "required_signals": ["INT", "TERM"], "rule_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001", "plugin_dispositions": []},
        "claim_boundary": "Core/raw-FSDB publication is independent of registered event-query success.",
    })

    layout = layout_contract()
    write_json("SERVER_RUNTIME_LAYOUT_CONTRACT.json", layout)
    runner_bytes = (BUILD_ROOT / "PREPARE_AND_RUN.sh").read_bytes()
    runner_vars = [
        "install_name", "package_id", "return_tag", "result_root", "return_zip", "return_sha", "server_root", "bootstrap_root",
        "compile_argv_json", "compile_source_identity_json", "compile_exit_txt", "compile_driver_log", "compile_first_error_txt",
        "compile_log_head_txt", "compile_log_tail_txt", "compile_full_log", "return_allowlist", "package_root", "runtime", "layout_helper",
        "compile_status", "run_status", "sim_started", "signal_status", "finalized", "bootstrap_ready", "sim_pid", "host_progress_pid",
        "run_root", "evidence_root", "compile_root", "cfg_root", "attempt", "root_gate_rc", "waveform_exit_kind", "waveform_receipt_rc",
        "runtime_dump_tcl", "actual_sim_argv_json", "query_receipt_rc",
    ]
    write_json("contracts/server_runner_return_resilience.json", {
        "schema": "server-runner-return-resilience-contract-v1",
        "package_id": PACKAGE_ID,
        "runner_path": f"{PACKAGE_ID}/PREPARE_AND_RUN.sh",
        "runner_sha256": sha(runner_bytes),
        "nounset_required": True,
        "package_owned_variables": runner_vars,
        "bootstrap_root_variable": "bootstrap_root",
        "first_fallible_tokens": ["command -v", "make -f"],
        "finalizer_arm_tokens": ["trap 'finalize $?' EXIT"],
        "compile_evidence_tokens": {"argv": "compile_argv.json", "source_identity": "compile_source_identity.json", "exit_code": "compile_exit.txt", "driver_log": "compile_driver.log", "first_error": "compile_first_error.txt", "bounded_head": "compile_log_head.txt", "bounded_tail": "compile_log_tail.txt"},
        "return_allowlist_tokens": ["compile_argv.json", "compile_source_identity.json", "compile_exit.txt", "compile_driver.log", "compile_first_error.txt", "compile_log_head.txt", "compile_log_tail.txt", "package_preflight.json", "install_preflight.json", "ndp_root_toplevel_pre.json", "ndp_root_toplevel_post.json", "ndp_root_toplevel_gate.json", "ndp_root_write_contract.json", "publication_preflight.json", "server_waveform_mandatory_return.py", "WAVEFORM_RUNTIME_RECEIPT.json", "DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0", "SIGNAL_QUERY_RECEIPT.json", "TIME_PROGRESS_RECEIPT.json", "FSDB_QUERY_BINDING.json"],
    })

    write_json("contracts/waveform_policy.json", {
        "schema": "node0004-fsdb-authoritative-smoke-policy-v1",
        "activation_epoch": "fsdb-authoritative-repeatable-return-v3-0a1dee9757c6",
        "capture": {"DUMP_VCD": 0, "DUMP_FSDB": 1, "TB_DUMP_FSDB": 0, "writer_count": 1, "primary": "wave.fsdb", "all_shards": True, "unbounded": True},
        "repeat": {"fixed_attempt": "smoke", "exact_owned_reset": True, "foreign_siblings_preserved": True, "fresh_execution_identity": True, "non_overwriting_return": True},
        "failure": {"missing_wave_after_start": "FAIL_CLOSED", "time_zero_only": "FAIL_CLOSED", "query_failure": "DIAGNOSTIC_EVIDENCE_INCOMPLETE_RAW_AND_CORE_PRESERVED"},
        "classification": "DIAGNOSTIC_SMOKE_ONLY_NOT_FORMAL_SUCCESSOR",
    })

    manifest = {
        "schema": "node0004-fsdb-authoritative-smoke-package-v1",
        "package_id": PACKAGE_ID,
        "install_name": PACKAGE_ID,
        "status": "PACKAGE_READY_NOT_RUN",
        "classification": "DIAGNOSTIC_SMOKE_ONLY_NOT_FORMAL_SERIALIZED_SUCCESSOR",
        "formal_operator_successor": False,
        "candidate_release": False,
        "activation_epoch": "fsdb-authoritative-repeatable-return-v3-0a1dee9757c6",
        "previous_version_progress": "v88b compile/elaboration passed and actual-source evidence disproved the retired ACK allegation as an observer/source-identity semantic false positive; its direct-VCD UCLI flow stopped at time 0.",
        "current_purpose": "Production-prove FSDB v3 time advance, attempt-local authoritative FSDB, complete registered smoke-event query and repeat-safe distinct formal returns before any formal family rebuild.",
        "frozen": {"config": True, "numeric": True, "workload": True, "golden": True, "functional_rtl": True},
        "retired_ack_comparator_present": False,
        "dump": {"DUMP_VCD": 0, "DUMP_FSDB": 1, "TB_DUMP_FSDB": 0},
        "server_actions_performed": [],
        "source_package": frozen["source_zip"],
        "frozen_workload_import": "provenance/frozen_v88b_workload_import.json",
        "path_length_budget": {
            "declared_target_root_max_chars": 96,
            "longest_projected_relative_path": f"install/cfg_pkg/{PACKAGE_ID}/runs/c0/install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin",
            "longest_projected_relative_path_chars": 115,
            "max_projected_absolute_path_chars": 212,
            "absolute_path_limit_chars": 240,
        },
        "files": [],
    }
    write_json("package_manifest.json", manifest)
    manifest["files"] = [row for row in file_map() if row["path"] != "package_manifest.json"]
    write_json("package_manifest.json", manifest)
    # One final map rewrite records the exact manifest-independent member map.
    deterministic_zip(BUILD_ROOT, FINAL_ZIP)
    write_json("../../release_receipt.json", {
        "schema": "node0004-fsdb-smoke-release-receipt-v1",
        "package_id": PACKAGE_ID,
        "status": "PACKAGE_READY_NOT_RUN",
        "zip": file_identity(FINAL_ZIP),
        "runner": file_identity(BUILD_ROOT / "PREPARE_AND_RUN.sh"),
        "manifest": file_identity(BUILD_ROOT / "package_manifest.json"),
        "activation_epoch": "fsdb-authoritative-repeatable-return-v3-0a1dee9757c6",
        "server_action": "NONE",
    })
    print(FINAL_ZIP)
    return 0


def post_request() -> dict[str, object]:
    def entry(source: str, archive: str | None = None, required: bool = False, source_root: str = "attempt") -> dict[str, object]:
        return {"source_root": source_root, "source": source, "archive": archive or source, "required": required}
    entries = [
        entry("evidence/compile_rootcause/compile_argv.json", required=True), entry("evidence/compile_rootcause/compile_source_identity.json", required=True),
        entry("evidence/compile_rootcause/compile_exit.txt", required=True), entry("evidence/compile_rootcause/compile_driver.log", required=True),
        entry("evidence/compile_rootcause/compile_first_error.txt", required=True), entry("evidence/compile_rootcause/compile_log_head.txt", required=True),
        entry("evidence/compile_rootcause/compile_log_tail.txt", required=True), entry("evidence/compile_exit_status.txt", required=True),
        entry("evidence/run_exit_status.txt", required=True), entry("evidence/signal_status.txt", required=True),
        entry("package_manifest.json", "evidence/returned_package_manifest.json", True, "package"),
        entry("evidence/package_preflight.json", required=True), entry("evidence/install_preflight.json", required=True),
        entry("evidence/ndp_root_toplevel_pre.json", required=True), entry("evidence/ndp_root_toplevel_post.json", required=True),
        entry("evidence/ndp_root_toplevel_gate.json", required=True), entry("evidence/ndp_root_write_contract.json", required=True),
        entry("evidence/publication_preflight.json", required=True), entry("evidence/actual_sim_argv.json"),
        entry("evidence/fsdb_smoke/SIGNAL_QUERY_RECEIPT.json"), entry("evidence/fsdb_smoke/TIME_PROGRESS_RECEIPT.json"),
        entry("evidence/fsdb_smoke/FSDB_QUERY_BINDING.json"), entry("evidence/fsdb_smoke/DIAGNOSTIC_STATUS.json"),
        entry("c0/sim.log", "runs/c0/sim.log"), entry("c0/simulator_argv.txt", "runs/c0/simulator_argv.txt"),
        entry("c0/host_progress.log", "runs/c0/host_progress.log"), entry("run/sim_results/dump_waveform.tcl", "runs/c0/dump_waveform.tcl"),
    ]
    return {
        "schema": "server-post-sim-return-request-v1", "package_id": PACKAGE_ID,
        "result_root": "/home/panqs/ndp/simresult", "return_basename_template": "{package_id}_{execution_id}_return.zip",
        "core_entries": entries,
        "waveform_discovery": {"plan_member": "contracts/server_waveform_mandatory_plan.json", "collector_member": "package_tools/server_waveform_mandatory_return.py", "runtime_receipt_source": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json", "collect_all_matching": True, "required_when_simulation_started": True, "no_size_limit": True, "manifest_archive_path": "waveforms/WAVEFORM_RUNTIME_RECEIPT.json"},
        "plugins": [],
        "max_plugin_output_bytes": 1048576,
        "claim_boundary": "Core and authoritative raw FSDB return survive query failure; incomplete time-progress/query evidence is fail-closed for smoke adjudication.",
    }


def layout_contract() -> dict[str, object]:
    projected = [
        "install/cfg_pkg/.codex_owner.{name}.json",
        f"install/codex_runs/{PACKAGE_ID}/.codex_owner.{{attempt}}.json",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/c0/sim.log",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/compile/sim_results/compile_driver.log",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/runtime_layout_receipt.json",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/run/sim_results/wave.fsdb",
    ]
    return {
        "schema": "server_package_runtime_layout_v1", "package_id": PACKAGE_ID, "install_name": PACKAGE_ID,
        "runner_member": "PREPARE_AND_RUN.sh", "manifest_member": "package_manifest.json",
        "shared_layout_helper": {"member": "package_tools/server_package_runtime_layout.py", "sha256": sha((BUILD_ROOT / "package_tools/server_package_runtime_layout.py").read_bytes())},
        "tb_cwd": "$server_root", "fixed_result_root": "/home/panqs/ndp/simresult",
        "required_preexisting_parents": ["install"], "package_creatable_parent_dirs": ["install/cfg_pkg", "install/codex_runs"],
        "runtime_roots": {"cfg_root": f"install/cfg_pkg/{PACKAGE_ID}", "run_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}", "evidence_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence", "compile_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/compile"},
        "payload_mounts": [{"source_prefix": "workload/runtime/", "runtime_prefix": f"install/cfg_pkg/{PACKAGE_ID}/"}],
        "sca_consumers": [{"member": "workload/runtime/runs/c0/sca_cfg.json", "plusarg": "SCA_CFG", "mode": "read_inputs"}, {"member": "workload/runtime/runs/c0/sca_cfg_D.json", "plusarg": "SCA_CFG_D", "mode": "write_outputs"}],
        "runner_bindings": {"layout_prepare_marker": "layout_values=\"$(python3 \"$layout_helper\" prepare", "tb_cwd_marker": "cd \"$server_root\"", "compile_marker": "echo RUNTIME_LAYOUT_COMPILE_START", "simulation_marker": "echo RUNTIME_LAYOUT_SIMULATION_START"},
        "path_budget": {"declared_target_root_max_chars": 96, "attempt_max_chars": 10, "absolute_path_limit_chars": 240, "max_projected_absolute_path_chars": 212, "additional_projected_paths": projected},
        "repeat_execution": {"mode": "RESET_EXACT_PACKAGE_OWNED_RUNTIME_ROOTS", "cfg_root_policy": "RESET_AND_RECREATE_EXACT_INSTALL_NAME", "run_root_policy": "RESET_AND_RECREATE_EXACT_PACKAGE_ATTEMPT", "foreign_sibling_policy": "PRESERVE", "symlink_or_special_entry_policy": "FAIL_CLOSED", "ownership_marker": ".codex_owner.{name}.json", "return_name_policy": "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS"},
        "finalizer": {"arm_marker": "trap 'finalize $?' EXIT", "first_preflight_marker": "if [ \"$#\" -ne 1 ]; then", "required_scenarios": ["normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM"]},
        "claim_boundary": "Mechanical install-subtree, exact-owned reset and distinct return layout only; no DUT claim.",
    }


RUNTIME_HELPER = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path

PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s1"

def digest(path):
    data = path.read_bytes(); return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

def root_snapshot(root):
    return [{"name": p.name, "type": "directory" if p.is_dir() else "file" if p.is_file() else "symlink" if p.is_symlink() else "other"} for p in sorted(root.iterdir(), key=lambda p:p.name)]

def main():
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest="cmd",required=True)
    for name in ("preflight","path-budget"):
        q=s.add_parser(name); q.add_argument("--package-root",type=Path,required=True)
        if name=="path-budget": q.add_argument("--target-root",type=Path,required=True)
    q=s.add_parser("verify-install"); q.add_argument("--package-root",type=Path,required=True); q.add_argument("--cfg-root",type=Path,required=True)
    q=s.add_parser("root-snapshot"); q.add_argument("--server-root",type=Path,required=True)
    q=s.add_parser("root-compare"); q.add_argument("--pre",type=Path,required=True); q.add_argument("--post",type=Path,required=True); q.add_argument("--contract",type=Path,required=True)
    a=p.parse_args(); errors=[]; detail={}
    if a.cmd=="root-snapshot": print(json.dumps(root_snapshot(a.server_root),sort_keys=True)); return 0
    if a.cmd=="root-compare":
        pre=json.loads(a.pre.read_text()); post=json.loads(a.post.read_text()); ok=pre==post
        print(json.dumps({"schema":"ndp-root-toplevel-gate-v1","valid":ok,"ndp_root_toplevel_unchanged":ok,"failure_class":None if ok else "SERVER_NDP_ROOT_TOPLEVEL_ENTRY_CREATED_OR_CHANGED","pre":pre,"post":post},sort_keys=True)); return 0 if ok else 1
    root=a.package_root
    if a.cmd=="path-budget":
        contract=json.loads((root/"SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text()); limit=contract["path_budget"]["absolute_path_limit_chars"]
        paths=[]
        for f in (root/"workload/runtime").rglob("*"):
            if f.is_file(): paths.append(f"install/cfg_pkg/{PACKAGE_ID}/"+f.relative_to(root/"workload/runtime").as_posix())
        paths += [x.replace("{attempt}","x"*10).replace("{name}",PACKAGE_ID) for x in contract["path_budget"]["additional_projected_paths"]]
        longest=max(paths,key=len); projected=len(str(a.target_root).rstrip("/"))+1+len(longest); ok=projected<=limit
        print(json.dumps({"schema":"server-package-path-budget-v1","pass":ok,"projected":projected,"limit":limit,"longest":longest},sort_keys=True)); return 0 if ok else 1
    required=["PREPARE_AND_RUN.sh","package_manifest.json","SERVER_RUNTIME_LAYOUT_CONTRACT.json","contracts/server_waveform_mandatory_plan.json","contracts/server_post_sim_return_request.json","contracts/fsdb_smoke_query_profile.json","diagnostics/fsdb_smoke_query_source_report.json","package_tools/dump_waveform.tcl","package_tools/server_waveform_mandatory_return.py","package_tools/server_post_sim_return.py","package_tools/server_package_runtime_layout.py","package_tools/fsdb_smoke_event_parser.py","tb_probe/fsdb_smoke_event_probe.svh","workload/runtime/runs/c0/sca_cfg.json","workload/runtime/runs/c0/sca_cfg_D.json"]
    base=root if a.cmd=="preflight" else a.cfg_root
    if a.cmd=="preflight":
        for rel in required:
            if not (base/rel).is_file(): errors.append("missing:"+rel)
        forbidden=[]
        for f in (root/"tb_probe").glob("*"):
            text=f.read_text(errors="replace")
            if "arb_req_ready" in text or "ACK_INLINE" in text: forbidden.append(f.name)
        if forbidden: errors.append("retired_ack_comparator_present:"+",".join(forbidden))
    else:
        source=root/"workload/runtime"
        for f in source.rglob("*"):
            if f.is_file():
                rel=f.relative_to(source)
                if not (base/rel).is_file() or (base/rel).read_bytes()!=f.read_bytes(): errors.append("installed_identity:"+rel.as_posix())
    print(json.dumps({"schema":"node0004-fsdb-smoke-preflight-v1","command":a.cmd,"pass":not errors,"errors":errors,"package_id":PACKAGE_ID,"claim_boundary":"Package/runtime plumbing only."},sort_keys=True)); return 0 if not errors else 1
if __name__=="__main__": raise SystemExit(main())
'''


EVENT_PARSER = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re
from pathlib import Path

EVENT=re.compile(r"^CODEX_FSDB_SMOKE_EVENT_V1 sequence=(\d+) time_tick=(\d+) candidate=([A-Za-z0-9_.-]+) width=(\d+) value=([bB]?[01xXzZ]+)$")
SUMMARY=re.compile(r"^CODEX_FSDB_SMOKE_SUMMARY_V1 time_tick=(\d+) time_zero=([01xXzZ]) time_progress=([01xXzZ]) rst_n=([01xXzZ])$")
def ident(path):
    data=path.read_bytes(); return {"path":str(path),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
def main():
    p=argparse.ArgumentParser()
    for name in ("log","profile","source-report","waveform-receipt","actual-compile-argv","actual-sim-argv","dump-control","output-dir"): p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args(); a.output_dir.mkdir(parents=True,exist_ok=True)
    profile=json.loads(a.profile.read_text()); source=json.loads(a.source_report.read_text()); raw=json.loads(a.waveform_receipt.read_text())
    catalog=profile["candidates"]; by_id={c["candidate_id"]:c for c in catalog}; events=[]; summary=None; errors=[]
    for line in a.log.read_text(encoding="utf-8",errors="replace").splitlines():
        m=EVENT.match(line.strip())
        if m:
            seq,tick,cid,width,value=m.groups(); c=by_id.get(cid)
            if c is None: errors.append("unexpected_candidate:"+cid); continue
            events.append({"sequence":int(seq),"time_tick":int(tick),"candidate_id":cid,"hierarchical_path":c["hierarchical_path"],"width":int(width),"value":value.lower()})
        m=SUMMARY.match(line.strip())
        if m: summary=m.groups()
    if [e["sequence"] for e in events] != list(range(len(events))): errors.append("noncontiguous_sequence")
    if summary is None: errors.append("summary_missing")
    covered=sorted({e["candidate_id"] for e in events}); expected=sorted(by_id); missing=sorted(set(expected)-set(covered))
    if missing: errors.append("missing_candidates:"+",".join(missing))
    if not any(e["candidate_id"]=="time_zero_marker" and e["time_tick"]==0 and e["value"]=="1" for e in events): errors.append("time_zero_marker_missing")
    if not any(e["candidate_id"]=="time_progress_marker" and e["time_tick"]>0 and e["value"]=="1" for e in events): errors.append("time_progress_missing")
    raw_complete=(raw.get("schema")=="server-waveform-runtime-receipt-v3" and raw.get("pass") is True and bool(raw.get("waveforms")) and all(w.get("completeness")=="COMPLETE" for w in raw.get("waveforms",[])))
    if not raw_complete: errors.append("raw_fsdb_incomplete")
    if raw.get("execution_id")!=os.environ.get("CODEX_EXECUTION_ID"): errors.append("execution_identity_drift")
    end=[]
    for c in catalog:
        rows=[e for e in events if e["candidate_id"]==c["candidate_id"]]
        if rows: end.append({k:rows[-1][k] for k in ("candidate_id","hierarchical_path","width","time_tick","value")})
    receipt={"schema":"server-waveform-signal-query-receipt-v1","package_id":os.environ["CODEX_PACKAGE_ID"],"execution_id":os.environ["CODEX_EXECUTION_ID"],"attempt_id":os.environ["CODEX_ATTEMPT_ID"],"profile_sha256":ident(a.profile)["sha256"],"probe_catalog_sha256":ident(a.source_report)["sha256"],"timescale":profile["timescale"],"completeness":"COMPLETE" if not errors else "PARTIAL","catalog":catalog,"capture":{"format":"REGISTERED_EVENT_ROWS","ordered":True,"every_transition":True,"no_byte_limit":True,"no_event_limit":True,"sampling":False,"truncation":False,"flush_complete":summary is not None,"source_generation_report":{"path":str(a.source_report),"sha256":ident(a.source_report)["sha256"]}},"candidate_coverage":{"expected":expected,"covered":covered,"missing":missing,"unexpected":[]},"events":events,"candidate_end_states":end or [{"candidate_id":catalog[0]["candidate_id"],"hierarchical_path":catalog[0]["hierarchical_path"],"width":1,"time_tick":0,"value":"x"}],"claim_boundary":"Registered complete package-smoke marker/reset events only; no DUT functional claim."}
    (a.output_dir/"SIGNAL_QUERY_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    progressed=not errors and any(e["time_tick"]>0 for e in events) and any(int(w.get("bytes",0))>0 for w in raw.get("waveforms",[]))
    progress={"schema":"node0004-fsdb-smoke-time-progress-v1","package_id":receipt["package_id"],"execution_id":receipt["execution_id"],"attempt_id":receipt["attempt_id"],"time_zero_marker":any(e["time_tick"]==0 for e in events),"time_greater_than_zero":any(e["time_tick"]>0 for e in events),"raw_fsdb_complete":raw_complete,"pass":progressed,"errors":errors}
    (a.output_dir/"TIME_PROGRESS_RECEIPT.json").write_text(json.dumps(progress,indent=2,sort_keys=True)+"\n")
    binding={"schema":"node0004-fsdb-smoke-query-binding-v1","package_id":receipt["package_id"],"execution_id":receipt["execution_id"],"attempt_id":receipt["attempt_id"],"identities":{"profile":ident(a.profile),"source_report":ident(a.source_report),"raw_receipt":ident(a.waveform_receipt),"actual_compile_argv":ident(a.actual_compile_argv),"actual_sim_argv":ident(a.actual_sim_argv),"dump_control":ident(a.dump_control)},"waveforms":raw.get("waveforms",[]),"allowlist_complete":not errors,"pass":progressed,"errors":errors,"claim_boundary":"Exact same-attempt compile/sim/dump/raw/query identity binding."}
    (a.output_dir/"FSDB_QUERY_BINDING.json").write_text(json.dumps(binding,indent=2,sort_keys=True)+"\n")
    (a.output_dir/"DIAGNOSTIC_STATUS.json").write_text(json.dumps({"schema":"server-diagnostic-evidence-status-v1","status":"COMPLETE" if progressed else "DIAGNOSTIC_EVIDENCE_INCOMPLETE","errors":errors},indent=2,sort_keys=True)+"\n")
    return 0 if progressed else 1
if __name__=="__main__": raise SystemExit(main())
'''


EVENT_PROBE = r'''`timescale 1ps/1ps
module codex_fsdb_smoke_event_probe(input logic clk, input logic rst_n);
  integer sequence;
  logic time_zero_marker;
  logic time_progress_marker;
  logic last_rst_n;
  task automatic emit(input string candidate, input logic value);
    $display("CODEX_FSDB_SMOKE_EVENT_V1 sequence=%0d time_tick=%0t candidate=%s width=1 value=%b", sequence, $time, candidate, value);
    sequence = sequence + 1;
  endtask
  initial begin
    sequence = 0;
    time_zero_marker = 1'b0;
    time_progress_marker = 1'b0;
    last_rst_n = rst_n;
    emit("time_zero_marker", time_zero_marker);
    time_zero_marker = 1'b1;
    emit("time_zero_marker", time_zero_marker);
    emit("time_progress_marker", time_progress_marker);
    emit("top_rst_n", rst_n);
  end
  always @(rst_n) begin
    if ($time > 0 && rst_n !== last_rst_n) begin
      last_rst_n = rst_n;
      emit("top_rst_n", rst_n);
    end
  end
  always @(posedge clk) begin
    if ($time > 0 && time_progress_marker !== 1'b1) begin
      time_progress_marker = 1'b1;
      emit("time_progress_marker", time_progress_marker);
    end
  end
  final begin
    $display("CODEX_FSDB_SMOKE_SUMMARY_V1 time_tick=%0t time_zero=%b time_progress=%b rst_n=%b", $time, time_zero_marker, time_progress_marker, rst_n);
  end
endmodule
bind tb_NDP_Top_new_phy codex_fsdb_smoke_event_probe u_codex_fsdb_smoke_probe(.clk(clk), .rst_n(rst_n));
'''


README = '''# Serialized Conv FSDB-only smoke s1

This is a diagnostic transport smoke, not a formal operator successor and not
a DUT adjudication package. It imports the exact v88b workload, leaves
config/numeric/golden/functional RTL unchanged, removes the retired ACK
comparator, and adds only package-owned FSDB/query/runtime-return surfaces.

Run exactly once per requested execution from the uploaded package directory:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01
```

The same command is intentionally repeatable. Each invocation resets only the
fixed package cfg root and exact `smoke` attempt root, while publishing a new
non-overwriting formal return ZIP under `/home/panqs/ndp/simresult`.
'''


RUNNER = r'''#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
install_name="r5_n4_hw_fsdbsmoke_s1"
package_id="r5_n4_hw_fsdbsmoke_s1"
return_tag="r$(date -u +%s%N)_$$"
result_root="/home/panqs/ndp/simresult"
return_zip="$result_root/${install_name}_${return_tag}_return.zip"
return_sha="${return_zip}.sha256"
server_root="${1:-}"
bootstrap_root="$server_root/install/codex_runs/$package_id/bootstrap-$return_tag"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
compile_full_log="$bootstrap_root/compile_driver.full.log"
return_allowlist="compile_argv.json compile_source_identity.json compile_exit.txt compile_driver.log compile_first_error.txt compile_log_head.txt compile_log_tail.txt"
package_root="$(dirname "${BASH_SOURCE[0]}")"
runtime="${package_root}/package_tools/fsdb_smoke_runtime.py"
layout_helper="${package_root}/package_tools/server_package_runtime_layout.py"
compile_status=125
run_status=125
sim_started=false
signal_status=NONE
finalized=0
bootstrap_ready=0
sim_pid=
host_progress_pid=
run_root=
evidence_root=
compile_root=
cfg_root=
attempt="smoke"
root_gate_rc=0
waveform_exit_kind=SIMULATION_NOT_STARTED
waveform_receipt_rc=0
runtime_dump_tcl=
actual_sim_argv_json=
query_receipt_rc=0

runner_fail() { rc="$1"; shift; printf 'RUNNER_ERROR code=%s package=%s message=%s\n' "$rc" "$package_id" "$*" >&2; exit "$rc"; }
publish_compile_evidence_to_attempt() {
  [ -n "$evidence_root" ] && [ -d "$evidence_root" ] || return 0
  target="$evidence_root/compile_rootcause"; mkdir -p -- "$target" || return 98
  for source in "$compile_argv_json" "$compile_source_identity_json" "$compile_exit_txt" "$compile_driver_log" "$compile_first_error_txt" "$compile_log_head_txt" "$compile_log_tail_txt"; do
    [ -f "$source" ] || continue; cp -f -- "$source" "$target/$(basename "$source")" || return 98
  done
}
publish_minimal_return() {
  mkdir -p -- "$result_root" || return 98; [ -d "$result_root" ] && [ -w "$result_root" ] || return 98
  stage="${result_root}/.${install_name}.${return_tag}.partial"; [ ! -e "$stage" ] || return 98; mkdir -p -- "$stage/evidence/compile_rootcause" || return 98
  if [ "$bootstrap_ready" -eq 1 ] && [ -d "$bootstrap_root" ]; then
    for source in "$compile_argv_json" "$compile_source_identity_json" "$compile_exit_txt" "$compile_driver_log" "$compile_first_error_txt" "$compile_log_head_txt" "$compile_log_tail_txt"; do [ -f "$source" ] && cp -f -- "$source" "$stage/evidence/compile_rootcause/$(basename "$source")"; done
  fi
  [ -f "$stage/evidence/compile_rootcause/compile_argv.json" ] || printf '%s\n' '{"schema":"server-compile-argv-v1","status":"RUNNER_PRE_BOOTSTRAP_FAILURE"}' > "$stage/evidence/compile_rootcause/compile_argv.json"
  [ -f "$stage/evidence/compile_rootcause/compile_source_identity.json" ] || printf '%s\n' '{"schema":"server-compile-source-identity-v1","status":"RUNNER_PRE_BOOTSTRAP_FAILURE"}' > "$stage/evidence/compile_rootcause/compile_source_identity.json"
  [ -f "$stage/evidence/compile_rootcause/compile_exit.txt" ] || printf '%s\n' "$compile_status" > "$stage/evidence/compile_rootcause/compile_exit.txt"
  [ -f "$stage/evidence/compile_rootcause/compile_driver.log" ] || printf '%s\n' 'compile driver did not start' > "$stage/evidence/compile_rootcause/compile_driver.log"
  [ -f "$stage/evidence/compile_rootcause/compile_first_error.txt" ] || printf '%s\n' 'runner failed before compile driver start' > "$stage/evidence/compile_rootcause/compile_first_error.txt"
  [ -f "$stage/evidence/compile_rootcause/compile_log_head.txt" ] || printf '%s\n' 'compile driver did not start' > "$stage/evidence/compile_rootcause/compile_log_head.txt"
  [ -f "$stage/evidence/compile_rootcause/compile_log_tail.txt" ] || printf '%s\n' 'compile driver did not start' > "$stage/evidence/compile_rootcause/compile_log_tail.txt"
  printf '%s\n' "$compile_status" > "$stage/compile_exit_status.txt"; printf '%s\n' "$run_status" > "$stage/run_exit_status.txt"; printf '%s\n' "$signal_status" > "$stage/signal_status.txt"; printf '%s\n' PRECHECK_PARTIAL_RETURN > "$stage/SERVER_RESULT_GATE"
  python3 - "$stage" "$return_zip" "$install_name" <<'PY'
import hashlib,json,os,pathlib,sys,zipfile
stage=pathlib.Path(sys.argv[1]); target=pathlib.Path(sys.argv[2]); identity=sys.argv[3]
manifest={"schema":"server-partial-return-v1","install_name":identity,"classification":"PRECHECK_PARTIAL_RETURN"}
(stage/"RETURN_MANIFEST.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
tmp=target.parent/("."+target.name+".tmp."+str(os.getpid()))
with zipfile.ZipFile(tmp,"x",compression=zipfile.ZIP_DEFLATED) as z:
  for path in sorted(p for p in stage.rglob("*") if p.is_file()): z.write(path,f"{identity}_return/{path.relative_to(stage).as_posix()}")
with zipfile.ZipFile(tmp) as z: assert z.testzip() is None
os.replace(tmp,target); digest=hashlib.sha256(target.read_bytes()).hexdigest(); side=pathlib.Path(str(target)+".sha256"); st=pathlib.Path(str(side)+".tmp."+str(os.getpid())); st.write_text(f"{digest}  {target.name}\n"); os.replace(st,side)
PY
  rc=$?; rm -rf -- "$stage"; return "$rc"
}
finalize() {
  original="$1"; [ "$finalized" -eq 0 ] || exit "$original"; finalized=1; trap - EXIT INT TERM HUP; set +e
  [ -z "$host_progress_pid" ] || kill "$host_progress_pid" 2>/dev/null; [ -z "$host_progress_pid" ] || wait "$host_progress_pid" 2>/dev/null
  if [ -n "$evidence_root" ] && [ -d "$evidence_root" ] && [ -f "$evidence_root/ndp_root_toplevel_pre.json" ]; then
    python3 "$runtime" root-snapshot --server-root "$server_root" > "$evidence_root/ndp_root_toplevel_post.json"; root_gate_rc=$?
    [ "$root_gate_rc" -ne 0 ] || python3 "$runtime" root-compare --pre "$evidence_root/ndp_root_toplevel_pre.json" --post "$evidence_root/ndp_root_toplevel_post.json" --contract "$evidence_root/ndp_root_write_contract.json" > "$evidence_root/ndp_root_toplevel_gate.json"; root_gate_rc=$?
    [ "$root_gate_rc" -eq 0 ] || printf '%s\n' '{"schema":"ndp-root-toplevel-gate-v1","valid":false,"ndp_root_toplevel_unchanged":false,"failure_class":"SERVER_NDP_ROOT_TOPLEVEL_ENTRY_CREATED_OR_CHANGED"}' > "$evidence_root/ndp_root_toplevel_gate.json"
  fi
  publish_compile_evidence_to_attempt
  [ -n "$evidence_root" ] && [ -d "$evidence_root" ] && [ -n "$run_root" ] && [ -d "$run_root" ] || { publish_minimal_return; exit "$original"; }
  printf '%s\n' "$compile_status" > "$evidence_root/compile_exit_status.txt"; printf '%s\n' "$run_status" > "$evidence_root/run_exit_status.txt"; printf '%s\n' "$signal_status" > "$evidence_root/signal_status.txt"
  if [ "$sim_started" != true ]; then if [ "$compile_status" -ne 0 ]; then waveform_exit_kind=COMPILE_FAILURE; else waveform_exit_kind=SIMULATION_NOT_STARTED; fi
  elif [ "$signal_status" = HUP ]; then waveform_exit_kind=HUP; elif [ "$signal_status" = INT ]; then waveform_exit_kind=INT; elif [ "$signal_status" = TERM ]; then waveform_exit_kind=TERM
  elif [ "$run_status" -eq 124 ]; then waveform_exit_kind=TIMEOUT; elif [ "$run_status" -eq 0 ]; then waveform_exit_kind=NATURAL; else waveform_exit_kind=SIMULATION_NONZERO; fi
  mkdir -p -- "$evidence_root/waveform"
  python3 "$package_root/package_tools/server_waveform_mandatory_return.py" collect-runtime --plan "$package_root/contracts/server_waveform_mandatory_plan.json" --attempt-root "$run_root" --execution-id "$return_tag" --simulation-started "$sim_started" --exit-kind "$waveform_exit_kind" --output "$evidence_root/waveform/WAVEFORM_RUNTIME_RECEIPT.json"; waveform_receipt_rc=$?
  export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag" CODEX_ATTEMPT_ID="$attempt" CODEX_PACKAGE_ID="$package_id" CODEX_SIM_EXIT_CODE="$run_status" CODEX_SIM_SIGNAL="$signal_status" CODEX_SIM_STARTED="$sim_started" CODEX_NATURAL_TERMINAL=false
  mkdir -p -- "$evidence_root/fsdb_smoke"
  if [ "$sim_started" = true ]; then
    python3 "$package_root/package_tools/fsdb_smoke_event_parser.py" --log "$run_root/c0/sim.log" --profile "$package_root/contracts/fsdb_smoke_query_profile.json" --source-report "$package_root/diagnostics/fsdb_smoke_query_source_report.json" --waveform-receipt "$evidence_root/waveform/WAVEFORM_RUNTIME_RECEIPT.json" --actual-compile-argv "$evidence_root/compile_rootcause/compile_argv.json" --actual-sim-argv "$evidence_root/actual_sim_argv.json" --dump-control "$runtime_dump_tcl" --output-dir "$evidence_root/fsdb_smoke"; query_receipt_rc=$?
  else
    printf '%s\n' '{"schema":"server-diagnostic-evidence-status-v1","status":"NOT_APPLICABLE_SIMULATION_NOT_STARTED","errors":[]}' > "$evidence_root/fsdb_smoke/DIAGNOSTIC_STATUS.json"
  fi
  # The parser writes SIGNAL_QUERY_RECEIPT.json, TIME_PROGRESS_RECEIPT.json and FSDB_QUERY_BINDING.json before shared finalization.
  python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"; core=$?
  [ -f "$evidence_root/return_core/RETURN_FINALIZER_STATE.json" ] || core=98
  final="$original"; [ "$final" -ne 0 ] || [ "$core" -eq 0 ] || final="$core"; [ "$root_gate_rc" -eq 0 ] || final=96; [ "$waveform_receipt_rc" -eq 0 ] || final=97; [ "$query_receipt_rc" -eq 0 ] || [ "$final" -ne 0 ] || final=95
  printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$final" "$return_zip" >&2; exit "$final"
}
on_signal() { signal_status="$1"; [ -z "$sim_pid" ] || kill -TERM "$sim_pid" 2>/dev/null; finalize "$2"; }
trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
if [ "$#" -ne 1 ]; then runner_fail 2 "expected exactly one server_root argument; usage: bash PREPARE_AND_RUN.sh /absolute/path/to/server_root"; fi
case "$1" in /*) ;; *) runner_fail 2 "server_root must be absolute: $1";; esac
for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || runner_fail 3 "required tool not found: $tool"; done
package_root="$(cd "$package_root" && pwd -P)" || runner_fail 2 "cannot resolve package_root"
runtime="${package_root}/package_tools/fsdb_smoke_runtime.py"; layout_helper="${package_root}/package_tools/server_package_runtime_layout.py"
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || runner_fail 2 "server_root missing or unreadable"
bootstrap_root="$server_root/install/codex_runs/$package_id/bootstrap-$return_tag"
compile_argv_json="$bootstrap_root/compile_argv.json"; compile_source_identity_json="$bootstrap_root/compile_source_identity.json"; compile_exit_txt="$bootstrap_root/compile_exit.txt"; compile_driver_log="$bootstrap_root/compile_driver.log"; compile_first_error_txt="$bootstrap_root/compile_first_error.txt"; compile_log_head_txt="$bootstrap_root/compile_log_head.txt"; compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"; compile_full_log="$bootstrap_root/compile_driver.full.log"
mkdir -p -- "$bootstrap_root" || runner_fail 14 "cannot create bootstrap evidence root"
printf '%s\n' '{"schema":"server-compile-argv-v1","status":"NOT_YET_RECORDED"}' > "$compile_argv_json"; printf '%s\n' '{"schema":"server-compile-source-identity-v1","status":"NOT_YET_RECORDED"}' > "$compile_source_identity_json"; printf '%s\n' 125 > "$compile_exit_txt"; printf '%s\n' 'compile driver has not started' > "$compile_driver_log"; cp "$compile_driver_log" "$compile_first_error_txt"; cp "$compile_driver_log" "$compile_log_head_txt"; cp "$compile_driver_log" "$compile_log_tail_txt"; bootstrap_ready=1
mkdir -p -- "$result_root" || runner_fail 9 "cannot create result root"; [ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || runner_fail 10 "fresh return identity collision"
ndp_pre_snapshot="$(python3 "$runtime" root-snapshot --server-root "$server_root")" || runner_fail 12 "NDP root pre-snapshot failed"
layout_values="$(python3 "$layout_helper" prepare --server-root "$server_root" --package-id "$package_id" --install-name "$install_name" --attempt "$attempt" --format shell)" || runner_fail 13 "repeat-safe exact-owned layout prepare failed"
eval "$layout_values"; cfg_root="$CFG_ROOT"; run_root="$RUN_ROOT"; evidence_root="$EVIDENCE_ROOT"; compile_root="$COMPILE_ROOT"
mkdir -p -- "$compile_root/sim_results" "$run_root/c0" "$run_root/run/sim_results" "$evidence_root/waveform"
printf '%s\n' "$ndp_pre_snapshot" > "$evidence_root/ndp_root_toplevel_pre.json"
printf '%s\n' '{"schema":"ndp-root-write-contract-v1","root_internal_write_targets":["install/cfg_pkg/r5_n4_hw_fsdbsmoke_s1","install/codex_runs/r5_n4_hw_fsdbsmoke_s1/smoke"],"external_write_target_policy":"unique formal return only"}' > "$evidence_root/ndp_root_write_contract.json"
printf '{"schema":"fixed-simresult-publication-preflight-v1","return_zip":"%s","return_sidecar":"%s","publication_state":"TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING"}\n' "$return_zip" "$return_sha" > "$evidence_root/publication_preflight.json"
python3 "$runtime" path-budget --package-root "$package_root" --target-root "$server_root" || runner_fail 8 "path-budget preflight failed"
python3 "$runtime" preflight --package-root "$package_root" > "$evidence_root/package_preflight.json" || runner_fail 5 "package preflight failed"
cp -a "$package_root/workload/runtime/." "$cfg_root/"
python3 "$runtime" verify-install --package-root "$package_root" --cfg-root "$cfg_root" > "$evidence_root/install_preflight.json" || runner_fail 6 "install identity failed"
python3 - "$cfg_root/runs/c0/sca_cfg_D.json" "$attempt" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text());
for value in d.values(): value["path"]=value["path"].replace("{attempt}",sys.argv[2])
p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
PY
echo RUNTIME_LAYOUT_COMPILE_START > "$evidence_root/compile_started.marker"
compile_argv=(timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0 "RUN_DIR=$compile_root" "VCS_EXTRA_OPTS=+incdir+$package_root/tb_probe $package_root/tb_probe/fsdb_smoke_event_probe.svh")
python3 - "$compile_argv_json" "$server_root" "${compile_argv[@]}" <<'PY'
import json,pathlib,sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({"schema":"server-compile-argv-v1","cwd":sys.argv[2],"argv":sys.argv[3:]},indent=2,sort_keys=True)+"\n")
PY
python3 - "$compile_source_identity_json" "$server_root/Makefile.tb_NDP_Top_new_phy" "$package_root/tb_probe/fsdb_smoke_event_probe.svh" "$package_root/package_tools/dump_waveform.tcl" <<'PY'
import hashlib,json,pathlib,sys
rows=[]
for raw in sys.argv[2:]:
 p=pathlib.Path(raw); data=p.read_bytes() if p.is_file() else b""; rows.append({"path":str(p),"exists":p.is_file(),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
pathlib.Path(sys.argv[1]).write_text(json.dumps({"schema":"server-compile-source-identity-v1","selected_sources":rows},indent=2,sort_keys=True)+"\n")
PY
cd "$server_root"
set +e; "${compile_argv[@]}" > "$compile_full_log" 2>&1; compile_status=$?; printf '%s\n' "$compile_status" > "$compile_exit_txt"
python3 - "$compile_full_log" "$compile_driver_log" "$compile_first_error_txt" "$compile_log_head_txt" "$compile_log_tail_txt" <<'PY'
import pathlib,re,sys
s,d,f,h,t=map(pathlib.Path,sys.argv[1:]); raw=s.read_bytes() if s.is_file() else b""; head=raw[:65536]; tail=raw[-65536:] if len(raw)>65536 else raw; h.write_bytes(head); t.write_bytes(tail); d.write_bytes(head+(b"\n--- BOUNDED HEAD/TAIL ---\n"+tail if len(raw)>65536 else b"")); lines=raw.decode(errors="replace").splitlines(); pats=[re.compile(x,re.I) for x in (r"^\s*(Error|Fatal)-\[",r"^\s*(error|fatal)\s*[:[]",r"^make: \*\*\*")]; hit=next((line for pat in pats for line in lines if pat.search(line)),next((line for line in lines if line.strip()),"compile log is empty")); f.write_text(hit[:4096]+"\n")
PY
publish_compile_evidence_to_attempt; [ "$compile_status" -eq 0 ] || runner_fail "$compile_status" "production compile failed"
runtime_dump_tcl="$run_root/run/sim_results/dump_waveform.tcl"
printf 'set CODEX_WAVE_PATH {%s}\n' "$run_root/run/sim_results/wave.fsdb" > "$runtime_dump_tcl"; cat "$package_root/package_tools/dump_waveform.tcl" >> "$runtime_dump_tcl"
simv="$compile_root/sim_results/simv"; sim_started=true; echo RUNTIME_LAYOUT_SIMULATION_START > "$evidence_root/simulation_started.marker"
printf '%s\n' "DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0 $simv -ucli -i $runtime_dump_tcl -l $run_root/c0/sim.log +vcs+lic+wait +SCA_CFG=$cfg_root/runs/c0/sca_cfg.json +SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json +CODEX_FSDB_SMOKE_QUERY" > "$run_root/c0/simulator_argv.txt"
actual_sim_argv_json="$evidence_root/actual_sim_argv.json"
python3 - "$run_root/c0/simulator_argv.txt" "$actual_sim_argv_json" <<'PY'
import json,pathlib,shlex,sys
pathlib.Path(sys.argv[2]).write_text(json.dumps({"schema":"server-sim-argv-v1","argv":shlex.split(pathlib.Path(sys.argv[1]).read_text())},indent=2,sort_keys=True)+"\n")
PY
DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0 timeout --foreground --signal=TERM --kill-after=30s 6h "$simv" -ucli -i "$runtime_dump_tcl" -l "$run_root/c0/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" +CODEX_FSDB_SMOKE_QUERY &
sim_pid=$!
( while kill -0 "$sim_pid" 2>/dev/null; do read -r host_monotonic _ < /proc/uptime; printf 'host_epoch=%s host_monotonic=%s stage=fsdb_smoke sim_log_bytes=%s\n' "$(date +%s)" "$host_monotonic" "$(wc -c < "$run_root/c0/sim.log" 2>/dev/null || printf 0)"; sleep 60; done ) > "$run_root/c0/host_progress.log" 2>&1 &
host_progress_pid=$!; wait "$sim_pid"; run_status=$?; sim_pid=; kill "$host_progress_pid" 2>/dev/null; wait "$host_progress_pid" 2>/dev/null; host_progress_pid=; exit "$run_status"
'''


if __name__ == "__main__":
    raise SystemExit(main())
