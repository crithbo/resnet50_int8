from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_node0007_nested_lc_v4 import ROOT_REL
from resnet50_pipeline.qlinearadd_node0007_nested_lc_v4_closure import (
    validate_closure as _validate_v4_closure,
)
from tools import build_qlinearadd_node0007_server_package as implementation
from tools.qlinearadd_node0007_server_runtime import (
    file_records,
    preflight as runtime_preflight,
)


INSTALL_NAME = "r5_qadd_n7_nested_lc_progress_v5"
CONTRACT_REL = Path(
    "contracts/operator_config/"
    "qlinearadd_node0007_nested_lc_progress_diagnostic_v5.json"
)
TASK_RECORD_REL = Path(
    ".agents/task_records/"
    "20260730_qlinearadd_node0007_nested_lc_v4_return_analysis.md"
)
SERVER_RULE_REL = Path(".agents/rules/服务器测试包生成规则.md")
SERVER_RULE_SHA256 = (
    "2e5cf649cd721f4444b0caca2d1ea6670823c02d9d86784d6d228351ea8c7227"
)
HEARTBEAT_CYCLES = 262_144
STALL_WINDOW_CYCLES = 1_048_576
HOST_SAMPLE_SECONDS = 60
DEEP_LIMIT = 64
PROGRESS_ALLOWLIST_COUNT = 7
ACCEPTED_RECEIPT_ONLY_DRIFT = {
    "active hardware-field rule SHA drifted",
    "active QLinearAdd rule SHA drifted",
}


def _validate_reused_v4_closure(root: Path) -> dict[str, object]:
    """Reuse the mainline-accepted v4 E2 facts without mutating its receipts."""
    report = _validate_v4_closure(root)
    if set(report.get("errors", [])) != ACCEPTED_RECEIPT_ONLY_DRIFT:
        return report

    request_facts = report.get("final_request_facts", {})
    simulator = report.get("config_bound_simulator", {})
    equivalence = report.get("nested_lc_ordered_equivalence", {})
    bounds = report.get("static_signed_feedback_bounds", {})
    mappings = report.get("mapping_from_empty_state", {})
    substantive_facts_hold = all(
        (
            request_facts.get("issue_count") == 0,
            request_facts.get("request_count_with_multiplicity") == 37_352_448,
            equivalence.get("valid") is True,
            bounds.get("valid") is True,
            simulator.get("logical_mismatch_count") == 0,
            simulator.get("physical_mismatch_count") == 0,
            simulator.get("padding_mismatch_count") == 0,
            simulator.get("numeric_analysis_repeated") is False,
            all(value.get("valid") is True for value in mappings.values()),
        )
    )
    if not substantive_facts_hold:
        return report

    refreshed = dict(report)
    refreshed.update(
        {
            "valid": True,
            "status": "E2_LOCAL_COMPLETE",
            "candidate_release": False,
            "claim": "CONFIG_ONLY_CORRECTNESS_BASELINE",
            "errors": [],
            "first_error": None,
            "receipt_refresh_only": True,
            "accepted_receipt_only_drift": sorted(ACCEPTED_RECEIPT_ONLY_DRIFT),
            "active_rule_receipts": {
                "hardware_field_rule": (
                    "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
                ),
                "qlinearadd_rule": (
                    "fea780962c9029e589ece90de2af8c70058aee25cffaf9822f1e16f28ff2ecba"
                ),
            },
        }
    )
    return refreshed


def _progress_contract() -> dict[str, object]:
    return {
        "schema": "qlinearadd-node0007-progress-localization-v1",
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "enabled_by_default": True,
        "read_only": True,
        "target_slice": 0,
        "observer_plusarg": "+RETURN_OBSERVER",
        "heartbeat_cycles": HEARTBEAT_CYCLES,
        "stall_window_cycles": STALL_WINDOW_CYCLES,
        "host_sample_period_seconds": HOST_SAMPLE_SECONDS,
        "deep_checkpoint_limit": DEEP_LIMIT,
        "minimum_monotonic_windows_for_progress": 2,
        "return_allowlist_entry_count": PROGRESS_ALLOWLIST_COUNT,
        "unique_error_interval": (
            "op_a_dequant first Start_Comp: LC/read accepted progress -> "
            "GA/buffer5/write completion -> LC last -> slice_cmpt_finish"
        ),
        "outcome_rules": {
            "two_windows_advance": "INTERRUPTED_WHILE_STILL_PROGRESSING",
            "flat_beyond_stall_window": "LONG_RUNNING_HANG_AT_LAST_BOUNDARY",
            "observer_absent": "PACKAGE_RUNTIME_OBSERVER_BINDING_FAILURE",
        },
    }


