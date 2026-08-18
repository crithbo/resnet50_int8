#!/usr/bin/env python3
"""Build v99b from the exact tested v98b package with operational guards."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_n4_hw_v98b_lcdup_tuple10"
PACKAGE = "r5_n4_hw_v99b_lcdup_guarded"
FAMILY = "conv_serialized_node0004"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v98b_lcdup_tuple10.zip"
OUT = ROOT / "outputs/conv_node0004_v99b_lcdup_guarded_release6"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
TEXT = {".json", ".md", ".sh", ".py", ".sv", ".svh", ".v", ".vh", ".txt"}


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one replacement, found {count}")
    return text.replace(old, new)


def import_source() -> None:
    with zipfile.ZipFile(SOURCE) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("v98 source ZIP CRC failure")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or not pure.parts or pure.parts[0] != OLD:
                raise RuntimeError(f"unsafe v98 member: {info.filename}")
            relative = PurePosixPath(*pure.parts[1:])
            if not relative.parts:
                continue
            data = archive.read(info)
            target = TREE.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.suffix.lower() in TEXT or target.name in {"PREPARE_AND_RUN.sh", "RETURN_ALLOWLIST.json"}:
                data = data.decode("utf-8").replace(OLD, PACKAGE).encode("utf-8")
            target.write_bytes(data)
            if (info.external_attr >> 16) & stat.S_IXUSR:
                target.chmod(0o755)


def patch_observer() -> None:
    path = TREE / "tb_probe/observer_only_wide_causal.svh"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "if (force_all || sig_clk !== prev_sig_clk) begin",
        "if (force_all) begin",
        "clock event predicate",
    )
    text = replace_once(
        text,
        "always @(sig_clk or sig_rst_n or",
        "always @(sig_rst_n or",
        "clock sensitivity",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runner() -> None:
    path = TREE / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "return_sha=\"${return_zip}.sha256\"", "return_sha=\"${return_zip}.sha256\"\ncleanup_receipt=\"${return_zip}.cleanup.json\"", "cleanup receipt")
    text = replace_once(
        text,
        "observer_chunk=\n",
        "observer_chunk=\nguard_receipt=\ncompile_guard_receipt=\nfinalization_guard_receipt=\n",
        "guard variables",
    )
    text = replace_once(
        text,
        "  mkdir -p \"$stage/evidence/compile_rootcause\" || return 98\n",
        "  mkdir -p \"$stage/evidence/compile_rootcause\" || return 98\n"
        "  for source in \"$guard_receipt\" \"$compile_guard_receipt\" \"$finalization_guard_receipt\" \"$evidence_root/PROCESS_TREE_RECEIPT.json\" \"$evidence_root/SIM_EXIT_RECEIPT.json\"; do [ -n \"$source\" ] && [ -f \"$source\" ] && cp -f \"$source\" \"$stage/evidence/$(basename \"$source\")\"; done\n",
        "minimal guard evidence",
    )
    text = replace_once(
        text,
        '  for source in "$compile_argv_json" "$compile_source_identity_json" "$compile_exit_txt" "$compile_driver_log" "$compile_first_error_txt" "$compile_log_head_txt" "$compile_log_tail_txt" "$compile_full_log"; do [ -f "$source" ] && cp -f "$source" "$stage/evidence/compile_rootcause/$(basename "$source")"; done',
        '  for source in "$compile_argv_json" "$compile_source_identity_json" "$compile_exit_txt" "$compile_driver_log" "$compile_first_error_txt" "$compile_log_head_txt" "$compile_log_tail_txt"; do [ -f "$source" ] && cp -f "$source" "$stage/evidence/compile_rootcause/$(basename "$source")"; done',
        "minimal full compile exclusion",
    )
    text = replace_once(
        text,
        '    python3 "$package_root/package_tools/node0004_observerwide_event_parser.py" --contract "$package_root/contracts/observer_only_wide_causal_contract.json" --chunk "$evidence_root/observer/chunks/events-000000.jsonl" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --exit-code "$run_status" --signal "$signal_status" --timed-out "$timed_out" --simulation-started true --process-receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" --heartbeat-log "$evidence_root/supervisor_heartbeat.jsonl" --actual-argv "$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json" --output-dir "$evidence_root"',
        '    python3 "$package_root/package_tools/node0004_observerwide_event_parser.py" --contract "$package_root/contracts/observer_only_wide_causal_contract.json" --chunk "$evidence_root/observer/chunks/events-000000.jsonl" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --exit-code "$run_status" --signal "$signal_status" --timed-out "$timed_out" --simulation-started true --process-receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" --heartbeat-log "$evidence_root/supervisor_heartbeat.jsonl" --actual-argv "$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json" --guard-receipt "$guard_receipt" --output-dir "$evidence_root"',
        "streaming parser guard receipt",
    )
    text = replace_once(
        text,
        '    cp -f "$run_root/c0/sim.log" "$source_bound_log"',
        '    python3 "$package_root/package_tools/filter_source_bound_log.py" --source "$run_root/c0/sim.log" --output "$source_bound_log" --prefix CODEX_PROBE_V1 --max-bytes 10000000',
        "bounded source log filter",
    )
    text = replace_once(
        text,
        '  python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"\n  core_rc=$?',
        '  set +e\n  python3 "$package_root/package_tools/server_observer_runtime_supervision.py" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --mode finalization --attempt-root "$run_root" --owned-root "$bootstrap_root" --cwd "$server_root" --disk-path "$server_root/install" --min-free-bytes 20000000000 --growth-limit-bytes 2000000000 --timeout 900 --interval 2 --grace 30 --receipt "$finalization_guard_receipt" -- python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"\n  core_rc=$?\n  set -e\n  if [ "$core_rc" -ne 0 ] || [ ! -f "$return_zip" ]; then rm -f "$return_zip" "$return_sha"; publish_minimal_return; core_rc=$?; fi',
        "emergency partial return fallback",
    )
    text = replace_once(
        text,
        '  final="$original"; [ "$final" -ne 0 ] || [ "$core_rc" -eq 0 ] || final="$core_rc"; [ "$observer_rc" -eq 0 ] || final=97; [ "$source_bound_rc" -eq 0 ] || final=97; [ "$manifest_rc" -eq 0 ] || final=98\n  printf \'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\\n\' "$package_id" "$compile_status" "$run_status" "$signal_status" "$final" "$return_zip" >&2',
        '  cleanup_rc=98\n  if [ -f "$return_zip" ]; then python3 "$package_root/package_tools/server_package_attempt_cleanup.py" --server-root "$server_root" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --run-root "$run_root" --bootstrap-root "$bootstrap_root" --return-zip "$return_zip" --finalization-guard-receipt "$finalization_guard_receipt" --output "$cleanup_receipt"; cleanup_rc=$?; fi\n  final="$original"; [ "$final" -ne 0 ] || [ "$core_rc" -eq 0 ] || final="$core_rc"; [ "$observer_rc" -eq 0 ] || final=97; [ "$source_bound_rc" -eq 0 ] || final=97; [ "$manifest_rc" -eq 0 ] || final=98; [ "$cleanup_rc" -eq 0 ] || final=99\n  printf \'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s cleanup=%s\\n\' "$package_id" "$compile_status" "$run_status" "$signal_status" "$final" "$return_zip" "$cleanup_receipt" >&2',
        "post-return cleanup",
    )
    text = replace_once(
        text,
        'mkdir -p "$bootstrap_root" || runner_fail 14 "cannot create bootstrap evidence root"',
        'mkdir -p "$bootstrap_root" || runner_fail 14 "cannot create bootstrap evidence root"\nprintf \'{"attempt_id":"%s","execution_id":"%s","package_id":"%s"}\\n\' "$attempt" "$return_tag" "$package_id" > "$bootstrap_root/.codex_bootstrap_owner.json"',
        "bootstrap ownership marker",
    )
    text = replace_once(
        text,
        'cfg_root="$CFG_ROOT"; run_root="$RUN_ROOT"; evidence_root="$EVIDENCE_ROOT"; compile_root="$COMPILE_ROOT"',
        'cfg_root="$CFG_ROOT"; run_root="$RUN_ROOT"; evidence_root="$EVIDENCE_ROOT"; compile_root="$COMPILE_ROOT"; guard_receipt="$evidence_root/OPERATIONAL_GUARD_RECEIPT.json"; compile_guard_receipt="$evidence_root/COMPILE_OPERATIONAL_GUARD_RECEIPT.json"; finalization_guard_receipt="$evidence_root/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json"',
        "guard paths",
    )
    text = replace_once(
        text,
        'set +e; timeout --foreground --signal=TERM --kill-after=30s 2h "${compile_argv[@]}" > "$compile_log" 2>&1; compile_status=$?; set -e',
        'set +e; python3 "$package_root/package_tools/server_observer_runtime_supervision.py" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --mode compile --attempt-root "$run_root" --owned-root "$bootstrap_root" --cwd "$server_root" --disk-path "$server_root/install" --min-free-bytes 20000000000 --growth-limit-bytes 8000000000 --watch "compile_log=$compile_log=200000000" --file-size-limit-bytes 500000000 --timeout 7200 --interval 2 --grace 30 --receipt "$compile_guard_receipt" --log "$compile_log" -- "${compile_argv[@]}"; compile_status=$?; set -e',
        "guarded compile",
    )
    old_sim = 'DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/package_tools/server_observer_runtime_supervision.py" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --heartbeat-source "$run_root/c0/sim.log" --heartbeat-output "$evidence_root/supervisor_heartbeat.jsonl" --heartbeat-regex \'CODEX_OBSERVER_SIM_TIME_V1 sim_time=([0-9]+)\' --timescale 1ps --timeout 21600 --interval 30 --grace 30 --receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" -- "$simv" -l "$run_root/c0/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" +CODEX_CAUSAL_OBSERVER +CODEX_OBSERVER_ONLY_WIDE_CAUSAL "+CODEX_OBSERVER_CHUNK=$observer_chunk" "+CODEX_PACKAGE_ID=$package_id" "+CODEX_EXECUTION_ID=$return_tag" "+CODEX_ATTEMPT_ID=$attempt"'
    new_sim = 'DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/package_tools/server_observer_runtime_supervision.py" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --mode simulation --attempt-root "$run_root" --cwd "$server_root" --disk-path "$server_root/install" --min-free-bytes 20000000000 --growth-limit-bytes 800000000 --watch "observer=$observer_chunk=400000000" --watch "sim_log=$run_root/c0/sim.log=200000000" --file-size-limit-bytes 500000000 --timeout 3600 --interval 2 --grace 45 --receipt "$guard_receipt" -- python3 "$package_root/package_tools/server_observer_runtime_supervision_base.py" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --heartbeat-source "$run_root/c0/sim.log" --heartbeat-output "$evidence_root/supervisor_heartbeat.jsonl" --heartbeat-regex \'CODEX_OBSERVER_SIM_TIME_V1 sim_time=([0-9]+)\' --timescale 1ps --timeout 3660 --interval 30 --grace 30 --receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" -- "$simv" -l "$run_root/c0/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" +CODEX_CAUSAL_OBSERVER +CODEX_OBSERVER_ONLY_WIDE_CAUSAL "+CODEX_OBSERVER_CHUNK=$observer_chunk" "+CODEX_PACKAGE_ID=$package_id" "+CODEX_EXECUTION_ID=$return_tag" "+CODEX_ATTEMPT_ID=$attempt"'
    text = replace_once(text, old_sim, new_sim, "guarded simulation")
    text = replace_once(
        text,
        '[ "$run_status" -eq 124 ] && timed_out=true',
        '[ "$run_status" -eq 124 ] && timed_out=true\n[ "$run_status" -eq 122 ] && signal_status=TERM\n[ "$run_status" -eq 122 ] && grep -q \'"stop_reason": "WALL_TIMEOUT"\' "$guard_receipt" 2>/dev/null && timed_out=true',
        "guard exit mapping",
    )
    path.write_text(text, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def update_contracts() -> None:
    contract_path = TREE / "contracts/observer_only_wide_causal_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["family_target_epoch"] = "node0004-lc-branch-duplication-guarded-v1"
    contract["rule_ids"].append("USER-OBSERVER-OPERATIONAL-GUARD-NO-SILENT-TRUNCATION-001")
    contract["claim_boundary"] = "All non-clock causal-net transitions plus exact simulation-time/owner-cycle heartbeat; the redundant free-running owner clock is recorded at initial/end state rather than every edge. Operational stop preserves all completed rows and marks the return incomplete."
    write_json(contract_path, contract)
    guard = {
        "schema": "server-observer-operational-guard-contract-v1",
        "package_id": PACKAGE,
        "activation_epoch": "node0004-observer-disk-exhaustion-guard-v1",
        "trigger": "user reported more than 50GB under install/codex_runs and no return ZIP for v98b",
        "thresholds": {
            "observer_stop_bytes": 400000000,
            "observer_file_rlimit_bytes": 500000000,
            "simulation_log_stop_bytes": 200000000,
            "compile_log_stop_bytes": 200000000,
            "attempt_runtime_growth_stop_bytes": 800000000,
            "compile_attempt_growth_stop_bytes": 8000000000,
            "finalization_growth_stop_bytes": 2000000000,
            "minimum_disk_free_bytes": 20000000000,
            "simulation_wall_seconds": 3600,
        },
        "clock_transport": {
            "signal_id": "sig_clk",
            "per_edge_jsonl_removed": True,
            "initial_and_end_state_retained": True,
            "periodic_owner_cycle_heartbeat_retained": True,
            "exact_event_sim_time_retained": True,
            "causal_exclusion_reason": "A deterministic free-running owner clock edge is redundant with exact event time and periodic owner-cycle heartbeat; logging every half-cycle caused the unbounded volume and does not distinguish any tuple10 candidate.",
        },
        "stop_semantics": {
            "stop_entire_simulation": True,
            "truncate_existing_rows": False,
            "sample_nonclock_causal_events": False,
            "delete_evidence_for_size": False,
            "partial_return": True,
            "diagnostic_status_on_guard": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "term_wait_kill_reap": True,
            "one_shot": True,
        },
        "persistent_install_codex_runs": {
            "post_return_exact_attempt_bytes": 0,
            "maximum_transient_growth_over_initial_bytes": 10800000000,
            "cleanup_after_durable_return": True,
            "foreign_siblings_preserved": True,
        },
        "pass_before_server_run": True,
        "claim_boundary": "Local operational-safety contract; production guard behavior remains a dynamic proof boundary.",
    }
    write_json(TREE / "contracts/observer_operational_guard_contract.json", guard)
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    insert = [
        {"archive": "evidence/OPERATIONAL_GUARD_RECEIPT.json", "required": False, "source": "evidence/OPERATIONAL_GUARD_RECEIPT.json", "source_root": "attempt"},
        {"archive": "evidence/COMPILE_OPERATIONAL_GUARD_RECEIPT.json", "required": False, "source": "evidence/COMPILE_OPERATIONAL_GUARD_RECEIPT.json", "source_root": "attempt"},
        {"archive": "evidence/observer_operational_guard_contract.json", "required": True, "source": "contracts/observer_operational_guard_contract.json", "source_root": "package"},
    ]
    request["core_entries"].extend(insert)
    write_json(request_path, request)
    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = json.loads(allow_path.read_text(encoding="utf-8"))
    allow["required"].extend([
        f"{PACKAGE}_return/evidence/OPERATIONAL_GUARD_RECEIPT.json",
        f"{PACKAGE}_return/evidence/COMPILE_OPERATIONAL_GUARD_RECEIPT.json",
        f"{PACKAGE}_return/evidence/observer_operational_guard_contract.json",
    ])
    write_json(allow_path, allow)


def regenerate_source_bound_observer() -> None:
    generated = OUT / "source_bound_regenerated"
    command = [
        sys.executable,
        str(ROOT / "tools/generate_server_source_bound_observer.py"),
        "materialize",
        "--catalog", str(TREE / "diagnostics/source_bound_probe_catalog.json"),
        "--plan", str(TREE / "diagnostics/source_bound_probe_plan.json"),
        "--output-dir", str(generated),
        "--report", str(generated / "source_bound_observer_generation_report.json"),
        "--cheap-check-output", str(generated / "cheap_prebuild.json"),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"source-bound regeneration failed: {completed.stderr[-4096:]}")
    destinations = {
        "source_bound_causal_observer.svh": (
            "diagnostics/source_bound_causal_observer.svh",
            "tb_probe/source_bound_causal_observer.svh",
        ),
        "source_bound_causal_parser.py": (
            "diagnostics/source_bound_causal_parser.py",
            "package_tools/source_bound_causal_parser.py",
        ),
        "source_bound_observer_focus.sv": ("diagnostics/source_bound_observer_focus.sv",),
        "source_bound_probe_binding.json": ("diagnostics/source_bound_probe_binding.json",),
        "source_bound_observer_generation_report.json": ("diagnostics/source_bound_observer_generation_report.json",),
    }
    for name, relatives in destinations.items():
        for relative in relatives:
            shutil.copyfile(generated / name, TREE / relative)


def file_rows() -> list[dict[str, object]]:
    return [
        {"path": path.relative_to(TREE).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(item for item in TREE.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]


def deterministic_zip() -> None:
    temporary = ZIP.with_name(f".{ZIP.name}.tmp.{os.getpid()}")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(path.relative_to(TREE.parent).as_posix(), (2026, 8, 16, 0, 0, 0))
            mode = 0o755 if os.access(path, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("generated ZIP CRC failure")
    os.replace(temporary, ZIP)


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"fresh output already exists: {OUT}")
    TREE.mkdir(parents=True)
    import_source()
    original_supervisor = TREE / "package_tools/server_observer_runtime_supervision.py"
    original_supervisor.replace(TREE / "package_tools/server_observer_runtime_supervision_base.py")
    copies = {
        ROOT / "tools/server_observer_operational_guard.py": TREE / "package_tools/server_observer_runtime_supervision.py",
        ROOT / "tools/server_package_attempt_cleanup.py": TREE / "package_tools/server_package_attempt_cleanup.py",
        ROOT / "tools/filter_source_bound_log.py": TREE / "package_tools/filter_source_bound_log.py",
        ROOT / "tools/node0004_guarded_observer_event_parser.py": TREE / "package_tools/node0004_observerwide_event_parser.py",
        ROOT / "tools/node0004_v99_package_release_preflight.py": TREE / "package_tools/package_release_preflight.py",
    }
    for source, target in copies.items():
        shutil.copyfile(source, target)
        target.chmod(0o755)
    patch_observer()
    patch_runner()
    update_contracts()
    regenerate_source_bound_observer()

    runner = TREE / "PREPARE_AND_RUN.sh"
    runner_contract = TREE / "contracts/server_runner_return_resilience.json"
    value = json.loads(runner_contract.read_text(encoding="utf-8"))
    value["runner_sha256"] = sha(runner)
    for variable in ("cleanup_receipt", "guard_receipt", "compile_guard_receipt", "finalization_guard_receipt"):
        if variable not in value["package_owned_variables"]:
            value["package_owned_variables"].append(variable)
    write_json(runner_contract, value)
    post_contract = TREE / "contracts/server_post_sim_return_contract.json"
    value = json.loads(post_contract.read_text(encoding="utf-8"))
    value["request_sha256"] = sha(TREE / "contracts/server_post_sim_return_request.json")
    write_json(post_contract, value)

    manifest_path = TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "schema": "node0004-v99b-lcdup-guarded-package-manifest-v1",
        "package_id": PACKAGE,
        "install_name": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "diagnostic_mode": "OBSERVER_ONLY_WIDE_CAUSAL_GUARDED",
        "activation_epoch": "node0004-observer-disk-exhaustion-guard-v1",
        "observer_only_contract_sha256": sha(TREE / "contracts/observer_only_wide_causal_contract.json"),
        "source_package": OLD,
        "previous_version_progress": "v98b preserved the mapper-A/B-proven LC9-to-LC3 duplication, but its every-clock-edge unbounded JSONL observer could grow beyond 50GB and disk exhaustion prevented a return.",
        "current_purpose": "Retain the identical LC-duplication config and tuple10/natural-terminal/Formal-D target while bounding operational footprint, preserving all completed causal rows, publishing a fail-closed partial return, reaping the process tree, and cleaning the exact attempt after durable return.",
        "server_actions_performed": [],
    })
    manifest["files"] = []
    write_json(manifest_path, manifest)
    readme = f"""# {PACKAGE}\n\nPrevious progress: local mapper A/B proved the LC9-to-LC3 copied branch equivalent and negligible-cost. v98b then exposed an unbounded every-clock-edge JSONL writer and produced no return after server disk exhaustion.\n\nCurrent purpose: confirm tuple10, natural terminal and Formal-D with the identical config while enforcing 200MB compile/sim-log stops, a 400MB observer stop, 8GB compile-growth, 800MB simulation-growth and 2GB finalization-growth stops, a 20GB disk reserve, a 60-minute simulation wall limit, TERM/wait/KILL/reap, emergency partial return and post-return exact-attempt cleanup. Maximum transient package-owned growth under install/codex_runs is 10.8GB over the initial attempt; persistent exact-attempt bytes after a durable return are zero. All completed non-clock causal transitions are retained; the deterministic owner clock is represented by initial/end state and periodic exact sim-time heartbeat.\n\nRun only after separate authorization:\n\n    bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01\n\nNo waveform is enabled. Functional RTL, workload, numeric and golden inputs are frozen.\n"""
    (TREE / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    manifest["files"] = file_rows()
    write_json(manifest_path, manifest)
    deterministic_zip()
    write_json(OUT / "build_receipt.json", {
        "schema": "node0004-v99b-lcdup-guarded-build-v1",
        "package_id": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)},
        "source_zip": {"path": SOURCE.relative_to(ROOT).as_posix(), "bytes": SOURCE.stat().st_size, "sha256": sha(SOURCE)},
        "pass": True,
        "errors": [],
    })
    print(ZIP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
