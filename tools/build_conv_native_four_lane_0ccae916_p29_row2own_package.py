#!/usr/bin/env python3
"""Build p29: row2 post-clear ownership diagnostic plus independent return core."""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p28_b5release_package as prior


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p28_b5release"
PACKAGE_ID = "r5_n4_0cc_p29_row2own"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_910_425
SOURCE_SHA256 = "3b15bf1cebf18b95d07e4c290ccf246d7cd6f89e6b2bd6c9665b05186b2e0066"
P28_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p28_return_analysis/report.json"
P28_ANALYSIS_SHA256 = "5acb6a0e2be476d874b09364270b1ffe2a9026a9cb8b917bf74212195337aed8"
SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p29_row2own_source_bound"
GENERATED = SOURCE_BOUND / "generated"
POST_SIM_HELPER = ROOT / "tools/server_post_sim_return.py"
POST_SIM_HELPER_SHA256 = "87c78dd8408d75430074f05e07e99ba3d1b7db3bc5907860b9d15969b172b0b8"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p29_row2own/build"
base = prior.base


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    prior.write_json(path, value)


def configure_prior() -> None:
    prior.SOURCE_ID = SOURCE_ID
    prior.PACKAGE_ID = PACKAGE_ID
    prior.SOURCE_ZIP = SOURCE_ZIP
    prior.SOURCE_BYTES = SOURCE_BYTES
    prior.SOURCE_SHA256 = SOURCE_SHA256
    prior.SOURCE_BOUND = SOURCE_BOUND
    prior.GENERATED = GENERATED
    prior.DEFAULT_OUTPUT = DEFAULT_OUTPUT


