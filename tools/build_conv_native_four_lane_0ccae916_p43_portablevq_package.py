#!/usr/bin/env python3
"""Build the p42-equivalent first-fresh direct-VCD/query successor."""

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

import build_conv_native_four_lane_0ccae916_p42_vecjoinfix_package as p42
import conv_native_portable_vcd_query as query_adapter
import server_waveform_portable_query as portable


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p43_portablevq"
SOURCE_ID = "r5_n4_0cc_p42_vecjoinfix"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
SOURCE_BYTES = 5_987_936
SOURCE_SHA256 = "e742737932de3158a2bb2905a2e56f7c260e170289d4e9484cde545108c23e55"
EPOCH = "waveform-portable-local-decodability-v1-b0a94cf60d6e"
RULE_ID = "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001"
RULE_IDS = [
    "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001",
    RULE_ID,
]
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p43_portablevq"
PREBUILD = BASE / "prebuild"
DEFAULT_OUTPUT = BASE / "build"
PIPELINE = ROOT / "tools/server_package_pipeline.py"
GATE_REGISTRY = ROOT / "contracts/server_package_build_gate_registry_v1.json"
RUNNER_VALIDATOR = ROOT / "tools/validate_server_runner_return_resilience.py"
SOURCE_BOUND_TOOL = ROOT / "tools/generate_server_source_bound_observer.py"
POST_SIM_TOOL = ROOT / "tools/server_post_sim_return.py"
WAVEFORM_TOOL = ROOT / "tools/server_waveform_mandatory_return.py"
PORTABLE_TOOL = ROOT / "tools/server_waveform_portable_query.py"
LOCAL_ANALYSIS_TOOL = ROOT / "tools/server_waveform_local_analysis.py"
QUERY_ADAPTER = ROOT / "tools/conv_native_portable_vcd_query.py"
FIRST_FRESH_TOOL = ROOT / "tools/validate_server_first_fresh_extra_audit.py"
PYTHON = sys.executable


class BuildError(RuntimeError):
    pass


def configure() -> None:
    p42.PACKAGE_ID = PACKAGE_ID
    p42.SOURCE_ID = SOURCE_ID
    p42.SOURCE_ZIP = SOURCE_ZIP
    p42.SOURCE_BYTES = SOURCE_BYTES
    p42.SOURCE_SHA256 = SOURCE_SHA256
    p42.EPOCH = EPOCH
    p42.RULE_IDS = RULE_IDS
    p42.BASE = BASE
    p42.PREBUILD = PREBUILD
    p42.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    p42.configure()


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
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def source_member(relative: str) -> bytes:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        return archive.read(f"{SOURCE_ID}/{relative}")


def source_text(relative: str) -> str:
    return source_member(relative).decode("utf-8").replace(SOURCE_ID, PACKAGE_ID)


def sha(path: Path) -> str:
    return p42.base.sha256(path)


def prepare_source_bound() -> dict[str, Path]:
    catalog = PREBUILD / "source_bound_probe_catalog.json"
    plan = PREBUILD / "source_bound_probe_plan.json"
    catalog.write_text(source_text("diagnostics/source_bound_probe_catalog.json"), encoding="utf-8")
    plan.write_text(source_text("diagnostics/source_bound_probe_plan.json"), encoding="utf-8")
    generated = PREBUILD / "source_bound_generated"
    report = PREBUILD / "source_bound_generation_report.json"
    cheap = PREBUILD / "source_bound_observer_generation.json"
    result = command(
        [
            PYTHON,
            str(SOURCE_BOUND_TOOL),
            "materialize",
            "--catalog",
            str(catalog),
            "--plan",
            str(plan),
            "--output-dir",
            str(generated),
            "--report",
            str(report),
            "--cheap-check-output",
            str(cheap),
        ]
    )
    if result.returncode:
        raise BuildError(f"source-bound materialization failed: {result.stderr}\n{result.stdout}")
    value = json.loads(cheap.read_text(encoding="utf-8"))
    if value.get("pass") is not True or value.get("errors") != []:
        raise BuildError("fresh source-bound generation did not pass")
    return {
        "catalog": catalog,
        "plan": plan,
        "generated": generated,
        "report": report,
        "cheap": cheap,
    }


