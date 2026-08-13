from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip


SOURCE = "r5_qadd_n7_cout32_rootclean_v37"
TARGET = "r5_qadd_n7_fullchain_v45"
SOURCE_SHA = "699696dcf59e1453669aa0af12c599963d05ed176f417858ddf2095fee4fcf87"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
FULL_PIPELINE = ROOT / "artifacts/q38/w/pipeline_output"
FULL_RECEIPT = ROOT / "artifacts/q38/build_receipt.json"
GOLDEN_SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_qadd_n7_split_d_full_v26/validation/golden"
)
FULL_CONTRACT_SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_qadd_n7_split_d_full_v26/TEST_PACKAGE_MANIFEST.json"
)
FULL_RUNTIME_SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_qadd_n7_split_d_full_v26/workload/runtime"
)
OUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fullchain-v45-package"
)
OUT_ZIP = OUT / f"{TARGET}.zip"
SERVER_RULE_SHA = (
    "16f7773796dccf4f27a5e412bb200f7b4190ffb87742d3dd2e466866a7f77dde"
)
INDEX_SHA = (
    "68c13cbd1461ca2a506174678d22cfdbfdc5aced25ad80150d4e4cacece7f2be"
)
HELPER = ROOT / "tools/server_package_runtime_layout.py"
HELPER_SHA = (
    "7969ca56e13a7e0a0a83bdfd48d1409d28eef2ae0fd63ad08f0ec5c39e2d848a"
)
RUNTIME = ROOT / "tools/qlinearadd_node0007_fullchain_runtime_v38.py"
BASE_RUNTIME_NAME = "qlinearadd_node0007_split_server_runtime_v25.py"
ROOT_GUARD_NAME = "qlinearadd_ndp_root_guard_v37.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def file_records(package: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def safe_extract(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA:
        raise ValueError("v37 source ZIP SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise ValueError("v37 source ZIP CRC differs")
        seen: set[str] = set()
        roots: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                raise ValueError(f"unsafe v37 member: {info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {SOURCE}:
            raise ValueError(f"v37 ZIP root differs: {roots}")
        archive.extractall(destination)
    return destination / SOURCE


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".bin", ".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE in text:
            path.write_text(
                text.replace(SOURCE, TARGET), encoding="utf-8", newline="\n"
            )


def _rewrite_paths(value: Any, old_prefix: str, new_prefix: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if (
                key == "path"
                and isinstance(child, str)
                and child.startswith(old_prefix)
            ):
                value[key] = new_prefix + child[len(old_prefix) :]
            else:
                _rewrite_paths(child, old_prefix, new_prefix)
    elif isinstance(value, list):
        for child in value:
            _rewrite_paths(child, old_prefix, new_prefix)


def install_full_workload(package: Path) -> dict[str, Any]:
    runtime = package / "workload/runtime"
    if runtime.exists():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True)
    shutil.copytree(FULL_PIPELINE / "install", runtime / "install")
    for stage in ("op_a_dequant", "op_b_dequant", "op_relocation_pad"):
        shutil.copytree(
            FULL_RUNTIME_SOURCE / "install" / stage,
            runtime / "install" / stage,
        )
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        shutil.copy2(FULL_RUNTIME_SOURCE / name, runtime / name)

    sca_path = runtime / "sca_cfg.json"
    sca = json.loads(sca_path.read_text(encoding="utf-8"))
    paths = [
        str(value["path"])
        for value in sca.values()
        if isinstance(value, dict) and isinstance(value.get("path"), str)
    ]
    if not paths or any(not path.startswith("install/") for path in paths):
        raise ValueError("SCA source namespace differs")
    first_parts = PurePosixPath(paths[0]).parts
    if first_parts[:2] == ("install", "cfg_pkg"):
        old_prefix = "/".join(first_parts[:3]) + "/"
        if any(not path.startswith(old_prefix) for path in paths):
            raise ValueError("SCA namespaced source prefix differs")
        _rewrite_paths(sca, old_prefix, f"install/cfg_pkg/{TARGET}/")
    else:
        _rewrite_paths(sca, "install/", f"install/cfg_pkg/{TARGET}/install/")
    write_json(sca_path, sca)

    full_contract = json.loads(FULL_CONTRACT_SOURCE.read_text(encoding="utf-8"))[
        "split_segment_contract"
    ]
    sca_d_path = runtime / "sca_cfg_D.json"
    sca_d = json.loads(sca_d_path.read_text(encoding="utf-8"))
    checks = {
        str(item["sca_key"]): item for item in full_contract["output_checks"]
    }
    if set(sca_d) != set(checks):
        raise ValueError("full pipeline/contract formal-D keys differ")
    for key, record in sca_d.items():
        record["path"] = (
            f"install/codex_runs/{TARGET}/{{attempt}}/"
            + str(checks[key]["runtime_path"])
        )
    write_json(sca_d_path, sca_d)

    golden = package / "validation/golden"
    if golden.exists():
        shutil.rmtree(golden)
    shutil.copytree(GOLDEN_SOURCE, golden)
    return full_contract


def update_progress_contract(package: Path) -> None:
    path = package / "diagnostics/progress_contract.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    stages = [
        "op_a_dequant",
        "op_b_dequant",
        "op_relocation_pad",
        "op_fp32_add",
        "op_tail_mul",
        "op_tail_round",
    ]
    value["schema"] = "qlinearadd-node0007-fullchain-progress-v38"
    value["stage_count"] = len(stages)
    value["stage_names"] = stages
    value["final_stage"] = stages[-1]
    value["claim_boundary"] = (
        "Qualified six-stage order plus low-rate causal checkpoints; level "
        "samples are state only and do not count as progress."
    )
    write_json(path, value)


def runner_text() -> str:
    return f"""#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
install_name="{TARGET}"
package_id="{TARGET}"
result_root="/home/panqs/ndp/simresult"
return_zip="$result_root/${{install_name}}_return.zip"
return_sha="${{return_zip}}.sha256"
package_root="$(dirname "${{BASH_SOURCE[0]}}")"
runtime="$package_root/package_tools/qlinearadd_node0007_fullchain_runtime_v38.py"
base_runtime="$package_root/package_tools/{BASE_RUNTIME_NAME}"
root_guard="$package_root/package_tools/{ROOT_GUARD_NAME}"
layout_helper="$package_root/package_tools/server_package_runtime_layout.py"
compile_status=125
simulation_status=125
signal_name=NONE
finalized=0
sim_pid=0
sampler_pid=0
server_root=
cfg_root=
run_root=
evidence_root=
compile_root=
attempt="a$$"
publish_minimal_return() {{
  mkdir -p -- "$result_root" || return 98
  [ -d "$result_root" ] && [ -w "$result_root" ] || return 98
  stage="$result_root/.${{install_name}}.return.$$"
  [ ! -e "$stage" ] || return 98
  mkdir -- "$stage" || return 98
  printf '%s\\n' "$compile_status" >"$stage/compile_exit_status.txt"
  printf '%s\\n' "$simulation_status" >"$stage/simulation_exit_status.txt"
  printf '%s\\n' "$signal_name" >"$stage/signal_status.txt"
  python3 - "$stage" "$return_zip" "$install_name" <<'PY'
import hashlib,json,os,pathlib,sys,zipfile
stage=pathlib.Path(sys.argv[1]); target=pathlib.Path(sys.argv[2]); ident=sys.argv[3]
manifest={{"schema":"server-partial-return-v1","install_name":ident,
"classification":"PRECHECK_PARTIAL_RETURN","allowlist":[
"compile_exit_status.txt","simulation_exit_status.txt","signal_status.txt",
"RETURN_MANIFEST.json"]}}
(stage/"RETURN_MANIFEST.json").write_text(json.dumps(manifest,sort_keys=True)+"\\n")
tmp=target.parent/("."+target.name+".tmp."+str(os.getpid()))
with zipfile.ZipFile(tmp,"w",compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(stage.iterdir()): z.write(p,f"{{ident}}_return/{{p.name}}")
with zipfile.ZipFile(tmp) as z: assert z.testzip() is None
os.replace(tmp,target)
digest=hashlib.sha256(target.read_bytes()).hexdigest()
side=pathlib.Path(str(target)+".sha256.tmp."+str(os.getpid()))
side.write_text(f"{{digest}}  {{target.name}}\\n")
os.replace(side,pathlib.Path(str(target)+".sha256"))
PY
  rc=$?
  rm -rf -- "$stage"
  return "$rc"
}}
sample_progress() {{
  [ -n "$evidence_root" ] && [ -d "$evidence_root" ] || return 0
  host_ns="$(date +%s%N)"
  tail_line=NONE
  [ ! -s "$run_root/return_observer.log" ] || \
    tail_line="$(tail -n 1 "$run_root/return_observer.log" | tr '\\t' ' ')"
  printf '%s\\t%s\\n' "$host_ns" "$tail_line" >>"$evidence_root/progress_samples.log"
}}
progress_sampler() {{
  while kill -0 "$sim_pid" 2>/dev/null; do sample_progress; sleep 60; done
  sample_progress
}}
finalize() {{
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1
  trap - EXIT HUP INT TERM
  set +e
  if [ "$sim_pid" -gt 0 ] && kill -0 "$sim_pid" 2>/dev/null; then
    kill -TERM "$sim_pid" 2>/dev/null; wait "$sim_pid" 2>/dev/null
  fi
  if [ "$sampler_pid" -gt 0 ] && kill -0 "$sampler_pid" 2>/dev/null; then
    kill -TERM "$sampler_pid" 2>/dev/null; wait "$sampler_pid" 2>/dev/null
  fi
  if [ -n "$evidence_root" ] && [ -d "$evidence_root" ] && \
     [ -n "$run_root" ] && [ -d "$run_root" ]; then
    sample_progress
    printf '%s\\n' "$compile_status" >"$evidence_root/compile_exit_status.txt"
    printf '%s\\n' "$simulation_status" >"$evidence_root/simulation_exit_status.txt"
    printf '%s\\n' "$signal_name" >"$evidence_root/signal_status.txt"
    python3 "$package_root/package_tools/qlinearadd_node0007_split_canonical_v25.py" \
      --observer-log "$run_root/return_observer.log" \
      --progress-contract "$evidence_root/progress_contract.json" \
      --output "$evidence_root/CANONICAL_PROGRESS_DECISION.json"
    canonical_status=$?
    printf '%s\\n' "$canonical_status" >"$evidence_root/canonical_decision_exit_status.txt"
    python3 "$runtime" analyze --package-root "$package_root" \
      --evidence-root "$evidence_root" --run-root "$run_root" \
      --compile-status "$compile_status" --simulation-status "$simulation_status"
    analysis_status=$?
    python3 "$root_guard" compare --server-root "$server_root" \
      --pre "$evidence_root/ndp_root_toplevel_pre.json" \
      --output "$evidence_root/ndp_root_toplevel_post.json"
    root_status=$?
    python3 "$runtime" collect --server-root "$server_root" \
      --install-name "$install_name" --package-root "$package_root" \
      --evidence-root "$evidence_root" --run-root "$run_root"
    collect_status=$?
    final="$original"
    [ "$final" -ne 0 ] || [ "$canonical_status" -eq 0 ] || final="$canonical_status"
    [ "$final" -ne 0 ] || [ "$analysis_status" -eq 0 ] || final="$analysis_status"
    [ "$final" -ne 0 ] || [ "$root_status" -eq 0 ] || final="$root_status"
    [ "$final" -ne 0 ] || [ "$collect_status" -eq 0 ] || final="$collect_status"
  else
    publish_minimal_return
    publish_status=$?
    final="$original"
    [ "$final" -ne 0 ] || [ "$publish_status" -eq 0 ] || final="$publish_status"
  fi
  exit "$final"
}}
on_signal() {{
  signal_name="$1"
  [ "$sim_pid" -le 0 ] || kill -TERM "$sim_pid" 2>/dev/null
  finalize "$2"
}}
trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x" >&2
  exit 2
fi
case "$1" in /*) ;; *) echo "server_root must be absolute" >&2; exit 2;; esac
for tool in python3 timeout make date tail grep; do
  command -v "$tool" >/dev/null 2>&1 || exit 3
done
package_root="$(cd "$package_root" && pwd -P)" || exit 2
runtime="$package_root/package_tools/qlinearadd_node0007_fullchain_runtime_v38.py"
base_runtime="$package_root/package_tools/{BASE_RUNTIME_NAME}"
root_guard="$package_root/package_tools/{ROOT_GUARD_NAME}"
layout_helper="$package_root/package_tools/server_package_runtime_layout.py"
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2
mkdir -p -- "$result_root" || exit 9
[ -d "$result_root" ] && [ -w "$result_root" ] || exit 9
[ "$(cd "$result_root" && pwd -P)" = "$result_root" ] || exit 9
[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || exit 10
root_pre="$(python3 "$root_guard" snapshot --server-root "$server_root")" || exit 12
layout_values="$(python3 "$layout_helper" prepare \
  --server-root "$server_root" --package-id "$package_id" \
  --install-name "$install_name" --attempt "$attempt" --format shell)" || exit 13
eval "$layout_values"
cfg_root="$CFG_ROOT"
run_root="$RUN_ROOT"
evidence_root="$EVIDENCE_ROOT"
compile_root="$COMPILE_ROOT"
mkdir -p -- "$compile_root/sim_results"
printf '%s\\n' "$root_pre" >"$evidence_root/ndp_root_toplevel_pre.json"
cat >"$evidence_root/fixed_result_preflight.json" <<EOF
{{"result_root":"/home/panqs/ndp/simresult",
"return_zip":"/home/panqs/ndp/simresult/${{install_name}}_return.zip",
"return_sidecar":"/home/panqs/ndp/simresult/${{install_name}}_return.zip.sha256"}}
EOF
cp "$package_root/diagnostics/progress_contract.json" "$evidence_root/progress_contract.json"
printf '# SIMULATION_NOT_STARTED\\n' >"$run_root/sim.log"
printf '# OBSERVER_NOT_STARTED\\n' >"$run_root/return_observer.log"
python3 "$runtime" preflight --package-root "$package_root" \
  >"$evidence_root/package_preflight.json" || exit 5
cp -a "$package_root/workload/runtime/." "$cfg_root/"
python3 - "$cfg_root/sca_cfg_D.json" "$attempt" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text())
for v in d.values(): v["path"]=v["path"].replace("{{attempt}}",sys.argv[2])
p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\\n")
PY
for slice_id in $(seq -w 0 27); do
  mkdir -p -- "$run_root/op_tail_round/slice${{slice_id}}"
done
python3 "$runtime" preflight-installed --package-root "$package_root" \
  --cfg-root "$cfg_root" --run-root "$run_root" \
  >"$evidence_root/installed_preflight.json" || exit 6
printf 'feature=QADD_FULLCHAIN_CAUSAL\\nargv_enabled=true\\n' \
  >"$evidence_root/feature_receipt.txt"
printf 'RUNTIME_LAYOUT_COMPILE_START\\n' >"$evidence_root/compile_started.marker"
cd "$server_root"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 \
  TB_DUMP_FSDB=0 RUN_DIR="$compile_root" \
  VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe +define+NATIVE_RETURN_OBSERVER_ENABLE" \
  >"$compile_root/sim_results/compile_driver.log" 2>&1
compile_status=$?
[ "$compile_status" -eq 0 ] || exit "$compile_status"
simv="$compile_root/sim_results/simv"
sim_args=(-l "$run_root/sim.log" +vcs+lic+wait
  "+SCA_CFG=$cfg_root/sca_cfg.json"
  "+SCA_CFG_D=$cfg_root/sca_cfg_D.json"
  +RETURN_OBSERVER +RETURN_OBS_SLICE=0
  +RETURN_OBS_STALL_CYCLES=1048576 +RETURN_OBS_HEARTBEAT_CYCLES=1048576
  +QADD_FP32_INGRESS_OBSERVER +RETURN_OBS_DEEP +RETURN_OBS_DEEP_LIMIT=64
  "+RETURN_OBS_FILE=$run_root/return_observer.log")
printf 'RUNTIME_LAYOUT_SIMULATION_START\\n' >"$evidence_root/simulation_started.marker"
printf 'timeout --foreground --signal=TERM --kill-after=30s 8h %q' "$simv" \
  >"$evidence_root/actual_simulator_argv.txt"
printf ' %q' "${{sim_args[@]}}" >>"$evidence_root/actual_simulator_argv.txt"
printf '\\n' >>"$evidence_root/actual_simulator_argv.txt"
timeout --foreground --signal=TERM --kill-after=30s 8h "$simv" "${{sim_args[@]}}" &
sim_pid=$!
progress_sampler &
sampler_pid=$!
wait "$sim_pid"
simulation_status=$?
sim_pid=0
[ "$sampler_pid" -le 0 ] || kill -TERM "$sampler_pid" 2>/dev/null
[ "$sampler_pid" -le 0 ] || wait "$sampler_pid" 2>/dev/null
sampler_pid=0
[ "$simulation_status" -eq 0 ] || exit "$simulation_status"
exit 0
"""


def runtime_contract(package: Path) -> dict[str, Any]:
    attempt = "a" * 10
    projected = {
        f"install/cfg_pkg/{TARGET}/"
        + path.relative_to(package / "workload/runtime").as_posix()
        for path in (package / "workload/runtime").rglob("*")
        if path.is_file()
    }
    additional = [
        f"install/codex_runs/{TARGET}/{{attempt}}/return_observer.log",
        f"install/codex_runs/{TARGET}/{{attempt}}/compile/sim_results/compile_driver.log",
        f"install/codex_runs/{TARGET}/{{attempt}}/op_tail_round/slice27/matrix_D_linearized_128bit.txt",
    ]
    roots = [
        f"install/cfg_pkg/{TARGET}",
        f"install/codex_runs/{TARGET}/{attempt}",
        f"install/codex_runs/{TARGET}/{attempt}/evidence",
        f"install/codex_runs/{TARGET}/{attempt}/compile",
    ]
    candidates = projected | {
        value.replace("{attempt}", attempt) for value in additional
    } | set(roots)
    longest = max(candidates, key=lambda value: (len(value), value))
    return {
        "schema": "server_package_runtime_layout_v1",
        "package_id": TARGET,
        "install_name": TARGET,
        "runner_member": "PREPARE_AND_RUN.sh",
        "manifest_member": "TEST_PACKAGE_MANIFEST.json",
        "shared_layout_helper": {
            "member": "package_tools/server_package_runtime_layout.py",
            "sha256": HELPER_SHA,
        },
        "tb_cwd": "$server_root",
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "required_preexisting_parents": ["install"],
        "package_creatable_parent_dirs": [
            "install/cfg_pkg",
            "install/codex_runs",
        ],
        "runtime_roots": {
            "cfg_root": f"install/cfg_pkg/{TARGET}",
            "run_root": f"install/codex_runs/{TARGET}/{{attempt}}",
            "evidence_root": f"install/codex_runs/{TARGET}/{{attempt}}/evidence",
            "compile_root": f"install/codex_runs/{TARGET}/{{attempt}}/compile",
        },
        "payload_mounts": [
            {
                "source_prefix": "workload/runtime/",
                "runtime_prefix": f"install/cfg_pkg/{TARGET}/",
            }
        ],
        "sca_consumers": [
            {
                "plusarg": "SCA_CFG",
                "member": "workload/runtime/sca_cfg.json",
                "mode": "read_inputs",
            },
            {
                "plusarg": "SCA_CFG_D",
                "member": "workload/runtime/sca_cfg_D.json",
                "mode": "write_outputs",
            },
        ],
        "runner_bindings": {
            "layout_prepare_marker": 'layout_values="$(python3 "$layout_helper" prepare',
            "tb_cwd_marker": 'cd "$server_root"',
            "compile_marker": "printf 'RUNTIME_LAYOUT_COMPILE_START",
            "simulation_marker": "printf 'RUNTIME_LAYOUT_SIMULATION_START",
        },
        "path_budget": {
            "attempt_max_chars": 10,
            "declared_target_root_max_chars": 96,
            "max_projected_absolute_path_chars": 97 + len(longest),
            "absolute_path_limit_chars": 240,
            "additional_projected_paths": additional,
        },
        "finalizer": {
            "arm_marker": "trap 'finalize $?' EXIT",
            "first_preflight_marker": 'if [ "$#" -ne 1 ]; then',
            "required_scenarios": [
                "normal",
                "preflight_fail",
                "compile_fail",
                "HUP",
                "INT",
                "TERM",
            ],
        },
        "claim_boundary": (
            "Package-local install-subtree/runtime-path/finalizer contract "
            "only. Production compile, DUT simulation, six-stage natural "
            "terminal, formal UINT8 28D, numeric correctness, E3, E4 and E5 "
            "require a formal server return."
        ),
        "_computed": {"longest": longest, "absolute": 97 + len(longest)},
    }


def update_manifest(package: Path, full_contract: dict[str, Any]) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["install_name"] = TARGET
    manifest["claim"] = "CONFIG_ONLY_CORRECTNESS_BASELINE"
    manifest["evidence_level"] = "E2_LOCAL_ONLY"
    manifest["candidate_release"] = False
    manifest["simulation_timeout"] = "8h"
    manifest["split_segment_contract"] = full_contract
    manifest["split_segment_contract"]["claim_boundary"] = (
        "full six-stage natural terminal plus exact final UINT8 28D"
    )
    manifest["source_assets"]["v37_split_c_return"] = {
        "path": (
            "artifacts/operator_config_validation/"
            "r5-qlinearadd-node0007-v37-return-analysis/report.json"
        ),
        "sha256": (
            "5b2488cbb93dc70561fc3b7054daf24d0b2ca5b886c889240c99e3b887988266"
        ),
    }
    manifest["source_assets"]["fullchain_local_assembly"] = {
        "path": FULL_RECEIPT.relative_to(ROOT).as_posix(),
        "sha256": sha256(FULL_RECEIPT),
    }
    manifest["frozen_semantics"].update(
        {
            "numeric_W3_qparams_tail": True,
            "workload_config_golden": True,
            "v37_fp32_output32": True,
            "functional_rtl": True,
        }
    )
    for item in manifest["return_allowlist"]:
        if str(item.get("source_path", "")).startswith("op_tail_round/"):
            item["source_root"] = "run"
    required = {
        str(item["target_path"]) for item in manifest["return_allowlist"]
    }
    for target in (
        "evidence/runtime_layout_receipt.json",
        "evidence/ndp_root_toplevel_pre.json",
        "evidence/ndp_root_toplevel_post.json",
        "evidence/fixed_result_preflight.json",
        "evidence/feature_receipt.txt",
    ):
        if target not in required:
            manifest["return_allowlist"].append(
                {
                    "source_root": "evidence",
                    "source_path": target.removeprefix("evidence/"),
                    "target_path": target,
                    "required": True,
                    "max_bytes": 1 << 20,
                }
            )
    receipts = manifest["rule_receipts"]
    receipts["server"]["sha256"] = SERVER_RULE_SHA
    receipts["server"]["path"] = ".agents/rules/服务器测试包生成规则.md"
    manifest["full_chain_gate"] = {
        "ordered_stage_names": full_contract["stage_names"],
        "natural_terminal_required": True,
        "formal_D_expected": 28,
        "formal_D_dtype": "uint8",
        "exact_golden_compare_required": True,
        "result_conjunction": (
            "compile0 AND simulation0 AND natural_terminal AND ordered6 "
            "AND formal_D_exact_set28 AND missing0 AND invalid0 AND mismatch0"
        ),
    }
    contract = runtime_contract(package)
    computed = contract.pop("_computed")
    write_json(package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json", contract)
    manifest["runtime_install_contract"] = {
        "only_preexisting_real_parent": "install",
        "package_creates": ["install/cfg_pkg", "install/codex_runs"],
        "cfg_root": f"$server_root/install/cfg_pkg/{TARGET}",
        "run_root": f"$server_root/install/codex_runs/{TARGET}/<attempt>",
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "root_direct_name_type_exact_set_unchanged": True,
        "shared_helper_sha256": HELPER_SHA,
    }
    manifest["path_length_budget"] = {
        "declared_target_root_max_chars": 96,
        "longest_projected_relative_path": computed["longest"],
        "longest_projected_relative_path_chars": len(computed["longest"]),
        "max_projected_absolute_path_chars": computed["absolute"],
        "absolute_path_limit_chars": 240,
        "pass": computed["absolute"] <= 240,
    }
    manifest["release_gate_matrix"] = {
        "schema": "server-package-release-gate-matrix-v1",
        "entries": {
            "package_bootstrap_path_runtime_D": {
                "applicability": "blocking_applicable",
                "status": "PASS_PENDING_FINAL_ZIP",
            },
            "runner_compile_finalizer": {
                "applicability": "blocking_applicable",
                "status": "PASS_PENDING_FINAL_ZIP",
            },
            "package_local_HDL": {
                "applicability": "receipt_reuse",
                "status": "PASS",
                "reason": "observer HDL byte-equal to dynamically compiled v37",
            },
            "materialized_config": {
                "applicability": "receipt_reuse",
                "status": "PASS",
                "reason": "six config JSONs and addresses byte-equal to v36/v18",
            },
            "observer_canonical": {
                "applicability": "blocking_applicable",
                "status": "PASS_PENDING_FINAL_ZIP",
            },
            "return_result": {
                "applicability": "blocking_applicable",
                "status": "PASS_PENDING_FINAL_ZIP",
            },
            "numeric_W3_golden": {
                "applicability": "receipt_reuse",
                "status": "PASS",
                "reason": "28 independent golden payloads byte-equal to v26",
            },
        },
    }
    manifest["final_zip_rule_self_audit"] = {
        "required": True,
        "status": "PENDING_EXACT_FINAL_ZIP",
        "rule_sha256": SERVER_RULE_SHA,
    }
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_fullchain_v38_server_package.py"
    )
    manifest["provenance"]["analysis_owner_thread"] = (
        "019fa2c0-b647-7a91-93bf-d21a173487e3"
    )
    manifest["provenance"]["return_target_thread"] = (
        "019fbec2-fe93-7e03-9314-cff6f222f33d"
    )
    manifest["files"] = file_records(package)
    write_json(path, manifest)


def build_directory(destination: Path) -> Path:
    package = safe_extract(destination)
    target = destination / TARGET
    package.rename(target)
    package = target
    replace_identity(package)
    full_contract = install_full_workload(package)
    update_progress_contract(package)
    tools = package / "package_tools"
    shutil.copy2(RUNTIME, tools / RUNTIME.name)
    shutil.copy2(HELPER, tools / HELPER.name)
    (package / "PREPARE_AND_RUN.sh").write_text(
        runner_text(), encoding="utf-8", newline="\n"
    )
    readme = package / "README.md"
    readme.write_text(
        "# QLinearAdd node0007 full-chain v38\n\n"
        "Six frozen stages, natural terminal, and exact final UINT8 28D. "
        "Only the real non-symlink server `install` directory must pre-exist; "
        "the package creates its cfg/run parents below it.\n\n"
        f"Run: `bash {TARGET}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        f"Return: `/home/panqs/ndp/simresult/{TARGET}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, full_contract)
    return package


def main() -> int:
    if (OUT / "build_receipt.json").exists() or OUT_ZIP.exists():
        raise ValueError(f"completed package output already exists: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="q38a-") as first, tempfile.TemporaryDirectory(
        prefix="q38b-"
    ) as second:
        package_a = build_directory(Path(first))
        package_b = build_directory(Path(second))
        zip_a = Path(first) / f"{TARGET}.zip"
        zip_b = Path(second) / f"{TARGET}.zip"
        deterministic_zip(package_a, zip_a)
        deterministic_zip(package_b, zip_b)
        if zip_a.read_bytes() != zip_b.read_bytes():
            raise ValueError("deterministic QAdd v38 builds differ")
        shutil.copy2(zip_a, OUT_ZIP)
    digest = sha256(OUT_ZIP)
    sidecar = Path(str(OUT_ZIP) + ".sha256")
    sidecar.write_text(
        f"{digest}  {OUT_ZIP.name}\n", encoding="ascii", newline="\n"
    )
    receipt = {
        "schema": "qlinearadd-node0007-fullchain-package-build-v38",
        "status": "BUILT_PENDING_FINAL_ZIP_AUDIT",
        "zip": {
            "path": OUT_ZIP.relative_to(ROOT).as_posix(),
            "bytes": OUT_ZIP.stat().st_size,
            "sha256": digest,
        },
        "deterministic_double_build": True,
        "source_v37_sha256": SOURCE_SHA,
        "fullchain_local_receipt_sha256": sha256(FULL_RECEIPT),
        "numeric_analysis_repeated": False,
        "split_c_repeated": False,
        "server_action": False,
    }
    write_json(OUT / "build_receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