def post_sim_request() -> dict[str, Any]:
    core: list[tuple[str, str, str, bool]] = [
        ("package", "package_manifest.json", "source_package/package_manifest.json", True),
        ("package", "diagnostics/source_bound_probe_binding.json", "source_package/source_bound_probe_binding.json", True),
        ("package", "diagnostics/source_bound_generation_report.json", "source_package/source_bound_generation_report.json", True),
        ("attempt", "evidence/compile_exit_status.txt", "evidence/compile_exit_status.txt", True),
        ("attempt", "evidence/run_exit_status.txt", "evidence/run_exit_status.txt", True),
        ("attempt", "evidence/signal_status.txt", "evidence/signal_status.txt", True),
        ("attempt", "evidence/package_local_preflight_status.json", "evidence/package_local_preflight_status.json", True),
        ("attempt", "evidence/package_preflight.json", "evidence/package_preflight.json", True),
        ("attempt", "evidence/install_preflight.json", "evidence/install_preflight.json", True),
        ("attempt", "evidence/observer_precompile.json", "evidence/observer_precompile.json", True),
        ("attempt", "evidence/ndp_root_toplevel_gate.json", "evidence/ndp_root_toplevel_gate.json", True),
        ("attempt", "evidence/production_rtl_identity.json", "evidence/production_rtl_identity.json", True),
        ("attempt", "evidence/source_bound_causal_decision.json", "evidence/source_bound_causal_decision.json", True),
        ("attempt", "evidence/buffer5_public_summary.json", "evidence/buffer5_public_summary.json", False),
        ("attempt", "evidence/public_order_summary.json", "evidence/public_order_summary.json", False),
        ("attempt", "evidence/triggered_causal_summary.json", "evidence/triggered_causal_summary.json", False),
        ("attempt", "evidence/feature_binding/c0.json", "evidence/feature_binding/c0.json", False),
        ("attempt", "evidence/SERVER_RESULT_GATE.json", "evidence/SERVER_RESULT_GATE.json", False),
        ("attempt", "compile/sim_results/compile_driver.log", "runs/compile/compile_driver.log", False),
        ("attempt", "c0/simulator_argv.txt", "runs/c0/simulator_argv.txt", True),
        ("attempt", "c0/sim.log", "runs/c0/sim.log", True),
        ("attempt", "c0/source_bound_causal.log", "runs/c0/source_bound_causal.log", True),
        ("attempt", "c0/return_observer.log", "runs/c0/return_observer.log", False),
        ("attempt", "c0/triggered_observer.log", "runs/c0/triggered_observer.log", False),
        ("attempt", "c0/public_order_observer.log", "runs/c0/public_order_observer.log", False),
        ("attempt", "c0/buffer5_public_observer.log", "runs/c0/buffer5_public_observer.log", False),
        ("attempt", "c0/host_progress.log", "runs/c0/host_progress.log", False),
    ]
    plugins = [
        {
            "plugin_id": "source_bound_parser",
            "argv": ["python3", "{package_root}/package_tools/source_bound_causal_parser.py", "--log", "{attempt_root}/c0/source_bound_causal.log", "--output", "{attempt_root}/evidence/source_bound_causal_decision.json"],
            "cwd_root": "attempt",
            "timeout_seconds": 120,
            "required_for_adjudication": True,
        },
        {
            "plugin_id": "buffer5_public_finalizer",
            "argv": ["python3", "{package_root}/package_tools/node0004_buffer5_public_finalizer.py", "--observer-log", "{attempt_root}/c0/buffer5_public_observer.log", "--output", "{attempt_root}/evidence/buffer5_public_summary.json"],
            "cwd_root": "attempt",
            "timeout_seconds": 120,
            "required_for_adjudication": False,
        },
        {
            "plugin_id": "triggered_causal_finalizer",
            "argv": ["python3", "{package_root}/package_tools/node0004_triggered_causal_finalizer.py", "--observer-log", "{attempt_root}/c0/triggered_observer.log", "--sim-log", "{attempt_root}/c0/sim.log", "--compile-status", "{attempt_root}/evidence/compile_exit_status.txt", "--run-status", "{attempt_root}/evidence/run_exit_status.txt", "--signal-status", "{attempt_root}/evidence/signal_status.txt", "--output", "{attempt_root}/evidence/triggered_causal_summary.json"],
            "cwd_root": "attempt",
            "timeout_seconds": 120,
            "required_for_adjudication": False,
        },
        {
            "plugin_id": "public_order_finalizer",
            "argv": ["python3", "{package_root}/package_tools/node0004_public_order_finalizer.py", "--observer-log", "{attempt_root}/c0/public_order_observer.log", "--compile-status", "{attempt_root}/evidence/compile_exit_status.txt", "--run-status", "{attempt_root}/evidence/run_exit_status.txt", "--signal-status", "{attempt_root}/evidence/signal_status.txt", "--output", "{attempt_root}/evidence/public_order_summary.json"],
            "cwd_root": "attempt",
            "timeout_seconds": 120,
            "required_for_adjudication": False,
        },
        {
            "plugin_id": "feature_binding",
            "argv": ["python3", "{package_root}/package_tools/node0004_assumed_hardware_server_runtime.py", "feature-binding", "--sim-log", "{attempt_root}/c0/sim.log", "--observer-log", "{attempt_root}/c0/return_observer.log", "--output", "{attempt_root}/evidence/feature_binding/c0.json"],
            "cwd_root": "attempt",
            "timeout_seconds": 120,
            "required_for_adjudication": False,
        },
        {
            "plugin_id": "family_analyze",
            "argv": ["python3", "{package_root}/package_tools/node0004_assumed_hardware_server_runtime.py", "analyze", "--package-root", "{package_root}", "--evidence-root", "{attempt_root}/evidence", "--run-root", "{attempt_root}"],
            "cwd_root": "attempt",
            "timeout_seconds": 180,
            "required_for_adjudication": False,
        },
    ]
    return {
        "schema": "server-post-sim-return-request-v1",
        "package_id": PACKAGE_ID,
        "result_root": "/home/panqs/ndp/simresult",
        "return_basename_template": "{package_id}_{execution_id}_return.zip",
        "core_entries": [
            {"source_root": root, "source": source, "archive": archive, "required": required}
            for root, source, archive, required in core
        ],
        "plugins": plugins,
        "max_plugin_output_bytes": 262144,
        "claim_boundary": (
            "p29 c0 row2 post-clear ownership diagnostic only. Core publication is independent of parser/plugin success; "
            "natural terminal, formal 320D and E3/E4/E5 remain dynamic and unclaimed."
        ),
    }