def probe_catalog(source_bound: dict[str, Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    binding = json.loads(
        (source_bound["generated"] / "source_bound_probe_binding.json").read_text(
            encoding="utf-8"
        )
    )
    wanted = [
        ("mse4_memag_output_accept", "mse_mem_ag_tag_valid", 1, "mse4_memag_valid"),
        ("mse4_memag_output_accept", "mse_mem_ag_bp_pre", 1, "mse4_memag_bp_pre"),
        ("mse4_descriptor_accept", "wr_data_chl_req_valid", 1, "mse4_descriptor_valid"),
        ("mse4_descriptor_accept", "wr_data_chl_req_ready", 1, "mse4_descriptor_ready"),
        ("mse4_buffer_data_accept", "buf2mse_rvalid", 1, "mse4_buffer_rvalid"),
        ("mse4_buffer_data_accept", "wr_data_chl_ready", 1, "mse4_buffer_ready"),
        ("mse4_wdata_output_accept", "mse2mem_wdata_valid", 2, "mse4_wdata_valid"),
        ("mse4_wdata_output_accept", "mem2mse_wdata_ready", 2, "mse4_wdata_ready"),
        ("mse4_slice_finish", "slice_cmpt_finish", 1, "mse4_slice_finish"),
    ]
    by_boundary = {row["boundary_id"]: row for row in binding["boundaries"]}
    rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    parent: str | None = None
    for boundary_id, name, width, candidate_id in wanted:
        boundary = by_boundary[boundary_id]
        instance = boundary["instance_scope"]["expected_instances"]
        if len(instance) != 1:
            raise BuildError(f"portable candidate boundary is not exact: {boundary_id}")
        boundary_parent = instance[0].rsplit(".codex_probe_", 1)[0]
        parent = boundary_parent if parent is None else parent
        if parent != boundary_parent:
            raise BuildError("portable MSE4 candidate boundaries do not share one exact instance")
        matches = [row for row in boundary["symbol_bindings"] if row["name"] == name]
        if len(matches) != 1 or matches[0]["width_bits"] != width:
            raise BuildError(f"portable candidate source binding changed: {boundary_id}/{name}")
        reference = f"{name} [1:0]" if width == 2 else name
        rows.append(
            {
                "candidate_id": candidate_id,
                "hierarchical_path": f"{boundary_parent}.{reference}",
                "width": width,
            }
        )
        source_rows.append(
            {
                "candidate_id": candidate_id,
                "boundary_id": boundary_id,
                "exact_parent_instance": boundary_parent,
                "symbol_binding": matches[0],
            }
        )
    return rows, {
        "schema": "conv-native-portable-query-source-report-v1",
        "package_id": PACKAGE_ID,
        "source_package_id": SOURCE_ID,
        "scope": "tb_NDP_Top_new_phy",
        "depth": 0,
        "catalog_complete": True,
        "candidate_exact_set": source_rows,
        "source_bound_generation_report": {
            "path": "diagnostics/source_bound_generation_report.json",
            "bytes": source_bound["report"].stat().st_size,
            "sha256": sha(source_bound["report"]),
        },
        "source_bound_binding": {
            "path": "diagnostics/source_bound_probe_binding.json",
            "bytes": (source_bound["generated"] / "source_bound_probe_binding.json").stat().st_size,
            "sha256": sha(source_bound["generated"] / "source_bound_probe_binding.json"),
        },
        "capture": {
            "source": "same-attempt direct VCD",
            "ordered_every_transition": True,
            "no_byte_limit": True,
            "no_file_limit": True,
            "no_event_limit": True,
            "no_time_window": True,
            "sampling": False,
            "truncation": False,
        },
        "claim_boundary": (
            "Static source-bound candidate identity only; actual compile/sim/dump/runtime "
            "identities are bound by the same-attempt portable status receipt."
        ),
    }


def portable_profile(source_bound: dict[str, Path]) -> tuple[Path, Path, Path]:
    catalog, source_report_value = probe_catalog(source_bound)
    source_report = PREBUILD / "portable_query_source_report.json"
    write_json(source_report, source_report_value)
    profile = {
        "schema": "server-waveform-portable-query-profile-v1",
        "rule_id": RULE_ID,
        "activation": "required_next_fresh",
        "activation_epoch": EPOCH,
        "raw_vpd": {
            "authoritative": True,
            "existing_dump_vcd_semantics": "VPD",
            "make_arguments": {"DUMP_VCD": "1", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
            "hard_limit_bytes": None,
            "truncation": False,
            "sampling": False,
            "size_based_deletion": False,
        },
        "portable_vcd": {
            "format": "VCD",
            "ucli_type": "VCD",
            "make_argument": {"DUMP_PORTABLE_VCD": "1"},
            "first_fresh_required": True,
            "source_bound_scope": {
                "top": "tb_NDP_Top_new_phy",
                "depth": 0,
                "source_receipt_sha256": sha(source_report),
            },
            "hard_limit_bytes": None,
            "truncation": False,
            "sampling": False,
            "size_based_deletion": False,
        },
        "signal_query": {
            "format": "REGISTERED_EVENT_ROWS",
            "custom_free_form_text": False,
            "hard_limit_bytes": None,
            "hard_limit_events": None,
            "sampling": False,
            "truncation": False,
            "ordered_every_transition": True,
        },
        "probe_catalog": catalog,
        "probe_catalog_sha256": hashlib.sha256(query_adapter.canonical(catalog)).hexdigest(),
        "failure_semantics": {
            "return_must_publish": True,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "preserve": ["raw_vpd", "compile_core", "sim_core", "signal_core", "return_core"],
        },
        "claim_boundary": (
            "p42-equivalent native MSE4 causal-chain portability only; no dynamic DUT claim."
        ),
    }
    profile_path = PREBUILD / "server_waveform_portable_profile.json"
    write_json(profile_path, profile)
    errors = portable.validate_profile(profile)
    if errors:
        raise BuildError(f"portable profile invalid: {errors}")
    attempt_root = f"install/codex_runs/{PACKAGE_ID}/a0"
    dump_text = portable.render_dump_tcl(
        profile, attempt_root, "CODEX_UNBOUNDED", "DIRECT_VCD_AND_QUERY"
    ).replace("run CODEX_UNBOUNDED\n", "run\n")
    dump_path = PREBUILD / "server_waveform_portable_dump.tcl"
    dump_path.write_text(dump_text, encoding="utf-8", newline="\n")
    return profile_path, dump_path, source_report


def patch_compile_helper(text: str) -> str:
    old = '''        "make", "-f", args.makefile.name, "compile", "DUMP_VCD=0", "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0", f"RUN_DIR={args.run_dir}",'''
    new = '''        "make", "-f", args.makefile.name, "compile", "DUMP_VCD=1", "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0", "DUMP_PORTABLE_VCD=1", f"RUN_DIR={args.run_dir}",'''
    if text.count(old) != 1:
        raise BuildError("compile-core actual argv source shape changed")
    text = text.replace(old, new)
    old_field = '''        "waveforms_explicitly_disabled": ["DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],'''
    new_field = '''        "waveforms_explicitly_disabled": [],
        "waveform_make_arguments": ["DUMP_VCD=1", "DUMP_FSDB=0", "TB_DUMP_FSDB=0", "DUMP_PORTABLE_VCD=1"],'''
    if text.count(old_field) != 1:
        raise BuildError("compile-core waveform receipt shape changed")
    return text.replace(old_field, new_field)


def patch_runner(text: str) -> str:
    declaration = '''waveform_collection_status=125
portable_shared_helper="$package_root/package_tools/server_waveform_portable_query.py"
portable_family_helper="$package_root/package_tools/conv_native_portable_vcd_query.py"
portable_profile="$package_root/contracts/server_waveform_portable_profile.json"
portable_dump_control="$package_root/contracts/server_waveform_portable_dump.tcl"
portable_source_report="$package_root/diagnostics/portable_query_source_report.json"
portable_collection_status=125'''
    if text.count("waveform_collection_status=125") != 2:
        raise BuildError("runner waveform declaration count changed")
    text = text.replace("waveform_collection_status=125", declaration)

    collect_marker = '''    waveform_collection_status=$?
    export CODEX_PACKAGE_ROOT="$package_root"'''
    collect_replacement = '''    waveform_collection_status=$?
    portable_collection_status=0
    python3 "$portable_family_helper" collect --profile "$portable_profile" --shared-helper "$portable_shared_helper" --asset-root "$server_root" --attempt-root "$run_root" --output-dir "$run_root/evidence/portable" --source-report "$portable_source_report" --vcd "$run_root/run/sim_results/wave.vcd" --actual-compile-argv "$compile_argv_json" --actual-sim-argv "$run_root/c0/actual_sim_argv.json" --dump-tcl "$waveform_runtime_dump_control" --raw-receipt "$run_root/evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json" --package-id "$package_identity" --execution-id "$return_tag" --attempt-id "$attempt" --exit-kind "$waveform_exit_kind" || portable_collection_status=$?
    export CODEX_PACKAGE_ROOT="$package_root"'''
    if text.count(collect_marker) != 1:
        raise BuildError("runner waveform collector insertion point changed")
    text = text.replace(collect_marker, collect_replacement)

    compile_old = 'compile DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$compile_root"'
    compile_new = 'compile DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 DUMP_PORTABLE_VCD=1 RUN_DIR="$compile_root"'
    if text.count(compile_old) != 1:
        raise BuildError("runner production compile argv changed")
    text = text.replace(compile_old, compile_new)

    dump_old = '''waveform_runtime_dump_control="$compile_root/sim_results/codex_waveform_full.tcl"
sed "s|\\$CODEX_WAVE_PATH|$compile_root/sim_results/wave.vpd|g" "$waveform_dump_control" > "$waveform_runtime_dump_control" || runner_fail 8 "mandatory waveform dump control materialization failed"
grep -F "dump -file $compile_root/sim_results/wave.vpd -type VPD" "$waveform_runtime_dump_control" >/dev/null || runner_fail 8 "mandatory VPD path binding failed"
grep -F "dump -add tb_NDP_Top_new_phy -depth 0 -aggregates" "$waveform_runtime_dump_control" >/dev/null || runner_fail 8 "full-hierarchy VPD scope binding failed"'''
    attempt_root = f"install/codex_runs/{PACKAGE_ID}/a0"
    dump_new = f'''mkdir -p "$run_root/run/sim_results" || runner_fail 8 "portable waveform runtime root cannot be created"
waveform_runtime_dump_control="$run_root/run/sim_results/codex_waveform_portable.tcl"
cp -- "$portable_dump_control" "$waveform_runtime_dump_control" || runner_fail 8 "portable waveform dump control materialization failed"
grep -F "dump -file {attempt_root}/run/sim_results/wave.vpd -type VPD" "$waveform_runtime_dump_control" >/dev/null || runner_fail 8 "authoritative VPD path binding failed"
grep -F "dump -file {attempt_root}/run/sim_results/wave.vcd -type VCD" "$waveform_runtime_dump_control" >/dev/null || runner_fail 8 "direct portable VCD path binding failed"
[ "$(grep -Fc "dump -add tb_NDP_Top_new_phy -depth 0 -aggregates" "$waveform_runtime_dump_control")" -eq 2 ] || runner_fail 8 "dual full-hierarchy scope binding failed"'''
    if text.count(dump_old) != 1:
        raise BuildError("runner dump-control block changed")
    text = text.replace(dump_old, dump_new)

    sim_text_old = '"DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 $simv'
    sim_text_new = '"DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 DUMP_PORTABLE_VCD=1 timeout --foreground --signal=TERM --kill-after=30s 12h $simv'
    if text.count(sim_text_old) != 1:
        raise BuildError("runner simulator argv receipt changed")
    text = text.replace(sim_text_old, sim_text_new)
    argv_marker = ''' > "$run_root/c0/simulator_argv.txt"
preflight_stage=PRODUCTION_SIMULATION'''
    argv_replacement = ''' > "$run_root/c0/simulator_argv.txt"
python3 "$portable_family_helper" argv-json --text "$run_root/c0/simulator_argv.txt" --output "$run_root/c0/actual_sim_argv.json" || runner_fail 8 "actual simulator argv JSON capture failed"
preflight_stage=PRODUCTION_SIMULATION'''
    if text.count(argv_marker) != 1:
        raise BuildError("runner simulator argv JSON insertion point changed")
    text = text.replace(argv_marker, argv_replacement)

    sim_exec_old = "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 timeout --foreground"
    sim_exec_new = "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 DUMP_PORTABLE_VCD=1 timeout --foreground"
    if text.count(sim_exec_old) != 1:
        raise BuildError("runner simulator execution prefix changed")
    text = text.replace(sim_exec_old, sim_exec_new)
    if "DUMP_VCD=0" in text:
        raise BuildError("runner disables authoritative VPD")
    return text


def prepare_prebuild() -> dict[str, Any]:
    if PREBUILD.exists():
        raise BuildError("refusing to overwrite p43 prebuild assets")
    PREBUILD.mkdir(parents=True)
    source_bound = prepare_source_bound()
    portable_profile_path, portable_dump, portable_source_report = portable_profile(source_bound)

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
    shutil.copyfile(PORTABLE_TOOL, PREBUILD / "server_waveform_portable_query.py")
    shutil.copyfile(LOCAL_ANALYSIS_TOOL, PREBUILD / "server_waveform_local_analysis.py")
    shutil.copyfile(QUERY_ADAPTER, PREBUILD / "conv_native_portable_vcd_query.py")
    for relative, target in (
        ("package_tools/fixed_simresult_publisher.py", "fixed_simresult_publisher.py"),
        ("tb_probe/native_return_observer.svh", "native_return_observer.svh"),
    ):
        (PREBUILD / target).write_text(source_text(relative), encoding="utf-8", newline="\n")

    waveform_plan = PREBUILD / "server_waveform_mandatory_plan.json"
    plan_value = json.loads(source_text("contracts/server_waveform_mandatory_plan.json"))
    plan_value["package_id"] = PACKAGE_ID
    plan_value["dump"]["runtime_search_roots"] = ["run/sim_results"]
    plan_value["claim_boundary"] = (
        "p42-equivalent diagnostic with authoritative full-hierarchy unbounded VPD; "
        "portable VCD/query is additive and cannot cancel the raw return."
    )
    write_json(waveform_plan, plan_value)
    mandatory_dump = PREBUILD / "server_waveform_dump.tcl"
    rendered = command(
        [PYTHON, str(WAVEFORM_TOOL), "render-dump-control", "--plan", str(waveform_plan), "--output", str(mandatory_dump)]
    )
    if rendered.returncode:
        raise BuildError(f"mandatory waveform dump render failed: {rendered.stderr}")

    contract = PREBUILD / "server_runner_return_resilience_contract.json"
    write_json(contract, p42.p41.runner_contract(runner))
    validation = PREBUILD / "runner_return_resilience.validation.json"
    checked = command(
        [PYTHON, str(RUNNER_VALIDATOR), "validate-tree", "--root", str(PREBUILD), "--contract", str(contract), "--output", str(validation)]
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
                "path": validation.relative_to(ROOT).as_posix(),
                "bytes": validation.stat().st_size,
                "sha256": sha(validation),
            },
        },
    )

    source_spec = ROOT / "outputs/conv_native_four_lane_0ccae916_p42_vecjoinfix/server_package_build_spec_v2.json"
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
    input_rows = [
        (SOURCE_ZIP, "package_identity"),
        (runner, "runner"),
        (contract, "return_core_contract"),
        (compile_helper, "return_collector"),
        (PREBUILD / "fixed_simresult_publisher.py", "return_collector"),
        (PREBUILD / "server_post_sim_return.py", "return_collector"),
        (PREBUILD / "server_waveform_mandatory_return.py", "waveform"),
        (PREBUILD / "server_waveform_portable_query.py", "waveform"),
        (PREBUILD / "conv_native_portable_vcd_query.py", "waveform"),
        (waveform_plan, "waveform"),
        (mandatory_dump, "waveform"),
        (portable_profile_path, "waveform"),
        (portable_dump, "waveform"),
        (portable_source_report, "probe_catalog"),
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
        for path, surface in input_rows
    ]
    fixtures = {
        "core_identity_bootstrap": ROOT / "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json",
        "storage_rotation": ROOT / "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json",
        "intermediate_report_format": ROOT / "fixtures/server_package_pipeline_v1/cheap/intermediate_report_format.json",
    }
    spec["cheap_check_reports"] = [
        {"gate_id": gate_id, "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}
        for gate_id, path in fixtures.items()
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
    ]
    validators = spec.setdefault("validators", {})
    validators["runner_return_resilience"] = {
        "validator_sha256": sha(RUNNER_VALIDATOR),
        "fixture_sha256": sha(runner_report),
    }
    for gate_id in ("source_bound_observer_generation", "source_bound_final_zip", "package_local_hdl", "diagnostic_semantics"):
        validators[gate_id] = {
            "validator_sha256": sha(SOURCE_BOUND_TOOL),
            "fixture_sha256": sha(source_bound["plan"]),
        }
    for gate_id in ("post_sim_return_core", "return_result_contract"):
        validators[gate_id] = {
            "validator_sha256": sha(POST_SIM_TOOL),
            "fixture_sha256": sha(waveform_plan),
        }
    validators["waveform_observation_final_zip"] = {
        "validator_sha256": sha(WAVEFORM_TOOL),
        "fixture_sha256": sha(waveform_plan),
    }
    validators["waveform_portable_local_decodability"] = {
        "validator_sha256": sha(PORTABLE_TOOL),
        "fixture_sha256": sha(portable_profile_path),
    }
    validators["first_fresh_extra_audit"] = {
        "validator_sha256": sha(FIRST_FRESH_TOOL),
        "fixture_sha256": sha(portable_source_report),
    }
    spec_path = BASE / "server_package_build_spec_v2.json"
    write_json(spec_path, spec)
    build_profile = BASE / "server_package_build_profile_v2.json"
    result = command(
        [PYTHON, str(PIPELINE), "prepare", "--spec", str(spec_path), "--registry", str(GATE_REGISTRY), "--workspace-root", str(ROOT), "--output", str(build_profile)]
    )
    if result.returncode:
        raise BuildError(f"shared aggregate failed: {result.stderr}\n{result.stdout}")
    aggregate = json.loads(build_profile.read_text(encoding="utf-8"))
    if aggregate.get("contract_valid") is not True or aggregate.get("preflight", {}).get("errors") != []:
        raise BuildError(f"shared aggregate did not close: {aggregate.get('preflight')}")
    if aggregate.get("execution_contract", {}).get("prebuild_aggregate_top_level_invocations") != 1:
        raise BuildError("shared prebuild aggregate invocation count differs")
    return {
        "runner": runner,
        "compile_helper": compile_helper,
        "contract": contract,
        "runner_report": runner_report,
        "waveform_plan": waveform_plan,
        "mandatory_dump": mandatory_dump,
        "portable_profile": portable_profile_path,
        "portable_dump": portable_dump,
        "portable_source_report": portable_source_report,
        "source_bound": source_bound,
        "spec": spec_path,
        "profile": build_profile,
    }


def add_portable_return_entries(request: dict[str, Any]) -> None:
    additions = [
        ("runs/c0/actual_sim_argv.json", "c0/actual_sim_argv.json", True),
        ("runs/run/codex_waveform_portable.tcl", "run/sim_results/codex_waveform_portable.tcl", True),
        ("waveforms/run/sim_results/wave.vcd", "run/sim_results/wave.vcd", False),
        ("evidence/portable/PORTABLE_QUERY_SOURCE_REPORT.json", "evidence/portable/PORTABLE_QUERY_SOURCE_REPORT.json", True),
        ("evidence/portable/SIGNAL_QUERY_RECEIPT.json", "evidence/portable/SIGNAL_QUERY_RECEIPT.json", False),
        ("evidence/portable/PORTABLE_RETURN_ALLOWLIST.json", "evidence/portable/PORTABLE_RETURN_ALLOWLIST.json", True),
        ("evidence/portable/PORTABLE_RUNTIME_REQUEST.json", "evidence/portable/PORTABLE_RUNTIME_REQUEST.json", True),
        ("evidence/portable/PORTABLE_WAVEFORM_RUNTIME_RECEIPT.json", "evidence/portable/PORTABLE_WAVEFORM_RUNTIME_RECEIPT.json", False),
        ("evidence/portable/PORTABLE_FIRST_FRESH_STATUS.json", "evidence/portable/PORTABLE_FIRST_FRESH_STATUS.json", True),
    ]
    archives = {row["archive"] for row in request["core_entries"]}
    for archive, source, required in additions:
        if archive in archives:
            raise BuildError(f"portable return archive collision: {archive}")
        request["core_entries"].append(
            {"archive": archive, "required": required, "source": source, "source_root": "attempt"}
        )


def patch_layout(package: Path) -> None:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value.update(
        {
            "package_id": PACKAGE_ID,
            "install_name": PACKAGE_ID,
            "claim_boundary": (
                "p42-equivalent package; the compile root stays frozen while only waveform "
                "artifacts use the canonical attempt/run path required by the portable contract."
            ),
        }
    )
    value["runtime_roots"]["compile_root"] = f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/compile"
    additions = [
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/c0/actual_sim_argv.json",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/run/sim_results/codex_waveform_portable.tcl",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/run/sim_results/wave.vpd",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/run/sim_results/wave.vcd",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/portable/PORTABLE_QUERY_SOURCE_REPORT.json",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/portable/SIGNAL_QUERY_RECEIPT.json",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/portable/PORTABLE_WAVEFORM_RUNTIME_RECEIPT.json",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/portable/PORTABLE_FIRST_FRESH_STATUS.json",
    ]
    current = value["path_budget"]["additional_projected_paths"]
    current.extend(item for item in additions if item not in current)
    write_json(path, value)


def patch_manifest(package: Path, assets: dict[str, Any]) -> None:
    # Reuse the established path-budget and file-table materialization, then
    # replace the p42-specific lifecycle statement with the exact p43 delta.
    p42.patch_manifest(package, assets)
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value.update(
        {
            "schema": "conv-native-four-lane-0ccae916-p43-portablevq-package-v1",
            "package_identity": PACKAGE_ID,
            "install_name": PACKAGE_ID,
            "workload_install_name": PACKAGE_ID,
            "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
            "return_name": f"{PACKAGE_ID}_<execution_id>_return.zip",
            "status": "PACKAGE_READY_NOT_RUN",
            "candidate_release": False,
        }
    )
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "pending_rotates_to_tested_only_via_family_storage_manager",
        "reason": (
            "p42 already carries the corrected two-bit valid/ready overlap diagnostic; "
            "p43 adds only the activated first-fresh portable VCD/query/runtime-return surfaces."
        ),
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
    }
    value["repair_delta"] = {
        "changed_surfaces": [
            "package_identity",
            "runner_waveform_arguments",
            "portable_dump_control",
            "portable_vcd_return",
            "registered_query_receipt",
            "portable_runtime_receipt",
            "compile_sim_argv_receipts",
            "runtime_path_binding",
            "storage",
        ],
        "source_p42_vector_handshake_repair_preserved": True,
        "target_diagnostic_modified": False,
        "functional_rtl_modified": False,
        "config_numeric_workload_golden_modified": False,
    }
    value["portable_waveform_query"] = {
        "rule_id": RULE_ID,
        "activation_epoch": EPOCH,
        "first_fresh_for_profile": True,
        "capture_mode": "DIRECT_VCD_AND_QUERY",
        "profile": "contracts/server_waveform_portable_profile.json",
        "dump_control": "contracts/server_waveform_portable_dump.tcl",
        "shared_helper": "package_tools/server_waveform_portable_query.py",
        "family_adapter": "package_tools/conv_native_portable_vcd_query.py",
        "raw_vpd_authoritative": True,
        "direct_vcd_required": True,
        "registered_complete_query_required": True,
        "no_byte_limit": True,
        "no_file_limit": True,
        "no_event_limit": True,
        "no_time_window": True,
        "sampling": False,
        "truncation": False,
        "failure_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "return_must_publish": True,
    }
    matrix = value.setdefault("release_gate_matrix", {})
    matrix["waveform_portable_local_decodability"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": None,
        "semantic_version": "1",
    }
    matrix["first_fresh_extra_audit"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": None,
        "epoch_id": EPOCH,
    }
    receipts = value.setdefault("rule_receipts", [])
    existing = {row["path"] for row in receipts}
    for relative in (
        "contracts/server_waveform_portable_query_profile_v1.json",
        "schemas/server_waveform_portable_profile_v1.schema.json",
        "schemas/server_waveform_signal_query_receipt_v1.schema.json",
        "schemas/server_waveform_portable_runtime_receipt_v1.schema.json",
        ".agents/task_records/20260812_portable_vcd_query_profile_v1_mainline_activation.md",
    ):
        if relative not in existing:
            source = ROOT / relative
            receipts.append({"path": relative, "bytes": source.stat().st_size, "sha256": sha(source)})
    value["rule_receipts_current_match"] = True
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
        "diagnostics/live_fixtures/arm_known_event.log",
    ]
    normalized: dict[str, bool] = {}
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        prefix = f"{SOURCE_ID}/"
        for relative in protected:
            current = (package / relative).read_bytes().replace(PACKAGE_ID.encode(), SOURCE_ID.encode())
            source = archive.read(prefix + relative)
            if relative == "diagnostics/source_bound_probe_catalog.json":
                # The fresh generator pretty-prints the same catalog.  Compare
                # its parsed contract, not incidental JSON whitespace.
                normalized[relative] = json.loads(current) == json.loads(source)
                continue
            if relative == "diagnostics/source_bound_probe_plan.json":
                # Package identity is provenance, while every diagnostic
                # boundary/candidate/predicate must remain semantically equal.
                normalized[relative] = json.loads(current) == json.loads(source)
                continue
            if relative == "tb_probe/source_bound_causal_observer.svh":
                marker = re.compile(rb"plan_semantic_sha256=[0-9a-f]{64}")
                current = marker.sub(b"plan_semantic_sha256=<IDENTITY_BOUND>", current)
                source = marker.sub(b"plan_semantic_sha256=<IDENTITY_BOUND>", source)
            normalized[relative] = current == source
        workload = sorted(
            name[len(prefix) :]
            for name in archive.namelist()
            if name.startswith(prefix + "workload/runtime/") and not name.endswith("/")
        )
        workload_equal = all(
            (package / relative).read_bytes().replace(PACKAGE_ID.encode(), SOURCE_ID.encode())
            == archive.read(prefix + relative)
            for relative in workload
        )
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    profile = json.loads((package / "contracts/server_waveform_portable_profile.json").read_text(encoding="utf-8"))
    result = {
        "source_p42_zip_bytes": SOURCE_BYTES,
        "source_p42_zip_sha256": SOURCE_SHA256,
        "workload_member_count": len(workload),
        "workload_identity_normalized_byte_equal": workload_equal,
        "protected_diagnostic_identity_normalized_equal": normalized,
        "p42_vector_handshake_and_target_diagnostic_frozen": all(normalized.values()),
        "config_numeric_workload_golden_functional_rtl_frozen": workload_equal,
        "raw_vpd_preserved": "DUMP_VCD=1" in runner and "DUMP_VCD=0" not in runner,
        "direct_vcd_enabled": "DUMP_PORTABLE_VCD=1" in runner,
        "portable_profile_valid": portable.validate_profile(profile) == [],
        "functional_rtl_modified": False,
        "target_diagnostic_modified": False,
    }
    if not all(
        (
            workload_equal,
            all(normalized.values()),
            result["raw_vpd_preserved"],
            result["direct_vcd_enabled"],
            result["portable_profile_valid"],
        )
    ):
        raise BuildError(f"p43 frozen-surface audit failed: {result}")
    return result


