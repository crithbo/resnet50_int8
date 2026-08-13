#!/usr/bin/env python3
"""Build the fresh native-Conv FSDB-v3/query successor from tested p43."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p43_portablevq_package as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p44_fsdbvq"
SOURCE_ID = "r5_n4_0cc_p43_portablevq"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane"
    / SOURCE_ID
    / f"{SOURCE_ID}.zip"
)
SOURCE_BYTES = 6_016_442
SOURCE_SHA256 = "657767774ef6762f4e93c3c0b23da71895c7ec699837ca443b0210457d55c11c"
EPOCH = "package-local-hdl-lexical-v1-01211147e247"
WAVE_EPOCH = "fsdb-authoritative-repeatable-return-v3-0a1dee9757c6"
RULE_IDS = [
    "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001",
    "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001",
    "CDA-SERVER-PACKAGE-LOCAL-HDL-RESERVED-DECLARATION-NAME-LEXICAL-001",
]
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p44_fsdbvq"
PREBUILD = BASE / "prebuild"
DEFAULT_OUTPUT = BASE / "build"
PIPELINE = ROOT / "tools/server_package_pipeline.py"
GATE_REGISTRY = ROOT / "contracts/server_package_build_gate_registry_v1.json"
RUNNER_VALIDATOR = ROOT / "tools/validate_server_runner_return_resilience.py"
SOURCE_BOUND_TOOL = ROOT / "tools/generate_server_source_bound_observer.py"
POST_SIM_TOOL = ROOT / "tools/server_post_sim_return.py"
WAVEFORM_TOOL = ROOT / "tools/server_waveform_mandatory_return.py"
LEXICAL_TOOL = ROOT / "tools/validate_server_package_local_hdl_lexical.py"
QUERY_TOOL = ROOT / "tools/conv_native_fsdb_event_query.py"
PYTHON = sys.executable


class BuildError(RuntimeError):
    pass


def configure() -> None:
    prior.PACKAGE_ID = PACKAGE_ID
    prior.SOURCE_ID = SOURCE_ID
    prior.SOURCE_ZIP = SOURCE_ZIP
    prior.SOURCE_BYTES = SOURCE_BYTES
    prior.SOURCE_SHA256 = SOURCE_SHA256
    prior.EPOCH = EPOCH
    prior.RULE_IDS = RULE_IDS
    prior.BASE = BASE
    prior.PREBUILD = PREBUILD
    prior.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    prior.configure()


def command(argv: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha(path: Path) -> str:
    return prior.p42.base.sha256(path)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def source_text(relative: str) -> str:
    return prior.source_text(relative)


def event_probe() -> str:
    candidates = [
        ("mse4_memag_valid", "mse_mem_ag_tag_valid", 1),
        ("mse4_memag_bp_pre", "mse_mem_ag_bp_pre", 1),
        ("mse4_descriptor_valid", "wr_data_chl_req_valid", 1),
        ("mse4_descriptor_ready", "wr_data_chl_req_ready", 1),
        ("mse4_buffer_rvalid", "buf2mse_rvalid", 1),
        ("mse4_buffer_ready", "wr_data_chl_ready", 1),
        ("mse4_wdata_valid", "mse2mem_wdata_valid", 2),
        ("mse4_wdata_ready", "mem2mse_wdata_ready", 2),
        ("mse4_slice_finish", "slice_cmpt_finish", 1),
    ]
    ports = "\n".join(
        f"  input logic {'[1:0] ' if width == 2 else ''}{name}{',' if index < len(candidates) - 1 else ''}"
        for index, (_, name, width) in enumerate(candidates)
    )
    rows = "\n".join(
        f'      $display("CODEX_NATIVE_FSDB_EVENT_V1 instance=%m sequence=%0d time_tick=%0t candidate={candidate_id} width={width} value=%b", event_seq_id, $time, {name});\n'
        "      event_seq_id = event_seq_id + 1;"
        for candidate_id, name, width in candidates
    )
    sensitivity = " or ".join(name for _, name, _ in candidates)
    connections = ",\n".join(f"  .{name}({name})" for _, name, _ in candidates)
    vector = ", ".join(name for _, name, _ in candidates)
    return f'''`timescale 1ps/1ps
module codex_native_fsdb_event_probe (
{ports}
);
  integer event_seq_id;
  task automatic emit_all;
    begin
{rows}
    end
  endtask
  initial begin
    event_seq_id = 0;
    if ($test$plusargs("CODEX_NATIVE_FSDB_QUERY")) begin
      #0;
      emit_all();
    end
  end
  always @({sensitivity}) begin
    if ($test$plusargs("CODEX_NATIVE_FSDB_QUERY")) emit_all();
  end
  final begin
    if ($test$plusargs("CODEX_NATIVE_FSDB_QUERY"))
      $display("CODEX_NATIVE_FSDB_SUMMARY_V1 instance=%m sequence_count=%0d time_tick=%0t end_vector=%b", event_seq_id, $time, {{{vector}}});
  end
endmodule

bind Memory_WR_Stream_Engine codex_native_fsdb_event_probe u_codex_native_fsdb_event_probe (
{connections}
);
'''


def prepare_query(source_bound: dict[str, Path]) -> dict[str, Path]:
    catalog, portable_source = prior.probe_catalog(source_bound)
    binding = json.loads(
        (source_bound["generated"] / "source_bound_probe_binding.json").read_text(encoding="utf-8")
    )
    parents = {
        row["exact_parent_instance"]
        for row in portable_source["candidate_exact_set"]
    }
    if len(parents) != 1:
        raise BuildError("MSE4 query candidates do not bind one exact parent instance")
    parent = next(iter(parents))
    probe = PREBUILD / "native_fsdb_event_probe.svh"
    probe.write_text(event_probe(), encoding="utf-8", newline="\n")
    profile = {
        "schema": "conv-native-fsdb-query-profile-v1",
        "profile_id": "native_conv_mse4_vector_join_fsdb_v1",
        "package_id": PACKAGE_ID,
        "activation_epoch": WAVE_EPOCH,
        "timescale": "1ps",
        "event_prefix": "CODEX_NATIVE_FSDB_EVENT_V1",
        "summary_prefix": "CODEX_NATIVE_FSDB_SUMMARY_V1",
        "exact_probe_instance": f"{parent}.u_codex_native_fsdb_event_probe",
        "candidates": catalog,
        "probe_catalog_sha256": hashlib.sha256(canonical(catalog)).hexdigest(),
        "requirements": {
            "contiguous_sequence": True,
            "every_ordered_4state_transition": True,
            "no_byte_limit": True,
            "no_file_limit": True,
            "no_event_limit": True,
            "no_time_window": True,
            "sampling": False,
            "truncation": False,
        },
        "claim_boundary": (
            "Frozen p42 MSE4 valid/ready/wdata/slice-finish target only; no dynamic DUT claim."
        ),
    }
    profile_path = PREBUILD / "native_fsdb_query_profile.json"
    write_json(profile_path, profile)
    source_report = {
        "schema": "conv-native-fsdb-query-source-report-v1",
        "package_id": PACKAGE_ID,
        "source_package_id": SOURCE_ID,
        "exact_parent_instance": parent,
        "exact_probe_instance": profile["exact_probe_instance"],
        "scope": "tb_NDP_Top_new_phy",
        "depth": 0,
        "timescale": "1ps",
        "catalog_complete": True,
        "candidate_exact_set": portable_source["candidate_exact_set"],
        "probe": {
            "path": "tb_probe/native_fsdb_event_probe.svh",
            "bytes": probe.stat().st_size,
            "sha256": sha(probe),
        },
        "profile": {
            "path": "contracts/native_fsdb_query_profile.json",
            "bytes": profile_path.stat().st_size,
            "sha256": sha(profile_path),
        },
        "source_bound_generation_report": portable_source["source_bound_generation_report"],
        "source_bound_binding": portable_source["source_bound_binding"],
        "writer_count": 1,
        "writer_owner": "package_tools/dump_waveform.tcl",
        "capture": {
            "source": "same-attempt registered package-local event rows plus authoritative FSDB",
            "ordered_every_transition": True,
            "no_byte_limit": True,
            "no_file_limit": True,
            "no_event_limit": True,
            "no_time_window": True,
            "sampling": False,
            "truncation": False,
        },
        "claim_boundary": "Static exact-source identity and candidate binding only; dynamic evidence remains unclaimed.",
    }
    source_report_path = PREBUILD / "native_fsdb_query_source_report.json"
    write_json(source_report_path, source_report)
    return {
        "probe": probe,
        "profile": profile_path,
        "source_report": source_report_path,
    }


def patch_compile_helper(text: str) -> str:
    text = text.replace(
        '"DUMP_VCD=1", "DUMP_FSDB=0",\n        "TB_DUMP_FSDB=0", "DUMP_PORTABLE_VCD=1",',
        '"DUMP_VCD=0", "DUMP_FSDB=1",\n        "TB_DUMP_FSDB=0",',
    )
    text = text.replace(
        'f"VCS_EXTRA_OPTS=+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+{args.package_root / \'tb_probe\'} {args.source}",',
        'f"VCS_EXTRA_OPTS=+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+{args.package_root / \'tb_probe\'} {\' \'.join(str(path) for path in args.source)}",',
    )
    text = text.replace(
        '"waveform_make_arguments": ["DUMP_VCD=1", "DUMP_FSDB=0", "TB_DUMP_FSDB=0", "DUMP_PORTABLE_VCD=1"],',
        '"waveform_make_arguments": ["DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0"],',
    )
    text = text.replace(
        '"package_source": file_identity(args.source),',
        '"package_sources": [file_identity(path) for path in args.source],',
    )
    text = text.replace(
        'start.add_argument("--source", type=Path, required=True)',
        'start.add_argument("--source", type=Path, required=True, action="append")',
    )
    required = ["DUMP_VCD=0", "DUMP_FSDB=1", "package_sources", 'action="append"']
    if not all(token in text for token in required) or "DUMP_PORTABLE_VCD" in text:
        raise BuildError("compile-core FSDB/multi-source patch did not close")
    return text


def patch_runner(text: str) -> str:
    if text.count('waveform_dump_control="$package_root/contracts/server_waveform_dump.tcl"') != 2:
        raise BuildError("p43 mandatory dump-control declaration changed")
    text = text.replace(
        'waveform_dump_control="$package_root/contracts/server_waveform_dump.tcl"',
        'waveform_dump_control="$package_root/package_tools/dump_waveform.tcl"',
    )
    portable = '''portable_shared_helper="$package_root/package_tools/server_waveform_portable_query.py"
portable_family_helper="$package_root/package_tools/conv_native_portable_vcd_query.py"
portable_profile="$package_root/contracts/server_waveform_portable_profile.json"
portable_dump_control="$package_root/contracts/server_waveform_portable_dump.tcl"
portable_source_report="$package_root/diagnostics/portable_query_source_report.json"
portable_collection_status=125'''
    query = '''fsdb_query_helper="$package_root/package_tools/conv_native_fsdb_event_query.py"
fsdb_query_profile="$package_root/contracts/native_fsdb_query_profile.json"
fsdb_query_source_report="$package_root/diagnostics/native_fsdb_query_source_report.json"
fsdb_query_probe="$package_root/tb_probe/native_fsdb_event_probe.svh"
fsdb_query_collection_status=125'''
    if text.count(portable) != 2:
        raise BuildError("p43 portable runner declarations changed")
    text = text.replace(portable, query)
    old_collect = '''portable_collection_status=0
    python3 "$portable_family_helper" collect --profile "$portable_profile" --shared-helper "$portable_shared_helper" --asset-root "$server_root" --attempt-root "$run_root" --output-dir "$run_root/evidence/portable" --source-report "$portable_source_report" --vcd "$run_root/run/sim_results/wave.vcd" --actual-compile-argv "$compile_argv_json" --actual-sim-argv "$run_root/c0/actual_sim_argv.json" --dump-tcl "$waveform_runtime_dump_control" --raw-receipt "$run_root/evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json" --package-id "$package_identity" --execution-id "$return_tag" --attempt-id "$attempt" --exit-kind "$waveform_exit_kind" || portable_collection_status=$?'''
    new_collect = '''fsdb_query_collection_status=0
    python3 "$fsdb_query_helper" collect --log "$run_root/c0/sim.log" --profile "$fsdb_query_profile" --source-report "$fsdb_query_source_report" --waveform-receipt "$run_root/evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json" --actual-compile-argv "$compile_argv_json" --actual-sim-argv "$run_root/c0/actual_sim_argv.json" --dump-control "$waveform_runtime_dump_control" --output-dir "$run_root/evidence/fsdb_query" --package-id "$package_identity" --execution-id "$return_tag" --attempt-id "$attempt" --exit-kind "$waveform_exit_kind" || fsdb_query_collection_status=$?'''
    if text.count(old_collect) != 1:
        raise BuildError("p43 portable collector block changed")
    text = text.replace(old_collect, new_collect)
    text = text.replace(
        'python3 "$compile_core_helper" prepare --output-root "$bootstrap_root" --cwd "$server_root" --makefile "$server_root/Makefile.tb_NDP_Top_new_phy" --source "$source_bound_observer" --package-root "$package_root" --run-dir "$compile_root"',
        'python3 "$compile_core_helper" prepare --output-root "$bootstrap_root" --cwd "$server_root" --makefile "$server_root/Makefile.tb_NDP_Top_new_phy" --source "$source_bound_observer" --source "$fsdb_query_probe" --package-root "$package_root" --run-dir "$compile_root"',
    )
    old_compile = 'compile DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 DUMP_PORTABLE_VCD=1 RUN_DIR="$compile_root" VCS_EXTRA_OPTS="+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe $source_bound_observer"'
    new_compile = 'compile DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0 RUN_DIR="$compile_root" VCS_EXTRA_OPTS="+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe $source_bound_observer $fsdb_query_probe"'
    if text.count(old_compile) != 1:
        raise BuildError("p43 production compile line changed")
    text = text.replace(old_compile, new_compile)
    dump_old = '''mkdir -p "$run_root/run/sim_results" || runner_fail 8 "portable waveform runtime root cannot be created"
waveform_runtime_dump_control="$run_root/run/sim_results/codex_waveform_portable.tcl"
cp -- "$portable_dump_control" "$waveform_runtime_dump_control" || runner_fail 8 "portable waveform dump control materialization failed"
grep -F "dump -file install/codex_runs/r5_n4_0cc_p44_fsdbvq/a0/run/sim_results/wave.vpd -type VPD" "$waveform_runtime_dump_control" >/dev/null || runner_fail 8 "authoritative VPD path binding failed"
grep -F "dump -file install/codex_runs/r5_n4_0cc_p44_fsdbvq/a0/run/sim_results/wave.vcd -type VCD" "$waveform_runtime_dump_control" >/dev/null || runner_fail 8 "direct portable VCD path binding failed"
[ "$(grep -Fc "dump -add tb_NDP_Top_new_phy -depth 0 -aggregates" "$waveform_runtime_dump_control")" -eq 2 ] || runner_fail 8 "dual full-hierarchy scope binding failed"'''
    dump_new = '''mkdir -p "$run_root/run/sim_results" || runner_fail 8 "FSDB waveform runtime root cannot be created"
waveform_runtime_dump_control="$run_root/run/sim_results/dump_waveform.tcl"
printf 'set CODEX_WAVE_PATH {%s}\n' "$run_root/run/sim_results/wave.fsdb" > "$waveform_runtime_dump_control" || runner_fail 8 "FSDB path preamble materialization failed"
cat "$waveform_dump_control" >> "$waveform_runtime_dump_control" || runner_fail 8 "FSDB dump control materialization failed"
grep -F "fsdbDumpfile \\$CODEX_WAVE_PATH" "$waveform_runtime_dump_control" >/dev/null || runner_fail 8 "attempt-local FSDB path binding failed"
grep -F "fsdbDumpvars 0 tb_NDP_Top_new_phy" "$waveform_runtime_dump_control" >/dev/null || runner_fail 8 "full-hierarchy depth-0 FSDB scope binding failed"'''
    if text.count(dump_old) != 1:
        raise BuildError("p43 dump-control block changed")
    text = text.replace(dump_old, dump_new)
    text = text.replace(
        "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 DUMP_PORTABLE_VCD=1",
        "DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0",
    )
    text = text.replace(
        'python3 "$portable_family_helper" argv-json',
        'python3 "$fsdb_query_helper" argv-json',
    )
    text = text.replace(
        "+CODEX_CAUSAL_OBSERVER +SCA_CFG=",
        "+CODEX_CAUSAL_OBSERVER +CODEX_NATIVE_FSDB_QUERY +SCA_CFG=",
    )
    text = text.replace(
        '+vcs+lic+wait +CODEX_CAUSAL_OBSERVER "+SCA_CFG=',
        '+vcs+lic+wait +CODEX_CAUSAL_OBSERVER +CODEX_NATIVE_FSDB_QUERY "+SCA_CFG=',
    )
    forbidden = ("DUMP_PORTABLE_VCD", "wave.vpd", "wave.vcd", "portable_")
    if any(token in text for token in forbidden):
        raise BuildError("retired portable/VPD runner surface remains")
    required = (
        "DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0",
        "+CODEX_NATIVE_FSDB_QUERY",
        "fsdbDumpvars 0 tb_NDP_Top_new_phy",
        '--source "$fsdb_query_probe"',
    )
    if not all(token in text for token in required):
        raise BuildError("FSDB/query runner patch incomplete")
    return text


def waveform_plan() -> dict[str, Any]:
    return {
        "schema": "server-waveform-mandatory-plan-v3",
        "package_id": PACKAGE_ID,
        "family": "conv_native_four_lane",
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
        "claim_boundary": (
            "Authoritative attempt-local unbounded full-hierarchy depth-0 FSDB plus all shards; "
            "no dynamic DUT success claim."
        ),
    }


def prepare_prebuild() -> dict[str, Any]:
    if PREBUILD.exists():
        raise BuildError("refusing to overwrite p44 prebuild")
    PREBUILD.mkdir(parents=True)
    source_bound = prior.prepare_source_bound()
    query = prepare_query(source_bound)
    runner = PREBUILD / "PREPARE_AND_RUN.sh"
    runner.write_text(patch_runner(source_text("PREPARE_AND_RUN.sh")), encoding="utf-8", newline="\n")
    compile_helper = PREBUILD / "compile_core_evidence.py"
    compile_helper.write_text(
        patch_compile_helper(source_text("package_tools/compile_core_evidence.py")),
        encoding="utf-8",
        newline="\n",
    )
    shutil.copyfile(POST_SIM_TOOL, PREBUILD / "server_post_sim_return.py")
    shutil.copyfile(WAVEFORM_TOOL, PREBUILD / "server_waveform_mandatory_return.py")
    shutil.copyfile(QUERY_TOOL, PREBUILD / "conv_native_fsdb_event_query.py")
    for relative, target in (
        ("package_tools/fixed_simresult_publisher.py", "fixed_simresult_publisher.py"),
        ("tb_probe/native_return_observer.svh", "native_return_observer.svh"),
    ):
        (PREBUILD / target).write_text(source_text(relative), encoding="utf-8", newline="\n")
    plan = PREBUILD / "server_waveform_mandatory_plan.json"
    write_json(plan, waveform_plan())
    dump = PREBUILD / "dump_waveform.tcl"
    rendered = command(
        [PYTHON, str(WAVEFORM_TOOL), "render-dump-control", "--plan", str(plan), "--output", str(dump)]
    )
    if rendered.returncode:
        raise BuildError(f"FSDB dump render failed: {rendered.stderr}\n{rendered.stdout}")
    contract = PREBUILD / "server_runner_return_resilience_contract.json"
    write_json(contract, prior.p42.p41.runner_contract(runner))
    runner_validation = PREBUILD / "runner_return_resilience.validation.json"
    checked = command(
        [PYTHON, str(RUNNER_VALIDATOR), "validate-tree", "--root", str(PREBUILD), "--contract", str(contract), "--output", str(runner_validation)]
    )
    if checked.returncode:
        raise BuildError(f"runner resilience prebuild failed: {checked.stderr}\n{checked.stdout}")
    runner_report = PREBUILD / "runner_return_resilience.json"
    write_json(
        runner_report,
        {
            "schema": "server-package-cheap-check-result-v1",
            "gate_id": "runner_return_resilience",
            "pass": True,
            "errors": [],
            "warnings": [],
            "exact_validation": {
                "path": runner_validation.relative_to(ROOT).as_posix(),
                "bytes": runner_validation.stat().st_size,
                "sha256": sha(runner_validation),
            },
        },
    )
    lexical_prebuild = PREBUILD / "package_local_hdl_lexical.prebuild.json"
    lexical = command([PYTHON, str(LEXICAL_TOOL), "--tree", str(PREBUILD), "--output", str(lexical_prebuild)])
    if lexical.returncode:
        raise BuildError(f"prebuild HDL lexical aggregate failed: {lexical.stderr}\n{lexical.stdout}")
    package_local_hdl = PREBUILD / "package_local_hdl.json"
    source_generation = json.loads(source_bound["cheap"].read_text(encoding="utf-8"))
    write_json(
        package_local_hdl,
        {
            "schema": "server-package-cheap-check-result-v1",
            "gate_id": "package_local_hdl",
            "pass": source_generation.get("pass") is True,
            "errors": source_generation.get("errors", []),
            "warnings": source_generation.get("warnings", []),
            "exact_generated_observer": {
                "path": (source_bound["generated"] / "source_bound_causal_observer.svh").relative_to(ROOT).as_posix(),
                "bytes": (source_bound["generated"] / "source_bound_causal_observer.svh").stat().st_size,
                "sha256": sha(source_bound["generated"] / "source_bound_causal_observer.svh"),
            },
            "additional_package_local_hdl_lexical": {
                "path": lexical_prebuild.relative_to(ROOT).as_posix(),
                "bytes": lexical_prebuild.stat().st_size,
                "sha256": sha(lexical_prebuild),
            },
        },
    )

    source_spec = ROOT / "outputs/conv_native_four_lane_0ccae916_p43_portablevq/server_package_build_spec_v2.json"
    spec = json.loads(source_spec.read_text(encoding="utf-8"))
    spec.update(
        {
            "package_id": PACKAGE_ID,
            "lifecycle": "NEXT_FRESH_SUCCESSOR",
            "changed_surfaces": [
                "package_identity",
                "runner",
                "return_core_contract",
                "return_collector",
                "waveform",
                "package_local_hdl",
                "probe_catalog",
                "storage",
            ],
            "rule_change_epoch": {
                "epoch_id": EPOCH,
                "first_fresh_after_change": True,
                "notification_acknowledged": True,
            },
            "receipt_reuse_candidates": [],
        }
    )
    inputs = [
        (SOURCE_ZIP, "package_identity"),
        (runner, "runner"),
        (contract, "return_core_contract"),
        (compile_helper, "return_collector"),
        (PREBUILD / "fixed_simresult_publisher.py", "return_collector"),
        (PREBUILD / "server_post_sim_return.py", "return_collector"),
        (PREBUILD / "server_waveform_mandatory_return.py", "waveform"),
        (PREBUILD / "conv_native_fsdb_event_query.py", "return_collector"),
        (plan, "waveform"),
        (dump, "waveform"),
        (query["profile"], "probe_catalog"),
        (query["source_report"], "probe_catalog"),
        (query["probe"], "package_local_hdl"),
        (source_bound["catalog"], "probe_catalog"),
        (source_bound["plan"], "probe_plan"),
        (source_bound["generated"] / "source_bound_causal_observer.svh", "package_local_hdl"),
        (source_bound["generated"] / "source_bound_causal_parser.py", "parser"),
        (PREBUILD / "native_return_observer.svh", "observer"),
    ]
    spec["inputs"] = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "surface": surface,
            "bytes": path.stat().st_size,
            "sha256": sha(path),
        }
        for path, surface in inputs
    ]
    fixtures = {
        "core_identity_bootstrap": ROOT / "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json",
        "storage_rotation": ROOT / "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json",
        "intermediate_report_format": ROOT / "fixtures/server_package_pipeline_v1/cheap/intermediate_report_format.json",
    }
    spec["cheap_check_reports"] = [
        {"gate_id": gate, "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}
        for gate, path in fixtures.items()
    ] + [
        {
            "gate_id": "source_bound_observer_generation",
            "path": source_bound["cheap"].relative_to(ROOT).as_posix(),
            "sha256": sha(source_bound["cheap"]),
        },
        {
            "gate_id": "runner_return_resilience",
            "path": runner_report.relative_to(ROOT).as_posix(),
            "sha256": sha(runner_report),
        },
        {
            "gate_id": "package_local_hdl",
            "path": package_local_hdl.relative_to(ROOT).as_posix(),
            "sha256": sha(package_local_hdl),
        },
    ]
    validators = spec.setdefault("validators", {})
    validators["runner_return_resilience"] = {"validator_sha256": sha(RUNNER_VALIDATOR), "fixture_sha256": sha(runner_report)}
    validators["package_local_hdl_lexical_final_zip"] = {"validator_sha256": sha(LEXICAL_TOOL), "fixture_sha256": sha(lexical_prebuild)}
    validators["waveform_observation_final_zip"] = {"validator_sha256": sha(WAVEFORM_TOOL), "fixture_sha256": sha(plan)}
    validators["waveform_portable_local_decodability"] = {"validator_sha256": sha(QUERY_TOOL), "fixture_sha256": sha(query["profile"])}
    spec_path = BASE / "server_package_build_spec_v2.json"
    write_json(spec_path, spec)
    profile = BASE / "server_package_build_profile_v2.json"
    aggregated = command(
        [PYTHON, str(PIPELINE), "prepare", "--spec", str(spec_path), "--registry", str(GATE_REGISTRY), "--workspace-root", str(ROOT), "--output", str(profile)]
    )
    if aggregated.returncode:
        raise BuildError(f"shared staging aggregate failed: {aggregated.stderr}\n{aggregated.stdout}")
    value = json.loads(profile.read_text(encoding="utf-8"))
    if value.get("contract_valid") is not True or value.get("preflight", {}).get("errors") != []:
        raise BuildError(f"shared staging aggregate did not close: {value.get('preflight')}")
    if value.get("execution_contract", {}).get("prebuild_aggregate_top_level_invocations") != 1:
        raise BuildError("shared staging aggregate invocation count changed")
    return {
        "runner": runner,
        "compile_helper": compile_helper,
        "contract": contract,
        "runner_report": runner_report,
        "plan": plan,
        "dump": dump,
        "query": query,
        "source_bound": source_bound,
        "spec": spec_path,
        "profile": profile,
        "lexical_prebuild": lexical_prebuild,
    }


def patch_layout(package: Path) -> None:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["package_id"] = PACKAGE_ID
    value["install_name"] = PACKAGE_ID
    value["claim_boundary"] = "Frozen p43 package with fresh FSDB-v3/query runtime-return surfaces only."
    paths = value["path_budget"]["additional_projected_paths"]
    paths = [
        item
        for item in paths
        if not any(token in item.lower() for token in ("portable", "wave.vpd", "wave.vcd", "codex_waveform"))
    ]
    additions = [
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/c0/actual_sim_argv.json",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/run/sim_results/dump_waveform.tcl",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/run/sim_results/wave.fsdb",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/fsdb_query/SIGNAL_QUERY_RECEIPT.json",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/fsdb_query/FSDB_QUERY_BINDING.json",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/fsdb_query/DIAGNOSTIC_STATUS.json",
    ]
    value["path_budget"]["additional_projected_paths"] = paths + [item for item in additions if item not in paths]
    write_json(path, value)


def patch_return(package: Path) -> None:
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["package_id"] = PACKAGE_ID
    request["core_entries"] = [
        row
        for row in request["core_entries"]
        if not any(token in (row.get("archive", "") + " " + row.get("source", "")).lower() for token in ("portable", "wave.vpd", "wave.vcd", "codex_waveform"))
    ]
    archives = {row["archive"] for row in request["core_entries"]}
    additions = [
        ("runs/c0/actual_sim_argv.json", "c0/actual_sim_argv.json", True, "attempt"),
        ("runs/c0/dump_waveform.tcl", "run/sim_results/dump_waveform.tcl", True, "attempt"),
        ("evidence/fsdb_query/SIGNAL_QUERY_RECEIPT.json", "evidence/fsdb_query/SIGNAL_QUERY_RECEIPT.json", False, "attempt"),
        ("evidence/fsdb_query/FSDB_QUERY_BINDING.json", "evidence/fsdb_query/FSDB_QUERY_BINDING.json", False, "attempt"),
        ("evidence/fsdb_query/DIAGNOSTIC_STATUS.json", "evidence/fsdb_query/DIAGNOSTIC_STATUS.json", False, "attempt"),
        ("evidence/fsdb_query/native_fsdb_query_source_report.json", "diagnostics/native_fsdb_query_source_report.json", True, "package"),
    ]
    for archive, source, required, root in additions:
        if archive not in archives:
            request["core_entries"].append({"archive": archive, "source": source, "required": required, "source_root": root})
    request["waveform_discovery"] = {
        "plan_member": "contracts/server_waveform_mandatory_plan.json",
        "collector_member": "package_tools/server_waveform_mandatory_return.py",
        "runtime_receipt_source": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
        "collect_all_matching": True,
        "required_when_simulation_started": True,
        "no_size_limit": True,
        "manifest_archive_path": "waveforms/WAVEFORM_RUNTIME_RECEIPT.json",
    }
    request["claim_boundary"] = (
        "Frozen p42 vector-handshake/MSE4 target plus authoritative FSDB and registered complete event receipt; "
        "query failure preserves raw/core return and marks evidence incomplete."
    )
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract.update(
        {
            "package_id": PACKAGE_ID,
            "helper_sha256": sha(package / "package_tools/server_post_sim_return.py"),
            "request_sha256": sha(request_path),
            "claim_boundary": request["claim_boundary"],
        }
    )
    write_json(contract_path, contract)


def patch_manifest(package: Path, assets: dict[str, Any]) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value.update(
        {
            "schema": "conv-native-four-lane-0ccae916-p44-fsdbvq-package-v1",
            "package_identity": PACKAGE_ID,
            "install_name": PACKAGE_ID,
            "workload_install_name": PACKAGE_ID,
            "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
            "return_name": f"{PACKAGE_ID}_<execution_id>_return.zip",
            "status": "PACKAGE_READY_NOT_RUN",
            "candidate_release": False,
            "previous_version_progress": (
                "p41 passed production compile beyond the Datahub repair; p42 corrected the two-bit vector "
                "handshake predicate; p43 was stopped at 0 ps by the retired direct-VCD command before MSE4 execution."
            ),
            "current_version_purpose": (
                "Preserve the p42 correction and MSE4 target while replacing retired VPD/direct-VCD runtime "
                "surfaces with authoritative FSDB-v3 and a complete source-bound registered event receipt."
            ),
        }
    )
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested_preserved",
        "reason": "User-authorized fresh FSDB-v3/query successor under the activated lexical hard gate.",
        "authorized_config_change": None,
        "numeric_w3_golden_repeated": False,
    }
    value["rule_change_epoch"] = {
        "epoch_id": EPOCH,
        "family": "conv_native_four_lane",
        "package_id": PACKAGE_ID,
        "first_fresh_after_change": True,
        "notification_acknowledged": True,
        "rule_ids": RULE_IDS,
        "upload_hold_until": "LOCAL_GATES_PASS_AND_SEPARATE_SERVER_EXECUTION_AUTHORIZATION",
    }
    value["repair_delta"] = {
        "changed_surfaces": [
            "package_identity",
            "fsdb_dump_control",
            "registered_query_probe_and_parser",
            "compile_sim_argv_receipts",
            "runtime_return_contract",
            "storage",
        ],
        "source_p42_vector_handshake_repair_preserved": True,
        "target_diagnostic_modified": False,
        "functional_rtl_modified": False,
        "config_numeric_workload_golden_modified": False,
    }
    value.pop("portable_waveform_query", None)
    value["fsdb_waveform_query"] = {
        "waveform_epoch": WAVE_EPOCH,
        "capture_mode": "AUTHORITATIVE_FSDB_AND_REGISTERED_EVENT_ROWS",
        "make_arguments": {"DUMP_VCD": 0, "DUMP_FSDB": 1, "TB_DUMP_FSDB": 0},
        "full_hierarchy_depth0": True,
        "raw_unbounded": True,
        "all_shards": True,
        "registered_query_profile": "contracts/native_fsdb_query_profile.json",
        "registered_query_source_report": "diagnostics/native_fsdb_query_source_report.json",
        "query_failure_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "raw_and_core_return_preserved_on_query_failure": True,
    }
    matrix = value.setdefault("release_gate_matrix", {})
    matrix["waveform_observation_final_zip"] = {"applicability": "blocking_applicable", "blocking": True, "pass": None, "semantic_version": "3"}
    matrix["waveform_portable_local_decodability"] = {"applicability": "blocking_applicable", "blocking": True, "pass": None, "semantic_version": "2"}
    matrix["package_local_hdl_lexical_final_zip"] = {"applicability": "blocking_applicable", "blocking": True, "pass": None, "semantic_version": "1"}
    matrix["first_fresh_extra_audit"] = {"applicability": "blocking_applicable", "blocking": True, "pass": None, "epoch_id": EPOCH}
    value["server_actions_performed"] = []
    layout_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    members = [row.relative_to(package).as_posix() for row in package.rglob("*") if row.is_file()]
    projected: set[str] = set()
    for mount in layout["payload_mounts"]:
        source_prefix = mount["source_prefix"]
        projected.update(
            mount["runtime_prefix"] + member[len(source_prefix):]
            for member in members
            if member.startswith(source_prefix)
        )
    attempt = "a" * int(layout["path_budget"]["attempt_max_chars"])
    projected.update(item.replace("{attempt}", attempt) for item in layout["runtime_roots"].values())
    projected.update(item.replace("{attempt}", attempt) for item in layout["path_budget"]["additional_projected_paths"])
    longest = max(projected, key=lambda item: (len(item), item))
    absolute = int(layout["path_budget"]["declared_target_root_max_chars"]) + 1 + len(longest)
    layout["path_budget"]["max_projected_absolute_path_chars"] = absolute
    write_json(layout_path, layout)
    inner = [row.relative_to(package).as_posix() for row in package.rglob("*") if row.is_file() and row != path]
    value["path_length_budget"] = {
        **value.get("path_length_budget", {}),
        "declared_target_root_max_chars": layout["path_budget"]["declared_target_root_max_chars"],
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": absolute,
        "absolute_path_limit_chars": layout["path_budget"]["absolute_path_limit_chars"],
        "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{relative}") for relative in inner),
        "max_inner_suffix_chars": max(map(len, inner)),
        "max_inner_depth": max(len(PurePosixPath(relative).parts) for relative in inner),
        "max_inner_component_chars": max(len(part) for relative in inner for part in PurePosixPath(relative).parts),
        "outer_identity_repeated_inside": False,
    }
    value["files"] = {
        row.relative_to(package).as_posix(): {"sha256": sha(row), "size_bytes": row.stat().st_size}
        for row in sorted(package.rglob("*"))
        if row.is_file() and row != path
    }
    write_json(path, value)


def verify_frozen(package: Path) -> dict[str, Any]:
    protected = [
        "tb_probe/native_return_observer.svh",
        "tb_probe/source_bound_causal_observer.svh",
        "tb_probe/source_bound_observer_focus.sv",
        "package_tools/source_bound_causal_parser.py",
        "package_tools/arm_known_parser.py",
        "package_tools/sa_epoch_parser.py",
        "package_tools/mse4_join_parser.py",
        "diagnostics/source_bound_probe_catalog.json",
        "diagnostics/source_bound_probe_plan.json",
        "diagnostics/arm_known_contract.json",
        "diagnostics/sa_epoch_contract.json",
        "diagnostics/mse4_join_contract.json",
        "diagnostics/exact_instance_identity.json",
    ]
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        prefix = SOURCE_ID + "/"
        normalized: dict[str, bool] = {}
        for relative in protected:
            current = (package / relative).read_bytes().replace(PACKAGE_ID.encode(), SOURCE_ID.encode())
            source = archive.read(prefix + relative)
            if relative.endswith("source_bound_causal_observer.svh"):
                marker = re.compile(rb"plan_semantic_sha256=[0-9a-f]{64}")
                current = marker.sub(b"plan_semantic_sha256=<IDENTITY_BOUND>", current)
                source = marker.sub(b"plan_semantic_sha256=<IDENTITY_BOUND>", source)
            if relative.endswith(".json"):
                try:
                    normalized[relative] = json.loads(current) == json.loads(source)
                    continue
                except (UnicodeDecodeError, json.JSONDecodeError):
                    pass
            normalized[relative] = current == source
        workload = sorted(
            name[len(prefix):]
            for name in archive.namelist()
            if name.startswith(prefix + "workload/runtime/") and not name.endswith("/")
        )
        workload_equal = all(
            (package / relative).read_bytes().replace(PACKAGE_ID.encode(), SOURCE_ID.encode())
            == archive.read(prefix + relative)
            for relative in workload
        )
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    result = {
        "source_p43_zip_bytes": SOURCE_BYTES,
        "source_p43_zip_sha256": SOURCE_SHA256,
        "workload_member_count": len(workload),
        "workload_identity_normalized_byte_equal": workload_equal,
        "protected_diagnostic_identity_normalized_equal": normalized,
        "p42_vector_handshake_and_mse4_target_frozen": all(normalized.values()),
        "config_numeric_workload_golden_functional_rtl_frozen": workload_equal,
        "fsdb_v3_flags": all(token in runner for token in ("DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0")),
        "retired_vpd_direct_vcd_absent": all(token not in runner for token in ("DUMP_PORTABLE_VCD", "wave.vpd", "wave.vcd")),
        "functional_rtl_modified": False,
        "target_diagnostic_modified": False,
    }
    if not all((workload_equal, all(normalized.values()), result["fsdb_v3_flags"], result["retired_vpd_direct_vcd_absent"])):
        raise BuildError(f"p44 frozen-surface audit failed: {result}")
    return result


def materialize(destination: Path, assets: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    package = prior.p42.base.safe_extract(destination)
    prior.p42.base.reidentity(package)
    obsolete = [
        "package_tools/server_waveform_portable_query.py",
        "package_tools/conv_native_portable_vcd_query.py",
        "tools/server_waveform_local_analysis.py",
        "contracts/server_waveform_portable_profile.json",
        "contracts/server_waveform_portable_dump.tcl",
        "contracts/server_waveform_dump.tcl",
        "diagnostics/portable_query_source_report.json",
    ]
    for relative in obsolete:
        path = package / relative
        if path.exists():
            path.unlink()
    shutil.copyfile(assets["runner"], package / "PREPARE_AND_RUN.sh")
    shutil.copyfile(assets["compile_helper"], package / "package_tools/compile_core_evidence.py")
    shutil.copyfile(PREBUILD / "fixed_simresult_publisher.py", package / "package_tools/fixed_simresult_publisher.py")
    shutil.copyfile(POST_SIM_TOOL, package / "package_tools/server_post_sim_return.py")
    shutil.copyfile(WAVEFORM_TOOL, package / "package_tools/server_waveform_mandatory_return.py")
    shutil.copyfile(QUERY_TOOL, package / "package_tools/conv_native_fsdb_event_query.py")
    shutil.copyfile(assets["plan"], package / "contracts/server_waveform_mandatory_plan.json")
    shutil.copyfile(assets["dump"], package / "package_tools/dump_waveform.tcl")
    shutil.copyfile(assets["query"]["profile"], package / "contracts/native_fsdb_query_profile.json")
    shutil.copyfile(assets["query"]["source_report"], package / "diagnostics/native_fsdb_query_source_report.json")
    shutil.copyfile(assets["query"]["probe"], package / "tb_probe/native_fsdb_event_probe.svh")
    generated = assets["source_bound"]["generated"]
    shutil.copyfile(generated / "source_bound_causal_observer.svh", package / "tb_probe/source_bound_causal_observer.svh")
    shutil.copyfile(generated / "source_bound_observer_focus.sv", package / "tb_probe/source_bound_observer_focus.sv")
    shutil.copyfile(generated / "source_bound_causal_parser.py", package / "package_tools/source_bound_causal_parser.py")
    shutil.copyfile(generated / "source_bound_probe_binding.json", package / "diagnostics/source_bound_probe_binding.json")
    shutil.copyfile(assets["source_bound"]["report"], package / "diagnostics/source_bound_generation_report.json")
    shutil.copyfile(assets["source_bound"]["cheap"], package / "diagnostics/source_bound_observer_generation.json")
    shutil.copyfile(assets["source_bound"]["catalog"], package / "diagnostics/source_bound_probe_catalog.json")
    shutil.copyfile(assets["source_bound"]["plan"], package / "diagnostics/source_bound_probe_plan.json")
    patch_layout(package)
    patch_return(package)
    write_json(package / "server_runner_return_resilience_contract.json", prior.p42.p41.runner_contract(package / "PREPARE_AND_RUN.sh"))
    prior.p42.base.refresh_derived_contracts(package)
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    pointer_value = json.loads(pointer.read_text(encoding="utf-8"))
    pointer_value.update({"schema": "conv-native-four-lane-p44-fsdbvq-pointer-v1", "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN"})
    write_json(pointer, pointer_value)
    readme = package / "README.md"
    readme.write_text(
        re.sub(r"\n## p43 first-fresh portable evidence.*\Z", "", readme.read_text(encoding="utf-8"), flags=re.S)
        + (
            "\n## p44 FSDB-v3 registered evidence\n\n"
            "This fresh p43-equivalent successor preserves the p42 vector-handshake correction and MSE4 target. "
            "It uses only attempt-local unbounded full-hierarchy FSDB plus a source-bound registered event receipt. "
            "Query failure marks DIAGNOSTIC_EVIDENCE_INCOMPLETE while raw FSDB and compile/sim/core return remain publishable.\n"
        ),
        encoding="utf-8",
        newline="\n",
    )
    patch_manifest(package, assets)
    return package, verify_frozen(package)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    configure()
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or sha(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact tested p43 source ZIP differs")
    assets = prepare_prebuild()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = [
        output / PACKAGE_ID,
        output / f"{PACKAGE_ID}.zip",
        output / f"{PACKAGE_ID}.zip.sha256",
        output / f"{PACKAGE_ID}.build.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite p44 build output")
    package, frozen = materialize(output, assets)
    lexical_tree = BASE / "package_local_hdl_lexical.staging.json"
    lexical = command([PYTHON, str(LEXICAL_TOOL), "--tree", str(package), "--output", str(lexical_tree)])
    if lexical.returncode:
        raise BuildError(f"staging HDL lexical aggregate failed: {lexical.stderr}\n{lexical.stdout}")
    with tempfile.TemporaryDirectory(prefix=".p44_repeat_", dir=ROOT) as temporary:
        _, repeated_frozen = materialize(Path(temporary), assets)
        repeated = Path(temporary) / PACKAGE_ID
        deterministic = prior.p42.base.tree_receipt(package) == prior.p42.base.tree_receipt(repeated)
    if not deterministic or repeated_frozen != frozen:
        raise BuildError("p44 deterministic double staging differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    prior.p42.base.deterministic_zip(package, zip_path)
    digest = sha(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p44-fsdbvq-build-v1",
        "status": "PACKAGE_BUILT_UPLOAD_HELD_PENDING_EXACT_FINAL_ZIP_GATES",
        "package_identity": PACKAGE_ID,
        "source_p43_zip_sha256": SOURCE_SHA256,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": True,
        "capture_mode": "AUTHORITATIVE_FSDB_AND_REGISTERED_EVENT_ROWS",
        "prebuild_aggregate_top_level_invocations": 1,
        "staging_hdl_lexical_aggregate_pass": True,
        "final_zip_count": 1,
        "zip": zip_path.relative_to(ROOT).as_posix(),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "deterministic_double_build_tree_equal": deterministic,
        "frozen": frozen,
        "shared_aggregate": {
            "path": assets["profile"].relative_to(ROOT).as_posix(),
            "bytes": assets["profile"].stat().st_size,
            "sha256": sha(assets["profile"]),
        },
        "staging_lexical_receipt": {
            "path": lexical_tree.relative_to(ROOT).as_posix(),
            "bytes": lexical_tree.stat().st_size,
            "sha256": sha(lexical_tree),
        },
        "config_numeric_workload_golden_rtl_frozen": True,
        "target_diagnostic_frozen": True,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
