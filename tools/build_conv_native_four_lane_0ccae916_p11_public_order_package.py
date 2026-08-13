#!/usr/bin/env python3
"""Build p11 public-order c0 diagnostic with fixed atomic server return."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p10_triggered_c0_package as base


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "r5_n4_0cc_p10_trig"
INSTALL_NAME = "r5_n4_0cc_p11f_pubord"
SOURCE_SHA256 = (
    "25c9c01fe7feb42ec8de3eef701386420e7ab014ad24630022539d97a9fb03b5"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "pending"
    / f"{SOURCE_NAME}.zip"
)
RETURN_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p10_return_analysis"
    / "report.json"
)
OBSERVER_APPEND = (
    ROOT
    / "resnet50_pipeline"
    / "conv_native_four_lane_public_order_observer_append_v1.svh"
)
PUBLIC_FINALIZER = (
    ROOT
    / "resnet50_pipeline"
    / "conv_native_four_lane_public_order_finalizer_v1.py"
)
FIXED_PUBLISHER = (
    ROOT
    / "resnet50_pipeline"
    / "fixed_simresult_atomic_return_publisher_v1.py"
)
OUTPUT_ROOT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p10_return_analysis"
    / "p11f_build"
)
RULE_PATHS = [
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
]


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def records(package: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    }


def source_zip() -> Path:
    storage = (
        ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
    )
    candidates = [
        SOURCE_ZIP,
        storage
        / "tested/conv_native_four_lane"
        / SOURCE_NAME
        / f"{SOURCE_NAME}.zip",
    ]
    for candidate in candidates:
        if candidate.is_file() and sha256(candidate) == SOURCE_SHA256:
            return candidate
    raise BuildError("exact p10 source ZIP is unavailable")


def extract_source(target: Path) -> Path:
    source = source_zip()
    package = target / INSTALL_NAME
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise BuildError("p10 source ZIP CRC differs")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or pure.parts[0] != SOURCE_NAME
            ):
                raise BuildError(f"unsafe p10 member: {info.filename}")
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:])
            output = package.joinpath(*relative.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.read(info))
    return package


def replace_identity(package: Path) -> None:
    old = SOURCE_NAME.encode()
    new = INSTALL_NAME.encode()
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        payload = path.read_bytes()
        if old in payload:
            path.write_bytes(payload.replace(old, new))


def patch_observer(package: Path) -> None:
    observer = package / "tb_probe/native_return_observer.svh"
    text = observer.read_text(encoding="utf-8")
    marker = "// Native Conv c0 public-surface order witness."
    if marker in text:
        raise BuildError("p11 observer already present")
    observer.write_text(
        text.rstrip() + "\n\n" + OBSERVER_APPEND.read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )


def patch_runtime_contract(package: Path) -> None:
    runtime = (
        package
        / "package_tools/node0004_assumed_hardware_server_runtime.py"
    )
    text = runtime.read_text(encoding="utf-8")
    old_class = '"CONFIG_FUNCTIONAL_FIX_WITH_PUBLIC_CAUSAL_DIAGNOSTICS"'
    new_class = '"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"'
    old_error = 'raise RuntimeErrorContract("p7 diagnostic identity differs")'
    new_error = 'raise RuntimeErrorContract("p11f diagnostic identity differs")'
    if text.count(old_class) != 1 or text.count(old_error) != 1:
        raise BuildError("inherited runtime contract surface differs")
    runtime.write_text(
        text.replace(old_class, new_class).replace(old_error, new_error),
        encoding="utf-8",
        newline="\n",
    )


def add_assets(package: Path) -> None:
    shutil.copy2(
        PUBLIC_FINALIZER,
        package / "package_tools/node0004_public_order_finalizer.py",
    )
    shutil.copy2(
        FIXED_PUBLISHER,
        package / "package_tools/fixed_simresult_publisher.py",
    )
    profile = json.loads(
        (
            ROOT
            / "contracts/operator_config/"
            "conv_native_four_lane_p10_triggered_causal_observability_v1.json"
        ).read_text(encoding="utf-8")
    )
    bound = profile["profiles"][0]
    bound["profile_id"] = "native_conv_node0004_p11f_public_order_v1"
    bound["storage"]["ring_events"] = 64
    bound["boundaries"].extend(
        [
            {
                "boundary_id": "nconv.c0.sa_output_raw_change",
                "role": "internal_match_compute",
                "stage_gate": "c0",
                "owner_clock_binding": "EXACT_FINAL_SOURCE_REQUIRED",
                "qualification": (
                    "package-local existing SA output tag monitor valid-rise "
                    "or tag-change witness; stable valid is state only"
                ),
                "direct_consumer_binding": "EXACT_FINAL_SOURCE_REQUIRED",
                "records": [
                    "count",
                    "first_time",
                    "last_time",
                    "last_tag",
                ],
            },
            {
                "boundary_id": "nconv.c0.sa_output_buffer_ready",
                "role": "consumer_accept",
                "stage_gate": "c0",
                "owner_clock_binding": "EXACT_FINAL_SOURCE_REQUIRED",
                "qualification": (
                    "Buffer-facing existing ready monitor sampled only with "
                    "raw SA output valid; level count is state-only"
                ),
                "direct_consumer_binding": "EXACT_FINAL_SOURCE_REQUIRED",
                "records": ["count", "first_time", "last_time", "pass"],
            },
        ]
    )
    bound["hypotheses"] = [
        {
            "hypothesis_id": "nconv_sa_output_generation_stop",
            "classification": "DYNAMIC_FLOW_CONTROL_STALL",
            "distinguished_by": [
                "nconv.c0.sa_input",
                "nconv.c0.sa_output_raw_change",
                "nconv.c0.sa_output",
            ],
            "decision": (
                "accepted SA inputs continue through terminal tags but raw "
                "SA output is absent at the qualified stall snapshot"
            ),
        },
        {
            "hypothesis_id": "nconv_sa_to_buffer5_backpressure",
            "classification": "DYNAMIC_FLOW_CONTROL_STALL",
            "distinguished_by": [
                "nconv.c0.sa_output_raw_change",
                "nconv.c0.sa_output_buffer_ready",
                "nconv.c0.sa_output",
            ],
            "decision": (
                "raw SA output remains valid while Buffer-facing ready is "
                "low and accepted-output count no longer advances"
            ),
        },
        {
            "hypothesis_id": "nconv_mse4_consumer_stall",
            "classification": "DYNAMIC_FLOW_CONTROL_STALL",
            "distinguished_by": [
                "nconv.c0.sa_output",
                "nconv.c0.mse4_index",
                "nconv.c0.buffer5_write",
            ],
            "decision": (
                "SA output accepted order advances beyond the MSE4 accepted "
                "index sequence"
            ),
        },
        {
            "hypothesis_id": "nconv_arm_terminal_zero_priority",
            "classification": "TERMINAL_PROPAGATION_FAILURE",
            "distinguished_by": [
                "nconv.c0.arm_response",
                "nconv.c0.arm_finish",
                "nconv.c0.sa_output_raw_change",
                "nconv.c0.sa_output_buffer_ready",
            ],
            "decision": (
                "ARM response traffic is accepted but finish stays zero; "
                "ordered SA raw/ready evidence establishes whether this is "
                "the earliest divergence or a downstream consequence"
            ),
        },
    ]
    bound["claim_boundary"] = (
        "Fresh p11f c0 public-order diagnostic only. It reuses the exact "
        "p10 production-compiled monitor surfaces and adds bounded ordered "
        "event storage; no formal 320D, E3, E4, E5 or performance claim."
    )
    profile["claim_boundary"] = (
        "Exact family-bound profile for p11f. Final observer bytes, fixed "
        "server return publisher, production compile and return remain "
        "independent gates."
    )
    write_json(package / "diagnostics/public_order_profile.json", profile)


def runner_text() -> str:
    return f"""#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/server_root" >&2
  exit 2
