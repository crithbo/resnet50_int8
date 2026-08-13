#!/usr/bin/env python3
"""Independent final-ZIP audit for the p8f full-chain/320D successor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (  # noqa: E402
    build_conv_native_four_lane_0ccae916_p8f_full_package as build,
)
from tools import (  # noqa: E402
    validate_conv_native_four_lane_df23e4d_server_package as legacy,
)
from tools import (  # noqa: E402
    validate_conv_native_four_lane_df23e4d_server_package_v2 as path_v2,
)


INSTALL_NAME = build.INSTALL_NAME
PACKAGE_ZIP = build.OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR = Path(str(PACKAGE_ZIP) + ".sha256")
OUTPUT = build.OUTPUT_ROOT / f"{INSTALL_NAME}.final_zip_audit.json"
RUNTIME_REL = Path(
    "package_tools/node0004_assumed_hardware_server_runtime.py"
)
OBSERVER_REL = Path("tb_probe/native_return_observer.svh")
GUARD_REL = Path("package_tools/node0004_package_observer_guard.py")
LEAF_PATHS = {
    name: ROOT / "NDP_copy01/rtl" / value["path"].removeprefix("code/NDP_rtl/")
    for name, value in json.loads(
        build.CLOUD_AUDIT.read_text(encoding="utf-8")
    )["cloud_expected_compiled_leaves"].items()
}


class ValidationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def immutable_cloud_fixture(root: Path) -> dict[str, Path]:
    audit = json.loads(build.CLOUD_AUDIT.read_text(encoding="utf-8"))
    fixture = root / "cloud_0cc_leaves"
    fixture.mkdir()
    result: dict[str, Path] = {}
    git = shutil.which("git")
    if git is None:
        raise ValidationError("git unavailable for immutable cloud fixture")
    for basename, record in audit["cloud_expected_compiled_leaves"].items():
        process = subprocess.run(
            [
                git,
                "-c",
                "safe.directory="
                + str((ROOT / "Trassic2.0_RTL").resolve()).replace("\\", "/"),
                "-C",
                str(ROOT / "Trassic2.0_RTL"),
                "show",
                f"{build.CLOUD_COMMIT}:{record['path']}",
            ],
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            raise ValidationError(
                f"immutable cloud blob unavailable: {basename}"
            )
        target = fixture / basename
        target.write_bytes(process.stdout)
        if sha256(target) != record["sha256"]:
            raise ValidationError(
                f"immutable cloud blob identity differs: {basename}"
            )
        result[basename] = target
    return result


def run_runtime(
    package: Path, arguments: list[str]
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(package / RUNTIME_REL), *arguments],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=180,
        check=False,
    )


def read_zip(
    path: Path,
) -> tuple[dict[str, bytes], dict[str, dict[str, Any]], list[str]]:
    legacy.INSTALL_NAME = INSTALL_NAME
    entries, errors = legacy.read_zip(path)
    records = {
        relative: {"size_bytes": len(payload), "sha256": digest(payload)}
        for relative, payload in entries.items()
    }
    return entries, records, errors


def source_relation(entries: dict[str, bytes]) -> dict[str, Any]:
    source_entries: dict[str, bytes] = {}
    errors: list[str] = []
    with zipfile.ZipFile(build.SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            errors.append("source CRC failure")
        prefix = f"{build.SOURCE_NAME}/"
        for info in archive.infolist():
            if info.is_dir():
                continue
            if not info.filename.startswith(prefix):
                errors.append(f"wrong source root: {info.filename}")
                continue
            source_entries[info.filename[len(prefix) :]] = archive.read(info)

    workload_prefix = "workload/runtime/"
    source_workload = {
        path: payload
        for path, payload in source_entries.items()
        if path.startswith(workload_prefix)
    }
    target_workload = {
        path: payload
        for path, payload in entries.items()
        if path.startswith(workload_prefix)
    }

    def normalize(payload: bytes, identity: str) -> bytes:
        return payload.replace(identity.encode(), b"<INSTALL_NAME>")

    missing = sorted(set(source_workload) - set(target_workload))
    extra = sorted(set(target_workload) - set(source_workload))
    changed: list[str] = []
    normalized: list[str] = []
    for relative in sorted(set(source_workload) & set(target_workload)):
        source = source_workload[relative]
        target = target_workload[relative]
        if source == target:
            continue
        if normalize(source, build.SOURCE_NAME) == normalize(
            target, INSTALL_NAME
        ):
            normalized.append(relative)
        else:
            changed.append(relative)
    address_consumers = [
        relative
        for relative in sorted(source_workload)
        if (
            relative.endswith(".json")
            or "mapping" in relative
            or "execplan" in relative
            or "bitstream" in relative
        )
    ]
    address_consumer_mismatches = [
        relative
        for relative in address_consumers
        if relative not in target_workload
        or normalize(
            source_workload[relative], build.SOURCE_NAME
        )
        != normalize(target_workload[relative], INSTALL_NAME)
    ]
    observer_equal = (
        source_entries.get(OBSERVER_REL.as_posix())
        == entries.get(OBSERVER_REL.as_posix())
    )
    golden_paths = [
        path for path in source_entries if path.startswith("validation/golden/")
    ]
    golden_equal = all(
        entries.get(path) == source_entries[path] for path in golden_paths
    )
    return {
        "valid": (
            not errors
            and not missing
            and not extra
            and not changed
            and not address_consumer_mismatches
            and observer_equal
            and golden_equal
        ),
        "source_zip_sha256": sha256(build.SOURCE_ZIP),
        "workload_file_count": len(source_workload),
        "workload_byte_equal_count": len(source_workload) - len(normalized),
        "install_identity_normalized_count": len(normalized),
        "missing": missing,
        "extra": extra,
        "changed": changed,
        "address_consumer_count": len(address_consumers),
        "address_consumer_mismatches": address_consumer_mismatches,
        "observer_byte_equal": observer_equal,
        "golden_file_count": len(golden_paths),
        "golden_byte_equal": golden_equal,
        "numeric_w3_golden_repeated": False,
    }


def identity_controls(package: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="n4-p8f-id-") as name:
        root = Path(name)
        cloud_paths = immutable_cloud_fixture(root)
        compile_log = root / "compile.log"
        compile_log.write_text(
            "\n".join(
                f"Parsing design file '{path}'"
                for path in cloud_paths.values()
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        exact = run_runtime(
            package,
            [
                "compile-identity",
                "--compile-log",
                str(compile_log),
                "--output",
                str(root / "exact.json"),
            ],
        )
        exact_receipt = json.loads((root / "exact.json").read_text())

        copied = root / "copied"
        copied.mkdir()
        copied_paths: dict[str, Path] = {}
        for basename, source in cloud_paths.items():
            target = copied / basename
            shutil.copy2(source, target)
            copied_paths[basename] = target
        copied_paths["Array_Request_Manager.sv"].write_bytes(
            b"safe non-RTL identity-difference fixture\n"
        )
        arbitrary_log = root / "arbitrary.log"
        arbitrary_log.write_text(
            "\n".join(
                f"Parsing design file '{path}'"
                for path in copied_paths.values()
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        arbitrary = run_runtime(
            package,
            [
                "compile-identity",
                "--compile-log",
                str(arbitrary_log),
                "--output",
                str(root / "arbitrary.json"),
            ],
        )
        arbitrary_receipt = json.loads(
            (root / "arbitrary.json").read_text()
        )

        incomplete_log = root / "incomplete.log"
        incomplete_log.write_text(
            "\n".join(
                row
                for row in compile_log.read_text().splitlines()
                if "RD_Data_Channel.sv" not in row
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        incomplete = run_runtime(
            package,
            [
                "compile-identity",
                "--compile-log",
                str(incomplete_log),
                "--output",
                str(root / "incomplete.json"),
            ],
        )
        incomplete_receipt = json.loads(
            (root / "incomplete.json").read_text()
        )
    checks = {
        "exact_command_exit": exact.returncode == 0,
        "exact_collection_valid": exact_receipt["collection_valid"] is True,
        "actual_matches_cloud": (
            exact_receipt["actual_differs_cloud_authority"] is False
        ),
        "actual_differs_local_three": sorted(
            name
            for name, value in exact_receipt["leaves"].items()
            if not value["matches_local_provenance"]
        )
        == [
            "Array_Request_Manager.sv",
            "Buffer_AG_Idx_Queue.sv",
            "RD_Data_Channel.sv",
        ],
        "local_difference_nonblocking": (
            exact_receipt["identity_difference_blocks_simulator"] is False
        ),
        "arbitrary_command_exit": arbitrary.returncode == 0,
        "arbitrary_collection_valid": (
            arbitrary_receipt["collection_valid"] is True
        ),
        "arbitrary_cloud_difference_recorded": (
            arbitrary_receipt["actual_differs_cloud_authority"] is True
        ),
        "arbitrary_difference_nonblocking": (
            arbitrary_receipt["identity_difference_blocks_simulator"] is False
        ),
        "incomplete_command_returns_receipt": incomplete.returncode == 0,
        "incomplete_collection_invalid": (
            incomplete_receipt["collection_valid"] is False
        ),
        "incomplete_difference_nonblocking": (
            incomplete_receipt["identity_difference_blocks_simulator"] is False
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "exact_cloud_positive": exact_receipt,
        "arbitrary_actual_positive": arbitrary_receipt,
        "incomplete_collection": incomplete_receipt,
    }


def package_negative_controls(package: Path) -> dict[str, Any]:
    runtime = package / RUNTIME_REL
    manifest_path = package / "package_manifest.json"
    manifest_original = manifest_path.read_bytes()
    observer = package / OBSERVER_REL
    observer_original = observer.read_bytes()
    controls: dict[str, bool] = {}

    positive = run_runtime(
        package, ["preflight", "--package-root", str(package)]
    )
    controls["positive_preflight"] = positive.returncode == 0

    extra = package / "UNDECLARED_NEGATIVE_CONTROL"
    extra.write_bytes(b"x")
    controls["extra_file_fails"] = (
        run_runtime(
            package, ["preflight", "--package-root", str(package)]
        ).returncode
        != 0
    )
    extra.unlink()

    observer.unlink()
    controls["observer_deleted_fails"] = (
        run_runtime(
            package, ["preflight", "--package-root", str(package)]
        ).returncode
        != 0
    )
    observer.write_bytes(observer_original)

    manifest = json.loads(manifest_original)
    first = manifest["readback_checks"][0]
    runtime_d = package / "workload/runtime" / Path(
        *PurePosixPath(first["runtime_path"]).parts
    )
    golden = package / Path(*PurePosixPath(first["golden_path"]).parts)
    runtime_d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(golden, runtime_d)
    manifest["files"][runtime_d.relative_to(package).as_posix()] = {
        "size_bytes": runtime_d.stat().st_size,
        "sha256": sha256(runtime_d),
    }
    write_json(manifest_path, manifest)
    controls["preloaded_formal_d_fails"] = (
        run_runtime(
            package, ["preflight", "--package-root", str(package)]
        ).returncode
        != 0
    )
    runtime_d.unlink()
    manifest_path.write_bytes(manifest_original)

    observer.write_bytes(observer_original + b"\n")
    manifest = json.loads(manifest_original)
    manifest["files"][OBSERVER_REL.as_posix()] = {
        "size_bytes": observer.stat().st_size,
        "sha256": sha256(observer),
    }
    write_json(manifest_path, manifest)
    guard = subprocess.run(
        [
            sys.executable,
            "-B",
            str(package / GUARD_REL),
            "--package-root",
            str(package),
        ],
        cwd=package,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    controls["observer_manifest_binding_fails"] = guard.returncode != 0
    observer.write_bytes(observer_original)
    manifest_path.write_bytes(manifest_original)

    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    controls["runner_macro_delete_fails"] = not legacy.validate_runner(
        runner.replace("+define+NATIVE_RETURN_OBSERVER_ENABLE", "+define+REMOVED")
    )["valid"]
    controls["runner_incdir_delete_fails"] = not legacy.validate_runner(
        runner.replace(
            "+incdir+$package_root/tb_probe", "+incdir+$package_root/removed"
        )
    )["valid"]
    controls["runner_return_target_delete_fails"] = not legacy.validate_runner(
        runner.replace(
            "+RETURN_OBS_FILE=$observer_log", "+REMOVED_RETURN_TARGET"
        )
    )["valid"]
    return {"valid": all(controls.values()), "checks": controls}


def git_bash_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        f"/{resolved.drive[0].lower()}"
        f"{resolved.as_posix()[len(resolved.drive):]}"
    )


def msys_tmp_path(path: Path) -> str:
    resolved = path.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    try:
        relative = resolved.relative_to(temp_root)
    except ValueError as error:
        raise ValidationError(
            f"runner fixture path is outside system temp: {resolved}"
        ) from error
    return "/tmp/" + relative.as_posix()


def runner_cloud_difference_control(package: Path) -> dict[str, Any]:
    bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if not bash.is_file():
        raise ValidationError("Git Bash unavailable")
    with tempfile.TemporaryDirectory(prefix="n4-p8f-runner-") as name:
        root = Path(name)
        server = root / "server"
        stub_bin = root / "stub-bin"
        control = root / "control"
        server.mkdir()
        stub_bin.mkdir()
        control.mkdir()
        cloud_paths = immutable_cloud_fixture(root)
        sim_started = control / "sim-started"
        runner_stdout = control / "runner.stdout"
        runner_stderr = control / "runner.stderr"
        runner_status = control / "runner.status"

        python_stub = stub_bin / "python3"
        python_stub.write_text(
            "#!/usr/bin/env bash\n"
            f'exec "{git_bash_path(Path(sys.executable))}" -B "$@"\n',
            encoding="utf-8",
            newline="\n",
        )
        parsing_rows = "".join(
            f"printf '%s\\n' \"Parsing design file '{path.as_posix()}'\"\n"
            for path in cloud_paths.values()
        )
        make_stub = stub_bin / "make"
        make_stub.write_text(
            "#!/usr/bin/env bash\n"
            "set -u\n"
            "run_dir=\n"
            "for argument in \"$@\"; do\n"
            "  case \"$argument\" in RUN_DIR=*) "
            "run_dir=\"${argument#RUN_DIR=}\";; esac\n"
            "done\n"
            "[ -n \"$run_dir\" ] || exit 84\n"
            "mkdir -p \"$run_dir/sim_results\"\n"
            + parsing_rows
            + "printf '%s\\n' 'Compilation completed!' "
            "'0 error(s), 0 warning(s)'\n"
            + "cat >\"$run_dir/sim_results/simv\" <<'SAFE_SIM'\n"
            "#!/usr/bin/env bash\n"
            "set -u\n"
            "sim_log=\n"
            "observer_log=\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  case \"$1\" in\n"
            "    -l) shift; sim_log=\"$1\";;\n"
            "    +RETURN_OBS_FILE=*) observer_log=\"${1#*=}\";;\n"
            "  esac\n"
            "  shift\n"
            "done\n"
            "[ -n \"$sim_log\" ] || exit 82\n"
            "[ -n \"$observer_log\" ] || exit 83\n"
            "printf '%s\\n' '[RETURN_OBSERVER] enabled "
            "N4PERF_FEATURE_ENABLE_V1 feature=NATIVE4_PROGRESS enabled=1' "
            ">\"$sim_log\"\n"
            "printf '%s\\n' '# Conv native four-lane progress observer v1' "
            "'N4PERF_FEATURE_ENABLE_V1 feature=NATIVE4_PROGRESS enabled=1 "
            "heartbeat_cycles=262144 stall_window_cycles=1048576 "
            "expected_stages=1' >\"$observer_log\"\n"
            "printf '%s\\n' SAFE_SIM_STUB_STARTED >\"$MOCK_SIM_STARTED\"\n"
            "trap 'exit 143' HUP INT TERM\n"
            "while :; do sleep 1; done\n"
            "SAFE_SIM\n"
            "chmod +x \"$run_dir/sim_results/simv\"\n"
            "exit 0\n",
            encoding="utf-8",
            newline="\n",
        )
        os.chmod(python_stub, 0o755)
        os.chmod(make_stub, 0o755)
        harness = (
            'export PATH="$1:/usr/bin:/bin:/c/Windows/System32"\n'
            'export MOCK_SIM_STARTED="$6"\n'
            'cd "$2"\n'
            'bash PREPARE_AND_RUN.sh "$3" >"$4" 2>"$5" &\n'
            'pid=$!\n'
            'attempt=0\n'
            'while [ ! -f "$6" ] && [ "$attempt" -lt 1200 ]; do\n'
            '  sleep 0.05\n'
            '  attempt=$((attempt + 1))\n'
            'done\n'
            'if [ ! -f "$6" ]; then\n'
            '  kill -TERM "$pid" 2>/dev/null\n'
            '  wait "$pid" 2>/dev/null\n'
            '  printf "124\\n" >"$7"\n'
            '  exit 0\n'
            'fi\n'
            'kill -TERM "$pid"\n'
            'wait "$pid"\n'
            'printf "%s\\n" "$?" >"$7"\n'
            'exit 0\n'
        )
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.run(
            [
                str(bash),
                "--noprofile",
                "--norc",
                "-c",
                harness,
                "n4-p8f-runner-control",
                msys_tmp_path(stub_bin),
                msys_tmp_path(package),
                msys_tmp_path(server),
                msys_tmp_path(runner_stdout),
                msys_tmp_path(runner_stderr),
                msys_tmp_path(sim_started),
                msys_tmp_path(runner_status),
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
        status = (
            int(runner_status.read_text().strip())
            if runner_status.is_file()
            else None
        )
        return_zip = server / f"{INSTALL_NAME}_return.zip"
        sidecar = Path(str(return_zip) + ".sha256")
        identity: dict[str, Any] = {}
        result_gate: dict[str, Any] = {}
        exact_set = False
        sidecar_exact = False
        if return_zip.is_file() and sidecar.is_file():
            sidecar_exact = (
                sidecar.read_text(encoding="ascii")
                == f"{sha256(return_zip)}  {return_zip.name}\n"
            )
            with zipfile.ZipFile(return_zip) as archive:
                names = [name for name in archive.namelist() if not name.endswith("/")]
                root_name = PurePosixPath(names[0]).parts[0]
                relative = {
                    PurePosixPath(*PurePosixPath(name).parts[1:]).as_posix()
                    for name in names
                }
                allowlist = json.loads(
                    archive.read(f"{root_name}/RETURN_ALLOWLIST.json")
                )
                declared = {item["path"] for item in allowlist["records"]}
                exact_set = relative == declared | {"RETURN_ALLOWLIST.json"}
                identity = json.loads(
                    archive.read(
                        f"{root_name}/evidence/production_rtl_identity.json"
                    )
                )
                result_gate = json.loads(
                    archive.read(
                        f"{root_name}/evidence/SERVER_RESULT_GATE.json"
                    )
                )
        checks = {
            "harness_exit": process.returncode == 0,
            "simulator_stub_reached": sim_started.is_file(),
            "runner_signal_exit": status == 143,
            "return_zip_present": return_zip.is_file(),
            "return_sidecar_exact": sidecar_exact,
            "return_exact_allowlist": exact_set,
            "identity_collection_valid": identity.get("collection_valid") is True,
            "actual_differs_local": (
                identity.get("actual_differs_local_provenance") is True
            ),
            "actual_matches_cloud": (
                identity.get("actual_differs_cloud_authority") is False
            ),
            "identity_difference_nonblocking": (
                identity.get("identity_difference_blocks_simulator") is False
            ),
            "signal_finalizer_result": (
                result_gate.get("status")
                == "CONV_NATIVE_FOUR_LANE_SERVER_FAILURE"
            ),
        }
        return {
            "valid": all(checks.values()),
            "checks": checks,
            "runner_status": status,
            "production_identity": identity,
            "result_gate": result_gate,
            "stdout_tail": (
                runner_stdout.read_text(errors="replace")[-1000:]
                if runner_stdout.is_file()
                else ""
            ),
            "stderr_tail": (
                runner_stderr.read_text(errors="replace")[-1000:]
                if runner_stderr.is_file()
                else ""
            ),
        }


def validate(zip_path: Path, sidecar: Path) -> dict[str, Any]:
    entries, zip_records, zip_errors = read_zip(zip_path)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    expected_files = manifest.get("files", {})
    actual_files = {
        path: value
        for path, value in zip_records.items()
        if path != "package_manifest.json"
    }
    current_rules = {
        relative: {
            "expected_sha256": expected,
            "observed_sha256": (
                sha256(ROOT / relative)
                if (ROOT / relative).is_file()
                else None
            ),
        }
        for relative, expected in manifest.get("rule_receipts", {}).items()
    }
    for record in current_rules.values():
        record["match"] = (
            record["expected_sha256"] == record["observed_sha256"]
        )
    source = source_relation(entries)
    build_receipt = json.loads(
        (
            build.OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json"
        ).read_text(encoding="utf-8")
    )

    with tempfile.TemporaryDirectory(prefix="n4-p8f-audit-") as name:
        root = Path(name)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(root)
        package = root / INSTALL_NAME
        before = legacy.package_records(package)
        preflight = run_runtime(
            package, ["preflight", "--package-root", str(package)]
        )
        path_v2.INSTALL_NAME = INSTALL_NAME
        path_gate = path_v2.path_budget_check(entries, manifest)
        path_negatives = path_v2.path_budget_negative_controls(
            entries, manifest
        )
        sca = legacy.sca_closure(package, manifest)
        runner_static = legacy.validate_runner(
            (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        )
        observer = legacy.observer_scope(package, manifest)
        identity = identity_controls(package)
        negatives = package_negative_controls(package)
        runner_e2e = runner_cloud_difference_control(package)
        after = legacy.package_records(package)
        immutable = before == after

    sidecar_exact = (
        sidecar.read_text(encoding="ascii")
        == f"{sha256(zip_path)}  {zip_path.name}\n"
    )
    runtime_d_absent = all(
        f"workload/runtime/{item['runtime_path']}" not in entries
        for item in manifest["readback_checks"]
    )
    golden_present = all(
        item["golden_path"] in entries
        for item in manifest["readback_checks"]
    )
    checks = {
        "zip_crc_path_root_no_symlink": not zip_errors,
        "sidecar_exact": sidecar_exact,
        "manifest_exact_set_hashes": expected_files == actual_files,
        "current_rule_receipts": (
            bool(current_rules)
            and all(item["match"] for item in current_rules.values())
        ),
        "candidate_identity": (
            manifest.get("status") == "PACKAGE_READY_NOT_RUN"
            and manifest.get("candidate_release") is False
            and manifest.get("candidate_class")
            == "PERFORMANCE_DIAGNOSTIC_CANDIDATE"
        ),
        "full_run_and_formal_counts": (
            manifest.get("simulation_run_count") == 27
            and manifest.get("natural_terminal_required_count") == 27
            and manifest.get("formal_readback_count") == 320
            and len(manifest.get("readback_checks", [])) == 320
        ),
        "runtime_d_absent_golden_present": (
            runtime_d_absent and golden_present
        ),
        "no_functional_rtl": (
            manifest.get("functional_rtl_file_count") == 0
            and manifest.get("server_rtl_entries") == 0
        ),
        "runtime_preflight": preflight.returncode == 0,
        "path_budget": path_gate["valid"],
        "path_negatives_fail_closed": all(path_negatives.values()),
        "sca_execplan_consumer_closure": sca["valid"],
        "runner_static_binding": runner_static["valid"],
        "observer_focused_hdl_scope": observer["valid"],
        "identity_controls": identity["valid"],
        "package_negatives": negatives["valid"],
        "runner_cloud_diff_reaches_simulator": runner_e2e["valid"],
        "source_p4_content_neutral": source["valid"],
        "package_immutable_under_audit": immutable,
        "deterministic_dual_build": (
            build_receipt["deterministic_dual_build_byte_equal"] is True
            and build_receipt["zip_sha256"] == sha256(zip_path)
        ),
        "single_release_gate_matrix": (
            manifest.get("release_gate_matrix", {}).get("single_matrix") is True
        ),
    }
    blocking_failures = [
        name for name, passed in checks.items() if not passed
    ]
    release_gate_matrix = {
        "schema": "conv-native-four-lane-p8f-final-release-gate-matrix-v1",
        "valid": not blocking_failures,
        "gates": {
            "core_package_bootstrap_path_runtime_d": {
                "applicability": "blocking_applicable",
                "status": (
                    "PASS"
                    if all(
                        checks[name]
                        for name in (
                            "zip_crc_path_root_no_symlink",
                            "sidecar_exact",
                            "manifest_exact_set_hashes",
                            "current_rule_receipts",
                            "runtime_d_absent_golden_present",
                            "runtime_preflight",
                            "path_budget",
                            "path_negatives_fail_closed",
                            "deterministic_dual_build",
                        )
                    )
                    else "FAIL"
                ),
            },
            "runner_compile_finalizer": {
                "applicability": "blocking_applicable",
                "status": (
                    "PASS"
                    if checks["runner_static_binding"]
                    and checks["runner_cloud_diff_reaches_simulator"]
                    and checks["identity_controls"]
                    else "FAIL"
                ),
                "evidence": (
                    "actual 0cc bytes differ from local provenance for three "
                    "leaves and the exact final runner still starts simv"
                ),
            },
            "package_local_hdl": {
                "applicability": "blocking_applicable",
                "status": (
                    "PASS" if checks["observer_focused_hdl_scope"] else "FAIL"
                ),
            },
            "materialized_config": {
                "applicability": "receipt_reuse",
                "status": (
                    "PASS"
                    if checks["source_p4_content_neutral"]
                    and checks["sca_execplan_consumer_closure"]
                    else "FAIL"
                ),
                "transaction_ledger": "RECEIPT_REUSE_BYTE_EQUAL",
                "boundary_microtrace": "NOT_APPLICABLE_BYTE_EQUAL",
                "physical_bank_row_validity": "RECEIPT_REUSE_BYTE_EQUAL",
            },
            "observer_parser_canonical": {
                "applicability": "receipt_reuse",
                "status": (
                    "PASS" if source["observer_byte_equal"] else "FAIL"
                ),
                "predicate_trace": "NOT_APPLICABLE_BYTE_EQUAL",
            },
            "return_result_joint": {
                "applicability": "blocking_applicable",
                "status": (
                    "PASS"
                    if checks["runner_cloud_diff_reaches_simulator"]
                    and checks["package_negatives"]
                    else "FAIL"
                ),
                "formal_server_result": "PENDING_NOT_RUN",
            },
            "numeric_w3_golden": {
                "applicability": "record_only",
                "status": "PASS",
                "repeated": False,
            },
        },
        "blocking_failures": blocking_failures,
    }
    valid = all(checks.values()) and release_gate_matrix["valid"]
    return {
        "schema": "conv-native-four-lane-0ccae916-p8f-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "FAIL",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "package_release": "PACKAGE_READY_NOT_RUN" if valid else "NONE",
        "candidate_release": False,
        "errors": blocking_failures,
        "checks": checks,
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": sha256(zip_path),
        "sidecar": str(sidecar),
        "sidecar_sha256": sha256(sidecar),
        "package_file_count": len(entries),
        "current_rule_receipts": current_rules,
        "release_gate_matrix": release_gate_matrix,
        "source_p4_content_neutral_relation": source,
        "path_length_budget_gate": path_gate,
        "path_length_negative_controls": path_negatives,
        "sca_consumer_closure": sca,
        "observer_scope": observer,
        "identity_nonblocking_controls": identity,
        "package_negative_controls": negatives,
        "runner_cloud_difference_control": runner_e2e,
        "performance_occurrence_inversion": manifest.get(
            "actual_performance_inversion"
        ),
        "claim_boundary": {
            "local_package_release_only": True,
            "server_run_performed": False,
            "natural_terminal_claimed": False,
            "formal_320d_claimed": False,
            "performance_E3_E4_E5_claimed": False,
        },
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "confirmed": [
                "changed runner is blocking-applicable",
                "byte-equal config/address/observer uses receipt reuse",
                "actual/local/cloud identity difference is nonblocking",
                "formal result requires 27 natural terminals and 320/320 D",
            ],
            "rule_delta_proposal": [],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, default=PACKAGE_ZIP)
    parser.add_argument("--sidecar", type=Path, default=SIDECAR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        result = validate(args.zip.resolve(), args.sidecar.resolve())
        write_json(args.output.resolve(), result)
    except Exception as error:
        print(f"validation failed: {error}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PACKAGE_READY_NOT_RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
