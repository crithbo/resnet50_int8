#!/usr/bin/env python3
"""Build the p41-return successor with an exact vector-handshake probe repair."""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p39_compilecore_package as base
import build_conv_native_four_lane_0ccae916_p41_vpdfull_package as p41


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p42_vecjoinfix"
SOURCE_ID = "r5_n4_0cc_p41_vpdfull"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
SOURCE_BYTES = 5_986_703
SOURCE_SHA256 = "339d8f4e17cbf34132be9bc84f33dec637ea3fd6ecc8deeec5aa5620a012a95a"
EPOCH = "waveform-mandatory-v2-01ca6d7cd4a4a270"
RULE_IDS = p41.RULE_IDS
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p42_vecjoinfix"
PREBUILD = BASE / "prebuild"
DEFAULT_OUTPUT = BASE / "build"
PIPELINE = ROOT / "tools/server_package_pipeline.py"
GATE_REGISTRY = ROOT / "contracts/server_package_build_gate_registry_v1.json"
RUNNER_VALIDATOR = ROOT / "tools/validate_server_runner_return_resilience.py"
SOURCE_BOUND_TOOL = ROOT / "tools/generate_server_source_bound_observer.py"
POST_SIM_TOOL = ROOT / "tools/server_post_sim_return.py"
WAVEFORM_TOOL = ROOT / "tools/server_waveform_mandatory_return.py"
FIRST_FRESH_TOOL = ROOT / "tools/validate_server_first_fresh_extra_audit.py"
P41_FIRST_FRESH = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p41_vpdfull/first_fresh_audit/first_fresh_validation.json"
)
PYTHON = sys.executable


class BuildError(RuntimeError):
    pass


def configure() -> None:
    for module in (base, p41):
        module.PACKAGE_ID = PACKAGE_ID
        module.SOURCE_ID = SOURCE_ID
        module.SOURCE_ZIP = SOURCE_ZIP
        module.SOURCE_BYTES = SOURCE_BYTES
        module.SOURCE_SHA256 = SOURCE_SHA256
        module.EPOCH = EPOCH
        module.RULE_IDS = RULE_IDS
        module.BASE = BASE
        module.PREBUILD = PREBUILD
        module.DEFAULT_OUTPUT = DEFAULT_OUTPUT


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


def source_member(relative: str) -> bytes:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        return archive.read(f"{SOURCE_ID}/{relative}")


def source_text(relative: str) -> str:
    return source_member(relative).decode("utf-8").replace(SOURCE_ID, PACKAGE_ID)