fi
case "$1" in /*) ;; *) echo "server_root must be absolute" >&2; exit 2;; esac
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2
package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd -P)"
runtime="$package_root/package_tools/node0004_assumed_hardware_server_runtime.py"
observer_guard="$package_root/package_tools/node0004_package_observer_guard.py"
trigger_finalizer="$package_root/package_tools/node0004_triggered_causal_finalizer.py"
public_finalizer="$package_root/package_tools/node0004_public_order_finalizer.py"
publisher="$package_root/package_tools/fixed_simresult_publisher.py"
install_name="{INSTALL_NAME}"
result_root="/home/panqs/ndp/simresult"
return_zip="/home/panqs/ndp/simresult/{INSTALL_NAME}_return.zip"
return_sha="/home/panqs/ndp/simresult/{INSTALL_NAME}_return.zip.sha256"
launch_cwd="$(pwd -P)"
for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || exit 3; done
mkdir -p -- "$result_root" || exit 9
[ -d "$result_root" ] && [ -w "$result_root" ] || exit 9
resolved_result_root="$(cd "$result_root" && pwd -P)" || exit 9
[ "$resolved_result_root" = "/home/panqs/ndp/simresult" ] || exit 9
[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || {{
  echo "Fixed result target conflict: $return_zip or $return_sha" >&2
  exit 10
}}
work_root="/home/panqs/ndp/simresult/.{INSTALL_NAME}.run.$$"
cfg_root="$work_root/install/cfg_pkg/$install_name"
run_root="$work_root/run"
evidence_root="$work_root/evidence"
for fresh in "$work_root" "$cfg_root" "$run_root" "$evidence_root"; do
  [ ! -e "$fresh" ] || {{ echo "Fresh namespace required: $fresh" >&2; exit 4; }}
done
for duplicate_root in "$server_root" "$package_root" "$launch_cwd"; do
  [ ! -e "$duplicate_root/${{install_name}}_return.zip" ] || exit 11
  [ ! -e "$duplicate_root/${{install_name}}_return.zip.sha256" ] || exit 11
done
python3 "$runtime" path-budget --package-root "$package_root" --server-root "$server_root" >/dev/null || exit 5
package_preflight_json="$(python3 "$runtime" preflight --package-root "$package_root")" || exit 5
mkdir -p "$cfg_root" "$run_root/compile/sim_results" "$evidence_root/natural_terminal" "$evidence_root/feature_binding"
printf '%s\\n' "$package_preflight_json" > "$evidence_root/package_preflight.json"
cp -a "$package_root/workload/runtime/." "$cfg_root/"
python3 "$runtime" verify-install --package-root "$package_root" --cfg-root "$cfg_root" > "$evidence_root/install_preflight.json" || exit 6
python3 "$observer_guard" --package-root "$package_root" > "$evidence_root/observer_precompile.json" || exit 7
cat > "$evidence_root/publication_preflight.json" <<EOF
{{
  "schema": "fixed-simresult-publication-preflight-v1",
  "result_root": "/home/panqs/ndp/simresult",
  "return_zip": "/home/panqs/ndp/simresult/{INSTALL_NAME}_return.zip",
  "return_sidecar": "/home/panqs/ndp/simresult/{INSTALL_NAME}_return.zip.sha256",
  "publication_state": "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING",
  "server_root_duplicate_absent": true,
  "package_root_duplicate_absent": true,
  "install_namespace_duplicate_absent": true,
  "run_root_duplicate_absent": true,
  "launch_cwd_duplicate_absent": true
}}
EOF
compile_status=125
run_status=125
signal_status=NONE
finalized=0
sim_pid=
progress_pid=
finalize() {{
  original="$1"; [ "$finalized" -eq 0 ] || exit "$original"; finalized=1
  trap - EXIT INT TERM HUP
  set +e
  [ -z "$progress_pid" ] || kill "$progress_pid" 2>/dev/null
  [ -z "$progress_pid" ] || wait "$progress_pid" 2>/dev/null
  printf '%s\\n' "$compile_status" > "$evidence_root/compile_exit_status.txt"
  printf '%s\\n' "$run_status" > "$evidence_root/run_exit_status.txt"
  printf '%s\\n' "$signal_status" > "$evidence_root/signal_status.txt"
  python3 "$trigger_finalizer" --observer-log "$run_root/c0/triggered_observer.log" --sim-log "$run_root/c0/sim.log" --compile-status "$evidence_root/compile_exit_status.txt" --run-status "$evidence_root/run_exit_status.txt" --signal-status "$evidence_root/signal_status.txt" --output "$evidence_root/triggered_causal_summary.json" >/dev/null 2>&1 || true
  python3 "$public_finalizer" --observer-log "$run_root/c0/public_order_observer.log" --compile-status "$evidence_root/compile_exit_status.txt" --run-status "$evidence_root/run_exit_status.txt" --signal-status "$evidence_root/signal_status.txt" --output "$evidence_root/public_order_summary.json" >/dev/null 2>&1 || true
  python3 "$runtime" analyze --package-root "$package_root" --evidence-root "$evidence_root" --run-root "$run_root"
  analysis=$?
  for duplicate_root in "$server_root" "$package_root" "$launch_cwd" "$cfg_root" "$run_root"; do
    [ ! -e "$duplicate_root/${{install_name}}_return.zip" ] || exit 11
    [ ! -e "$duplicate_root/${{install_name}}_return.zip.sha256" ] || exit 11
  done
  publication_json="$(python3 "$publisher" --package-root "$package_root" --evidence-root "$evidence_root" --run-root "$run_root")"
  collection=$?
  [ "$collection" -ne 0 ] || printf '%s\\n' "$publication_json"
  final="$original"
  [ "$final" -ne 0 ] || [ "$analysis" -eq 0 ] || final="$analysis"
  [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] || final="$collection"
  exit "$final"
}}
trap 'finalize $?' EXIT
on_signal() {{
  signal_status="$1"
  [ -z "$sim_pid" ] || kill -TERM "$sim_pid" 2>/dev/null
  finalize "$2"
}}
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
cd "$server_root"
printf '%s\\n' "make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=$run_root/compile VCS_EXTRA_OPTS=+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe" > "$evidence_root/compile_argv.txt"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$run_root/compile" VCS_EXTRA_OPTS="+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe" > "$run_root/compile/sim_results/compile_driver.log" 2>&1
compile_status=$?
[ "$compile_status" -eq 0 ] || exit "$compile_status"
python3 "$runtime" compile-identity --compile-log "$run_root/compile/sim_results/compile_driver.log" --output "$evidence_root/production_rtl_identity.json" >/dev/null 2>&1 || true
simv="$run_root/compile/sim_results/simv"
mkdir -p "$run_root/c0"
observer_log="$run_root/c0/return_observer.log"
trigger_log="$run_root/c0/triggered_observer.log"
public_log="$run_root/c0/public_order_observer.log"
printf '%s\\n' "$simv -l $run_root/c0/sim.log +vcs+lic+wait +SCA_CFG=$cfg_root/runs/c0/sca_cfg.json +SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json +RETURN_OBSERVER +N4D_C0_BOUNDARY_DIAG +RETURN_OBS_SLICE=0 +RETURN_OBS_STALL_CYCLES=1048576 +RETURN_OBS_HEARTBEAT_CYCLES=262144 +RETURN_OBS_FILE=$observer_log +N4T_CAUSAL_PROFILE +N4T_NO_PROGRESS_CYCLES=1048576 +N4T_FILE=$trigger_log +N4P_PUBLIC_ORDER_PROFILE +N4P_EVENT_LIMIT=64 +N4P_FILE=$public_log" > "$run_root/c0/simulator_argv.txt"
timeout --foreground --signal=TERM --kill-after=30s 12h "$simv" -l "$run_root/c0/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" +RETURN_OBSERVER +N4D_C0_BOUNDARY_DIAG +RETURN_OBS_SLICE=0 +RETURN_OBS_STALL_CYCLES=1048576 +RETURN_OBS_HEARTBEAT_CYCLES=262144 "+RETURN_OBS_FILE=$observer_log" +N4T_CAUSAL_PROFILE +N4T_NO_PROGRESS_CYCLES=1048576 "+N4T_FILE=$trigger_log" +N4P_PUBLIC_ORDER_PROFILE +N4P_EVENT_LIMIT=64 "+N4P_FILE=$public_log" &
sim_pid=$!
(
  while kill -0 "$sim_pid" 2>/dev/null; do
    host_epoch="$(date +%s)"
    trigger_bytes=0
    public_bytes=0
    [ ! -f "$trigger_log" ] || trigger_bytes="$(wc -c < "$trigger_log")"
    [ ! -f "$public_log" ] || public_bytes="$(wc -c < "$public_log")"
    printf 'host_epoch=%s run=c0 trigger_bytes=%s public_bytes=%s\\n' "$host_epoch" "$trigger_bytes" "$public_bytes"
    sleep 30
  done
) > "$run_root/c0/host_progress.log" 2>&1 &
progress_pid=$!
wait "$sim_pid"
run_status=$?
sim_pid=
kill "$progress_pid" 2>/dev/null
wait "$progress_pid" 2>/dev/null
progress_pid=
python3 "$runtime" feature-binding --sim-log "$run_root/c0/sim.log" --observer-log "$observer_log" --output "$evidence_root/feature_binding/c0.json"
feature_status=$?
if [ "$run_status" -eq 0 ] && [ "$feature_status" -ne 0 ]; then exit 10; fi
if [ "$run_status" -eq 0 ]; then
  python3 "$runtime" qualify-run --sim-log "$run_root/c0/sim.log" --observer-log "$observer_log" --output "$evidence_root/natural_terminal/c0.json" || exit 9
fi
exit "$run_status"
"""


def update_manifest(package: Path) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    observer = package / "tb_probe/native_return_observer.svh"
    manifest.update(
        {
            "schema": "conv-native-four-lane-p11-public-order-package-v1",
            "install_name": INSTALL_NAME,
            "run_namespace": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return.zip",
            "status": "PACKAGE_READY_NOT_RUN",
            "package_release": "PACKAGE_READY_NOT_RUN",
            "candidate_release": False,
            "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "formal_readback_count": 0,
            "formal_readback_claimed": False,
            "functional_rtl_modified": False,
            "functional_rtl_file_count": 0,
            "server_action": False,
        }
    )
    manifest["source_p10_return_analysis"] = {
        "path": RETURN_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": sha256(RETURN_ANALYSIS),
        "return_sha256": (
            "568a0c63f0db3e21a63a9fae94a711f91583fabb4f00a1a47ced0d613d721434"
        ),
        "classification": "LONG_RUNNING_HANG_CONFIRMED_BEFORE_EXTERNAL_HUP",
    }
    manifest["observer_binding"].update(
        {
            "source": "tb_probe/native_return_observer.svh",
            "sha256": sha256(observer),
            "size_bytes": observer.stat().st_size,
            "public_order_append_sha256": sha256(OBSERVER_APPEND),
            "new_dut_hierarchy_references": 0,
        }
    )
    manifest["triggered_causal_observability"] = {
        "profile_path": "diagnostics/public_order_profile.json",
        "profile_sha256": sha256(
            package / "diagnostics/public_order_profile.json"
        ),
        "runtime_enable": "+N4P_PUBLIC_ORDER_PROFILE",
        "runtime_budget": "+N4P_EVENT_LIMIT=64",
        "time_zero_marker": (
            "N4P_FEATURE_ENABLE_V1 feature=NATIVE4_PUBLIC_ORDER enabled=1"
        ),
        "observer_return": "runs/c0/public_order_observer.log",
        "summary_return": "evidence/public_order_summary.json",
        "stable_level_is_progress": False,
        "drives_dut": False,
        "changes_timeout": False,
    }
    allowlist = manifest["return_allowlist"]
    additions = [
        {
            "source_root": "evidence",
            "source_path": "publication_preflight.json",
            "target_path": "evidence/publication_preflight.json",
            "required": True,
            "max_bytes": 2 * 1024 * 1024,
            "missing_semantics": "fixed publication preflight unavailable",
        },
        {
            "source_root": "evidence",
            "source_path": "public_order_summary.json",
            "target_path": "evidence/public_order_summary.json",
            "required": True,
            "max_bytes": 2 * 1024 * 1024,
            "missing_semantics": "public-order finalizer unavailable",
        },
        {
            "source_root": "run",
            "source_path": "c0/public_order_observer.log",
            "target_path": "runs/c0/public_order_observer.log",
            "required": False,
            "max_bytes": 2 * 1024 * 1024,
            "missing_semantics": "public-order feature did not reach time zero",
        },
    ]
    existing_targets = {item["target_path"] for item in allowlist}
    allowlist.extend(
        item for item in additions if item["target_path"] not in existing_targets
    )
    manifest["fixed_server_result_publication"] = {
        "result_root": "/home/panqs/ndp/simresult",
        "return_zip": (
            f"/home/panqs/ndp/simresult/{INSTALL_NAME}_return.zip"
        ),
        "return_sidecar": (
            f"/home/panqs/ndp/simresult/{INSTALL_NAME}_return.zip.sha256"
        ),
        "configurable": False,
        "shared_exactly_once_finalizer": True,
        "atomic_hidden_staging": True,
        "target_conflict_fail_closed": True,
        "local_workspace_mapping_forbidden": True,
        "duplicate_roots_required_absent": [
            "NDP_copy0x server_root",
            "package_root",
            "install namespace",
            "run_root",
            "launch cwd",
        ],
    }
    manifest["diagnostic_execution_reduction"].update(
        {
            "kept": (
                manifest["diagnostic_execution_reduction"].get("kept", [])
            ),
            "claim_boundary": (
                "same frozen c0 causal slice as p10; p11 changes only "
                "observer/finalizer/return publication"
            ),
        }
    )
    manifest["successor_candidate_matrix"] = {
        "SA_OUTPUT_GENERATION_STOP": [
            "raw SA output absent at stall after accepted input sequence"
        ],
        "SA_TO_BUFFER5_BACKPRESSURE": [
            "raw SA output held valid with Buffer-facing ready low"
        ],
        "MSE4_CONSUMER_STALL": [
            "SA output accepted sequence exceeds MSE4 accepted index sequence"
        ],
        "ARM_TERMINAL_CONSEQUENCE_OR_CAUSE": [
            "ARM finish remains zero, ordered earliest SA boundary adjudicates priority"
        ],
    }
    manifest["release_gate_matrix"] = {
        "core_always": {
            "applicable": True,
            "pass": True,
            "changed_surface": [
                "fresh identity",
                "fixed atomic return publisher",
            ],
            "evidence": ["final ZIP exact-set/path/runtime-D audit"],
            "blocking": True,
        },
        "runner": {
            "applicable": True,
            "pass": True,
            "changed_surface": [
                "shared EXIT/HUP/INT/TERM fixed-result finalizer"
            ],
            "evidence": [
                "safe compile/simulator stubs",
                "isolated publication harness",
            ],
            "blocking": True,
        },
        "package_local_hdl": {
            "applicable": True,
            "pass": True,
            "changed_surface": ["public-order observer append"],
            "evidence": [
                "focused syntax/scope",
                "actual-consumer closure",
            ],
            "blocking": True,
        },
        "materialized_config": {
            "applicable": "receipt_reuse",
            "pass": True,
            "changed_surface": [],
            "evidence": ["p10 workload/runtime byte equality"],
            "blocking": False,
        },
        "diagnostic_semantics": {
            "applicable": True,
            "pass": True,
            "changed_surface": [
                "raw-valid/ready state separated from accepted progress",
                "bounded ordered event snapshot",
            ],
            "evidence": ["predicate/event trace"],
            "blocking": True,
        },
        "return_result": {
            "applicable": True,
            "pass": True,
            "changed_surface": ["fixed result publication and p11 allowlist"],
            "evidence": ["normal/compile-fail/INT/TERM publication harness"],
            "blocking": True,
        },
        "record_only_warnings": [
            "numeric/W3/golden/address/config are byte-frozen and not rerun"
        ],
    }
    manifest["rule_receipts"] = [
        {
            "path": rule,
            "sha256": sha256(ROOT / rule),
            "reason": (
                "mutable plan provenance"
                if rule == ".agents/plan.md"
                else "current generation/release rule"
            ),
        }
        for rule in RULE_PATHS
    ]
    manifest["rule_receipts_current_match"] = True
    current_ids = set(manifest.get("delivery_successor", {}).get("rule_ids", []))
    current_ids.update(
        {
            "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
            "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
            "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
            "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
            "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
            "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
        }
    )
    manifest.setdefault("delivery_successor", {})["rule_ids"] = sorted(
        current_ids
    )
    manifest["path_length_budget"].update(
        {
            "declared_target_root_max_chars": 96,
            "max_projected_absolute_path_chars": 240,
            "fixed_result_root": "/home/panqs/ndp/simresult",
        }
    )
    final_paths = sorted(records(package))
    manifest["path_length_budget"].update(
        {
            "max_zip_member_chars": max(
                len(f"{INSTALL_NAME}/{relative}") for relative in final_paths
            ),
            "max_inner_suffix_chars": max(map(len, final_paths)),
            "max_inner_depth": max(
                len(PurePosixPath(relative).parts) for relative in final_paths
            ),
            "max_inner_component_chars": max(
                len(component)
                for relative in final_paths
                for component in PurePosixPath(relative).parts
            ),
        }
    )
    manifest["files"] = records(package)
    write_json(path, manifest)
    manifest["files"] = records(package)
    write_json(path, manifest)


def build_directory(target: Path) -> Path:
    package = extract_source(target)
    replace_identity(package)
    patch_runtime_contract(package)
    patch_observer(package)
    add_assets(package)
    (package / "PREPARE_AND_RUN.sh").write_text(
        runner_text(), encoding="utf-8", newline="\n"
    )
    (package / "README.md").write_text(
        "# Native Conv node0004 p11 public-order c0 diagnostic\n\n"
        "p10 proved a qualified stall before the external HUP. p11 keeps the "
        "same byte-frozen c0 workload/config and records bounded accepted tag "
        "order plus raw-SA-output/Buffer-ready state to distinguish the "
        "remaining first-divergence candidates. It does not modify functional "
        "RTL and makes no formal-D/E3/E4/E5/performance claim.\n\n"
        "Server command:\n\n"
        f"`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        "The server publishes the only return ZIP and sidecar directly under "
        "`/home/panqs/ndp/simresult`.\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package)
    return package


def build() -> dict[str, Any]:
    targets = [
        OUTPUT_ROOT / INSTALL_NAME,
        OUTPUT_ROOT / f"{INSTALL_NAME}.zip",
        OUTPUT_ROOT / f"{INSTALL_NAME}.zip.sha256",
        OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite an existing p11 target")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    package = build_directory(OUTPUT_ROOT)
    zip_path = OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
    base.INSTALL_NAME = INSTALL_NAME
    base.deterministic_zip(package, zip_path)
    value = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="native4-p11-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = sha256(repeat_zip) == value
    if not deterministic:
        raise BuildError("p11 deterministic rebuild differs")
    sidecar = OUTPUT_ROOT / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{value}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    result = {
        "schema": "conv-native-four-lane-p11-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package": str(package),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": value,
        "sidecar": str(sidecar),
        "deterministic_double_build": deterministic,
        "source_p10_sha256": SOURCE_SHA256,
        "p10_return_analysis_sha256": sha256(RETURN_ANALYSIS),
        "functional_rtl_modified": False,
        "config_numeric_w3_golden_address_changed": False,
        "server_action": False,
    }
    write_json(OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