def _diagnostic_allowlist(
    readbacks: list[dict[str, object]],
) -> list[dict[str, object]]:
    records = _BASE_RETURN_ALLOWLIST(readbacks)

    def add(
        source_root: str,
        source_path: str,
        target_path: str,
        max_bytes: int,
        missing_meaning: str,
    ) -> None:
        records.append(
            {
                "source_root": source_root,
                "source_path": source_path,
                "target_path": target_path,
                "required": True,
                "max_bytes": max_bytes,
                "missing_meaning": missing_meaning,
            }
        )

    add(
        "evidence",
        "progress_contract.json",
        "evidence/progress_contract.json",
        1 << 20,
        "declared progress and stall-window contract unavailable",
    )
    add(
        "evidence",
        "actual_simulator_argv.txt",
        "evidence/actual_simulator_argv.txt",
        1 << 20,
        "actual observer-enabled simulator argv unavailable",
    )
    add(
        "evidence",
        "host_timing.txt",
        "evidence/host_timing.txt",
        1 << 20,
        "host wall-clock timing unavailable",
    )
    add(
        "evidence",
        "signal_status.txt",
        "evidence/signal_status.txt",
        1 << 20,
        "runner signal/exit classification unavailable",
    )
    add(
        "evidence",
        "progress_samples.log",
        "evidence/progress_samples.log",
        8 << 20,
        "host-to-simulator progress samples unavailable",
    )
    add(
        "evidence",
        "observer_binding.txt",
        "evidence/observer_binding.txt",
        1 << 20,
        "runtime observer binding result unavailable",
    )
    add(
        "run",
        "sim_results/return_observer/return_observer.log",
        "runs/return_observer.log",
        8 << 20,
        "read-only accepted/completion progress observer unavailable",
    )
    return records