def install_post_sim_contract(package: Path) -> dict[str, Any]:
    if base.sha256(POST_SIM_HELPER) != POST_SIM_HELPER_SHA256:
        raise BuildError("shared post-sim helper identity differs")
    helper = package / "package_tools/server_post_sim_return.py"
    helper.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(POST_SIM_HELPER, helper)
    request_path = package / "contracts/server_post_sim_return_request.json"
    write_json(request_path, post_sim_request())
    contract = {
        "schema": "server-post-sim-return-contract-v1",
        "package_id": PACKAGE_ID,
        "runner_member": "PREPARE_AND_RUN.sh",
        "helper_member": "package_tools/server_post_sim_return.py",
        "helper_sha256": base.sha256(helper),
        "request_member": "contracts/server_post_sim_return_request.json",
        "request_sha256": base.sha256(request_path),
        "invocation_mode": "JSON_REQUEST_ONLY_NO_POSITIONAL_COLLECTOR",
        "sim_exit_persisted_before_plugins": True,
        "plugin_failure_blocks_core_return": False,
        "required_scenarios": [
            "natural_success",
            "natural_success_plugin_failure",
            "simulation_nonzero",
            "idempotent_reentry",
        ],
        "claim_boundary": post_sim_request()["claim_boundary"],
    }
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    write_json(contract_path, contract)
    return {
        "helper": {"path": helper.relative_to(package).as_posix(), "bytes": helper.stat().st_size, "sha256": base.sha256(helper)},
        "request": {"path": request_path.relative_to(package).as_posix(), "bytes": request_path.stat().st_size, "sha256": base.sha256(request_path)},
        "contract": {"path": contract_path.relative_to(package).as_posix(), "bytes": contract_path.stat().st_size, "sha256": base.sha256(contract_path)},
    }


def _remove_function(path: Path, function_name: str) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function_name]
    if len(matches) != 1:
        raise BuildError(f"expected one {function_name} function in {path.name}")
    node = matches[0]
    lines = text.splitlines(keepends=True)
    del lines[node.lineno - 1 : node.end_lineno]
    path.write_text("".join(lines), encoding="utf-8", newline="\n")


def remove_legacy_positional_collectors(package: Path) -> dict[str, Any]:
    """Remove inherited, unused post-sim positional collection ABIs from p29."""
    publisher = package / "package_tools/fixed_simresult_publisher.py"
    runtime = package / "package_tools/node0004_assumed_hardware_server_runtime.py"
    numeric = package / "package_tools/node0004_assumed_hardware_server_runtime_v2_base.py"
    for path in (publisher, runtime, numeric):
        _remove_function(path, "collect")

    text = publisher.read_text(encoding="utf-8")
    old = '''    else:\n        if args.evidence_root is None or args.run_root is None:\n            raise PublishError("normal collection roots are required")\n        result = collect(\n            package_root=args.package_root.resolve(),\n            evidence_root=args.evidence_root.resolve(),\n            run_root=args.run_root.resolve(),\n            return_zip=args.return_zip,\n        )\n'''
    new = '''    else:\n        raise PublishError("normal post-sim publication is owned by server_post_sim_return.py")\n'''
    if text.count(old) != 1:
        raise BuildError("legacy fixed publisher normal branch differs")
    publisher.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

    text = runtime.read_text(encoding="utf-8")
    old = '''    col = sub.add_parser("collect")\n    col.add_argument("--server-root", type=Path, required=True)\n    col.add_argument("--evidence-root", type=Path, required=True)\n    col.add_argument("--run-root", type=Path, required=True)\n    col.add_argument("--package-root", type=Path, required=True)\n'''
    if text.count(old) != 1:
        raise BuildError("legacy family runtime collector parser differs")
    text = text.replace(old, "", 1)
    old = '''    else:\n        value = collect(\n            args.server_root,\n            args.evidence_root,\n            args.run_root,\n            args.package_root,\n        )\n'''
    new = '''    else:\n        raise RuntimeErrorContract("unknown command; post-sim publication uses the shared return core")\n'''
    if text.count(old) != 1:
        raise BuildError("legacy family runtime collector dispatch differs")
    runtime.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

    text = numeric.read_text(encoding="utf-8")
    old = '''    col = sub.add_parser("collect")\n    col.add_argument("--server-root", type=Path, required=True)\n    col.add_argument("--install-name", required=True)\n    col.add_argument("--evidence-root", type=Path, required=True)\n    col.add_argument("--run-root", type=Path, required=True)\n    col.add_argument("--cfg-root", type=Path, required=True)\n    col.add_argument("--package-root", type=Path, required=True)\n'''
    if text.count(old) != 1:
        raise BuildError("legacy numeric runtime collector parser differs")
    text = text.replace(old, "", 1)
    old = '''    else:\n        value = collect(\n            args.server_root,\n            args.install_name,\n            args.evidence_root,\n            args.run_root,\n            args.cfg_root,\n            args.package_root,\n        )\n'''
    new = '''    else:\n        raise RuntimeErrorContract("unknown command; post-sim publication uses the shared return core")\n'''
    if text.count(old) != 1:
        raise BuildError("legacy numeric runtime collector dispatch differs")
    numeric.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

    offenders: list[str] = []
    forbidden = ("def collect(", ".collect(", "base.collect", "_base_collect")
    for path in sorted((package / "package_tools").glob("*.py")):
        if path.name == "server_post_sim_return.py":
            continue
        payload = path.read_text(encoding="utf-8", errors="replace")
        if any(token in payload for token in forbidden):
            offenders.append(path.name)
    if offenders:
        raise BuildError(f"legacy positional collector surface remains: {offenders}")
    return {
        path.relative_to(package).as_posix(): {"bytes": path.stat().st_size, "sha256": base.sha256(path)}
        for path in (publisher, runtime, numeric)
    }


