#!/usr/bin/env python3
"""Build the current-rule exact-native MaxPool node0002 server package."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_n2_maxpool_native_reuse_v4"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
OUTPUT_ZIP = OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
OUTPUT_SIDECAR = Path(str(OUTPUT_ZIP) + ".sha256")
BUILD_RECEIPT = OUTPUT_ROOT / f"{INSTALL_NAME}.build.json"
SOURCE_JSON = ROOT / "ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json"
SOURCE_JSON_SHA256 = (
    "a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1"
)
OBSERVER_SOURCE = ROOT / "tools/maxpool_node0002_progress_observer_v4.svh"
RUNTIME_SOURCE = ROOT / "tools/maxpool_node0002_native_reuse_server_runtime_v4.py"
RUNTIME_BASE_SOURCE = ROOT / "tools/maxpool_node0002_original_json_server_runtime.py"
E2_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "maxpool-node0002-config-only-e2-v1/validation_report.json"
)
E2_REPORT_SHA256 = (
    "5fb484e9c1bf40b86d68c21c8837e6a61978e63cac40e9e2f5b3b42ea3dd9a61"
)
CANONICAL_PREFIX = "| CANONICAL_MAXPOOL_DIAG_DECISION_V1 |"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.native_json_maxpool_package import (  # noqa: E402
    SOURCE_BLOB,
    SOURCE_COMMIT,
    SOURCE_REMOTE,
    generate_native_json_maxpool_package,
    validate_native_json_maxpool_package,
)
from tools.maxpool_node0002_native_reuse_server_runtime_v4 import (  # noqa: E402
    preflight_package,
)


class MaxPoolNativeReuseBuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def file_records(
    root: Path, *, exclude_manifest: bool = False
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == "TEST_PACKAGE_MANIFEST.json":
            continue
        if path.is_symlink():
            raise MaxPoolNativeReuseBuildError(f"symlink is forbidden: {path}")
        records[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return records


def tree_sha256(records: Mapping[str, Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for path, item in sorted(records.items()):
        digest.update(
            f"{path}\0{item['size_bytes']}\0{item['sha256']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _rule_receipts() -> tuple[list[dict[str, Any]], list[str]]:
    paths = (
        ROOT / ".agents/rules/生成前必读索引.md",
        ROOT / ".agents/rules/算子配置规则.md",
        ROOT / ".agents/rules/NDP硬件字段语义.md",
        ROOT / ".agents/rules/服务器测试包生成规则.md",
        ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
        ROOT / ".agents/task_records/20260727_maxpool_node0002_mainline_adjudication.md",
        ROOT / ".agents/task_records/20260727_maxpool_node0002_config_only_e2.md",
        ROOT / "contracts/operator_config/maxpool_node0002_config_only_e2_v1.json",
        E2_REPORT,
        SOURCE_JSON,
    )
    receipts = []
    for path in paths:
        if not path.is_file():
            raise MaxPoolNativeReuseBuildError(f"required receipt missing: {path}")
        receipts.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "current_match": True,
            }
        )
    rule_ids = [
        "CDA-REUSE-FIRST-DEFERRED-RETEST-001",
        "CDA-GA-INT8-MAX-NUMERIC-001",
        "CDA-GA-INT8-MAX-PIPE-001",
        "CDA-SERVER-WORKLOAD-PROVENANCE-001",
        "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
        "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
        "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
        "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
        "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
        "CDA-SERVER-ONE-COMMAND-001",
        "CDA-SCA-D-TB-READBACK-LENGTH-001",
        "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
        "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
        "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
        "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
        "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
        "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001",
        "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
        "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
        "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
        "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
    ]
    return receipts, rule_ids


def _prefix_sca(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    changes = []
    prefix = f"install/cfg_pkg/{INSTALL_NAME}/"
    for key, item in value.items():
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        old = item["path"]
        pure = PurePosixPath(old)
        if pure.is_absolute() or ".." in pure.parts:
            raise MaxPoolNativeReuseBuildError(f"unsafe SCA path: {old}")
        item["path"] = prefix + pure.as_posix()
        changes.append({"key": key, "before": old, "after": item["path"]})
    write_json(path, value)
    return {"path": path.name, "changes": changes, "changed_count": len(changes)}


def _readback_checks(runtime: Path) -> list[dict[str, Any]]:
    sca_d = json.loads((runtime / "sca_cfg_D.json").read_text(encoding="utf-8"))
    checks = []
    for key, item in sorted(sca_d.items()):
        slice_id = 0 if "slice0" in key else 1
        path = PurePosixPath(item["path"])
        prefix = ("install", "cfg_pkg", INSTALL_NAME)
        if path.parts[:3] != prefix:
            raise MaxPoolNativeReuseBuildError("SCA_D namespace differs")
        runtime_path = PurePosixPath(*path.parts[3:]).as_posix()
        checks.append(
            {
                "key": key,
                "runtime_path": runtime_path,
                "golden_path": f"workload/runtime/golden/slice{slice_id:02d}.txt",
                "length_128bit": int(item["length"]),
                "slice_id": slice_id,
            }
        )
    if len(checks) != 4:
        raise MaxPoolNativeReuseBuildError("formal readback exact set differs")
    return checks


def _return_allowlist(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = [
        ("package", "TEST_PACKAGE_MANIFEST.json", "package/TEST_PACKAGE_MANIFEST.json", True, 1 << 20),
        ("evidence", "package_preflight.json", "evidence/package_preflight.json", True, 1 << 20),
        ("evidence", "installed_preflight.json", "evidence/installed_preflight.json", True, 1 << 20),
        ("evidence", "actual_compile_argv.txt", "evidence/actual_compile_argv.txt", True, 1 << 20),
        ("evidence", "observer_binding.json", "evidence/observer_binding.json", False, 1 << 20),
        ("evidence", "CANONICAL_PROGRESS_DECISION.json", "evidence/CANONICAL_PROGRESS_DECISION.json", False, 1 << 20),
        ("evidence", "SERVER_RESULT_GATE.json", "evidence/SERVER_RESULT_GATE.json", True, 2 << 20),
        ("evidence", "server_command.txt", "evidence/server_command.txt", True, 1 << 20),
        ("evidence", "compile_exit_status.txt", "evidence/compile_exit_status.txt", True, 4096),
        ("evidence", "sim_exit_status.txt", "evidence/sim_exit_status.txt", True, 4096),
        ("evidence", "run_exit_status.txt", "evidence/run_exit_status.txt", True, 4096),
        ("evidence", "termination_signal.txt", "evidence/termination_signal.txt", False, 4096),
        ("run", "sim_results/compile_driver.log", "logs/compile_driver.log", True, 2 << 20),
        ("run", "sim_results/compile.log", "logs/compile.log", False, 2 << 20),
        ("run", "sim_results/simulator_argv.txt", "evidence/simulator_argv.txt", False, 1 << 20),
        ("run", "sim_results/sim.log", "logs/sim.log", False, 8 << 20),
        ("run", "sim_results/return_observer.log", "logs/return_observer.log", False, 8 << 20),
        ("run", "sim_results/host_progress.log", "logs/host_progress.log", False, 2 << 20),
        ("cfg", "sca_cfg.json", "config/sca_cfg.json", True, 2 << 20),
        ("cfg", "sca_cfg_D.json", "config/sca_cfg_D.json", True, 2 << 20),
    ]
    result = [
        {
            "source_root": source_root,
            "source_path": source_path,
            "target_path": target_path,
            "required": required,
            "max_bytes": max_bytes,
        }
        for source_root, source_path, target_path, required, max_bytes in items
    ]
    for check in checks:
        result.append(
            {
                "source_root": "cfg",
                "source_path": check["runtime_path"],
                "target_path": f"formal_readback/{check['key']}.txt",
                "required": False,
                "max_bytes": 2 << 20,
            }
        )
    return result


def _run_script() -> str:
    return """#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1