def _run_script() -> str:
    return f"""#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in /*) ;; *) echo "server root must be absolute" >&2; exit 2;; esac
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2
package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd -P)"
runtime="$package_root/package_tools/qlinearadd_node0007_server_runtime.py"
install_name="{INSTALL_NAME}"
cfg_rel="install/cfg_pkg/$install_name"
cfg_root="$server_root/$cfg_rel"
run_root="$server_root/run_$install_name"
evidence_root="$server_root/evidence_$install_name"
return_dir="$server_root/${{install_name}}_return"
return_zip="${{return_dir}}.zip"
return_sha="${{return_zip}}.sha256"
observer_log="$run_root/sim_results/return_observer/return_observer.log"
progress_log="$evidence_root/progress_samples.log"
for tool in python3 timeout make date tail grep; do command -v "$tool" >/dev/null 2>&1 || exit 3; done
for fresh in "$cfg_root" "$run_root" "$evidence_root" "$return_dir" "$return_zip" "$return_sha"; do
  [ ! -e "$fresh" ] || {{ echo "Fresh namespace required: $fresh" >&2; exit 4; }}
done
mkdir -p "$cfg_root" "$run_root/sim_results/return_observer" "$evidence_root"
cp "$package_root/diagnostics/progress_contract.json" "$evidence_root/progress_contract.json"
package_start_ns="$(date +%s%N)"
printf 'package_start_epoch_ns=%s\\n' "$package_start_ns" >"$evidence_root/host_timing.txt"
python3 "$runtime" preflight --package-root "$package_root" \
  >"$evidence_root/package_preflight.json" || exit 5
cp -a "$package_root/workload/runtime/." "$cfg_root/"
cp "$package_root/TEST_PACKAGE_MANIFEST.json" "$evidence_root/PACKAGE_MANIFEST.json"
python3 "$runtime" preflight-installed --package-root "$package_root" \
  --cfg-root "$cfg_root" >"$evidence_root/installed_preflight.json" || exit 6
compile_status=125
simulation_status=125
signal_name=NONE
sim_pid=0
sampler_pid=0
finalized=0
sample_progress() {{
  host_ns="$(date +%s%N)"
  observer_tail="OBSERVER_NOT_CREATED"
  if [ -s "$observer_log" ]; then
    observer_tail="$(tail -n 1 "$observer_log" | tr '\\t' ' ')"
  fi
  printf '%s\\t%s\\n' "$host_ns" "$observer_tail" >>"$progress_log"
}}
progress_sampler() {{
  while kill -0 "$sim_pid" 2>/dev/null; do
    sample_progress
    sleep {HOST_SAMPLE_SECONDS}
  done
  sample_progress
}}
finalize() {{
  original="$1"; [ "$finalized" -eq 0 ] || exit "$original"; finalized=1
  trap - EXIT HUP INT TERM
  set +e
  if [ "$sim_pid" -gt 0 ] && kill -0 "$sim_pid" 2>/dev/null; then
    kill -TERM "$sim_pid" 2>/dev/null
    wait "$sim_pid" 2>/dev/null
  fi
  if [ "$sampler_pid" -gt 0 ] && kill -0 "$sampler_pid" 2>/dev/null; then
    kill -TERM "$sampler_pid" 2>/dev/null
    wait "$sampler_pid" 2>/dev/null
  fi
  sample_progress
  printf 'final_epoch_ns=%s\\n' "$(date +%s%N)" >>"$evidence_root/host_timing.txt"
  printf 'signal=%s\\ncompile_status=%s\\nsimulation_status=%s\\n' \
    "$signal_name" "$compile_status" "$simulation_status" \
    >"$evidence_root/signal_status.txt"
  if [ -s "$observer_log" ] && \
     grep -q 'Native NDP return observer' "$observer_log"; then
    printf 'observer_enabled_and_returned=true\\n' >"$evidence_root/observer_binding.txt"
  else
    printf 'observer_enabled_and_returned=false\\n' >"$evidence_root/observer_binding.txt"
  fi
  printf '%s\\n' "$compile_status" >"$evidence_root/compile_exit_status.txt"
  printf '%s\\n' "$simulation_status" >"$evidence_root/simulation_exit_status.txt"
  python3 "$runtime" analyze --package-root "$package_root" \
    --cfg-root "$cfg_root" --evidence-root "$evidence_root" \
    --run-root "$run_root" --compile-status "$compile_status" \
    --simulation-status "$simulation_status"
  analysis_status=$?
  python3 "$runtime" collect --server-root "$server_root" \
    --install-name "$install_name" --package-root "$package_root" \
    --cfg-root "$cfg_root" --evidence-root "$evidence_root" \
    --run-root "$run_root"
  collection_status=$?
  final="$original"
  [ "$final" -ne 0 ] || [ "$analysis_status" -eq 0 ] || final="$analysis_status"
  [ "$final" -ne 0 ] || [ "$collection_status" -eq 0 ] || final="$collection_status"
  exit "$final"
}}
trap 'finalize $?' EXIT
trap 'signal_name=HUP; simulation_status=125; finalize 125' HUP
trap 'signal_name=INT; simulation_status=125; finalize 125' INT
trap 'signal_name=TERM; simulation_status=125; finalize 125' TERM
cd "$server_root"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile \
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$run_root" \
  VCS_EXTRA_OPTS="+define+NATIVE_RETURN_OBSERVER_ENABLE" \
  >"$run_root/sim_results/compile_driver.log" 2>&1
compile_status=$?
[ "$compile_status" -eq 0 ] || exit "$compile_status"
simv="$run_root/sim_results/simv"
sim_start_ns="$(date +%s%N)"
printf 'sim_start_epoch_ns=%s\\n' "$sim_start_ns" >>"$evidence_root/host_timing.txt"
sim_args=(
  -l "$run_root/sim_results/sim.log"
  +vcs+lic+wait
  "+SCA_CFG=$cfg_rel/sca_cfg.json"
  "+SCA_CFG_D=$cfg_rel/sca_cfg_D.json"
  +RETURN_OBSERVER
  +RETURN_OBS_SLICE=0
  +RETURN_OBS_STALL_CYCLES={STALL_WINDOW_CYCLES}
  +RETURN_OBS_HEARTBEAT_CYCLES={HEARTBEAT_CYCLES}
  +RETURN_OBS_DEEP
  +RETURN_OBS_DEEP_LIMIT={DEEP_LIMIT}
  "+RETURN_OBS_FILE=$observer_log"
)
printf 'timeout --foreground --signal=TERM --kill-after=30s 12h %q' "$simv" \
  >"$evidence_root/actual_simulator_argv.txt"
printf ' %q' "${{sim_args[@]}}" >>"$evidence_root/actual_simulator_argv.txt"
printf '\\n' >>"$evidence_root/actual_simulator_argv.txt"
timeout --foreground --signal=TERM --kill-after=30s 12h "$simv" "${{sim_args[@]}}" &
sim_pid=$!
progress_sampler &
sampler_pid=$!
wait "$sim_pid"
simulation_status=$?
sim_pid=0
if kill -0 "$sampler_pid" 2>/dev/null; then
  kill -TERM "$sampler_pid" 2>/dev/null
  wait "$sampler_pid" 2>/dev/null
fi
sampler_pid=0
sample_progress
[ "$simulation_status" -eq 0 ] || exit "$simulation_status"
exit 0
"""


