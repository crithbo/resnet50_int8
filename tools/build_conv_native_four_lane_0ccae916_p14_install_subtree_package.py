#!/usr/bin/env python3
"""Build the native-four-lane p14 install-subtree runtime-layout successor."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p13_pathfix"
PACKAGE_ID = "r5_n4_0cc_p14_install"
WORKLOAD_INSTALL_NAME = "r5_n4_0cc_p11f_pubord"
ATTEMPT = "a0"
ATTEMPT_MAX_CHARS = 2
SOURCE_SHA256 = (
    "a2c9e849bf57bc96d05ceb50c22351ae512470343bf1c96928d5b57962c8fe01"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "superseded/conv_native_four_lane"
    / SOURCE_ID
    / f"{SOURCE_ID}.zip"
)
OUTPUT_ROOT = (
    ROOT / "outputs/conv_native_four_lane_0ccae916_p14_install_subtree"
)
SHARED_LAYOUT_HELPER = ROOT / "tools/server_package_runtime_layout.py"
SHARED_LAYOUT_HELPER_SHA256 = (
    "82723ecc427c3e42cfc327eff87cae7d5d935b9f6dccb220e78bfa573d11a9ae"
)
SERVER_ROOT_BUDGET_CHARS = 96
ABSOLUTE_PATH_LIMIT_CHARS = 240
RUNTIME_PREFIX = f"install/cfg_pkg/{WORKLOAD_INSTALL_NAME}"
RUN_PREFIX = f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}"


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
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
        if path.name != "package_manifest.json"
    }


def extract_exact_source(target: Path) -> Path:
    if not SOURCE_ZIP.is_file() or sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact held p13 source ZIP differs or is unavailable")
    package = target / PACKAGE_ID
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("held p13 source ZIP CRC differs")
        names = [item.filename for item in archive.infolist()]
        if len(names) != len(set(names)):
            raise BuildError("held p13 source ZIP has duplicate members")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or pure.parts[0] != SOURCE_ID
            ):
                raise BuildError(f"unsafe held p13 member: {info.filename}")
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:])
            output = package.joinpath(*relative.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.read(info))
    return package


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"{label} anchor count differs: {text.count(old)}")
    return text.replace(old, new)


def patch_sca_d(package: Path) -> list[str]:
    path = package / "workload/runtime/runs/c0/sca_cfg_D.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    old_prefix = f"{RUNTIME_PREFIX}/runs/c0/install/"
    new_prefix = f"{RUN_PREFIX}/c0/d/"
    changed: list[str] = []
    for key, record in value.items():
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise BuildError(f"unexpected SCA_D record: {key}")
        old = record["path"]
        if not old.startswith(old_prefix):
            raise BuildError(f"SCA_D source prefix differs: {old}")
        record["path"] = new_prefix + old[len(old_prefix) :]
        changed.append(record["path"])
    if len(changed) != 28 or len(changed) != len(set(changed)):
        raise BuildError("SCA_D output path count differs")
    write_json(path, value)
    return sorted(changed)


def patch_runtime(package: Path) -> None:
    path = (
        package
        / "package_tools/node0004_assumed_hardware_server_runtime.py"
    )
    text = path.read_text(encoding="utf-8")
    consumer_start = text.index(
        '    marker = f"install/cfg_pkg/{INSTALL_NAME}/"'
    )
    consumer_end = text.index(
        '    return {\n'
        '        "schema": "conv-native-four-lane-0ccae916-c0diag-preflight-v1",',
        consumer_start,
    )
    consumer_replacement = f'''    input_marker = f"install/cfg_pkg/{{INSTALL_NAME}}/"
    output_marker = "install/codex_runs/{PACKAGE_ID}/{ATTEMPT}/c0/d/"
    for name, allow_missing in (
        ("sca_cfg.json", False),
        ("sca_cfg_D.json", True),
    ):
        value = load_json(runtime_root / f"runs/c0/{{name}}")
        for record in value.values():
            if not isinstance(record, dict) or "path" not in record:
                continue
            consumer = record["path"]
            if not isinstance(consumer, str):
                raise RuntimeErrorContract(
                    f"{{name}} consumer identity differs"
                )
            if allow_missing:
                if not consumer.startswith(output_marker):
                    raise RuntimeErrorContract(
                        f"{{name}} output consumer identity differs"
                    )
            else:
                if not consumer.startswith(input_marker):
                    raise RuntimeErrorContract(
                        f"{{name}} input consumer identity differs"
                    )
                target = _safe_child(
                    runtime_root, consumer[len(input_marker) :]
                )
                if not target.is_file():
                    raise RuntimeErrorContract(
                        f"{{name}} direct consumer is missing"
                    )
'''
    text = (
        text[:consumer_start]
        + consumer_replacement
        + text[consumer_end:]
    )
    budget_start = text.index(
        "def path_budget(package_root: Path, server_root: Path)"
    )
    budget_end = text.index("\n\ndef collect_compile_identity", budget_start)
    budget_replacement = '''def path_budget(package_root: Path, server_root: Path) -> dict[str, Any]:
    manifest = load_json(package_root / "package_manifest.json")
    budget = manifest.get("path_length_budget", {})
    relative_chars = budget.get("max_projected_relative_path_chars")
    declared_chars = budget.get("longest_projected_relative_path_chars")
    root_budget = budget.get("declared_target_root_max_chars")
    declared_absolute = budget.get("max_projected_absolute_path_chars")
    limit = budget.get("max_projected_absolute_path_limit_chars")
    longest = budget.get("longest_projected_relative_path")
    if (
        not isinstance(relative_chars, int)
        or not isinstance(declared_chars, int)
        or not isinstance(root_budget, int)
        or not isinstance(declared_absolute, int)
        or not isinstance(limit, int)
        or not isinstance(longest, str)
        or len(longest) != relative_chars
        or declared_chars != relative_chars
        or declared_absolute != root_budget + 1 + relative_chars
    ):
        raise RuntimeErrorContract("path budget is malformed")
    server = server_root.resolve()
    projected = len(str(server)) + 1 + relative_chars
    receipt = {
        "schema": "conv-native-four-lane-0ccae916-c0diag-path-budget-v1",
        "valid": projected <= limit,
        "server_root": str(server),
        "server_root_chars": len(str(server)),
        "declared_target_root_max_chars": root_budget,
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": declared_chars,
        "max_projected_relative_path_chars": relative_chars,
        "declared_max_projected_absolute_path_chars": declared_absolute,
        "actual_projected_absolute_path_chars": projected,
        "max_projected_absolute_path_limit_chars": limit,
        "required_shortening_chars": max(0, projected - limit),
    }
    if not receipt["valid"]:
        raise RuntimeErrorContract(
            f"server root exceeds path budget: {projected}>{limit}"
        )
    return receipt
'''
    text = (
        text[:budget_start]
        + budget_replacement
        + text[budget_end:]
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def bootstrap_publisher_code() -> str:
    return r'''

def publish_bootstrap_partial(
    *,
    package_root: Path,
    exit_code: int,
    signal_name: str,
    stage: str,
    server_root: str,
) -> dict[str, Any]:
    """Publish a bounded partial return before install layout exists."""
    manifest = load_json(package_root / "package_manifest.json")
    package_identity = manifest.get("package_identity")
    if package_identity != "r5_n4_0cc_p14_install":
        raise PublishError("package release identity differs")
    result_root = RESULT_ROOT
    result_root.mkdir(parents=True, exist_ok=True)
    if result_root.resolve() != result_root or not os.access(
        result_root, os.W_OK | os.X_OK
    ):
        raise PublishError("fixed result root is not exact/writable")
    final_zip = result_root / f"{package_identity}_return.zip"
    final_sidecar = Path(str(final_zip) + ".sha256")
    if final_zip.exists() or final_sidecar.exists():
        raise PublishError("fixed result target conflict")
    stage_root = result_root / f".{package_identity}.bootstrap.{os.getpid()}"
    if stage_root.exists():
        raise PublishError("fixed result staging conflict")
    return_dir = stage_root / f"{package_identity}_return"
    staged_zip = stage_root / final_zip.name
    staged_sidecar = stage_root / final_sidecar.name
    evidence_dir = return_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=False)
    status = {
        "schema": "conv-native-four-lane-package-local-preflight-status-v1",
        "preflight_stage": stage,
        "runner_exit_status": exit_code,
        "signal_status": signal_name,
        "server_root": server_root,
        "runtime_layout_created": False,
        "production_compile_started": False,
        "dut_simulation_started": False,
        "partial": True,
    }
    write_json(evidence_dir / "package_local_preflight_status.json", status)
    records = [
        {
            "path": "evidence/package_local_preflight_status.json",
            "size_bytes": (
                evidence_dir / "package_local_preflight_status.json"
            ).stat().st_size,
            "sha256": sha256(
                evidence_dir / "package_local_preflight_status.json"
            ),
            "required": True,
            "max_bytes": 2097152,
        }
    ]
    publication = {
        "result_root": str(result_root),
        "return_zip": str(final_zip),
        "return_sidecar": str(final_sidecar),
        "publication_state": "BOOTSTRAP_PARTIAL_STAGING",
        "duplicate_absent": True,
    }
    write_json(
        return_dir / "RETURN_MANIFEST.json",
        {
            "schema": (
                "conv-native-four-lane-install-layout-partial-"
                "return-manifest-v1"
            ),
            "package_identity": package_identity,
            "source_package_manifest_sha256": sha256(
                package_root / "package_manifest.json"
            ),
            "partial": True,
            "preflight_stage": stage,
            "fixed_result_publication": publication,
            "records_excluding_this_manifest": records,
        },
    )
    write_json(
        return_dir / "RETURN_ALLOWLIST.json",
        {
            "schema": (
                "conv-native-four-lane-install-layout-partial-"
                "return-allowlist-v1"
            ),
            "package_identity": package_identity,
            "partial": True,
            "records": records,
        },
    )
    deterministic_zip(return_dir, staged_zip)
    value = sha256(staged_zip)
    staged_sidecar.write_text(
        f"{value}  {final_zip.name}\n", encoding="ascii", newline="\n"
    )
    if final_zip.exists() or final_sidecar.exists():
        raise PublishError("fixed result target conflict before publish")
    os.replace(staged_zip, final_zip)
    os.replace(staged_sidecar, final_sidecar)
    if sha256(final_zip) != value:
        raise PublishError("published return SHA differs")
    if final_sidecar.read_text(encoding="ascii").split() != [
        value,
        final_zip.name,
    ]:
        raise PublishError("published return sidecar differs")
    shutil.rmtree(return_dir)
    stage_root.rmdir()
    return {
        "schema": "fixed-simresult-bootstrap-partial-publication-v1",
        "return_zip": str(final_zip),
        "return_sidecar": str(final_sidecar),
        "return_zip_bytes": final_zip.stat().st_size,
        "return_zip_sha256": value,
        "publication_state": "ATOMIC_PUBLISHED_VERIFIED",
        "partial": True,
        "duplicate_absent": True,
    }
'''


def patch_publisher(package: Path) -> None:
    path = package / "package_tools/fixed_simresult_publisher.py"
    text = path.read_text(encoding="utf-8")
    if text.count(SOURCE_ID) != 1:
        raise BuildError("publisher p13 identity anchor differs")
    text = text.replace(SOURCE_ID, PACKAGE_ID)
    marker = "\ndef main() -> int:\n"
    if text.count(marker) != 1:
        raise BuildError("publisher main anchor differs")
    text = text.replace(marker, bootstrap_publisher_code() + marker)
    old_main = '''def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    result = collect(
        package_root=args.package_root.resolve(),
        evidence_root=args.evidence_root.resolve(),
        run_root=args.run_root.resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0
'''
    new_main = '''def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--bootstrap-partial", action="store_true")
    parser.add_argument("--exit-code", type=int, default=125)
    parser.add_argument("--signal-name", default="NONE")
    parser.add_argument("--stage", default="EARLY_PREFLIGHT")
    parser.add_argument("--server-root", default="")
    args = parser.parse_args()
    if args.bootstrap_partial:
        result = publish_bootstrap_partial(
            package_root=args.package_root.resolve(),
            exit_code=args.exit_code,
            signal_name=args.signal_name,
            stage=args.stage,
            server_root=args.server_root,
        )
    else:
        if args.evidence_root is None or args.run_root is None:
            raise PublishError("normal collection roots are required")
        result = collect(
            package_root=args.package_root.resolve(),
            evidence_root=args.evidence_root.resolve(),
            run_root=args.run_root.resolve(),
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0
'''
    text = replace_once(text, old_main, new_main, "publisher main")
    path.write_text(text, encoding="utf-8", newline="\n")


def runner_text() -> str:
    return f'''#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd -P)"
package_identity="{PACKAGE_ID}"
install_name="{WORKLOAD_INSTALL_NAME}"
attempt="{ATTEMPT}"
layout_helper="$package_root/package_tools/server_package_runtime_layout.py"
runtime="$package_root/package_tools/node0004_assumed_hardware_server_runtime.py"
observer_guard="$package_root/package_tools/node0004_package_observer_guard.py"
trigger_finalizer="$package_root/package_tools/node0004_triggered_causal_finalizer.py"
public_finalizer="$package_root/package_tools/node0004_public_order_finalizer.py"
publisher="$package_root/package_tools/fixed_simresult_publisher.py"
root_gate="$package_root/package_tools/ndp_root_toplevel_exact_set_gate.py"
result_root="/home/panqs/ndp/simresult"
return_zip="/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip"
return_sha="/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip.sha256"
launch_cwd="$(pwd -P)"
server_root="${{1-}}"
work_root=""
cfg_root=""
run_root=""
evidence_root=""
compile_root=""
compile_status=125
run_status=125
signal_status=NONE
finalized=0
sim_pid=
progress_pid=
root_gate_status=125
path_budget_status=125
package_preflight_status=125
install_preflight_status=125
observer_preflight_status=125
preflight_stage=BOOTSTRAP_ARMED
finalize() {{
  original="$1"; [ "$finalized" -eq 0 ] || exit "$original"; finalized=1
  trap - EXIT INT TERM HUP
  set +e
  [ -z "$progress_pid" ] || kill "$progress_pid" 2>/dev/null
  [ -z "$progress_pid" ] || wait "$progress_pid" 2>/dev/null
  if [ -z "$evidence_root" ] || [ ! -d "$evidence_root" ]; then
    python3 "$publisher" --bootstrap-partial --package-root "$package_root" --exit-code "$original" --signal-name "$signal_status" --stage "$preflight_stage" --server-root "$server_root"
    publication=$?
    [ "$original" -ne 0 ] || original="$publication"
    exit "$original"
  fi
  post_snapshot_json="$(python3 "$root_gate" snapshot --server-root "$server_root")"
  post_capture=$?
  [ "$post_capture" -ne 0 ] || printf '%s\\n' "$post_snapshot_json" > "$evidence_root/ndp_root_toplevel_post.json"
  [ "$post_capture" -eq 0 ] || printf '%s\\n' '{{"schema":"ndp-root-toplevel-post-capture-error"}}' > "$evidence_root/ndp_root_toplevel_post.json"
  python3 "$root_gate" compare --pre "$evidence_root/ndp_root_toplevel_pre.json" --post "$evidence_root/ndp_root_toplevel_post.json" --manifest "$package_root/package_manifest.json" --output "$evidence_root/ndp_root_toplevel_gate.json" >/dev/null 2>&1
  root_gate_status=$?
  printf '%s\\n' "$compile_status" > "$evidence_root/compile_exit_status.txt"
  printf '%s\\n' "$run_status" > "$evidence_root/run_exit_status.txt"
  printf '%s\\n' "$signal_status" > "$evidence_root/signal_status.txt"
  [ "$package_preflight_status" -eq 0 ] || printf '%s\\n' '{{"schema":"package-preflight-failed-v1","valid":false,"status":"FAILED_BEFORE_COMPILE"}}' > "$evidence_root/package_preflight.json"
  [ "$install_preflight_status" -eq 0 ] || printf '%s\\n' '{{"schema":"install-preflight-not-complete-v1","valid":false,"status":"NOT_COMPLETE_BEFORE_COMPILE"}}' > "$evidence_root/install_preflight.json"
  [ "$observer_preflight_status" -eq 0 ] || printf '%s\\n' '{{"schema":"observer-precompile-not-complete-v1","valid":false,"status":"NOT_COMPLETE_BEFORE_COMPILE"}}' > "$evidence_root/observer_precompile.json"
  cat > "$evidence_root/package_local_preflight_status.json" <<EOF
{{
  "schema": "conv-native-four-lane-package-local-preflight-status-v1",
  "preflight_stage": "$preflight_stage",
  "path_budget_exit_status": $path_budget_status,
  "package_preflight_exit_status": $package_preflight_status,
  "install_preflight_exit_status": $install_preflight_status,
  "observer_preflight_exit_status": $observer_preflight_status,
  "production_compile_started": $([ "$compile_status" -eq 125 ] && printf false || printf true),
  "dut_simulation_started": $([ "$run_status" -eq 125 ] && printf false || printf true),
  "partial": $([ "$original" -eq 0 ] && printf false || printf true)
}}
EOF
  python3 "$trigger_finalizer" --observer-log "$run_root/c0/triggered_observer.log" --sim-log "$run_root/c0/sim.log" --compile-status "$evidence_root/compile_exit_status.txt" --run-status "$evidence_root/run_exit_status.txt" --signal-status "$evidence_root/signal_status.txt" --output "$evidence_root/triggered_causal_summary.json" >/dev/null 2>&1 || true
  python3 "$public_finalizer" --observer-log "$run_root/c0/public_order_observer.log" --compile-status "$evidence_root/compile_exit_status.txt" --run-status "$evidence_root/run_exit_status.txt" --signal-status "$evidence_root/signal_status.txt" --output "$evidence_root/public_order_summary.json" >/dev/null 2>&1 || true
  python3 "$runtime" analyze --package-root "$package_root" --evidence-root "$evidence_root" --run-root "$run_root"
  analysis=$?
  for duplicate_root in "$server_root" "$package_root" "$launch_cwd" "$cfg_root" "$run_root"; do
    [ ! -e "$duplicate_root/${{package_identity}}_return.zip" ] || exit 11
    [ ! -e "$duplicate_root/${{package_identity}}_return.zip.sha256" ] || exit 11
  done
  publication_json="$(python3 "$publisher" --package-root "$package_root" --evidence-root "$evidence_root" --run-root "$run_root")"
  collection=$?
  [ "$collection" -ne 0 ] || printf '%s\\n' "$publication_json"
  final="$original"
  [ "$final" -ne 0 ] || [ "$analysis" -eq 0 ] || final="$analysis"
  [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] || final="$collection"
  [ "$final" -ne 0 ] || [ "$root_gate_status" -eq 0 ] || final="$root_gate_status"
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
if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/server_root" >&2
  exit 2
fi
case "$1" in /*) ;; *) echo "server_root must be absolute" >&2; exit 2;; esac
preflight_stage=SERVER_ROOT_RESOLUTION
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2
for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || exit 3; done
preflight_stage=ROOT_SNAPSHOT
pre_snapshot_json="$(python3 "$root_gate" snapshot --server-root "$server_root")" || exit 12
mkdir -p -- "$result_root" || exit 9
[ -d "$result_root" ] && [ -w "$result_root" ] || exit 9
resolved_result_root="$(cd "$result_root" && pwd -P)" || exit 9
[ "$resolved_result_root" = "/home/panqs/ndp/simresult" ] || exit 9
[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || {{
  echo "Fixed result target conflict: $return_zip or $return_sha" >&2
  exit 10
}}
for duplicate_root in "$server_root" "$package_root" "$launch_cwd"; do
  [ ! -e "$duplicate_root/${{package_identity}}_return.zip" ] || exit 11
  [ ! -e "$duplicate_root/${{package_identity}}_return.zip.sha256" ] || exit 11
done
preflight_stage=INSTALL_LAYOUT_PREPARE
layout_shell="$(python3 "$layout_helper" prepare --server-root "$server_root" --package-id "$package_identity" --install-name "$install_name" --attempt "$attempt" --format shell)"
layout_status=$?
[ "$layout_status" -eq 0 ] || exit 12
eval "$layout_shell"
work_root="$RUN_ROOT"
cfg_root="$CFG_ROOT"
run_root="$RUN_ROOT"
evidence_root="$EVIDENCE_ROOT"
compile_root="$COMPILE_ROOT"
mkdir -p "$compile_root/sim_results" "$evidence_root/natural_terminal" "$evidence_root/feature_binding"
mkdir -p "$run_root/c0/d/op_w0/slice"{{00..27}}
printf '%s\\n' "$pre_snapshot_json" > "$evidence_root/ndp_root_toplevel_pre.json"
parent_preflight_json="$(python3 "$root_gate" validate-parents --server-root "$server_root" --manifest "$package_root/package_manifest.json")" || exit 12
printf '%s\\n' "$parent_preflight_json" > "$evidence_root/ndp_root_parent_preflight.json"
printf '%s\\n' '{{"schema":"package-preflight-not-reached-v1","valid":false,"status":"NOT_REACHED"}}' > "$evidence_root/package_preflight.json"
printf '%s\\n' '{{"schema":"install-preflight-not-reached-v1","valid":false,"status":"NOT_REACHED"}}' > "$evidence_root/install_preflight.json"
printf '%s\\n' '{{"schema":"observer-precompile-not-reached-v1","valid":false,"status":"NOT_REACHED"}}' > "$evidence_root/observer_precompile.json"
cat > "$evidence_root/publication_preflight.json" <<EOF
{{
  "schema": "fixed-simresult-publication-preflight-v1",
  "result_root": "/home/panqs/ndp/simresult",
  "return_zip": "/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip",
  "return_sidecar": "/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip.sha256",
  "publication_state": "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING",
  "server_root_duplicate_absent": true,
  "package_root_duplicate_absent": true,
  "install_namespace_duplicate_absent": true,
  "run_root_duplicate_absent": true,
  "launch_cwd_duplicate_absent": true
}}
EOF
preflight_stage=PATH_BUDGET_RUNNING
python3 "$runtime" path-budget --package-root "$package_root" --server-root "$server_root" > "$evidence_root/path_budget.json" 2> "$evidence_root/path_budget.stderr.txt"
path_budget_status=$?
[ "$path_budget_status" -eq 0 ] || exit 5
preflight_stage=PACKAGE_PREFLIGHT_RUNNING
python3 "$runtime" preflight --package-root "$package_root" > "$evidence_root/package_preflight.json" 2> "$evidence_root/package_preflight.stderr.txt"
package_preflight_status=$?
[ "$package_preflight_status" -eq 0 ] || exit 5
preflight_stage=INSTALL_COPY
cp -a "$package_root/workload/runtime/." "$cfg_root/"
python3 "$runtime" verify-install --package-root "$package_root" --cfg-root "$cfg_root" > "$evidence_root/install_preflight.json" 2> "$evidence_root/install_preflight.stderr.txt"
install_preflight_status=$?
[ "$install_preflight_status" -eq 0 ] || exit 6
preflight_stage=OBSERVER_PREFLIGHT
python3 "$observer_guard" --package-root "$package_root" > "$evidence_root/observer_precompile.json" 2> "$evidence_root/observer_precompile.stderr.txt"
observer_preflight_status=$?
[ "$observer_preflight_status" -eq 0 ] || exit 7
preflight_stage=PRODUCTION_COMPILE
cd "$server_root"
printf '%s\\n' "make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=$compile_root VCS_EXTRA_OPTS=+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe" > "$evidence_root/compile_argv.txt"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$compile_root" VCS_EXTRA_OPTS="+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe" > "$compile_root/sim_results/compile_driver.log" 2>&1
compile_status=$?
[ "$compile_status" -eq 0 ] || exit "$compile_status"
python3 "$runtime" compile-identity --compile-log "$compile_root/sim_results/compile_driver.log" --output "$evidence_root/production_rtl_identity.json" >/dev/null 2>&1 || true
simv="$compile_root/sim_results/simv"
mkdir -p "$run_root/c0"
observer_log="$run_root/c0/return_observer.log"
trigger_log="$run_root/c0/triggered_observer.log"
public_log="$run_root/c0/public_order_observer.log"
printf '%s\\n' "$simv -l $run_root/c0/sim.log +vcs+lic+wait +SCA_CFG=$cfg_root/runs/c0/sca_cfg.json +SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json +RETURN_OBSERVER +N4D_C0_BOUNDARY_DIAG +RETURN_OBS_SLICE=0 +RETURN_OBS_STALL_CYCLES=1048576 +RETURN_OBS_HEARTBEAT_CYCLES=262144 +RETURN_OBS_FILE=$observer_log +N4T_CAUSAL_PROFILE +N4T_NO_PROGRESS_CYCLES=1048576 +N4T_FILE=$trigger_log +N4P_PUBLIC_ORDER_PROFILE +N4P_EVENT_LIMIT=64 +N4P_FILE=$public_log" > "$run_root/c0/simulator_argv.txt"
preflight_stage=PRODUCTION_SIMULATION
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
'''


def patch_runner(package: Path) -> None:
    (package / "PREPARE_AND_RUN.sh").write_text(
        runner_text(), encoding="utf-8", newline="\n"
    )


def add_return_declarations(manifest: dict[str, Any]) -> None:
    declarations = manifest.get("return_allowlist")
    if not isinstance(declarations, list):
        raise BuildError("return allowlist is malformed")
    additions = (
        (
            "runtime_layout_receipt.json",
            True,
            "shared install-subtree layout was not created",
        ),
    )
    existing = {
        str(item.get("source_path"))
        for item in declarations
        if isinstance(item, dict)
    }
    for source_path, required, missing in additions:
        if source_path in existing:
            continue
        declarations.append(
            {
                "source_root": "evidence",
                "source_path": source_path,
                "target_path": f"evidence/{source_path}",
                "required": required,
                "max_bytes": 2 * 1024 * 1024,
                "missing_semantics": missing,
            }
        )


def additional_projected_paths(sca_d_paths: list[str]) -> list[str]:
    prefix = f"install/codex_runs/{PACKAGE_ID}/{{attempt}}"
    values = {
        *(
            path.replace(f"/{ATTEMPT}/", "/{attempt}/", 1)
            for path in sca_d_paths
        ),
        f"{prefix}/compile/sim_results/compile_driver.log",
        f"{prefix}/compile/sim_results/simv",
        f"{prefix}/c0/triggered_observer.log",
        f"{prefix}/c0/public_order_observer.log",
        f"{prefix}/c0/return_observer.log",
        f"{prefix}/c0/sim.log",
        f"{prefix}/evidence/runtime_layout_receipt.json",
        f"{prefix}/evidence/triggered_causal_summary.json",
        f"{prefix}/evidence/public_order_summary.json",
        f"{prefix}/evidence/package_local_preflight_status.json",
        f"{prefix}/evidence/ndp_root_toplevel_gate.json",
    }
    return sorted(values)


def projected_paths(
    package: Path, additions: list[str]
) -> set[str]:
    runtime = package / "workload/runtime"
    attempt_probe = "a" * ATTEMPT_MAX_CHARS
    values = {
        f"{RUNTIME_PREFIX}/{path.relative_to(runtime).as_posix()}"
        for path in runtime.rglob("*")
        if path.is_file()
    }
    values.update(
        {
            RUNTIME_PREFIX,
            f"install/codex_runs/{PACKAGE_ID}/{attempt_probe}",
            f"install/codex_runs/{PACKAGE_ID}/{attempt_probe}/evidence",
            f"install/codex_runs/{PACKAGE_ID}/{attempt_probe}/compile",
        }
    )
    values.update(
        path.replace("{attempt}", attempt_probe) for path in additions
    )
    return values


def path_budget(
    package: Path, additions: list[str]
) -> dict[str, Any]:
    projected = projected_paths(package, additions)
    longest = max(projected, key=lambda item: (len(item), item))
    inner = sorted(file_records(package))
    relative_chars = len(longest)
    absolute_chars = SERVER_ROOT_BUDGET_CHARS + 1 + relative_chars
    if relative_chars != 115 or absolute_chars > ABSOLUTE_PATH_LIMIT_CHARS:
        raise BuildError(
            f"p12 regression/path budget differs: {longest!r} "
            f"{relative_chars=} {absolute_chars=}"
        )
    return {
        "rule_id": "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
        "declared_target_root_max_chars": SERVER_ROOT_BUDGET_CHARS,
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": relative_chars,
        "max_projected_relative_path_chars": relative_chars,
        "max_projected_absolute_path_chars": absolute_chars,
        "absolute_path_limit_chars": ABSOLUTE_PATH_LIMIT_CHARS,
        "max_projected_absolute_path_limit_chars": (
            ABSOLUTE_PATH_LIMIT_CHARS
        ),
        "max_zip_member_chars": max(
            len(f"{PACKAGE_ID}/{relative}") for relative in inner
        ),
        "max_inner_suffix_chars": max(map(len, inner)),
        "max_inner_depth": max(
            len(PurePosixPath(relative).parts) for relative in inner
        ),
        "max_inner_component_chars": max(
            len(part)
            for relative in inner
            for part in PurePosixPath(relative).parts
        ),
        "outer_identity_repeated_inside": False,
        "fixed_result_root": "/home/panqs/ndp/simresult",
    }


def write_layout_contract(
    package: Path, sca_d_paths: list[str]
) -> dict[str, Any]:
    helper_target = (
        package / "package_tools/server_package_runtime_layout.py"
    )
    if sha256(SHARED_LAYOUT_HELPER) != SHARED_LAYOUT_HELPER_SHA256:
        raise BuildError("current shared layout helper differs")
    shutil.copyfile(SHARED_LAYOUT_HELPER, helper_target)
    additions = additional_projected_paths(sca_d_paths)
    budget = path_budget(package, additions)
    contract = {
        "schema": "server_package_runtime_layout_v1",
        "package_id": PACKAGE_ID,
        "install_name": WORKLOAD_INSTALL_NAME,
        "runner_member": "PREPARE_AND_RUN.sh",
        "manifest_member": "package_manifest.json",
        "shared_layout_helper": {
            "member": "package_tools/server_package_runtime_layout.py",
            "sha256": SHARED_LAYOUT_HELPER_SHA256,
        },
        "tb_cwd": "$server_root",
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "required_preexisting_parents": [
            "install",
            "install/cfg_pkg",
            "install/codex_runs",
        ],
        "runtime_roots": {
            "cfg_root": RUNTIME_PREFIX,
            "run_root": (
                f"install/codex_runs/{PACKAGE_ID}/{{attempt}}"
            ),
            "evidence_root": (
                f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence"
            ),
            "compile_root": (
                f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/compile"
            ),
        },
        "payload_mounts": [
            {
                "source_prefix": "workload/runtime/",
                "runtime_prefix": f"{RUNTIME_PREFIX}/",
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
                'layout_shell="$(python3 "$layout_helper" prepare'
            ),
            "tb_cwd_marker": 'cd "$server_root"',
            "compile_marker": "preflight_stage=PRODUCTION_COMPILE",
            "simulation_marker": (
                "preflight_stage=PRODUCTION_SIMULATION"
            ),
        },
        "path_budget": {
            "attempt_max_chars": ATTEMPT_MAX_CHARS,
            "declared_target_root_max_chars": (
                SERVER_ROOT_BUDGET_CHARS
            ),
            "max_projected_absolute_path_chars": budget[
                "max_projected_absolute_path_chars"
            ],
            "absolute_path_limit_chars": ABSOLUTE_PATH_LIMIT_CHARS,
            "additional_projected_paths": additions,
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
            "Mechanical install-subtree runtime layout, SCA open-path "
            "projection, early partial-return finalizer and fixed-result "
            "publication only; no DUT, numeric, terminal, formal-D, E4 or "
            "E5 claim."
        ),
    }
    write_json(package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json", contract)
    return contract


def update_manifest(
    package: Path,
    contract: dict[str, Any],
    sca_d_paths: list[str],
) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    additions = contract["path_budget"]["additional_projected_paths"]
    manifest.update(
        {
            "schema": "conv-native-four-lane-p14-install-package-v1",
            "package_identity": PACKAGE_ID,
            "workload_install_name": WORKLOAD_INSTALL_NAME,
            "install_name": WORKLOAD_INSTALL_NAME,
            "return_name": f"{PACKAGE_ID}_return.zip",
            "run_namespace": (
                f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}"
            ),
            "candidate_release": False,
            "status": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        }
    )
    manifest["fixed_server_result_publication"] = {
        "result_root": "/home/panqs/ndp/simresult",
        "return_zip": (
            f"/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip"
        ),
        "return_sidecar": (
            f"/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip.sha256"
        ),
        "atomic_same_directory_staging": True,
    }
    manifest["runner_only_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_package_zip_sha256": SOURCE_SHA256,
        "changed_surfaces": [
            "fresh package/return identity",
            "PREPARE_AND_RUN.sh",
            "package_manifest.json",
            "TEST_PACKAGE_MANIFEST.json",
            "README.md",
            "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
            "package_tools/server_package_runtime_layout.py",
            "package_tools/fixed_simresult_publisher.py",
            (
                "package_tools/"
                "node0004_assumed_hardware_server_runtime.py"
            ),
            "workload/runtime/runs/c0/sca_cfg_D.json path prefix only",
        ],
        "frozen_surfaces": [
            "all other workload/runtime bytes",
            "config/mapping/bitstream/execplan/SCA input bytes",
            "numeric/W3/golden",
            "diagnostics/tb_probe/observer/timeout",
            "functional RTL/ISA/hardware/active ndp-sim",
        ],
    }
    manifest["ndp_root_toplevel_contract"] = {
        "runtime_write_targets": [
            RUNTIME_PREFIX,
            f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}",
        ],
        "root_internal_preexisting_parents": ["install"],
        "root_external_write_roots": [
            "/home/panqs/ndp/simresult"
        ],
    }
    manifest["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "reason": (
            "p13 was held before shared install-subtree layout gate"
        ),
        "sca_d_output_paths": sca_d_paths,
        "rule_ids": [
            "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
            "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
            "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
            "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
            "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
        ],
    }
    add_return_declarations(manifest)
    manifest["release_gate_matrix"] = {
        "core_always": {
            "applicability": "blocking_applicable",
            "pass": True,
            "blocking": True,
        },
        "runner": {
            "applicability": "blocking_applicable",
            "pass": True,
            "blocking": True,
        },
        "package_local_hdl": {
            "applicability": "receipt_reuse",
            "pass": True,
            "blocking": False,
        },
        "materialized_config": {
            "applicability": "blocking_applicable",
            "pass": True,
            "changed_surface": [
                "SCA_D mechanical runtime output prefix only"
            ],
            "blocking": True,
        },
        "diagnostic_semantics": {
            "applicability": "receipt_reuse",
            "pass": True,
            "blocking": False,
        },
        "return_result": {
            "applicability": "blocking_applicable",
            "pass": True,
            "blocking": True,
        },
        "runtime_layout": {
            "applicability": "blocking_applicable",
            "pass": True,
            "rule_id": (
                "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001"
            ),
            "blocking": True,
        },
        "record_only": [
            "numeric/W3/golden/config/address/observer/timeout/RTL frozen",
            "no DUT execution in local final audit",
        ],
    }
    manifest["path_length_budget"] = path_budget(package, additions)
    manifest["files"] = file_records(package)
    write_json(path, manifest)
    manifest["path_length_budget"] = path_budget(package, additions)
    manifest["files"] = file_records(package)
    write_json(path, manifest)


def update_test_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value.update(
        {
            "schema": "conv-native-four-lane-p14-install-pointer-v1",
            "package_identity": PACKAGE_ID,
            "install_name": WORKLOAD_INSTALL_NAME,
            "candidate_release": False,
            "formal_readback_count": 0,
            "runtime_layout_contract": (
                "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
            ),
        }
    )
    write_json(path, value)


def update_readme(package: Path) -> None:
    (package / "README.md").write_text(
        "# Native Conv node0004 p14 install-subtree successor\n\n"
        "This fresh package preserves the held p13 diagnostic workload, "
        "configuration, numeric/golden data, observer, timeout and RTL/ISA "
        "semantics. Package-owned cfg/run/evidence/compile state is created "
        "only below the supplied NDP root's pre-existing install/cfg_pkg "
        "and install/codex_runs directories. SCA_D output paths are "
        "mechanically rebound to the same isolated attempt tree.\n\n"
        "Server command:\n\n"
        "`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        "The supplied NDP root must already contain real, non-symlink "
        "`install`, `install/cfg_pkg`, and `install/codex_runs` "
        "directories. Expected normal or partial return:\n\n"
        f"`/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip`\n",
        encoding="utf-8",
        newline="\n",
    )


def build_directory(target: Path) -> Path:
    package = extract_exact_source(target)
    sca_d_paths = patch_sca_d(package)
    patch_runtime(package)
    patch_publisher(package)
    patch_runner(package)
    update_test_manifest(package)
    update_readme(package)
    contract = write_layout_contract(package, sca_d_paths)
    update_manifest(package, contract, sca_d_paths)
    return package


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(
            item for item in package.rglob("*") if item.is_file()
        ):
            relative = (
                Path(PACKAGE_ID) / path.relative_to(package)
            ).as_posix()
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (
                (
                    0o100755
                    if path.name == "PREPARE_AND_RUN.sh"
                    else 0o100644
                )
                << 16
            )
            archive.writestr(info, path.read_bytes())


def main() -> int:
    targets = (
        OUTPUT_ROOT / PACKAGE_ID,
        OUTPUT_ROOT / f"{PACKAGE_ID}.zip",
        OUTPUT_ROOT / f"{PACKAGE_ID}.zip.sha256",
        OUTPUT_ROOT / f"{PACKAGE_ID}.build.json",
    )
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite an existing p14 target")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    package = build_directory(OUTPUT_ROOT)
    zip_path = OUTPUT_ROOT / f"{PACKAGE_ID}.zip"
    deterministic_zip(package, zip_path)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="native4-p14-repeat-") as temp:
        repeated = build_directory(Path(temp))
        repeated_zip = Path(temp) / f"{PACKAGE_ID}.zip"
        deterministic_zip(repeated, repeated_zip)
        deterministic = sha256(repeated_zip) == digest
    if not deterministic:
        raise BuildError("p14 deterministic double build differs")
    sidecar = OUTPUT_ROOT / f"{PACKAGE_ID}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    result = {
        "schema": "conv-native-four-lane-p14-install-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "workload_install_name": WORKLOAD_INSTALL_NAME,
        "source_p13_zip_sha256": SOURCE_SHA256,
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "deterministic_double_build": deterministic,
        "functional_rtl_modified": False,
        "config_numeric_w3_golden_observer_timeout_changed": False,
        "sca_d_path_prefix_only_changed": True,
        "server_action": False,
    }
    write_json(OUTPUT_ROOT / f"{PACKAGE_ID}.build.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
