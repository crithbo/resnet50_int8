from __future__ import annotations

import argparse
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

from tools import (  # noqa: E402
    conv_native_four_lane_e1fb0f7_c0_diag_runtime as runtime,
)
from tools import (  # noqa: E402
    node0004_assumed_hardware_server_runtime_v2 as numeric_base,
)


INSTALL_NAME = runtime.INSTALL_NAME
SOURCE_INSTALL_NAME = "r5_n4_df23e4d_p4"
OUTPUT_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
SOURCE_P4_ZIP = OUTPUT_ROOT / f"{SOURCE_INSTALL_NAME}.zip"
SOURCE_P4_SHA256 = (
    "c8d42f979b07468e869d077755f987c09c04d017cd1bc6ab50a71a8ee1d0204e"
)
SOURCE_V1_SHA256 = (
    "5cbf05cac96f887c6753d378c7f3f44daf04f60caa6016f1f41eab274cebd62f"
)
RETURN_ANALYSIS = (
    ROOT / "outputs/conv_native_four_lane_df23e4d_v1_return_analysis/report.json"
)
RETURN_ANALYSIS_SHA256 = (
    "8857cd23f809f59c290eaa0a5216b9213ae3a37bc81d6472a6338c5a984c55dd"
)
CURRENT_SYNC = (
    ROOT / "artifacts/rtl_sync/trassic_master_e1fb0f7_20260804/report.json"
)
CURRENT_SYNC_SHA256 = (
    "c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c"
)
OBSERVER_SOURCE = (
    ROOT
    / "tests/rtl_audit"
    / "conv_native_four_lane_e1fb0f7_c0_diag_observer.svh"
)
RUNTIME_SOURCE = (
    ROOT / "tools/conv_native_four_lane_e1fb0f7_c0_diag_runtime.py"
)
NUMERIC_BASE_SOURCE = (
    ROOT / "tools/node0004_assumed_hardware_server_runtime_v2.py"
)
OBSERVER_GUARD_SOURCE = (
    ROOT / "tools/conv_native_four_lane_package_observer_guard.py"
)
SERVER_ROOT_BUDGET_CHARS = 96
ABSOLUTE_PATH_LIMIT_CHARS = 240
RULE_RECEIPTS = {
    ".agents/agent.md": (
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
    ),
    ".agents/rules/生成前必读索引.md": (
        "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2"
    ),
    ".agents/rules/服务器测试包生成规则.md": (
        "5f1369c4af431baaf74044a004a3383860a9d279561712616fb19e745465c7f9"
    ),
    ".agents/rules/算子配置规则.md": (
        "8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497"
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
        "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba"
    ),
}
RETURN_ALLOWLIST = [
    {
        "source_root": source_root,
        "source_path": source_path,
        "target_path": target_path,
        "required": required,
        "max_bytes": max_bytes,
        "missing_semantics": missing_semantics,
    }
    for (
        source_root,
        source_path,
        target_path,
        required,
        max_bytes,
        missing_semantics,
    ) in (
        (
            "evidence",
            "package_preflight.json",
            "evidence/package_preflight.json",
            True,
            2 * 1024 * 1024,
            "package preflight did not complete",
        ),
        (
            "evidence",
            "install_preflight.json",
            "evidence/install_preflight.json",
            True,
            2 * 1024 * 1024,
            "install preflight did not complete",
        ),
        (
            "evidence",
            "observer_precompile.json",
            "evidence/observer_precompile.json",
            True,
            2 * 1024 * 1024,
            "package observer guard did not complete",
        ),
        (
            "evidence",
            "compile_argv.txt",
            "evidence/compile_argv.txt",
            False,
            2 * 1024 * 1024,
            "compile was not reached",
        ),
        (
            "evidence",
            "compile_exit_status.txt",
            "evidence/compile_exit_status.txt",
            True,
            2 * 1024 * 1024,
            "finalizer did not record compile status",
        ),
        (
            "evidence",
            "production_rtl_identity.json",
            "evidence/production_rtl_identity.json",
            False,
            2 * 1024 * 1024,
            "actual production compile identity unavailable",
        ),
        (
            "evidence",
            "run_exit_status.txt",
            "evidence/run_exit_status.txt",
            True,
            2 * 1024 * 1024,
            "finalizer did not record run status",
        ),
        (
            "evidence",
            "signal_status.txt",
            "evidence/signal_status.txt",
            True,
            2 * 1024 * 1024,
            "finalizer did not record signal status",
        ),
        (
            "evidence",
            "SERVER_RESULT_GATE.json",
            "evidence/SERVER_RESULT_GATE.json",
            True,
            2 * 1024 * 1024,
            "result gate did not complete",
        ),
        (
            "evidence",
            "feature_binding/c0.json",
            "evidence/feature_binding/c0.json",
            False,
            2 * 1024 * 1024,
            "simulation did not produce a feature binding receipt",
        ),
        (
            "evidence",
            "natural_terminal/c0.json",
            "evidence/natural_terminal/c0.json",
            False,
            2 * 1024 * 1024,
            "c0 did not reach natural terminal qualification",
        ),
        (
            "run",
            "c0/host_progress.log",
            "runs/c0/host_progress.log",
            False,
            2 * 1024 * 1024,
            "c0 host watchdog did not start",
        ),
        (
            "run",
            "c0/return_observer.log",
            "runs/c0/return_observer.log",
            False,
            8 * 1024 * 1024,
            "c0 observer was not enabled or simulation did not start",
        ),
        (
            "run",
            "c0/sim.log",
            "runs/c0/sim.log",
            False,
            2 * 1024 * 1024,
            "c0 simulation did not start",
        ),
        (
            "run",
            "c0/simulator_argv.txt",
            "runs/c0/simulator_argv.txt",
            False,
            2 * 1024 * 1024,
            "c0 simulator was not invoked",
        ),
        (
            "run",
            "compile/sim_results/compile.log",
            "runs/compile/compile.log",
            False,
            4 * 1024 * 1024,
            "production compiler did not emit its secondary log",
        ),
        (
            "run",
            "compile/sim_results/compile_driver.log",
            "runs/compile/compile_driver.log",
            False,
            4 * 1024 * 1024,
            "production compile was not reached",
        ),
        (
            "package",
            "package_manifest.json",
            "source_package/package_manifest.json",
            True,
            2 * 1024 * 1024,
            "source package manifest unavailable",
        ),
    )
]


class PackageBuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    return numeric_base.sha256(path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PackageBuildError(f"JSON root must be object: {path}")
    return value


def check_inputs() -> None:
    expected = {
        SOURCE_P4_ZIP: SOURCE_P4_SHA256,
        RETURN_ANALYSIS: RETURN_ANALYSIS_SHA256,
        CURRENT_SYNC: CURRENT_SYNC_SHA256,
    }
    expected.update(
        {
            ROOT / relative: digest
            for relative, digest in RULE_RECEIPTS.items()
        }
    )
    errors = [
        f"{path}: identity differs"
        for path, digest in expected.items()
        if not path.is_file() or sha256(path) != digest
    ]
    if errors:
        raise PackageBuildError("; ".join(errors))
    analysis = load_json(RETURN_ANALYSIS)
    if (
        analysis.get("status")
        != "HISTORICAL_V1_DYNAMIC_FAILURE_CONSUMABLE"
        or analysis.get("valid") is not True
        or analysis.get("successor_adjudication", {}).get(
            "fresh_successor_required"
        )
        is not True
    ):
        raise PackageBuildError("historical v1 return analysis is not closed")


def safe_extract_source(destination: Path) -> Path:
    roots: set[str] = set()
    seen: set[str] = set()
    with zipfile.ZipFile(SOURCE_P4_ZIP) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise PackageBuildError(f"source p4 CRC failed: {bad}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
                or stat.S_ISLNK(mode)
            ):
                raise PackageBuildError(
                    f"unsafe source p4 member: {info.filename}"
                )
            seen.add(info.filename)
            if not pure.parts:
                continue
            roots.add(pure.parts[0])
            if info.is_dir():
                continue
            if pure.parts[0] != SOURCE_INSTALL_NAME:
                raise PackageBuildError("source p4 root differs")
            relative = PurePosixPath(*pure.parts[1:])
            target = (
                destination / SOURCE_INSTALL_NAME / Path(*relative.parts)
            ).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise PackageBuildError("source p4 member escapes destination")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    if roots != {SOURCE_INSTALL_NAME}:
        raise PackageBuildError(f"source p4 roots differ: {sorted(roots)}")
    package = destination / SOURCE_INSTALL_NAME
    manifest = load_json(package / "package_manifest.json")
    observed = numeric_base.package_records(package)
    if observed != manifest.get("files"):
        raise PackageBuildError("source p4 exact-set differs")
    target = destination / INSTALL_NAME
    package.rename(target)
    return target


def _remove_tree_inside(package: Path, target: Path) -> None:
    resolved_package = package.resolve()
    resolved_target = target.resolve()
    if not resolved_target.is_relative_to(resolved_package):
        raise PackageBuildError(f"prune target escapes package: {target}")
    if resolved_target.is_dir():
        shutil.rmtree(resolved_target)


def _normalize_json_identity(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if SOURCE_INSTALL_NAME not in text:
        return
    path.write_text(
        text.replace(SOURCE_INSTALL_NAME, INSTALL_NAME),
        encoding="utf-8",
        newline="\n",
    )


def run_script() -> str:
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
install_name="{INSTALL_NAME}"
cfg_root="$server_root/install/cfg_pkg/$install_name"
run_root="$server_root/run_$install_name"
evidence_root="$server_root/evidence_$install_name"
return_dir="$server_root/${{install_name}}_return"
return_zip="${{return_dir}}.zip"
return_sha="${{return_zip}}.sha256"
for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || exit 3; done
for fresh in "$cfg_root" "$run_root" "$evidence_root" "$return_dir" "$return_zip" "$return_sha"; do
  [ ! -e "$fresh" ] || {{ echo "Fresh namespace required: $fresh" >&2; exit 4; }}
done
python3 "$runtime" path-budget --package-root "$package_root" \
  --server-root "$server_root" >/dev/null || exit 5
package_preflight_json="$(python3 "$runtime" preflight \
  --package-root "$package_root")" || exit 5
mkdir -p "$cfg_root" "$run_root/compile/sim_results" \
  "$evidence_root/natural_terminal" "$evidence_root/feature_binding"
printf '%s\\n' "$package_preflight_json" \
  > "$evidence_root/package_preflight.json"
cp -a "$package_root/workload/runtime/." "$cfg_root/"
python3 "$runtime" verify-install --package-root "$package_root" \
  --cfg-root "$cfg_root" > "$evidence_root/install_preflight.json" || exit 6
python3 "$observer_guard" --package-root "$package_root" \
  > "$evidence_root/observer_precompile.json" || exit 7
compile_status=125
run_status=125
feature_status=125
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
    --evidence-root "$evidence_root" --run-root "$run_root"
  analysis=$?
  python3 "$runtime" collect --server-root "$server_root" \
    --evidence-root "$evidence_root" --run-root "$run_root" \
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
mkdir -p "$run_root/c0"
observer_log="$run_root/c0/return_observer.log"
printf '%s\\n' \
  "$simv -l $run_root/c0/sim.log +vcs+lic+wait +SCA_CFG=$cfg_root/runs/c0/sca_cfg.json +SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json +RETURN_OBSERVER +N4D_C0_BOUNDARY_DIAG +RETURN_OBS_SLICE=0 +RETURN_OBS_STALL_CYCLES=1048576 +RETURN_OBS_HEARTBEAT_CYCLES=262144 +RETURN_OBS_FILE=$observer_log" \
  > "$run_root/c0/simulator_argv.txt"
timeout --foreground --signal=TERM --kill-after=30s 1h "$simv" \
  -l "$run_root/c0/sim.log" +vcs+lic+wait \
  "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" \
  "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" \
  +RETURN_OBSERVER +N4D_C0_BOUNDARY_DIAG +RETURN_OBS_SLICE=0 \
  +RETURN_OBS_STALL_CYCLES=1048576 \
  +RETURN_OBS_HEARTBEAT_CYCLES=262144 \
  "+RETURN_OBS_FILE=$observer_log" &
sim_pid=$!
(
  while kill -0 "$sim_pid" 2>/dev/null; do
    host_epoch="$(date +%s)"
    observer_bytes=0
    [ ! -f "$observer_log" ] || observer_bytes="$(wc -c < "$observer_log")"
    printf 'host_epoch=%s run=c0 observer_bytes=%s\\n' \
      "$host_epoch" "$observer_bytes"
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
python3 "$runtime" feature-binding \
  --sim-log "$run_root/c0/sim.log" \
  --observer-log "$observer_log" \
  --output "$evidence_root/feature_binding/c0.json"
feature_status=$?
if [ "$run_status" -eq 0 ] && [ "$feature_status" -ne 0 ]; then
  exit 10
fi
if [ "$run_status" -eq 0 ]; then
  python3 "$runtime" qualify-run \
    --sim-log "$run_root/c0/sim.log" \
    --observer-log "$observer_log" \
    --output "$evidence_root/natural_terminal/c0.json" || exit 9
fi
exit "$run_status"
"""


def _path_budget(package: Path) -> dict[str, Any]:
    projections = [
        (
            f"install/cfg_pkg/{INSTALL_NAME}/"
            f"{path.relative_to(package / 'workload/runtime').as_posix()}"
        )
        for path in (package / "workload/runtime").rglob("*")
        if path.is_file()
    ]
    projections.extend(
        [
            f"run_{INSTALL_NAME}/compile/sim_results/compile_driver.log",
            f"run_{INSTALL_NAME}/c0/return_observer.log",
            f"evidence_{INSTALL_NAME}/production_rtl_identity.json",
            f"{INSTALL_NAME}_return/runs/c0/return_observer.log",
        ]
    )
    longest = max(projections, key=len)
    projected = SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
    if projected > ABSOLUTE_PATH_LIMIT_CHARS:
        raise PackageBuildError("projected server path exceeds budget")
    inner = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file() and path.name != "package_manifest.json"
    ]
    return {
        "rule_id": "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
        "declared_target_root_max_chars": SERVER_ROOT_BUDGET_CHARS,
        "max_projected_absolute_path_limit_chars": ABSOLUTE_PATH_LIMIT_CHARS,
        "max_projected_absolute_path_chars": projected,
        "max_projected_relative_path_chars": len(longest),
        "longest_projected_relative_path": longest,
        "max_zip_member_chars": max(
            len(f"{INSTALL_NAME}/{relative}") for relative in inner
        ),
        "max_inner_suffix_chars": max(map(len, inner)),
        "max_inner_depth": max(len(PurePosixPath(item).parts) for item in inner),
        "max_inner_component_chars": max(
            len(component)
            for item in inner
            for component in PurePosixPath(item).parts
        ),
        "outer_identity_repeated_inside": False,
        "exceptions": [
            {
                "scope": "workload/runtime/runs/c0/install/**",
                "reason": (
                    "frozen p4 c0 causal workload and simulator SCA ABI are "
                    "retained byte-for-byte; projected absolute maximum is "
                    "still below the 240-character hard limit"
                ),
                "semantic_change_if_renamed": (
                    "would alter the exact causal-slice SCA consumer paths"
                ),
            }
        ],
        "actual_server_guard": (
            "runtime recomputes normalized user-root path budget before "
            "creating install/run/evidence namespaces"
        ),
    }


def materialize(destination: Path) -> Path:
    package = safe_extract_source(destination)
    runs = package / "workload/runtime/runs"
    dropped_runs = sorted(path.name for path in runs.iterdir() if path.name != "c0")
    for path in list(runs.iterdir()):
        if path.name != "c0":
            _remove_tree_inside(package, path)
    _remove_tree_inside(package, package / "validation")
    tools_root = package / "package_tools"
    for name in (
        "node0004_assumed_hardware_server_runtime_v5_base.py",
        "node0004_native_four_lane_runtime_v1_base.py",
    ):
        target = tools_root / name
        if target.is_file():
            target.unlink()
    shutil.copy2(
        RUNTIME_SOURCE,
        tools_root / "node0004_assumed_hardware_server_runtime.py",
    )
    shutil.copy2(
        NUMERIC_BASE_SOURCE,
        tools_root / "node0004_assumed_hardware_server_runtime_v2_base.py",
    )
    shutil.copy2(
        OBSERVER_GUARD_SOURCE,
        tools_root / "node0004_package_observer_guard.py",
    )
    shutil.copy2(
        OBSERVER_SOURCE,
        package / "tb_probe/native_return_observer.svh",
    )
    for json_path in package.rglob("*.json"):
        if json_path.name != "package_manifest.json":
            _normalize_json_identity(json_path)
    (package / "PREPARE_AND_RUN.sh").write_text(
        run_script(), encoding="utf-8", newline="\n"
    )
    (package / "README.md").write_text(
        "# Conv node0004 native-four-lane c0 boundary diagnostic p5\n\n"
        "This fresh diagnostic keeps the p4 c0 workload byte-for-byte except "
        "for the required install identity in the two SCA JSON consumers. It "
        "drops c1/c2, all 24 tail runs and all formal D golden payloads because "
        "the historical v1 first divergence occurs inside c0 before any D.\n\n"
        "Run exactly once from the extracted package root:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/server_root\n"
        "```\n\n"
        "The run is bounded to one hour and returns partial evidence on "
        "timeout. It is DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX, carries no "
        "functional RTL, claims no E3/E4/E5 and does not inspect server "
        "source before the actual VCS compile.\n",
        encoding="utf-8",
        newline="\n",
    )
    write_json(
        package / "TEST_PACKAGE_MANIFEST.json",
        {
            "schema": "conv-native-four-lane-e1fb0f7-c0diag-pointer-v1",
            "status": "PACKAGE_READY_NOT_RUN",
            "install_name": INSTALL_NAME,
            "canonical_manifest": "package_manifest.json",
            "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "formal_readback_count": 0,
        },
    )
    write_json(
        package / "provenance/current_local_rtl_binding.json",
        {
            "schema": (
                "conv-native-four-lane-e1fb0f7-c0diag-rtl-binding-v1"
            ),
            "source_baseline_commit": runtime.EXPECTED_COMMIT,
            "source_sync_report": str(CURRENT_SYNC.relative_to(ROOT)).replace(
                "\\", "/"
            ),
            "source_sync_report_sha256": CURRENT_SYNC_SHA256,
            "expected_actual_compile_leaves": runtime.EXPECTED_LEAVES,
            "expected_byte_identity": (
                "immutable Git blob/raw Linux checkout bytes"
            ),
            "precompile_server_source_preflight": False,
            "functional_rtl_in_package": False,
        },
    )
    manifest = load_json(package / "package_manifest.json")
    manifest.update(
        {
            "schema": (
                "resnet50-conv-native-four-lane-e1fb0f7-c0diag-"
                "server-package-v1"
            ),
            "status": "PACKAGE_READY_NOT_RUN",
            "package_release": "PACKAGE_READY_NOT_RUN",
            "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "install_name": INSTALL_NAME,
            "run_namespace": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return.zip",
            "conv_run_ids": ["c0"],
            "tail_run_ids": [],
            "tail_materialization": [],
            "readback_checks": [],
            "formal_readback_count": 0,
            "natural_terminal_required_count": 1,
            "expected_production_rtl_identity": {
                "commit": runtime.EXPECTED_COMMIT,
                "leaves": runtime.EXPECTED_LEAVES,
                "expected_byte_identity": (
                    "immutable Git blob/raw Linux checkout bytes"
                ),
                "receipt_timing": "after actual production VCS compile",
                "precompile_server_source_preflight": False,
            },
            "server_source_identity_bound": True,
            "server_source_preflight_performed": False,
            "functional_rtl_modified": False,
            "functional_rtl_file_count": 0,
            "server_rtl_entries": 0,
            "host_precompute_internal_tensor": False,
            "source_return_analysis": {
                "path": str(RETURN_ANALYSIS.relative_to(ROOT)).replace(
                    "\\", "/"
                ),
                "sha256": RETURN_ANALYSIS_SHA256,
                "historical_return_sha256": (
                    "8166c8dd85aece80714d051c7d88591f181e4bd35c5c74dc91aa90554867fd44"
                ),
                "classification": (
                    "HISTORICAL_V1_DYNAMIC_FAILURE_CONSUMABLE"
                ),
            },
            "delivery_and_workload_provenance": {
                "source_p4_zip_sha256": SOURCE_P4_SHA256,
                "source_v1_zip_sha256": SOURCE_V1_SHA256,
                "p4_content_neutral_workload_file_count": 503,
                "c0_source": (
                    "source p4 workload/runtime/runs/c0 exact bytes, with "
                    "install identity normalized only in sca_cfg.json and "
                    "sca_cfg_D.json"
                ),
            },
            "diagnostic_execution_reduction": {
                "classification": (
                    "CAUSAL_PREFIX_C0_ONLY_DIAGNOSTIC_REDUCTION"
                ),
                "kept_run_ids": ["c0"],
                "dropped_run_ids": dropped_runs,
                "source_run_count": 27,
                "diagnostic_run_count": 1,
                "run_count_reduction": "27x",
                "kept_stage_prefix": (
                    "full c0 Conv wave0 stage, all 28 slices, exact input/"
                    "config/bitstream/execplan/SCA timing and backpressure"
                ),
                "dropped_after_first_divergence": [
                    "c1",
                    "c2",
                    "24 requant tail runs",
                    "320 formal D golden/readback endpoints",
                ],
                "boundary_input_source": (
                    "unchanged graph-external/frozen c0 package inputs; no "
                    "host-precomputed internal tensor"
                ),
                "expected_wall_clock": (
                    "one-hour bound versus historical c0 twelve-hour timeout"
                ),
                "formal_claim_boundary": (
                    "diagnostic only; no formal D, E3, E4 or E5 claim"
                ),
                "negative_control": (
                    "removing any retained c0 member fails package exact-set "
                    "preflight before compile"
                ),
            },
            "candidate_decision_matrix": [
                {
                    "candidate": "memory response starvation",
                    "distinguishing_result": (
                        "per-MSE req exceeds rdata before RD inbuffer"
                    ),
                },
                {
                    "candidate": "RD_Data_Channel blockage",
                    "distinguishing_result": (
                        "rdata/metadata enter but inbuffer, prepared-data or "
                        "buffer handoff stops with queue/count level witness"
                    ),
                },
                {
                    "candidate": "Buffer_AG or Array_Request_Manager pressure",
                    "distinguishing_result": (
                        "queue full/hold/backpressure with unmatched qualified "
                        "write/read or request/response counts"
                    ),
                },
                {
                    "candidate": "SA/buffer consumer starvation",
                    "distinguishing_result": (
                        "read-MSE buffer handoff progresses but SA input/output "
                        "or buffer4/5 accepted events stop"
                    ),
                },
                {
                    "candidate": "MSE4/finish propagation",
                    "distinguishing_result": (
                        "SA output exists but MSE4 index/request/write-data or "
                        "slice finish remains absent"
                    ),
                },
                {
                    "candidate": "e1fb0f7 changed LSU path resolves df23 stall",
                    "distinguishing_result": (
                        "actual eight-leaf e1fb0f7 identity matches and "
                        "qualified progress crosses the historical 2,097,152 "
                        "cycle plateau"
                    ),
                },
            ],
            "observer_binding": {
                "source": "tb_probe/native_return_observer.svh",
                "source_sha256": sha256(OBSERVER_SOURCE),
                "compile_include": (
                    "VCS_EXTRA_OPTS=+define+NATIVE_RETURN_OBSERVER_ENABLE "
                    "+incdir+<package_root>/tb_probe"
                ),
                "runtime_enable": "+RETURN_OBSERVER",
                "feature_runtime_enable": "+N4D_C0_BOUNDARY_DIAG",
                "time0_marker": (
                    "N4D_FEATURE_ENABLE_V2 "
                    "feature=NATIVE4_C0_BOUNDARY enabled=1 "
                    "heartbeat_cycles=262144 stall_cycles=1048576 "
                    "slice=0"
                ),
                "canonical_record": "N4D_CANONICAL_V1",
                "progress_record": "N4D_PROGRESS_V1",
                "summary_record": "N4D_SUMMARY_V1",
                "does_not_force_terminal": True,
                "qualified_domains": ["clk_db", "clk_sg"],
            },
            "diagnostic_features": [
                {
                    "feature": "NATIVE4_C0_BOUNDARY",
                    "runtime_enable": "+N4D_C0_BOUNDARY_DIAG",
                    "limit_parameters": {
                        "heartbeat_cycles": 262144,
                        "stall_cycles": 1048576,
                        "slice": 0,
                    },
                    "time0_marker": (
                        "N4D_FEATURE_ENABLE_V2 "
                        "feature=NATIVE4_C0_BOUNDARY enabled=1 "
                        "heartbeat_cycles=262144 "
                        "stall_cycles=1048576 slice=0"
                    ),
                    "binding_receipt": (
                        "evidence/feature_binding/c0.json"
                    ),
                    "record_schema": "N4D_PROGRESS_V1",
                    "canonical_schema": "N4D_CANONICAL_V1",
                    "return_target": (
                        "evidence/feature_binding/c0.json"
                    ),
                }
            ],
            "progress_diagnostics": {
                "historical_first_plateau_cycle": 2_097_152,
                "heartbeat_cycles": 262_144,
                "stall_window_cycles": 1_048_576,
                "host_heartbeat_seconds": 30,
                "run_timeout_seconds": 3600,
                "qualified_boundaries": [
                    "per-MSE/per-channel request/read-data/write-data",
                    "all read-MSE metadata/inbuffer/prepared-data/buffer",
                    "all MSE Buffer_AG queue write/read and full/empty",
                    "all six Array_Request_Manager request/response/hold/finish",
                    "both Neighbor_Out_AG request/in/out/full/empty/finish",
                    "SA input/output and buffer4/5 write/read",
                    "MSE4 index/request/write-data and slice finish",
                ],
                "raw_level_samples_excluded_from_progress": True,
            },
            "return_budget": {
                "zip_max_bytes": 16 * 1024 * 1024,
                "uncompressed_max_bytes": 32 * 1024 * 1024,
                "single_text_max_bytes": 8 * 1024 * 1024,
            },
            "return_allowlist": RETURN_ALLOWLIST,
            "rule_receipts": RULE_RECEIPTS,
            "rule_receipts_current_match": True,
            "server_action": False,
        }
    )
    provenance = manifest.get("workload_provenance", {})
    provenance.update(
        {
            "package_builder": (
                "tools/"
                "build_conv_native_four_lane_e1fb0f7_c0_diag_package.py"
            ),
            "package_builder_sha256": sha256(Path(__file__)),
            "runtime_source_sha256": sha256(RUNTIME_SOURCE),
            "observer_source_sha256": sha256(OBSERVER_SOURCE),
            "command": (
                ".venv/Scripts/python.exe -B tools/"
                "build_conv_native_four_lane_e1fb0f7_c0_diag_package.py"
            ),
        }
    )
    manifest["workload_provenance"] = provenance
    manifest["path_length_budget"] = _path_budget(package)
    manifest["files"] = numeric_base.package_records(package)
    write_json(package / "package_manifest.json", manifest)
    runtime.preflight(package)
    old_identity_hits: list[str] = []
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix not in {
            ".json",
            ".md",
            ".py",
            ".sh",
            ".txt",
        }:
            continue
        if SOURCE_INSTALL_NAME in path.read_text(
            encoding="utf-8", errors="ignore"
        ):
            old_identity_hits.append(path.relative_to(package).as_posix())
    if old_identity_hits:
        raise PackageBuildError(
            f"stale p4 identity remains: {old_identity_hits[:3]}"
        )
    return package


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(
            item for item in package.rglob("*") if item.is_file()
        ):
            relative = f"{package.name}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, (2026, 8, 5, 0, 0, 0))
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def build_reproducible(output_root: Path) -> dict[str, Any]:
    check_inputs()
    package_path = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation):
        if path.exists():
            raise PackageBuildError(f"refusing to overwrite: {path}")
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="n4-p5-a-") as first_name, (
        tempfile.TemporaryDirectory(prefix="n4-p5-b-")
    ) as second_name:
        first_root = Path(first_name)
        second_root = Path(second_name)
        first_package = materialize(first_root)
        second_package = materialize(second_root)
        first_zip = first_root / f"{INSTALL_NAME}.zip"
        second_zip = second_root / f"{INSTALL_NAME}.zip"
        deterministic_zip(first_package, first_zip)
        deterministic_zip(second_package, second_zip)
        first_sha = sha256(first_zip)
        second_sha = sha256(second_zip)
        first_records = numeric_base.package_records(
            first_package, exclude_manifest=False
        )
        second_records = numeric_base.package_records(
            second_package, exclude_manifest=False
        )
        if first_sha != second_sha or first_records != second_records:
            raise PackageBuildError("deterministic dual build differs")
        shutil.copytree(first_package, package_path)
        shutil.copy2(first_zip, zip_path)
    digest = sha256(zip_path)
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    receipt = {
        "schema": "conv-native-four-lane-e1fb0f7-c0diag-build-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "install_name": INSTALL_NAME,
        "package": str(package_path),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "sidecar_sha256": sha256(sidecar),
        "package_file_count": len(
            numeric_base.package_records(
                package_path, exclude_manifest=False
            )
        ),
        "deterministic_dual_build": True,
        "source_p4_sha256": SOURCE_P4_SHA256,
        "source_v1_sha256": SOURCE_V1_SHA256,
        "run_ids": ["c0"],
        "formal_D_count": 0,
        "functional_rtl_entries": [],
        "server_action": False,
    }
    write_json(validation, receipt)
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
