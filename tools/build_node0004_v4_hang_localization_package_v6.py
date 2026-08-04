from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.node0004_hang_localization_runtime_v6 import (  # noqa: E402
    package_records,
    preflight,
    sha256,
)
from tools.node0004_package_observer_guard import (  # noqa: E402
    observer_precompile_receipt,
)


INSTALL_NAME = "r5_n4_hw_v6_hangloc"
SOURCE_INSTALL_NAME = "r5_n4_hw_v4_rootbind"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v4_rootbind.zip"
)
SOURCE_ZIP_SHA256 = (
    "61e28a7c218230869ad1a5247023edb9bf8ee9af5a0660124fc8966ce5ad239e"
)
RETURN_ZIP_SHA256 = (
    "14ae820aeba624d92189f482603f8777f9fd8c43c01a3e9b455b03fe0e5e0983"
)
PLAN_SHA256 = (
    "0a32926c67670a2e1d43cddf809ae7284eb62b8f859772647703bf6ecde36010"
)
SERVER_RULE_SHA256 = (
    "2e5cf649cd721f4444b0caca2d1ea6670823c02d9d86784d6d228351ea8c7227"
)
BASE_OBSERVER = ROOT / "NDP_copy01/native_return_observer.svh"
OBSERVER_TAIL = ROOT / "tools/node0004_hang_localization_observer_tail_v6.svh"
RUNTIME_SOURCE = ROOT / "tools/node0004_hang_localization_runtime_v6.py"
OBSERVER_GUARD = ROOT / "tools/node0004_package_observer_guard.py"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_PREFIX = f"install/cfg_pkg/{SOURCE_INSTALL_NAME}/"
CURRENT_PREFIX = f"install/cfg_pkg/{INSTALL_NAME}/"


class BuildError(ValueError):
    pass


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{package.name}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, (2026, 7, 30, 0, 0, 0))
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _safe_entries(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    prefix = f"{SOURCE_INSTALL_NAME}/"
    result: list[zipfile.ZipInfo] = []
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        pure = PurePosixPath(name)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in name
            or name in seen
            or (mode and stat.S_ISLNK(mode))
            or not name.startswith(prefix)
        ):
            raise BuildError(f"unsafe source member: {name}")
        seen.add(name)
        if not info.is_dir():
            result.append(info)
    return result


