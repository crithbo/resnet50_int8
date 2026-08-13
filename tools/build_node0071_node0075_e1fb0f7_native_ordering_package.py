#!/usr/bin/env python3
"""Build a deterministic diagnostic server package for node0071 -> node0075."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "r5_n71_n75_e1f_native_v3"
PACKAGE_DIR = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / PACKAGE_NAME
)
ZIP_PATH = PACKAGE_DIR.with_suffix(".zip")
SIDECAR = Path(str(ZIP_PATH) + ".sha256")
BUILD_ID = "r5-node0071-node0075-e1fb0f7-native-ordering-package-v3"
REPORT_DIR = ROOT / "artifacts/operator_config_validation" / BUILD_ID

INTEGRATION = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-native-ordering-integration-v1"
)
INTEGRATION_WORKLOAD = INTEGRATION / "workload"
INTEGRATION_REPORT = INTEGRATION / "report.json"
INTEGRATION_VALIDATION = INTEGRATION / "validation.json"
N75_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0075-df23e4d-eight-pass-materializer-v1/materializer_report.json"
)
RUNTIME_SOURCE = (
    ROOT / "tools/node0071_node0075_native_ordering_server_runtime.py"
)
OBSERVER_SOURCE = (
    ROOT
    / "tests/rtl/"
    "node0071_node0075_e1fb0f7_native_ordering_observer.svh"
)
RULE_INDEX = ROOT / ".agents/rules/生成前必读索引.md"
OPERATOR_RULES = ROOT / ".agents/rules/算子配置规则.md"
HARDWARE_RULES = ROOT / ".agents/rules/NDP硬件字段语义.md"
SERVER_RULES = ROOT / ".agents/rules/服务器测试包生成规则.md"
INT8_RULES = ROOT / ".agents/rules/INT8_SA点积专项规则.md"
UINT8_RULES = ROOT / ".agents/rules/精确UINT8量化尾专项规则.md"
PLAN = ROOT / ".agents/plan.md"
AUTHORIZATION = (
    ROOT
    / ".agents/task_records/"
    "20260805_node0075_no_explicit_barrier_native_ordering_authorization.md"
)
PYTHON = Path(sys.executable).resolve()

RUNNER = """#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in /*) ;; *) echo "NDP_copy path must be absolute" >&2; exit 2;; esac

package_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
server_root="$(cd "$1" && pwd -P)"
install_name="r5_n71_n75_e1f_native_v3"
cfg_root="$server_root/install/cfg_pkg/$install_name"
run_root="$server_root/run_$install_name"
evidence_root="$server_root/evidence_$install_name"
return_root="$server_root/${install_name}_return"
runtime="$package_root/pkg/runtime.py"
observer_log="$run_root/return_observer.log"
progress_log="$evidence_root/host_progress.log"

for tool in python3 timeout make date tail tr grep sleep wc cp mkdir; do
  command -v "$tool" >/dev/null 2>&1 || exit 3
done
for target in "$cfg_root" "$run_root" "$evidence_root" "$return_root" \
  "${return_root}.zip" "${return_root}.zip.sha256"; do
  [ ! -e "$target" ] || { echo "Fresh target required: $target" >&2; exit 4; }
done

mkdir "$evidence_root"
python3 "$runtime" preflight --package-root "$package_root" \
  >"$evidence_root/package_preflight.json" || exit 5
path_budget_status="$(python3 - "$package_root/TEST_PACKAGE_MANIFEST.json" "$package_root" <<'PY'
import json, pathlib, sys
m=json.load(open(sys.argv[1], encoding='utf-8'))
b=m['path_length_budget']; root=pathlib.Path(sys.argv[2]).resolve()
members=[p for p in root.rglob('*') if p.is_file()]
suffix=max((len(p.relative_to(root).as_posix()) for p in members), default=0)
projected=len(str(root))+1+suffix
errors=[]
if projected > b['max_projected_absolute_path_chars']: errors.append('absolute_path_budget')
if suffix > b['max_inner_suffix_chars']: errors.append('inner_suffix_budget')
print(json.dumps({'valid':not errors,'errors':errors,'actual_root_chars':len(str(root)),
                  'actual_max_suffix_chars':suffix,'actual_projected_chars':projected},
                 sort_keys=True))
