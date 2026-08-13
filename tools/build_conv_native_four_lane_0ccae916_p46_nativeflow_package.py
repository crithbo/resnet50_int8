#!/usr/bin/env python3
"""Build the p46 native-flow observer successor from consumed/tested p45."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p45_obswide"
PACKAGE_ID = "r5_n4_0cc_p46_nativeflow"
FAMILY = "conv_native_four_lane"
ACTIVATION_EPOCH = "runtime-preflight-native-flow-v1"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/tested"
    / FAMILY
    / SOURCE_ID
    / f"{SOURCE_ID}.zip"
)
SOURCE_BYTES = 5_974_378
SOURCE_SHA = "fda80c374db7f906abc9e0dcbed768d64e58ab1e8351e90867abdb79e8d99e5c"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p46_nativeflow_release"
TREE = OUT / "build" / PACKAGE_ID
ZIP = OUT / f"{PACKAGE_ID}.zip"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def write(relative: str, data: bytes, *, executable: bool = False) -> Path:
    path = TREE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def write_json(relative: str, value: object) -> Path:
    return write(relative, canonical(value))


def identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load_base() -> Any:
    path = ROOT / "tools/build_conv_native_four_lane_0ccae916_p45_obswide_package.py"
    spec = importlib.util.spec_from_file_location("conv_native_p45_builder_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load p45 builder base")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runner() -> str:
    return r'''#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
package_id="__PACKAGE_ID__"
install_name="__PACKAGE_ID__"
attempt="a0"
return_tag="r$(date -u +%s%N)_$$"
server_root="${1-}"
result_root="/home/panqs/ndp/simresult"
return_zip="$result_root/${package_id}_${return_tag}_return.zip"
return_sha="${return_zip}.sha256"
package_root=""
case "${BASH_SOURCE[0]}" in /*) package_root="${BASH_SOURCE[0]%/*}";; */*) package_root="$PWD/${BASH_SOURCE[0]%/*}";; *) package_root="$PWD";; esac
bootstrap_root="${server_root}/install/codex_runs/${package_id}/${attempt}/evidence/compile_bootstrap"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_log_receipt_json="$bootstrap_root/compile_log_receipt.json"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
compile_status=125
run_status=125
signal_status=NONE
sim_started=false
timed_out=false
finalized=0
run_root=""
evidence_root=""
compile_root=""
cfg_root=""
source_identity_status=NOT_STARTED
preflight_stage=ARGUMENT_SYNTAX
observer_chunk=""
source_bound_observer="$package_root/tb_probe/source_bound_causal_observer.svh"
wide_observer="$package_root/tb_probe/observer_only_wide_causal.svh"
simv=""

# Exact return bindings: ACTUAL_COMPILE_SIM_ARGV.json SIM_EXIT_RECEIPT.json
# COMPILE_CORE.json compile_driver.log compile_first_error.txt
# PROCESS_TREE_RECEIPT.json SIM_TIME_HEARTBEAT.json OBSERVER_SIGNAL_CATALOG.json
# OBSERVER_EVENT_INDEX.json OBSERVER_DECISION.json events-000000.jsonl
# DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RETURN_FINALIZER_STATE.json
runner_fail() { code="$1"; shift; printf 'RUNNER_ERROR package=%s code=%s message=%s\n' "$package_id" "$code" "$*" >&2; exit "$code"; }
bootstrap_finalize() {
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1
  trap - EXIT INT TERM HUP
  set +e
  python3 "$package_root/package_tools/fixed_simresult_publisher.py" --bootstrap-partial --package-root "$package_root" --exit-code "$original" --signal-name "$signal_status" --stage "$preflight_stage" --server-root "$server_root" --bootstrap-root "$bootstrap_root" --return-zip "$return_zip"
  publish_rc=$?
  [ "$original" -ne 0 ] || original="$publish_rc"
  printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$original" "$return_zip" >&2
  exit "$original"
}
on_bootstrap_signal() { signal_status="$1"; bootstrap_finalize "$2"; }
trap 'bootstrap_finalize $?' EXIT
trap 'on_bootstrap_signal HUP 129' HUP
trap 'on_bootstrap_signal INT 130' INT
trap 'on_bootstrap_signal TERM 143' TERM

[ "$#" -eq 1 ] || runner_fail 2 "usage requires one absolute server root"
case "$1" in /*) ;; *) runner_fail 2 "server root argument must be absolute";; esac
# CODEX_PRODUCTION_LAUNCH

finalize() {
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1
  trap - EXIT INT TERM HUP
  set +e
  if [ -z "$evidence_root" ] || [ ! -d "$evidence_root" ]; then
    python3 "$package_root/package_tools/fixed_simresult_publisher.py" --bootstrap-partial --package-root "$package_root" --exit-code "$original" --signal-name "$signal_status" --stage "$preflight_stage" --server-root "$server_root" --bootstrap-root "$bootstrap_root" --return-zip "$return_zip"
    publish_rc=$?
    [ "$original" -ne 0 ] || original="$publish_rc"
    printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$original" "$return_zip" >&2
    exit "$original"
  fi
  mkdir -p "$evidence_root/compile_rootcause" "$evidence_root/observer" "$run_root/c0"
  return_args=""
  [ "$sim_started" = true ] && return_args="$return_args --simulation-started"
  [ "$timed_out" = true ] && return_args="$return_args --timed-out"
  python3 "$package_root/package_tools/compile_core_evidence.py" return-core --output-root "$bootstrap_root" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --compile-exit "$compile_status" --sim-exit "$run_status" $return_args --signal "$signal_status"
  for name in compile_argv.json compile_source_identity.json compile_exit.txt compile_driver.log compile_log_receipt.json compile_log_head.txt compile_log_tail.txt compile_first_error.txt COMPILE_CORE.json NATIVE_FLOW_FAILURE_DIFFERENTIAL.json; do
    [ ! -f "$bootstrap_root/$name" ] || cp -f "$bootstrap_root/$name" "$evidence_root/compile_rootcause/$name"
  done
  [ ! -f "$bootstrap_root/ACTUAL_COMPILE_SIM_ARGV.json" ] || cp -f "$bootstrap_root/ACTUAL_COMPILE_SIM_ARGV.json" "$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json"
  [ ! -f "$bootstrap_root/SIM_EXIT_RECEIPT.json" ] || cp -f "$bootstrap_root/SIM_EXIT_RECEIPT.json" "$evidence_root/observer/SIM_EXIT_RECEIPT.json"
  observer_rc=0
  if [ "$sim_started" = true ]; then
    grep '^CODEX_PROBE_V1 ' "$run_root/c0/sim.log" > "$run_root/c0/source_bound_causal.log" || true
    python3 "$package_root/package_tools/source_bound_causal_parser.py" --log "$run_root/c0/source_bound_causal.log" --output "$evidence_root/source_bound_causal_decision.json" >/dev/null 2>&1 || true
    python3 "$package_root/package_tools/node0004_observerwide_event_parser.py" --contract "$package_root/contracts/observer_only_wide_causal_contract.json" --chunk "$evidence_root/observer/chunks/events-000000.jsonl" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --exit-code "$run_status" --signal "$signal_status" --timed-out "$timed_out" --simulation-started true --process-receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" --heartbeat-log "$evidence_root/supervisor_heartbeat.jsonl" --actual-argv "$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json" --output-dir "$evidence_root/observer"
    observer_rc=$?
  fi
  export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag" CODEX_ATTEMPT_ID="$attempt" CODEX_PACKAGE_ID="$package_id" CODEX_SIM_EXIT_CODE="$run_status" CODEX_SIM_SIGNAL="$signal_status" CODEX_SIM_STARTED="$sim_started" CODEX_NATURAL_TERMINAL=false
  [ "$run_status" -eq 0 ] && export CODEX_NATURAL_TERMINAL=true
  python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"
  core_rc=$?
  manifest_rc=98
  if [ -f "$return_zip" ]; then
    python3 "$package_root/package_tools/node0004_observerwide_return_manifest.py" --zip "$return_zip" --contract "$package_root/contracts/observer_only_wide_causal_contract.json" --sidecar "$return_sha"
    manifest_rc=$?
  fi
  final="$original"
  [ "$final" -ne 0 ] || [ "$core_rc" -eq 0 ] || final="$core_rc"
  [ "$sim_started" = false ] || [ "$observer_rc" -eq 0 ] || final=97
  [ "$manifest_rc" -eq 0 ] || final=98
  printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$final" "$return_zip" >&2
  exit "$final"
}
on_signal() { signal_status="$1"; finalize "$2"; }
finalized=0
trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM

preflight_stage=NATIVE_CD
cd "$server_root" || runner_fail 4 "native production cd failed; inspect returned cwd and exit"
server_root="$PWD"
cfg_root="$server_root/install/cfg_pkg/$package_id"
run_root="$server_root/install/codex_runs/$package_id/$attempt"
evidence_root="$server_root/install/codex_runs/$package_id/$attempt/evidence"
compile_root="$server_root/install/codex_runs/$package_id/$attempt/compile"
bootstrap_root="$evidence_root/compile_bootstrap"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_log_receipt_json="$bootstrap_root/compile_log_receipt.json"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
preflight_stage=NATIVE_PACKAGE_INSTALL
rm -rf -- "$cfg_root" "$run_root"
layout_mode=CODEX_DIRECT_PACKAGE_OWNED_LAYOUT
mkdir -p "$cfg_root" "$compile_root/sim_results" "$run_root/c0" "$evidence_root/observer/chunks" "$evidence_root/compiled_source" "$bootstrap_root" "$result_root" || runner_fail 14 "native package-owned install directories could not be created"
cp -a "$package_root/workload/runtime/." "$cfg_root/" || runner_fail 6 "native package-owned workload install failed"
observer_chunk="$evidence_root/observer/chunks/events-000000.jsonl"
python3 "$package_root/package_tools/compile_core_evidence.py" prepare --output-root "$bootstrap_root" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --cwd "$server_root" --makefile-name Makefile.tb_NDP_Top_new_phy --source "$source_bound_observer" --source "$wide_observer" --package-root "$package_root" --run-dir "$compile_root" --attempt-root "$run_root" --sca-cfg "$cfg_root/runs/c0/sca_cfg.json" --sca-cfg-d "$cfg_root/runs/c0/sca_cfg_D.json" --observer-chunk "$observer_chunk" --repeat-num 1 || runner_fail 8 "compile-core actual argv bootstrap failed"

preflight_stage=PRODUCTION_COMPILE
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$compile_root" VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe $source_bound_observer $wide_observer" > "$compile_driver_log" 2>&1
compile_status=$?
set -e
python3 "$package_root/package_tools/compile_core_evidence.py" finalize --output-root "$bootstrap_root" --exit-code "$compile_status" || runner_fail 8 "compile-core post-actual-command finalize failed"
[ "$compile_status" -eq 0 ] || exit "$compile_status"
set +e
python3 "$package_root/package_tools/conv_native_observerwide_source_identity.py" --server-root "$server_root" --compile-log "$compile_driver_log" --compile-exit "$compile_exit_txt" --contract "$package_root/contracts/observer_only_wide_causal_contract.json" --output-dir "$evidence_root/compiled_source" --output "$evidence_root/compiled_source/source_identity.json"
source_rc=$?
set -e
source_identity_status=DIAGNOSTIC_EVIDENCE_INCOMPLETE
[ "$source_rc" -eq 0 ] && source_identity_status=COMPLETE
simv="$compile_root/sim_results/simv"
printf '%s\n' "$simv -l $run_root/c0/sim.log +SCA_CFG=$cfg_root/runs/c0/sca_cfg.json +SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json +CODEX_CAUSAL_OBSERVER +CODEX_OBSERVER_ONLY_WIDE_CAUSAL +CODEX_OBSERVER_CHUNK=$observer_chunk" > "$run_root/c0/simulator_argv.txt"
preflight_stage=PRODUCTION_SIMULATION
sim_started=true
set +e
DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/package_tools/server_observer_runtime_supervision.py" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --heartbeat-source "$run_root/c0/sim.log" --heartbeat-output "$evidence_root/supervisor_heartbeat.jsonl" --heartbeat-regex 'CODEX_OBSERVER_SIM_TIME_V1 sim_time=([0-9]+)' --timescale 1ps --timeout 43200 --interval 30 --grace 30 --receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" -- "$simv" -l "$run_root/c0/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" +CODEX_CAUSAL_OBSERVER +CODEX_OBSERVER_ONLY_WIDE_CAUSAL "+CODEX_OBSERVER_CHUNK=$observer_chunk" "+CODEX_PACKAGE_ID=$package_id" "+CODEX_EXECUTION_ID=$return_tag" "+CODEX_ATTEMPT_ID=$attempt"
run_status=$?
set -e
[ "$run_status" -eq 124 ] && timed_out=true
[ "$run_status" -eq 129 ] && signal_status=HUP
[ "$run_status" -eq 130 ] && signal_status=INT
[ "$run_status" -eq 143 ] && signal_status=TERM
exit "$run_status"
'''.replace("__PACKAGE_ID__", PACKAGE_ID)


def post_request() -> dict[str, Any]:
    def entry(root: str, source: str, archive: str, required: bool = False) -> dict[str, Any]:
        return {"source_root": root, "source": source, "archive": archive, "required": required}

    rows = [
        entry("package", "package_manifest.json", "evidence/returned_package_manifest.json", True),
        entry("package", "contracts/observer_only_wide_causal_contract.json", "evidence/observer_only_wide_causal_contract.json", True),
        entry("package", "contracts/native_flow_failure_differential_contract.json", "evidence/native_flow_failure_differential_contract.json", True),
        entry("package", "diagnostics/source_bound_probe_binding.json", "evidence/source_bound_probe_binding.json", True),
        entry("attempt", "evidence/ACTUAL_COMPILE_SIM_ARGV.json", "evidence/ACTUAL_COMPILE_SIM_ARGV.json", True),
        entry("attempt", "evidence/observer/SIM_EXIT_RECEIPT.json", "evidence/observer/SIM_EXIT_RECEIPT.json", True),
        entry("attempt", "evidence/compile_rootcause/COMPILE_CORE.json", "evidence/compile_rootcause/COMPILE_CORE.json", True),
        entry("attempt", "evidence/compile_rootcause/compile_driver.log", "evidence/compile_rootcause/compile_driver.log", True),
        entry("attempt", "evidence/compile_rootcause/compile_log_receipt.json", "evidence/compile_rootcause/compile_log_receipt.json", True),
        entry("attempt", "evidence/compile_rootcause/compile_first_error.txt", "evidence/compile_rootcause/compile_first_error.txt", True),
        entry("attempt", "evidence/compile_rootcause/compile_argv.json", "evidence/compile_rootcause/compile_argv.json", True),
        entry("attempt", "evidence/compile_rootcause/compile_source_identity.json", "evidence/compile_rootcause/compile_source_identity.json", True),
        entry("attempt", "evidence/compile_rootcause/compile_exit.txt", "evidence/compile_rootcause/compile_exit.txt", True),
        entry("attempt", "evidence/compile_rootcause/compile_log_head.txt", "evidence/compile_rootcause/compile_log_head.txt"),
        entry("attempt", "evidence/compile_rootcause/compile_log_tail.txt", "evidence/compile_rootcause/compile_log_tail.txt"),
        entry("attempt", "evidence/compile_rootcause/NATIVE_FLOW_FAILURE_DIFFERENTIAL.json", "evidence/compile_rootcause/NATIVE_FLOW_FAILURE_DIFFERENTIAL.json", True),
        entry("attempt", "evidence/PROCESS_TREE_RECEIPT.json", "evidence/PROCESS_TREE_RECEIPT.json"),
        entry("attempt", "evidence/observer/SIM_TIME_HEARTBEAT.json", "evidence/observer/SIM_TIME_HEARTBEAT.json"),
        entry("attempt", "evidence/observer/OBSERVER_SIGNAL_CATALOG.json", "evidence/observer/OBSERVER_SIGNAL_CATALOG.json"),
        entry("attempt", "evidence/observer/OBSERVER_EVENT_INDEX.json", "evidence/observer/OBSERVER_EVENT_INDEX.json"),
        entry("attempt", "evidence/observer/OBSERVER_DECISION.json", "evidence/observer/OBSERVER_DECISION.json"),
        entry("attempt", "evidence/observer/chunks/events-000000.jsonl", "observer/chunks/events-000000.jsonl"),
        entry("attempt", "evidence/compiled_source/source_identity.json", "evidence/compiled_source/source_identity.json"),
        entry("attempt", "evidence/source_bound_causal_decision.json", "evidence/source_bound_causal_decision.json"),
        entry("attempt", "c0/source_bound_causal.log", "runs/c0/source_bound_causal.log"),
        entry("attempt", "c0/sim.log", "runs/c0/sim.log"),
        entry("attempt", "c0/simulator_argv.txt", "runs/c0/simulator_argv.txt"),
    ]
    return {
        "schema": "server-post-sim-return-request-v1",
        "package_id": PACKAGE_ID,
        "result_root": "/home/panqs/ndp/simresult",
        "return_basename_template": "{package_id}_{execution_id}_return.zip",
        "core_entries": rows,
        "plugins": [],
        "max_plugin_output_bytes": 262144,
        "claim_boundary": "Native-flow actual-command and observer-only core publication; family interpretation remains post-return.",
    }


def native_flow_contract() -> dict[str, Any]:
    dispatch = json.loads((ROOT / "contracts/server_runtime_preflight_native_flow_dispatch_v1.json").read_text(encoding="utf-8"))
    return {
        "schema": "conv-native-native-flow-failure-differential-contract-v1",
        "package_id": PACKAGE_ID,
        "activation_epoch": ACTIVATION_EPOCH,
        "production_launch_marker": "# CODEX_PRODUCTION_LAUNCH",
        "server_environment_adjudicator": "ACTUAL_PRODUCTION_COMMAND_ONLY",
        "provider_preflight_performed": False,
        "required_attempt_fields": dispatch["native_failure_differential"]["required_attempt_fields"],
        "reference_paths": dispatch["native_failure_differential"]["required_reference_paths"],
        "classifications": dispatch["native_failure_differential"]["classifications"],
        "unknown_semantics": dispatch["native_failure_differential"]["unknown_semantics"],
        "claim_boundary": dispatch["claim_boundary"],
    }


def runtime_layout_contract() -> dict[str, Any]:
    helper = TREE / "package_tools/server_package_runtime_layout.py"
    cfg = f"install/cfg_pkg/{PACKAGE_ID}"
    attempt = "a" * 48
    projected: set[str] = set()
    prefix = "workload/runtime/"
    for path in TREE.rglob("*"):
        if path.is_file():
            relative = path.relative_to(TREE).as_posix()
            if relative.startswith(prefix):
                projected.add(f"{cfg}/{relative[len(prefix):]}")
    roots = {
        "cfg_root": cfg,
        "run_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}",
        "evidence_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence",
        "compile_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/compile",
    }
    additional = [
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/compile_rootcause/compile_driver.log",
        f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/observer/chunks/events-000000.jsonl",
    ]
    candidates = projected | {value.replace("{attempt}", attempt) for value in roots.values()} | {value.replace("{attempt}", attempt) for value in additional}
    longest = max(candidates, key=lambda value: (len(value), value))
    root_max = 128
    absolute_limit = 1024
    projected_absolute = root_max + 1 + len(longest)
    contract = {
        "schema": "server_package_runtime_layout_v1",
        "package_id": PACKAGE_ID,
        "install_name": PACKAGE_ID,
        "runner_member": "PREPARE_AND_RUN.sh",
        "manifest_member": "package_manifest.json",
        "shared_layout_helper": {"member": "package_tools/server_package_runtime_layout.py", "sha256": sha(helper)},
        "tb_cwd": "$server_root",
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "required_preexisting_parents": ["install"],
        "package_creatable_parent_dirs": ["install/cfg_pkg", "install/codex_runs"],
        "runtime_roots": roots,
        "payload_mounts": [{"source_prefix": prefix, "runtime_prefix": f"{cfg}/"}],
        "sca_consumers": [
            {"plusarg": "SCA_CFG", "member": "workload/runtime/runs/c0/sca_cfg.json", "mode": "read_inputs"},
            {"plusarg": "SCA_CFG_D", "member": "workload/runtime/runs/c0/sca_cfg_D.json", "mode": "write_outputs"},
        ],
        "runner_bindings": {
            "layout_prepare_marker": "layout_mode=CODEX_DIRECT_PACKAGE_OWNED_LAYOUT",
            "tb_cwd_marker": 'cd "$server_root"',
            "compile_marker": "preflight_stage=PRODUCTION_COMPILE",
            "simulation_marker": "preflight_stage=PRODUCTION_SIMULATION",
        },
        "path_budget": {
            "attempt_max_chars": 48,
            "declared_target_root_max_chars": root_max,
            "max_projected_absolute_path_chars": projected_absolute,
            "absolute_path_limit_chars": absolute_limit,
            "additional_projected_paths": additional,
        },
        "repeat_execution": {
            "mode": "RESET_EXACT_PACKAGE_OWNED_RUNTIME_ROOTS",
            "cfg_root_policy": "RESET_AND_RECREATE_EXACT_INSTALL_NAME",
            "run_root_policy": "RESET_AND_RECREATE_EXACT_PACKAGE_ATTEMPT",
            "foreign_sibling_policy": "PRESERVE",
            "symlink_or_special_entry_policy": "FAIL_CLOSED",
            "ownership_marker": ".codex_owner.{name}.json",
            "return_name_policy": "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS",
        },
        "finalizer": {
            "arm_marker": "trap 'bootstrap_finalize $?' EXIT",
            "first_preflight_marker": '[ "$#" -eq 1 ]',
            "required_scenarios": ["normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM"],
        },
        "claim_boundary": "Direct package-owned install/runtime layout and fixed return publication only; no server, DUT, terminal, D, E4 or E5 claim.",
    }
    return contract


def update_manifest(contract: dict[str, Any]) -> None:
    manifest_path = TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    budget = contract["path_budget"]
    attempt = "a" * budget["attempt_max_chars"]
    candidates: set[str] = set()
    for mount in contract["payload_mounts"]:
        for path in TREE.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(TREE).as_posix()
            if relative.startswith(mount["source_prefix"]):
                candidates.add(mount["runtime_prefix"] + relative[len(mount["source_prefix"]):])
    candidates.update(value.replace("{attempt}", attempt) for value in contract["runtime_roots"].values())
    candidates.update(value.replace("{attempt}", attempt) for value in budget["additional_projected_paths"])
    longest = max(candidates, key=lambda value: (len(value), value))
    manifest.update(
        {
            "schema": "conv-native-four-lane-p46-native-flow-package-v1",
            "package_identity": PACKAGE_ID,
            "install_name": PACKAGE_ID,
            "status": "PACKAGE_READY_NOT_RUN",
            "activation_epoch": ACTIVATION_EPOCH,
            "base_epoch": "observer-only-wide-causal-v1",
            "first_fresh_after_change": True,
            "source_package": SOURCE_ID,
            "observer_only_contract_sha256": sha(TREE / "contracts/observer_only_wide_causal_contract.json"),
            "previous_version_progress": "p41 passed production compile beyond the Datahub repair; p42 fixed the two-bit vector predicate; p45 broad observer compile failed at unresolved DW_ecc/DW_sync/DW_lod/DW_fifo_s1_sf before simulation.",
            "current_purpose": "Run the corrected p42-equivalent MSE4 diagnostic through the native production path without provider preflight and return exact native-flow compile/simulation/observer evidence.",
            "dump_values": {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0},
            "frozen": {"config": True, "numeric": True, "workload": True, "golden": True, "functional_rtl": True, "target_diagnostic": True},
            "runtime_preflight_noninterference": {"marker": "# CODEX_PRODUCTION_LAUNCH", "server_environment_adjudicator": "ACTUAL_PRODUCTION_COMMAND_ONLY", "provider_preflight": False},
            "server_actions_performed": [],
        }
    )
    manifest["path_length_budget"].update(
        {
            "declared_target_root_max_chars": budget["declared_target_root_max_chars"],
            "longest_projected_relative_path": longest,
            "longest_projected_relative_path_chars": len(longest),
            "max_projected_absolute_path_chars": budget["declared_target_root_max_chars"] + 1 + len(longest),
            "absolute_path_limit_chars": budget["absolute_path_limit_chars"],
        }
    )
    manifest["files"] = {
        path.relative_to(TREE).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(item for item in TREE.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    }
    manifest_path.write_bytes(canonical(manifest))


def patch_tree(base: Any) -> None:
    stale_build_receipt = TREE / "build_receipt.json"
    if stale_build_receipt.exists():
        stale_build_receipt.unlink()
    stale_frozen = TREE / "provenance/frozen_p44_surface.json"
    if stale_frozen.exists():
        frozen_value = json.loads(stale_frozen.read_text(encoding="utf-8"))
        write_json("provenance/frozen_p45_surface.json", frozen_value)
        stale_frozen.unlink()
    write("package_tools/compile_core_evidence.py", (ROOT / "tools/conv_native_p46_nativeflow_compile_core.py").read_bytes(), executable=True)
    write("package_tools/server_package_runtime_layout.py", (ROOT / "tools/server_package_runtime_layout.py").read_bytes(), executable=True)
    runner_path = write("PREPARE_AND_RUN.sh", runner().encode("utf-8"), executable=True)
    request_path = write_json("contracts/server_post_sim_return_request.json", post_request())
    native_path = write_json("contracts/native_flow_failure_differential_contract.json", native_flow_contract())

    observer = json.loads((TREE / "contracts/observer_only_wide_causal_contract.json").read_text(encoding="utf-8"))
    observer["claim_boundary"] = "Frozen p42 vector predicate and MSE4 target with exact native-flow actual-command and broad observer transport; production result remains unclaimed."
    write_json("contracts/observer_only_wide_causal_contract.json", observer)
    root = f"{PACKAGE_ID}_return/"
    allowlist = json.loads((TREE / "RETURN_ALLOWLIST.json").read_text(encoding="utf-8"))
    allowlist["required"] = sorted(set(allowlist["required"] + [
        root + "evidence/compile_rootcause/compile_driver.log",
        root + "evidence/compile_rootcause/compile_log_receipt.json",
        root + "evidence/compile_rootcause/compile_argv.json",
        root + "evidence/compile_rootcause/compile_source_identity.json",
        root + "evidence/compile_rootcause/compile_exit.txt",
        root + "evidence/compile_rootcause/NATIVE_FLOW_FAILURE_DIFFERENTIAL.json",
    ]))
    write_json("RETURN_ALLOWLIST.json", allowlist)

    post_contract = json.loads((TREE / "contracts/server_post_sim_return_contract.json").read_text(encoding="utf-8"))
    post_contract["request_sha256"] = sha(request_path)
    post_contract["claim_boundary"] = "Native-flow actual-command, complete compile-core and observer-only return publication; family interpretation remains separate."
    write_json("contracts/server_post_sim_return_contract.json", post_contract)

    runner_contract = {
        "schema": "server-runner-return-resilience-contract-v1",
        "package_id": PACKAGE_ID,
        "runner_path": f"{PACKAGE_ID}/PREPARE_AND_RUN.sh",
        "runner_sha256": sha(runner_path),
        "nounset_required": True,
        "bootstrap_root_variable": "bootstrap_root",
        "package_owned_variables": [
            "package_id", "install_name", "attempt", "return_tag", "server_root", "result_root", "return_zip", "return_sha", "package_root", "bootstrap_root", "compile_argv_json", "compile_source_identity_json", "compile_exit_txt", "compile_driver_log", "compile_log_receipt_json", "compile_log_head_txt", "compile_log_tail_txt", "compile_first_error_txt", "compile_status", "run_status", "signal_status", "sim_started", "timed_out", "finalized", "run_root", "evidence_root", "compile_root", "cfg_root", "source_identity_status", "preflight_stage", "observer_chunk", "source_bound_observer", "wide_observer", "simv"
        ],
        "finalizer_arm_tokens": ["trap 'bootstrap_finalize $?' EXIT"],
        "first_fallible_tokens": ['cd "$server_root"', "make -f"],
        "compile_evidence_tokens": {
            "argv": "compile_argv.json",
            "source_identity": "compile_source_identity.json",
            "exit_code": "compile_exit.txt",
            "driver_log": "compile_driver.log",
            "first_error": "compile_first_error.txt",
            "bounded_head": "compile_log_head.txt",
            "bounded_tail": "compile_log_tail.txt",
        },
        "return_allowlist_tokens": ["ACTUAL_COMPILE_SIM_ARGV.json", "SIM_EXIT_RECEIPT.json", "COMPILE_CORE.json", "compile_log_receipt.json", "NATIVE_FLOW_FAILURE_DIFFERENTIAL.json", "PROCESS_TREE_RECEIPT.json", "OBSERVER_EVENT_INDEX.json", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
    }
    write_json("server_runner_return_resilience_contract.json", runner_contract)
    layout = runtime_layout_contract()
    write_json("SERVER_RUNTIME_LAYOUT_CONTRACT.json", layout)

    pointer = json.loads((TREE / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    pointer.update({"schema": "conv-native-four-lane-p46-native-flow-pointer-v1", "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN", "activation_epoch": ACTIVATION_EPOCH, "observer_only_contract_sha256": sha(TREE / "contracts/observer_only_wide_causal_contract.json"), "server_actions_performed": []})
    write_json("TEST_PACKAGE_MANIFEST.json", pointer)
    source_bound = json.loads((TREE / "diagnostics/source_bound_final_zip_contract.json").read_text(encoding="utf-8"))
    source_bound["claim_boundary"] = "Fresh p46 source-bound p42/MSE4 observer with native-flow actual-command evidence; production result remains unclaimed."
    write_json("diagnostics/source_bound_final_zip_contract.json", source_bound)
    write_json("diagnostics/runtime_preflight_noninterference_contract.json", {"schema": "conv-native-runtime-preflight-noninterference-v1", "package_id": PACKAGE_ID, "activation_epoch": ACTIVATION_EPOCH, "runner_sha256": sha(runner_path), "production_launch_marker": "# CODEX_PRODUCTION_LAUNCH", "marker_count_required": 1, "provider_preflight_performed": False, "server_environment_adjudicator": "ACTUAL_PRODUCTION_COMMAND_ONLY", "native_flow_contract": {"path": native_path.relative_to(TREE).as_posix(), "sha256": sha(native_path)}, "pass": True})
    write("README.md", f"# {PACKAGE_ID}\n\nPrevious progress: p41 passed production compile beyond the Datahub repair; p42 fixed the two-bit vector valid/ready scalar false-negative; p45 broad observer compilation failed at unresolved DW_ecc/DW_sync/DW_lod/DW_fifo_s1_sf before simulation.\n\nCurrent purpose: run the corrected p42-equivalent MSE4 wdata/slice-finish diagnostic through the native production path without provider preflight and return exact native-flow compile, simulation and broad observer evidence.\n\nRun only after separate authorization: `bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\nThe observer evidence threshold is decimal 100000000 bytes and warning-only. There is no hard byte, file, event or time-window cap, sampling, truncation or size deletion.\n".encode("utf-8"))
    update_manifest(layout)
    base.reject_retired_text()


def build() -> None:
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or sha(SOURCE_ZIP) != SOURCE_SHA:
        raise RuntimeError("consumed/tested p45 identity drift")
    base = load_base()
    base.OLD_ID = SOURCE_ID
    base.PACKAGE_ID = PACKAGE_ID
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_BYTES = SOURCE_BYTES
    base.SOURCE_SHA = SOURCE_SHA
    base.OUT = OUT
    base.BUILD_PARENT = OUT / "build"
    base.TREE = TREE
    base.ZIP = ZIP
    base.build()
    patch_tree(base)
    base.deterministic_zip(ZIP)
    repeat = OUT / f"{PACKAGE_ID}.repeat.zip"
    base.deterministic_zip(repeat)
    if sha(repeat) != sha(ZIP):
        raise RuntimeError("p46 deterministic ZIP mismatch")
    receipt = {
        "schema": "conv-native-p46-native-flow-build-v1",
        "package_id": PACKAGE_ID,
        "family": FAMILY,
        "activation_epoch": ACTIVATION_EPOCH,
        "source_p45": identity(SOURCE_ZIP),
        "zip": identity(ZIP),
        "repeat_zip": identity(repeat),
        "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "target_diagnostic"],
        "dump_values": {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0},
        "server_actions_performed": [],
        "pass": True,
    }
    (OUT / "build_receipt.json").write_bytes(canonical(receipt))


if __name__ == "__main__":
    build()
