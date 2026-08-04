from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (  # noqa: E402
    validate_conv_native_four_lane_df23e4d_server_package as v1,
)


INSTALL_NAME = "r5_n4_df23e4d_p4"
SOURCE_V1_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_conv_native_four_lane_df23e4d_perf_v1.zip"
)
RUNTIME_REL = Path(
    "package_tools/node0004_assumed_hardware_server_runtime.py"
)
MISSING_WITNESS = Path(
    "workload/runtime/runs/t000/install/cfg_pkg/"
    "op_mul_w0_s00_resnet50_requant_node0004_mul_w0_s00_bitstream_128b.bin"
)
_V1_RUNNER_COMPILE_STUB = v1.runner_compile_stub
_V1_RUNNER_SIGNAL_STUB = v1.runner_signal_stub
_SUBPROCESS_RUN = subprocess.run


def _git_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        f"/{resolved.drive[0].lower()}"
        f"{resolved.as_posix()[len(resolved.drive):]}"
    )


def _run_v1_stub_through_msys_tmp(
    control: Any, package: Path, prefix: str
) -> dict[str, Any]:
    """Keep local Git-Bash writes under /tmp in the managed sandbox."""
    with tempfile.TemporaryDirectory(prefix=prefix) as name:
        root = Path(name).resolve()
        system_temp = Path(tempfile.gettempdir()).resolve()
        if root.parent != system_temp:
            raise v1.ValidationError(
                "safe runner control did not allocate directly under system temp"
            )
        windows_prefix = _git_path(root)
        msys_prefix = f"/tmp/{root.name}"

        def rewrite(value: Any) -> Any:
            if isinstance(value, str):
                return value.replace(windows_prefix, msys_prefix)
            if isinstance(value, list):
                return [rewrite(item) for item in value]
            if isinstance(value, tuple):
                return tuple(rewrite(item) for item in value)
            return value

        def run_with_tmp_mapping(
            *arguments: Any, **keywords: Any
        ) -> subprocess.CompletedProcess[Any]:
            rewritten = list(arguments)
            if rewritten:
                rewritten[0] = rewrite(rewritten[0])
            environment = keywords.get("env")
            if isinstance(environment, dict):
                environment = dict(environment)
                environment["PATH"] = (
                    f"{msys_prefix}/stub-bin:"
                    f"{msys_prefix}/signal-stub-bin:"
                    "/usr/bin:/bin:/c/Windows/System32"
                )
                keywords["env"] = environment
            return _SUBPROCESS_RUN(*rewritten, **keywords)

        v1.subprocess.run = run_with_tmp_mapping
        try:
            return control(package, root)
        finally:
            v1.subprocess.run = _SUBPROCESS_RUN


def runner_compile_stub_safe(
    package: Path, _root: Path
) -> dict[str, Any]:
    return _run_v1_stub_through_msys_tmp(
        _V1_RUNNER_COMPILE_STUB, package, "n4-compile-"
    )


def runner_signal_stub_safe(
    package: Path, _root: Path
) -> dict[str, Any]:
    return _run_v1_stub_through_msys_tmp(
        _V1_RUNNER_SIGNAL_STUB, package, "n4-signal-"
    )


def _configure_v1() -> None:
    v1.INSTALL_NAME = INSTALL_NAME
    v1.runner_compile_stub = runner_compile_stub_safe
    v1.runner_signal_stub = runner_signal_stub_safe


def _projections(entries: dict[str, bytes], manifest: dict[str, Any]) -> list[str]:
    result = []
    prefix = "workload/runtime/"
    for relative in entries:
        if relative.startswith(prefix):
            result.append(
                f"install/cfg_pkg/{INSTALL_NAME}/{relative[len(prefix):]}"
            )
    for record in manifest.get("readback_checks", []):
        runtime_path = str(record["runtime_path"]).replace("\\", "/")
        result.append(f"{INSTALL_NAME}_return/readbacks/{runtime_path}")
    result.extend(
        [
            f"run_{INSTALL_NAME}/compile/sim_results/compile_driver.log",
            f"run_{INSTALL_NAME}/t207/return_observer.log",
            f"evidence_{INSTALL_NAME}/natural_terminal/t207.json",
            f"{INSTALL_NAME}_return/runs/t207/return_observer.log",
        ]
    )
    return result


