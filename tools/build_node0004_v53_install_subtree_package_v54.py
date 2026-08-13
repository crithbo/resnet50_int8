from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_node0004_v51_ndp_root_gate_package_v52 import (
    deterministic_zip,
    sha256,
)


SOURCE = "r5_n4_hw_v53_sca_cwd_fix"
INSTALL = "r5_n4_hw_v59_install_subtree"
SOURCE_SHA = "3ec80d1f583c267b4e894a06e196a61c63ed60ee5b5c672556329abd074ad77a"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
DEFAULT_OUTPUT = (
    ROOT / "outputs/conv_node0004_v53_install_subtree_successor/v59_build"
)
SERVER_RULE_SHA = (
    "570ffedd04d5f41bc3093e5aa498544325281a4d81f2f4ddc889b754e968424c"
)
INDEX_SHA = (
    "1101d76534c4898569dbfd0fd4ed1f99800d4a8ec0bdd8dbbef3ce030d147fc1"
)
CONVERGENCE_SHA = (
    "123e66c80048808e93b7151b1dca4af3faee823f458310d41856163790656020"
)
HELPER = ROOT / "tools/server_package_runtime_layout.py"
HELPER_SHA = (
    "82723ecc427c3e42cfc327eff87cae7d5d935b9f6dccb220e78bfa573d11a9ae"
)


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def extract_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA:
        raise BuildError("v53 source ZIP SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise BuildError(f"v53 source CRC failed at {bad}")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                raise BuildError(f"unsafe/duplicate member: {info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {SOURCE}:
            raise BuildError(f"v53 source root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE in text:
            path.write_text(
                text.replace(SOURCE, INSTALL), encoding="utf-8", newline="\n"
            )


def rewrite_sca_d(package: Path) -> None:
    path = package / "workload/runtime/runs/c0/sca_cfg_D.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    old_prefix = f"install/cfg_pkg/{INSTALL}/runs/c0/"
    new_prefix = f"install/codex_runs/{INSTALL}/{{attempt}}/c0/"
    changed = 0
    for value in document.values():
        if not isinstance(value, dict) or not isinstance(value.get("path"), str):
            raise BuildError("unexpected SCA-D leaf")
        old = value["path"]
        if not old.startswith(old_prefix):
            raise BuildError(f"unexpected SCA-D prefix: {old}")
        value["path"] = new_prefix + old[len(old_prefix) :]
        changed += 1
    if changed != 28:
        raise BuildError(f"SCA-D output count differs: {changed}")
    write_json(path, document)


def patch_runtime_preflight(package: Path) -> None:
    path = (
        package
        / "package_tools/node0004_hang_localization_runtime_v7.py"
    )
    text = path.read_text(encoding="utf-8")
    leaf_old = (
        '    elif isinstance(value, str) and '
        'value.startswith("install/cfg_pkg/"):\n'
    )
    leaf_new = (
        "    elif isinstance(value, str) and value.startswith(\n"
        '        ("install/cfg_pkg/", "install/codex_runs/")\n'
        "    ):\n"
    )
    if text.count(leaf_old) != 1:
        raise BuildError("runtime SCA path-leaf anchor differs")
    text = text.replace(leaf_old, leaf_new, 1)
    old = """        for leaf in _path_leaves(load_json(path)):
            prefix = f"install/cfg_pkg/{manifest['install_name']}/"
            if not leaf.startswith(prefix):
                raise DiagnosticRuntimeError(f"stale SCA root: {leaf}")
            target = safe_child(runtime, leaf[len(prefix) :])
            if path.name == "sca_cfg_D.json":
                if target.exists():
                    raise DiagnosticRuntimeError(f"preloaded D: {target}")
                output_count += 1
            else:
                if not target.is_file():
                    raise DiagnosticRuntimeError(f"missing input: {target}")
                input_count += 1
"""
    new = """        for leaf in _path_leaves(load_json(path)):
            if path.name == "sca_cfg_D.json":
                prefix = (
                    f"install/codex_runs/{manifest['install_name']}/"
                    "{attempt}/"
                )
                if not leaf.startswith(prefix):
                    raise DiagnosticRuntimeError(
                        f"stale SCA-D output root: {leaf}"
                    )
                output_count += 1
            else:
                prefix = f"install/cfg_pkg/{manifest['install_name']}/"
                if not leaf.startswith(prefix):
                    raise DiagnosticRuntimeError(f"stale SCA root: {leaf}")
                target = safe_child(runtime, leaf[len(prefix) :])
                if not target.is_file():
                    raise DiagnosticRuntimeError(f"missing input: {target}")
                input_count += 1
"""
    if text.count(old) != 1:
        raise BuildError("runtime SCA preflight anchor differs")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def runner_text() -> str:
    return f"""#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
install_name="{INSTALL}"
package_id="{INSTALL}"
result_root="/home/panqs/ndp/simresult"
return_zip="${{result_root}}/${{install_name}}_return.zip"
return_sha="${{return_zip}}.sha256"
package_root="$(dirname "${{BASH_SOURCE[0]}}")"
runtime="${{package_root}}/package_tools/node0004_hang_localization_runtime.py"
observer_guard="${{package_root}}/package_tools/node0004_package_observer_guard.py"
layout_helper="${{package_root}}/package_tools/server_package_runtime_layout.py"
compile_status=125
run_status=125
signal_status=NONE
finalized=0
sim_pid=
host_progress_pid=
server_root=
run_root=
evidence_root=
compile_root=
cfg_root=
attempt="a$$"
publish_minimal_return() {{
  mkdir -p -- "$result_root" || return 98
  [ -d "$result_root" ] && [ -w "$result_root" ] || return 98
  stage="${{result_root}}/.${{install_name}}.return.$$"
  [ ! -e "$stage" ] || return 98
  mkdir -- "$stage" || return 98
  printf '%s\\n' "$compile_status" > "$stage/compile_exit_status.txt"
  printf '%s\\n' "$run_status" > "$stage/run_exit_status.txt"
  printf '%s\\n' "$signal_status" > "$stage/signal_status.txt"
  printf '%s\\n' "PRECHECK_PARTIAL_RETURN" > "$stage/SERVER_RESULT_GATE"
  printf '%s\\n' "compile_exit_status.txt" "run_exit_status.txt" \
    "signal_status.txt" "SERVER_RESULT_GATE" "RETURN_MANIFEST.json" \
    > "$stage/RETURN_ALLOWLIST"
  python3 - "$stage" "$return_zip" "$install_name" <<'PY'
import hashlib, json, os, pathlib, sys, zipfile
stage = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
identity = sys.argv[3]
manifest = {{
    "schema": "server-partial-return-v1",
    "install_name": identity,
    "classification": "PRECHECK_PARTIAL_RETURN",
    "allowlist": [
        "compile_exit_status.txt", "run_exit_status.txt", "signal_status.txt",
        "SERVER_RESULT_GATE", "RETURN_MANIFEST.json"
    ],
}}
(stage / "RETURN_MANIFEST.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\\n", encoding="utf-8"
)
tmp = target.parent / ("." + target.name + ".tmp." + str(os.getpid()))
with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(stage.iterdir()):
        archive.write(path, f"{{identity}}_return/{{path.name}}")
with zipfile.ZipFile(tmp) as archive:
    assert archive.testzip() is None
os.replace(tmp, target)
digest = hashlib.sha256(target.read_bytes()).hexdigest()
side_tmp = pathlib.Path(str(target) + ".sha256.tmp." + str(os.getpid()))
side_tmp.write_text(f"{{digest}}  {{target.name}}\\n", encoding="ascii")
os.replace(side_tmp, pathlib.Path(str(target) + ".sha256"))
PY
  rc=$?
  rm -rf -- "$stage"
  return "$rc"
}}
finalize() {{
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1
  trap - EXIT INT TERM HUP
  set +e
  [ -z "$host_progress_pid" ] || kill "$host_progress_pid" 2>/dev/null
  [ -z "$host_progress_pid" ] || wait "$host_progress_pid" 2>/dev/null
  if [ -n "$evidence_root" ] && [ -d "$evidence_root" ] && \
     [ -n "$run_root" ] && [ -d "$run_root" ]; then
    printf '%s\\n' "$compile_status" > "$evidence_root/compile_exit_status.txt"
    printf '%s\\n' "$run_status" > "$evidence_root/run_exit_status.txt"
    printf '%s\\n' "$signal_status" > "$evidence_root/signal_status.txt"
    root_gate=96
    if [ -n "$server_root" ] && [ -d "$server_root" ]; then
      python3 "$runtime" root-snapshot --server-root "$server_root" \
        > "$evidence_root/ndp_root_toplevel_post.json"
      post_snapshot=$?
      if [ "$post_snapshot" -eq 0 ] && \
         [ -f "$evidence_root/ndp_root_toplevel_pre.json" ]; then
        python3 "$runtime" root-compare \
          --pre "$evidence_root/ndp_root_toplevel_pre.json" \
          --post "$evidence_root/ndp_root_toplevel_post.json" \
          --contract "$evidence_root/ndp_root_write_contract.json" \
          > "$evidence_root/ndp_root_toplevel_gate.json"
        root_gate=$?
      fi
    fi
    python3 "$runtime" analyze --package-root "$package_root" \
      --evidence-root "$evidence_root" --run-root "$run_root"
    analysis=$?
    python3 "$runtime" collect --server-root "$result_root" \
      --ndp-root "$server_root" --install-name "$install_name" \
      --evidence-root "$evidence_root" --run-root "$run_root"
    collection=$?
    final="$original"
    [ "$final" -ne 0 ] || [ "$analysis" -eq 0 ] || final="$analysis"
    [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] || final="$collection"
    [ "$final" -ne 0 ] || [ "$root_gate" -eq 0 ] || final="$root_gate"
  else
    publish_minimal_return
    publication=$?
    final="$original"
    [ "$final" -ne 0 ] || [ "$publication" -eq 0 ] || final="$publication"
  fi
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
if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/server_root" >&2
  exit 2
fi
case "$1" in /*) ;; *) echo "server_root must be absolute" >&2; exit 2;; esac
for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || exit 3; done
package_root="$(cd "$package_root" && pwd -P)" || exit 2
runtime="${{package_root}}/package_tools/node0004_hang_localization_runtime.py"
observer_guard="${{package_root}}/package_tools/node0004_package_observer_guard.py"
layout_helper="${{package_root}}/package_tools/server_package_runtime_layout.py"
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2
mkdir -p -- "$result_root" || exit 9
[ -d "$result_root" ] && [ -w "$result_root" ] || exit 9
resolved_result_root="$(cd "$result_root" && pwd -P)" || exit 9
[ "$resolved_result_root" = "$result_root" ] || exit 9
[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || exit 10
ndp_pre_snapshot="$(python3 "$runtime" root-snapshot --server-root "$server_root")" || exit 12
layout_values="$(python3 "$layout_helper" prepare \
  --server-root "$server_root" --package-id "$package_id" \
  --install-name "$install_name" --attempt "$attempt" \
  --format shell)" || exit 13
eval "$layout_values"
cfg_root="$CFG_ROOT"
run_root="$RUN_ROOT"
evidence_root="$EVIDENCE_ROOT"
compile_root="$COMPILE_ROOT"
mkdir -p -- "$compile_root/sim_results" "$run_root/c0"
printf '%s\\n' "$ndp_pre_snapshot" > "$evidence_root/ndp_root_toplevel_pre.json"
cat > "$evidence_root/ndp_root_write_contract.json" <<EOF
{{
  "schema": "ndp-root-write-contract-v1",
  "server_root": "${{server_root}}",
  "result_root": "/home/panqs/ndp/simresult",
  "root_internal_write_targets": [
    "install/cfg_pkg/${{install_name}}",
    "install/codex_runs/${{package_id}}/${{attempt}}"
  ],
  "existing_first_level_parents": ["install"],
  "external_write_targets": [
    "/home/panqs/ndp/simresult/${{install_name}}_return.zip",
    "/home/panqs/ndp/simresult/${{install_name}}_return.zip.sha256"
  ]
}}
EOF
cat > "$evidence_root/publication_preflight.json" <<EOF
{{
  "schema": "fixed-simresult-publication-preflight-v1",
  "result_root": "/home/panqs/ndp/simresult",
  "return_zip": "/home/panqs/ndp/simresult/${{install_name}}_return.zip",
  "return_sidecar": "/home/panqs/ndp/simresult/${{install_name}}_return.zip.sha256",
  "publication_state": "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING",
  "server_root_duplicate_absent": true,
  "package_root_duplicate_absent": true,
  "install_namespace_duplicate_absent": true,
  "run_root_duplicate_absent": true,
  "launch_cwd_duplicate_absent": true
}}
EOF
python3 "$runtime" path-budget --package-root "$package_root" \
  --target-root "$server_root" || exit 8
python3 "$runtime" preflight --package-root "$package_root" \
  > "$evidence_root/package_preflight.json" || exit 5
cp -a "$package_root/workload/runtime/." "$cfg_root/"
python3 "$runtime" verify-install --package-root "$package_root" \
  --cfg-root "$cfg_root" > "$evidence_root/install_preflight.json" || exit 6
python3 - "$cfg_root/runs/c0/sca_cfg_D.json" "$attempt" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
attempt = sys.argv[2]
doc = json.loads(path.read_text(encoding="utf-8"))
for value in doc.values():
    value["path"] = value["path"].replace("{{attempt}}", attempt)
path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
PY
python3 "$observer_guard" --package-root "$package_root" \
  --manifest "$package_root/package_manifest.json" \
  > "$evidence_root/observer_precompile.json" || exit 7
echo RUNTIME_LAYOUT_COMPILE_START > "$evidence_root/compile_started.marker"
cd "$server_root"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 \
  TB_DUMP_FSDB=0 RUN_DIR="$compile_root" \
  VCS_EXTRA_OPTS="+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe" \
  > "$compile_root/sim_results/compile_driver.log" 2>&1
compile_status=$?
[ "$compile_status" -eq 0 ] || exit "$compile_status"
simv="$compile_root/sim_results/simv"
echo RUNTIME_LAYOUT_SIMULATION_START > "$evidence_root/simulation_started.marker"
printf '%s\\n' \
  "$simv -l $run_root/c0/sim.log +vcs+lic+wait +SCA_CFG=$cfg_root/runs/c0/sca_cfg.json +SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json +RETURN_OBSERVER +RETURN_OBS_FILE=$run_root/c0/return_observer.log" \
  > "$run_root/c0/simulator_argv.txt"
timeout --foreground --signal=TERM --kill-after=30s 6h "$simv" \
  -l "$run_root/c0/sim.log" +vcs+lic+wait \
  "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" \
  "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" \
  +RETURN_OBSERVER +RETURN_OBS_MSE4_DESCRIPTOR +RETURN_OBS_MSE4_DESCRIPTOR_LIMIT=96 \
  +RETURN_OBS_MSE4_INDEX +RETURN_OBS_MSE4_INDEX_LIMIT=96 \
  +RETURN_OBS_LC18_PE7 +RETURN_OBS_LC18_PE7_LIMIT=96 \
  +RETURN_OBS_ROWLC4_BUFAG +RETURN_OBS_ROWLC4_BUFAG_LIMIT=128 \
  +RETURN_OBS_B5RD +RETURN_OBS_B5RD_LIMIT=96 \
  +RETURN_OBS_DWRITE_PATH +RETURN_OBS_DWRITE_PATH_LIMIT=64 \
  +RETURN_OBS_DATAHUB_DRAIN +RETURN_OBS_DATAHUB_DRAIN_LIMIT=64 \
  +RETURN_OBS_WRDRAIN +RETURN_OBS_WRDRAIN_LIMIT=1 \
  +RETURN_OBS_WRTERM +RETURN_OBS_WRTERM_LIMIT=96 \
  +RETURN_OBS_LC9_SPLIT +RETURN_OBS_LC9_SPLIT_LIMIT=128 \
  +RETURN_OBS_LC9_ACTUAL +RETURN_OBS_LC9_ACTUAL_LIMIT=192 \
  +RETURN_OBS_DTERM_OWNER +RETURN_OBS_DTERM_OWNER_LIMIT=96 \
  +RETURN_OBS_LC13_LC14 +RETURN_OBS_LC13_LC14_LIMIT=128 \
  +RETURN_OBS_SLICE=0 +RETURN_OBS_STALL_CYCLES=4096 \
  +RETURN_OBS_HEARTBEAT_CYCLES=262144 +RETURN_HANG_DIAG \
  +RETURN_HANG_DIAG_SAMPLE_CYCLES=262144 \
  +RETURN_HANG_DIAG_STALL_WINDOWS=4 +RETURN_HANG_DIAG_MAX_CYCLES=8388608 \
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


def package_records(package: Path) -> dict[str, str]:
    manifest_path = package / "package_manifest.json"
    return {
        path.relative_to(package).as_posix(): sha256(path)
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest_path
    }


def runtime_contract(package: Path) -> dict[str, object]:
    attempt_max = 10
    root_max = 96
    limit = 240
    additional = [
        f"install/codex_runs/{INSTALL}/{{attempt}}/c0/return_observer.log",
        f"install/codex_runs/{INSTALL}/{{attempt}}/compile/sim_results/compile_driver.log",
        f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/runtime_layout_receipt.json",
    ]
    projected = {
        f"install/cfg_pkg/{INSTALL}/"
        + path.relative_to(package / "workload/runtime").as_posix()
        for path in (package / "workload/runtime").rglob("*")
        if path.is_file()
    }
    attempt = "a" * attempt_max
    roots = [
        f"install/cfg_pkg/{INSTALL}",
        f"install/codex_runs/{INSTALL}/{attempt}",
        f"install/codex_runs/{INSTALL}/{attempt}/evidence",
        f"install/codex_runs/{INSTALL}/{attempt}/compile",
    ]
    candidates = projected | {
        value.replace("{attempt}", attempt) for value in additional
    } | set(roots)
    longest = max(candidates, key=lambda item: (len(item), item))
    projected_absolute = root_max + 1 + len(longest)
    return {
        "schema": "server_package_runtime_layout_v1",
        "package_id": INSTALL,
        "install_name": INSTALL,
        "runner_member": "PREPARE_AND_RUN.sh",
        "manifest_member": "package_manifest.json",
        "shared_layout_helper": {
            "member": "package_tools/server_package_runtime_layout.py",
            "sha256": HELPER_SHA,
        },
        "tb_cwd": "$server_root",
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "required_preexisting_parents": [
            "install",
            "install/cfg_pkg",
            "install/codex_runs",
        ],
        "runtime_roots": {
            "cfg_root": f"install/cfg_pkg/{INSTALL}",
            "run_root": f"install/codex_runs/{INSTALL}/{{attempt}}",
            "evidence_root": (
                f"install/codex_runs/{INSTALL}/{{attempt}}/evidence"
            ),
            "compile_root": (
                f"install/codex_runs/{INSTALL}/{{attempt}}/compile"
            ),
        },
        "payload_mounts": [
            {
                "source_prefix": "workload/runtime/",
                "runtime_prefix": f"install/cfg_pkg/{INSTALL}/",
            }
        ],
        "sca_consumers": [
            {
                "plusarg": "SCA_CFG",
                "member": "workload/runtime/runs/c0/sca_cfg.json",
                "mode": "read_inputs",
            },
            {
                "plusarg": "SCA_CFG_D",
                "member": "workload/runtime/runs/c0/sca_cfg_D.json",
                "mode": "write_outputs",
            },
        ],
        "runner_bindings": {
            "layout_prepare_marker": (
                'layout_values="$(python3 "$layout_helper" prepare'
            ),
            "tb_cwd_marker": 'cd "$server_root"',
            "compile_marker": "echo RUNTIME_LAYOUT_COMPILE_START",
            "simulation_marker": "echo RUNTIME_LAYOUT_SIMULATION_START",
        },
        "path_budget": {
            "attempt_max_chars": attempt_max,
            "declared_target_root_max_chars": root_max,
            "max_projected_absolute_path_chars": projected_absolute,
            "absolute_path_limit_chars": limit,
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
            "Mechanical install-subtree runtime layout and SCA path binding "
            "only; no numeric, RTL, terminal, formal-D, E4 or E5 claim."
        ),
        "_computed": {
            "longest": longest,
            "longest_chars": len(longest),
            "projected_absolute": projected_absolute,
        },
    }


def update_manifest(package: Path, contract: dict[str, object]) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    computed = contract.pop("_computed")
    manifest["install_name"] = INSTALL
    manifest["source_package_sha256"] = SOURCE_SHA
    manifest["active_receipts"]["generation_index_sha256"] = INDEX_SHA
    manifest["active_receipts"]["server_package_rule_sha256"] = SERVER_RULE_SHA
    manifest["active_receipts"]["convergence_rule_sha256"] = CONVERGENCE_SHA
    manifest["runtime_install_contract"] = {
        "schema": "install-subtree-runtime-layout-v1",
        "tb_launch_cwd": "$server_root",
        "cfg_root": f"$server_root/install/cfg_pkg/{INSTALL}",
        "run_root": (
            f"$server_root/install/codex_runs/{INSTALL}/<attempt>"
        ),
        "evidence_and_compile_under_run_root": True,
        "fixed_result_root_final_only": "/home/panqs/ndp/simresult",
        "input_consumer_count": 86,
        "output_consumer_count": 28,
        "shared_helper_sha256": HELPER_SHA,
    }
    manifest["ndp_root_toplevel_contract"] = {
        "root_internal_write_targets": [
            f"install/cfg_pkg/{INSTALL}",
            f"install/codex_runs/{INSTALL}/<attempt>",
        ],
        "existing_first_level_parents": ["install"],
        "required_preexisting_parents": [
            "install",
            "install/cfg_pkg",
            "install/codex_runs",
        ],
        "work_root": f"$server_root/install/codex_runs/{INSTALL}/<attempt>",
        "root_direct_name_type_exact_set_unchanged": True,
    }
    manifest["path_length_budget"] = {
        "declared_target_root_max_chars": 96,
        "longest_projected_relative_path": computed["longest"],
        "longest_projected_relative_path_chars": computed["longest_chars"],
        "max_projected_absolute_path_chars": computed["projected_absolute"],
        "absolute_path_limit_chars": 240,
        "rule_id": "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
        "pass": computed["projected_absolute"] <= 240,
    }
    manifest["v53_hold_adjudication"] = {
        "source_zip_sha256": SOURCE_SHA,
        "status": "PACKAGE_HELD_PRE_SHARED_INSTALL_LAYOUT_GATE",
        "replacement": INSTALL,
    }
    matrix = [
        row
        for row in manifest.get("release_gate_matrix", [])
        if row.get("gate_id") != "RUNTIME_LAYOUT"
    ]
    matrix.append(
        {
            "gate_id": "RUNTIME_LAYOUT",
            "applicability": "blocking_applicable",
            "blocking": True,
            "status": "PASS_PENDING_EXACT_FINAL_ZIP_SHARED_VALIDATION",
            "changed_surface": [
                "PREPARE_AND_RUN.sh",
                "SCA-D output paths",
                "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
                "package_manifest.json",
            ],
            "evidence": [
                "shared runtime-layout report",
                "family safe-runner harness",
                "all 86 SCA inputs opened from exact TB cwd",
            ],
        }
    )
    manifest["release_gate_matrix"] = matrix
    manifest["files"] = package_records(package)
    write_json(path, manifest)
    manifest["files"] = package_records(package)
    write_json(path, manifest)


def build_directory(output: Path) -> Path:
    package = output / INSTALL
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="node0004-v53-source-") as temp:
        shutil.copytree(extract_source(Path(temp)), package)
    replace_identity(package)
    rewrite_sca_d(package)
    patch_runtime_preflight(package)
    (package / "PREPARE_AND_RUN.sh").write_text(
        runner_text(), encoding="utf-8", newline="\n"
    )
    helper_target = package / "package_tools/server_package_runtime_layout.py"
    shutil.copyfile(HELPER, helper_target)
    if sha256(helper_target) != HELPER_SHA:
        raise BuildError("embedded shared layout helper differs")
    contract = runtime_contract(package)
    computed = dict(contract["_computed"])
    write_json(
        package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        {key: value for key, value in contract.items() if key != "_computed"},
    )
    write_json(
        package / "provenance/v53_to_v59_install_subtree.json",
        {
            "schema": "node0004-v53-to-v59-install-subtree-v1",
            "source_v53_sha256": SOURCE_SHA,
            "classification": "RUNNER_LAYOUT_ONLY_FUNCTIONAL_PACKAGE_FIX",
            "changed_surface": [
                "fresh identity",
                "runner cfg/run/evidence/compile layout",
                "SCA-D mechanical output path binding",
                "manifest/runtime-layout contract/README",
            ],
            "frozen": [
                "numeric",
                "W3",
                "qparam",
                "tail",
                "workload payload bytes except SCA path strings",
                "golden",
                "observer",
                "timeout",
                "backpressure",
                "functional RTL",
                "ISA",
                "hardware",
                "active ndp-sim",
            ],
            "server_action": False,
        },
    )
    (package / "README.md").write_text(
        "# node0004 v59 install-subtree runtime-layout fix\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "This fresh successor replaces held v53 mechanically. Package-owned "
        "cfg/run/evidence/compile state is created only below pre-existing "
        "`$server_root/install/cfg_pkg` and `$server_root/install/codex_runs`; "
        "`/home/panqs/ndp/simresult` is used only for the atomic final return. "
        "The TB cwd remains `$server_root`, and all 86 frozen SCA input paths "
        "resolve into the installed cfg subtree.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        f"Expected return: `/home/panqs/ndp/simresult/{INSTALL}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    contract["_computed"] = computed
    update_manifest(package, contract)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    targets = [
        output / INSTALL,
        output / f"{INSTALL}.zip",
        output / f"{INSTALL}.zip.sha256",
        output / f"{INSTALL}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite existing v59 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL}.zip"
    deterministic_zip(package, zip_path)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v59-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL}.zip"
        deterministic_zip(repeat, repeat_zip)
        deterministic = sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v59 deterministic rebuild differs")
    sidecar = output / f"{INSTALL}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-v53-to-v59-install-subtree-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v53_sha256": SOURCE_SHA,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "observer_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{INSTALL}.validation.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
