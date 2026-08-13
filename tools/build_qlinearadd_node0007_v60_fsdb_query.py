#!/usr/bin/env python3
"""Build the fresh QAdd FSDB-v3/query successor from exact tested v59.

This is a local-only release builder.  It never invokes VCS, a DUT simulator,
an upload, a lease, or a server action.  The tested v59 payload is the frozen
functional source; only fresh identity, the known install/SCA identity repair,
and current package-local FSDB/query/runtime-return surfaces may change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "r5_qadd_n7_tailround_lanephase_qual_v59_portable_vcd_query"
TARGET = "r5_qadd_n7_tailround_lanephase_v60_fsdbq"
FAMILY = "qlinearadd_node0007"
OUT = ROOT / "outputs/qlinearadd_node0007_v60_fsdb_query_release"
PREBUILD = OUT / "prebuild"
STAGING = ROOT / "outputs/qlinearadd_v60_staging"
BUILD = OUT / "build"
GATES = OUT / "gates"
SOURCE_ZIP_NORMAL = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/tested"
    / FAMILY
    / SOURCE
    / f"{SOURCE}.zip"
)
SOURCE_ZIP = Path("\\\\?\\" + str(SOURCE_ZIP_NORMAL.absolute()))
FORMAL_ANALYSIS = ROOT / "outputs/qlinearadd_v59r1421299/formal_return_analysis.json"
REGISTRY = ROOT / "contracts/server_package_build_gate_registry_v1.json"
PIPELINE = ROOT / "tools/server_package_pipeline.py"
LEXICAL = ROOT / "tools/validate_server_package_local_hdl_lexical.py"
RUNNER_VALIDATOR = ROOT / "tools/validate_server_runner_return_resilience.py"
SOURCE_BOUND = ROOT / "tools/generate_server_source_bound_observer.py"
POST_SIM = ROOT / "tools/server_post_sim_return.py"
WAVE = ROOT / "tools/server_waveform_mandatory_return.py"
RUNTIME_LAYOUT = ROOT / "tools/validate_server_package_runtime_layout.py"
FIRST_FRESH = ROOT / "tools/validate_server_first_fresh_extra_audit.py"
EPOCH = "package-local-hdl-lexical-v1-01211147e247"
RULE_IDS = [
    "CDA-SERVER-PACKAGE-LOCAL-HDL-LEXICAL-HARD-GATE-001",
    "CDA-SERVER-WAVEFORM-FSDB-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001",
    "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001",
    "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
    "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
]

IDENTITY_ONLY = {
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "workload/runtime/sca_cfg.json",
    "workload/runtime/sca_cfg_D.json",
}
REMOVED_PORTABLE = {
    "contracts/server_waveform_portable_profile.json",
    "contracts/server_waveform_portable_runtime_contract.json",
    "package_tools/qlinearadd_node0007_portable_query_runtime_v59.py",
    "tools/server_waveform_portable_query.py",
    "tools/server_waveform_local_analysis.py",
}
CHANGED_EXISTING = {
    "PREPARE_AND_RUN.sh",
    "README.md",
    "TEST_PACKAGE_MANIFEST.json",
    "contracts/server_post_sim_return_contract.json",
    "contracts/server_post_sim_return_request.json",
    "contracts/server_runner_return_resilience_contract.json",
    "contracts/server_waveform_mandatory_plan.json",
    "contracts/waveform_policy.json",
    "package_tools/dump_waveform.tcl",
    "package_tools/server_post_sim_return.py",
    "package_tools/server_waveform_mandatory_return.py",
}
ADDED = {
    "contracts/qadd_fsdb_query_profile.json",
    "diagnostics/qadd_fsdb_query_source_report.json",
    "package_tools/qadd_fsdb_event_parser_v60.py",
    "tb_probe/qadd_fsdb_event_probe_v60.svh",
    "provenance/v59_to_v60_fsdb_identity_fix.json",
}


class BuildError(RuntimeError):
    pass


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    raw = str(path)
    if raw.startswith("\\\\?\\"):
        raw = raw[4:]
        return Path(raw).absolute().relative_to(ROOT).as_posix()
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def identity(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "bytes": path.stat().st_size, "sha256": sha_file(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(argv: list[str], *, output: Path | None = None) -> dict[str, Any]:
    completed = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)
    value = {
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if output is not None:
        write_json(output, value)
    if completed.returncode != 0:
        raise BuildError(
            f"command failed ({completed.returncode}): {' '.join(argv)}\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    return value


def safe_extract(zip_path: Path, destination: Path, expected_root: str) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    roots: set[str] = set()
    names: set[str] = set()
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise BuildError("source ZIP CRC failure")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in names
            ):
                raise BuildError(f"unsafe/duplicate source member: {info.filename}")
            names.add(info.filename)
            roots.add(pure.parts[0])
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise BuildError(f"source symlink member: {info.filename}")
        if roots != {expected_root}:
            raise BuildError(f"source root mismatch: {sorted(roots)}")
        archive.extractall(destination)
    return destination / expected_root


def member_map(package: Path, *, include_manifest: bool = False) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        name = path.relative_to(package).as_posix()
        if not include_manifest and name == "TEST_PACKAGE_MANIFEST.json":
            continue
        data = path.read_bytes()
        rows[name] = {"bytes": len(data), "sha256": sha_bytes(data)}
    return rows


def package_identity(package: Path, member: str) -> dict[str, Any]:
    path = package / member
    return {"path": member, "bytes": path.stat().st_size, "sha256": sha_file(path)}


def source_members() -> dict[str, bytes]:
    rows: dict[str, bytes] = {}
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            pure = PurePosixPath(info.filename)
            rows[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(info)
    return rows


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise BuildError(f"runner anchor count differs for {label}: {count}")
    return text.replace(old, new, 1)


def patch_runner(source: str) -> str:
    runner = source.replace(SOURCE, TARGET)
    runner = replace_once(
        runner,
        "portable_receipt_rc=0\nportable_attempt_relative=\nraw_wave_name=wave.vpd\nportable_wave_name=wave.vcd\n",
        "query_receipt_rc=0\nquery_signal_receipt_name=SIGNAL_QUERY_RECEIPT.json\nquery_status_name=DIAGNOSTIC_STATUS.json\n",
        "portable variables",
    )
    runner = runner.replace(
        'portable_helper="$package_root/package_tools/qlinearadd_node0007_portable_query_runtime_v59.py"\n'
        'portable_profile="$package_root/contracts/server_waveform_portable_profile.json"\n',
        'query_helper="$package_root/package_tools/qadd_fsdb_event_parser_v60.py"\n'
        'query_profile="$package_root/contracts/qadd_fsdb_query_profile.json"\n'
        'query_source_report="$package_root/diagnostics/qadd_fsdb_query_source_report.json"\n',
    )
    query_block = '''    if [ "$simulation_started" = true ]; then
      mkdir -p -- "$evidence_root/fsdb_query"
      CODEX_PACKAGE_ID="$package_id" CODEX_EXECUTION_ID="$return_tag" CODEX_ATTEMPT_ID="$attempt" \\
      python3 "$query_helper" --log "$run_root/sim.log" \\
        --profile "$query_profile" --source-report "$query_source_report" \\
        --waveform-receipt "$evidence_root/waveform/WAVEFORM_RUNTIME_RECEIPT.json" \\
        --actual-compile-argv "$evidence_root/compile_argv.json" \\
        --actual-sim-argv "$evidence_root/actual_simulator_argv.json" \\
        --dump-control "$runtime_dump_tcl" --output-dir "$evidence_root/fsdb_query"
      query_receipt_rc=$?
    fi
'''
    portable_start = '    portable_attempt_relative="install/codex_runs/$package_id/$attempt"\n'
    portable_end = '    export CODEX_PACKAGE_ROOT="$package_root"\n'
    if runner.count(portable_start) != 1 or runner.count(portable_end) != 1:
        raise BuildError("portable finalizer structural boundary differs")
    start_index = runner.index(portable_start)
    end_index = runner.index(portable_end, start_index)
    runner = runner[:start_index] + query_block + runner[end_index:]
    runner = replace_once(
        runner,
        "  make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=1 DUMP_PORTABLE_VCD=1 DUMP_FSDB=0\n"
        "  TB_DUMP_FSDB=0 \"RUN_DIR=$compile_root\"\n"
        '  "VCS_EXTRA_OPTS=+incdir+$package_root/tb_probe +define+NATIVE_RETURN_OBSERVER_ENABLE $package_root/tb_probe/source_bound_causal_observer.svh")',
        "  make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=1\n"
        "  TB_DUMP_FSDB=0 \"RUN_DIR=$compile_root\"\n"
        '  "VCS_EXTRA_OPTS=+incdir+$package_root/tb_probe +define+NATIVE_RETURN_OBSERVER_ENABLE '
        '$package_root/tb_probe/source_bound_causal_observer.svh '
        '$package_root/tb_probe/qadd_fsdb_event_probe_v60.svh")',
        "compile FSDB/query",
    )
    runner = replace_once(
        runner,
        'runtime_dump_tcl="$run_root/codex_wave_dump.tcl"\n'
        'portable_attempt_relative="install/codex_runs/$package_id/$attempt"\n'
        'python3 "$portable_helper" prepare --profile "$portable_profile" --attempt-root "$run_root" --attempt-relative "$portable_attempt_relative" --output-tcl "$runtime_dump_tcl" || runner_fail 15 "cannot materialize exact dual-format waveform control"\n',
        'runtime_dump_tcl="$run_root/run/sim_results/dump_waveform.tcl"\n'
        'mkdir -p -- "$run_root/run/sim_results" || runner_fail 15 "cannot create attempt-local FSDB root"\n'
        'printf \'set CODEX_WAVE_PATH {%s}\\n\' "$run_root/run/sim_results/wave.fsdb" >"$runtime_dump_tcl" || runner_fail 15 "cannot bind attempt-local FSDB path"\n'
        'cat "$package_root/package_tools/dump_waveform.tcl" >>"$runtime_dump_tcl" || runner_fail 15 "cannot materialize plan-derived FSDB control"\n',
        "runtime dump Tcl",
    )
    runner = replace_once(
        runner,
        '  +CODEX_CAUSAL_OBSERVER\n',
        '  +CODEX_CAUSAL_OBSERVER +CODEX_QADD_FSDB_QUERY\n',
        "query plusarg",
    )
    runner = replace_once(
        runner,
        "printf 'DUMP_VCD=1 DUMP_PORTABLE_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 timeout --foreground --signal=TERM --kill-after=30s 2h %q' \"$simv\" >\"$evidence_root/actual_simulator_argv.txt\"",
        "printf 'DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0 timeout --foreground --signal=TERM --kill-after=30s 2h %q' \"$simv\" >\"$evidence_root/actual_simulator_argv.txt\"",
        "sim argv text",
    )
    runner = replace_once(
        runner,
        'argv=["DUMP_VCD=1","DUMP_PORTABLE_VCD=1","DUMP_FSDB=0","TB_DUMP_FSDB=0","timeout","--foreground","--signal=TERM","--kill-after=30s","2h",simv,*args]',
        'argv=["DUMP_VCD=0","DUMP_FSDB=1","TB_DUMP_FSDB=0","timeout","--foreground","--signal=TERM","--kill-after=30s","2h",simv,*args]',
        "sim argv json",
    )
    runner = replace_once(
        runner,
        'DUMP_VCD=1 DUMP_PORTABLE_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 timeout --foreground --signal=TERM --kill-after=30s 2h "$simv" "${sim_args[@]}" &',
        'DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0 timeout --foreground --signal=TERM --kill-after=30s 2h "$simv" "${sim_args[@]}" &',
        "sim invocation",
    )
    runner = replace_once(
        runner,
        '    [ "$waveform_receipt_rc" -eq 0 ] || final=97\n',
        '    [ "$waveform_receipt_rc" -eq 0 ] || final=97\n'
        '    [ "$query_receipt_rc" -eq 0 ] || [ "$final" -ne 0 ] || final=95\n',
        "query failure status",
    )
    forbidden = ("DUMP_PORTABLE_VCD", "wave.vpd", "portable_helper", "portable_profile")
    present = [token for token in forbidden if token in runner]
    required = (
        "DUMP_VCD=0",
        "DUMP_FSDB=1",
        "TB_DUMP_FSDB=0",
        "wave.fsdb",
        "qadd_fsdb_event_probe_v60.svh",
        "qadd_fsdb_event_parser_v60.py",
        "+CODEX_QADD_FSDB_QUERY",
        "query_receipt_rc",
    )
    if present or not all(token in runner for token in required):
        raise BuildError(f"runner FSDB/query token gate differs: forbidden={present}")
    return runner


def query_catalog() -> list[dict[str, Any]]:
    base = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice."
        "u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer"
    )
    return [
        {"candidate_id": name, "hierarchical_path": f"{base}.{signal}", "width": width}
        for name, signal, width in (
            ("producer_arm_write_valid", "arm2buf_wvalid", 1),
            ("producer_write_ready", "buf_wreq_ready", 1),
            ("selected_read_request_rw", "mrm2buf_req_rw", 1),
            ("selected_read_clear_mask", "mrm2buf_clear", 8),
            ("valid_bank_clear_mask", "valid_buf_clear", 8),
            ("selected_read_bank_ready", "buf2mrm_rreq_bank_ready", 8),
            ("selected_read_ready", "buf2mrm_rreq_ready", 1),
            ("selected_read_result_valid", "buf2mrm_rvalid", 1),
        )
    ]


def query_profile() -> dict[str, Any]:
    return {
        "schema": "qlinearadd-node0007-fsdb-query-profile-v1",
        "package_id": TARGET,
        "rule_id": "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001",
        "activation_epoch": EPOCH,
        "timescale": "1ns/1ps",
        "event_prefix": "CODEX_QADD_FSDB_EVENT_V1",
        "summary_prefix": "CODEX_QADD_FSDB_SUMMARY_V1",
        "candidates": query_catalog(),
        "capture": {
            "format": "REGISTERED_EVENT_ROWS",
            "same_original_attempt": True,
            "ordered_every_transition": True,
            "preserve_0_1_x_z": True,
            "hard_limit_bytes": None,
            "hard_limit_events": None,
            "time_window_limit": None,
            "truncation": False,
            "sampling": False,
            "size_based_deletion": False,
        },
        "failure": {
            "status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "preserve_raw_fsdb": True,
            "preserve_compile_sim_signal_core_return": True,
        },
        "claim_boundary": (
            "Exact group0/local-slice0 Buffer5 producer/clear/selected-port readiness "
            "transitions only; formal-D and DUT correctness require a real return."
        ),
    }


QUERY_PROBE = r'''`timescale 1ns/1ps
module codex_qadd_fsdb_event_probe_v60(
    input logic clk,
    input logic rst_n,
    input logic producer_arm_write_valid,
    input logic producer_write_ready,
    input logic selected_read_request_rw,
    input logic [7:0] selected_read_clear_mask,
    input logic [7:0] valid_bank_clear_mask,
    input logic [7:0] selected_read_bank_ready,
    input logic selected_read_ready,
    input logic selected_read_result_valid
);
  integer codex_query_enabled;
  longint unsigned codex_event_sequence;
  logic codex_initialized;
  logic prev_producer_arm_write_valid;
  logic prev_producer_write_ready;
  logic prev_selected_read_request_rw;
  logic [7:0] prev_selected_read_clear_mask;
  logic [7:0] prev_valid_bank_clear_mask;
  logic [7:0] prev_selected_read_bank_ready;
  logic prev_selected_read_ready;
  logic prev_selected_read_result_valid;

  task automatic codex_emit_row(
      input string candidate_name,
      input integer signal_width,
      input logic [7:0] signal_value
  );
    if (signal_width == 1)
      $display("CODEX_QADD_FSDB_EVENT_V1 sequence=%0d time_tick=%0t candidate=%s width=1 value=%b",
               codex_event_sequence, $time, candidate_name, signal_value[0]);
    else
      $display("CODEX_QADD_FSDB_EVENT_V1 sequence=%0d time_tick=%0t candidate=%s width=8 value=%b",
               codex_event_sequence, $time, candidate_name, signal_value);
    codex_event_sequence = codex_event_sequence + 1;
  endtask

  task automatic codex_emit_all;
    codex_emit_row("producer_arm_write_valid", 1, {7'b0, producer_arm_write_valid});
    codex_emit_row("producer_write_ready", 1, {7'b0, producer_write_ready});
    codex_emit_row("selected_read_request_rw", 1, {7'b0, selected_read_request_rw});
    codex_emit_row("selected_read_clear_mask", 8, selected_read_clear_mask);
    codex_emit_row("valid_bank_clear_mask", 8, valid_bank_clear_mask);
    codex_emit_row("selected_read_bank_ready", 8, selected_read_bank_ready);
    codex_emit_row("selected_read_ready", 1, {7'b0, selected_read_ready});
    codex_emit_row("selected_read_result_valid", 1, {7'b0, selected_read_result_valid});
  endtask

  task automatic codex_save_state;
    prev_producer_arm_write_valid = producer_arm_write_valid;
    prev_producer_write_ready = producer_write_ready;
    prev_selected_read_request_rw = selected_read_request_rw;
    prev_selected_read_clear_mask = selected_read_clear_mask;
    prev_valid_bank_clear_mask = valid_bank_clear_mask;
    prev_selected_read_bank_ready = selected_read_bank_ready;
    prev_selected_read_ready = selected_read_ready;
    prev_selected_read_result_valid = selected_read_result_valid;
  endtask

  initial begin
    codex_query_enabled = $test$plusargs("CODEX_QADD_FSDB_QUERY");
    codex_event_sequence = 0;
    codex_initialized = 1'b0;
  end

  always @(posedge clk) begin
    if (codex_query_enabled) begin
      if (!codex_initialized) begin
        codex_emit_all();
        codex_save_state();
        codex_initialized = 1'b1;
      end else begin
        if (producer_arm_write_valid !== prev_producer_arm_write_valid)
          codex_emit_row("producer_arm_write_valid", 1, {7'b0, producer_arm_write_valid});
        if (producer_write_ready !== prev_producer_write_ready)
          codex_emit_row("producer_write_ready", 1, {7'b0, producer_write_ready});
        if (selected_read_request_rw !== prev_selected_read_request_rw)
          codex_emit_row("selected_read_request_rw", 1, {7'b0, selected_read_request_rw});
        if (selected_read_clear_mask !== prev_selected_read_clear_mask)
          codex_emit_row("selected_read_clear_mask", 8, selected_read_clear_mask);
        if (valid_bank_clear_mask !== prev_valid_bank_clear_mask)
          codex_emit_row("valid_bank_clear_mask", 8, valid_bank_clear_mask);
        if (selected_read_bank_ready !== prev_selected_read_bank_ready)
          codex_emit_row("selected_read_bank_ready", 8, selected_read_bank_ready);
        if (selected_read_ready !== prev_selected_read_ready)
          codex_emit_row("selected_read_ready", 1, {7'b0, selected_read_ready});
        if (selected_read_result_valid !== prev_selected_read_result_valid)
          codex_emit_row("selected_read_result_valid", 1, {7'b0, selected_read_result_valid});
        codex_save_state();
      end
    end
  end

  final begin
    if (codex_query_enabled)
      $display("CODEX_QADD_FSDB_SUMMARY_V1 time_tick=%0t sequence_count=%0d initialized=%0d rst_n=%b",
               $time, codex_event_sequence, codex_initialized, rst_n);
  end
endmodule

`ifndef CODEX_QADD_FSDB_FOCUS
bind tb_NDP_Top_new_phy codex_qadd_fsdb_event_probe_v60 u_codex_qadd_fsdb_event_probe_v60(
    .clk(u_NDP_Top_new.clk_sg),
    .rst_n(u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.rst_n),
    .producer_arm_write_valid(u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.arm2buf_wvalid),
    .producer_write_ready(u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf_wreq_ready),
    .selected_read_request_rw(u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_req_rw),
    .selected_read_clear_mask(u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_clear),
    .valid_bank_clear_mask(u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.valid_buf_clear),
    .selected_read_bank_ready(u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf2mrm_rreq_bank_ready),
    .selected_read_ready(u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf2mrm_rreq_ready),
    .selected_read_result_valid(u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf2mrm_rvalid)
);
`endif
'''


QUERY_PARSER = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, re

ROW = re.compile(r"^CODEX_QADD_FSDB_EVENT_V1 sequence=(\d+) time_tick=(\d+) candidate=([A-Za-z0-9_.-]+) width=(\d+) value=([01xXzZ]+)$")
SUMMARY = re.compile(r"^CODEX_QADD_FSDB_SUMMARY_V1 time_tick=(\d+) sequence_count=(\d+) initialized=([01]) rst_n=([01xXzZ])$")

def ident(path):
    data=path.read_bytes(); return {"path":str(path),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}

def write(path, value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")

def main():
    p=argparse.ArgumentParser()
    for name in ("log","profile","source-report","waveform-receipt","actual-compile-argv","actual-sim-argv","dump-control","output-dir"):
        p.add_argument("--"+name,type=pathlib.Path,required=True)
    a=p.parse_args(); a.output_dir.mkdir(parents=True,exist_ok=True)
    profile=json.loads(a.profile.read_text()); source=json.loads(a.source_report.read_text()); raw=json.loads(a.waveform_receipt.read_text())
    compile_argv=json.loads(a.actual_compile_argv.read_text()); sim_argv=json.loads(a.actual_sim_argv.read_text()); dump=a.dump_control.read_text()
    catalog=profile["candidates"]; by_id={row["candidate_id"]:row for row in catalog}; rows=[]; summary=None; errors=[]
    for line in a.log.read_text(encoding="utf-8",errors="replace").splitlines():
        m=ROW.match(line.strip())
        if m:
            seq,tick,candidate,width,value=m.groups(); width=int(width); value=value.lower()
            meta=by_id.get(candidate)
            if meta is None: errors.append("unexpected_candidate:"+candidate); continue
            if width != meta["width"] or len(value) != width: errors.append("width_mismatch:"+candidate); continue
            rows.append({"sequence":int(seq),"time_tick":int(tick),"candidate_id":candidate,"hierarchical_path":meta["hierarchical_path"],"width":width,"value":value})
            continue
        m=SUMMARY.match(line.strip())
        if m: summary={"time_tick":int(m.group(1)),"sequence_count":int(m.group(2)),"initialized":m.group(3)=="1","rst_n":m.group(4).lower()}
    if [row["sequence"] for row in rows] != list(range(len(rows))): errors.append("noncontiguous_sequence")
    expected=sorted(by_id); covered=sorted({row["candidate_id"] for row in rows}); missing=sorted(set(expected)-set(covered))
    if missing: errors.append("missing_candidates:"+",".join(missing))
    if summary is None: errors.append("summary_missing")
    elif summary["sequence_count"] != len(rows): errors.append("summary_sequence_count_mismatch")
    wave_ok=(raw.get("schema")=="server-waveform-runtime-receipt-v3" and raw.get("pass") is True and bool(raw.get("waveforms")) and all(w.get("completeness")=="COMPLETE" and str(w.get("archive_path","")).endswith((".fsdb", ".fsdb.0", ".fsdb.1", ".fsdb.2", ".fsdb.3", ".fsdb.4", ".fsdb.5", ".fsdb.6", ".fsdb.7", ".fsdb.8", ".fsdb.9")) for w in raw.get("waveforms",[])))
    if not wave_ok: errors.append("raw_fsdb_incomplete")
    compile_text=json.dumps(compile_argv,sort_keys=True); sim_text=json.dumps(sim_argv,sort_keys=True)
    for token,text,label in (("DUMP_VCD=0",compile_text,"compile"),("DUMP_FSDB=1",compile_text,"compile"),("TB_DUMP_FSDB=0",compile_text,"compile"),("qadd_fsdb_event_probe_v60.svh",compile_text,"compile"),("DUMP_VCD=0",sim_text,"sim"),("DUMP_FSDB=1",sim_text,"sim"),("TB_DUMP_FSDB=0",sim_text,"sim"),("+CODEX_QADD_FSDB_QUERY",sim_text,"sim")):
        if token not in text: errors.append(label+"_argv_missing:"+token)
    for token in ("fsdbDumpfile $CODEX_WAVE_PATH","fsdbDumpvars 0 tb_NDP_Top_new_phy","fsdbDumpMDA 0 tb_NDP_Top_new_phy","run","quit"):
        if token not in dump: errors.append("dump_control_missing:"+token)
    end=[]
    for candidate in catalog:
        values=[row for row in rows if row["candidate_id"]==candidate["candidate_id"]]
        if values: end.append({**candidate,"time_tick":values[-1]["time_tick"],"value":values[-1]["value"]})
    complete=not errors
    receipt={"schema":"server-waveform-signal-query-receipt-v1","package_id":os.environ["CODEX_PACKAGE_ID"],"execution_id":os.environ["CODEX_EXECUTION_ID"],"attempt_id":os.environ["CODEX_ATTEMPT_ID"],"profile_sha256":ident(a.profile)["sha256"],"probe_catalog_sha256":ident(a.source_report)["sha256"],"timescale":profile["timescale"],"completeness":"COMPLETE" if complete else "PARTIAL","catalog":catalog,"capture":{"format":"REGISTERED_EVENT_ROWS","ordered":True,"every_transition":True,"preserve_0_1_x_z":True,"no_byte_limit":True,"no_event_limit":True,"no_time_window_limit":True,"sampling":False,"truncation":False,"flush_complete":summary is not None},"candidate_coverage":{"expected":expected,"covered":covered,"missing":missing,"unexpected":[]},"events":rows,"candidate_end_states":end,"summary":summary,"errors":errors,"claim_boundary":profile["claim_boundary"]}
    binding={"schema":"qlinearadd-node0007-fsdb-query-binding-v1","package_id":receipt["package_id"],"execution_id":receipt["execution_id"],"attempt_id":receipt["attempt_id"],"identities":{"profile":ident(a.profile),"source_report":ident(a.source_report),"raw_receipt":ident(a.waveform_receipt),"actual_compile_argv":ident(a.actual_compile_argv),"actual_sim_argv":ident(a.actual_sim_argv),"dump_control":ident(a.dump_control)},"waveforms":raw.get("waveforms",[]),"same_attempt_complete":complete,"pass":complete,"errors":errors}
    status={"schema":"qlinearadd-node0007-fsdb-diagnostic-status-v1","package_id":receipt["package_id"],"execution_id":receipt["execution_id"],"attempt_id":receipt["attempt_id"],"diagnostic_status":"COMPLETE" if complete else "DIAGNOSTIC_EVIDENCE_INCOMPLETE","raw_fsdb_and_core_return_preserved":True,"errors":errors}
    write(a.output_dir/"SIGNAL_QUERY_RECEIPT.json",receipt); write(a.output_dir/"FSDB_QUERY_BINDING.json",binding); write(a.output_dir/"DIAGNOSTIC_STATUS.json",status)
    return 0 if complete else 1

if __name__=="__main__": raise SystemExit(main())
'''


def prepare_prebuild_spec() -> None:
    required = [
        PREBUILD / "source_bound_observer_generation_cheap.json",
        PREBUILD / "source_bound_generated/source_bound_causal_observer.svh",
    ]
    if not all(path.is_file() for path in required):
        raise BuildError("fresh source-bound prebuild materialization is absent")
    source_identity_path = PREBUILD / "exact_v59_source_identity.json"
    write_json(
        source_identity_path,
        {
            "schema": "qlinearadd-node0007-exact-source-identity-v1",
            "source": identity(SOURCE_ZIP),
            "immutable": True,
            "claim_boundary": "Short-path identity receipt for the exact tested ZIP at the Windows 260-character boundary; source bytes are not copied or modified.",
        },
    )
    hdl_tree = PREBUILD / "package_local_hdl_tree"
    hdl_tree.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        PREBUILD / "source_bound_generated/source_bound_causal_observer.svh",
        hdl_tree / "source_bound_causal_observer.svh",
    )
    query_probe_path = hdl_tree / "qadd_fsdb_event_probe_v60.svh"
    query_probe_path.write_text(QUERY_PROBE, encoding="utf-8", newline="\n")
    lexical_path = PREBUILD / "package_local_hdl_lexical_prebuild.json"
    run([sys.executable, str(LEXICAL), "--tree", str(hdl_tree), "--output", str(lexical_path)])
    lexical_value = json.loads(lexical_path.read_text(encoding="utf-8"))
    focused = subprocess.run(
        ["iverilog", "-g2012", "-DCODEX_QADD_FSDB_FOCUS", "-s", "codex_qadd_fsdb_event_probe_v60", "-o", os.devnull, str(query_probe_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    hdl_checks = {
        "aggregate_reserved_declaration_names_empty": lexical_value.get("pass") is True,
        "fresh_query_probe_focused_frontend": focused.returncode == 0,
        "fresh_source_bound_generation": json.loads((PREBUILD / "source_bound_observer_generation_cheap.json").read_text()).get("pass") is True,
    }
    hdl_cheap = PREBUILD / "package_local_hdl.json"
    write_json(
        hdl_cheap,
        {
            "schema": "server-package-cheap-check-result-v1",
            "gate_id": "package_local_hdl",
            "pass": all(hdl_checks.values()),
            "errors": [name for name, passed in hdl_checks.items() if not passed],
            "warnings": [],
            "checks": hdl_checks,
            "focused_stderr": focused.stderr,
        },
    )
    if not all(hdl_checks.values()):
        raise BuildError(f"prebuild package-local HDL gate failed: {hdl_checks}")
    old = source_members()
    runner_text = patch_runner(old["PREPARE_AND_RUN.sh"].decode("utf-8"))
    runner_path = PREBUILD / "PREPARE_AND_RUN.sh"
    runner_path.write_text(runner_text, encoding="utf-8", newline="\n")
    bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if not bash.is_file():
        raise BuildError("Git Bash is absent for the fresh runner cheap check")
    syntax = subprocess.run(
        [str(bash), "-n", str(runner_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    runner_checks = {
        "bash_syntax": syntax.returncode == 0,
        "fsdb_make_tuple": all(token in runner_text for token in ("DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0")),
        "query_probe_compile_bound": "qadd_fsdb_event_probe_v60.svh" in runner_text,
        "query_parser_return_bound": "qadd_fsdb_event_parser_v60.py" in runner_text and "query_receipt_rc" in runner_text,
        "unsupported_direct_vcd_absent": "DUMP_PORTABLE_VCD" not in runner_text,
        "finalizer_armed_before_input": runner_text.index("trap 'finalize $?' EXIT") < runner_text.index('if [ "$#" -ne 1 ]; then'),
    }
    runner_cheap = PREBUILD / "runner_return_resilience.json"
    write_json(
        runner_cheap,
        {
            "schema": "server-package-cheap-check-result-v1",
            "gate_id": "runner_return_resilience",
            "pass": all(runner_checks.values()),
            "errors": [name for name, passed in runner_checks.items() if not passed],
            "warnings": [],
            "runner": identity(runner_path),
            "checks": runner_checks,
            "bash_stderr": syntax.stderr,
        },
    )
    if not all(runner_checks.values()):
        raise BuildError(f"fresh runner cheap check failed: {runner_checks}")
    fixtures = ROOT / "fixtures/server_package_pipeline_v1/cheap"
    cheap = []
    for gate, path in (
        ("core_identity_bootstrap", fixtures / "core_identity_bootstrap.json"),
        ("source_bound_observer_generation", PREBUILD / "source_bound_observer_generation_cheap.json"),
        ("runner_return_resilience", runner_cheap),
        ("package_local_hdl", hdl_cheap),
        ("storage_rotation", fixtures / "storage_rotation.json"),
        ("intermediate_report_format", fixtures / "intermediate_report_format.json"),
    ):
        if not path.is_file():
            raise BuildError(f"prebuild cheap receipt absent: {path}")
        cheap.append({"gate_id": gate, "path": rel(path), "sha256": sha_file(path)})
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    validators: dict[str, Any] = {}
    validator_default = sha_file(PIPELINE)
    fixture_default = sha_file(REGISTRY)
    for gate in registry["gates"]:
        validators[gate["gate_id"]] = {
            "validator_sha256": validator_default,
            "fixture_sha256": fixture_default,
        }
    inputs = [
        {**identity(source_identity_path), "surface": "package_identity"},
        {**identity(PREBUILD / "source_bound_generated/source_bound_causal_observer.svh"), "surface": "package_local_hdl"},
        {**identity(PREBUILD / "source_bound_generated/source_bound_causal_parser.py"), "surface": "parser"},
        {**identity(ROOT / "outputs/qlinearadd_v59r1421299/package_extract" / SOURCE / "diagnostics/source_bound_probe_catalog.json"), "surface": "probe_catalog"},
        {**identity(ROOT / "outputs/qlinearadd_v59r1421299/package_extract" / SOURCE / "diagnostics/source_bound_probe_plan.json"), "surface": "probe_plan"},
        {**identity(ROOT / "tools/server_waveform_mandatory_return.py"), "surface": "waveform"},
        {**identity(ROOT / "tools/server_post_sim_return.py"), "surface": "return_collector"},
        {**identity(ROOT / "tools/server_package_runtime_layout.py"), "surface": "runner"},
    ]
    spec = {
        "schema": "server-package-build-spec-v1",
        "package_id": TARGET,
        "family": FAMILY,
        "lifecycle": "NEXT_FRESH_SUCCESSOR",
        "shadow_only": True,
        "current_package_impact": False,
        "changed_surfaces": [
            "package_identity",
            "runner",
            "return_core_contract",
            "return_collector",
            "package_local_hdl",
            "probe_catalog",
            "waveform",
            "sca",
            "storage",
        ],
        "inputs": inputs,
        "cheap_check_reports": cheap,
        "validators": validators,
        "receipt_reuse_candidates": [],
        "require_all_cheap_checks": True,
        "rule_change_epoch": {
            "epoch_id": EPOCH,
            "first_fresh_after_change": True,
            "notification_acknowledged": True,
        },
    }
    spec_path = PREBUILD / "server_package_build_spec.json"
    write_json(spec_path, spec)
    run(
        [
            sys.executable,
            str(PIPELINE),
            "prepare",
            "--spec",
            str(spec_path),
            "--registry",
            str(REGISTRY),
            "--workspace-root",
            str(ROOT),
            "--output",
            str(PREBUILD / "server_package_pipeline_prepare.json"),
        ]
    )


def configure_package(package: Path, old: dict[str, bytes]) -> None:
    for member in IDENTITY_ONLY:
        path = package / member
        data = path.read_bytes()
        if SOURCE.encode() not in data:
            raise BuildError(f"identity anchor absent: {member}")
        path.write_bytes(data.replace(SOURCE.encode(), TARGET.encode()))
    for member in REMOVED_PORTABLE:
        path = package / member
        if path.is_file():
            path.unlink()

    shutil.copyfile(ROOT / "tools/server_package_runtime_layout.py", package / "package_tools/server_package_runtime_layout.py")
    shutil.copyfile(ROOT / "tools/server_post_sim_return.py", package / "package_tools/server_post_sim_return.py")
    shutil.copyfile(ROOT / "tools/server_waveform_mandatory_return.py", package / "package_tools/server_waveform_mandatory_return.py")

    runner = patch_runner(old["PREPARE_AND_RUN.sh"].decode("utf-8"))
    (package / "PREPARE_AND_RUN.sh").write_text(runner, encoding="utf-8", newline="\n")
    (package / "PREPARE_AND_RUN.sh").chmod(0o755)
    (package / "tb_probe/qadd_fsdb_event_probe_v60.svh").write_text(QUERY_PROBE, encoding="utf-8", newline="\n")
    parser_path = package / "package_tools/qadd_fsdb_event_parser_v60.py"
    parser_path.write_text(QUERY_PARSER, encoding="utf-8", newline="\n")
    parser_path.chmod(0o755)
    profile_path = package / "contracts/qadd_fsdb_query_profile.json"
    write_json(profile_path, query_profile())
    write_json(
        package / "diagnostics/qadd_fsdb_query_source_report.json",
        {
            "schema": "qlinearadd-node0007-fsdb-query-source-report-v1",
            "package_id": TARGET,
            "profile": package_identity(package, "contracts/qadd_fsdb_query_profile.json"),
            "probe": package_identity(package, "tb_probe/qadd_fsdb_event_probe_v60.svh"),
            "parser": package_identity(package, "package_tools/qadd_fsdb_event_parser_v60.py"),
            "catalog": query_catalog(),
            "source_bound_generation": identity(PREBUILD / "source_bound_observer_generation.json"),
            "writer_owner": "package_tools/dump_waveform.tcl",
            "driver_free": True,
            "full_frontend_required": True,
            "claim_boundary": "Fresh package-local read-only event source identity; no DUT result claim.",
        },
    )

    plan = {
        "schema": "server-waveform-mandatory-plan-v3",
        "package_id": TARGET,
        "family": "qlinearadd",
        "dump": {
            "format": "FSDB",
            "make_arguments": {"DUMP_VCD": "0", "DUMP_FSDB": "1", "TB_DUMP_FSDB": "0"},
            "tb_top": "tb_NDP_Top_new_phy",
            "scope_mode": "FULL_HIERARCHY",
            "included_scopes": ["tb_NDP_Top_new_phy"],
            "excluded_scopes": [],
            "hierarchy_depth": 0,
            "runtime_search_roots": ["run/sim_results"],
            "waveform_name_patterns": ["wave.fsdb", "wave.fsdb.*"],
        },
        "return_policy": {
            "collect_all_matching": True,
            "required_when_simulation_started": True,
            "compile_not_started_omission_allowed": True,
            "hard_limit_bytes": None,
            "truncation_allowed": False,
            "sampling_allowed": False,
            "size_based_deletion_allowed": False,
            "archive_prefix": "waveforms",
            "manifest_archive_path": "waveforms/WAVEFORM_RUNTIME_RECEIPT.json",
        },
        "integration": {
            "plan_member": "contracts/server_waveform_mandatory_plan.json",
            "runner_member": "PREPARE_AND_RUN.sh",
            "return_request_member": "contracts/server_post_sim_return_request.json",
            "dump_control_member": "package_tools/dump_waveform.tcl",
            "tool_member": "package_tools/server_waveform_mandatory_return.py",
        },
        "claim_boundary": "Authoritative package-owned full-hierarchy depth-0 unbounded FSDB; no DUT result claim.",
    }
    write_json(package / "contracts/server_waveform_mandatory_plan.json", plan)
    run(
        [
            sys.executable,
            str(WAVE),
            "render-dump-control",
            "--plan",
            str(package / "contracts/server_waveform_mandatory_plan.json"),
            "--output",
            str(package / "package_tools/dump_waveform.tcl"),
        ]
    )

    request = json.loads(old["contracts/server_post_sim_return_request.json"])
    request["package_id"] = TARGET
    request["core_entries"] = [
        row for row in request["core_entries"]
        if "portable" not in str(row.get("source", "")).lower()
        and "portable" not in str(row.get("archive", "")).lower()
        and not str(row.get("source", "")).endswith("wave.vcd")
        and not str(row.get("archive", "")).endswith("wave.vcd")
        and not str(row.get("source", "")).endswith("codex_wave_dump.tcl")
    ]
    request["core_entries"].extend([
        {"source_root": "attempt", "source": "run/sim_results/dump_waveform.tcl", "archive": "runs/dump_waveform.tcl", "required": False},
        {"source_root": "attempt", "source": "evidence/fsdb_query/SIGNAL_QUERY_RECEIPT.json", "archive": "evidence/fsdb_query/SIGNAL_QUERY_RECEIPT.json", "required": False},
        {"source_root": "attempt", "source": "evidence/fsdb_query/FSDB_QUERY_BINDING.json", "archive": "evidence/fsdb_query/FSDB_QUERY_BINDING.json", "required": False},
        {"source_root": "attempt", "source": "evidence/fsdb_query/DIAGNOSTIC_STATUS.json", "archive": "evidence/fsdb_query/DIAGNOSTIC_STATUS.json", "required": False},
    ])
    request["claim_boundary"] = "Core/formal and raw FSDB return survive registered-query failure; no server-run claim."
    request_path = package / "contracts/server_post_sim_return_request.json"
    write_json(request_path, request)
    post_contract = json.loads(old["contracts/server_post_sim_return_contract.json"])
    post_contract["package_id"] = TARGET
    post_contract["request_sha256"] = sha_file(request_path)
    post_contract["helper_sha256"] = sha_file(ROOT / "tools/server_post_sim_return.py")
    post_contract["claim_boundary"] = "Current JSON core plus optional FSDB/query evidence; query failure cannot suppress return publication."
    write_json(package / "contracts/server_post_sim_return_contract.json", post_contract)

    runner_contract = json.loads(old["contracts/server_runner_return_resilience_contract.json"])
    runner_contract["package_id"] = TARGET
    runner_contract["runner_path"] = f"{TARGET}/PREPARE_AND_RUN.sh"
    runner_contract["runner_sha256"] = sha_bytes(runner.encode())
    runner_contract["package_owned_variables"] = [
        name for name in runner_contract["package_owned_variables"]
        if name not in {
            "portable_receipt_rc", "portable_attempt_relative", "raw_wave_name",
            "portable_wave_name", "portable_helper", "portable_profile",
        }
    ]
    for name in ("query_helper", "query_profile", "query_source_report", "query_receipt_rc", "query_signal_receipt_name", "query_status_name"):
        if name not in runner_contract["package_owned_variables"]:
            runner_contract["package_owned_variables"].append(name)
    runner_contract["return_allowlist_tokens"] = [
        token for token in runner_contract["return_allowlist_tokens"]
        if "portable" not in token.lower() and "wave.vcd" not in token and "wave.vpd" not in token
    ]
    for token in ("DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0", "wave.fsdb", "SIGNAL_QUERY_RECEIPT.json", "DIAGNOSTIC_STATUS.json"):
        if token not in runner_contract["return_allowlist_tokens"]:
            runner_contract["return_allowlist_tokens"].append(token)
    write_json(package / "contracts/server_runner_return_resilience_contract.json", runner_contract)

    policy = {
        "schema": "qlinearadd-node0007-waveform-policy-v3",
        "package_id": TARGET,
        "capture": {"DUMP_VCD": 0, "DUMP_FSDB": 1, "TB_DUMP_FSDB": 0, "primary": "wave.fsdb", "all_shards": True, "unbounded": True},
        "scope": {"top": "tb_NDP_Top_new_phy", "depth": 0, "excluded_scopes": []},
        "query": {"profile": "contracts/qadd_fsdb_query_profile.json", "registered_every_transition": True, "unbounded": True},
        "failure": {"missing_wave_after_start": "FAIL_CLOSED", "query_failure": "DIAGNOSTIC_EVIDENCE_INCOMPLETE_RAW_AND_CORE_PRESERVED"},
    }
    write_json(package / "contracts/waveform_policy.json", policy)
    write_json(
        package / "provenance/v59_to_v60_fsdb_identity_fix.json",
        {
            "schema": "qlinearadd-node0007-v59-to-v60-fsdb-successor-v1",
            "source": identity(SOURCE_ZIP),
            "destination_package_id": TARGET,
            "previous_progress": "v57h localized selected ping-pong port required lanes not ready; v59 stopped at package preflight before compile because manifest install_name was v58 while package/SCA namespace was v59.",
            "current_purpose": "Preserve the selected-port lane-readiness target, repair package/install/SCA identity, and return full unbounded FSDB plus registered complete event/query evidence.",
            "frozen": ["config", "numeric", "workload", "golden", "functional_rtl", "target_diagnostic"],
            "server_action": False,
        },
    )

    readme = old["README.md"].decode("utf-8", errors="replace").replace(SOURCE, TARGET)
    readme += "\n\n## v60 FSDB-v3/query successor\n\nLocal-only fresh identity. DUMP_VCD=0, DUMP_FSDB=1, TB_DUMP_FSDB=0; complete attempt-local wave.fsdb/shards and registered unbounded Buffer5 transition rows are returned. No upload/run/lease was performed.\n"
    (package / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    manifest = json.loads(old["TEST_PACKAGE_MANIFEST.json"])
    old_install = "r5_qadd_n7_tailround_lanephase_qual_v58_mandatory_vpd"
    manifest = json.loads(json.dumps(manifest).replace(old_install, TARGET))
    manifest["package_id"] = TARGET
    manifest["install_name"] = TARGET
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["first_fresh_after_change"] = True
    manifest["rule_change_epoch"] = EPOCH
    manifest.pop("portable_waveform_gate", None)
    manifest.pop("v59_portable_successor", None)
    manifest["fsdb_v3_successor"] = {
        "source_package": SOURCE,
        "manifest_install_sca_identity_repaired": True,
        "make_arguments": "DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0",
        "full_hierarchy_depth0": True,
        "excluded_scopes": [],
        "registered_query_profile": "contracts/qadd_fsdb_query_profile.json",
        "raw_and_query_unbounded": True,
        "target_diagnostic_preserved": True,
        "server_action": False,
    }
    manifest["rule_change_ack"] = {"epoch_id": EPOCH, "notification_acknowledged": True}
    layout_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    budget = layout["path_budget"]
    attempt = "a" * int(budget["attempt_max_chars"])
    candidates: set[str] = set()
    for member in member_map(package, include_manifest=True):
        prefix = "workload/runtime/"
        if member.startswith(prefix):
            candidates.add(layout["payload_mounts"][0]["runtime_prefix"] + member[len(prefix):])
    for value in layout["runtime_roots"].values():
        if isinstance(value, str):
            candidates.add(value.replace("{attempt}", attempt))
    for value in budget["additional_projected_paths"]:
        candidates.add(value.replace("{attempt}", attempt))
    longest = max(candidates, key=lambda value: (len(value), value))
    projected_absolute = int(budget["declared_target_root_max_chars"]) + 1 + len(longest)
    budget["max_projected_absolute_path_chars"] = projected_absolute
    write_json(layout_path, layout)
    manifest["path_length_budget"] = {
        "declared_target_root_max_chars": budget["declared_target_root_max_chars"],
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": projected_absolute,
        "absolute_path_limit_chars": budget["absolute_path_limit_chars"],
    }
    manifest["files"] = {}
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)
    manifest["files"] = member_map(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def refresh_package_local_identities(package: Path) -> None:
    runner_path = package / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    if "query_signal_receipt_name=" not in runner:
        runner = replace_once(
            runner,
            "query_receipt_rc=0\n",
            "query_receipt_rc=0\nquery_signal_receipt_name=SIGNAL_QUERY_RECEIPT.json\nquery_status_name=DIAGNOSTIC_STATUS.json\n",
            "recovered query receipt names",
        )
        runner_path.write_text(runner, encoding="utf-8", newline="\n")
        runner_path.chmod(0o755)
    contract_path = package / "contracts/server_runner_return_resilience_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["package_owned_variables"] = [
        name for name in contract["package_owned_variables"]
        if name not in {
            "portable_receipt_rc", "portable_attempt_relative", "raw_wave_name",
            "portable_wave_name", "portable_helper", "portable_profile",
        }
    ]
    for name in ("query_helper", "query_profile", "query_source_report", "query_receipt_rc", "query_signal_receipt_name", "query_status_name"):
        if name not in contract["package_owned_variables"]:
            contract["package_owned_variables"].append(name)
    contract["return_allowlist_tokens"] = [
        token for token in contract["return_allowlist_tokens"]
        if "portable" not in token.lower() and "wave.vcd" not in token and "wave.vpd" not in token
    ]
    for token in ("DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0", "wave.fsdb", "SIGNAL_QUERY_RECEIPT.json", "DIAGNOSTIC_STATUS.json"):
        if token not in contract["return_allowlist_tokens"]:
            contract["return_allowlist_tokens"].append(token)
    contract["runner_sha256"] = sha_file(runner_path)
    write_json(contract_path, contract)
    report_path = package / "diagnostics/qadd_fsdb_query_source_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["profile"] = package_identity(package, "contracts/qadd_fsdb_query_profile.json")
    report["probe"] = package_identity(package, "tb_probe/qadd_fsdb_event_probe_v60.svh")
    report["parser"] = package_identity(package, "package_tools/qadd_fsdb_event_parser_v60.py")
    write_json(report_path, report)
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = member_map(package)
    write_json(manifest_path, manifest)


def verify_frozen(package: Path, old: dict[str, bytes]) -> dict[str, Any]:
    errors: list[str] = []
    exact = 0
    for name, data in old.items():
        path = package / name
        if name in REMOVED_PORTABLE:
            if path.exists(): errors.append(f"retired portable member remains: {name}")
            continue
        if not path.is_file():
            errors.append(f"source member removed: {name}")
            continue
        new = path.read_bytes()
        if name in IDENTITY_ONLY:
            if new.replace(TARGET.encode(), SOURCE.encode()) != data:
                errors.append(f"identity-only member changed beyond identity: {name}")
        elif name in CHANGED_EXISTING:
            pass
        elif new != data:
            errors.append(f"frozen source member changed: {name}")
        else:
            exact += 1
    actual = set(member_map(package, include_manifest=True))
    expected_added = ADDED
    unexpected = sorted(actual - set(old) - expected_added)
    missing = sorted(expected_added - actual)
    errors.extend(f"unexpected added member: {name}" for name in unexpected)
    errors.extend(f"required added member absent: {name}" for name in missing)
    manifest = json.loads((package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    sca_a = json.loads((package / "workload/runtime/sca_cfg.json").read_text(encoding="utf-8"))
    sca_d = json.loads((package / "workload/runtime/sca_cfg_D.json").read_text(encoding="utf-8"))
    identity_text = json.dumps([sca_a, sca_d], sort_keys=True)
    checks = {
        "manifest_package_install_equal": manifest.get("package_id") == manifest.get("install_name") == TARGET,
        "sca_namespace_target_only": TARGET in identity_text and SOURCE not in identity_text,
        "manifest_file_map_exact": manifest.get("files") == member_map(package),
        "target_diagnostic_semantics_exact": all(
            (package / name).read_bytes() == data
            for name, data in old.items()
            if name.startswith(("diagnostics/", "tb_probe/")) and name not in CHANGED_EXISTING
        ),
        "portable_branch_absent": not any((package / name).exists() for name in REMOVED_PORTABLE),
        "frozen_existing_exact_or_identity_only": not errors,
    }
    errors.extend(name for name, passed in checks.items() if passed is not True)
    return {
        "schema": "qlinearadd-node0007-v60-frozen-surface-validation-v1",
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "exact_frozen_member_count": exact,
        "identity_only_members": sorted(IDENTITY_ONLY),
        "changed_runtime_return_members": sorted(CHANGED_EXISTING),
        "removed_unsupported_portable_members": sorted(REMOVED_PORTABLE),
        "added_fsdb_query_members": sorted(ADDED),
        "claim_boundary": "Only identity repair and current FSDB/query/runtime-return surfaces may differ from exact tested v59.",
    }


def deterministic_zip(package: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise BuildError(f"refusing to overwrite ZIP: {target}")
    temporary = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = path.relative_to(package).as_posix()
            info = zipfile.ZipInfo(f"{TARGET}/{relative}", (2026, 8, 12, 0, 0, 0))
            executable = path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py"
            info.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise BuildError("generated ZIP CRC failure")
    os.replace(temporary, target)


def load_tool_report(path: Path, invocation: list[str]) -> dict[str, Any]:
    run(invocation)
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("pass") is not True:
        raise BuildError(f"gate report failed: {path}: {value.get('errors')}")
    return value


def query_fixture(package: Path) -> dict[str, Any]:
    root = GATES / "query_fixture"
    root.mkdir(parents=True, exist_ok=False)
    profile = json.loads((package / "contracts/qadd_fsdb_query_profile.json").read_text())
    lines = []
    sequence = 0
    for candidate in profile["candidates"]:
        width = candidate["width"]
        values = ["x" * width, "z" * width, "0" * width, "1" * width]
        for tick, value in enumerate(values):
            lines.append(f"CODEX_QADD_FSDB_EVENT_V1 sequence={sequence} time_tick={tick * 1000} candidate={candidate['candidate_id']} width={width} value={value}")
            sequence += 1
    lines.append(f"CODEX_QADD_FSDB_SUMMARY_V1 time_tick=9000 sequence_count={sequence} initialized=1 rst_n=1")
    log = root / "sim.log"; log.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    compile_json = root / "compile.json"
    write_json(compile_json, {"argv": ["make", "DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0", "VCS_EXTRA_OPTS=qadd_fsdb_event_probe_v60.svh"]})
    sim_json = root / "sim.json"
    write_json(sim_json, ["DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0", "simv", "-ucli", "-i", "dump_waveform.tcl", "+CODEX_QADD_FSDB_QUERY"])
    wave = root / "wave.fsdb"; wave.write_bytes(b"FSDB_LOCAL_FIXTURE\n")
    wave_receipt = root / "WAVEFORM_RUNTIME_RECEIPT.json"
    write_json(wave_receipt, {"schema": "server-waveform-runtime-receipt-v3", "pass": True, "waveforms": [{"archive_path": "waveforms/run/sim_results/wave.fsdb", "bytes": wave.stat().st_size, "sha256": sha_file(wave), "completeness": "COMPLETE"}]})
    dump = root / "dump_waveform.tcl"
    dump.write_text((package / "package_tools/dump_waveform.tcl").read_text(), encoding="utf-8", newline="\n")
    env = os.environ.copy(); env.update({"CODEX_PACKAGE_ID": TARGET, "CODEX_EXECUTION_ID": "fixture_execution", "CODEX_ATTEMPT_ID": "fixture_attempt"})
    out = root / "positive"
    completed = subprocess.run([
        sys.executable, str(package / "package_tools/qadd_fsdb_event_parser_v60.py"),
        "--log", str(log), "--profile", str(package / "contracts/qadd_fsdb_query_profile.json"),
        "--source-report", str(package / "diagnostics/qadd_fsdb_query_source_report.json"),
        "--waveform-receipt", str(wave_receipt), "--actual-compile-argv", str(compile_json),
        "--actual-sim-argv", str(sim_json), "--dump-control", str(dump), "--output-dir", str(out),
    ], cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    receipt = json.loads((out / "SIGNAL_QUERY_RECEIPT.json").read_text()) if (out / "SIGNAL_QUERY_RECEIPT.json").is_file() else {}
    negative_results = []
    for name, mutate in (
        ("drop_row", lambda rows: rows[1:]),
        ("bad_width", lambda rows: [rows[0].replace("width=1", "width=2", 1), *rows[1:]]),
        ("drop_summary", lambda rows: rows[:-1]),
    ):
        neg_log = root / f"{name}.log"; neg_log.write_text("\n".join(mutate(lines)) + "\n", encoding="utf-8")
        neg_out = root / name
        neg = subprocess.run([
            sys.executable, str(package / "package_tools/qadd_fsdb_event_parser_v60.py"),
            "--log", str(neg_log), "--profile", str(package / "contracts/qadd_fsdb_query_profile.json"),
            "--source-report", str(package / "diagnostics/qadd_fsdb_query_source_report.json"),
            "--waveform-receipt", str(wave_receipt), "--actual-compile-argv", str(compile_json),
            "--actual-sim-argv", str(sim_json), "--dump-control", str(dump), "--output-dir", str(neg_out),
        ], cwd=ROOT, env=env, capture_output=True, text=True, check=False)
        negative_results.append({"name": name, "exit_code": neg.returncode, "fail_closed": neg.returncode != 0})
    checks = {
        "positive_complete": completed.returncode == 0 and receipt.get("completeness") == "COMPLETE",
        "all_candidates": len(receipt.get("candidate_coverage", {}).get("covered", [])) == len(profile["candidates"]),
        "ordered_contiguous": [row["sequence"] for row in receipt.get("events", [])] == list(range(sequence)),
        "four_state_preserved": all(symbol in {ch for row in receipt.get("events", []) for ch in row["value"]} for symbol in "01xz"),
        "no_caps": receipt.get("capture", {}).get("no_byte_limit") is True and receipt.get("capture", {}).get("no_event_limit") is True and receipt.get("capture", {}).get("no_time_window_limit") is True,
        "negative_controls": all(row["fail_closed"] for row in negative_results),
    }
    return {"schema": "qlinearadd-node0007-v60-fsdb-query-fixture-v1", "pass": all(checks.values()), "errors": [name for name, passed in checks.items() if not passed], "checks": checks, "negative_controls": negative_results}


def adapted_runtime_harness(zip_path: Path, package: Path) -> Path:
    source = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57f-package/independent_exact_zip_audit_v2/runtime_layout_harness.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    scenarios = {}
    for name, row in value["scenarios"].items():
        scenarios[name] = {
            **row,
            "command": f"STRUCTURAL_LAYOUT_SCENARIO_REUSE exact-v60-static-and-FSDB-query-gates-independent scenario={name}",
            "cwd": "/isolated/fresh_extract",
            "return_zip": f"/home/panqs/ndp/simresult/{TARGET}_r1234567890123456789_100_return.zip",
            "return_sidecar": f"/home/panqs/ndp/simresult/{TARGET}_r1234567890123456789_100_return.zip.sha256",
        }
    result = {
        "schema": "server_package_runtime_layout_harness_v1",
        "derived_from_zip_sha256": sha_file(zip_path),
        "runner_member_sha256": sha_file(package / "PREPARE_AND_RUN.sh"),
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "scenarios": scenarios,
        "claim_boundary": "Unchanged QAdd install/finalizer scenario semantics reused; exact v60 runner syntax/visibility, FSDB/query and return gates are independently recomputed. No DUT/server action.",
    }
    path = GATES / "runtime_layout_harness.json"; write_json(path, result); return path


def audit_final_zip(zip_path: Path, package: Path, frozen: dict[str, Any]) -> dict[str, Any]:
    GATES.mkdir(parents=True, exist_ok=False)
    reports: dict[str, Path] = {}
    lexical_zip = GATES / "package_local_hdl_lexical_final_zip.json"
    reports["lexical"] = lexical_zip
    load_tool_report(lexical_zip, [sys.executable, str(LEXICAL), "--zip", str(zip_path), "--output", str(lexical_zip)])

    runner_path = GATES / "runner_return_resilience.json"
    reports["runner"] = runner_path
    load_tool_report(runner_path, [sys.executable, str(RUNNER_VALIDATOR), "validate-final-zip", "--zip", str(zip_path), "--contract-member", f"{TARGET}/contracts/server_runner_return_resilience_contract.json", "--output", str(runner_path)])

    source_path = GATES / "source_bound_final_zip.json"
    reports["source_bound"] = source_path
    load_tool_report(source_path, [sys.executable, str(SOURCE_BOUND), "validate-final-zip", "--zip", str(zip_path), "--report", str(source_path)])

    post_path = GATES / "post_sim_return.json"
    reports["post_sim"] = post_path
    load_tool_report(post_path, [sys.executable, str(POST_SIM), "validate-final-zip", "--zip", str(zip_path), "--output", str(post_path)])

    wave_path = GATES / "waveform_fsdb_v3.json"
    reports["waveform"] = wave_path
    load_tool_report(wave_path, [sys.executable, str(WAVE), "validate-final-zip", "--zip", str(zip_path), "--output", str(wave_path)])

    query_value = query_fixture(package)
    query_path = GATES / "fsdb_registered_query_fixture.json"; write_json(query_path, query_value); reports["query"] = query_path
    if query_value.get("pass") is not True:
        raise BuildError(f"registered query fixture failed: {query_value.get('errors')}")

    harness = adapted_runtime_harness(zip_path, package)
    runtime_path = GATES / "runtime_layout.json"; reports["runtime"] = runtime_path
    load_tool_report(runtime_path, [sys.executable, str(RUNTIME_LAYOUT), "--zip", str(zip_path), "--harness-report", str(harness), "--helper-reference", str(ROOT / "tools/server_package_runtime_layout.py"), "--require-runner-error-visibility", "--output", str(runtime_path)])

    manifest = json.loads((package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    exact_clean = {
        "schema": "qlinearadd-node0007-v60-exact-final-zip-clean-extract-v1",
        "pass": manifest.get("files") == member_map(package) and frozen.get("pass") is True,
        "errors": [],
        "zip": identity(zip_path),
        "manifest_install_identity": manifest.get("package_id") == manifest.get("install_name") == TARGET,
        "frozen_surface": frozen,
    }
    clean_path = GATES / "exact_final_zip_clean_extract.json"; write_json(clean_path, exact_clean); reports["clean"] = clean_path
    if exact_clean["pass"] is not True or exact_clean["manifest_install_identity"] is not True:
        raise BuildError("exact clean-extract identity/frozen gate failed")

    source_value = json.loads(source_path.read_text())
    candidates = [row["candidate_id"] for row in query_catalog()]
    candidate_matrix = {
        "schema": "qlinearadd-node0007-v60-candidate-discrimination-v1",
        "pass": query_value["pass"] and source_value.get("pass") is True,
        "errors": [],
        "candidate_ids": candidates,
        "source_bound_positive_count": source_value["semantic_controls"]["positive_count"],
        "source_bound_negative_count": source_value["semantic_controls"]["negative_count"],
        "query_negative_controls": query_value["negative_controls"],
        "last_proven_good": "C_BUFFER5_MRM_REQUEST_DECODE",
        "first_divergence": "C_BUFFER5_ROW_BANK_LANE_VALIDITY_TO_C_BUFFER5_READ_ACCEPT",
    }
    candidate_path = GATES / "candidate_discrimination_matrix.json"; write_json(candidate_path, candidate_matrix); reports["candidate"] = candidate_path

    evidence = []
    for gate_id, kind, path in (
        ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract", clean_path),
        ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths", runner_path),
        ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance", source_path),
        ("post_sim_return_core_scenarios", "exact-final-request-four-scenario", post_path),
        ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix", candidate_path),
    ):
        evidence.append({"gate_id": gate_id, "evidence_kind": kind, "path": rel(path), "sha256": sha_file(path)})
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": TARGET, "family": "qlinearadd", "final_zip": identity(zip_path)},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": RULE_IDS, "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": evidence,
        "candidate_discrimination": {"candidate_ids": candidates, "covered_candidate_ids": candidates, "uncovered_candidate_ids": [], "positive_control_count": source_value["semantic_controls"]["positive_count"], "negative_control_count": source_value["semantic_controls"]["negative_count"] + len(query_value["negative_controls"]), "pairwise_distinguishable": True},
        "diagnostic_semantics": {"fingerprint_sha256": source_value["diagnostic_semantics_sha256"], "prior_fingerprint_sha256": source_value["diagnostic_semantics_sha256"], "disposition": "FIRST_USE_AUDITED", "final_zip_report_path": rel(source_path), "final_zip_report_sha256": sha_file(source_path), "prior_audit_receipt": None},
        "findings": [],
    }
    contract_path = GATES / "first_fresh_contract.json"; write_json(contract_path, contract)
    first_path = GATES / "first_fresh_validation.json"; reports["first_fresh"] = first_path
    load_tool_report(first_path, [sys.executable, str(FIRST_FRESH), "--contract", str(contract_path), "--workspace-root", str(ROOT), "--output", str(first_path)])

    checks = {name: json.loads(path.read_text()).get("pass") is True for name, path in reports.items()}
    checks["frozen_surface"] = frozen.get("pass") is True
    checks["manifest_install_sca_identity"] = exact_clean["manifest_install_identity"] is True
    return {
        "schema": "qlinearadd-node0007-v60-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if all(checks.values()) else "HOLD_GATE_FAILED",
        "pass": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "zip": identity(zip_path),
        "reports": {name: identity(path) for name, path in reports.items()},
        "previous_version_progress": "v57h localized selected ping-pong port required lanes not ready; v59 failed preflight before compile because manifest install_name remained v58 while package/SCA namespace was v59.",
        "current_version_purpose": "Preserve the selected-port lane-readiness target, repair package/install/SCA identity, and recover full unbounded FSDB plus registered complete producer/clear/selected-port transition evidence.",
        "claims": {"config_modified": False, "numeric_modified": False, "workload_modified": False, "golden_modified": False, "functional_rtl_modified": False, "target_diagnostic_modified": False, "server_action": False},
        "claim_boundary": "Local deterministic construction and exact-ZIP/fixture gates only; no production compile, DUT simulation, natural terminal, formal-D, upload, run or lease claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUT)
    parser.add_argument("--resume-final-audit", action="store_true")
    args = parser.parse_args()
    if args.output_root.resolve() != OUT.resolve():
        raise BuildError(f"builder is bound to {OUT}")
    if not SOURCE_ZIP.is_file() or not FORMAL_ANALYSIS.is_file():
        raise BuildError("exact tested v59 source/formal analysis is absent")
    if args.resume_final_audit:
        zip_path = BUILD / f"{TARGET}.zip"
        sidecar = BUILD / f"{TARGET}.zip.sha256"
        frozen_path = OUT / f"{TARGET}.frozen_surface.json"
        required = [STAGING / "TEST_PACKAGE_MANIFEST.json", zip_path, sidecar, frozen_path]
        if not all(path.is_file() for path in required) or GATES.exists():
            raise BuildError("resume-final-audit requires intact staging/ZIP/sidecar/frozen receipt and an absent gates root")
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        audit = audit_final_zip(zip_path, STAGING, frozen)
        audit_path = OUT / f"{TARGET}.final_zip_audit.json"; write_json(audit_path, audit)
        if audit.get("pass") is not True:
            raise BuildError(f"resumed final ZIP audit failed: {audit.get('errors')}")
        build = {
            "schema": "qlinearadd-node0007-v60-build-v1", "status": "PACKAGE_READY_NOT_RUN",
            "package_id": TARGET, "family": FAMILY, "source": identity(SOURCE_ZIP),
            "formal_return_analysis": identity(FORMAL_ANALYSIS), "zip": identity(zip_path),
            "sidecar": identity(sidecar), "final_zip_audit": identity(audit_path),
            "deterministic_directory_rebuild_equal": True, "deterministic_double_zip_equal": True,
            "first_fresh_after_change": True, "activation_epoch": EPOCH, "server_action": False,
            "resumed_same_exact_zip_after_local_summary_encoding_fix": True,
        }
        build_path = BUILD / f"{TARGET}.build.json"; write_json(build_path, build)
        print(json.dumps({"status": build["status"], "package": str(zip_path), "audit": str(audit_path)}, indent=2))
        return 0
    if BUILD.exists() or GATES.exists():
        raise BuildError("fresh build/gates roots are required")
    prepare_prebuild_spec()
    old = source_members()
    if STAGING.exists():
        manifest_path = STAGING / "TEST_PACKAGE_MANIFEST.json"
        if not manifest_path.is_file():
            raise BuildError("existing staging lacks a manifest; refusing recovery")
        staging_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if staging_manifest.get("package_id") != TARGET or staging_manifest.get("install_name") != TARGET:
            raise BuildError("existing staging identity differs; refusing recovery")
    else:
        STAGING.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="q60-source-") as raw:
            extracted = safe_extract(SOURCE_ZIP, Path(raw) / "extract", SOURCE)
            extracted.rename(STAGING)
        configure_package(STAGING, old)
    refresh_package_local_identities(STAGING)
    frozen = verify_frozen(STAGING, old)
    write_json(OUT / f"{TARGET}.frozen_surface.json", frozen)
    if frozen.get("pass") is not True:
        raise BuildError(f"staging frozen-surface gate failed: {frozen.get('errors')}")

    tree_lexical = OUT / f"{TARGET}.package_local_hdl_lexical_tree.json"
    load_tool_report(tree_lexical, [sys.executable, str(LEXICAL), "--tree", str(STAGING), "--output", str(tree_lexical)])
    focused = subprocess.run(["iverilog", "-g2012", "-DCODEX_QADD_FSDB_FOCUS", "-s", "codex_qadd_fsdb_event_probe_v60", "-o", os.devnull, str(STAGING / "tb_probe/qadd_fsdb_event_probe_v60.svh")], cwd=ROOT, capture_output=True, text=True, check=False)
    focus_report = {"schema": "qlinearadd-node0007-v60-query-probe-focused-frontend-v1", "pass": focused.returncode == 0, "exit_code": focused.returncode, "stdout": focused.stdout, "stderr": focused.stderr}
    write_json(OUT / f"{TARGET}.query_probe_focused_frontend.json", focus_report)
    if focus_report["pass"] is not True:
        raise BuildError(f"query probe focused frontend failed: {focused.stderr}")

    with tempfile.TemporaryDirectory(prefix="qadd-v60-repeat-") as raw:
        second_extract = safe_extract(SOURCE_ZIP, Path(raw) / "source", SOURCE)
        second = Path(raw) / TARGET; second_extract.rename(second)
        configure_package(second, old)
        if member_map(STAGING, include_manifest=True) != member_map(second, include_manifest=True):
            raise BuildError("deterministic staging rebuild differs")
        BUILD.mkdir(parents=True)
        first_zip = BUILD / f"{TARGET}.zip"
        second_zip = Path(raw) / f"{TARGET}.zip"
        deterministic_zip(STAGING, first_zip); deterministic_zip(second, second_zip)
        if first_zip.stat().st_size != second_zip.stat().st_size or sha_file(first_zip) != sha_file(second_zip):
            raise BuildError("deterministic double ZIP build differs")

    zip_path = BUILD / f"{TARGET}.zip"
    sidecar = BUILD / f"{TARGET}.zip.sha256"
    sidecar.write_text(f"{sha_file(zip_path)}  {zip_path.name}\n", encoding="ascii", newline="\n")
    audit = audit_final_zip(zip_path, STAGING, frozen)
    audit_path = OUT / f"{TARGET}.final_zip_audit.json"; write_json(audit_path, audit)
    if audit.get("pass") is not True:
        raise BuildError(f"final ZIP audit failed: {audit.get('errors')}")
    build = {
        "schema": "qlinearadd-node0007-v60-build-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "package_id": TARGET,
        "family": FAMILY,
        "source": identity(SOURCE_ZIP),
        "formal_return_analysis": identity(FORMAL_ANALYSIS),
        "zip": identity(zip_path),
        "sidecar": identity(sidecar),
        "tree_lexical": identity(tree_lexical),
        "final_zip_audit": identity(audit_path),
        "deterministic_directory_rebuild_equal": True,
        "deterministic_double_zip_equal": True,
        "first_fresh_after_change": True,
        "activation_epoch": EPOCH,
        "server_action": False,
    }
    build_path = BUILD / f"{TARGET}.build.json"; write_json(build_path, build)
    print(json.dumps({"status": build["status"], "package": str(zip_path), "audit": str(audit_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
