from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_node0004_assumed_hardware_server_package as base  # noqa: E402
from tools import conv_native_four_lane_df23e4d_server_runtime as runtime  # noqa: E402


INSTALL_NAME = "r5_conv_native_four_lane_df23e4d_perf_v1"
OUTPUT_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
LOCAL_ROOT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-conv-native-four-lane-df23e4d-v1"
)
LOCAL_CONTRACT = (
    ROOT
    / "contracts/operator_config"
    / "r5_conv_native_four_lane_df23e4d_local_e2_v1.json"
)
REVALIDATION = (
    ROOT / "outputs/conv_native_four_lane_df23e4d_revalidation/report.json"
)
SYNC_REPORT = (
    ROOT
    / "artifacts/rtl_sync/trassic_master_df23e4d_20260804/report.json"
)
OBSERVER_SOURCE = (
    ROOT
    / "tests/rtl_audit"
    / "conv_native_four_lane_df23e4d_progress_observer.svh"
)
OBSERVER_SHA256 = base.sha256(OBSERVER_SOURCE)
RULE_RECEIPTS = {
    ".agents/agent.md": (
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
    ),
    ".agents/rules/生成前必读索引.md": (
        "5146225e549942c4e25780ac4fc0120d7cac1ef355879284450dad2e48df237b"
    ),
    ".agents/rules/服务器测试包生成规则.md": (
        "0916c655b0581cd99836d8cc1561a3f41b15b25e861692d596a4789c039b090e"
    ),
    ".agents/rules/算子配置规则.md": (
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"
    ),
    ".agents/rules/NDP硬件字段语义.md": (
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
    ),
    ".agents/rules/INT8_SA点积专项规则.md": (
        "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
    ),
    ".agents/rules/精确UINT8量化尾专项规则.md": (
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"
    ),
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": (
        "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7"
    ),
}


class PackageBuildError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PackageBuildError(f"JSON root must be an object: {path}")
    return value


def check_inputs() -> None:
    expected = {
        LOCAL_CONTRACT: (
            "f9ecec4f99a5a906637ef5f480329513acc0202b59baee4b9387fb93b05446a2"
        ),
        REVALIDATION: (
            "d681d682ad38ccb7a72427a9cfbba2d8e232d1a6e7be6adef784604f958e2f92"
        ),
        SYNC_REPORT: (
            "6cf79c6d461ffb73ba7554dec8056b178a81ec5018bd0068accda4efb9a366a5"
        ),
        OBSERVER_SOURCE: OBSERVER_SHA256,
    }
    expected.update({ROOT / path: digest for path, digest in RULE_RECEIPTS.items()})
    errors = [
        f"{path}: identity differs"
        for path, digest in expected.items()
        if not path.is_file() or base.sha256(path) != digest
    ]
    if errors:
        raise PackageBuildError("; ".join(errors))
    local = load_json(LOCAL_CONTRACT)
    if (
        local.get("status") != "LOCAL_E2_PASS"
        or local.get("candidate_release") is not False
        or local.get("stage_gates", {}).get("config_bound_E2") is not True
    ):
        raise PackageBuildError("local E2 contract is not closed")


def run_script() -> str:
    tail_ids = " ".join(
        f"t{wave}{shard:02d}"
        for wave in range(3)
        for shard in range(8)
    )
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
runtime="${{package_root}}/package_tools/node0004_assumed_hardware_server_runtime.py"
observer_guard="${{package_root}}/package_tools/node0004_package_observer_guard.py"
install_name="{INSTALL_NAME}"
cfg_root="${{server_root}}/install/cfg_pkg/${{install_name}}"
run_root="${{server_root}}/run_${{install_name}}"
evidence_root="${{server_root}}/evidence_${{install_name}}"
return_dir="${{server_root}}/${{install_name}}_return"
return_zip="${{return_dir}}.zip"
return_sha="${{return_zip}}.sha256"
for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || exit 3; done
for fresh in "$cfg_root" "$run_root" "$evidence_root" "$return_dir" "$return_zip" "$return_sha"; do
  [ ! -e "$fresh" ] || {{ echo "Fresh namespace required: $fresh" >&2; exit 4; }}