def path_budget_check(
    entries: dict[str, bytes], manifest: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    budget = manifest.get("path_length_budget")
    if not isinstance(budget, dict):
        return {"valid": False, "errors": ["path_length_budget missing"]}
    paths = [path for path in entries if path != "package_manifest.json"]
    inner_records = [
        {
            "path": path,
            "chars": len(path),
            "depth": len(Path(path).parts),
            "max_component_chars": max(len(part) for part in Path(path).parts),
        }
        for path in paths
    ]
    longest_inner = max(inner_records, key=lambda item: int(item["chars"]))
    deepest = max(
        inner_records,
        key=lambda item: (int(item["depth"]), int(item["chars"])),
    )
    max_zip_member = max(len(f"{INSTALL_NAME}/{path}") for path in paths)
    projections = _projections(entries, manifest)
    longest_projected = max(projections, key=len)
    target_root = budget.get("declared_target_root_max_chars")
    absolute_limit = budget.get(
        "max_projected_absolute_path_limit_chars"
    )
    projected_absolute = (
        int(target_root) + 1 + len(longest_projected)
        if isinstance(target_root, int)
        else -1
    )
    expected = {
        "max_projected_absolute_path_chars": projected_absolute,
        "max_projected_relative_path_chars": len(longest_projected),
        "longest_projected_relative_path": longest_projected,
        "max_zip_member_chars": max_zip_member,
        "max_inner_suffix_chars": int(longest_inner["chars"]),
        "longest_inner_member": str(longest_inner["path"]),
        "max_inner_depth": int(deepest["depth"]),
        "deepest_inner_member": str(deepest["path"]),
        "outer_identity_repeated_inside": False,
    }
    for key, value in expected.items():
        if budget.get(key) != value:
            errors.append(f"path budget field differs: {key}")
    if not isinstance(absolute_limit, int) or projected_absolute > absolute_limit:
        errors.append("projected absolute path exceeds limit")
    if any(INSTALL_NAME in Path(path).parts for path in paths):
        errors.append("outer identity repeats inside package")
    return {
        "valid": not errors,
        "errors": errors,
        "expected": expected,
        "declared": budget,
    }


def path_budget_negative_controls(
    entries: dict[str, bytes], manifest: dict[str, Any]
) -> dict[str, Any]:
    too_deep = dict(entries)
    too_deep[
        "workload/runtime/"
        + ("deep/" * 30)
        + "member.bin"
    ] = b"x"
    repeated = dict(entries)
    repeated[f"{INSTALL_NAME}/duplicate.txt"] = b"x"
    stale = copy.deepcopy(manifest)
    stale["path_length_budget"]["longest_projected_relative_path"] = "stale"
    return {
        "deep_member_fail_closed": not path_budget_check(
            too_deep, manifest
        )["valid"],
        "repeated_outer_identity_fail_closed": not path_budget_check(
            repeated, manifest
        )["valid"],
        "stale_consumer_reference_fail_closed": not path_budget_check(
            entries, stale
        )["valid"],
    }


def _run_without_bytecode_environment(
    runtime: Path, arguments: list[str]
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.pop("PYTHONDONTWRITEBYTECODE", None)
    return subprocess.run(
        [sys.executable, str(runtime), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=180,
        check=False,
    )


def extraction_controls(zip_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix=".n4p4-", dir=ROOT, ignore_cleanup_errors=True
    ) as name:
        root = Path(name)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(root)
        package = root / INSTALL_NAME
        runtime = package / RUNTIME_REL
        clean = _run_without_bytecode_environment(
            runtime, ["preflight", "--package-root", str(package)]
        )
        bytecode = list(package.rglob("__pycache__")) + list(
            package.rglob("*.pyc")
        )
        path_positive = _run_without_bytecode_environment(
            runtime,
            [
                "path-budget",
                "--package-root",
                str(package),
                "--server-root",
                "C:/n4srv",
            ],
        )
        too_long_root = "C:/" + ("r" * 180)
        path_negative = _run_without_bytecode_environment(
            runtime,
            [
                "path-budget",
                "--package-root",
                str(package),
                "--server-root",
                too_long_root,
            ],
        )
        missing_target = package / MISSING_WITNESS
        missing_present_before = missing_target.is_file()
        missing_target.unlink()
        missing = _run_without_bytecode_environment(
            runtime, ["preflight", "--package-root", str(package)]
        )
        runner = (package / "PREPARE_AND_RUN.sh").read_text(
            encoding="utf-8"
        )
        first_preflight = runner.index(
            'package_preflight_json="$(python3 "$runtime" preflight'
        )
        namespace_create = runner.index('mkdir -p "$cfg_root"')
        bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        if not bash.is_file():
            raise v1.ValidationError(
                "Git Bash is unavailable for missing-member runner control"
            )

        with tempfile.TemporaryDirectory(prefix="n4-missing-") as server_name:
            control_root = Path(server_name).resolve()
            if control_root.parent != Path(tempfile.gettempdir()).resolve():
                raise v1.ValidationError(
                    "missing-member control escaped system temp"
                )
            missing_server = control_root / "server"
            stub_bin = control_root / "stub-bin"
            missing_server.mkdir()
            stub_bin.mkdir()
            python_stub = stub_bin / "python3"
            python_stub.write_text(
                "#!/usr/bin/env bash\n"
                f'exec "{_git_path(Path(sys.executable))}" -B "$@"\n',
                encoding="utf-8",
                newline="\n",
            )
            make_stub = stub_bin / "make"
            make_stub.write_text(
                "#!/usr/bin/env bash\nexit 91\n",
                encoding="utf-8",
                newline="\n",
            )
            os.chmod(python_stub, 0o755)
            os.chmod(make_stub, 0o755)
            msys_root = f"/tmp/{control_root.name}"
            harness = (
                'export PATH="$1:/usr/bin:/bin:/c/Windows/System32"\n'
                'bash PREPARE_AND_RUN.sh "$2"\n'
            )
            environment = dict(os.environ)
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            missing_runner = subprocess.run(
                [
                    str(bash),
                    "--noprofile",
                    "--norc",
                    "-c",
                    harness,
                    "native4-missing-control",
                    f"{msys_root}/stub-bin",
                    f"{msys_root}/server",
                ],
                cwd=package,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=180,
                check=False,
            )
            candidate_paths = [
                missing_server / f"install/cfg_pkg/{INSTALL_NAME}",
                missing_server / f"run_{INSTALL_NAME}",
                missing_server / f"evidence_{INSTALL_NAME}",
            ]
            missing_runner_no_namespace = not any(
                path.exists() for path in candidate_paths
            )
        cleanup_contract = all(
            token in runner
            for token in (
                "cleanup_empty_preflight_namespaces",
                'rmdir "$cfg_root"',
                'rmdir "$run_root/compile/sim_results"',
                'rmdir "$evidence_root/natural_terminal"',
            )
        )
        return {
            "valid": (
                clean.returncode == 0
                and not bytecode
                and path_positive.returncode == 0
                and path_negative.returncode != 0
                and missing_present_before
                and missing.returncode != 0
                and first_preflight > namespace_create
                and cleanup_contract
                and missing_runner.returncode == 5
                and missing_runner_no_namespace
            ),
            "clean_preflight_exit": clean.returncode,
            "clean_preflight_stdout": clean.stdout[-1000:],
            "clean_preflight_stderr": clean.stderr[-1000:],
            "bytecode_artifact_count": len(bytecode),
            "path_budget_positive_exit": path_positive.returncode,
            "path_budget_negative_exit": path_negative.returncode,
            "missing_witness": MISSING_WITNESS.as_posix(),
            "missing_witness_present_before_negative": missing_present_before,
            "missing_member_negative_exit": missing.returncode,
            "missing_member_negative_stderr": missing.stderr[-1000:],
            "single_complete_preflight_after_empty_namespace_create": (
                first_preflight > namespace_create
            ),
            "failed_preflight_cleanup_contract": cleanup_contract,
            "missing_member_runner_exit": missing_runner.returncode,
            "missing_member_runner_stderr": missing_runner.stderr[-1000:],
            "missing_member_runner_left_candidate_namespace": (
                not missing_runner_no_namespace
            ),
        }


def workload_identity(
    v2_entries: dict[str, bytes],
) -> dict[str, Any]:
    v1_entries: dict[str, bytes] = {}
    errors: list[str] = []
    source_root = "r5_conv_native_four_lane_df23e4d_perf_v1/"
    with zipfile.ZipFile(SOURCE_V1_ZIP) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"source v1 ZIP CRC failure: {bad}")
        for info in archive.infolist():
            if info.is_dir():
                continue
            if not info.filename.startswith(source_root):
                errors.append(f"source v1 wrong root: {info.filename}")
                continue
            relative = info.filename[len(source_root) :]
            v1_entries[relative] = archive.read(info)
    prefix = "workload/runtime/"
    source = {
        path: payload
        for path, payload in v1_entries.items()
        if path.startswith(prefix)
    }
    successor = {
        path: payload
        for path, payload in v2_entries.items()
        if path.startswith(prefix)
    }
    missing = sorted(set(source) - set(successor))
    extra = sorted(set(successor) - set(source))
    def normalized_json(payload: bytes, install_name: str) -> bytes:
        value = json.loads(payload.decode("utf-8"))

        def normalize(item: Any) -> Any:
            if isinstance(item, str):
                return item.replace(install_name, "<INSTALL_NAME>")
            if isinstance(item, list):
                return [normalize(child) for child in item]
            if isinstance(item, dict):
                return {
                    key: normalize(child)
                    for key, child in sorted(item.items())
                }
            return item

        return json.dumps(
            normalize(value),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    changed: list[str] = []
    identity_normalized: list[str] = []
    for path in sorted(set(source) & set(successor)):
        if source[path] == successor[path]:
            continue
        if path.endswith(("/sca_cfg.json", "/sca_cfg_D.json")):
            source_normalized = normalized_json(
                source[path],
                "r5_conv_native_four_lane_df23e4d_perf_v1",
            )
            successor_normalized = normalized_json(
                successor[path], INSTALL_NAME
            )
            if source_normalized == successor_normalized:
                identity_normalized.append(path)
                continue
        changed.append(path)
    return {
        "valid": not errors and not missing and not extra and not changed,
        "source_zip_sha256": v1.sha256(SOURCE_V1_ZIP),
        "file_count": len(source),
        "byte_identical_count": len(source) - len(identity_normalized),
        "install_identity_normalized_json_count": len(identity_normalized),
        "missing": missing[:10],
        "extra": extra[:10],
        "changed": changed[:10],
    }


def validate(zip_path: Path, sidecar: Path) -> dict[str, Any]:
    _configure_v1()
    result = v1.validate(zip_path, sidecar)
    entries, zip_errors = v1.read_zip(zip_path)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    path_budget = path_budget_check(entries, manifest)
    path_negatives = path_budget_negative_controls(entries, manifest)
    extraction = extraction_controls(zip_path)
    workload = workload_identity(entries)
    delivery_checks = {
        "fresh_v2_identity": (
            manifest.get("install_name") == INSTALL_NAME
            and manifest.get("schema", "").endswith("server-package-v2")
        ),
        "path_budget_exact": path_budget["valid"],
        "path_budget_negatives_fail_closed": all(path_negatives.values()),
        "fresh_extract_and_missing_member_controls": extraction["valid"],
        "v1_v2_workload_byte_identity": workload["valid"],
        "source_zip_has_no_crc_or_root_error": not zip_errors,
    }
    delivery_errors = [
        f"v2 delivery check failed: {name}"
        for name, passed in delivery_checks.items()
        if not passed
    ]
    result["schema"] = (
        "conv-native-four-lane-df23e4d-final-zip-validation-v2"
    )
    result["delivery_successor_checks"] = delivery_checks
    result["path_length_budget_gate"] = path_budget
    result["path_length_negative_controls"] = path_negatives
    result["fresh_extraction_controls"] = extraction
    result["v1_v2_workload_identity"] = workload
    result["errors"].extend(delivery_errors)
    result["error_count"] = len(result["errors"])
    result["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] = not result["errors"]
    result["status"] = (
        "PACKAGE_READY_NOT_RUN"
        if not result["errors"]
        else "PACKAGE_VALIDATION_FAILED"
    )
    if (
        "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001"
        not in result["applicable_rule_ids"]
    ):
        result["applicable_rule_ids"].append(
            "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001"
        )
    result["claim_boundary"] = (
        "v2 delivery/extraction successor plus " + result["claim_boundary"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(
            args.zip.resolve(),
            args.sidecar.resolve(),
        )
        v1.write_json(args.output.resolve(), result)
    except Exception as error:
        print(f"validation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PACKAGE_READY_NOT_RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