def materialize(destination: Path, assets: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    package = p42.base.safe_extract(destination)
    p42.base.reidentity(package)
    shutil.copyfile(assets["runner"], package / "PREPARE_AND_RUN.sh")
    shutil.copyfile(assets["compile_helper"], package / "package_tools/compile_core_evidence.py")
    shutil.copyfile(PREBUILD / "fixed_simresult_publisher.py", package / "package_tools/fixed_simresult_publisher.py")
    shutil.copyfile(POST_SIM_TOOL, package / "package_tools/server_post_sim_return.py")
    shutil.copyfile(WAVEFORM_TOOL, package / "package_tools/server_waveform_mandatory_return.py")
    shutil.copyfile(PORTABLE_TOOL, package / "package_tools/server_waveform_portable_query.py")
    shutil.copyfile(QUERY_ADAPTER, package / "package_tools/conv_native_portable_vcd_query.py")
    tools_dir = package / "tools"
    tools_dir.mkdir(exist_ok=True)
    (tools_dir / "__init__.py").write_text("", encoding="utf-8")
    shutil.copyfile(LOCAL_ANALYSIS_TOOL, tools_dir / "server_waveform_local_analysis.py")
    shutil.copyfile(assets["waveform_plan"], package / "contracts/server_waveform_mandatory_plan.json")
    shutil.copyfile(assets["mandatory_dump"], package / "contracts/server_waveform_dump.tcl")
    shutil.copyfile(assets["portable_profile"], package / "contracts/server_waveform_portable_profile.json")
    shutil.copyfile(assets["portable_dump"], package / "contracts/server_waveform_portable_dump.tcl")
    shutil.copyfile(assets["portable_source_report"], package / "diagnostics/portable_query_source_report.json")
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
    write_json(package / "server_runner_return_resilience_contract.json", p42.p41.runner_contract(package / "PREPARE_AND_RUN.sh"))
    p42.base.refresh_derived_contracts(package)

    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["package_id"] = PACKAGE_ID
    request["waveform_discovery"] = {
        "plan_member": "contracts/server_waveform_mandatory_plan.json",
        "collector_member": "package_tools/server_waveform_mandatory_return.py",
        "runtime_receipt_source": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
        "collect_all_matching": True,
        "required_when_simulation_started": True,
        "no_size_limit": True,
        "manifest_archive_path": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
    }
    add_portable_return_entries(request)
    request["claim_boundary"] = (
        "Frozen p42 MSE4 target plus authoritative raw VPD, same-attempt direct VCD, "
        "and registered complete query receipt. Dynamic result remains unclaimed."
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
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    pointer_value = json.loads(pointer.read_text(encoding="utf-8"))
    pointer_value.update(
        {
            "schema": "conv-native-four-lane-p43-portablevq-pointer-v1",
            "package_identity": PACKAGE_ID,
            "status": "PACKAGE_READY_NOT_RUN",
        }
    )
    write_json(pointer, pointer_value)
    readme = package / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + (
            "\n## p43 first-fresh portable evidence\n\n"
            "This p42-equivalent successor retains authoritative unbounded full-hierarchy VPD and "
            "adds same-attempt direct unbounded VCD plus the registered source-bound MSE4 event/query receipt. "
            "Portable failure is fail-closed as DIAGNOSTIC_EVIDENCE_INCOMPLETE while raw/core return remains mandatory.\n"
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
        raise BuildError("exact p42 source ZIP differs")
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
        raise BuildError("refusing to overwrite p43 build output")
    package, frozen = materialize(output, assets)
    with tempfile.TemporaryDirectory(prefix=".p43_repeat_", dir=ROOT) as temporary:
        _, repeated_frozen = materialize(Path(temporary), assets)
        repeated = Path(temporary) / PACKAGE_ID
        deterministic = p42.base.tree_receipt(package) == p42.base.tree_receipt(repeated)
    if not deterministic or repeated_frozen != frozen:
        raise BuildError("p43 deterministic double staging differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    p42.base.deterministic_zip(package, zip_path)
    digest = sha(zip_path)
    Path(str(zip_path) + ".sha256").write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "conv-native-four-lane-p43-portablevq-build-v1",
        "status": "PACKAGE_BUILT_UPLOAD_HELD_PENDING_EXACT_FINAL_ZIP_GATES",
        "package_identity": PACKAGE_ID,
        "source_p42_zip_sha256": SOURCE_SHA256,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": True,
        "capture_mode": "DIRECT_VCD_AND_QUERY",
        "prebuild_aggregate_top_level_invocations": 1,
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
        "portable_profile": {
            "path": assets["portable_profile"].relative_to(ROOT).as_posix(),
            "bytes": assets["portable_profile"].stat().st_size,
            "sha256": sha(assets["portable_profile"]),
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