done
mkdir -p "$cfg_root" "$run_root/compile/sim_results" "$evidence_root/natural_terminal"
python3 "$runtime" preflight --package-root "$package_root" \
  > "$evidence_root/package_preflight.json" || exit 5
cp -a "$package_root/workload/runtime/." "$cfg_root/"
python3 "$runtime" verify-install --package-root "$package_root" \
  --cfg-root "$cfg_root" > "$evidence_root/install_preflight.json" || exit 6
python3 "$observer_guard" --package-root "$package_root" \
  > "$evidence_root/observer_precompile.json" || exit 7
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
  python3 "$runtime" analyze --package-root "$package_root" \
    --cfg-root "$cfg_root" --evidence-root "$evidence_root"
  analysis=$?
  python3 "$runtime" collect --server-root "$server_root" \
    --install-name "$install_name" --evidence-root "$evidence_root" \
    --run-root "$run_root" --cfg-root "$cfg_root" \
    --package-root "$package_root"
  collection=$?
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
printf '%s\\n' \
  "make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=$run_root/compile VCS_EXTRA_OPTS=+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe" \
  > "$evidence_root/compile_argv.txt"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 \
  TB_DUMP_FSDB=0 RUN_DIR="$run_root/compile" \
  VCS_EXTRA_OPTS="+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe" \
  > "$run_root/compile/sim_results/compile_driver.log" 2>&1
compile_status=$?
[ "$compile_status" -eq 0 ] || exit "$compile_status"
python3 "$runtime" compile-identity \
  --compile-log "$run_root/compile/sim_results/compile_driver.log" \
  --output "$evidence_root/production_rtl_identity.json" || exit 8
simv="$run_root/compile/sim_results/simv"
run_one() {{
  id="$1"
  case "$id" in c*) expected_stages=1;; t*) expected_stages=2;; esac
  mkdir -p "$run_root/$id"
  observer_log="$run_root/$id/return_observer.log"
  printf '%s\\n' \
    "$simv -l $run_root/$id/sim.log +vcs+lic+wait +SCA_CFG=$cfg_root/runs/$id/sca_cfg.json +SCA_CFG_D=$cfg_root/runs/$id/sca_cfg_D.json +RETURN_OBSERVER +RETURN_OBS_SLICE=0 +RETURN_OBS_STALL_CYCLES=1048576 +RETURN_OBS_HEARTBEAT_CYCLES=262144 +RETURN_OBS_EXPECTED_STAGES=$expected_stages +RETURN_OBS_FILE=$observer_log" \
    > "$run_root/$id/simulator_argv.txt"
  timeout --foreground --signal=TERM --kill-after=30s 12h "$simv" \
    -l "$run_root/$id/sim.log" +vcs+lic+wait \
    "+SCA_CFG=$cfg_root/runs/$id/sca_cfg.json" \
    "+SCA_CFG_D=$cfg_root/runs/$id/sca_cfg_D.json" \
    +RETURN_OBSERVER +RETURN_OBS_SLICE=0 \
    +RETURN_OBS_STALL_CYCLES=1048576 \
    +RETURN_OBS_HEARTBEAT_CYCLES=262144 \
    "+RETURN_OBS_EXPECTED_STAGES=$expected_stages" \
    "+RETURN_OBS_FILE=$observer_log" &
  sim_pid=$!
  (
    while kill -0 "$sim_pid" 2>/dev/null; do
      host_epoch="$(date +%s)"
      observer_bytes=0
      [ ! -f "$observer_log" ] || observer_bytes="$(wc -c < "$observer_log")"
      printf 'host_epoch=%s run=%s observer_bytes=%s\\n' \
        "$host_epoch" "$id" "$observer_bytes"
      sleep 60
    done
  ) > "$run_root/$id/host_progress.log" 2>&1 &
  progress_pid=$!
  wait "$sim_pid"
  status=$?
  sim_pid=
  kill "$progress_pid" 2>/dev/null
  wait "$progress_pid" 2>/dev/null
  progress_pid=
  [ "$status" -eq 0 ] || return "$status"
  python3 "$runtime" qualify-run --run-id "$id" \
    --sim-log "$run_root/$id/sim.log" \
    --observer-log "$observer_log" \
    --output "$evidence_root/natural_terminal/$id.json"
}}
for id in c0 c1 c2; do
  run_one "$id" || {{ run_status=$?; exit "$run_status"; }}