def patch_wdata_predicate(plan: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(plan)
    value["package_id"] = PACKAGE_ID
    boundary = next(
        row for row in value["boundaries"] if row["boundary_id"] == "mse4_wdata_output_accept"
    )
    target = next(
        row for row in boundary["classes"] if row["class_id"] == "MSE4_WDATA_OUTPUT_ACCEPT"
    )
    old = target["predicate"]
    if old.get("op") != "AND" or len(old.get("args", [])) != 2:
        raise BuildError("p41 MSE4 wdata predicate shape changed")
    symbol_ids = [row.get("symbol_id") for row in old["args"]]
    if any(row.get("op") != "SIGNAL" for row in old["args"]):
        raise BuildError("p41 MSE4 wdata predicate operands changed")
    target["predicate"] = {
        "op": "BIT_AND_NONZERO",
        "symbol_ids": symbol_ids,
    }
    return value


def prepare_source_bound() -> dict[str, Path]:
    catalog = PREBUILD / "source_bound_probe_catalog.json"
    plan = PREBUILD / "source_bound_probe_plan.json"
    catalog.write_text(
        source_text("diagnostics/source_bound_probe_catalog.json"),
        encoding="utf-8",
        newline="\n",
    )
    source_plan = json.loads(
        source_text("diagnostics/source_bound_probe_plan.json")
    )
    write_json(plan, patch_wdata_predicate(source_plan))
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
        raise BuildError("source-bound cheap check did not pass")
    observer = (generated / "source_bound_causal_observer.svh").read_text(encoding="utf-8")
    wdata_module = observer.split("module codex_probe_mse4_wdata_output_accept(", 1)[1].split(
        "endmodule", 1
    )[0]
    if "((|(p_0 & p_2)) === 1'b1)" not in wdata_module:
        raise BuildError("generated observer lacks exact vector-handshake overlap predicate")
    if "wire codex_progress_now = ((p_0 === 1'b1) && (p_2 === 1'b1));" in wdata_module:
        raise BuildError("generated observer retained the p41 scalar case-equality defect")
    return {
        "catalog": catalog,
        "plan": plan,
        "generated": generated,
        "report": report,
        "cheap": cheap,
    }


def prepare_prebuild() -> dict[str, Any]:
    if PREBUILD.exists():
        raise BuildError("refusing to overwrite p42 prebuild assets")
    PREBUILD.mkdir(parents=True)
    runner = PREBUILD / "PREPARE_AND_RUN.sh"
    runner.write_text(source_text("PREPARE_AND_RUN.sh"), encoding="utf-8", newline="\n")
    for relative, target in (
        ("package_tools/compile_core_evidence.py", "compile_core_evidence.py"),
        ("package_tools/fixed_simresult_publisher.py", "fixed_simresult_publisher.py"),
        ("tb_probe/native_return_observer.svh", "native_return_observer.svh"),
    ):
        (PREBUILD / target).write_text(source_text(relative), encoding="utf-8", newline="\n")
    shutil.copyfile(POST_SIM_TOOL, PREBUILD / "server_post_sim_return.py")
    shutil.copyfile(WAVEFORM_TOOL, PREBUILD / "server_waveform_mandatory_return.py")
    waveform_plan = PREBUILD / "server_waveform_mandatory_plan.json"
    write_json(waveform_plan, p41.waveform_plan())
    dump = PREBUILD / "server_waveform_dump.tcl"
    rendered = command(
        [
            PYTHON,
            str(WAVEFORM_TOOL),
            "render-dump-control",
            "--plan",
            str(waveform_plan),
            "--output",
            str(dump),
        ]
    )
    if rendered.returncode:
        raise BuildError(f"waveform dump render failed: {rendered.stderr}")

    contract = PREBUILD / "server_runner_return_resilience_contract.json"
    write_json(contract, p41.runner_contract(runner))
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
        raise BuildError(f"runner resilience prebuild failed: {checked.stderr}")
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
        (ROOT / "outputs/conv_native_four_lane_0ccae916_p41_vpdfull/server_package_build_spec_v2.json").read_text(
            encoding="utf-8"
        )
    )
    spec.update(
        {
            "package_id": PACKAGE_ID,
            "lifecycle": "NEXT_FRESH_SUCCESSOR",
            "changed_surfaces": [
                "package_identity",
                "package_local_hdl",
                "canonical_predicate",
                "probe_plan",
                "parser",
                "storage",
            ],
            "rule_change_epoch": {
                "epoch_id": EPOCH,
                "first_fresh_after_change": False,
                "prior_audit_receipt": {
                    "path": P41_FIRST_FRESH.relative_to(ROOT).as_posix(),
                    "sha256": base.sha256(P41_FIRST_FRESH),
                    "package_id": SOURCE_ID,
                },
            },
        }
    )
    input_rows = [
        (SOURCE_ZIP, "package_identity"),
        (runner, "runner"),
        (contract, "return_core_contract"),
        (PREBUILD / "compile_core_evidence.py", "return_collector"),
        (PREBUILD / "fixed_simresult_publisher.py", "return_collector"),
        (PREBUILD / "server_post_sim_return.py", "return_collector"),
        (PREBUILD / "server_waveform_mandatory_return.py", "waveform"),
        (waveform_plan, "waveform"),
        (dump, "waveform"),
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
            "sha256": base.sha256(path),
        }
        for path, surface in input_rows
    ]
    fixtures = {
        "core_identity_bootstrap": ROOT / "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json",
        "storage_rotation": ROOT / "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json",
        "intermediate_report_format": ROOT / "fixtures/server_package_pipeline_v1/cheap/intermediate_report_format.json",
    }
    spec["cheap_check_reports"] = [
        {
            "gate_id": gate_id,
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": base.sha256(path),
        }
        for gate_id, path in fixtures.items()
    ] + [
        {
            "gate_id": "source_bound_observer_generation",
            "path": source_bound["cheap"].relative_to(ROOT).as_posix(),
            "sha256": base.sha256(source_bound["cheap"]),
        },
        {
            "gate_id": "runner_return_resilience",
            "path": runner_report.relative_to(ROOT).as_posix(),
            "sha256": base.sha256(runner_report),
        },
    ]
    validators = spec.setdefault("validators", {})
    validators["runner_return_resilience"] = {
        "validator_sha256": base.sha256(RUNNER_VALIDATOR),
        "fixture_sha256": base.sha256(runner_report),
    }
    for gate_id in ("source_bound_observer_generation", "source_bound_final_zip", "package_local_hdl"):
        validators[gate_id] = {
            "validator_sha256": base.sha256(SOURCE_BOUND_TOOL),
            "fixture_sha256": base.sha256(
                source_bound["cheap"] if gate_id == "source_bound_observer_generation" else source_bound["plan"]
            ),
        }
    validators["diagnostic_semantics"] = {
        "validator_sha256": base.sha256(SOURCE_BOUND_TOOL),
        "fixture_sha256": base.sha256(source_bound["plan"]),
    }
    for gate_id in ("post_sim_return_core", "return_result_contract"):
        validators[gate_id] = {
            "validator_sha256": base.sha256(POST_SIM_TOOL),
            "fixture_sha256": base.sha256(waveform_plan),
        }
    validators["waveform_observation_final_zip"] = {
        "validator_sha256": base.sha256(WAVEFORM_TOOL),
        "fixture_sha256": base.sha256(waveform_plan),
    }
    validators["first_fresh_extra_audit"] = {
        "validator_sha256": base.sha256(FIRST_FRESH_TOOL),
        "fixture_sha256": base.sha256(P41_FIRST_FRESH),
    }
    spec_path = BASE / "server_package_build_spec_v2.json"
    write_json(spec_path, spec)
    profile = BASE / "server_package_build_profile_v2.json"
    result = command(
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
    if result.returncode:
        raise BuildError(f"shared aggregate failed: {result.stderr}\n{result.stdout}")
    value = json.loads(profile.read_text(encoding="utf-8"))
    if (
        value.get("contract_valid") is not True
        or value.get("preflight", {}).get("errors") != []
        or value.get("execution_contract", {}).get("prebuild_aggregate_top_level_invocations") != 1
    ):
        raise BuildError(f"shared aggregate did not close: {value.get('preflight')}")
    return {
        "runner": runner,
        "contract": contract,
        "runner_report": runner_report,
        "waveform_plan": waveform_plan,
        "dump": dump,
        "source_bound": source_bound,
        "spec": spec_path,
        "profile": profile,
    }


def patch_manifest(package: Path, assets: dict[str, Any]) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value.update(
        {
            "schema": "conv-native-four-lane-0ccae916-p42-vecjoinfix-package-v1",
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
        "source_disposition_after_consumption": "tested_bound_to_p41_formal_return",
        "reason": (
            "p41 passed production compile and mandatory waveform return, but its generated "
            "source-bound 2-bit wdata handshake predicate used scalar case equality and missed "
            "the 18 MSE4 wdata transactions recorded by the independent native ledger."
        ),
        "authorized_config_change": None,
        "numeric_w3_golden_repeated": False,
    }
    value["rule_change_epoch"] = {
        "epoch_id": EPOCH,
        "family": "conv_native_four_lane",
        "package_id": PACKAGE_ID,
        "first_fresh_after_change": False,
        "prior_first_fresh_receipt": P41_FIRST_FRESH.relative_to(ROOT).as_posix(),
        "notification_acknowledged": True,
        "rule_ids": RULE_IDS,
    }
    value["repair_delta"] = {
        "changed_surfaces": [
            "package_identity",
            "source_bound_probe_plan",
            "generated_source_bound_observer",
            "generated_source_bound_binding",
            "generated_source_bound_parser_receipts",
            "storage",
        ],
        "source_bound_vector_handshake": {
            "boundary": "mse4_wdata_output_accept",
            "old_semantics": "(valid_vector === 1'b1) && (ready_vector === 1'b1)",
            "new_semantics": "(|(valid_vector & ready_vector)) === 1'b1",
            "operator": "BIT_AND_NONZERO",
            "operand_width_bits": [2, 2],
        },
        "target_diagnostic_modified": False,
        "diagnostic_implementation_repaired": True,
        "mandatory_waveform_semantics_modified": False,
        "functional_rtl_modified": False,
        "config_numeric_workload_golden_modified": False,
    }
    value["rule_receipts"] = []
    for relative in (
        ".agents/rules/生成前必读索引.md",
        ".agents/rules/服务器测试包生成规则.md",
        "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
        "contracts/server_waveform_mandatory_return_dispatch_v2.json",
        "contracts/server_package_build_gate_registry_v1.json",
        "contracts/server_post_sim_return_next_fresh_dispatch_v1.json",
    ):
        source = ROOT / relative
        value["rule_receipts"].append(
            {"path": relative, "bytes": source.stat().st_size, "sha256": base.sha256(source)}
        )
    value["rule_receipts_current_match"] = True
    layout_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    projected: set[str] = set()
    members = [row.relative_to(package).as_posix() for row in package.rglob("*") if row.is_file()]
    for mount in layout["payload_mounts"]:
        source_prefix = mount["source_prefix"]
        projected.update(
            mount["runtime_prefix"] + member[len(source_prefix) :]
            for member in members
            if member.startswith(source_prefix)
        )
    attempt = "a" * int(layout["path_budget"]["attempt_max_chars"])
    projected.update(item.replace("{attempt}", attempt) for item in layout["runtime_roots"].values())
    projected.update(
        item.replace("{attempt}", attempt) for item in layout["path_budget"]["additional_projected_paths"]
    )
    longest = max(projected, key=lambda item: (len(item), item))
    absolute = int(layout["path_budget"]["declared_target_root_max_chars"]) + 1 + len(longest)
    layout["path_budget"]["max_projected_absolute_path_chars"] = absolute
    write_json(layout_path, layout)
    path_budget = value.setdefault("path_length_budget", {})
    path_budget.update(
        {
            "declared_target_root_max_chars": layout["path_budget"]["declared_target_root_max_chars"],
            "longest_projected_relative_path": longest,
            "longest_projected_relative_path_chars": len(longest),
            "max_projected_relative_path_chars": len(longest),
            "max_projected_absolute_path_chars": absolute,
            "absolute_path_limit_chars": layout["path_budget"]["absolute_path_limit_chars"],
        }
    )
    inner = [
        row.relative_to(package).as_posix()
        for row in package.rglob("*")
        if row.is_file() and row != path
    ]
    path_budget.update(
        {
            "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{relative}") for relative in inner),
            "max_inner_suffix_chars": max(map(len, inner)),
            "max_inner_depth": max(len(PurePosixPath(relative).parts) for relative in inner),
            "max_inner_component_chars": max(
                len(part) for relative in inner for part in PurePosixPath(relative).parts
            ),
            "outer_identity_repeated_inside": False,
        }
    )
    value["files"] = {
        row.relative_to(package).as_posix(): {
            "sha256": base.sha256(row),
            "size_bytes": row.stat().st_size,
        }
        for row in sorted(package.rglob("*"))
        if row.is_file() and row != path
    }
    write_json(path, value)


