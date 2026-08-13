#!/usr/bin/env python3
"""Build the p38 runner/return-only fresh successor with frozen DUT inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p39_compilecore"
SOURCE_ID = "r5_n4_0cc_p38_mse4join"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_970_142
SOURCE_SHA256 = "328b7ec7b7034a1a2c202fad38d628199cfbbaa2213196d94daab39c25ff4d22"
EPOCH = "20260811-runner-definition-compilefail-core-return-v1"
RULE_IDS = [
    "CDA-SERVER-RUNNER-SET-U-DEFINITION-BEFORE-USE-001",
    "CDA-SERVER-COMPILEFAIL-CORE-RETURN-ROOT-CAUSE-001",
]
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p39_compilecore"
PREBUILD = BASE / "prebuild"
DEFAULT_OUTPUT = BASE / "build"
RUNNER_VALIDATOR = ROOT / "tools/validate_server_runner_return_resilience.py"
PIPELINE = ROOT / "tools/server_package_pipeline.py"
GATE_REGISTRY = ROOT / "contracts/server_package_build_gate_registry_v1.json"
HELPER_SOURCE = ROOT / "tools/conv_native_p39_compile_core_evidence.py"
PUBLISHER_SOURCE = ROOT / "tools/conv_native_p39_fixed_simresult_publisher.py"


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def source_runner() -> str:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        return archive.read(f"{SOURCE_ID}/PREPARE_AND_RUN.sh").decode("utf-8")


def render_runner() -> str:
    source = source_runner().replace(SOURCE_ID, PACKAGE_ID)
    start = source.index("package_root=")
    end = source.index("runner_fail() {")
    header = f'''package_identity="{PACKAGE_ID}"
install_name="{PACKAGE_ID}"
attempt="a0"
return_tag="r$(date -u +%s%N)_$$"
launch_cwd="$PWD"
server_root="${{1-}}"
bootstrap_root="${{server_root}}/install/codex_runs/${{package_identity}}/bootstrap-${{return_tag}}"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_log_receipt_json="$bootstrap_root/compile_log_receipt.json"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
return_allowlist_compile_argv="compile_core/compile_argv.json"
return_allowlist_compile_source="compile_core/compile_source_identity.json"
return_allowlist_compile_exit="compile_core/compile_exit.txt"
return_allowlist_compile_receipt="compile_core/compile_log_receipt.json"
return_allowlist_compile_head="compile_core/compile_log_head.txt"
return_allowlist_compile_tail="compile_core/compile_log_tail.txt"
return_allowlist_compile_first_error="compile_core/compile_first_error.txt"
case "${{BASH_SOURCE[0]}}" in
  /*) package_root="${{BASH_SOURCE[0]%/*}}" ;;
  */*) package_root="$PWD/${{BASH_SOURCE[0]%/*}}" ;;
  *) package_root="$PWD" ;;
esac
layout_helper="$package_root/package_tools/server_package_runtime_layout.py"
runtime="$package_root/package_tools/node0004_assumed_hardware_server_runtime.py"
observer_guard="$package_root/package_tools/node0004_package_observer_guard.py"
source_bound_parser="$package_root/package_tools/source_bound_causal_parser.py"
source_bound_observer="$package_root/tb_probe/source_bound_causal_observer.svh"
post_sim_helper="$package_root/package_tools/server_post_sim_return.py"
post_sim_request="$package_root/contracts/server_post_sim_return_request.json"
compile_core_helper="$package_root/package_tools/compile_core_evidence.py"
trigger_finalizer="$package_root/package_tools/node0004_triggered_causal_finalizer.py"
public_finalizer="$package_root/package_tools/node0004_public_order_finalizer.py"
b5_finalizer="$package_root/package_tools/node0004_buffer5_public_finalizer.py"
publisher="$package_root/package_tools/fixed_simresult_publisher.py"
root_gate="$package_root/package_tools/ndp_root_toplevel_exact_set_gate.py"
result_root="/home/panqs/ndp/simresult"
return_zip="/home/panqs/ndp/simresult/${{package_identity}}_${{return_tag}}_return.zip"
return_sha="${{return_zip}}.sha256"
work_root=""
cfg_root=""
run_root=""
evidence_root=""
compile_root=""
compile_status=125
run_status=125
signal_status=NONE
finalized=0
sim_pid=
progress_pid=
root_gate_status=125
path_budget_status=125
package_preflight_status=125
install_preflight_status=125
observer_preflight_status=125
preflight_stage=BOOTSTRAP_ARMED
natural_terminal=false
simulation_started=false
'''
    runner = source[:start] + header + source[end:]
    runner = runner.replace(
        '--stage "$preflight_stage" --server-root "$server_root" --return-zip "$return_zip"',
        '--stage "$preflight_stage" --server-root "$server_root" --bootstrap-root "$bootstrap_root" --return-zip "$return_zip"',
    )
    trap_marker = "trap 'on_signal TERM 143' TERM\n"
    bootstrap = '''package_root="$(cd "$package_root" 2>/dev/null && pwd -P)" || runner_fail 2 "package-root path cannot be resolved"
layout_helper="$package_root/package_tools/server_package_runtime_layout.py"
runtime="$package_root/package_tools/node0004_assumed_hardware_server_runtime.py"
observer_guard="$package_root/package_tools/node0004_package_observer_guard.py"
source_bound_parser="$package_root/package_tools/source_bound_causal_parser.py"
source_bound_observer="$package_root/tb_probe/source_bound_causal_observer.svh"
post_sim_helper="$package_root/package_tools/server_post_sim_return.py"
post_sim_request="$package_root/contracts/server_post_sim_return_request.json"
compile_core_helper="$package_root/package_tools/compile_core_evidence.py"
trigger_finalizer="$package_root/package_tools/node0004_triggered_causal_finalizer.py"
public_finalizer="$package_root/package_tools/node0004_public_order_finalizer.py"
b5_finalizer="$package_root/package_tools/node0004_buffer5_public_finalizer.py"
publisher="$package_root/package_tools/fixed_simresult_publisher.py"
root_gate="$package_root/package_tools/ndp_root_toplevel_exact_set_gate.py"
'''
    runner = runner.replace(trap_marker, trap_marker + bootstrap, 1)
    resolve_marker = 'server_root="$(cd "$1" 2>/dev/null && pwd -P)" || runner_fail 2 "server-root path cannot be resolved"\n'
    runner = runner.replace(resolve_marker, resolve_marker + '''bootstrap_root="$server_root/install/codex_runs/$package_identity/bootstrap-$return_tag"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_log_receipt_json="$bootstrap_root/compile_log_receipt.json"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
''', 1)
    runner = runner.replace('eval "$layout_shell"\n', '''eval "$layout_shell"
bootstrap_root="${RUN_ROOT%/*}/bootstrap-$return_tag"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_log_receipt_json="$bootstrap_root/compile_log_receipt.json"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
mkdir -p -- "$bootstrap_root" || runner_fail 9 "bootstrap compile-core root cannot be created"
''', 1)
    old_compile_start = 'printf \'%s\\n\' "make -f Makefile.tb_NDP_Top_new_phy compile'
    begin = runner.index(old_compile_start)
    finish_token = '[ "$compile_status" -eq 0 ] || exit "$compile_status"\n'
    finish = runner.index(finish_token, begin) + len(finish_token)
    new_compile = '''python3 "$compile_core_helper" prepare --output-root "$bootstrap_root" --cwd "$server_root" --makefile "$server_root/Makefile.tb_NDP_Top_new_phy" --source "$source_bound_observer" --package-root "$package_root" --run-dir "$compile_root" || runner_fail 8 "compile-core prepare failed"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$compile_root" VCS_EXTRA_OPTS="+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe $source_bound_observer" > "$compile_driver_log" 2>&1
compile_status=$?
python3 "$compile_core_helper" finalize --output-root "$bootstrap_root" --exit-code "$compile_status"
compile_core_status=$?
[ "$compile_core_status" -eq 0 ] || runner_fail 8 "compile-core finalize failed"
[ "$compile_status" -eq 0 ] || exit "$compile_status"
'''
    runner = runner[:begin] + new_compile + runner[finish:]
    runner = runner.replace('"$compile_root/sim_results/compile_driver.log"', '"$compile_driver_log"')
    if runner.count('python3 "$post_sim_helper" finalize --request "$post_sim_request"') != 1:
        raise BuildError("shared post-sim finalizer count changed")
    return runner


def runner_contract(runner: Path, runner_path: str = "PREPARE_AND_RUN.sh") -> dict[str, Any]:
    return {
        "schema": "server-runner-return-resilience-contract-v1",
        "package_id": PACKAGE_ID,
        "runner_path": runner_path,
        "runner_sha256": sha256(runner),
        "nounset_required": True,
        "package_owned_variables": [
            "package_identity", "install_name", "attempt", "return_tag", "server_root", "bootstrap_root",
            "compile_argv_json", "compile_source_identity_json", "compile_exit_txt", "compile_driver_log",
            "compile_log_receipt_json", "compile_log_head_txt", "compile_log_tail_txt", "compile_first_error_txt",
        ],
        "bootstrap_root_variable": "bootstrap_root",
        "finalizer_arm_tokens": ["trap 'finalize $?' EXIT"],
        "first_fallible_tokens": ['package_root="$(cd "$package_root"'],
        "compile_evidence_tokens": {
            "argv": "compile_argv.json", "source_identity": "compile_source_identity.json",
            "exit_code": "compile_exit.txt", "driver_log": "compile_driver.log",
            "first_error": "compile_first_error.txt", "bounded_head": "compile_log_head.txt",
            "bounded_tail": "compile_log_tail.txt",
        },
        "return_allowlist_tokens": [
            "compile_core/compile_argv.json", "compile_core/compile_source_identity.json",
            "compile_core/compile_exit.txt", "compile_core/compile_log_receipt.json",
            "compile_core/compile_log_head.txt", "compile_core/compile_log_tail.txt",
            "compile_core/compile_first_error.txt",
        ],
    }


def command(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)


def prepare_prebuild() -> dict[str, Any]:
    if PREBUILD.exists():
        raise BuildError("refusing to overwrite p39 prebuild assets")
    PREBUILD.mkdir(parents=True)
    runner = PREBUILD / "PREPARE_AND_RUN.sh"
    runner.write_text(render_runner(), encoding="utf-8", newline="\n")
    shutil.copyfile(HELPER_SOURCE, PREBUILD / "compile_core_evidence.py")
    shutil.copyfile(PUBLISHER_SOURCE, PREBUILD / "fixed_simresult_publisher.py")
    contract = PREBUILD / "server_runner_return_resilience_contract.json"
    write_json(contract, runner_contract(runner))
    validation = PREBUILD / "runner_return_resilience.validation.json"
    result = command([
        sys.executable, str(RUNNER_VALIDATOR), "validate-tree", "--root", str(PREBUILD),
        "--contract", str(contract), "--output", str(validation),
    ])
    if result.returncode:
        raise BuildError(f"prebuild runner resilience failed: {result.stderr}\n{validation.read_text(encoding='utf-8')}")
    report = PREBUILD / "runner_return_resilience.json"
    write_json(report, {
        "schema": "server-package-cheap-check-result-v1", "gate_id": "runner_return_resilience",
        "pass": True, "errors": [], "warnings": [],
        "exact_validation": {"path": validation.relative_to(ROOT).as_posix(), "bytes": validation.stat().st_size, "sha256": sha256(validation)},
    })
    fixture = ROOT / "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json"
    storage = ROOT / "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json"
    formatting = ROOT / "fixtures/server_package_pipeline_v1/cheap/intermediate_report_format.json"
    p38_spec = json.loads((ROOT / "outputs/conv_native_four_lane_0ccae916_p38_mse4join/server_package_build_spec_v2.json").read_text(encoding="utf-8"))
    p38_spec.update({"package_id": PACKAGE_ID, "lifecycle": "NEXT_FRESH_SUCCESSOR", "changed_surfaces": ["package_identity", "runner", "return_core_contract", "return_collector", "storage"]})
    p38_spec["rule_change_epoch"] = {"epoch_id": EPOCH, "first_fresh_after_change": True, "prior_audit_receipt": None}
    frozen_generation_inputs = [row for row in p38_spec["inputs"] if row.get("surface") in {"package_local_hdl", "parser", "probe_catalog", "probe_plan"}]
    p38_spec["inputs"] = [
        {"path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "surface": "package_identity", "bytes": SOURCE_ZIP.stat().st_size, "sha256": sha256(SOURCE_ZIP)},
        *({"path": path.relative_to(ROOT).as_posix(), "surface": surface, "bytes": path.stat().st_size, "sha256": sha256(path)} for path, surface in (
            (runner, "runner"), (contract, "return_core_contract"), (PREBUILD / "compile_core_evidence.py", "return_collector"),
            (PREBUILD / "fixed_simresult_publisher.py", "return_collector"),
        )),
        *frozen_generation_inputs,
    ]
    generation_check = next(row for row in json.loads((ROOT / "outputs/conv_native_four_lane_0ccae916_p38_mse4join/server_package_build_spec_v2.json").read_text(encoding="utf-8"))["cheap_check_reports"] if row["gate_id"] == "source_bound_observer_generation")
    p38_spec["cheap_check_reports"] = [
        {"gate_id": "core_identity_bootstrap", "path": fixture.relative_to(ROOT).as_posix(), "sha256": sha256(fixture)},
        generation_check,
        {"gate_id": "runner_return_resilience", "path": report.relative_to(ROOT).as_posix(), "sha256": sha256(report)},
        {"gate_id": "storage_rotation", "path": storage.relative_to(ROOT).as_posix(), "sha256": sha256(storage)},
        {"gate_id": "intermediate_report_format", "path": formatting.relative_to(ROOT).as_posix(), "sha256": sha256(formatting)},
    ]
    p38_spec["validators"]["runner_return_resilience"] = {"validator_sha256": sha256(RUNNER_VALIDATOR), "fixture_sha256": sha256(report)}
    spec = BASE / "server_package_build_spec_v2.json"
    write_json(spec, p38_spec)
    profile = BASE / "server_package_build_profile_v2.json"
    pipeline = command([sys.executable, str(PIPELINE), "prepare", "--spec", str(spec), "--registry", str(GATE_REGISTRY), "--workspace-root", str(ROOT), "--output", str(profile)])
    if pipeline.returncode:
        raise BuildError(f"shared aggregate failed: {pipeline.stderr}\n{pipeline.stdout}")
    value = json.loads(profile.read_text(encoding="utf-8"))
    if value.get("contract_valid") is not True or value.get("preflight", {}).get("errors") != [] or value.get("execution_contract", {}).get("prebuild_aggregate_top_level_invocations") != 1:
        raise BuildError("shared prebuild aggregate did not close")
    return {"runner": runner, "contract": contract, "report": report, "spec": spec, "profile": profile}


def safe_extract(destination: Path) -> Path:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        infos = archive.infolist()
        if archive.testzip() is not None:
            raise BuildError("source ZIP CRC failed")
        for row in infos:
            pure = PurePosixPath(row.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in row.filename or stat.S_ISLNK(row.external_attr >> 16):
                raise BuildError("unsafe source ZIP member")
        archive.extractall(destination)
    source = destination / SOURCE_ID
    target = destination / PACKAGE_ID
    try:
        source.rename(target)
    except PermissionError:
        # Windows indexers can briefly retain an extracted directory handle.
        # A byte-for-byte copy is deterministic and the temporary source root
        # is outside the packaged tree.
        shutil.copytree(source, target)
    return target


def reidentity(package: Path) -> None:
    for path in sorted(row for row in package.rglob("*") if row.is_file()):
        data = path.read_bytes()
        if SOURCE_ID.encode() not in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BuildError(f"identity occurs in non-UTF8 member: {path}") from exc
        path.write_text(text.replace(SOURCE_ID, PACKAGE_ID), encoding="utf-8", newline="\n")


def refresh_manifest(package: Path, assets: dict[str, Any]) -> None:
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "schema": "conv-native-four-lane-0ccae916-p39-compilecore-package-v1",
        "package_identity": PACKAGE_ID, "install_name": PACKAGE_ID, "workload_install_name": PACKAGE_ID,
        "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
        "return_name": f"{PACKAGE_ID}_<execution_id>_return.zip",
        "status": "PACKAGE_READY_NOT_RUN", "candidate_release": False,
    })
    manifest["delivery_successor"] = {
        "source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "pending_replaced_by_fresh_successor",
        "reason": "p38 compile=2 return lacked actual argv/source/log/first-error root-cause evidence",
        "authorized_config_change": None, "numeric_w3_golden_repeated": False,
    }
    manifest["rule_change_epoch"] = {
        "epoch_id": EPOCH, "family": "conv_native_four_lane", "package_id": PACKAGE_ID,
        "first_fresh_after_change": True, "notification_acknowledged": True,
        "rule_ids": RULE_IDS, "upload_hold_until": "ALL_EXACT_FINAL_ZIP_AND_FIRST_FRESH_GATES_PASS",
    }
    manifest["runner_return_resilience"] = {
        "contract": {"path": "server_runner_return_resilience_contract.json", "bytes": (package / "server_runner_return_resilience_contract.json").stat().st_size, "sha256": sha256(package / "server_runner_return_resilience_contract.json")},
        "runner": {"path": "PREPARE_AND_RUN.sh", "bytes": (package / "PREPARE_AND_RUN.sh").stat().st_size, "sha256": sha256(package / "PREPARE_AND_RUN.sh")},
        "bootstrap_root": f"<server_root>/install/codex_runs/{PACKAGE_ID}/bootstrap-<return_tag>",
        "compile_core_allowlist": ["compile_argv.json", "compile_source_identity.json", "compile_exit.txt", "compile_log_receipt.json", "compile_log_head.txt", "compile_log_tail.txt", "compile_first_error.txt"],
        "waveform_included": False,
    }
    matrix = manifest.setdefault("release_gate_matrix", {})
    matrix["runner_return_resilience"] = {"applicability": "blocking_applicable", "blocking": True, "pass": None}
    matrix["first_fresh_extra_audit"] = {"applicability": "blocking_applicable", "blocking": True, "pass": None, "epoch_id": EPOCH}
    matrix["materialized_config"] = {"applicability": "receipt_reuse", "blocking": False, "pass": True, "scope": "87 p38 install payload bytes frozen; SCA identity-normalized equal"}
    manifest.setdefault("release_gate_applicability", {})["first_fresh_extra_audit"] = "blocking_first_fresh_new_runner_return_epoch"
    manifest["post_sim_return_core"]["runner"] = {"path": "PREPARE_AND_RUN.sh", "bytes": (package / "PREPARE_AND_RUN.sh").stat().st_size, "sha256": sha256(package / "PREPARE_AND_RUN.sh"), "shared_post_sim_invocations": 1}
    layout_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    if "package_id" in layout:
        layout["package_id"] = PACKAGE_ID
    layout["claim_boundary"] = "p39 changes package identity, runner and bootstrap compile-failure return only; p38 workload/config/numeric/RTL bytes remain frozen."
    projected: set[str] = set()
    members = [row.relative_to(package).as_posix() for row in package.rglob("*") if row.is_file()]
    for mount in layout["payload_mounts"]:
        source_prefix = mount["source_prefix"]
        projected.update(mount["runtime_prefix"] + member[len(source_prefix):] for member in members if member.startswith(source_prefix))
    attempt = "a" * int(layout["path_budget"]["attempt_max_chars"])
    projected.update(value.replace("{attempt}", attempt) for value in layout["runtime_roots"].values())
    projected.update(value.replace("{attempt}", attempt) for value in layout["path_budget"]["additional_projected_paths"])
    longest = max(projected, key=lambda item: (len(item), item))
    absolute = int(layout["path_budget"]["declared_target_root_max_chars"]) + 1 + len(longest)
    layout["path_budget"]["max_projected_absolute_path_chars"] = absolute
    write_json(layout_path, layout)
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value.update({"schema": "conv-native-four-lane-p39-compilecore-pointer-v1", "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN"})
    write_json(pointer, value)
    path_budget = manifest.setdefault("path_length_budget", {})
    path_budget.update({
        "declared_target_root_max_chars": layout["path_budget"]["declared_target_root_max_chars"],
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": absolute,
        "absolute_path_limit_chars": layout["path_budget"]["absolute_path_limit_chars"],
    })
    inner = [row.relative_to(package).as_posix() for row in package.rglob("*") if row.is_file() and row != manifest_path]
    path_budget.update({
        "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{relative}") for relative in inner),
        "max_inner_suffix_chars": max(map(len, inner)),
        "max_inner_depth": max(len(PurePosixPath(relative).parts) for relative in inner),
        "max_inner_component_chars": max(len(part) for relative in inner for part in PurePosixPath(relative).parts),
        "outer_identity_repeated_inside": False,
    })
    manifest["files"] = {
        row.relative_to(package).as_posix(): {"sha256": sha256(row), "size_bytes": row.stat().st_size}
        for row in sorted(package.rglob("*")) if row.is_file() and row != manifest_path
    }
    write_json(manifest_path, manifest)


def refresh_derived_contracts(package: Path) -> None:
    """Regenerate identity-bound observer products and request receipts."""
    with tempfile.TemporaryDirectory(prefix=".p39_source_bound_", dir=ROOT) as temporary:
        generated = Path(temporary) / "generated"
        report = Path(temporary) / "source_bound_generation_report.json"
        cheap = Path(temporary) / "source_bound_observer_generation.json"
        result = command([
            sys.executable, str(ROOT / "tools/generate_server_source_bound_observer.py"), "materialize",
            "--catalog", str(package / "diagnostics/source_bound_probe_catalog.json"),
            "--plan", str(package / "diagnostics/source_bound_probe_plan.json"),
            "--output-dir", str(generated), "--report", str(report), "--cheap-check-output", str(cheap),
        ])
        if result.returncode:
            raise BuildError(f"p39 source-bound regeneration failed: {result.stderr}\n{result.stdout}")
        shutil.copyfile(generated / "source_bound_causal_observer.svh", package / "tb_probe/source_bound_causal_observer.svh")
        shutil.copyfile(generated / "source_bound_causal_parser.py", package / "package_tools/source_bound_causal_parser.py")
        shutil.copyfile(generated / "source_bound_probe_binding.json", package / "diagnostics/source_bound_probe_binding.json")
        report_value = json.loads(report.read_text(encoding="utf-8"))
        report_value["catalog"]["path"] = "diagnostics/source_bound_probe_catalog.json"
        report_value["plan"]["path"] = "diagnostics/source_bound_probe_plan.json"
        write_json(package / "diagnostics/source_bound_generation_report.json", report_value)
    request = package / "contracts/server_post_sim_return_request.json"
    contract = package / "contracts/server_post_sim_return_contract.json"
    value = json.loads(contract.read_text(encoding="utf-8"))
    value["package_id"] = PACKAGE_ID
    value["request_sha256"] = sha256(request)
    write_json(contract, value)


def materialize(destination: Path, assets: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    package = safe_extract(destination)
    reidentity(package)
    shutil.copyfile(assets["runner"], package / "PREPARE_AND_RUN.sh")
    shutil.copyfile(PREBUILD / "compile_core_evidence.py", package / "package_tools/compile_core_evidence.py")
    shutil.copyfile(PREBUILD / "fixed_simresult_publisher.py", package / "package_tools/fixed_simresult_publisher.py")
    contract_target = package / "server_runner_return_resilience_contract.json"
    write_json(contract_target, runner_contract(package / "PREPARE_AND_RUN.sh"))
    refresh_derived_contracts(package)
    refresh_manifest(package, assets)
    source_prefix = f"{SOURCE_ID}/"
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        frozen = sorted(name[len(source_prefix):] for name in archive.namelist() if name.startswith(source_prefix + "workload/runtime/runs/c0/install/") and not name.endswith("/"))
        byte_equal = len(frozen) == 87 and all((package / name).read_bytes() == archive.read(source_prefix + name) for name in frozen)
        sca = {}
        for name in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json"):
            sca[name] = (package / name).read_text(encoding="utf-8").replace(PACKAGE_ID, SOURCE_ID) == archive.read(source_prefix + name).decode("utf-8")
    frozen_report = {"frozen_install_payload_member_count": len(frozen), "frozen_install_payload_byte_equal": byte_equal, "sca_identity_normalized_equal": sca, "functional_rtl_modified": False}
    if not byte_equal or not all(sca.values()):
        raise BuildError("p38 config/workload freeze check failed")
    return package, frozen_report


def tree_receipt(package: Path) -> dict[str, tuple[int, str]]:
    return {row.relative_to(package).as_posix(): (row.stat().st_size, sha256(row)) for row in sorted(package.rglob("*")) if row.is_file()}


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(row for row in package.rglob("*") if row.is_file()):
            info = zipfile.ZipInfo(f"{PACKAGE_ID}/{path.relative_to(package).as_posix()}", (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644) << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p38 source ZIP differs")
    assets = prepare_prebuild()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = [output / PACKAGE_ID, output / f"{PACKAGE_ID}.zip", output / f"{PACKAGE_ID}.zip.sha256", output / f"{PACKAGE_ID}.build.json"]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite p39 build output")
    package, frozen = materialize(output, assets)
    with tempfile.TemporaryDirectory(prefix=".p39_repeat_", dir=ROOT) as temporary:
        repeated, _ = materialize(Path(temporary), assets)
        deterministic = tree_receipt(package) == tree_receipt(repeated)
    if not deterministic:
        raise BuildError("p39 deterministic double staging differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    deterministic_zip(package, zip_path)
    digest = sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p39-compilecore-build-v1", "status": "PACKAGE_BUILT_UPLOAD_HELD_PENDING_EXACT_FINAL_ZIP_GATES",
        "package_identity": PACKAGE_ID, "source_p38_zip_sha256": SOURCE_SHA256, "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": True, "prebuild_aggregate_top_level_invocations": 1, "final_zip_count": 1,
        "zip": str(zip_path.relative_to(ROOT)), "zip_bytes": zip_path.stat().st_size, "zip_sha256": digest,
        "deterministic_double_build_tree_equal": deterministic, "frozen": frozen,
        "runner_return_resilience_prebuild": {"path": assets["report"].relative_to(ROOT).as_posix(), "bytes": assets["report"].stat().st_size, "sha256": sha256(assets["report"])},
        "shared_aggregate": {"path": assets["profile"].relative_to(ROOT).as_posix(), "bytes": assets["profile"].stat().st_size, "sha256": sha256(assets["profile"])},
        "config_numeric_workload_rtl_frozen": True, "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