def _extract_c0_only(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise BuildError("frozen v4 source ZIP identity differs")
    package = destination / INSTALL_NAME
    package.mkdir(parents=True)
    allowed_roots = (
        "workload/runtime/runs/c0/",
        "workload/runtime/",
    )
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("frozen v4 source ZIP CRC failed")
        for info in _safe_entries(archive):
            relative = PurePosixPath(info.filename).relative_to(
                SOURCE_INSTALL_NAME
            )
            relative_text = relative.as_posix()
            keep = (
                relative_text.startswith("workload/runtime/runs/c0/")
                or (
                    relative_text.startswith("workload/runtime/")
                    and "/runs/" not in f"/{relative_text}"
                )
            )
            if not keep:
                continue
            target = package / Path(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    if not (package / "workload/runtime/runs/c0/sca_cfg.json").is_file():
        raise BuildError("c0 extraction is incomplete")
    return package


def _replace_prefix(value: Any) -> tuple[Any, int]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        count = 0
        for key, item in value.items():
            result[key], delta = _replace_prefix(item)
            count += delta
        return result, count
    if isinstance(value, list):
        result_list: list[Any] = []
        count = 0
        for item in value:
            updated, delta = _replace_prefix(item)
            result_list.append(updated)
            count += delta
        return result_list, count
    if isinstance(value, str) and value.startswith(SOURCE_PREFIX):
        return CURRENT_PREFIX + value[len(SOURCE_PREFIX) :], 1
    return value, 0


def _relocate_c0(package: Path) -> dict[str, Any]:
    result: dict[str, int] = {}
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        path = package / "workload/runtime/runs/c0" / name
        before = json.loads(path.read_text(encoding="utf-8"))
        after, count = _replace_prefix(before)
        write_json(path, after)
        result[name] = count
    if result != {"sca_cfg.json": 86, "sca_cfg_D.json": 28}:
        raise BuildError(f"c0 SCA relocation differs: {result}")
    return {
        "changed_sca_file_count": 2,
        "input_path_leaf_count": 86,
        "formal_d_path_leaf_count": 28,
        "old_prefix": SOURCE_PREFIX,
        "new_prefix": CURRENT_PREFIX,
        "non_path_semantics_changed": False,
    }


def _observer(package: Path) -> str:
    base = BASE_OBSERVER.read_text(encoding="utf-8")
    tail = OBSERVER_TAIL.read_text(encoding="utf-8")
    if "DIAG_DECISION" in base:
        raise BuildError("base observer unexpectedly contains v6 diagnostic")
    target = package / "tb_probe/native_return_observer.svh"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        base.rstrip() + "\n\n" + tail,
        encoding="utf-8",
        newline="\n",
    )
    return sha256(target)


def _runner(observer_sha: str) -> str:
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
runtime="${{package_root}}/package_tools/node0004_hang_localization_runtime.py"
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
mkdir -p "$cfg_root" "$run_root/compile/sim_results" "$run_root/c0" "$evidence_root"
python3 "$runtime" preflight --package-root "$package_root" \
  > "$evidence_root/package_preflight.json" || exit 5
cp -a "$package_root/workload/runtime/." "$cfg_root/"
python3 "$runtime" verify-install --package-root "$package_root" \
  --cfg-root "$cfg_root" > "$evidence_root/install_preflight.json" || exit 6
python3 "$observer_guard" --package-root "$package_root" \
  --expected-sha256 "{observer_sha}" \
  > "$evidence_root/observer_precompile.json" || exit 7
compile_status=125
run_status=125
signal_status=NONE
finalized=0
sim_pid=
host_progress_pid=
finalize() {{
  original="$1"; [ "$finalized" -eq 0 ] || exit "$original"; finalized=1
  trap - EXIT INT TERM HUP
  set +e
  [ -z "$host_progress_pid" ] || kill "$host_progress_pid" 2>/dev/null
  [ -z "$host_progress_pid" ] || wait "$host_progress_pid" 2>/dev/null
  printf '%s\\n' "$compile_status" > "$evidence_root/compile_exit_status.txt"
  printf '%s\\n' "$run_status" > "$evidence_root/run_exit_status.txt"
  printf '%s\\n' "$signal_status" > "$evidence_root/signal_status.txt"
  python3 "$runtime" analyze --package-root "$package_root" \
    --evidence-root "$evidence_root" --run-root "$run_root"
  analysis=$?
  python3 "$runtime" collect --server-root "$server_root" \
    --install-name "$install_name" --evidence-root "$evidence_root" \
    --run-root "$run_root"
  collection=$?
  final="$original"
  [ "$final" -ne 0 ] || [ "$analysis" -eq 0 ] || final="$analysis"
  [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] || final="$collection"
  exit "$final"
}}
on_signal() {{
  signal_status="$1"
  [ -z "$sim_pid" ] || kill -TERM "$sim_pid" 2>/dev/null
  finalize "$2"
}}
trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
cd "$server_root"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 \
  TB_DUMP_FSDB=0 RUN_DIR="$run_root/compile" \
  VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe" \
  > "$run_root/compile/sim_results/compile_driver.log" 2>&1
compile_status=$?
[ "$compile_status" -eq 0 ] || exit "$compile_status"
simv="$run_root/compile/sim_results/simv"
printf '%s\\n' \
  "$simv -l $run_root/c0/sim.log +vcs+lic+wait +SCA_CFG=$cfg_root/runs/c0/sca_cfg.json +SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json +RETURN_OBSERVER +RETURN_OBS_SLICE=0 +RETURN_OBS_HEARTBEAT_CYCLES=262144 +RETURN_HANG_DIAG +RETURN_HANG_DIAG_SAMPLE_CYCLES=262144 +RETURN_HANG_DIAG_STALL_WINDOWS=4 +RETURN_HANG_DIAG_MAX_CYCLES=8388608 +RETURN_OBS_FILE=$run_root/c0/return_observer.log" \
  > "$run_root/c0/simulator_argv.txt"
timeout --foreground --signal=TERM --kill-after=30s 6h "$simv" \
  -l "$run_root/c0/sim.log" +vcs+lic+wait \
  "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" \
  "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" \
  +RETURN_OBSERVER +RETURN_OBS_SLICE=0 \
  +RETURN_OBS_STALL_CYCLES=4096 \
  +RETURN_OBS_HEARTBEAT_CYCLES=262144 \
  +RETURN_HANG_DIAG \
  +RETURN_HANG_DIAG_SAMPLE_CYCLES=262144 \
  +RETURN_HANG_DIAG_STALL_WINDOWS=4 \
  +RETURN_HANG_DIAG_MAX_CYCLES=8388608 \
  "+RETURN_OBS_FILE=$run_root/c0/return_observer.log" &
sim_pid=$!
(
  while kill -0 "$sim_pid" 2>/dev/null; do
    read -r host_monotonic _ < /proc/uptime
    host_epoch="$(date +%s)"
    observer_bytes=0
    last_progress=NONE
    if [ -f "$run_root/c0/return_observer.log" ]; then
      observer_bytes="$(wc -c < "$run_root/c0/return_observer.log")"
      last_progress="$(grep -a 'PROGRESS_WINDOW' "$run_root/c0/return_observer.log" | tail -n 1)"
      [ -n "$last_progress" ] || last_progress=NONE
    fi
    printf 'host_epoch=%s host_monotonic=%s stage=c0 start_comp_expected=1 completed_stages=0 observer_bytes=%s last_progress=%s\\n' \
      "$host_epoch" "$host_monotonic" "$observer_bytes" "$last_progress"
    sleep 60
  done
) > "$run_root/c0/host_progress.log" 2>&1 &
host_progress_pid=$!
wait "$sim_pid"
run_status=$?
sim_pid=
kill "$host_progress_pid" 2>/dev/null
wait "$host_progress_pid" 2>/dev/null
host_progress_pid=
exit "$run_status"
"""


def _readme() -> str:
    return f"""# node0004 v6 bounded hang-localization package

Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

This package is not a Conv result candidate and cannot establish E4/E5.  It
preserves only frozen v4 c0 inputs and stops on either natural c0 terminal, four
consecutive 262144-cycle no-progress windows, or an 8388608-cycle diagnostic
budget.  It never extends the v4 12-hour timeout and never modifies functional
RTL.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip` and adjacent `.sha256`.
"""


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = _extract_c0_only(destination)
    relocation = _relocate_c0(package)
    observer_sha = _observer(package)
    tools_dir = package / "package_tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        RUNTIME_SOURCE,
        tools_dir / "node0004_hang_localization_runtime.py",
    )
    shutil.copy2(OBSERVER_GUARD, tools_dir / OBSERVER_GUARD.name)
    runner = package / "PREPARE_AND_RUN.sh"
    runner.write_text(_runner(observer_sha), encoding="utf-8", newline="\n")
    runner.chmod(0o755)
    (package / "README.md").write_text(
        _readme(), encoding="utf-8", newline="\n"
    )
    manifest = {
        "schema": "resnet50-node0004-hang-localization-package-v6",
        "install_name": INSTALL_NAME,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "status": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_PLUS_V4_PARTIAL_DYNAMIC",
        "run_ids": ["c0"],
        "frozen_source_package": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "sha256": SOURCE_ZIP_SHA256,
        },
        "bound_v4_return_sha256": RETURN_ZIP_SHA256,
        "active_receipts": {
            "plan_mutable_provenance_sha256": PLAN_SHA256,
            "server_package_rule_sha256": SERVER_RULE_SHA256,
            "rules": [
                "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
                "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
            ],
        },
        "unresolved_boundary": (
            "c0 Start_Comp accepted; first non-progress boundary is not "
            "observable in v4 between qualified read requests/data, SA input/"
            "transout/buffer5, D request/data, and last_index0 slice finish"
        ),
        "progress_contract": {
            "host_sample_period_seconds": 60,
            "simulation_sample_cycles": 262144,
            "stall_windows": 4,
            "stall_window_cycles": 1048576,
            "max_diagnostic_cycles": 8388608,
            "normal_minimum_progress_event": (
                "at least one qualified request, read-data, buffer4/5 "
                "read/write, D request, or D write-data handshake"
            ),
            "stage": "c0",
            "start_comp_sequence": 1,
            "completed_stage_initial_value": 0,
            "host_monotonic_source": "/proc/uptime",
            "simulation_time_source": "$time in native observer",
            "per_text_log_max_bytes": 8388608,
        },
        "expected_c0_slice0_counts": {
            "read_stream0_requests": 256,
            "read_stream1_requests": 50176,
            "read_stream3_requests": 1568,
            "write_stream0_requests": 12544,
            "write_stream0_data": 12544,
            "natural_slice_finish": 1,
        },
        "decision_table": [
            ["LC_TO_READ_REQUEST", "no qualified A/B/C request"],
            ["READ_REQUEST_TO_MEMORY_DATA", "request exists, no read data"],
            ["READ_DATA_TO_SA_INPUT_C", "read data exists, buffer4 never read"],
            [
                "SA_INPUT_MATCH_TO_SA_OUTPUT_BUFFER5",
                "buffer4 read exists, buffer5 never written",
            ],
            [
                "BUFFER5_WRITE_TO_BUFFER5_READ",
                "buffer5 written but never consumed",
            ],
            [
                "BUFFER5_READ_TO_D_WRITE_REQUEST",
                "buffer5 consumed, no D request",
            ],
            [
                "D_WRITE_REQUEST_TO_D_WRITE_DATA",
                "D request exists, no D data acceptance",
            ],
            [
                "D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH",
                "D data accepted, no natural terminal",
            ],
        ],
        "c0_root_relocation": relocation,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "frozen_c0_inputs_reused_read_only": True,
        "formal_readback_claimed": False,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_action": False,
        "quarantined_package": {
            "name": "r5_n4_hw_v5_observe.zip",
            "sha256": (
                "fb7a36e380c1329c29faf9170a0e117715bdc0d0198bc0568e47298d517844cb"
            ),
            "status": "QUARANTINED_PENDING_HANG_REVIEW",
        },
        "observer_sha256": observer_sha,
    }
    manifest["files"] = package_records(package)
    write_json(package / "package_manifest.json", manifest)
    proof = preflight(package)
    observer = observer_precompile_receipt(package, observer_sha)
    if not observer["valid"]:
        raise BuildError(f"observer XMR gate failed: {observer['errors']}")
    return package, {
        "preflight": proof,
        "observer": observer,
        "relocation": relocation,
    }


def _repeat(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path)
    records = package_records(package)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v6-repeat-") as temporary:
        repeat_root = Path(temporary)
        repeat_package, _ = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeat_package, repeat_zip)
        if records != package_records(repeat_package):
            raise BuildError("repeated package trees differ")
        if digest != sha256(repeat_zip):
            raise BuildError("repeated deterministic ZIPs differ")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    package_path = output / INSTALL_NAME
    zip_path = output / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    output.mkdir(parents=True, exist_ok=True)
    try:
        package, proof = build_directory(output)
        repeated = _repeat(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        receipt = {
            "schema": "node0004-hang-localization-package-validation-v6",
            "status": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN",
            "package": str(package),
            "zip": str(zip_path),
            "zip_bytes": zip_path.stat().st_size,
            "zip_sha256": digest,
            "sidecar": str(sidecar),
            "source_zip_sha256": SOURCE_ZIP_SHA256,
            "bound_return_sha256": RETURN_ZIP_SHA256,
            "package_file_count": proof["preflight"]["package_file_count"],
            "observer_sha256": proof["preflight"]["observer_sha256"],
            "observer_static_gate": proof["observer"]["xmr_static_gate"],
            "observer_runtime_enabled": True,
            "observer_return_allowlisted": True,
            "host_monotonic_return_allowlisted": True,
            "simulator_argv_return_allowlisted": True,
            "stall_window_cycles": 1048576,
            "max_diagnostic_cycles": 8388608,
            "c0_only": True,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
            "repeated_build": repeated,
        }
        write_json(validation, receipt)
    except Exception as error:
        print(f"package build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