raise SystemExit(0 if not errors else 42)
PY
)" || { printf '%s\n' "$path_budget_status" >"$evidence_root/path_budget.json"; exit 42; }
printf '%s\n' "$path_budget_status" >"$evidence_root/path_budget.json"

mkdir -p "$server_root/install/cfg_pkg"
cp -a "$package_root/workload" "$cfg_root"
mkdir "$run_root"
python3 "$runtime" verify-install --package-root "$package_root" \
  --cfg-root "$cfg_root" >"$evidence_root/install_preflight.json" || exit 6
python3 "$runtime" prepare-run --package-root "$package_root" \
  --server-root "$server_root" --run-root "$run_root" \
  >"$evidence_root/runtime_d_absent.json" || exit 7

compile_extra_opts="+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/obs"
printf 'make -C %q -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=%q VCS_EXTRA_OPTS=%q\n' \
  "$server_root" "$run_root" "$compile_extra_opts" \
  >"$evidence_root/compile_argv.txt"

compile_status=125
run_status=125
runner_status=125
signal_name=NONE
sim_pid=0
sampler_pid=0
finalized=0

sample_progress() {
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
}

progress_sampler() {
  while kill -0 "$sim_pid" 2>/dev/null; do
    sample_progress
    sleep 60
  done
  sample_progress
}

finalize() {
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
  runner_status="$original"
  printf '%s\n' "$compile_status" >"$evidence_root/compile_exit_status.txt"
  printf '%s\n' "$run_status" >"$evidence_root/run_exit_status.txt"
  printf '%s\n' "$runner_status" >"$evidence_root/runner_exit_status.txt"
  printf '%s\n' "$signal_name" >"$evidence_root/signal_status.txt"
  if [ -s "$observer_log" ] && \
     grep -Fq 'N75_FEATURE_ENABLE_V2 feature=NATIVE_ORDERING enabled=1' "$observer_log"; then
    printf 'observer_enabled_and_returned=true\nfeature=NATIVE_ORDERING\na_event_limit=9000\n' \
      >"$evidence_root/observer_binding.txt"
  else
    printf 'observer_enabled_and_returned=false\nfeature=NATIVE_ORDERING\na_event_limit=UNKNOWN\n' \
      >"$evidence_root/observer_binding.txt"
  fi
  python3 "$runtime" analyze --package-root "$package_root" \
    --server-root "$server_root" --run-root "$run_root" \
    --evidence-root "$evidence_root"
  analysis_status=$?
  python3 "$runtime" collect --package-root "$package_root" \
    --server-root "$server_root" --run-root "$run_root" \
    --evidence-root "$evidence_root"
  collection_status=$?
  final="$original"
  [ "$final" -ne 0 ] || [ "$analysis_status" -eq 0 ] || final="$analysis_status"
  [ "$final" -ne 0 ] || [ "$collection_status" -eq 0 ] || final="$collection_status"
  exit "$final"
}
trap 'finalize $?' EXIT
trap 'signal_name=HUP; run_status=125; finalize 125' HUP
trap 'signal_name=INT; run_status=125; finalize 125' INT
trap 'signal_name=TERM; run_status=125; finalize 125' TERM

set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -C "$server_root" -f Makefile.tb_NDP_Top_new_phy compile \
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$run_root" \
  VCS_EXTRA_OPTS="$compile_extra_opts" >"$run_root/compile.log" 2>&1
compile_status=$?
set -e
[ "$compile_status" -eq 0 ] || exit "$compile_status"

