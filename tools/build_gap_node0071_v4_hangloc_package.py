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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import (  # noqa: E402
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import (  # noqa: E402
    file_records,
)


INSTALL_NAME = "r5_n71_gap_v4_hangloc"
SOURCE_NAME = "r5_n71_gap_v3_cwd"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v3_cwd.zip"
)
SOURCE_SHA256 = (
    "3d6c8c580e178717b1c0a9bf70f5c55fd8cbcc8a74c7e9b5673f36b743604c80"
)
RETURN_SHA256 = (
    "a466f809dfc765d245bdca1180cb4422d6142912cdd9a0fcce82d98b2e831d15"
)
OUTPUT_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
)
HEARTBEAT_CYCLES = 262_144
STALL_WINDOW_CYCLES = 1_048_576
HOST_SAMPLE_SECONDS = 60
DEEP_LIMIT = 64
PROGRESS_ALLOWLIST_COUNT = 7


class PackageBuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_entries(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    prefix = f"{SOURCE_NAME}/"
    entries: list[zipfile.ZipInfo] = []
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
            raise PackageBuildError(f"unsafe source member: {name}")
        seen.add(name)
        if not info.is_dir():
            entries.append(info)
    return entries


def _extract_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise PackageBuildError("frozen v3 source identity differs")
    package = destination / INSTALL_NAME
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise PackageBuildError("frozen v3 source CRC failed")
        for info in _safe_entries(archive):
            relative = PurePosixPath(info.filename).relative_to(SOURCE_NAME)
            target = package.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    return package


def _replace_identity(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(SOURCE_NAME, INSTALL_NAME)
    if isinstance(value, list):
        return [_replace_identity(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _replace_identity(item)
            for key, item in value.items()
        }
    return value


def _progress_contract() -> dict[str, Any]:
    return {
        "schema": "gap-node0071-progress-localization-v1",
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "enabled_by_default": True,
        "read_only": True,
        "target_slice": 0,
        "heartbeat_cycles": HEARTBEAT_CYCLES,
        "stall_window_cycles": STALL_WINDOW_CYCLES,
        "host_sample_period_seconds": HOST_SAMPLE_SECONDS,
        "deep_checkpoint_limit": DEEP_LIMIT,
        "minimum_monotonic_windows_for_progress": 2,
        "required_return_records": PROGRESS_ALLOWLIST_COUNT,
        "first_unproven_interval": (
            "sum_s1 Start_Comp -> LC/MSE0 accepted read -> GA accepted/"
            "completed output -> MSE4 accepted D write -> last-data "
            "accepted -> slice_cmpt_finish"
        ),
        "monotonic_counters": [
            "req",
            "rdata",
            "wdata",
            "buf4_wr",
            "buf4_rd",
            "buf5_wr",
            "buf5_rd",
            "deep_addr_enqueue",
            "deep_req_hs",
            "deep_meta",
            "deep_consume",
            "deep_buffer",
            "deep_ga",
            "deep_mse4_idx",
            "sg_ga_input",
            "sg_ga_output",
            "sg_mse4_req",
            "sg_mse4_wdata",
        ],
        "stage_events": [
            "CFG_START",
            "CFG_FINISH",
            "EXEC_START",
            "COMP_FINISH",
        ],
        "last_terminal_evidence": [
            "DEEP_MSE4_INDEX lc0/lc2/pe1/index state",
            "SG_MSE4_REQ/SG_MSE4_WDATA accepted counters",
            "COMP_FINISH slice_cmpt_finish edge",
            "FINAL summary",
        ],
        "outcome_rules": {
            "two_windows_advance": "INTERRUPTED_WHILE_STILL_PROGRESSING",
            "flat_beyond_stall_window": "LONG_RUNNING_HANG_AT_LAST_BOUNDARY",
            "observer_absent": "PACKAGE_RUNTIME_OBSERVER_BINDING_FAILURE",
            "natural_terminal_only": "FUNCTIONAL_EXECUTION_COMPLETED",
        },
    }


def _allowlist_entry(
    source_root: str,
    source_path: str,
    target_path: str,
    max_bytes: int,
    missing_meaning: str,
) -> dict[str, Any]:
    return {
        "source_root": source_root,
        "source_path": source_path,
        "target_path": target_path,
        "required": True,
        "max_bytes": max_bytes,
        "missing_meaning": missing_meaning,
    }


def _progress_allowlist() -> list[dict[str, Any]]:
    return [
        _allowlist_entry(
            "evidence",
            "progress_contract.json",
            "evidence/progress_contract.json",
            1 << 20,
            "declared progress/stall-window contract unavailable",
        ),
        _allowlist_entry(
            "evidence",
            "actual_simulator_argv.txt",
            "evidence/actual_simulator_argv.txt",
            1 << 20,
            "actual observer-enabled simulator argv unavailable",
        ),
        _allowlist_entry(
            "evidence",
            "host_timing.txt",
            "evidence/host_timing.txt",
            1 << 20,
            "host wall-clock evidence unavailable",
        ),
        _allowlist_entry(
            "evidence",
            "signal_status.txt",
            "evidence/signal_status.txt",
            1 << 20,
            "timeout/signal status unavailable",
        ),
        _allowlist_entry(
            "evidence",
            "progress_samples.log",
            "evidence/progress_samples.log",
            8 << 20,
            "host-to-simulator progress samples unavailable",
        ),
        _allowlist_entry(
            "evidence",
            "observer_binding.txt",
            "evidence/observer_binding.txt",
            1 << 20,
            "runtime observer binding result unavailable",
        ),
        _allowlist_entry(
            "run",
            "sim_results/return_observer/return_observer.log",
            "runs/return_observer.log",
            8 << 20,
            "stage/accepted/completion/last/terminal observer unavailable",
        ),
    ]


def _runner() -> str:
    return f"""#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in /*) ;; *) echo "NDP_copy path must be absolute" >&2; exit 2;; esac

package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd -P)"
server_root="$(cd "$1" && pwd -P)"
install_name="{INSTALL_NAME}"
cfg_root="$server_root/install/cfg_pkg/$install_name"
run_root="$server_root/run_$install_name"
evidence_root="$server_root/evidence_$install_name"
return_root="$server_root/${{install_name}}_return"
runtime="$package_root/package_tools/gap_node0071_complete_server_runtime.py"
observer_guard="$package_root/package_tools/gap_node0071_package_observer_guard.py"
observer_log="$run_root/sim_results/return_observer/return_observer.log"
progress_log="$evidence_root/progress_samples.log"
for tool in python3 timeout make date tail tr grep sleep; do
  command -v "$tool" >/dev/null 2>&1 || exit 3
done
for target in "$cfg_root" "$run_root" "$evidence_root" "$return_root" \
  "${{return_root}}.zip" "${{return_root}}.zip.sha256"; do
  [ ! -e "$target" ] || {{ echo "Fresh target required: $target" >&2; exit 4; }}
done

python3 "$runtime" preflight --package-root "$package_root" || exit 5
mkdir -p "$server_root/install/cfg_pkg"
cp -a "$package_root/workload" "$cfg_root"
mkdir "$evidence_root"
mkdir -p "$cfg_root/readback" "$run_root/sim_results/return_observer"
cp "$package_root/TEST_PACKAGE_MANIFEST.json" \
  "$evidence_root/PACKAGE_MANIFEST.json"
cp "$package_root/diagnostics/progress_contract.json" \
  "$evidence_root/progress_contract.json"
python3 "$runtime" preflight-installed --package-root "$package_root" \
  --cfg-root "$cfg_root" >"$evidence_root/installed_preflight.json" || exit 6
python3 "$observer_guard" --package-root "$package_root" \
  --expected-sha256 \
  "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49" \
  >"$evidence_root/observer_precompile.json" || exit 7
printf '%s\n' \
  "make -C <user-root> ... VCS_EXTRA_OPTS=+incdir+<package-root>/tb_probe; (cd <user-root> && <run>/simv +SCA_CFG=install/cfg_pkg/{INSTALL_NAME}/sca_cfg.json +SCA_CFG_D=install/cfg_pkg/{INSTALL_NAME}/sca_cfg_D.json +RETURN_OBSERVER +RETURN_OBS_FILE=<run>/sim_results/return_observer/return_observer.log)" \
  >"$evidence_root/server_command.txt"

package_start_ns="$(date +%s%N)"
printf 'package_start_epoch_ns=%s\n' "$package_start_ns" \
  >"$evidence_root/host_timing.txt"
compile_status=125
simulation_status=125
runner_status=125
signal_name=NONE
sim_pid=0
sampler_pid=0
finalized=0

sample_progress() {{
  host_ns="$(date +%s%N)"
  observer_bytes=0
  observer_tail="OBSERVER_NOT_CREATED"
  if [ -f "$observer_log" ]; then
    observer_bytes="$(wc -c <"$observer_log" | tr -d ' ')"
  fi
  if [ -s "$observer_log" ]; then
    observer_tail="$(tail -n 1 "$observer_log" | tr '\t' ' ')"
  fi
  printf '%s\tobserver_bytes=%s\t%s\n' \
    "$host_ns" "$observer_bytes" "$observer_tail" >>"$progress_log"
}}

progress_sampler() {{
  while kill -0 "$sim_pid" 2>/dev/null; do
    sample_progress
    sleep {HOST_SAMPLE_SECONDS}
  done
  sample_progress
}}

finalize() {{
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1
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
  printf 'final_epoch_ns=%s\n' "$(date +%s%N)" \
    >>"$evidence_root/host_timing.txt"
  runner_status="$original"
  printf 'signal=%s\ncompile_status=%s\nsimulation_status=%s\nrunner_status=%s\n' \
    "$signal_name" "$compile_status" "$simulation_status" "$runner_status" \
    >"$evidence_root/signal_status.txt"
  if [ -s "$observer_log" ] && \
     grep -q 'Native NDP return observer' "$observer_log"; then
    printf 'observer_enabled_and_returned=true\n' \
      >"$evidence_root/observer_binding.txt"
  else
    printf 'observer_enabled_and_returned=false\n' \
      >"$evidence_root/observer_binding.txt"
  fi
  printf '%s\n' "$compile_status" \
    >"$evidence_root/compile_exit_status.txt"
  printf '%s\n' "$simulation_status" \
    >"$evidence_root/simulation_exit_status.txt"
  printf '%s\n' "$runner_status" \
    >"$evidence_root/runner_exit_status.txt"
  python3 "$runtime" analyze --package-root "$package_root" \
    --cfg-root "$cfg_root" --evidence-root "$evidence_root" \
    --run-root "$run_root" --compile-status "$compile_status" \
    --simulation-status "$simulation_status"
  analysis_status=$?
  python3 "$runtime" collect --server-root "$server_root" \
    --install-name "$install_name" --evidence-root "$evidence_root" \
    --run-root "$run_root" --cfg-root "$cfg_root"
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

set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -C "$server_root" -f Makefile.tb_NDP_Top_new_phy compile \
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$run_root" \
  VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe" \
  >"$run_root/sim_results/compile.log" 2>&1
compile_status=$?
[ "$compile_status" -eq 0 ] || exit "$compile_status"

cd "$server_root"
simv="$run_root/sim_results/simv"
sim_args=(
  -l "$run_root/sim_results/sim.log"
  +vcs+lic+wait
  +sim_time=100ms
  +BITSTREAM=install/bitstream.txt
  "+SCA_CFG=install/cfg_pkg/$install_name/sca_cfg.json"
  "+SCA_CFG_D=install/cfg_pkg/$install_name/sca_cfg_D.json"
  +RETURN_OBSERVER
  +RETURN_OBS_SLICE=0
  +RETURN_OBS_STALL_CYCLES={STALL_WINDOW_CYCLES}
  +RETURN_OBS_HEARTBEAT_CYCLES={HEARTBEAT_CYCLES}
  +RETURN_OBS_DEEP
  +RETURN_OBS_DEEP_LIMIT={DEEP_LIMIT}
  "+RETURN_OBS_FILE=$observer_log"
)
printf 'sim_start_epoch_ns=%s\n' "$(date +%s%N)" \
  >>"$evidence_root/host_timing.txt"
printf 'timeout --foreground --signal=TERM --kill-after=30s 12h %q' "$simv" \
  >"$evidence_root/actual_simulator_argv.txt"
printf ' %q' "${{sim_args[@]}}" \
  >>"$evidence_root/actual_simulator_argv.txt"
printf '\n' >>"$evidence_root/actual_simulator_argv.txt"
timeout --foreground --signal=TERM --kill-after=30s 12h \
  "$simv" "${{sim_args[@]}}" &
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


def _patch_runtime(package: Path) -> None:
    path = (
        package
        / "package_tools/gap_node0071_complete_server_runtime.py"
    )
    text = path.read_text(encoding="utf-8")
    anchor = "len(allowlist) != 60"
    if text.count(anchor) != 1:
        raise PackageBuildError("runtime allowlist anchor differs")
    path.write_text(
        text.replace(anchor, "len(allowlist) != 67"),
        encoding="utf-8",
        newline="\n",
    )


def _rebind_sca(package: Path) -> None:
    for relative in ("workload/sca_cfg.json", "workload/sca_cfg_D.json"):
        path = package / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        rebound = _replace_identity(value)
        if rebound == value:
            raise PackageBuildError(f"identity absent from {relative}")
        write_json(path, rebound)
        if SOURCE_NAME in path.read_text(encoding="utf-8"):
            raise PackageBuildError(f"stale source identity in {relative}")


def _numeric_workload_records(package: Path) -> dict[str, Any]:
    records = file_records(
        package / "workload", exclude_manifest=False
    )
    records.pop("sca_cfg.json")
    records.pop("sca_cfg_D.json")
    return records


def _preflight(package: Path) -> dict[str, Any]:
    process = subprocess.run(
        [
            sys.executable,
            str(
                package
                / "package_tools/gap_node0071_complete_server_runtime.py"
            ),
            "preflight",
            "--package-root",
            str(package),
        ],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        raise PackageBuildError(
            f"diagnostic preflight failed: {process.stdout} {process.stderr}"
        )
    value = json.loads(process.stdout)
    if not isinstance(value, dict) or value.get("valid") is not True:
        raise PackageBuildError("diagnostic preflight receipt differs")
    return value


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = _extract_source(destination)
    frozen_before = _numeric_workload_records(package)
    _rebind_sca(package)
    _patch_runtime(package)
    diagnostics = package / "diagnostics"
    diagnostics.mkdir()
    write_json(diagnostics / "progress_contract.json", _progress_contract())
    (package / "PREPARE_AND_RUN.sh").write_text(
        _runner(), encoding="utf-8", newline="\n"
    )
    (package / "README.md").write_text(
        "# GAP node0071 v4 progress localization\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n"
        "It reuses the frozen v3 workload and enables the package-local "
        "read-only observer in the actual simulator argv. Run once with:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = _replace_identity(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    allowlist = manifest.get("return_allowlist")
    if not isinstance(allowlist, list) or len(allowlist) != 60:
        raise PackageBuildError("base allowlist differs")
    allowlist.extend(_progress_allowlist())
    manifest.update(
        {
            "schema": "gap-node0071-progress-server-package-v4",
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "read-only progress localization for the first sum_s1 "
                "Start_Comp interval; no functional fix and no E3/E4/E5"
            ),
            "functional_fix": False,
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "source_v3_return_sha256": RETURN_SHA256,
            "progress_localization": _progress_contract(),
            "source_numeric_payload_reused_without_rebuild": True,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
        }
    )
    provenance = manifest.get("generation_provenance")
    if not isinstance(provenance, dict):
        raise PackageBuildError("generation provenance differs")
    provenance.update(
        {
            "tool": "tools/build_gap_node0071_v4_hangloc_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "bound_return_sha256": RETURN_SHA256,
            "numeric_payload_rebuilt": False,
            "diagnostic_only": True,
        }
    )
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    checked = _preflight(package)
    frozen_after = _numeric_workload_records(package)
    if frozen_before != frozen_after:
        raise PackageBuildError("frozen numeric workload drifted")
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    required_runner_terms = (
        "+RETURN_OBSERVER",
        f"+RETURN_OBS_HEARTBEAT_CYCLES={HEARTBEAT_CYCLES}",
        f"+RETURN_OBS_STALL_CYCLES={STALL_WINDOW_CYCLES}",
        "progress_samples.log",
        "actual_simulator_argv.txt",
        'cd "$server_root"',
    )
    if not all(term in runner for term in required_runner_terms):
        raise PackageBuildError("progress runner binding differs")
    if SOURCE_NAME in runner:
        raise PackageBuildError("stale source identity in runner")
    return package, {
        "numeric_workload_tree_equal": True,
        "numeric_workload_file_count": len(frozen_after),
        "package_preflight": checked,
        "observer_runtime_enabled": True,
        "progress_allowlist_count": PROGRESS_ALLOWLIST_COUNT,
    }


def _repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_records = file_records(package, exclude_manifest=False)
    first_sha = sha256(zip_path)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v4-repeat-"
    ) as temporary:
        repeat_package, repeat_proof = build_directory(Path(temporary))
        repeat_zip = Path(temporary) / f"{INSTALL_NAME}.zip"
        deterministic_zip(
            repeat_package, repeat_zip, archive_root=INSTALL_NAME
        )
        if (
            first_records
            != file_records(repeat_package, exclude_manifest=False)
            or first_sha != sha256(repeat_zip)
            or not repeat_proof["numeric_workload_tree_equal"]
        ):
            raise PackageBuildError("repeated build differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
    }


def _fresh_extract_preflight(zip_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v4-bootstrap-"
    ) as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            if archive.testzip() is not None:
                raise PackageBuildError("diagnostic ZIP CRC failed")
            archive.extractall(root)
        package = root / INSTALL_NAME
        before = file_records(package, exclude_manifest=False)
        checked = _preflight(package)
        after = file_records(package, exclude_manifest=False)
        if before != after:
            raise PackageBuildError("fresh preflight mutated package")
    return {
        "tree_unchanged": True,
        "preflight": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package_path = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation_path = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation_path):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        package, proof = build_directory(output_root)
        repeated = _repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        fresh = _fresh_extract_preflight(zip_path)
        validation = {
            "schema": "gap-node0071-progress-package-validation-v4",
            "status": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "zip_size_bytes": zip_path.stat().st_size,
            "sidecar": str(sidecar),
            "bound_source_zip": str(SOURCE_ZIP),
            "bound_source_zip_sha256": SOURCE_SHA256,
            "bound_return_sha256": RETURN_SHA256,
            "numeric_workload_tree_equal":
                proof["numeric_workload_tree_equal"],
            "numeric_workload_file_count":
                proof["numeric_workload_file_count"],
            "package_preflight": proof["package_preflight"],
            "observer_runtime_enabled": True,
            "progress_allowlist_count": PROGRESS_ALLOWLIST_COUNT,
            "wall_clock_recovered": True,
            "sim_time_recovered": True,
            "stage_start_comp_recovered": True,
            "accepted_completion_recovered": True,
            "last_terminal_recovered": True,
            "stall_window_declared": STALL_WINDOW_CYCLES,
            "functional_fix": False,
            "functional_rtl_modified": False,
            "preloaded_runtime_readback_target_count": 0,
            "result_gate_fail_closed": True,
            "return_allowlist_only": True,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "server_action": False,
            "repeated_build": repeated,
            "fresh_extract_preflight": fresh,
        }
        write_json(validation_path, validation)
    except Exception as error:
        print(f"GAP v4 diagnostic build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
