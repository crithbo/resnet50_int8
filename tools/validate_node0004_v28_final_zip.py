from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


INSTALL_NAME = "r5_n4_hw_v28_dwrite_path_diag_bind"
SOURCE_NAME = "r5_n4_hw_v26_transout_threshold_fix"
ZIP_SHA256 = (
    "a3b2be33d395356b06c96e8311c017544cbdcc7b3e553006ae582acea176101f"
)
SOURCE_SHA256 = (
    "94beb61460e033fbf8ec7afd4cd64e38cd23681fb894df9960bd3cb4be962ddb"
)
CURRENT_RECEIPTS = {
    "agent": "d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721",
    "index": "db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5",
    "server": "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48",
    "int8_sa": "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    "readme": "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7",
}
FEATURES = (
    ("RETURN_OBS_DEEP", "+RETURN_OBS_DEEP", "+RETURN_OBS_DEEP_LIMIT=256"),
    (
        "RETURN_OBS_ABPE",
        "+RETURN_OBS_ABPE",
        "+RETURN_HANG_DIAG_MAX_CYCLES=8388608",
    ),
    (
        "RETURN_HANG_DIAG",
        "+RETURN_HANG_DIAG",
        "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144",
    ),
    (
        "RETURN_OBS_FINAL_RELEASE",
        "+RETURN_OBS_FINAL_RELEASE",
        "+RETURN_OBS_FINAL_RELEASE_LIMIT=256",
    ),
    (
        "RETURN_OBS_DWRITE_PATH",
        "+RETURN_OBS_DWRITE_PATH",
        "+RETURN_OBS_DWRITE_PATH_LIMIT=64",
    ),
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(path: Path, root: str) -> tuple[dict[str, bytes], list[str]]:
    entries: dict[str, bytes] = {}
    errors: list[str] = []
    roots: set[str] = set()
    seen: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"CRC failure: {bad}")
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
                errors.append(f"unsafe/duplicate/symlink: {info.filename}")
                continue
            seen.add(info.filename)
            if not pure.parts:
                continue
            roots.add(pure.parts[0])
            if info.is_dir():
                continue
            if pure.parts[0] != root:
                errors.append(f"root differs: {info.filename}")
                continue
            entries[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(info)
    if roots != {root}:
        errors.append(f"root set differs: {sorted(roots)}")
    return entries, errors


def normalized(payload: bytes, identity: str) -> bytes:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload
    return text.replace(identity, "<INSTALL>").encode()


def import_runtime(package: Path) -> Any:
    runtime_path = (
        package / "package_tools/node0004_hang_localization_runtime.py"
    )
    spec = importlib.util.spec_from_file_location("v28_runtime", runtime_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import v28 runtime")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(runtime_path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def feature_binding_controls(package: Path, root: Path) -> dict[str, Any]:
    runtime = import_runtime(package)
    evidence = root / "evidence"
    run = root / "run"
    (run / "c0").mkdir(parents=True)
    evidence.mkdir()
    (evidence / "compile_exit_status.txt").write_text("0\n", encoding="ascii")
    argv_tokens = (
        ["simv"]
        + [token for _, enable, limit in FEATURES for token in (enable, limit)]
        + [
            "+RETURN_HANG_DIAG_STALL_WINDOWS=4",
            "+RETURN_HANG_DIAG_MAX_CYCLES=8388608",
        ]
    )
    markers = [
        (
            "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | "
            f"feature={name} enabled=1 "
            + (
                "budget_name=RETURN_HANG_DIAG_MAX_CYCLES budget=8388608"
                if name == "RETURN_OBS_ABPE"
                else (
                    "sample_cycles=262144 stall_windows=4 max_cycles=8388608"
                    if name == "RETURN_HANG_DIAG"
                    else (
                        f"limit_name={limit[1:].split('=')[0]} "
                        f"limit={limit.split('=')[1]}"
                    )
                )
            )
        )
        for name, _, limit in FEATURES
    ]

    def run_case(argv: list[str], rows: list[str]) -> dict[str, Any]:
        (run / "c0/simulator_argv.txt").write_text(
            " ".join(argv) + "\n", encoding="utf-8"
        )
        observer = run / "c0/return_observer.log"
        if rows:
            observer.write_text("\n".join(rows) + "\n", encoding="utf-8")
        elif observer.exists():
            observer.unlink()
        return runtime.diagnostic_feature_binding(evidence, run)

    positive = run_case(argv_tokens, markers)
    enable_negative = run_case(
        [token for token in argv_tokens if token != "+RETURN_OBS_DWRITE_PATH"],
        markers,
    )
    limit_negative = run_case(
        [
            token
            for token in argv_tokens
            if token != "+RETURN_OBS_DWRITE_PATH_LIMIT=64"
        ],
        markers,
    )
    marker_negative = run_case(
        argv_tokens,
        [row for row in markers if "feature=RETURN_OBS_DWRITE_PATH " not in row],
    )
    return_negative = run_case(argv_tokens, [])
    return {
        "positive": positive,
        "negative_delete_enable": enable_negative,
        "negative_delete_limit": limit_negative,
        "negative_delete_time0_marker": marker_negative,
        "negative_delete_return_target": return_negative,
        "all_negative_controls_fail_closed": all(
            item.get("valid") is False
            for item in (
                enable_negative,
                limit_negative,
                marker_negative,
                return_negative,
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v26", required=True, type=Path)
    parser.add_argument("--runner-controls", required=True, type=Path)
    parser.add_argument("--observer-scope", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    zip_path = args.zip.resolve()
    sidecar = args.sidecar.resolve()
    source_path = args.source_v26.resolve()
    entries, zip_errors = read_zip(zip_path, INSTALL_NAME)
    source, source_errors = read_zip(source_path, SOURCE_NAME)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    runner = json.loads(args.runner_controls.read_text(encoding="utf-8"))
    scope = json.loads(args.observer_scope.read_text(encoding="utf-8"))
    digest = sha256_file(zip_path)
    errors = zip_errors + source_errors
    manifest_files = manifest.get("files", {})
    runtime_paths = {
        path for path in entries if path.startswith("workload/runtime/")
    }
    source_runtime_paths = {
        path for path in source if path.startswith("workload/runtime/")
    }
    runtime_equal = (
        runtime_paths == source_runtime_paths
        and all(
            normalized(entries[path], INSTALL_NAME)
            == normalized(source[path], SOURCE_NAME)
            for path in runtime_paths
        )
    )
    changed = [
        path
        for path in sorted(set(entries) & set(source))
        if normalized(entries[path], INSTALL_NAME)
        != normalized(source[path], SOURCE_NAME)
    ]
    expected_changed = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "package_manifest.json",
        "package_tools/node0004_hang_localization_runtime.py",
        "tb_probe/native_return_observer.svh",
    }
    receipt_text = json.dumps(manifest, sort_keys=True)
    prepare = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    observer = entries.get("tb_probe/native_return_observer.svh", b"").decode(
        "utf-8", errors="replace"
    )
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode("utf-8", errors="replace")
    with tempfile.TemporaryDirectory(prefix="v28-final-audit-") as temp:
        package = Path(temp) / INSTALL_NAME
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(Path(temp))
        feature_controls = feature_binding_controls(
            package, Path(temp) / "feature-controls"
        )
    checks = {
        "zip_sha": digest == ZIP_SHA256,
        "sidecar": sidecar.read_text(encoding="ascii")
        == f"{digest}  {zip_path.name}\n",
        "source_sha": sha256_file(source_path) == SOURCE_SHA256,
        "manifest_exact_set_hashes": (
            set(manifest_files) == set(entries) - {"package_manifest.json"}
            and all(
                path in entries and sha256_bytes(entries[path]) == value
                for path, value in manifest_files.items()
            )
        ),
        "identity_classification": (
            manifest.get("install_name") == INSTALL_NAME
            and manifest.get("classification")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("candidate_release") is False
        ),
        "frozen_scope": (
            manifest.get("numeric_analysis_repeated") is False
            and manifest.get("node0004_workload_rebuilt") is False
            and manifest.get("configuration_rebuilt_in_this_successor") is False
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
            and runtime_equal
        ),
        "only_expected_source_changes": set(changed) == expected_changed,
        "current_rule_receipts": all(value in receipt_text for value in CURRENT_RECEIPTS.values()),
        "observer_narrow_feature": (
            observer.count("DWRITE_PATH_BOUNDARY_V1") == 1
            and observer.count(
                "feature=RETURN_OBS_DWRITE_PATH enabled=%0d"
            )
            == 1
            and "return_obs_write_dwrite_path_state(event_name);" in observer
        ),
        "actual_runner_binding": (
            prepare.count("+RETURN_OBS_DWRITE_PATH") == 4
            and prepare.count("+RETURN_OBS_DWRITE_PATH_LIMIT=64") == 2
            and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in prepare
            and "+incdir+$package_root/tb_probe" in prepare
        ),
        "collector_binding": (
            runtime.count('"feature": "RETURN_OBS_DWRITE_PATH"') == 1
            and runtime.count('"enable": "+RETURN_OBS_DWRITE_PATH"') == 1
            and runtime.count(
                '"limits": ("+RETURN_OBS_DWRITE_PATH_LIMIT=64",)'
            )
            == 1
        ),
        "runner_controls": runner.get("valid") is True,
        "observer_scope": (
            scope.get("valid") is True
            and scope.get("all_negative_controls_fail_closed") is True
        ),
        "feature_binding_positive": (
            feature_controls["positive"].get("valid") is True
            and len(feature_controls["positive"].get("features", [])) == 5
        ),
        "feature_binding_negatives": feature_controls[
            "all_negative_controls_fail_closed"
        ],
        "minimal_server_preflight": (
            "git rev-parse" not in prepare
            and "README_HARDWARE_SIM_ENTRY" not in prepare
        ),
    }
    if not all(checks.values()):
        errors += [name for name, passed in checks.items() if not passed]
    report: dict[str, Any] = {
        "schema": "node0004-v28-final-zip-rule-self-audit-v1",
        "valid": not errors,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": digest,
        },
        "sidecar": {
            "path": str(sidecar),
            "bytes": sidecar.stat().st_size,
            "sha256": sha256_file(sidecar),
        },
        "source_v26_sha256": sha256_file(source_path),
        "changed_after_identity_normalization": changed,
        "feature_binding_controls": feature_controls,
        "runner_controls_sha256": sha256_file(args.runner_controls),
        "observer_scope_sha256": sha256_file(args.observer_scope),
        "current_receipts": CURRENT_RECEIPTS,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt_in_this_successor": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