cd "$server_root"
simv="$run_root/sim_results/simv"
sim_args=(
  -l "$run_root/sim.log"
  +vcs+lic+wait
  +sim_time=100ms
  +BITSTREAM=install/bitstream.txt
  "+SCA_CFG=install/cfg_pkg/$install_name/sca_cfg.json"
  "+SCA_CFG_D=install/cfg_pkg/$install_name/sca_cfg_D.json"
  +RETURN_OBSERVER
  +N75_NATIVE_ORDERING
  +N75_A_EVENT_LIMIT=9000
  +RETURN_OBS_STALL_CYCLES=1048576
  +RETURN_OBS_HEARTBEAT_CYCLES=262144
  "+RETURN_OBS_FILE=$observer_log"
)
printf 'timeout --foreground --signal=TERM --kill-after=30s 12h %q' "$simv" \
  >"$evidence_root/simulator_argv.txt"
printf ' %q' "${sim_args[@]}" >>"$evidence_root/simulator_argv.txt"
printf '\n' >>"$evidence_root/simulator_argv.txt"
timeout --foreground --signal=TERM --kill-after=30s 12h \
  "$simv" "${sim_args[@]}" &
sim_pid=$!
progress_sampler &
sampler_pid=$!
wait "$sim_pid"
run_status=$?
sim_pid=0
if kill -0 "$sampler_pid" 2>/dev/null; then
  kill -TERM "$sampler_pid" 2>/dev/null
  wait "$sampler_pid" 2>/dev/null