_BASE_RETURN_ALLOWLIST = implementation._return_allowlist
_BASE_BUILD_DIRECTORY = implementation.build_directory


def _diagnostic_build_directory(destination: Path) -> Path:
    package = _BASE_BUILD_DIRECTORY(destination)
    diagnostics = package / "diagnostics"
    diagnostics.mkdir()
    implementation.write_json(
        diagnostics / "progress_contract.json", _progress_contract()
    )
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = implementation.load_json(manifest_path)
    manifest.update(
        {
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "read-only progress localization for the first op_a_dequant "
                "Start_Comp interval; no functional fix, no E3/E4/E5 claim"
            ),
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "functional_fix": False,
            "progress_localization": _progress_contract(),
            "source_v4_identity": {
                "zip": (
                    "artifacts/operator_config_validation/"
                    "r5-server-test-packages/r5_qadd_n7_nested_lc_v4.zip"
                ),
                "sha256": (
                    "dfe6ab0e11482d9af7954ba3e87911b770f8d80efa4148352b63d27bf7df2361"
                ),
                "workload_semantics_unchanged": True,
            },
        }
    )
    manifest["files"] = file_records(package)
    implementation.write_json(manifest_path, manifest)
    (package / "README.md").write_text(
        "# QLinearAdd node0007 nested-LC progress diagnostic v5\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "This is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves the "
        "frozen v4 workload and enables the server's optional read-only "
        "observer in the actual simulator argv. It does not carry or modify "
        "functional RTL, TB, or observer source. Missing observer binding "
        "fails closed in the return allowlist.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest = implementation.load_json(manifest_path)
    manifest["files"] = file_records(package)
    implementation.write_json(manifest_path, manifest)
    runtime_preflight(package)
    return package


def configure() -> None:
    implementation.INSTALL_NAME = INSTALL_NAME
    implementation.MANIFEST_SCHEMA = (
        "qlinearadd-node0007-nested-lc-progress-server-package-v5"
    )
    implementation.PACKAGE_DESCRIPTION = (
        "ResNet50 node0007 nested-LC read-only progress diagnostic"
    )
    implementation.GENERATOR_REL = (
        "tools/build_qlinearadd_node0007_nested_lc_progress_v5_server_package.py"
    )
    implementation.ROOT_REL = ROOT_REL
    implementation.CONTRACT_REL = CONTRACT_REL
    implementation.TASK_RECORD_REL = TASK_RECORD_REL
    implementation.SOURCE_PIPELINE = (
        implementation.ROOT / ROOT_REL / "execplan/pipeline_output"
    )
    implementation.validate_closure = _validate_reused_v4_closure
    implementation.SERVER_RULE_REL = SERVER_RULE_REL
    implementation.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    implementation.SUPERSEDED_IDENTITY = {
        "zip": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "r5_qadd_n7_nested_lc_v4.zip"
        ),
        "sha256": (
            "dfe6ab0e11482d9af7954ba3e87911b770f8d80efa4148352b63d27bf7df2361"
        ),
        "reason": (
            "v4 was manually interrupted without progress counters; v5 does "
            "not replace its function and only localizes progress"
        ),
        "v4_functional_identity_unchanged": True,
    }
    implementation._return_allowlist = _diagnostic_allowlist
    implementation.run_script = _run_script
    implementation.preflight = lambda package: {"deferred": True}
    implementation.build_directory = _diagnostic_build_directory


def main() -> int:
    configure()
    result = implementation.main()
    if result:
        return result
    validation_path = (
        implementation.OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json"
    )
    value = json.loads(validation_path.read_text(encoding="utf-8"))
    value.update(
        {
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "functional_fix": False,
            "progress_localization_enabled_by_default": True,
            "stall_window_cycles": STALL_WINDOW_CYCLES,
        }
    )
    implementation.write_json(validation_path, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