done
python3 "$runtime" materialize-tail --package-root "$package_root" \
  --cfg-root "$cfg_root" --output "$evidence_root/tail_materialization.json" \
  || {{ run_status=$?; exit "$run_status"; }}
for id in {tail_ids}; do
  run_one "$id" || {{ run_status=$?; exit "$run_status"; }}
done
run_status=0
exit 0
"""


def augment_package(package: Path) -> Path:
    tools_root = package / "package_tools"
    shutil.copy2(
        ROOT / "tools/node0004_assumed_hardware_server_runtime_v5.py",
        tools_root / "node0004_assumed_hardware_server_runtime_v5_base.py",
    )
    shutil.copy2(
        ROOT / "tools/node0004_assumed_hardware_server_runtime_v2.py",
        tools_root / "node0004_assumed_hardware_server_runtime_v2_base.py",
    )
    shutil.copy2(
        ROOT / "tools/conv_native_four_lane_package_observer_guard.py",
        tools_root / "node0004_package_observer_guard.py",
    )
    observer = package / "tb_probe/native_return_observer.svh"
    observer.parent.mkdir()
    shutil.copy2(OBSERVER_SOURCE, observer)
    if base.sha256(observer) != OBSERVER_SHA256:
        raise PackageBuildError("copied observer identity differs")

    local = load_json(LOCAL_CONTRACT)
    provenance = {
        "schema": "conv-native-four-lane-df23e4d-rtl-binding-v1",
        "upstream_commit": "df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727",
        "sync_report_sha256": base.sha256(SYNC_REPORT),
        "expected_production_leaves": runtime.EXPECTED_LEAVES,
        "binding_policy": (
            "post-compile VCS parsing receipts and production-path hashes"
        ),
        "server_source_preflight_performed": False,
        "functional_rtl_in_package": False,
    }
    base.write_json(
        package / "provenance/current_local_rtl_binding.json", provenance
    )
    base.write_json(
        package / "TEST_PACKAGE_MANIFEST.json",
        {
            "schema": "conv-native-four-lane-test-package-pointer-v1",
            "status": "PACKAGE_READY_NOT_RUN",
            "install_name": INSTALL_NAME,
            "canonical_manifest": "package_manifest.json",
            "candidate_release": False,
            "formal_readback_count": 320,
        },
    )
    (package / "README.md").write_text(
        "# Conv node0004 native-four-lane performance candidate\n\n"
        "Run exactly once from the extracted package root:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy01\n"
        "```\n\n"
        "This is a non-release performance diagnostic candidate. It compiles "
        "the production server RTL once, executes 3 Conv waves and 24 "
        "requant-tail runs, requires a natural terminal for every run, and "
        "checks 320 formal D endpoints. It carries no functional RTL and "
        "does not inspect server source before compilation. The return ZIP "
        "is created on success or failure.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest = load_json(package / "package_manifest.json")
    for record in manifest.get("readback_checks", []):
        runtime_d = (
            package
            / "workload/runtime"
            / Path(*Path(str(record["runtime_path"])).parts)
        )
        if runtime_d.is_file():
            runtime_d.unlink()
    manifest.update(
        {
            "schema": "resnet50-conv-native-four-lane-df23e4d-server-package-v1",
            "status": "PACKAGE_READY_NOT_RUN",
            "package_release": "PACKAGE_READY_NOT_RUN",
            "candidate_class": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "install_name": INSTALL_NAME,
            "run_namespace": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return.zip",
            "current_local_contract": {
                "path": str(LOCAL_CONTRACT.relative_to(ROOT)).replace("\\", "/"),
                "sha256": base.sha256(LOCAL_CONTRACT),
            },
            "current_rtl_revalidation": {
                "path": str(REVALIDATION.relative_to(ROOT)).replace("\\", "/"),
                "sha256": base.sha256(REVALIDATION),
            },
            "expected_production_rtl_identity": {
                "commit": "df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727",
                "leaves": runtime.EXPECTED_LEAVES,
                "receipt_timing": "after actual production VCS compile",
            },
            "server_source_identity_bound": True,
            "server_source_preflight_performed": False,
            "formal_readback_count": 320,
            "natural_terminal_required_count": 27,
            "functional_rtl_modified": False,
            "functional_rtl_file_count": 0,
            "server_rtl_entries": 0,
            "host_precompute_internal_tensor": False,
            "observer_binding": {
                "source": "tb_probe/native_return_observer.svh",
                "source_sha256": OBSERVER_SHA256,
                "compile_include": (
                    "VCS_EXTRA_OPTS=+define+NATIVE_RETURN_OBSERVER_ENABLE "
                    "+incdir+<package_root>/tb_probe"
                ),
                "runtime_enable": "+RETURN_OBSERVER",
                "runtime_limits": [
                    "+RETURN_OBS_HEARTBEAT_CYCLES=262144",
                    "+RETURN_OBS_STALL_CYCLES=1048576",
                    "+RETURN_OBS_EXPECTED_STAGES=<1|2>",
                ],
                "time0_marker": (
                    "N4PERF_FEATURE_ENABLE_V1 "
                    "feature=NATIVE4_PROGRESS enabled=1"
                ),
                "canonical_record": "N4PERF_CANONICAL_DECISION_V1",
                "runtime_return_target": "+RETURN_OBS_FILE=<run>/return_observer.log",
                "return_allowlist": "runs/<run_id>/return_observer.log",
                "does_not_force_terminal": True,
            },
            "progress_diagnostics": {
                "feature": "NATIVE4_PROGRESS",
                "qualified_events": [
                    "cfg start/finish rising event",
                    "exec start/slice finish rising event",
                    "local request/rdata/wdata handshake",
                    "bank frame accepted handshake",
                ],
                "raw_levels_excluded_from_progress": True,
                "canonical_decisions": [
                    "HEARTBEAT",
                    "STILL_PROGRESSING",
                    "LONG_RUNNING_HANG_AT_EXEC_TO_SLICE_FINISH",
                    "EXPECTED_STAGE_PREFIX_COMPLETE",
                    "INCOMPLETE_AT_SIMULATOR_END",
                ],
                "minimum_expected_forward_event": (
                    "at least one qualified delta per stall window while active"
                ),
                "observer_heartbeat_cycles": 262144,
                "host_heartbeat_seconds": 60,
                "stall_window_cycles": 1048576,
                "return_log_max_bytes": 8 * 1024 * 1024,
            },
            "return_budget": {
                "zip_max_bytes": 128 * 1024 * 1024,
                "expanded_max_bytes": 512 * 1024 * 1024,
                "single_text_max_bytes": 8 * 1024 * 1024,
                "reason": "320 exact formal D readbacks require an explicit uplift",
            },
            "return_allowlist_contract": {
                "required_control": [
                    "RETURN_MANIFEST.json",
                    "RETURN_ALLOWLIST.json",
                    "evidence/package_preflight.json",
                    "evidence/install_preflight.json",
                    "evidence/compile_exit_status.txt",
                    "evidence/run_exit_status.txt",
                    "evidence/signal_status.txt",
                    "evidence/SERVER_RESULT_GATE.json",
                    "source_package/package_manifest.json",
                ],
                "success_required": [
                    "evidence/production_rtl_identity.json",
                    "evidence/natural_terminal/<27 run ids>.json",
                    "runs/<27 run ids>/simulator_argv.txt",
                    "runs/<27 run ids>/return_observer.log",
                    "readbacks/<320 formal runtime paths>",
                ],
                "partial_optional": [
                    "evidence/tail_materialization.json",
                    "runs/<run id>/sim.log",
                    "runs/<run id>/host_progress.log",
                    "runs/compile/sim_results/compile_driver.log",
                    "runs/compile/sim_results/compile.log",
                ],
                "forbidden": [
                    "csrc/",
                    "simv",
                    "simv.daidir/",
                    "waveform",
                    "nested archive",
                    "complete run/install tree",
                ],
            },
            "workload_provenance": {
                "rebuild_chain": (
                    "planner->encoder->mapping->bitstream->execplan->SCA/SCA_D"
                ),
                "local_artifact_root": str(LOCAL_ROOT.relative_to(ROOT)).replace(
                    "\\", "/"
                ),
                "local_contract_sha256": base.sha256(LOCAL_CONTRACT),
                "package_builder": (
                    "tools/build_conv_native_four_lane_df23e4d_server_package.py"
                ),
                "package_builder_sha256": base.sha256(Path(__file__)),
                "cwd": str(ROOT),
                "command": (
                    ".venv/Scripts/python.exe "
                    "tools/build_conv_native_four_lane_df23e4d_server_package.py"
                ),
                "double_fresh_build_required": True,
            },
            "actual_performance_inversion": local[
                "address_lifetime_terminal"
            ]["actual_performance_inversion"],
            "rule_receipts": RULE_RECEIPTS,
            "rule_feedback": {
                "type": "RULE_CONFIRMATION",
                "confirmed": [
                    "CDA-SA-INT8-RTL-COMPATIBILITY-001",
                    "CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001",
                    "final-ZIP exact-set and no-preloaded-D server gates",
                    "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
                    "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
                    "production RTL identity is collected after actual compile",
                    "natural terminal and 320 formal D form one conjunction",
                ],
                "rule_delta_proposal": [],
            },
            "server_action": False,
        }
    )
    if len(manifest.get("readback_checks", [])) != 320:
        raise PackageBuildError("formal readback list is not exactly 320")
    if len(manifest.get("conv_run_ids", [])) != 3:
        raise PackageBuildError("Conv run count differs")
    if len(manifest.get("tail_run_ids", [])) != 24:
        raise PackageBuildError("tail run count differs")
    manifest["files"] = runtime.numeric_base.package_records(package)
    base.write_json(package / "package_manifest.json", manifest)
    runtime.preflight(package)
    return package


def build_directory(destination: Path) -> Path:
    base.INSTALL_NAME = INSTALL_NAME
    base.LOCAL_ROOT = LOCAL_ROOT
    base.RUNTIME_SOURCE = (
        ROOT / "tools/conv_native_four_lane_df23e4d_server_runtime.py"
    )
    base.run_script = run_script
    return augment_package(base.build_directory(destination))


def build_reproducible(output_root: Path) -> dict[str, Any]:
    check_inputs()
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (zip_path, sidecar, validation):
        if path.exists():
            raise PackageBuildError(f"refusing to overwrite: {path}")
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native4-package-a-") as a_name:
        with tempfile.TemporaryDirectory(prefix="native4-package-b-") as b_name:
            package_a = build_directory(Path(a_name))
            package_b = build_directory(Path(b_name))
            zip_a = Path(a_name) / f"{INSTALL_NAME}.zip"
            zip_b = Path(b_name) / f"{INSTALL_NAME}.zip"
            base.deterministic_zip(package_a, zip_a)
            base.deterministic_zip(package_b, zip_b)
            digest_a = base.sha256(zip_a)
            digest_b = base.sha256(zip_b)
            files_equal = (
                runtime.numeric_base.package_records(
                    package_a, exclude_manifest=False
                )
                == runtime.numeric_base.package_records(
                    package_b, exclude_manifest=False
                )
            )
            if digest_a != digest_b or not files_equal:
                raise PackageBuildError("two fresh package builds differ")
            file_count = len(
                runtime.numeric_base.package_records(
                    package_a, exclude_manifest=False
                )
            )
            shutil.copy2(zip_a, zip_path)
    digest = base.sha256(zip_path)
    if digest != digest_a:
        raise PackageBuildError("final ZIP differs from fresh build")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    receipt = {
        "schema": "conv-native-four-lane-df23e4d-package-build-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "candidate_release": False,
        "expanded_package": None,
        "zip": str(zip_path),
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "package_file_count": file_count,
        "deterministic_double_build": {
            "zip_sha256_equal": digest_a == digest_b == digest,
            "exact_file_records_equal": files_equal,
        },
        "formal_readback_count": 320,
        "simulation_run_count": 27,
        "server_action": False,
    }
    base.write_json(validation, receipt)
    return receipt


def main() -> int:
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    try:
        result = build_reproducible(args.output_root.resolve())
    except Exception as error:
        print(f"package build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