fi
sampler_pid=0
sample_progress
[ "$run_status" -eq 0 ] || exit "$run_status"
exit 0
"""


class PackageError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PackageError(f"JSON root differs: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def copy_exact(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if (
        source.stat().st_size != destination.stat().st_size
        or sha256(source) != sha256(destination)
    ):
        raise PackageError(f"copy identity differs: {source} -> {destination}")


def records(root: Path, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = exclude or set()
    result: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PackageError(f"symlink forbidden: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        result.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return result


def deterministic_zip(root: Path, destination: Path) -> None:
    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = f"{root.name}/{path.relative_to(root).as_posix()}"
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o755 if path.name == "PREPARE_AND_RUN.sh" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


def installed(relative: str) -> str:
    return f"install/cfg_pkg/{PACKAGE_NAME}/{relative}"


def runtime(relative: str) -> str:
    return f"run_{PACKAGE_NAME}/formal_d/{relative}"


def _copy_payloads(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source_sca = load_json(INTEGRATION_WORKLOAD / "sca_cfg.json")
    source_sca_d = load_json(INTEGRATION_WORKLOAD / "sca_cfg_D.json")
    workload = root / "workload"
    sca: dict[str, Any] = {
        "Exec_Base": "0x01706400",
        "Exec_Length": 518,
        "ExecutionPlan": {
            "base_addr": "0x01706400",
            "path": installed("ep.txt"),
        },
        "Repeat_Num": 32,
    }
    copy_exact(INTEGRATION_WORKLOAD / "install/execplan.txt", workload / "ep.txt")

    for slice_id in range(16):
        source = (
            INTEGRATION_WORKLOAD
            / f"input/node0071/slice{slice_id:02d}/matrix_A_128bit.txt"
        )
        relative = f"i/s{slice_id:02d}.txt"
        copy_exact(source, workload / relative)
        sca[f"n71_i{slice_id:02d}"] = {
            "base_addr": source_sca[f"node0071_input_slice{slice_id}"]["base_addr"],
            "path": installed(relative),
        }

    for stage_index in range(1, 9):
        source_key = f"node0071_stage{stage_index:02d}_config"
        source_item = source_sca[source_key]
        source = INTEGRATION_WORKLOAD / Path(source_item["path"]).name
        source = (
            INTEGRATION_WORKLOAD
            / "install/cfg_pkg/node0071"
            / Path(source_item["path"]).name
        )
        relative = f"c/71s{stage_index:02d}.bin"
        copy_exact(source, workload / relative)
        sca[f"n71_s{stage_index:02d}_cfg"] = {
            "base_addr": source_item["base_addr"],
            "path": installed(relative),
        }

    for pass_index in range(8):
        source = (
            INTEGRATION_WORKLOAD
            / f"weights/node0075/pass{pass_index:02d}/"
            "matrix_B_linearized_128bit.txt"
        )
        relative = f"b/p{pass_index:02d}.txt"
        copy_exact(source, workload / relative)
        for slice_id in range(16):
            source_key = (
                f"node0075_accum_pass{pass_index:02d}_matrixB_slice{slice_id}"
            )
            sca[f"n75_b_p{pass_index:02d}_s{slice_id:02d}"] = {
                "base_addr": source_sca[source_key]["base_addr"],
                "path": installed(relative),
            }

    for kind, short in (("accum", "a"), ("scale", "s"), ("round", "r")):
        for pass_index in range(8):
            source_key = f"node0075_{kind}_pass{pass_index:02d}_config"
            source_item = source_sca[source_key]
            source = (
                INTEGRATION_WORKLOAD
                / "install/cfg_pkg/node0075"
                / Path(source_item["path"]).name
            )
            relative = f"c/75{short}{pass_index:02d}.bin"
            copy_exact(source, workload / relative)
            sca[f"n75_{short}{pass_index:02d}_cfg"] = {
                "base_addr": source_item["base_addr"],
                "path": installed(relative),
            }

    sca_d: dict[str, Any] = {}
    for slice_id in range(16):
        source_item = source_sca_d[f"node0071_final_uint8_slice{slice_id}"]
        sca_d[f"n71_d_s{slice_id:02d}"] = {
            "base_addr": source_item["base_addr"],
            "length": 128,
            "path": runtime(f"71/u/s{slice_id:02d}.txt"),
        }
    for pass_index in range(8):
        for slice_id in range(16):
            source_item = source_sca_d[
                f"node0075_final_uint8_pass{pass_index:02d}_slice{slice_id}"
            ]
            sca_d[f"n75_d_p{pass_index:02d}_s{slice_id:02d}"] = {
                "base_addr": source_item["base_addr"],
                "length": 8,
                "path": runtime(f"75/u/p{pass_index:02d}/s{slice_id:02d}.txt"),
            }
    write_json(workload / "sca_cfg.json", sca)
    write_json(workload / "sca_cfg_D.json", sca_d)
    return sca, sca_d


def _copy_goldens(root: Path) -> list[dict[str, Any]]:
    workload = root / "workload"
    checks: list[dict[str, Any]] = []
    n71_categories = {"sum_int32": "i", "scaled_fp32": "f", "final_uint8": "u"}
    for category, short in n71_categories.items():
        for slice_id in range(16):
            source = (
                INTEGRATION_WORKLOAD
                / f"golden/node0071/{category}/slice{slice_id:02d}/"
                "matrix_D_128bit.txt"
            )
            relative = f"g/71/{short}/s{slice_id:02d}.txt"
            destination = workload / relative
            copy_exact(source, destination)
            if category == "final_uint8":
                checks.append(
                    {
                        "id": f"n71_final_s{slice_id:02d}",
                        "runtime_path": runtime(f"71/u/s{slice_id:02d}.txt"),
                        "golden_path": f"workload/{relative}",
                        "line_count_128bit": 128,
                        "size_bytes": destination.stat().st_size,
                        "sha256": sha256(destination),
                    }
                )
    n75_categories = {"accum_int32": "a", "scaled_fp32": "s", "final_uint8": "u"}
    for category, short in n75_categories.items():
        for pass_index in range(8):
            for slice_id in range(16):
                source = (
                    INTEGRATION_WORKLOAD
                    / f"golden/node0075/{category}/pass{pass_index:02d}/"
                    f"slice{slice_id:02d}/matrix_D_128bit.txt"
                )
                relative = (
                    f"g/75/{short}/p{pass_index:02d}/s{slice_id:02d}.txt"
                )
                destination = workload / relative
                copy_exact(source, destination)
                if category == "final_uint8":
                    checks.append(
                        {
                            "id": f"n75_final_p{pass_index:02d}_s{slice_id:02d}",
                            "runtime_path": runtime(
                                f"75/u/p{pass_index:02d}/s{slice_id:02d}.txt"
                            ),
                            "golden_path": f"workload/{relative}",
                            "line_count_128bit": 8,
                            "size_bytes": destination.stat().st_size,
                            "sha256": sha256(destination),
                        }
                    )
    if len(checks) != 144:
        raise PackageError("readback check count differs")
    return checks


def _readme() -> str:
    return f"""# node0071 -> node0075 native-ordering diagnostic