def patch_runner(package: Path) -> dict[str, Any]:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    needle = 'source_bound_observer="$package_root/tb_probe/source_bound_causal_observer.svh"\n'
    addition = (
        needle
        + 'post_sim_helper="$package_root/package_tools/server_post_sim_return.py"\n'
        + 'post_sim_request="$package_root/contracts/server_post_sim_return_request.json"\n'
    )
    if text.count(needle) != 1:
        raise BuildError("runner source-bound declaration differs")
    text = text.replace(needle, addition, 1)
    needle = "observer_preflight_status=125\npreflight_stage=BOOTSTRAP_ARMED\n"
    replacement = needle + "natural_terminal=false\nsimulation_started=false\n"
    if text.count(needle) != 1:
        raise BuildError("runner state declaration differs")
    text = text.replace(needle, replacement, 1)
    marker = '  python3 "$trigger_finalizer" --observer-log'
    if text.count(marker) != 1:
        raise BuildError("legacy finalizer plugin boundary differs")
    core_branch = r'''  sim_started="$simulation_started"
  if [ "$sim_started" = true ]; then
    source_bound_log="$run_root/c0/source_bound_causal.log"
    if [ -s "$run_root/c0/sim.log" ]; then
      grep '^CODEX_PROBE_V1 ' "$run_root/c0/sim.log" > "$source_bound_log" || true
    else
      : > "$source_bound_log"
    fi
    sim_exit_code="$run_status"
    [ "$sim_exit_code" -ne 125 ] || sim_exit_code="$original"
    export CODEX_PACKAGE_ROOT="$package_root"
    CODEX_ATTEMPT_ROOT="$(cd "$run_root" && pwd -P)"
    export CODEX_ATTEMPT_ROOT
    export CODEX_EXECUTION_ID="$return_tag"
    export CODEX_SIM_EXIT_CODE="$sim_exit_code"
    export CODEX_SIM_SIGNAL="$signal_status"
    export CODEX_SIM_STARTED=true
    export CODEX_NATURAL_TERMINAL="$natural_terminal"
    # RETURN_FINALIZER_STATE.json and SIM_EXIT_RECEIPT.json are persisted by the shared core before plugins.
    publication_json="$(python3 "$post_sim_helper" finalize --request "$post_sim_request")"
    collection=$?
    [ "$collection" -ne 0 ] || printf '%s\n' "$publication_json"
    final="$original"
    [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] || final="$collection"
    [ "$final" -ne 0 ] || [ "$root_gate_status" -eq 0 ] || final="$root_gate_status"
    printf 'RUNNER_FINAL_STATUS package=%s exit=%s\n' "$package_identity" "$final" >&2
    exit "$final"
  fi
  publication_json="$(python3 "$publisher" --bootstrap-partial --package-root "$package_root" --exit-code "$original" --signal-name "$signal_status" --stage "$preflight_stage" --server-root "$server_root" --return-zip "$return_zip")"
  collection=$?
  [ "$collection" -ne 0 ] || printf '%s\n' "$publication_json"
  final="$original"
  [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] || final="$collection"
  [ "$final" -ne 0 ] || [ "$root_gate_status" -eq 0 ] || final="$root_gate_status"
  printf 'RUNNER_FINAL_STATUS package=%s exit=%s\n' "$package_identity" "$final" >&2
  exit "$final"
'''
    text = text.replace(marker, core_branch + marker, 1)
    needle = "preflight_stage=PRODUCTION_SIMULATION\n"
    replacement = needle + "simulation_started=true\n"
    if text.count(needle) != 1:
        raise BuildError("production simulation boundary differs")
    text = text.replace(needle, replacement, 1)
    needle = '  python3 "$runtime" qualify-run --sim-log "$run_root/c0/sim.log" --observer-log "$observer_log" --output "$evidence_root/natural_terminal/c0.json" || runner_fail 9 "natural-terminal qualification failed"\n'
    replacement = needle + "  natural_terminal=true\n"
    if text.count(needle) != 1:
        raise BuildError("natural qualification boundary differs")
    text = text.replace(needle, replacement, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {
        "path": "PREPARE_AND_RUN.sh",
        "bytes": path.stat().st_size,
        "sha256": base.sha256(path),
        "shared_post_sim_invocations": text.count('python3 "$post_sim_helper" finalize --request "$post_sim_request"'),
        "required_env_tokens": {name: text.count(name) for name in (
            "CODEX_PACKAGE_ROOT", "CODEX_ATTEMPT_ROOT", "CODEX_EXECUTION_ID", "CODEX_SIM_EXIT_CODE",
            "CODEX_SIM_SIGNAL", "CODEX_SIM_STARTED", "CODEX_NATURAL_TERMINAL", "RETURN_FINALIZER_STATE.json",
        )},
    }


def patch_manifest(package: Path, post_sim: dict[str, Any], runner: dict[str, Any]) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if base.sha256(P28_ANALYSIS) != P28_ANALYSIS_SHA256:
        raise BuildError("formal p28 analysis identity differs")
    analysis = json.loads(P28_ANALYSIS.read_text(encoding="utf-8"))
    if analysis.get("valid") is not True or analysis.get("status") != "P28_ROW2_CLEAR_VISIBLE_READY_STILL_BLOCKED_SUCCESSOR_REQUIRED":
        raise BuildError("formal p28 analysis is not accepted")
    value.update({
        "schema": "conv-native-four-lane-0ccae916-p29-row2own-package-v1",
        "package_identity": PACKAGE_ID,
        "install_name": PACKAGE_ID,
        "workload_install_name": PACKAGE_ID,
        "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
        "return_name": f"{PACKAGE_ID}_<execution_id>_return.zip",
        "status": "PACKAGE_READY_NOT_RUN",
    })
    value["source_p28_formal_return_analysis"] = {
        "path": P28_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": P28_ANALYSIS_SHA256,
        "return_sha256": analysis["return_identity"]["sha256"],
        "source_zip_sha256": analysis["source_identity"]["sha256"],
        "classification": analysis["classification"],
        "last_progress_guard": analysis["failure_localization"]["LAST_PROVEN_GOOD"],
        "first_divergence": analysis["failure_localization"]["FIRST_DIVERGENCE"],
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p28 proves row2 read and clear; p29 distinguishes post-clear repopulation, mask coverage, and ready recomputation",
        "authorized_config_change": None,
        "numeric_w3_golden_repeated": False,
    }
    value["post_sim_return_core"] = {
        "rule_id": "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
        "enforcement": "required_next_fresh",
        "members": post_sim,
        "runner": runner,
        "sim_exit_persisted_before_plugins": True,
        "plugin_failure_blocks_core_return": False,
        "claim_boundary": post_sim_request()["claim_boundary"],
    }
    value["source_bound_observer_binding"]["claim_boundary"] = "c0 Buffer5 row2 post-clear ownership and ready recomputation only"
    value["release_gate_applicability"].update({
        "post_sim_return_core": "blocking_applicable_required_next_fresh",
        "materialized_config": "receipt_reuse_byte_equal_p28",
        "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
    })
    value["release_gate_matrix"].update({
        "post_sim_return_core": {
            "applicability": "blocking_applicable",
            "blocking": True,
            "pass": None,
            "enforcement": "required_next_fresh",
            "scope": "filled by exact shared final-ZIP scenario validator",
        },
        "materialized_config": {
            "applicability": "receipt_reuse",
            "blocking": False,
            "pass": True,
            "scope": "87 p28 installed payload members byte-equal and SCA identity-normalized equal",
            "causal_transaction_ledger": "receipt_reuse_p18",
            "boundary_microtrace": "receipt_reuse_p18",
            "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
        },
    })
    contract = json.loads((package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(encoding="utf-8"))
    paths = base.projected_paths(package, contract)
    longest = max(paths, key=lambda item: (len(item), item))
    inner = [item.relative_to(package).as_posix() for item in package.rglob("*") if item.is_file() and item != path] + ["package_manifest.json"]
    value["path_length_budget"].update({
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": contract["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest),
        "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{relative}") for relative in inner),
        "max_inner_suffix_chars": max(map(len, inner)),
        "max_inner_depth": max(len(PurePosixPath(relative).parts) for relative in inner),
        "max_inner_component_chars": max(len(part) for relative in inner for part in PurePosixPath(relative).parts),
        "outer_identity_repeated_inside": False,
    })
    base.refresh_manifest_files(package, value)
    write_json(path, value)