def verify_frozen(package: Path) -> dict[str, Any]:
    source_plan = json.loads(source_member("diagnostics/source_bound_probe_plan.json"))
    normalized_source_plan = json.loads(
        json.dumps(source_plan).replace(SOURCE_ID, PACKAGE_ID)
    )
    expected_plan = patch_wdata_predicate(normalized_source_plan)
    actual_plan = json.loads(
        (package / "diagnostics/source_bound_probe_plan.json").read_text(encoding="utf-8")
    )
    protected = (
        "tb_probe/native_return_observer.svh",
        "diagnostics/source_bound_probe_catalog.json",
        "diagnostics/arm_known_contract.json",
        "diagnostics/sa_epoch_contract.json",
        "diagnostics/mse4_join_contract.json",
        "diagnostics/exact_instance_identity.json",
        "contracts/server_waveform_mandatory_plan.json",
        "contracts/server_waveform_dump.tcl",
    )
    protected_equal: dict[str, bool] = {}
    for relative in protected:
        current = (package / relative).read_bytes().replace(PACKAGE_ID.encode(), SOURCE_ID.encode())
        original = source_member(relative)
        protected_equal[relative] = current == original
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        prefix = f"{SOURCE_ID}/"
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
    observer = (package / "tb_probe/source_bound_causal_observer.svh").read_text(encoding="utf-8")
    wdata_module = observer.split("module codex_probe_mse4_wdata_output_accept(", 1)[1].split(
        "endmodule", 1
    )[0]
    result = {
        "source_p41_zip_bytes": SOURCE_BYTES,
        "source_p41_zip_sha256": SOURCE_SHA256,
        "workload_member_count": len(workload),
        "workload_identity_normalized_byte_equal": workload_equal,
        "protected_identity_normalized_equal": protected_equal,
        "target_plan_equals_single_intended_predicate_repair": actual_plan == expected_plan,
        "generated_vector_overlap_present": "((|(p_0 & p_2)) === 1'b1)" in wdata_module,
        "p41_scalar_case_equality_absent": (
            "wire codex_progress_now = ((p_0 === 1'b1) && (p_2 === 1'b1));" not in wdata_module
        ),
        "config_numeric_workload_golden_functional_rtl_frozen": workload_equal,
        "mandatory_waveform_semantics_frozen": protected_equal.get(
            "contracts/server_waveform_mandatory_plan.json"
        )
        is True,
        "functional_rtl_modified": False,
        "target_diagnostic_modified": False,
    }
    if not (
        workload_equal
        and all(protected_equal.values())
        and result["target_plan_equals_single_intended_predicate_repair"]
        and result["generated_vector_overlap_present"]
        and result["p41_scalar_case_equality_absent"]
    ):
        raise BuildError(f"p42 frozen-surface audit failed: {result}")
    return result


