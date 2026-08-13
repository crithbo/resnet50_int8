#!/usr/bin/env python3
"""Build the mandatory-full-VPD successor of the superseded native p40 package."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import build_conv_native_four_lane_0ccae916_p39_compilecore_package as base


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p41_vpdfull"
SOURCE_ID = "r5_n4_0cc_p40_dhpubfix"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/superseded"
    / "conv_native_four_lane"
    / SOURCE_ID
    / f"{SOURCE_ID}.zip"
)
SOURCE_BYTES = 5_973_269
SOURCE_SHA256 = "64c47086bcc1e9dade1b1c9e9fb912c186f49a0ab223c816996e08e9ad86b39f"
EPOCH = "waveform-mandatory-v2-01ca6d7cd4a4a270"
RULE_IDS = [
    "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001",
    "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
    "CDA-SERVER-RUNNER-SET-U-DEFINITION-BEFORE-USE-001",
    "CDA-SERVER-COMPILEFAIL-CORE-RETURN-ROOT-CAUSE-001",
    "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
]
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p41_vpdfull"
PREBUILD = BASE / "prebuild"
DEFAULT_OUTPUT = BASE / "build"
PIPELINE = ROOT / "tools/server_package_pipeline.py"
GATE_REGISTRY = ROOT / "contracts/server_package_build_gate_registry_v1.json"
RUNNER_VALIDATOR = ROOT / "tools/validate_server_runner_return_resilience.py"
SOURCE_BOUND_TOOL = ROOT / "tools/generate_server_source_bound_observer.py"
POST_SIM_TOOL = ROOT / "tools/server_post_sim_return.py"
WAVEFORM_TOOL = ROOT / "tools/server_waveform_mandatory_return.py"
FIRST_FRESH_TOOL = ROOT / "tools/validate_server_first_fresh_extra_audit.py"
PYTHON = sys.executable


class BuildError(RuntimeError):
    pass


def configure_base() -> None:
    base.PACKAGE_ID = PACKAGE_ID
    base.SOURCE_ID = SOURCE_ID
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_BYTES = SOURCE_BYTES
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.EPOCH = EPOCH
    base.RULE_IDS = RULE_IDS
    base.BASE = BASE
    base.PREBUILD = PREBUILD
    base.DEFAULT_OUTPUT = DEFAULT_OUTPUT


def source_member(relative: str) -> bytes:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        return archive.read(f"{SOURCE_ID}/{relative}")


def source_text(relative: str) -> str:
    return source_member(relative).decode("utf-8").replace(SOURCE_ID, PACKAGE_ID)


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
    base.write_json(path, value)


def waveform_plan() -> dict[str, Any]:
    return {
        "schema": "server-waveform-mandatory-plan-v2",
        "package_id": PACKAGE_ID,
        "family": "conv_native_four_lane",
        "dump": {
            "format": "VPD",
            "make_arguments": {
                "DUMP_VCD": "1",
                "DUMP_FSDB": "0",
                "TB_DUMP_FSDB": "0",
            },
            "tb_top": "tb_NDP_Top_new_phy",
            "hierarchy_depth": 0,
            "scope_mode": "FULL_HIERARCHY",
            "included_scopes": ["tb_NDP_Top_new_phy"],
            "excluded_scopes": [],
            "runtime_search_roots": ["compile/sim_results"],
            "waveform_name_patterns": ["wave.vpd", "wave.vpd.*"],
        },
        "return_policy": {
            "required_when_simulation_started": True,
            "compile_not_started_omission_allowed": True,
            "collect_all_matching": True,
            "archive_prefix": "waveforms",
            "manifest_archive_path": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
            "hard_limit_bytes": None,
            "truncation_allowed": False,
            "sampling_allowed": False,
            "size_based_deletion_allowed": False,
        },
        "integration": {
            "plan_member": "contracts/server_waveform_mandatory_plan.json",
            "runner_member": "PREPARE_AND_RUN.sh",
            "return_request_member": "contracts/server_post_sim_return_request.json",
            "dump_control_member": "contracts/server_waveform_dump.tcl",
            "tool_member": "package_tools/server_waveform_mandatory_return.py",
        },
        "claim_boundary": (
            "Full-hierarchy unbounded VPD capture for the frozen p40-equivalent native Conv "
            "diagnostic; waveform evidence does not claim natural terminal, formal D, E4 or E5."
        ),
    }


def render_runner() -> str:
    runner = source_text("PREPARE_AND_RUN.sh")
    anchor = 'post_sim_request="$package_root/contracts/server_post_sim_return_request.json"\n'
    addition = anchor + (
        'waveform_helper="$package_root/package_tools/server_waveform_mandatory_return.py"\n'
        'waveform_plan="$package_root/contracts/server_waveform_mandatory_plan.json"\n'
        'waveform_dump_control="$package_root/contracts/server_waveform_dump.tcl"\n'
        'waveform_runtime_dump_control=""\n'
        'waveform_exit_kind="SIMULATION_NOT_STARTED"\n'
        'waveform_collection_status=125\n'
    )
    if runner.count(anchor) != 2:
        raise BuildError("p40 post-sim request binding count changed")
    runner = runner.replace(anchor, addition)

    old_tools = "for tool in python3 timeout make; do"
    if runner.count(old_tools) != 1:
        raise BuildError("p40 required-tool preflight changed")
    runner = runner.replace(old_tools, "for tool in python3 timeout make sed; do", 1)

    old_compile = (
        "timeout --foreground --signal=TERM --kill-after=30s 2h make -f "
        "Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0"
    )
    new_compile = old_compile.replace("DUMP_VCD=0", "DUMP_VCD=1")
    if runner.count(old_compile) != 1:
        raise BuildError("p40 production compile command changed")
    runner = runner.replace(old_compile, new_compile, 1)

    simv_anchor = 'simv="$compile_root/sim_results/simv"\n'
    runtime_dump = simv_anchor + r'''waveform_runtime_dump_control="$compile_root/sim_results/codex_waveform_full.tcl"
sed "s|\$CODEX_WAVE_PATH|$compile_root/sim_results/wave.vpd|g" "$waveform_dump_control" > "$waveform_runtime_dump_control" || runner_fail 8 "mandatory waveform dump control materialization failed"
grep -F "dump -file $compile_root/sim_results/wave.vpd -type VPD" "$waveform_runtime_dump_control" >/dev/null || runner_fail 8 "mandatory VPD path binding failed"
grep -F "dump -add tb_NDP_Top_new_phy -depth 0 -aggregates" "$waveform_runtime_dump_control" >/dev/null || runner_fail 8 "full-hierarchy VPD scope binding failed"
'''
    if runner.count(simv_anchor) != 1:
        raise BuildError("p40 simv binding changed")
    runner = runner.replace(simv_anchor, runtime_dump, 1)

    printed_prefix = 'printf \'%s\\n\' "$simv -l $run_root/c0/sim.log '
    printed_replacement = (
        'printf \'%s\\n\' "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 '
        '$simv -l $run_root/c0/sim.log -ucli -i $waveform_runtime_dump_control '
    )
    if runner.count(printed_prefix) != 1:
        raise BuildError("p40 simulator argv receipt changed")
    runner = runner.replace(printed_prefix, printed_replacement, 1)

    actual_prefix = (
        'timeout --foreground --signal=TERM --kill-after=30s 12h "$simv" '
        '-l "$run_root/c0/sim.log" '
    )
    actual_replacement = (
        'DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 '
        'timeout --foreground --signal=TERM --kill-after=30s 12h "$simv" '
        '-l "$run_root/c0/sim.log" -ucli -i "$waveform_runtime_dump_control" '
    )
    if runner.count(actual_prefix) != 1:
        raise BuildError("p40 simulator launch changed")
    runner = runner.replace(actual_prefix, actual_replacement, 1)

    export_anchor = '    export CODEX_PACKAGE_ROOT="$package_root"\n'
    collect = r'''    case "$signal_status" in
      HUP|INT|TERM) waveform_exit_kind="$signal_status" ;;
      *)
        if [ "$run_status" -eq 124 ]; then
          waveform_exit_kind=TIMEOUT
        elif [ "$run_status" -eq 0 ] && [ "$natural_terminal" = true ]; then
          waveform_exit_kind=NATURAL
        else
          waveform_exit_kind=SIMULATION_NONZERO
        fi
        ;;
    esac
    mkdir -p "$run_root/evidence/waveform"
    python3 "$waveform_helper" collect-runtime --plan "$waveform_plan" --attempt-root "$run_root" --execution-id "$return_tag" --simulation-started true --exit-kind "$waveform_exit_kind" --output "$run_root/evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json"
    waveform_collection_status=$?
'''
    if runner.count(export_anchor) != 1:
        raise BuildError("p40 post-sim environment anchor changed")
    runner = runner.replace(export_anchor, collect + export_anchor, 1)

    final_anchor = '    [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] || final="$collection"\n'
    if runner.count(final_anchor) != 1:
        raise BuildError("p40 shared finalizer result anchor changed")
    runner = runner.replace(
        final_anchor,
        final_anchor
        + '    [ "$final" -ne 0 ] || [ "$waveform_collection_status" -eq 0 ] || final="$waveform_collection_status"\n',
        1,
    )

    old_signal = '''on_signal() {
  signal_status="$1"
  [ -z "$sim_pid" ] || kill -TERM "$sim_pid" 2>/dev/null
  finalize "$2"
}
'''
    new_signal = '''on_signal() {
  signal_status="$1"
  if [ -n "$sim_pid" ]; then
    kill -TERM "$sim_pid" 2>/dev/null
    wait "$sim_pid" 2>/dev/null
    run_status=$?
    sim_pid=
  fi
  finalize "$2"
}
'''
    if runner.count(old_signal) != 1:
        raise BuildError("p40 signal handler changed")
    runner = runner.replace(old_signal, new_signal, 1)

    required = (
        "DUMP_VCD=1",
        "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0",
        "server_waveform_mandatory_return.py",
        "collect-runtime",
        "wave.vpd",
        "tb_NDP_Top_new_phy -depth 0 -aggregates",
    )
    if not all(token in runner for token in required):
        raise BuildError("mandatory waveform runner binding is incomplete")
    if "DUMP_VCD=0" in runner:
        raise BuildError("old dump=0 semantics remain in p41 runner")
    return runner


def runner_contract(runner: Path) -> dict[str, Any]:
    value = base.runner_contract(runner)
    value["package_owned_variables"].extend(
        [
            "waveform_helper",
            "waveform_plan",
            "waveform_dump_control",
            "waveform_runtime_dump_control",
            "waveform_exit_kind",
            "waveform_collection_status",
        ]
    )
    return value


def prepare_source_bound() -> dict[str, Path]:
    catalog = PREBUILD / "source_bound_probe_catalog.json"
    plan = PREBUILD / "source_bound_probe_plan.json"
    catalog.write_text(source_text("diagnostics/source_bound_probe_catalog.json"), encoding="utf-8", newline="\n")
    plan.write_text(source_text("diagnostics/source_bound_probe_plan.json"), encoding="utf-8", newline="\n")
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
        raise BuildError(f"fresh source-bound prebuild failed: {result.stderr}\n{result.stdout}")
    value = json.loads(cheap.read_text(encoding="utf-8"))
    if value.get("pass") is not True or value.get("errors") != []:
        raise BuildError("fresh source-bound cheap check did not pass")
    return {"catalog": catalog, "plan": plan, "generated": generated, "report": report, "cheap": cheap}


def prepare_prebuild() -> dict[str, Any]:
    if PREBUILD.exists():
        raise BuildError("refusing to overwrite p41 prebuild assets")
    PREBUILD.mkdir(parents=True)
    runner = PREBUILD / "PREPARE_AND_RUN.sh"
    runner.write_text(render_runner(), encoding="utf-8", newline="\n")
    for relative, target in (
        ("package_tools/compile_core_evidence.py", "compile_core_evidence.py"),
        ("package_tools/fixed_simresult_publisher.py", "fixed_simresult_publisher.py"),
        ("tb_probe/native_return_observer.svh", "native_return_observer.svh"),
    ):
        (PREBUILD / target).write_text(source_text(relative), encoding="utf-8", newline="\n")
    shutil.copyfile(POST_SIM_TOOL, PREBUILD / "server_post_sim_return.py")
    shutil.copyfile(WAVEFORM_TOOL, PREBUILD / "server_waveform_mandatory_return.py")
    plan_path = PREBUILD / "server_waveform_mandatory_plan.json"
    write_json(plan_path, waveform_plan())
    dump_path = PREBUILD / "server_waveform_dump.tcl"
    rendered = command(
        [
            PYTHON,
            str(WAVEFORM_TOOL),
            "render-dump-control",
            "--plan",
            str(plan_path),
            "--output",
            str(dump_path),
        ]
    )
    if rendered.returncode:
        raise BuildError(f"waveform dump-control render failed: {rendered.stderr}")

    contract = PREBUILD / "server_runner_return_resilience_contract.json"
    write_json(contract, runner_contract(runner))
    validation = PREBUILD / "runner_return_resilience.validation.json"
    checked = command(
        [
            PYTHON,
            str(RUNNER_VALIDATOR),
            "validate-tree",
            "--root",
            str(PREBUILD),
            "--contract",
            str(contract),
            "--output",
            str(validation),
        ]
    )
    if checked.returncode:
        raise BuildError(
            f"runner resilience prebuild failed: {checked.stderr}\n{validation.read_text(encoding='utf-8')}"
        )
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
                "sha256": base.sha256(validation),
            },
        },
    )
    source_bound = prepare_source_bound()

    spec = json.loads(
        (BASE.parent / "conv_native_four_lane_0ccae916_p40_dhpubfix/server_package_build_spec_v2.json").read_text(
            encoding="utf-8"
        )
    )
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
                "prior_audit_receipt": None,
            },
        }
    )
    fixture = ROOT / "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json"
    storage = ROOT / "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json"
    formatting = ROOT / "fixtures/server_package_pipeline_v1/cheap/intermediate_report_format.json"
    input_rows = [
        (SOURCE_ZIP, "package_identity"),
        (runner, "runner"),
        (contract, "return_core_contract"),
        (PREBUILD / "compile_core_evidence.py", "return_collector"),
        (PREBUILD / "fixed_simresult_publisher.py", "return_collector"),
        (PREBUILD / "server_post_sim_return.py", "return_collector"),
        (PREBUILD / "server_waveform_mandatory_return.py", "waveform"),
        (plan_path, "waveform"),
        (dump_path, "waveform"),
        (source_bound["catalog"], "probe_catalog"),
        (source_bound["plan"], "probe_plan"),
        (source_bound["generated"] / "source_bound_causal_parser.py", "parser"),
        (PREBUILD / "native_return_observer.svh", "package_local_hdl"),
    ]
    spec["inputs"] = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "surface": surface,
            "bytes": path.stat().st_size,
            "sha256": base.sha256(path),
        }
        for path, surface in input_rows
    ]
    spec["cheap_check_reports"] = [
        {"gate_id": "core_identity_bootstrap", "path": fixture.relative_to(ROOT).as_posix(), "sha256": base.sha256(fixture)},
        {"gate_id": "source_bound_observer_generation", "path": source_bound["cheap"].relative_to(ROOT).as_posix(), "sha256": base.sha256(source_bound["cheap"])},
        {"gate_id": "runner_return_resilience", "path": runner_report.relative_to(ROOT).as_posix(), "sha256": base.sha256(runner_report)},
        {"gate_id": "storage_rotation", "path": storage.relative_to(ROOT).as_posix(), "sha256": base.sha256(storage)},
        {"gate_id": "intermediate_report_format", "path": formatting.relative_to(ROOT).as_posix(), "sha256": base.sha256(formatting)},
    ]
    validators = spec.setdefault("validators", {})
    validators["runner_return_resilience"] = {
        "validator_sha256": base.sha256(RUNNER_VALIDATOR),
        "fixture_sha256": base.sha256(runner_report),
    }
    validators["source_bound_observer_generation"] = {
        "validator_sha256": base.sha256(SOURCE_BOUND_TOOL),
        "fixture_sha256": base.sha256(source_bound["cheap"]),
    }
    validators["source_bound_final_zip"] = {
        "validator_sha256": base.sha256(SOURCE_BOUND_TOOL),
        "fixture_sha256": base.sha256(source_bound["plan"]),
    }
    for gate in ("post_sim_return_core", "return_result_contract"):
        validators[gate] = {
            "validator_sha256": base.sha256(POST_SIM_TOOL),
            "fixture_sha256": base.sha256(plan_path),
        }
    validators["waveform_observation_final_zip"] = {
        "validator_sha256": base.sha256(WAVEFORM_TOOL),
        "fixture_sha256": base.sha256(plan_path),
    }
    validators["first_fresh_extra_audit"] = {
        "validator_sha256": base.sha256(FIRST_FRESH_TOOL),
        "fixture_sha256": base.sha256(plan_path),
    }
    spec_path = BASE / "server_package_build_spec_v2.json"
    write_json(spec_path, spec)
    profile = BASE / "server_package_build_profile_v2.json"
    aggregated = command(
        [
            PYTHON,
            str(PIPELINE),
            "prepare",
            "--spec",
            str(spec_path),
            "--registry",
            str(GATE_REGISTRY),
            "--workspace-root",
            str(ROOT),
            "--output",
            str(profile),
        ]
    )
    if aggregated.returncode:
        raise BuildError(f"shared prebuild aggregate failed: {aggregated.stderr}\n{aggregated.stdout}")
    value = json.loads(profile.read_text(encoding="utf-8"))
    if (
        value.get("contract_valid") is not True
        or value.get("preflight", {}).get("errors") != []
        or value.get("execution_contract", {}).get("prebuild_aggregate_top_level_invocations") != 1
    ):
        raise BuildError("shared prebuild aggregate did not close")
    return {
        "runner": runner,
        "contract": contract,
        "runner_report": runner_report,
        "plan": plan_path,
        "dump": dump_path,
        "source_bound": source_bound,
        "spec": spec_path,
        "profile": profile,
    }


def patch_runtime_contract(package: Path) -> None:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["package_id"] = PACKAGE_ID
    value["install_name"] = PACKAGE_ID
    additions = [
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/compile/sim_results/codex_waveform_full.tcl",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/compile/sim_results/wave.vpd",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
    ]
    existing = value["path_budget"]["additional_projected_paths"]
    for item in additions:
        if item not in existing:
            existing.append(item)
    value["claim_boundary"] = (
        "p41 changes fresh identity plus mandatory VPD/runtime-return plumbing only; p40 public-surface "
        "observer, compile first-error semantics, config, numeric, workload and functional RTL remain frozen."
    )
    write_json(path, value)


def patch_readme(package: Path) -> None:
    path = package / "README.md"
    text = path.read_text(encoding="utf-8")
    text += (
        "\n## p41 mandatory waveform successor\n\n"
        "This fresh identity preserves the p40 diagnostic and enables VCS VPD capture with "
        "`DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0`. The dump starts at "
        "`tb_NDP_Top_new_phy`, depth 0, with no excluded hierarchy. Every `wave.vpd` shard is "
        "streamed into the formal return without a size cap. If simulation starts and no waveform "
        "is found, the result fails closed as evidence-incomplete; compile-not-started returns still "
        "publish the bounded compile core.\n"
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_manifest(package: Path) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value.update(
        {
            "schema": "conv-native-four-lane-0ccae916-p41-vpdfull-package-v1",
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
        "source_disposition_after_consumption": "superseded_preserved_waveform_hold",
        "reason": (
            "The user-mandated shared waveform gate invalidated the old p40 dump=0 release semantics; "
            "the p40 public-surface and structured-first-error repair is preserved."
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
        "upload_hold_until": "ALL_EXACT_FINAL_ZIP_AND_FIRST_FRESH_GATES_PASS",
    }
    value["repair_delta"] = {
        "preserved_p40_public_surface_observer": True,
        "preserved_p40_structured_first_error": True,
        "changed_surfaces": ["package_identity", "runner", "return_core_contract", "return_collector", "waveform", "storage"],
        "waveform": "mandatory full-hierarchy VPD plus unbounded exact-shard formal return",
        "functional_rtl_modified": False,
        "config_numeric_workload_modified": False,
        "target_diagnostic_modified": False,
    }
    value["mandatory_waveform"] = {
        "rule_id": RULE_IDS[0],
        "shared_gate_epoch": EPOCH,
        "plan": "contracts/server_waveform_mandatory_plan.json",
        "collector": "package_tools/server_waveform_mandatory_return.py",
        "runtime_receipt": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
        "dump_arguments": {"DUMP_VCD": "1", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
        "tb_top": "tb_NDP_Top_new_phy",
        "hierarchy_depth": 0,
        "scope_mode": "FULL_HIERARCHY",
        "excluded_scopes": [],
        "hard_limit_bytes": None,
        "collect_all_matching": True,
        "simulation_started_missing_waveform": "EVIDENCE_INCOMPLETE_FAIL_CLOSED",
        "compile_not_started_waveform_omission": "ALLOWED_WITH_COMPILE_CORE",
    }
    matrix = value.setdefault("release_gate_matrix", {})
    matrix["waveform_observation_final_zip"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": None,
        "semantic_version": "2",
    }
    matrix["post_sim_return_core"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": None,
    }
    matrix["first_fresh_extra_audit"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": None,
        "epoch_id": EPOCH,
    }
    value.setdefault("release_gate_applicability", {})["waveform_observation_final_zip"] = (
        "blocking_shared_waveform_mandatory_v2"
    )
    resilience = value.setdefault("runner_return_resilience", {})
    resilience["waveform_included"] = True
    resilience["runner"] = {
        "path": "PREPARE_AND_RUN.sh",
        "bytes": (package / "PREPARE_AND_RUN.sh").stat().st_size,
        "sha256": base.sha256(package / "PREPARE_AND_RUN.sh"),
    }
    resilience["contract"] = {
        "path": "server_runner_return_resilience_contract.json",
        "bytes": (package / "server_runner_return_resilience_contract.json").stat().st_size,
        "sha256": base.sha256(package / "server_runner_return_resilience_contract.json"),
    }
    value["return_budget"] = {
        "non_waveform_members": "existing bounded text/core policy retained",
        "waveform_hard_limit_bytes": None,
        "waveform_truncation_allowed": False,
        "waveform_sampling_allowed": False,
        "waveform_size_based_deletion_allowed": False,
    }
    allowlist = value.setdefault("return_allowlist_contract", {})
    forbidden = [item for item in allowlist.get("forbidden", []) if item != "waveform"]
    allowlist["forbidden"] = forbidden
    allowlist["mandatory_waveform"] = {
        "discovery": ["wave.vpd", "wave.vpd.*"],
        "manifest": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
        "required_when_simulation_started": True,
        "size_limit": None,
    }
    post = value.setdefault("post_sim_return_core", {})
    post["helper"] = {
        "path": "package_tools/server_post_sim_return.py",
        "bytes": (package / "package_tools/server_post_sim_return.py").stat().st_size,
        "sha256": base.sha256(package / "package_tools/server_post_sim_return.py"),
    }
    post["request"] = {
        "path": "contracts/server_post_sim_return_request.json",
        "bytes": (package / "contracts/server_post_sim_return_request.json").stat().st_size,
        "sha256": base.sha256(package / "contracts/server_post_sim_return_request.json"),
    }
    value["rule_receipts"] = []
    for rule_path in (
        ".agents/rules/生成前必读索引.md",
        ".agents/rules/服务器测试包生成规则.md",
        "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
        "contracts/server_waveform_mandatory_return_dispatch_v2.json",
        "contracts/server_package_build_gate_registry_v1.json",
        "contracts/server_post_sim_return_next_fresh_dispatch_v1.json",
    ):
        source = ROOT / rule_path
        value["rule_receipts"].append(
            {"path": rule_path, "bytes": source.stat().st_size, "sha256": base.sha256(source)}
        )
    value["rule_receipts_current_match"] = True
    value["files"] = {
        item.relative_to(package).as_posix(): {
            "sha256": base.sha256(item),
            "size_bytes": item.stat().st_size,
        }
        for item in sorted(package.rglob("*"))
        if item.is_file() and item != path
    }
    write_json(path, value)


def verify_frozen(package: Path) -> dict[str, Any]:
    prefix = f"{SOURCE_ID}/"
    normalized_equal: dict[str, bool] = {}
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
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        for relative in protected:
            current = (package / relative).read_bytes().replace(
                PACKAGE_ID.encode(), SOURCE_ID.encode()
            )
            source = archive.read(prefix + relative)
            if relative == "tb_probe/source_bound_causal_observer.svh":
                # The generated observer embeds the semantic SHA of the probe
                # plan.  A fresh package identity changes that plan SHA even
                # when the identity-normalized plan and every executable probe
                # statement remain byte-for-byte frozen.  Normalize only this
                # generated provenance comment; the plan itself is checked
                # independently below as a protected diagnostic surface.
                marker = re.compile(rb"plan_semantic_sha256=[0-9a-f]{64}")
                current = marker.sub(b"plan_semantic_sha256=<IDENTITY_BOUND>", current)
                source = marker.sub(b"plan_semantic_sha256=<IDENTITY_BOUND>", source)
            normalized_equal[relative] = current == source
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
    result = {
        "source_p40_zip_bytes": SOURCE_BYTES,
        "source_p40_zip_sha256": SOURCE_SHA256,
        "workload_member_count": len(workload),
        "workload_identity_normalized_byte_equal": workload_equal,
        "protected_diagnostic_identity_normalized_equal": normalized_equal,
        "p40_public_surface_and_target_diagnostic_frozen": all(normalized_equal.values()),
        "config_numeric_workload_functional_rtl_frozen": workload_equal,
        "functional_rtl_modified": False,
    }
    if not workload_equal or not all(normalized_equal.values()):
        raise BuildError(f"p40 frozen-surface comparison failed: {result}")
    return result


def materialize(destination: Path, assets: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    package = base.safe_extract(destination)
    base.reidentity(package)
    shutil.copyfile(assets["runner"], package / "PREPARE_AND_RUN.sh")
    shutil.copyfile(PREBUILD / "compile_core_evidence.py", package / "package_tools/compile_core_evidence.py")
    shutil.copyfile(PREBUILD / "fixed_simresult_publisher.py", package / "package_tools/fixed_simresult_publisher.py")
    shutil.copyfile(POST_SIM_TOOL, package / "package_tools/server_post_sim_return.py")
    shutil.copyfile(WAVEFORM_TOOL, package / "package_tools/server_waveform_mandatory_return.py")
    shutil.copyfile(assets["plan"], package / "contracts/server_waveform_mandatory_plan.json")
    shutil.copyfile(assets["dump"], package / "contracts/server_waveform_dump.tcl")
    write_json(package / "server_runner_return_resilience_contract.json", runner_contract(package / "PREPARE_AND_RUN.sh"))

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
    request["claim_boundary"] = (
        "Frozen p40-equivalent MSE4 join diagnostic plus mandatory full-hierarchy VPD return. "
        "Natural terminal, formal 320D and E3/E4/E5 remain unclaimed."
    )
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract.update(
        {
            "package_id": PACKAGE_ID,
            "helper_sha256": base.sha256(package / "package_tools/server_post_sim_return.py"),
            "request_sha256": base.sha256(request_path),
            "claim_boundary": request["claim_boundary"],
        }
    )
    write_json(contract_path, contract)

    base.refresh_derived_contracts(package)
    patch_runtime_contract(package)
    patch_readme(package)
    base.refresh_manifest(package, assets)
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    pointer_value = json.loads(pointer.read_text(encoding="utf-8"))
    pointer_value.update(
        {
            "schema": "conv-native-four-lane-p41-vpdfull-pointer-v1",
            "package_identity": PACKAGE_ID,
            "status": "PACKAGE_READY_NOT_RUN",
        }
    )
    write_json(pointer, pointer_value)
    patch_manifest(package)
    frozen = verify_frozen(package)
    return package, frozen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    configure_base()
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact superseded p40 source ZIP differs")
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
        raise BuildError("refusing to overwrite p41 build output")
    package, frozen = materialize(output, assets)
    with tempfile.TemporaryDirectory(prefix=".p41_repeat_", dir=ROOT) as temporary:
        repeated, repeated_frozen = materialize(Path(temporary), assets)
        deterministic = base.tree_receipt(package) == base.tree_receipt(repeated)
    if not deterministic or repeated_frozen != frozen:
        raise BuildError("p41 deterministic double staging differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "conv-native-four-lane-p41-vpdfull-build-v1",
        "status": "PACKAGE_BUILT_UPLOAD_HELD_PENDING_EXACT_FINAL_ZIP_GATES",
        "package_identity": PACKAGE_ID,
        "source_p40_zip_sha256": SOURCE_SHA256,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": True,
        "prebuild_aggregate_top_level_invocations": 1,
        "final_zip_count": 1,
        "zip": zip_path.relative_to(ROOT).as_posix(),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "deterministic_double_build_tree_equal": deterministic,
        "frozen": frozen,
        "runner_return_resilience_prebuild": {
            "path": assets["runner_report"].relative_to(ROOT).as_posix(),
            "bytes": assets["runner_report"].stat().st_size,
            "sha256": base.sha256(assets["runner_report"]),
        },
        "shared_aggregate": {
            "path": assets["profile"].relative_to(ROOT).as_posix(),
            "bytes": assets["profile"].stat().st_size,
            "sha256": base.sha256(assets["profile"]),
        },
        "waveform_plan": {
            "path": assets["plan"].relative_to(ROOT).as_posix(),
            "bytes": assets["plan"].stat().st_size,
            "sha256": base.sha256(assets["plan"]),
        },
        "config_numeric_workload_rtl_frozen": True,
        "target_diagnostic_frozen": True,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