def patch_contract_and_docs(package: Path) -> None:
    contract_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["claim_boundary"] = "p29 preserves p28 payload/config and changes only generated row2 ownership diagnostics plus shared post-sim return core."
    paths = base.projected_paths(package, contract)
    longest = max(paths, key=lambda item: (len(item), item))
    contract["path_budget"]["max_projected_absolute_path_chars"] = contract["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    write_json(contract_path, contract)
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value.update({"schema": "conv-native-four-lane-p29-row2own-pointer-v1", "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN"})
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p29 row2 ownership diagnostic\n\n"
        "Fresh successor of tested p28. It preserves the 87 installed payload members and uses generated source-bound diagnostics to distinguish row2 post-clear ownership. The shared post-sim return core publishes independently of parser success.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8", newline="\n",
    )


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_prior()
    package, inherited = prior.build_directory(destination)
    removed_collectors = remove_legacy_positional_collectors(package)
    post_sim = install_post_sim_contract(package)
    runner = patch_runner(package)
    patch_contract_and_docs(package)
    patch_manifest(package, post_sim, runner)
    return package, {"inherited": inherited, "removed_collectors": removed_collectors, "post_sim": post_sim, "runner": runner}


def frozen_checks(package: Path) -> dict[str, Any]:
    frozen = prior.frozen_checks(package)
    frozen["source_p28_zip_sha256"] = SOURCE_SHA256
    return frozen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = (output / PACKAGE_ID, output / f"{PACKAGE_ID}.zip", output / f"{PACKAGE_ID}.zip.sha256", output / f"{PACKAGE_ID}.build.json")
    if any(target.exists() for target in targets):
        raise BuildError("refusing to overwrite p29 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p28 source differs")
    package, receipts = build_directory(output)
    frozen = frozen_checks(package)
    if not frozen["frozen_install_payload_byte_equal"] or not frozen["legacy_observer_byte_equal"] or not all(frozen["sca_identity_normalized_equal"].values()) or frozen["frozen_install_payload_member_count"] != 87:
        raise BuildError("frozen p28 payload differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    with tempfile.TemporaryDirectory(prefix=".p29_repeat_", dir=ROOT) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeat_zip = Path(temporary) / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p29 deterministic double build differs")
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p29-row2own-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "source_p28_zip_sha256": SOURCE_SHA256,
        "source_p28_analysis_sha256": P28_ANALYSIS_SHA256,
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha,
        "deterministic_double_build": deterministic,
        "receipts": receipts,
        "frozen": frozen,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