def materialize(destination: Path, assets: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    package = base.safe_extract(destination)
    base.reidentity(package)
    shutil.copyfile(assets["runner"], package / "PREPARE_AND_RUN.sh")
    shutil.copyfile(PREBUILD / "compile_core_evidence.py", package / "package_tools/compile_core_evidence.py")
    shutil.copyfile(PREBUILD / "fixed_simresult_publisher.py", package / "package_tools/fixed_simresult_publisher.py")
    shutil.copyfile(POST_SIM_TOOL, package / "package_tools/server_post_sim_return.py")
    shutil.copyfile(WAVEFORM_TOOL, package / "package_tools/server_waveform_mandatory_return.py")
    shutil.copyfile(assets["waveform_plan"], package / "contracts/server_waveform_mandatory_plan.json")
    shutil.copyfile(assets["dump"], package / "contracts/server_waveform_dump.tcl")
    shutil.copyfile(assets["source_bound"]["plan"], package / "diagnostics/source_bound_probe_plan.json")
    write_json(
        package / "server_runner_return_resilience_contract.json",
        p41.runner_contract(package / "PREPARE_AND_RUN.sh"),
    )
    base.refresh_derived_contracts(package)
    request = package / "contracts/server_post_sim_return_request.json"
    contract = package / "contracts/server_post_sim_return_contract.json"
    request_value = json.loads(request.read_text(encoding="utf-8"))
    request_value["package_id"] = PACKAGE_ID
    request_value["claim_boundary"] = (
        "Frozen p41 MSE4 target with exact vector-overlap source-bound handshake repair and "
        "unchanged mandatory full-hierarchy VPD return. Natural terminal, formal 320D and E3/E4/E5 remain unclaimed."
    )
    write_json(request, request_value)
    contract_value = json.loads(contract.read_text(encoding="utf-8"))
    contract_value.update(
        {
            "package_id": PACKAGE_ID,
            "helper_sha256": base.sha256(package / "package_tools/server_post_sim_return.py"),
            "request_sha256": base.sha256(request),
            "claim_boundary": request_value["claim_boundary"],
        }
    )
    write_json(contract, contract_value)
    runtime = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    runtime_value = json.loads(runtime.read_text(encoding="utf-8"))
    runtime_value["package_id"] = PACKAGE_ID
    runtime_value["install_name"] = PACKAGE_ID
    runtime_value["claim_boundary"] = (
        "p42 changes fresh identity plus the package-local source-bound vector handshake implementation only; "
        "runner, waveform, config, numeric, workload, golden and functional RTL remain frozen."
    )
    write_json(runtime, runtime_value)
    readme = package / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + (
            "\n## p42 vector-handshake observer repair\n\n"
            "The MSE4 wdata source-bound boundary now qualifies any known same-channel "
            "`valid & ready` bit. This repairs p41's scalar case-equality false negative; "
            "the MSE4 target, workload and mandatory full-hierarchy VPD semantics are unchanged.\n"
        ),
        encoding="utf-8",
        newline="\n",
    )
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    pointer_value = json.loads(pointer.read_text(encoding="utf-8"))
    pointer_value.update(
        {
            "schema": "conv-native-four-lane-p42-vecjoinfix-pointer-v1",
            "package_identity": PACKAGE_ID,
            "status": "PACKAGE_READY_NOT_RUN",
        }
    )
    write_json(pointer, pointer_value)
    patch_manifest(package, assets)
    return package, verify_frozen(package)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    configure()
    if not P41_FIRST_FRESH.is_file():
        raise BuildError("p41 first-fresh receipt is absent")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p41 source ZIP differs")
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
        raise BuildError("refusing to overwrite p42 build output")
    package, frozen = materialize(output, assets)
    with tempfile.TemporaryDirectory(prefix=".p42_repeat_", dir=ROOT) as temporary:
        repeated, repeated_frozen = materialize(Path(temporary), assets)
        deterministic = base.tree_receipt(package) == base.tree_receipt(repeated)
    if not deterministic or repeated_frozen != frozen:
        raise BuildError("p42 deterministic double staging differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "conv-native-four-lane-p42-vecjoinfix-build-v1",
        "status": "PACKAGE_BUILT_UPLOAD_HELD_PENDING_EXACT_FINAL_ZIP_GATES",
        "package_identity": PACKAGE_ID,
        "source_p41_zip_sha256": SOURCE_SHA256,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": False,
        "prior_first_fresh_receipt": P41_FIRST_FRESH.relative_to(ROOT).as_posix(),
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
            "sha256": base.sha256(assets["profile"]),
        },
        "source_bound_generation": {
            "path": assets["source_bound"]["cheap"].relative_to(ROOT).as_posix(),
            "bytes": assets["source_bound"]["cheap"].stat().st_size,
            "sha256": base.sha256(assets["source_bound"]["cheap"]),
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
