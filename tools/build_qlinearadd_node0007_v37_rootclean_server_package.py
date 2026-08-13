from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records


SOURCE_NAME = "r5_qadd_n7_cout32_v36"
TARGET_NAME = "r5_qadd_n7_cout32_rootclean_v37"
SOURCE_ZIP = ROOT / (
    "artifacts/operator_config_validation/r5-server-test-packages/pending/"
    f"{SOURCE_NAME}.zip"
)
SOURCE_SHA256 = "b10712a584ad69cfeacfeb70d4faa913d0a82e59f66a1466e3b59b444a90a382"
RETURN_REPORT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-v36-return-analysis/report.json"
)
OUT_ROOT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-v37-rootclean-package"
)
OUT_ZIP = OUT_ROOT / f"{TARGET_NAME}.zip"
OUT_SIDECAR = Path(str(OUT_ZIP) + ".sha256")

RULES = {
    "agent": ROOT / ".agents/agent.md",
    "index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common": ROOT / ".agents/rules/算子配置规则.md",
    "hardware": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_extract(source: Path, parent: Path) -> Path:
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise ValueError("source ZIP CRC failure")
        names = archive.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names}
        if roots != {SOURCE_NAME}:
            raise ValueError(f"source ZIP root differs: {sorted(roots)}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or (info.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ValueError(f"unsafe source ZIP member: {info.filename}")
        archive.extractall(parent)
    source_root = parent / SOURCE_NAME
    target_root = parent / TARGET_NAME
    source_root.rename(target_root)
    return target_root


ROOT_GUARD = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

def snapshot(root: Path) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("server root is not a directory")
    entries = []
    for path in root.iterdir():
        if path.is_symlink():
            kind = "symlink"
        elif path.is_dir():
            kind = "directory"
        elif path.is_file():
            kind = "file"
        else:
            kind = "other"
        entries.append({"name": path.name, "type": kind})
    entries.sort(key=lambda item: (item["name"], item["type"]))
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema": "ndp-root-toplevel-exact-set-v1",
        "server_root": str(root),
        "entries": entries,
        "entry_count": len(entries),
        "exact_set_sha256": hashlib.sha256(canonical).hexdigest(),
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--server-root", type=Path, required=True)
    compare = sub.add_parser("compare")
    compare.add_argument("--server-root", type=Path, required=True)
    compare.add_argument("--pre", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        current = snapshot(args.server_root)
        if args.cmd == "snapshot":
            print(json.dumps(current, sort_keys=True))
            return 0
        pre = json.loads(args.pre.read_text(encoding="utf-8"))
        unchanged = (
            pre.get("server_root") == current["server_root"]
            and pre.get("entries") == current["entries"]
            and pre.get("exact_set_sha256") == current["exact_set_sha256"]
        )
        report = {
            "schema": "ndp-root-toplevel-compare-v1",
            "rule_id": "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
            "pre": pre,
            "post": current,
            "ndp_root_toplevel_unchanged": unchanged,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return 0 if unchanged else 12
    except Exception as exc:
        print(f"root topology guard failed: {exc}", file=sys.stderr)
        return 13

if __name__ == "__main__":
    raise SystemExit(main())
'''


RUNNER = r'''#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in /*) ;; *) echo "server root must be absolute" >&2; exit 2;; esac
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2
package_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
runtime="$package_root/package_tools/qlinearadd_node0007_split_server_runtime_v25.py"
root_guard="$package_root/package_tools/qlinearadd_ndp_root_guard_v37.py"
install_name="$(python3 "$runtime" manifest-value --package-root "$package_root" --key install_name)" || exit 5
simulation_timeout="$(python3 "$runtime" manifest-value --package-root "$package_root" --key simulation_timeout)" || exit 5
case "$install_name" in
  *[!A-Za-z0-9._-]*|"") echo "unsafe manifest install_name" >&2; exit 5;;
esac
root_pre_json="$(python3 "$root_guard" snapshot --server-root "$server_root")" || exit 12
existing_parent="$server_root/install"
[ -d "$existing_parent" ] && [ ! -L "$existing_parent" ] || {
  echo "Declared pre-existing parent is absent or not a real directory: $existing_parent" >&2
  exit 12
}
result_root="/home/panqs/ndp/simresult"
return_zip="$result_root/${install_name}_return.zip"
return_sha="${return_zip}.sha256"
mkdir -p -- "$result_root" || exit 9
[ -d "$result_root" ] && [ -w "$result_root" ] || exit 9
resolved_result_root="$(cd "$result_root" && pwd -P)" || exit 9
[ "$resolved_result_root" = "$result_root" ] || exit 9
[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || {
  echo "Fixed result target conflict: $return_zip or $return_sha" >&2
  exit 10
}
state_root="$existing_parent/.qa.$$"
cfg_rel="i/$install_name"
cfg_root="$state_root/$cfg_rel"
run_root="$state_root/r"
evidence_root="$state_root/e"
for tool in python3 timeout make date tail grep; do command -v "$tool" >/dev/null 2>&1 || exit 3; done
python3 "$package_root/package_tools/package_path_budget_guard_v34.py" --manifest "$package_root/TEST_PACKAGE_MANIFEST.json" --server-root "$server_root" || exit 5
for fresh in "$state_root" "$cfg_root" "$run_root" "$evidence_root"; do
  [ ! -e "$fresh" ] || { echo "Fresh namespace required: $fresh" >&2; exit 4; }
done
for duplicate_root in "$server_root" "$package_root" "$state_root"; do
  [ ! -e "$duplicate_root/${install_name}_return.zip" ] || exit 11
  [ ! -e "$duplicate_root/${install_name}_return.zip.sha256" ] || exit 11
done
mkdir -p "$cfg_root" "$run_root/sim_results/return_observer" "$evidence_root"
printf '%s\n' "$root_pre_json" >"$evidence_root/ndp_root_toplevel_pre.json"
cat >"$evidence_root/fixed_result_preflight.json" <<EOF
{
  "schema": "qadd-fixed-result-preflight-v1",
  "result_root": "/home/panqs/ndp/simresult",
  "return_zip": "/home/panqs/ndp/simresult/${install_name}_return.zip",
  "return_sidecar": "/home/panqs/ndp/simresult/${install_name}_return.zip.sha256",
  "publication_state": "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING",
  "server_root_duplicate_absent": true,
  "package_root_duplicate_absent": true,
  "state_root_duplicate_absent": true
}
EOF
observer_log="$run_root/sim_results/return_observer/return_observer.log"
progress_log="$evidence_root/progress_samples.log"
decision_runtime="$package_root/package_tools/qlinearadd_node0007_fp32_ingress_canonical_v29.py"
canonical_decision="$evidence_root/CANONICAL_PROGRESS_DECISION.json"
feature_receipt="$evidence_root/fp32_ingress_feature_receipt.txt"
printf '# COMPILE_NOT_STARTED_OR_DRIVER_LOG_UNAVAILABLE\n' >"$run_root/sim_results/compile.log"
printf '# SIMULATION_NOT_STARTED_COMPILE_NOT_PASSED\n' >"$run_root/sim_results/sim.log"
printf 'SIMULATION_NOT_STARTED_COMPILE_NOT_PASSED\n' >"$evidence_root/actual_simulator_argv.txt"
printf '# OBSERVER_NOT_STARTED_COMPILE_NOT_PASSED\n' >"$observer_log"
cp "$package_root/diagnostics/progress_contract.json" "$evidence_root/progress_contract.json"
package_start_ns="$(date +%s%N)"
printf 'package_start_epoch_ns=%s\n' "$package_start_ns" >"$evidence_root/host_timing.txt"
python3 "$runtime" preflight --package-root "$package_root" >"$evidence_root/package_preflight.json" || exit 5
cp -a "$package_root/workload/runtime/." "$cfg_root/"
cp "$package_root/TEST_PACKAGE_MANIFEST.json" "$evidence_root/PACKAGE_MANIFEST.json"
python3 "$runtime" preflight-installed --package-root "$package_root" --cfg-root "$cfg_root" >"$evidence_root/installed_preflight.json" || exit 6
compile_status=125
simulation_status=125
signal_name=NONE
sim_pid=0
sampler_pid=0
finalized=0
canonical_decision_status=125
root_guard_status=125
sample_progress() {
  host_ns="$(date +%s%N)"
  observer_tail="OBSERVER_NOT_CREATED"
  if [ -s "$observer_log" ]; then
    observer_tail="$(tail -n 1 "$observer_log" | tr '\t' ' ')"
  fi
  printf '%s\t%s\n' "$host_ns" "$observer_tail" >>"$progress_log"
}
progress_sampler() {
  while kill -0 "$sim_pid" 2>/dev/null; do
    sample_progress
    sleep 60
  done
  sample_progress
}
finalize() {
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
  printf 'final_epoch_ns=%s\n' "$(date +%s%N)" >>"$evidence_root/host_timing.txt"
  printf 'signal=%s\ncompile_status=%s\nsimulation_status=%s\n' "$signal_name" "$compile_status" "$simulation_status" >"$evidence_root/signal_status.txt"
  if [ -s "$observer_log" ] && grep -q 'Native NDP return observer' "$observer_log"; then
    printf 'observer_enabled_and_returned=true\n' >"$evidence_root/observer_binding.txt"
  else
    printf 'observer_enabled_and_returned=false\n' >"$evidence_root/observer_binding.txt"
  fi
  feature_argv=false
  feature_time0=false
  feature_snapshot=false
  if [ -s "$evidence_root/actual_simulator_argv.txt" ] && grep -q '+RETURN_OBS_DEEP' "$evidence_root/actual_simulator_argv.txt" && grep -q '+QADD_FP32_INGRESS_OBSERVER' "$evidence_root/actual_simulator_argv.txt"; then feature_argv=true; fi
  if [ -s "$run_root/sim_results/sim.log" ] && grep -q 'QADD_FP32_INGRESS_OBSERVER_V19_TIME0' "$run_root/sim_results/sim.log"; then feature_time0=true; fi
  if [ -s "$observer_log" ] && grep -q '# QADD_FP32_INGRESS_OBSERVER_V19 ' "$observer_log"; then feature_snapshot=true; fi
  printf 'feature=QADD_SPLIT_C_FP32_INGRESS\nargv_enabled=%s\ntime0_marker=%s\nreturned_snapshot_marker=%s\n' "$feature_argv" "$feature_time0" "$feature_snapshot" >"$feature_receipt"
  printf '%s\n' "$compile_status" >"$evidence_root/compile_exit_status.txt"
  printf '%s\n' "$simulation_status" >"$evidence_root/simulation_exit_status.txt"
  python3 "$decision_runtime" --observer-log "$observer_log" --progress-contract "$evidence_root/progress_contract.json" --output "$canonical_decision"
  canonical_decision_status=$?
  printf '%s\n' "$canonical_decision_status" >"$evidence_root/canonical_decision_exit_status.txt"
  python3 "$runtime" analyze --package-root "$package_root" --cfg-root "$cfg_root" --evidence-root "$evidence_root" --run-root "$run_root" --compile-status "$compile_status" --simulation-status "$simulation_status"
  analysis_status=$?
  python3 "$root_guard" compare --server-root "$server_root" --pre "$evidence_root/ndp_root_toplevel_pre.json" --output "$evidence_root/ndp_root_toplevel_post.json"
  root_guard_status=$?
  python3 "$runtime" collect --server-root "$server_root" --install-name "$install_name" --package-root "$package_root" --cfg-root "$cfg_root" --evidence-root "$evidence_root" --run-root "$run_root"
  collection_status=$?
  final="$original"
  [ "$final" -ne 0 ] || [ "$canonical_decision_status" -eq 0 ] || final="$canonical_decision_status"
  [ "$final" -ne 0 ] || [ "$analysis_status" -eq 0 ] || final="$analysis_status"
  [ "$final" -ne 0 ] || [ "$root_guard_status" -eq 0 ] || final="$root_guard_status"
  [ "$final" -ne 0 ] || [ "$collection_status" -eq 0 ] || final="$collection_status"
  exit "$final"
}
trap 'finalize $?' EXIT
trap 'signal_name=HUP; simulation_status=125; finalize 125' HUP
trap 'signal_name=INT; simulation_status=125; finalize 125' INT
trap 'signal_name=TERM; simulation_status=125; finalize 125' TERM
observer_source="$package_root/tb_probe/native_return_observer.svh"
[ -r "$observer_source" ] || { echo "package observer source is not readable" >&2; exit 7; }
set +e
printf '%s\n' "make -C $server_root -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=$run_root VCS_EXTRA_OPTS=+incdir+$package_root/tb_probe +define+NATIVE_RETURN_OBSERVER_ENABLE" >"$evidence_root/actual_compile_argv.txt"
timeout --foreground --signal=TERM --kill-after=30s 2h make -C "$server_root" -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$run_root" VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe +define+NATIVE_RETURN_OBSERVER_ENABLE" >"$run_root/sim_results/compile_driver.log" 2>&1
compile_status=$?
[ "$compile_status" -eq 0 ] || exit "$compile_status"
simv="$run_root/sim_results/simv"
sim_start_ns="$(date +%s%N)"
printf 'sim_start_epoch_ns=%s\n' "$sim_start_ns" >>"$evidence_root/host_timing.txt"
sim_args=(
  -l "$run_root/sim_results/sim.log"
  +vcs+lic+wait
  "+SCA_CFG=$cfg_rel/sca_cfg.json"
  "+SCA_CFG_D=$cfg_rel/sca_cfg_D.json"
  +RETURN_OBSERVER
  +RETURN_OBS_SLICE=0
  +RETURN_OBS_STALL_CYCLES=1048576
  +RETURN_OBS_HEARTBEAT_CYCLES=1048576
  +QADD_FP32_INGRESS_OBSERVER
  +RETURN_OBS_DEEP
  +RETURN_OBS_DEEP_LIMIT=64
  "+RETURN_OBS_FILE=$observer_log"
)
printf 'timeout --foreground --signal=TERM --kill-after=30s %q %q' "$simulation_timeout" "$simv" >"$evidence_root/actual_simulator_argv.txt"
printf ' %q' "${sim_args[@]}" >>"$evidence_root/actual_simulator_argv.txt"
printf '\n' >>"$evidence_root/actual_simulator_argv.txt"
cd "$state_root"
timeout --foreground --signal=TERM --kill-after=30s "$simulation_timeout" "$simv" "${sim_args[@]}" &
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
'''


COLLECTOR = r'''def collect(
    server_root: Path,
    install_name: str,
    package_root: Path,
    evidence_root: Path,
    run_root: Path,
    cfg_root: Path,
) -> dict[str, Any]:
    fixed = Path("/home/panqs/ndp/simresult")
    fixed.mkdir(parents=True, exist_ok=True)
    if not fixed.is_dir():
        raise RuntimeGateError("fixed result root is not a directory")
    final_zip = fixed / f"{install_name}_return.zip"
    final_sha = Path(str(final_zip) + ".sha256")
    if final_zip.exists() or final_sha.exists():
        raise RuntimeGateError("fixed result target conflict")
    stage_root = fixed / f".{install_name}.publish.{os.getpid()}"
    if stage_root.exists():
        raise RuntimeGateError("publication staging conflict")
    destination = stage_root / f"{install_name}_return"
    staged_zip = stage_root / f"{install_name}_return.zip"
    staged_sha = Path(str(staged_zip) + ".sha256")
    destination.mkdir(parents=True, exist_ok=False)
    roots = {"evidence": evidence_root, "run": run_root, "cfg": cfg_root}
    manifest = load_json(package_root / MANIFEST)
    collected: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in manifest["return_allowlist"]:
        source = safe_child(roots[str(item["source_root"])], str(item["source_path"]))
        target = safe_child(destination, str(item["target_path"]))
        if not source.is_file():
            if item["required"]:
                missing.append(str(item["target_path"]))
            continue
        if source.stat().st_size > int(item["max_bytes"]):
            raise RuntimeGateError(f"return budget exceeded: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        collected.append(
            {
                "path": str(item["target_path"]),
                "size_bytes": target.stat().st_size,
                "sha256": sha256(target),
            }
        )
    duplicate_paths = [
        server_root / final_zip.name,
        server_root / final_sha.name,
        package_root / final_zip.name,
        package_root / final_sha.name,
        cfg_root / final_zip.name,
        cfg_root / final_sha.name,
        run_root / final_zip.name,
        run_root / final_sha.name,
    ]
    duplicate_absent = all(not path.exists() for path in duplicate_paths)
    if not duplicate_absent:
        raise RuntimeGateError("same-name return duplicate exists outside fixed result root")
    preflight = load_json(evidence_root / "fixed_result_preflight.json")
    if (
        preflight.get("result_root") != str(fixed)
        or preflight.get("return_zip") != str(final_zip)
        or preflight.get("return_sidecar") != str(final_sha)
    ):
        raise RuntimeGateError("fixed result preflight differs")
    root_post = load_json(evidence_root / "ndp_root_toplevel_post.json")
    if root_post.get("ndp_root_toplevel_unchanged") is not True:
        raise RuntimeGateError("NDP root direct-child exact-set changed")
    publication = {
        "result_root": str(fixed),
        "return_zip": str(final_zip),
        "return_sidecar": str(final_sha),
        "publication_state": "STAGING_VALIDATED_BEFORE_ATOMIC_RENAME",
        "target_sha256_source": "adjacent sidecar after archive finalization",
        "duplicate_absent": duplicate_absent,
        "ndp_root_toplevel_unchanged": True,
        "ndp_root_pre_sha256": root_post["pre"]["exact_set_sha256"],
        "ndp_root_post_sha256": root_post["post"]["exact_set_sha256"],
    }
    return_manifest = {
        "schema": "qlinearadd-node0007-split-return-manifest-v37",
        "status": "complete" if not missing else "incomplete",
        "install_name": install_name,
        "allowlist_only": True,
        "required_missing": missing,
        "files": sorted(collected, key=lambda item: item["path"]),
        "fixed_result_publication": publication,
    }
    write_json(destination / "RETURN_MANIFEST.json", return_manifest)
    observed = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file() and path.name != "RETURN_MANIFEST.json"
    }
    if observed != {str(item["path"]) for item in collected}:
        raise RuntimeGateError("return exact-set differs")
    with zipfile.ZipFile(
        staged_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in destination.rglob("*") if item.is_file()):
            relative = f"{install_name}_return/{path.relative_to(destination).as_posix()}"
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(staged_zip) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeGateError(f"staged return CRC failure: {bad}")
    digest = sha256(staged_zip)
    staged_sha.write_text(
        f"{digest}  {final_zip.name}\n", encoding="ascii", newline="\n"
    )
    tokens = staged_sha.read_text(encoding="ascii").split()
    if tokens != [digest, final_zip.name]:
        raise RuntimeGateError("staged sidecar differs")
    if final_zip.exists() or final_sha.exists():
        raise RuntimeGateError("fixed result target conflict before publish")
    os.replace(staged_zip, final_zip)
    os.replace(staged_sha, final_sha)
    if sha256(final_zip) != digest:
        raise RuntimeGateError("published return SHA differs")
    if final_sha.read_text(encoding="ascii").split() != [digest, final_zip.name]:
        raise RuntimeGateError("published sidecar differs")
    shutil.rmtree(destination)
    stage_root.rmdir()
    return {
        "zip": str(final_zip),
        "sidecar": str(final_sha),
        "sha256": digest,
        "publication_state": "ATOMIC_PUBLISHED_VERIFIED",
        "duplicate_absent": True,
        "ndp_root_toplevel_unchanged": True,
        "required_missing": missing,
    }
'''


def patch_runtime(package: Path) -> None:
    path = (
        package
        / "package_tools/qlinearadd_node0007_split_server_runtime_v25.py"
    )
    text = path.read_text(encoding="utf-8")
    if "import os\n" not in text:
        text = text.replace("import json\n", "import json\nimport os\n", 1)
    begin = text.index("def collect(\n")
    end = text.index("\ndef main() -> int:", begin)
    text = text[:begin] + COLLECTOR + text[end:]
    namespace_anchors = {
        """prefix = f"install/cfg_pkg/{manifest['install_name']}/\"""":
        """prefix = f"i/{manifest['install_name']}/\"""",
        """cfg_rel = f"install/cfg_pkg/{manifest['install_name']}\"""":
        """cfg_rel = f"i/{manifest['install_name']}\"""",
    }
    for old, new in namespace_anchors.items():
        if text.count(old) != 1:
            raise ValueError(f"runtime namespace anchor differs: {old}")
        text = text.replace(old, new)
    path.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, TARGET_NAME),
                encoding="utf-8",
                newline="\n",
            )
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        path = package / "workload/runtime" / name
        text = path.read_text(encoding="utf-8")
        old = f"install/cfg_pkg/{TARGET_NAME}"
        if old not in text:
            raise ValueError(f"{name} identity path anchor missing")
        path.write_text(
            text.replace(old, f"i/{TARGET_NAME}"),
            encoding="utf-8",
            newline="\n",
        )


def update_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["install_name"] = TARGET_NAME
    manifest["schema"] = "qlinearadd-node0007-rootclean-runner-package-v37"
    manifest["claim"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_v37_rootclean_server_package.py"
    )
    manifest["provenance"]["successor_reason"] = (
        "v36 formal return was externally interrupted before the target stage; "
        "current root-top-level rule holds the old runner because it creates "
        "root-level run/evidence/return entries"
    )
    manifest["source_assets"]["v36_frozen_source_zip"] = {
        "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
        "bytes": SOURCE_ZIP.stat().st_size,
        "sha256": SOURCE_SHA256,
        "immutable": True,
        "runtime_identity": "PACKAGE_HELD_NDP_ROOT_TOPLEVEL_GATE_REQUIRED",
    }
    manifest["source_assets"]["v36_return_analysis"] = {
        "path": RETURN_REPORT.relative_to(ROOT).as_posix(),
        "bytes": RETURN_REPORT.stat().st_size,
        "sha256": sha256(RETURN_REPORT),
    }
    manifest["runner_only_successor"] = {
        "source_identity": SOURCE_NAME,
        "target_identity": TARGET_NAME,
        "config_semantics_changed": False,
        "workload_changed": False,
        "numeric_changed": False,
        "golden_changed": False,
        "observer_changed": False,
        "timeout_changed": False,
        "functional_rtl_modified": False,
        "package_infrastructure_changed": [
            "runner paths",
            "fixed-result atomic collector",
            "NDP root direct-child exact-set guard",
            "identity and receipts",
            "removed forbidden packaged __pycache__/pyc",
        ],
    }
    manifest["ndp_root_toplevel_contract"] = {
        "rule_id": "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
        "server_root_argument": "single absolute NDP_copy0x root",
        "pre_existing_parent": "install",
        "pre_existing_parent_required": True,
        "state_namespace": "install/.qa.<pid>",
        "root_direct_child_writes": [],
        "root_internal_writes": [
            "install/.qa.<pid>/i/<install_name>",
            "install/.qa.<pid>/r",
            "install/.qa.<pid>/e",
        ],
        "pre_post_names_and_types_exact_set": True,
        "return_result_root": "/home/panqs/ndp/simresult",
    }
    manifest["fixed_result_publication"] = {
        "rule_id": "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
        "server_runtime_only": True,
        "result_root": "/home/panqs/ndp/simresult",
        "return_zip": (
            f"/home/panqs/ndp/simresult/{TARGET_NAME}_return.zip"
        ),
        "return_sidecar": (
            f"/home/panqs/ndp/simresult/{TARGET_NAME}_return.zip.sha256"
        ),
        "atomic_hidden_staging": True,
        "same_name_duplicates_outside_result_root_forbidden": True,
    }
    extra_allowlist = [
        {
            "max_bytes": 1048576,
            "required": True,
            "source_path": "ndp_root_toplevel_pre.json",
            "source_root": "evidence",
            "target_path": "evidence/ndp_root_toplevel_pre.json",
        },
        {
            "max_bytes": 1048576,
            "required": True,
            "source_path": "ndp_root_toplevel_post.json",
            "source_root": "evidence",
            "target_path": "evidence/ndp_root_toplevel_post.json",
        },
        {
            "max_bytes": 1048576,
            "required": True,
            "source_path": "fixed_result_preflight.json",
            "source_root": "evidence",
            "target_path": "evidence/fixed_result_preflight.json",
        },
    ]
    existing_targets = {
        item["target_path"] for item in manifest["return_allowlist"]
    }
    manifest["return_allowlist"].extend(
        item for item in extra_allowlist if item["target_path"] not in existing_targets
    )
    aliases = {
        "agent": "agent",
        "index": "index",
        "generation_index": "index",
        "server": "server",
        "server_package": "server",
        "common": "common",
        "common_operator": "common",
        "hardware": "hardware",
        "hardware_fields": "hardware",
        "qadd": "qadd",
        "qlinearadd": "qadd",
        "tail": "tail",
        "exact_tail": "tail",
    }
    receipts = manifest["rule_receipts"]
    for alias, canonical in aliases.items():
        record = dict(receipts.get(alias, {}))
        record.update(
            {
                "path": RULES[canonical].relative_to(ROOT).as_posix(),
                "sha256": sha256(RULES[canonical]),
                "current_match": True,
            }
        )
        receipts[alias] = record
    server_ids = set(receipts["server"].get("applicable_rule_ids", []))
    server_ids.update(
        {
            "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
            "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
            "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
            "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
        }
    )
    receipts["server"]["applicable_rule_ids"] = sorted(server_ids)
    receipts["server_package"]["applicable_rule_ids"] = sorted(server_ids)
    manifest["release_gate_matrix"] = {
        "schema": "server-package-release-gate-matrix-v1",
        "single_machine_record": True,
        "gates": {
            "package_bootstrap_path_runtime_D": {
                "applicability": "required",
                "changed_surface": ["identity", "runner paths", "pycache removal"],
            },
            "runner_compile_finalizer": {
                "applicability": "required",
                "changed_surface": [
                    "pre-existing parent",
                    "root exact-set guard",
                    "fixed atomic result",
                ],
            },
            "package_local_HDL": {
                "applicability": "receipt_reuse",
                "reason": "all package-local HDL byte-equal to v36",
            },
            "materialized_config": {
                "applicability": "receipt_reuse",
                "reason": (
                    "semantic config/mapping/bitstream/execplan unchanged; "
                    "only package namespace paths changed"
                ),
            },
            "observer_canonical": {
                "applicability": "receipt_reuse",
                "reason": "observer/parser/predicate bytes unchanged from v36",
            },
            "return_result": {
                "applicability": "required",
                "changed_surface": [
                    "atomic publication",
                    "root pre/post receipts",
                    "return allowlist",
                ],
            },
            "numeric_W3_golden": {
                "applicability": "record_only",
                "reason": "byte-equal frozen semantic assets",
            },
        },
    }
    manifest["final_zip_rule_self_audit"] = {
        "required": True,
        "status": "PENDING_POST_BUILD_DIRECT_FINAL_ZIP_AUDIT",
    }
    projections = []
    for old in manifest["path_length_budget"]["projected_relative_paths"]:
        value = old.replace(SOURCE_NAME, TARGET_NAME)
        value = value.replace(
            f"install/cfg_pkg/{TARGET_NAME}",
            f"install/.qa.123456/i/{TARGET_NAME}",
        )
        value = value.replace(
            f"run_{TARGET_NAME}", "install/.qa.123456/r"
        )
        value = value.replace(
            f"evidence_{TARGET_NAME}", "install/.qa.123456/e"
        )
        if value.startswith(f"{TARGET_NAME}_return"):
            value = f"../simresult/{value}"
        projections.append(value)
    projections.extend(
        [
            "install/.qa.123456/e/ndp_root_toplevel_pre.json",
            "install/.qa.123456/e/ndp_root_toplevel_post.json",
            "install/.qa.123456/e/fixed_result_preflight.json",
        ]
    )
    manifest["path_length_budget"]["projected_relative_paths"] = sorted(
        set(projections)
    )
    manifest["path_length_budget"]["max_projected_relative_path_chars"] = max(
        map(len, manifest["path_length_budget"]["projected_relative_paths"])
    )
    manifest["path_length_budget"]["max_projected_absolute_path_chars"] = (
        manifest["path_length_budget"]["declared_target_root_max_chars"]
        + 1
        + manifest["path_length_budget"]["max_projected_relative_path_chars"]
    )
    manifest["path_length_budget"]["long_component_exceptions"] = [
        item
        for item in manifest["path_length_budget"]["long_component_exceptions"]
        if not item["component"].endswith(".pyc")
    ]
    manifest["files"] = file_records(package, exclude_manifest=True)
    manifest["path_length_budget"]["max_zip_member_chars"] = max(
        len(f"{TARGET_NAME}/{path}")
        for path in [*manifest["files"], "TEST_PACKAGE_MANIFEST.json"]
    )
    manifest["path_length_budget"]["max_inner_suffix_chars"] = max(
        map(len, manifest["files"])
    )
    manifest["path_length_budget"]["max_inner_depth"] = max(
        path.count("/") + 1 for path in manifest["files"]
    )
    write_json(path, manifest)


def materialize(parent: Path) -> Path:
    package = safe_extract(SOURCE_ZIP, parent)
    pycache = package / "package_tools/__pycache__"
    if pycache.exists():
        shutil.rmtree(pycache)
    for pyc in package.rglob("*.pyc"):
        pyc.unlink()
    replace_identity(package)
    (package / "PREPARE_AND_RUN.sh").write_text(
        RUNNER, encoding="utf-8", newline="\n"
    )
    (package / "package_tools/qlinearadd_ndp_root_guard_v37.py").write_text(
        ROOT_GUARD, encoding="utf-8", newline="\n"
    )
    patch_runtime(package)
    readme = package / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\nV37 is a runner-only current-rule replacement for held v36. "
        "All package-owned runtime state is placed below the pre-existing "
        "NDP-root `install/` directory. The direct-child name/type exact-set "
        "is captured before writes and compared in the shared finalizer. "
        "The only final return is atomically published on the server at "
        f"`/home/panqs/ndp/simresult/{TARGET_NAME}_return.zip`. "
        "Config, workload, numeric/golden assets, observer, timeout and "
        "functional RTL are frozen from v36.\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package)
    return package


def main() -> int:
    if not SOURCE_ZIP.is_file() or sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise ValueError("frozen v36 source ZIP identity differs")
    if not RETURN_REPORT.is_file():
        raise FileNotFoundError("v36 return analysis report missing")
    if OUT_ROOT.exists():
        raise ValueError("fresh v37 output path already exists")
    OUT_ROOT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="qadd-v37-a-") as first, tempfile.TemporaryDirectory(
        prefix="qadd-v37-b-"
    ) as second:
        package_a = materialize(Path(first))
        package_b = materialize(Path(second))
        zip_a = Path(first) / f"{TARGET_NAME}.zip"
        zip_b = Path(second) / f"{TARGET_NAME}.zip"
        deterministic_zip(package_a, zip_a)
        deterministic_zip(package_b, zip_b)
        if zip_a.read_bytes() != zip_b.read_bytes():
            raise ValueError("deterministic double build differs")
        OUT_ROOT.mkdir()
        shutil.copy2(zip_a, OUT_ZIP)
    OUT_SIDECAR.write_text(
        f"{sha256(OUT_ZIP)}  {OUT_ZIP.name}\n",
        encoding="ascii",
        newline="\n",
    )
    receipt = {
        "schema": "qlinearadd-node0007-v37-rootclean-build-v1",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "source_zip": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": sha256(SOURCE_ZIP),
        },
        "target_zip": {
            "path": OUT_ZIP.relative_to(ROOT).as_posix(),
            "bytes": OUT_ZIP.stat().st_size,
            "sha256": sha256(OUT_ZIP),
        },
        "sidecar": {
            "path": OUT_SIDECAR.relative_to(ROOT).as_posix(),
            "bytes": OUT_SIDECAR.stat().st_size,
            "sha256": sha256(OUT_SIDECAR),
        },
        "deterministic_double_build": True,
        "semantic_freeze": {
            "config": True,
            "workload": True,
            "numeric": True,
            "golden": True,
            "observer": True,
            "simulation_timeout": "8h",
            "functional_rtl_modified": False,
        },
        "changed_surface": [
            "package identity",
            "runner-owned paths",
            "root exact-set guard",
            "fixed-result atomic collector",
            "manifest/README/receipts",
            "forbidden pycache removal",
        ],
        "server_action": False,
    }
    write_json(OUT_ROOT / "build_receipt.json", receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