if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in
  /*) ;;
  *) echo "Server root must be absolute: $1" >&2; exit 2 ;;
esac
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2
package_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
runtime_tool="${package_root}/package_tools/maxpool_node0002_native_reuse_server_runtime_v4.py"

for tool in python3 timeout make; do
  command -v "${tool}" >/dev/null 2>&1 || { echo "Missing command: ${tool}" >&2; exit 3; }
done
install_name="$(python3 "${runtime_tool}" manifest-value \
  --package-root "${package_root}" --key install_name)" || exit 5
cfg_root="${server_root}/install/cfg_pkg/${install_name}"
run_dir="${server_root}/run_${install_name}"
evidence_root="${server_root}/evidence_${install_name}"
return_dir="${server_root}/${install_name}_return"
return_zip="${return_dir}.zip"
return_sha="${return_zip}.sha256"
server_command="bash PREPARE_AND_RUN.sh ${server_root}"

for fresh in "${cfg_root}" "${run_dir}" "${evidence_root}" \
  "${return_dir}" "${return_zip}" "${return_sha}"; do
  [ ! -e "${fresh}" ] || { echo "Fresh namespace required: ${fresh}" >&2; exit 4; }
done
mkdir -p "${evidence_root}" "${run_dir}/sim_results"
printf '%s\n' "${server_command}" > "${evidence_root}/server_command.txt"

compile_status=125
sim_status=125
run_status=125
termination_signal=""
finalization_started=0

finalize_return() {
  original_status="$1"
  [ "${finalization_started}" -eq 0 ] || exit "${original_status}"
  finalization_started=1
  trap - EXIT HUP INT TERM
  set +e
  [ -z "${termination_signal}" ] || \
    printf '%s\n' "${termination_signal}" > "${evidence_root}/termination_signal.txt"
  printf '%s\n' "${compile_status}" > "${evidence_root}/compile_exit_status.txt"
  printf '%s\n' "${sim_status}" > "${evidence_root}/sim_exit_status.txt"
  printf '%s\n' "${run_status}" > "${evidence_root}/run_exit_status.txt"
  python3 "${runtime_tool}" analyze \
    --server-root "${server_root}" --package-root "${package_root}" \
    --install-name "${install_name}" --evidence-root "${evidence_root}" \
    --run-dir "${run_dir}" --compile-status "${compile_status}" \
    --sim-status "${sim_status}" --output "${evidence_root}/SERVER_RESULT_GATE.json" \
    >/dev/null
  analysis_status=$?
  python3 "${runtime_tool}" collect \
    --server-root "${server_root}" --package-root "${package_root}" \
    --install-name "${install_name}" --evidence-root "${evidence_root}" \
    --run-dir "${run_dir}" --run-status "${run_status}" \
    --server-command "${server_command}" >/dev/null
  collection_status=$?
  if [ -f "${return_zip}" ]; then
    echo "Return ZIP: ${return_zip}"
  else
    echo "Return collection failed." >&2
  fi
  final_status="${original_status}"
  if [ "${final_status}" -eq 0 ] && [ "${analysis_status}" -ne 0 ]; then
    final_status="${analysis_status}"
  fi
  if [ "${final_status}" -eq 0 ] && [ "${collection_status}" -ne 0 ]; then
    final_status="${collection_status}"
  fi
  exit "${final_status}"
}
trap 'finalize_return $?' EXIT
trap 'termination_signal=HUP; exit 129' HUP
trap 'termination_signal=INT; exit 130' INT
trap 'termination_signal=TERM; exit 143' TERM

python3 "${runtime_tool}" preflight-package \
  --package-root "${package_root}" --install-name "${install_name}" \
  --output "${evidence_root}/package_preflight.json" >/dev/null || exit 5
mkdir -p "${cfg_root}"
cp -a "${package_root}/workload/runtime/." "${cfg_root}/"
python3 "${runtime_tool}" preflight-installed \
  --package-root "${package_root}" --server-root "${server_root}" \
  --install-name "${install_name}" \
  --output "${evidence_root}/installed_preflight.json" >/dev/null || exit 5

compile_args=(
  make -f Makefile.tb_NDP_Top_new_phy compile
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0
  "RUN_DIR=${run_dir}"
  "VCS_EXTRA_OPTS=+incdir+${package_root}/tb_probe +define+NATIVE_RETURN_OBSERVER_ENABLE"
)
printf '%q ' "${compile_args[@]}" > "${evidence_root}/actual_compile_argv.txt"
printf '\n' >> "${evidence_root}/actual_compile_argv.txt"
cd "${server_root}"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  "${compile_args[@]}" > "${run_dir}/sim_results/compile_driver.log" 2>&1
compile_status=$?
if [ "${compile_status}" -eq 0 ]; then
  sim_args=(
    "${run_dir}/sim_results/simv"
    -l "${run_dir}/sim_results/sim.log"
    +vcs+lic+wait
    "+SCA_CFG=${cfg_root}/sca_cfg.json"
    "+SCA_CFG_D=${cfg_root}/sca_cfg_D.json"
    +RETURN_OBSERVER
    "+RETURN_OBS_FILE=${run_dir}/sim_results/return_observer.log"
    +RETURN_OBS_SAMPLE_CYCLES=262144
    +RETURN_OBS_STALL_WINDOWS=4
  )
  printf '%q ' "${sim_args[@]}" > "${run_dir}/sim_results/simulator_argv.txt"
  printf '\n' >> "${run_dir}/sim_results/simulator_argv.txt"
  timeout --foreground --signal=TERM --kill-after=30s 12h \
    "${sim_args[@]}" &
  sim_pid=$!
  (
    while kill -0 "${sim_pid}" 2>/dev/null; do
      now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      bytes=0
      [ ! -f "${run_dir}/sim_results/return_observer.log" ] || \
        bytes="$(wc -c < "${run_dir}/sim_results/return_observer.log")"
      printf 'utc=%s observer_bytes=%s\n' "${now}" "${bytes}"
      sleep 60
    done
  ) > "${run_dir}/sim_results/host_progress.log" 2>&1 &
  monitor_pid=$!
  wait "${sim_pid}"
  sim_status=$?
  kill "${monitor_pid}" >/dev/null 2>&1 || true
  wait "${monitor_pid}" >/dev/null 2>&1 || true
else
  sim_status=125
fi
if [ "${compile_status}" -ne 0 ]; then
  run_status="${compile_status}"
else
  run_status="${sim_status}"
fi
set -e
exit "${run_status}"
"""


def _validate_runtime(runtime: Path) -> dict[str, Any]:
    result = validate_native_json_maxpool_package(runtime)
    if result.get("status") != "hardware_execplan_package_validated":
        raise MaxPoolNativeReuseBuildError("native workload validation differs")
    source_copy = (
        runtime
        / "source_config/maxpool_config_16_112_112_stride2_padding1.json.original"
    )
    if source_copy.read_bytes() != SOURCE_JSON.read_bytes():
        raise MaxPoolNativeReuseBuildError("source JSON bytes changed")
    freeze = json.loads((runtime / "freeze_manifest.json").read_text(encoding="utf-8"))
    tensors = freeze.get("real_resnet_tensors", {})
    numeric = freeze.get("numeric_validation", [])
    if (
        tensors.get("reuse_class") != "EXACT_FULL_OPERATOR"
        or tensors.get("numeric_analysis_repeated") is not False
        or tensors.get("approved_e2_report_sha256") != E2_REPORT_SHA256
        or len(numeric) != 2
        or any(item.get("numeric_analysis_repeated") is not False for item in numeric)
    ):
        raise MaxPoolNativeReuseBuildError("E2 reuse receipt differs")
    return {
        "validation": result,
        "runtime_file_count": len(file_records(runtime)),
        "runtime_tree_sha256": tree_sha256(file_records(runtime)),
        "freeze_manifest_sha256": sha256(runtime / "freeze_manifest.json"),
        "source_json_sha256": sha256(source_copy),
        "approved_e2_report_sha256": E2_REPORT_SHA256,
    }


def build_directory(destination: Path) -> Path:
    package = destination / INSTALL_NAME
    if package.exists():
        raise MaxPoolNativeReuseBuildError("fresh build root required")
    runtime = package / "workload/runtime"
    validation = package / "validation"
    tools = package / "package_tools"
    probe = package / "tb_probe"
    runtime.parent.mkdir(parents=True)
    validation.mkdir()
    tools.mkdir()
    probe.mkdir()
    generate_native_json_maxpool_package(
        ROOT, runtime, reuse_approved_e2=True
    )
    runtime_facts = _validate_runtime(runtime)
    shutil.move(runtime / "manifest.json", validation / "source_workload_manifest.json")
    before_sca = {name: sha256(runtime / name) for name in ("sca_cfg.json", "sca_cfg_D.json")}
    adaptations = [_prefix_sca(runtime / name) for name in ("sca_cfg.json", "sca_cfg_D.json")]
    write_json(
        validation / "materialized_diff.json",
        {
            "schema": "maxpool-node0002-native-materialized-diff-v4",
            "source_json_byte_identity": {
                "path": "workload/runtime/source_config/"
                "maxpool_config_16_112_112_stride2_padding1.json.original",
                "sha256": SOURCE_JSON_SHA256,
                "rewritten": False,
            },
            "operator_json_diff_count": 0,
            "semantic_non_base_diff_count": 0,
            "planner_owned_base_diff_count": 0,
            "transport_only_changed_files": ["sca_cfg.json", "sca_cfg_D.json"],
            "transport_source_sha256": before_sca,
            "transport_adaptations": adaptations,
        },
    )
    shutil.copyfile(RUNTIME_SOURCE, tools / RUNTIME_SOURCE.name)
    shutil.copyfile(RUNTIME_BASE_SOURCE, tools / RUNTIME_BASE_SOURCE.name)
    shutil.copyfile(OBSERVER_SOURCE, probe / "native_return_observer.svh")
    (package / "PREPARE_AND_RUN.sh").write_text(
        _run_script(), encoding="utf-8", newline="\n"
    )
    os.chmod(package / "PREPARE_AND_RUN.sh", 0o755)
    receipts, rule_ids = _rule_receipts()
    checks = _readback_checks(runtime)
    allowlist = _return_allowlist(checks)
    (package / "README.md").write_text(
        "# MaxPool node0002 exact-native JSON dynamic diagnostic\n\n"
        "Run one command from this extracted directory:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "The native ndp-sim MaxPool JSON is packaged byte-for-byte at SHA256 "
        f"`{SOURCE_JSON_SHA256}`. No operator semantic leaf or functional RTL is "
        "changed. Two real ResNet tiles exercise the exact operator configuration; "
        "frozen W3 input/golden and the approved full-node local-E2 result are reused "
        "without repeating MaxPool numeric analysis. The low-volume observer is "
        "read-only and stops after four flat qualified-progress windows.\n",
        encoding="utf-8",
        newline="\n",
    )
    payload = file_records(package)
    manifest = {
        "schema": "maxpool-node0002-native-reuse-server-package-v4",
        "status": "PACKAGE_READY_NOT_RUN",
        "install_name": INSTALL_NAME,
        "test_id": "r5_maxpool_node0002_native_reuse_v4",
        "operator": {
            "node_id": "node-0002",
            "hwop_id": "r5:hwop-0002-00",
            "op_type": "MaxPoolUint8",
            "full_node_shape": {
                "input": [16, 64, 112, 112],
                "output": [16, 64, 56, 56],
            },
            "attributes": {
                "kernel_shape": [3, 3],
                "strides": [2, 2],
                "pads": [1, 1, 1, 1],
                "same_qdomain": True,
            },
        },
        "reuse_class": "EXACT_FULL_OPERATOR",
        "reuse_boundary": {
            "semantic_reuse": "full operator configuration and qdomain",
            "dynamic_occurrence_scope": "two real ResNet channel tiles on slices 0 and 1",
            "not_full_node_e4_e5": True,
            "approved_e2_report": E2_REPORT.relative_to(ROOT).as_posix(),
            "approved_e2_report_sha256": E2_REPORT_SHA256,
        },
        "source_json": {
            "path": SOURCE_JSON.relative_to(ROOT).as_posix(),
            "sha256": SOURCE_JSON_SHA256,
            "size_bytes": SOURCE_JSON.stat().st_size,
            "packaged_copy": "workload/runtime/source_config/"
            "maxpool_config_16_112_112_stride2_padding1.json.original",
            "byte_identical": True,
            "rewritten": False,
            "git_remote": SOURCE_REMOTE,
            "git_commit": SOURCE_COMMIT,
            "git_blob": SOURCE_BLOB,
        },
        "numeric_analysis_repeated": False,
        "workload_rebuilt": False,
        "native_mapping_bitstream_execplan_materialized": True,
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "compile_count": 1,
        "simulation_run_count": 1,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_source_preflight_performed": False,
        "known_open_blockers_not_bypassed": [
            "B_GA_INT8_MAX_FLOW",
            "B_MAXPOOL_SERVER_E4_E5",
        ],
        "observer_binding_four_way": {
            "source_path": "tb_probe/native_return_observer.svh",
            "source_size_bytes": (probe / "native_return_observer.svh").stat().st_size,
            "source_sha256": sha256(probe / "native_return_observer.svh"),
            "include_option": "+incdir+$package_root/tb_probe",
            "compile_enable": "+define+NATIVE_RETURN_OBSERVER_ENABLE",
            "runtime_enable": "+RETURN_OBSERVER",
            "time0_marker": "[MAXPOOL_RETURN_OBSERVER] enabled",
            "return_targets": [
                "evidence/simulator_argv.txt",
                "evidence/observer_binding.json",
                "logs/return_observer.log",
            ],
        },
        "progress_diagnostics": {
            "enabled_by_default": True,
            "read_only": True,
            "low_volume": True,
            "sample_cycles": 262144,
            "stall_windows": 4,
            "source_clock": "clk_sg",
            "snapshot_clock": "clk_db",
            "qualified_events": [
                "local_req_hs",
                "local_rdata_hs",
                "local_wdata_hs",
                "ga_pe_alu_pipeline0_enable",
                "ga_pe_outbuffer_wr_en",
                "slice_cmpt_finish",
            ],
            "raw_levels_not_progress": [
                "alu_pipeline0_valid_bit",
                "alu_pipeline0_bp_post",
            ],
            "canonical_prefix": CANONICAL_PREFIX.strip(),
            "feature_specific_runtime_gate": None,
            "feature_enable_rule_applicability": "NOT_APPLICABLE_NO_SUBFEATURE_GATE",
            "required_after_compile_success": [
                "evidence/simulator_argv.txt",
                "evidence/observer_binding.json",
                "logs/return_observer.log",
                "logs/host_progress.log",
            ],
        },
        "readback_checks": checks,
        "return_allowlist": allowlist,
        "budgets": {
            "return_zip_max_bytes": 16 << 20,
            "return_extracted_max_bytes": 32 << 20,
            "per_text_file_max_bytes": 8 << 20,
        },
        "rule_receipts": receipts,
        "rule_ids": rule_ids,
        "current_rule_match": True,
        "only_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "expected_return": f"{INSTALL_NAME}_return.zip",
        "source_workload": runtime_facts,
        "payload_tree_sha256": tree_sha256(payload),
        "files": payload,
    }
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)
    preflight_package(package, INSTALL_NAME)
    return package


def write_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{INSTALL_NAME}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def build() -> dict[str, Any]:
    for target in (OUTPUT_ZIP, OUTPUT_SIDECAR, BUILD_RECEIPT):
        if target.exists():
            raise MaxPoolNativeReuseBuildError(f"fresh output required: {target}")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="maxpool-v4-a-") as first_text:
        first = Path(first_text)
        package = build_directory(first)
        first_zip = first / OUTPUT_ZIP.name
        write_zip(package, first_zip)
        with tempfile.TemporaryDirectory(prefix="maxpool-v4-b-") as second_text:
            second = Path(second_text)
            second_package = build_directory(second)
            second_zip = second / OUTPUT_ZIP.name
            write_zip(second_package, second_zip)
            if first_zip.read_bytes() != second_zip.read_bytes():
                raise MaxPoolNativeReuseBuildError("deterministic package rebuild differs")
        shutil.copyfile(first_zip, OUTPUT_ZIP)
    OUTPUT_SIDECAR.write_text(
        f"{sha256(OUTPUT_ZIP)}  {OUTPUT_ZIP.name}\n",
        encoding="ascii",
        newline="\n",
    )
    receipt = {
        "schema": "maxpool-node0002-native-reuse-build-v4",
        "status": "BUILT_PENDING_INDEPENDENT_FINAL_ZIP_AUDIT",
        "zip": OUTPUT_ZIP.relative_to(ROOT).as_posix(),
        "zip_size_bytes": OUTPUT_ZIP.stat().st_size,
        "zip_sha256": sha256(OUTPUT_ZIP),
        "sidecar": OUTPUT_SIDECAR.relative_to(ROOT).as_posix(),
        "sidecar_sha256": sha256(OUTPUT_SIDECAR),
        "deterministic_double_build": True,
        "numeric_analysis_repeated": False,
        "source_json_sha256": SOURCE_JSON_SHA256,
    }
    write_json(BUILD_RECEIPT, receipt)
    return receipt


def main() -> int:
    try:
        value = build()
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"MaxPool native-reuse package build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