Status: `PACKAGE_READY_NOT_RUN`, `DIAGNOSTIC_ONLY`, `candidate_release=false`.

Run exactly:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

Expected return: `{PACKAGE_NAME}_return.zip`.

The workload uses one simulator and one execplan: graph-external node0071 input,
8 node0071 stages, a normal command transition, then node0075 8 accumulate +
8 scale + 8 exact UINT8 round stages.  No A preload, host tensor replay, dump/
reload, functional RTL change, or explicit barrier opcode is used.  Dynamic
failure is classified as instance scheduling/ordering first, not automatically
as an RTL bug.
"""


def _return_allowlist(
    readback_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    def add(
        destination: str,
        source_scope: str,
        source_path: str,
        *,
        required: bool,
        max_bytes: int,
        missing_semantics: str,
        copy_mode: str = "exact",
    ) -> None:
        records.append(
            {
                "destination": destination,
                "source_scope": source_scope,
                "source_path": source_path,
                "required": required,
                "max_bytes": max_bytes,
                "missing_semantics": missing_semantics,
                "copy_mode": copy_mode,
            }
        )

    for name in (
        "package_preflight.json",
        "install_preflight.json",
        "runtime_d_absent.json",
        "compile_exit_status.txt",
        "run_exit_status.txt",
        "runner_exit_status.txt",
        "signal_status.txt",
        "compile_argv.txt",
        "observer_binding.txt",
        "SERVER_RESULT_GATE.json",
    ):
        add(
            f"e/{name}",
            "evidence",
            name,
            required=True,
            max_bytes=16 * 1024 * 1024,
            missing_semantics="required finalizer evidence missing",
        )
    add(
        "e/simulator_argv.txt",
        "evidence",
        "simulator_argv.txt",
        required=False,
        max_bytes=1024 * 1024,
        missing_semantics="simulation was not launched",
    )
    for destination, source in (
        ("src/TEST_PACKAGE_MANIFEST.json", "TEST_PACKAGE_MANIFEST.json"),
        ("src/sca_cfg.json", "workload/sca_cfg.json"),
        ("src/sca_cfg_D.json", "workload/sca_cfg_D.json"),
    ):
        add(
            destination,
            "package",
            source,
            required=True,
            max_bytes=16 * 1024 * 1024,
            missing_semantics="source package identity evidence missing",
        )
    for destination, source, limit in (
        ("log/compile.head_tail.log", "compile.log", 2 * 1024 * 1024),
        ("log/sim.head_tail.log", "sim.log", 2 * 1024 * 1024),
        ("log/return_observer.log", "return_observer.log", 8 * 1024 * 1024),
    ):
        add(
            destination,
            "run",
            source,
            required=False,
            max_bytes=limit,
            missing_semantics="corresponding compile/simulation artifact absent",
            copy_mode="head_tail",
        )
    add(
        "log/host_progress.log",
        "evidence",
        "host_progress.log",
        required=False,
        max_bytes=1024 * 1024,
        missing_semantics="no host progress sample was produced",
        copy_mode="head_tail",
    )
    runtime_prefix = PurePosixPath(f"run_{PACKAGE_NAME}/formal_d")
    for item in readback_checks:
        runtime_path = PurePosixPath(str(item["runtime_path"]))
        destination = "d/" + runtime_path.relative_to(runtime_prefix).as_posix()
        add(
            destination,
            "server",
            runtime_path.as_posix(),
            required=False,
            max_bytes=int(item["size_bytes"]),
            missing_semantics="formal D missing; result conjunction must fail",
        )
    if len(records) != 162:
        raise PackageError("return allowlist record count differs")
    return {
        "schema": "node0071-node0075-native-ordering-return-allowlist-v1",
        "records": records,
        "generated_members": [
            "RETURN_ALLOWLIST.json",
            "RETURN_MANIFEST.json",
        ],
        "forbidden": [
            "csrc",
            "simv",
            "simv.daidir",
            "waveform",
            "nested_archive",
            "source_test_package_zip",
        ],
    }


def _build_tree(root: Path) -> dict[str, Any]:
    workload = root / "workload"
    workload.mkdir(parents=True)
    sca, sca_d = _copy_payloads(root)
    readback_checks = _copy_goldens(root)
    return_allowlist = _return_allowlist(readback_checks)
    copy_exact(RUNTIME_SOURCE, root / "pkg/runtime.py")
    copy_exact(OBSERVER_SOURCE, root / "obs/native_return_observer.svh")
    (root / "PREPARE_AND_RUN.sh").write_text(
        RUNNER, encoding="utf-8", newline="\n"
    )
    os.chmod(root / "PREPARE_AND_RUN.sh", 0o755)
    (root / "README.md").write_text(_readme(), encoding="utf-8", newline="\n")
    for source, destination in (
        (INTEGRATION_REPORT, root / "p/e2_report.json"),
        (INTEGRATION_VALIDATION, root / "p/e2_validation.json"),
        (INTEGRATION / "mapping_manifest.json", root / "p/mapping.json"),
        (INTEGRATION / "execplan_manifest.json", root / "p/execplan.json"),
        (INTEGRATION / "golden_manifest.json", root / "p/golden.json"),
    ):
        copy_exact(source, destination)

    n75_report = load_json(N75_REPORT)
    progress_contract = {
        "schema": "node0071-node0075-native-ordering-progress-contract-v1",
        "ordered_stages": (
            [f"node0071_stage{index:02d}" for index in range(1, 9)]
            + [f"node0075_accum_pass{index:02d}" for index in range(8)]
            + [f"node0075_scale_pass{index:02d}" for index in range(8)]
            + [f"node0075_round_pass{index:02d}" for index in range(8)]
        ),
        "stage_count": 32,
        "producer_stage": 8,
        "consumer_accumulate_stages": list(range(9, 17)),
        "expected": {
            "slice_finish_total": 512,
            "producer_hub_request_accept": 1024,
            "producer_hub_wdata_accept": 1024,
            "producer_stage08_slice_finish": 16,
            "node0075_a_request_accept": 8192,
            "node0075_a_consumer_data_accept": 8192,
            "a_traffic_bytes": 262144,
            "unique_a_bytes": 32768,
        },
        "stall_window_cycles": 1048576,
        "heartbeat_cycles": 262144,
        "a_event_limit": 9000,
        "explicit_barrier_claim": False,
        "opcode110_is_barrier": False,
        "canonical_prefix": "N75_CANONICAL_DECISION_V2",
        "event_prefix": "N75_A_REQ_V1",
    }
    write_json(root / "diag/progress.json", progress_contract)

    inner_paths = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    ]
    max_inner = max(map(len, inner_paths))
    longest = max(inner_paths, key=len)
    projected = 96 + 1 + len(PACKAGE_NAME) + 1 + max_inner
    manifest_path = root / "TEST_PACKAGE_MANIFEST.json"
    observer_path = root / "obs/native_return_observer.svh"
    manifest = {
        "schema": "node0071-node0075-native-ordering-server-package-v1",
        "package_name": PACKAGE_NAME,
        "install_name": PACKAGE_NAME,
        "run_namespace": PACKAGE_NAME,
        "return_directory": f"{PACKAGE_NAME}_return",
        "return_zip": f"{PACKAGE_NAME}_return.zip",
        "status": "PACKAGE_READY_NOT_RUN",
        "diagnostic_only": True,
        "diagnostic_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "functional_rtl_modified": False,
        "functional_rtl_file_count": 0,
        "explicit_barrier_claim": False,
        "opcode110_is_barrier": False,
        "server_source_identity_bound": False,
        "single_command": (
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
        ),
        "expected_return": f"{PACKAGE_NAME}_return.zip",
        "stage_count": 32,
        "execplan_line_count": 518,
        "formal_readback_count": len(sca_d),
        "a_preload_count": 0,
        "b_destination_count": 128,
        "readback_checks": readback_checks,
        "a_coverage": n75_report["a_consumer_coverage"],
        "observer": {
            "path": "obs/native_return_observer.svh",
            "size_bytes": observer_path.stat().st_size,
            "sha256": sha256(observer_path),
            "compile_macro": "NATIVE_RETURN_OBSERVER_ENABLE",
            "runtime_enable": "+RETURN_OBSERVER +N75_NATIVE_ORDERING",
            "time0_marker": (
                "N75_FEATURE_ENABLE_V2 feature=NATIVE_ORDERING enabled=1"
            ),
            "event_limit": 9000,
            "read_only": True,
        },
        "diagnostic_feature": {
            "name": "NATIVE_ORDERING",
            "runtime_enable": "+N75_NATIVE_ORDERING",
            "generic_observer_enable": "+RETURN_OBSERVER",
            "event_limit_argument": "+N75_A_EVENT_LIMIT=9000",
            "event_limit": 9000,
            "stall_window_argument": "+RETURN_OBS_STALL_CYCLES=1048576",
            "heartbeat_argument": "+RETURN_OBS_HEARTBEAT_CYCLES=262144",
            "time0_marker": (
                "N75_FEATURE_ENABLE_V2 feature=NATIVE_ORDERING enabled=1"
            ),
            "binding_receipt": "e/observer_binding.txt",
            "event_schema": "N75_A_REQ_V1",
            "canonical_schema": "N75_CANONICAL_DECISION_V2",
            "return_log_target": "log/return_observer.log",
        },
        "canonical_decision": {
            "schema": "N75_CANONICAL_DECISION_V2",
            "unique_record_required": True,
            "required_fields": [
                "decision",
                "reason",
                "boundary",
                "sample_begin",
                "sample_end",
                "stage_start",
                "stage_finish",
                "slice_finish_total",
                "producer_req",
                "producer_wdata",
                "producer_finish",
                "first_a_cycle",
                "first_a_order_ok",
                "a_req",
                "a_data",
                "a_event_lines",
            ],
            "natural_terminal_scope": "all 32 stages and all 16 slices",
            "explicit_barrier_claim": False,
        },
        "return_allowlist": return_allowlist,
        "diagnostic_execution_reduction": {
            "kept": (
                "complete graph-external node0071 8-stage producer prefix and "
                "complete node0075 24-stage target"
            ),
            "dropped": [],
            "reason": (
                "producer-consumer ordering and final D require the complete "
                "authorized 32-stage causal execution; no legal shorter boundary "
                "can generate the aliased A bytes"
            ),
            "boundary_input_source": "graph external typed uint8 inputs only",
            "host_internal_tensor_replay": False,
        },
        "path_length_budget": {
            "declared_target_root_max_chars": 96,
            "max_projected_absolute_path_chars": 240,
            "max_zip_member_chars": len(PACKAGE_NAME) + 1 + max_inner,
            "max_inner_suffix_chars": 128,
            "max_inner_depth": max(path.count("/") + 1 for path in inner_paths),
            "longest_inner_member": longest,
            "actual_max_inner_suffix_chars": max_inner,
            "projected_absolute_chars": projected,
            "exceptions": [],
        },
        "source_inputs": [
            identity(path)
            for path in (
                INTEGRATION_REPORT,
                INTEGRATION_VALIDATION,
                N75_REPORT,
                RUNTIME_SOURCE,
                OBSERVER_SOURCE,
                PLAN,
                AUTHORIZATION,
                RULE_INDEX,
                OPERATOR_RULES,
                HARDWARE_RULES,
                SERVER_RULES,
                INT8_RULES,
                UINT8_RULES,
            )
        ],
        "rule_receipts": [
            {
                **identity(path),
                "current_match": True,
            }
            for path in (
                RULE_INDEX,
                OPERATOR_RULES,
                HARDWARE_RULES,
                SERVER_RULES,
                INT8_RULES,
                UINT8_RULES,
            )
        ],
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed_rule_ids": [
                "CDA-EXECPLAN-BARRIER-OPCODE-LIVE-DRAIN-SEMANTICS-001",
                "CDA-SERVER-WORKLOAD-PROVENANCE-001",
                "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
                "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            ],
            "rule_delta_proposal": [],
        },
        "workload_files": records(workload),
        "files": records(root, {"TEST_PACKAGE_MANIFEST.json"}),
    }
    write_json(manifest_path, manifest)
    return manifest


def build() -> dict[str, Any]:
    required = [
        INTEGRATION_REPORT,
        INTEGRATION_VALIDATION,
        N75_REPORT,
        RUNTIME_SOURCE,
        OBSERVER_SOURCE,
        RULE_INDEX,
        OPERATOR_RULES,
        HARDWARE_RULES,
        SERVER_RULES,
        INT8_RULES,
        UINT8_RULES,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise PackageError(f"required input missing: {missing}")
    integration_validation = load_json(INTEGRATION_VALIDATION)
    if (
        integration_validation.get("status")
        != "CONFIG_BOUND_NATIVE_ORDERING_INTEGRATION_E2_VALIDATION_PASS"
    ):
        raise PackageError("integration E2 validation is not pass")
    if PACKAGE_DIR.exists() or ZIP_PATH.exists() or SIDECAR.exists():
        raise PackageError("fresh package identity required")

    with tempfile.TemporaryDirectory(prefix="n71n75_native_pkg_") as temporary:
        temp = Path(temporary)
        roots: list[Path] = []
        zips: list[Path] = []
        manifests: list[dict[str, Any]] = []
        for build_index in range(2):
            parent = temp / f"b{build_index}"
            root = parent / PACKAGE_NAME
            root.mkdir(parents=True)
            manifests.append(_build_tree(root))
            archive = parent / f"{PACKAGE_NAME}.zip"
            deterministic_zip(root, archive)
            roots.append(root)
            zips.append(archive)
        if zips[0].read_bytes() != zips[1].read_bytes():
            raise PackageError("deterministic double build ZIP bytes differ")
        if records(roots[0]) != records(roots[1]):
            raise PackageError("deterministic double build trees differ")
        PACKAGE_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(roots[0], PACKAGE_DIR)
        shutil.copyfile(zips[0], ZIP_PATH)

    zip_digest = sha256(ZIP_PATH)
    SIDECAR.write_text(
        f"{zip_digest}  {ZIP_PATH.name}\n",
        encoding="ascii",
        newline="\n",
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "node0071-node0075-native-ordering-package-build-report-v1",
        "build_id": BUILD_ID,
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_SELF_AUDIT",
        "package_release": "HELD_PENDING_FINAL_ZIP_SELF_AUDIT",
        "candidate_release": False,
        "package": {
            "path": PACKAGE_DIR.relative_to(ROOT).as_posix(),
            "file_count": len(records(PACKAGE_DIR)),
        },
        "zip": {
            "path": ZIP_PATH.relative_to(ROOT).as_posix(),
            "size_bytes": ZIP_PATH.stat().st_size,
            "sha256": zip_digest,
        },
        "sidecar": identity(SIDECAR),
        "deterministic_double_build": True,
        "functional_rtl_modified": False,
        "server_uploaded": False,
        "server_run": False,
        "lease_taken": False,
        "final_zip_self_audit_passed": False,
    }
    write_json(REPORT_DIR / "build_report.json", report)
    return report


def main() -> int:
    try:
        report = build()
    except (PackageError, OSError, ValueError, KeyError) as exc:
        print(f"PACKAGE_BUILD_FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
