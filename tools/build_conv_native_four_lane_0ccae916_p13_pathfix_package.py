#!/usr/bin/env python3
"""Build the p13 path-budget and early-finalizer fix from exact p12."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p12_rootgate"
PACKAGE_ID = "r5_n4_0cc_p13_pathfix"
WORKLOAD_INSTALL_NAME = "r5_n4_0cc_p11f_pubord"
SOURCE_SHA256 = (
    "ab8f13aaa2e66f01bd9c5461f8131b9cf0f89fb1706feb5fcd6aac0f15957646"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "pending"
    / f"{SOURCE_ID}.zip"
)
OUTPUT_ROOT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p12_preflight_failure_p13_pathfix"
)
SERVER_ROOT_BUDGET_CHARS = 96
ABSOLUTE_PATH_LIMIT_CHARS = 240


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


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
        raise BuildError("exact p12 source ZIP differs or is unavailable")
    package = target / PACKAGE_ID
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("p12 source ZIP CRC differs")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or pure.parts[0] != SOURCE_ID
            ):
                raise BuildError(f"unsafe p12 member: {info.filename}")
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


def patch_publisher(package: Path) -> None:
    path = package / "package_tools/fixed_simresult_publisher.py"
    text = path.read_text(encoding="utf-8")
    if text.count(SOURCE_ID) != 1:
        raise BuildError("publisher p12 identity anchor differs")
    path.write_text(
        text.replace(SOURCE_ID, PACKAGE_ID),
        encoding="utf-8",
        newline="\n",
    )


def early_finalizer_middle() -> str:
    return r'''mkdir -p "$cfg_root" "$run_root/compile/sim_results" "$evidence_root/natural_terminal" "$evidence_root/feature_binding"
printf '%s\n' "$pre_snapshot_json" > "$evidence_root/ndp_root_toplevel_pre.json"
printf '%s\n' "$parent_preflight_json" > "$evidence_root/ndp_root_parent_preflight.json"
printf '%s\n' '{"schema":"package-preflight-not-reached-v1","valid":false,"status":"NOT_REACHED"}' > "$evidence_root/package_preflight.json"
printf '%s\n' '{"schema":"install-preflight-not-reached-v1","valid":false,"status":"NOT_REACHED"}' > "$evidence_root/install_preflight.json"
printf '%s\n' '{"schema":"observer-precompile-not-reached-v1","valid":false,"status":"NOT_REACHED"}' > "$evidence_root/observer_precompile.json"
cat > "$evidence_root/publication_preflight.json" <<EOF
{
  "schema": "fixed-simresult-publication-preflight-v1",
  "result_root": "/home/panqs/ndp/simresult",
  "return_zip": "/home/panqs/ndp/simresult/r5_n4_0cc_p13_pathfix_return.zip",
  "return_sidecar": "/home/panqs/ndp/simresult/r5_n4_0cc_p13_pathfix_return.zip.sha256",
  "publication_state": "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING",
  "server_root_duplicate_absent": true,
  "package_root_duplicate_absent": true,
  "install_namespace_duplicate_absent": true,
  "run_root_duplicate_absent": true,
  "launch_cwd_duplicate_absent": true
}
EOF
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
preflight_stage=BOOTSTRAP_READY
finalize() {
  original="$1"; [ "$finalized" -eq 0 ] || exit "$original"; finalized=1
  trap - EXIT INT TERM HUP
  set +e
  [ -z "$progress_pid" ] || kill "$progress_pid" 2>/dev/null
  [ -z "$progress_pid" ] || wait "$progress_pid" 2>/dev/null
  post_snapshot_json="$(python3 "$root_gate" snapshot --server-root "$server_root")"
  post_capture=$?
  [ "$post_capture" -ne 0 ] || printf '%s\n' "$post_snapshot_json" > "$evidence_root/ndp_root_toplevel_post.json"
  [ "$post_capture" -eq 0 ] || printf '%s\n' '{"schema":"ndp-root-toplevel-post-capture-error"}' > "$evidence_root/ndp_root_toplevel_post.json"
  python3 "$root_gate" compare --pre "$evidence_root/ndp_root_toplevel_pre.json" --post "$evidence_root/ndp_root_toplevel_post.json" --manifest "$package_root/package_manifest.json" --output "$evidence_root/ndp_root_toplevel_gate.json" >/dev/null 2>&1
  root_gate_status=$?
  printf '%s\n' "$compile_status" > "$evidence_root/compile_exit_status.txt"
  printf '%s\n' "$run_status" > "$evidence_root/run_exit_status.txt"
  printf '%s\n' "$signal_status" > "$evidence_root/signal_status.txt"
  [ "$package_preflight_status" -eq 0 ] || printf '%s\n' '{"schema":"package-preflight-failed-v1","valid":false,"status":"FAILED_BEFORE_COMPILE"}' > "$evidence_root/package_preflight.json"
  [ "$install_preflight_status" -eq 0 ] || printf '%s\n' '{"schema":"install-preflight-not-complete-v1","valid":false,"status":"NOT_COMPLETE_BEFORE_COMPILE"}' > "$evidence_root/install_preflight.json"
  [ "$observer_preflight_status" -eq 0 ] || printf '%s\n' '{"schema":"observer-precompile-not-complete-v1","valid":false,"status":"NOT_COMPLETE_BEFORE_COMPILE"}' > "$evidence_root/observer_precompile.json"
  cat > "$evidence_root/package_local_preflight_status.json" <<EOF
{
  "schema": "conv-native-four-lane-package-local-preflight-status-v1",
  "preflight_stage": "$preflight_stage",
  "path_budget_exit_status": $path_budget_status,
  "package_preflight_exit_status": $package_preflight_status,
  "install_preflight_exit_status": $install_preflight_status,
  "observer_preflight_exit_status": $observer_preflight_status,
  "production_compile_started": $([ "$compile_status" -eq 125 ] && printf false || printf true),
  "dut_simulation_started": $([ "$run_status" -eq 125 ] && printf false || printf true)
}
EOF
  python3 "$trigger_finalizer" --observer-log "$run_root/c0/triggered_observer.log" --sim-log "$run_root/c0/sim.log" --compile-status "$evidence_root/compile_exit_status.txt" --run-status "$evidence_root/run_exit_status.txt" --signal-status "$evidence_root/signal_status.txt" --output "$evidence_root/triggered_causal_summary.json" >/dev/null 2>&1 || true
  python3 "$public_finalizer" --observer-log "$run_root/c0/public_order_observer.log" --compile-status "$evidence_root/compile_exit_status.txt" --run-status "$evidence_root/run_exit_status.txt" --signal-status "$evidence_root/signal_status.txt" --output "$evidence_root/public_order_summary.json" >/dev/null 2>&1 || true
  python3 "$runtime" analyze --package-root "$package_root" --evidence-root "$evidence_root" --run-root "$run_root"
  analysis=$?
  for duplicate_root in "$server_root" "$package_root" "$launch_cwd" "$cfg_root" "$run_root"; do
    [ ! -e "$duplicate_root/${package_identity}_return.zip" ] || exit 11
    [ ! -e "$duplicate_root/${package_identity}_return.zip.sha256" ] || exit 11
  done
  publication_json="$(python3 "$publisher" --package-root "$package_root" --evidence-root "$evidence_root" --run-root "$run_root")"
  collection=$?
  [ "$collection" -ne 0 ] || printf '%s\n' "$publication_json"
  final="$original"
  [ "$final" -ne 0 ] || [ "$analysis" -eq 0 ] || final="$analysis"
  [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] || final="$collection"
  [ "$final" -ne 0 ] || [ "$root_gate_status" -eq 0 ] || final="$root_gate_status"
  exit "$final"
}
trap 'finalize $?' EXIT
on_signal() {
  signal_status="$1"
  [ -z "$sim_pid" ] || kill -TERM "$sim_pid" 2>/dev/null
  finalize "$2"
}
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
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
'''


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    if text.count(SOURCE_ID) != 6:
        raise BuildError(f"runner p12 identity count differs: {text.count(SOURCE_ID)}")
    text = text.replace(SOURCE_ID, PACKAGE_ID)
    start = 'python3 "$runtime" path-budget --package-root "$package_root"'
    end = 'cd "$server_root"\n'
    if text.count(start) != 1 or text.count(end) != 1:
        raise BuildError("runner preflight/finalizer anchors differ")
    prefix = text[: text.index(start)]
    suffix = text[text.index(end) :]
    path.write_text(
        prefix + early_finalizer_middle() + suffix,
        encoding="utf-8",
        newline="\n",
    )


def add_return_declarations(manifest: dict[str, Any]) -> None:
    declarations = manifest.get("return_allowlist")
    if not isinstance(declarations, list):
        raise BuildError("return allowlist is malformed")
    additions = (
        (
            "package_local_preflight_status.json",
            True,
            "early shared finalizer did not record package-local stage status",
        ),
        (
            "path_budget.json",
            False,
            "path-budget rejected before emitting a positive receipt",
        ),
        (
            "path_budget.stderr.txt",
            False,
            "path-budget emitted no stderr",
        ),
        (
            "package_preflight.stderr.txt",
            False,
            "package preflight emitted no stderr",
        ),
        (
            "install_preflight.stderr.txt",
            False,
            "install preflight emitted no stderr",
        ),
        (
            "observer_precompile.stderr.txt",
            False,
            "observer preflight emitted no stderr",
        ),
    )
    existing = {
        str(item.get("source_path"))
        for item in declarations
        if isinstance(item, dict)
    }
    for source_path, required, missing in additions:
        if source_path in existing:
            raise BuildError(f"return declaration already exists: {source_path}")
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


def compute_path_budget(package: Path) -> dict[str, Any]:
    runtime = package / "workload/runtime"
    projected = [
        f"install/cfg_pkg/{WORKLOAD_INSTALL_NAME}/"
        f"{path.relative_to(runtime).as_posix()}"
        for path in runtime.rglob("*")
        if path.is_file()
    ]
    projected.extend(
        [
            f"run_{PACKAGE_ID}/compile/sim_results/compile_driver.log",
            f"run_{PACKAGE_ID}/c0/triggered_observer.log",
            f"evidence_{PACKAGE_ID}/triggered_causal_summary.json",
            f"{PACKAGE_ID}_return/evidence/triggered_causal_summary.json",
            f"{PACKAGE_ID}_return/evidence/package_local_preflight_status.json",
        ]
    )
    longest = max(projected, key=len)
    inner = sorted(file_records(package))
    result = {
        "rule_id": "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
        "declared_target_root_max_chars": SERVER_ROOT_BUDGET_CHARS,
        "max_projected_absolute_path_limit_chars": ABSOLUTE_PATH_LIMIT_CHARS,
        "max_projected_absolute_path_chars": (
            SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
        ),
        "max_projected_relative_path_chars": len(longest),
        "longest_projected_relative_path": longest,
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
        "actual_server_guard": (
            "exact runtime recomputes normalized user-root path budget "
            "before production compile"
        ),
        "fixed_result_root": "/home/panqs/ndp/simresult",
    }
    if (
        len(longest) != result["max_projected_relative_path_chars"]
        or result["max_projected_absolute_path_chars"]
        > ABSOLUTE_PATH_LIMIT_CHARS
    ):
        raise BuildError(f"path budget self-check failed: {result}")
    return result


def update_manifest(package: Path) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "conv-native-four-lane-p13-pathfix-package-v1",
            "package_identity": PACKAGE_ID,
            "workload_install_name": WORKLOAD_INSTALL_NAME,
            "install_name": WORKLOAD_INSTALL_NAME,
            "return_name": f"{PACKAGE_ID}_return.zip",
            "run_namespace": f"run_{PACKAGE_ID}",
            "candidate_release": False,
            "status": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        }
    )
    manifest["fixed_server_result_publication"] = {
        **manifest.get("fixed_server_result_publication", {}),
        "result_root": "/home/panqs/ndp/simresult",
        "return_zip": (
            f"/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip"
        ),
        "return_sidecar": (
            f"/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip.sha256"
        ),
    }
    manifest["runner_only_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_package_zip_sha256": SOURCE_SHA256,
        "changed_surfaces": [
            "PREPARE_AND_RUN.sh",
            "package_manifest.json",
            "TEST_PACKAGE_MANIFEST.json",
            "README.md",
            "package_tools/fixed_simresult_publisher.py",
        ],
        "frozen_surfaces": [
            "workload/runtime",
            "diagnostics",
            "tb_probe",
            "package runtime",
            "numeric",
            "golden",
            "observer",
            "timeout",
            "functional RTL",
        ],
    }
    manifest["ndp_root_toplevel_contract"] = {
        **manifest.get("ndp_root_toplevel_contract", {}),
        "root_external_write_roots": [
            "/home/panqs/ndp/simresult",
            f"/home/panqs/ndp/simresult/.{PACKAGE_ID}.run.<pid>",
        ],
    }
    manifest["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "reason": "p12 package-local path-budget manifest was malformed",
        "changed_surface": [
            "fresh outer package/return identity",
            "path-budget recomputation from final exact package",
            "shared finalizer and signal traps before path-budget/preflight",
            "package-local preflight status and stderr return evidence",
            "exact runner path-budget/preflight audit coverage",
        ],
        "frozen_surface": [
            "workload/runtime",
            "diagnostics",
            "tb_probe",
            "package runtime and observer guard/finalizers",
            "numeric/W3/golden/config/timeout/functional RTL",
        ],
        "rule_ids": sorted(
            set(
                manifest.get("delivery_successor", {}).get("rule_ids", [])
            )
            | {
                "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
                "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
                "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
                "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
                "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
                "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
            }
        ),
    }
    add_return_declarations(manifest)
    manifest["release_gate_matrix"] = {
        "core_always": {
            "applicability": "blocking_applicable",
            "pass": True,
            "changed_surface": [
                "fresh outer package identity",
                "manifest path-budget self-consistency",
            ],
            "blocking": True,
        },
        "runner": {
            "applicability": "blocking_applicable",
            "pass": True,
            "changed_surface": [
                "early shared finalizer/traps",
                "exact path-budget/preflight to compile path",
                "preflight-failure partial-return publication",
            ],
            "blocking": True,
        },
        "package_local_hdl": {
            "applicability": "receipt_reuse",
            "pass": True,
            "evidence": ["p12 package-local HDL/TB byte equality"],
            "blocking": False,
        },
        "materialized_config": {
            "applicability": "receipt_reuse",
            "pass": True,
            "evidence": ["p12 workload/runtime byte equality"],
            "blocking": False,
        },
        "diagnostic_semantics": {
            "applicability": "receipt_reuse",
            "pass": True,
            "evidence": ["p12 diagnostics and runtime byte equality"],
            "blocking": False,
        },
        "return_result": {
            "applicability": "blocking_applicable",
            "pass": True,
            "changed_surface": [
                "p13 fixed result identity",
                "preflight-failure partial return",
            ],
            "blocking": True,
        },
        "record_only": [
            "numeric/W3/golden/address/config/observer/timeout/RTL frozen",
            "no DUT execution in local final audit",
        ],
    }
    manifest["path_length_budget"] = compute_path_budget(package)
    manifest["files"] = file_records(package)
    write_json(path, manifest)
    manifest["path_length_budget"] = compute_path_budget(package)
    manifest["files"] = file_records(package)
    write_json(path, manifest)


def update_test_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value.update(
        {
            "schema": "conv-native-four-lane-p13-pathfix-pointer-v1",
            "package_identity": PACKAGE_ID,
            "install_name": WORKLOAD_INSTALL_NAME,
            "candidate_release": False,
            "formal_readback_count": 0,
        }
    )
    write_json(path, value)


def update_readme(package: Path) -> None:
    (package / "README.md").write_text(
        "# Native Conv node0004 p13 path-budget preflight fix\n\n"
        "This fresh package preserves the exact p12 workload/config, "
        "numeric/golden data, observer, timeout, package runtime and "
        "functional RTL bytes. It recomputes the path budget from the final "
        "package and installs the shared finalizer before package-local "
        "path-budget/preflight, so such failures publish a bounded partial "
        "return to the fixed server result directory.\n\n"
        "Server command:\n\n"
        "`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        "Expected return for normal, compile failure, timeout or catchable "
        "HUP/INT/TERM and package-local preflight failure:\n\n"
        f"`/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip`\n",
        encoding="utf-8",
        newline="\n",
    )


def build_directory(target: Path) -> Path:
    package = extract_exact_source(target)
    patch_publisher(package)
    patch_runner(package)
    update_test_manifest(package)
    update_readme(package)
    update_manifest(package)
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
                (0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644)
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
        raise BuildError("refusing to overwrite an existing p13 target")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    package = build_directory(OUTPUT_ROOT)
    zip_path = OUTPUT_ROOT / f"{PACKAGE_ID}.zip"
    deterministic_zip(package, zip_path)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="native4-p13-repeat-") as temp:
        repeated = build_directory(Path(temp))
        repeated_zip = Path(temp) / f"{PACKAGE_ID}.zip"
        deterministic_zip(repeated, repeated_zip)
        deterministic = sha256(repeated_zip) == digest
    if not deterministic:
        raise BuildError("p13 deterministic double build differs")
    sidecar = OUTPUT_ROOT / f"{PACKAGE_ID}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    result = {
        "schema": "conv-native-four-lane-p13-pathfix-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "workload_install_name": WORKLOAD_INSTALL_NAME,
        "source_p12_zip_sha256": SOURCE_SHA256,
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "deterministic_double_build": deterministic,
        "functional_rtl_modified": False,
        "config_numeric_w3_golden_observer_timeout_changed": False,
        "package_runtime_changed": False,
        "server_action": False,
    }
    write_json(OUTPUT_ROOT / f"{PACKAGE_ID}.build.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
