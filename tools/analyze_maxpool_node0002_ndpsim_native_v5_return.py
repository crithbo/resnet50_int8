#!/usr/bin/env python3
"""Receipt-only analysis for the MaxPool node0002 native ndp-sim v5 return."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
RETURN_ZIP = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-08\r5_n2_maxpool_ndpsim_native_v5_return.zip"
)
SOURCE_ZIP = (
    WORKSPACE
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n2_maxpool_ndpsim_native_v5.zip"
)
SOURCE_SIDECAR = SOURCE_ZIP.with_suffix(SOURCE_ZIP.suffix + ".sha256")
SOURCE_JSON = (
    WORKSPACE
    / "ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json"
)

INSTALL_NAME = "r5_n2_maxpool_ndpsim_native_v5"
RUN_NAME = "run_r5_n2_maxpool_ndpsim_native_v5"
RETURN_NAME = "r5_n2_maxpool_ndpsim_native_v5_return"
SOURCE_JSON_SHA256 = (
    "a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1"
)
EXPECTED_RETURN_SHA256 = (
    "68265ded27f981d3ac448848baae2658ee15710c947155c8ed69dd9fa78fb1dc"
)
EXPECTED_SOURCE_SHA256 = (
    "9a193d8f97d7b43d7e43886a2bc42dffee74e585832f5360a13a8ead2fa7269e"
)

CONTROL_FILES = {
    "agent": ".agents/agent.md",
    "plan_mutable": ".agents/plan.md",
    "index": ".agents/rules/生成前必读索引.md",
    "server_rule": ".agents/rules/服务器测试包生成规则.md",
    "common_operator_rule": ".agents/rules/算子配置规则.md",
    "ndp_field_rule": ".agents/rules/NDP硬件字段语义.md",
    "hardware_readme": "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
    "source_task_record": (
        ".agents/task_records/20260803_maxpool_node0002_ndpsim_native_v5_package.md"
    ),
    "source_release_report": (
        "artifacts/operator_config_validation/"
        "r5-maxpool-node0002-ndpsim-native-v5/report.json"
    ),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json_bytes(data: bytes) -> Any:
    return json.loads(data.decode("utf-8"))


def safe_member_name(name: str) -> bool:
    if not name or "\\" in name or name.startswith("/"):
        return False
    parts = PurePosixPath(name).parts
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def zip_audit(archive: zipfile.ZipFile) -> dict[str, Any]:
    infos = archive.infolist()
    names = [item.filename for item in infos]
    normalized = [PurePosixPath(name).as_posix() for name in names]
    unsafe = [name for name in names if not safe_member_name(name)]
    duplicates = sorted(
        {name for name in normalized if normalized.count(name) > 1}
    )
    symlinks = [
        item.filename
        for item in infos
        if stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK
    ]
    roots = sorted({PurePosixPath(name).parts[0] for name in names if name})
    return {
        "crc_error": archive.testzip(),
        "member_count": len(infos),
        "unsafe_paths": unsafe,
        "duplicate_paths": duplicates,
        "symlink_paths": symlinks,
        "roots": roots,
        "compressed_bytes": sum(item.compress_size for item in infos),
        "uncompressed_bytes": sum(item.file_size for item in infos),
    }


def text(archive: zipfile.ZipFile, member: str) -> str:
    return archive.read(member).decode("utf-8", "replace")


def parse_status(archive: zipfile.ZipFile, root: str, name: str) -> int:
    return int(text(archive, root + "evidence/" + name).strip())


def analyze() -> dict[str, Any]:
    errors: list[str] = []
    control_receipts = {
        name: {
            "path": relative,
            "sha256": sha256_path(WORKSPACE / relative),
            "bytes": (WORKSPACE / relative).stat().st_size,
        }
        for name, relative in CONTROL_FILES.items()
    }

    return_sha = sha256_path(RETURN_ZIP)
    source_sha = sha256_path(SOURCE_ZIP)
    source_json_sha = sha256_path(SOURCE_JSON)
    if return_sha != EXPECTED_RETURN_SHA256:
        errors.append("return ZIP SHA256 mismatch")
    if source_sha != EXPECTED_SOURCE_SHA256:
        errors.append("source ZIP SHA256 mismatch")
    if source_json_sha != SOURCE_JSON_SHA256:
        errors.append("authoritative source JSON SHA256 mismatch")

    adjacent_candidates = [
        RETURN_ZIP.with_suffix(RETURN_ZIP.suffix + ".sha256"),
        RETURN_ZIP.with_suffix(".zip.sha256"),
    ]
    adjacent_sidecar_present = any(path.is_file() for path in adjacent_candidates)

    with zipfile.ZipFile(RETURN_ZIP) as returned, zipfile.ZipFile(
        SOURCE_ZIP
    ) as source:
        return_zip_audit = zip_audit(returned)
        source_zip_audit = zip_audit(source)
        if return_zip_audit["crc_error"] is not None:
            errors.append("return ZIP CRC failure")
        if return_zip_audit["unsafe_paths"]:
            errors.append("return ZIP unsafe path")
        if return_zip_audit["duplicate_paths"]:
            errors.append("return ZIP duplicate path")
        if return_zip_audit["symlink_paths"]:
            errors.append("return ZIP symlink")
        if return_zip_audit["roots"] != [RETURN_NAME]:
            errors.append("return ZIP root identity mismatch")

        return_root = RETURN_NAME + "/"
        source_root = INSTALL_NAME + "/"
        manifest_member = return_root + "RETURN_MANIFEST.json"
        returned_manifest_member = (
            return_root + "package/TEST_PACKAGE_MANIFEST.json"
        )
        source_manifest_member = source_root + "TEST_PACKAGE_MANIFEST.json"
        return_manifest = load_json_bytes(returned.read(manifest_member))
        package_manifest = load_json_bytes(returned.read(returned_manifest_member))
        source_manifest_bytes = source.read(source_manifest_member)
        package_manifest_bytes = returned.read(returned_manifest_member)

        records = return_manifest.get("files", [])
        record_paths = [str(item.get("path")) for item in records]
        actual_paths = sorted(
            member[len(return_root) :]
            for member in returned.namelist()
            if member != manifest_member
        )
        exact_set = sorted(record_paths) == actual_paths
        if not exact_set:
            errors.append("RETURN_MANIFEST exact-set mismatch")

        receipt_mismatches: list[dict[str, Any]] = []
        for item in records:
            relative = str(item["path"])
            payload = returned.read(return_root + relative)
            observed = {
                "path": relative,
                "size_bytes": len(payload),
                "sha256": sha256_bytes(payload),
            }
            if (
                observed["size_bytes"] != int(item["size_bytes"])
                or observed["sha256"] != str(item["sha256"])
            ):
                receipt_mismatches.append(observed)
        if receipt_mismatches:
            errors.append("RETURN_MANIFEST per-file receipt mismatch")

        package_manifest_equal = package_manifest_bytes == source_manifest_bytes
        if not package_manifest_equal:
            errors.append("returned/source package manifest byte mismatch")

        identity = {
            "install_name": package_manifest.get("install_name"),
            "run_name": package_manifest.get("run_name"),
            "return_name": package_manifest.get("return", {}).get("name"),
            "return_zip": package_manifest.get("return", {}).get("zip"),
            "return_manifest_install_name": return_manifest.get(
                "package_install_name"
            ),
            "return_manifest_return_name": return_manifest.get("return_name"),
        }
        identity_expected = {
            "install_name": INSTALL_NAME,
            "run_name": RUN_NAME,
            "return_name": RETURN_NAME,
            "return_zip": RETURN_NAME + ".zip",
            "return_manifest_install_name": INSTALL_NAME,
            "return_manifest_return_name": RETURN_NAME,
        }
        identity_match = identity == identity_expected
        if not identity_match:
            errors.append("package/install/run/return identity mismatch")

        source_sca_member = source_root + "workload/native/sca_cfg.json"
        source_sca_d_member = source_root + "workload/native/sca_cfg_D.json"
        returned_sca_member = return_root + "config/sca_cfg.json"
        returned_sca_d_member = return_root + "config/sca_cfg_D.json"
        sca_bytes_equal = (
            source.read(source_sca_member) == returned.read(returned_sca_member)
        )
        sca_d_bytes_equal = (
            source.read(source_sca_d_member) == returned.read(returned_sca_d_member)
        )
        if not sca_bytes_equal or not sca_d_bytes_equal:
            errors.append("returned/source SCA identity mismatch")
        sca = load_json_bytes(returned.read(returned_sca_member))
        sca_d = load_json_bytes(returned.read(returned_sca_d_member))

        package_preflight = load_json_bytes(
            returned.read(return_root + "evidence/package_preflight.json")
        )
        installed_preflight = load_json_bytes(
            returned.read(return_root + "evidence/installed_preflight.json")
        )
        result_gate = load_json_bytes(
            returned.read(return_root + "evidence/SERVER_RESULT_GATE.json")
        )
        finalizer_status = load_json_bytes(
            returned.read(return_root + "evidence/finalizer_status.json")
        )

        compile_status = parse_status(
            returned, return_root, "compile_exit_status.txt"
        )
        simulation_status = parse_status(
            returned, return_root, "simulation_exit_status.txt"
        )
        runner_status = parse_status(returned, return_root, "runner_exit_status.txt")
        termination_signal = text(
            returned, return_root + "evidence/termination_signal.txt"
        ).strip()
        actual_compile_argv = text(
            returned, return_root + "evidence/actual_compile_argv.txt"
        ).strip()
        actual_simulator_argv = text(
            returned, return_root + "evidence/actual_simulator_argv.txt"
        ).strip()
        sim_log = text(returned, return_root + "logs/sim_tail.log")
        compile_log = text(returned, return_root + "logs/compile_driver_tail.log")

        expected_cfg = (
            f"/install/cfg_pkg/{INSTALL_NAME}/sca_cfg.json"
        )
        expected_cfg_d = (
            f"/install/cfg_pkg/{INSTALL_NAME}/sca_cfg_D.json"
        )
        argv_binding = {
            "compile_run_name": RUN_NAME in actual_compile_argv,
            "simulator_run_name": RUN_NAME in actual_simulator_argv,
            "sca_cfg": expected_cfg in actual_simulator_argv,
            "sca_cfg_d": expected_cfg_d in actual_simulator_argv,
        }
        if not all(argv_binding.values()):
            errors.append("actual compile/simulator argv identity binding mismatch")

        markers = {
            "compile_completed": "Compilation completed!" in compile_log,
            "matrices_loaded_30": "JSON config: 30 matrices loaded" in sim_log,
            "exec_identity": (
                "JSON config: Exec_Base=0x0003d800 Exec_Length=29" in sim_log
            ),
            "reg_started": "Reg Started." in sim_log,
            "slice_start": "INFO: slice start" in sim_log,
            "slice_completed": "INFO: slice completed after" in sim_log,
            "simulation_completed": (
                "Simulation completed successfully!" in sim_log
            ),
            "interrupt": "Interrupt at time" in sim_log,
        }
        simulation_started = (
            markers["matrices_loaded_30"]
            and markers["reg_started"]
            and markers["slice_start"]
        )
        natural_terminal = (
            markers["slice_completed"] and markers["simulation_completed"]
        )
        start_match = re.search(r"\[(\d+)\] INFO: slice start", sim_log)
        interrupt_match = re.search(r"Interrupt at time (\d+)", sim_log)
        start_ps = int(start_match.group(1)) if start_match else None
        interrupt_ps = int(interrupt_match.group(1)) if interrupt_match else None
        post_start_ps = (
            interrupt_ps - start_ps
            if start_ps is not None and interrupt_ps is not None
            else None
        )

        formal_members = sorted(
            path
            for path in actual_paths
            if path.startswith("formal_readback/") and path.endswith(".txt")
        )
        formal = result_gate.get("formal_readback", {})
        formal_summary = {
            "expected_count": int(formal.get("expected_count", -1)),
            "present_count": int(formal.get("present_count", -1)),
            "missing_count": int(formal.get("missing_count", -1)),
            "invalid_count": int(formal.get("invalid_count", -1)),
            "mismatch_byte_count": formal.get("mismatch_byte_count"),
            "returned_members": formal_members,
            "all_missing_mismatch_is_evaluable": False,
        }
        if (
            formal_summary["expected_count"] != 28
            or formal_summary["present_count"] != len(formal_members)
            or formal_summary["missing_count"] != 28 - len(formal_members)
        ):
            errors.append("formal readback summary inconsistency")

        preflight_valid = bool(
            package_preflight.get("valid")
            and installed_preflight.get("valid")
            and package_preflight.get("runtime_D_initially_absent")
            and installed_preflight.get("runtime_D_initially_absent")
            and package_preflight.get("source_json_sha256")
            == SOURCE_JSON_SHA256
            and installed_preflight.get("source_json_sha256")
            == SOURCE_JSON_SHA256
        )
        if not preflight_valid:
            errors.append("package/install preflight invalid")

        finalizer_valid = bool(
            finalizer_status.get("finalizer_entered") is True
            and int(finalizer_status.get("original_status", -1)) == runner_status
            and int(finalizer_status.get("analysis_status", -1)) == 0
            and termination_signal == "INT"
        )
        if not finalizer_valid:
            errors.append("EXIT/signal finalizer receipt mismatch")

        gate_consistent = bool(
            result_gate.get("result_gate") is False
            and result_gate.get("natural_terminal") is False
            and int(result_gate.get("compile_exit_status", -1)) == compile_status
            and int(result_gate.get("simulation_exit_status", -1))
            == simulation_status
            and bool(result_gate.get("user_override_native_path"))
            and result_gate.get("source_json_sha256") == SOURCE_JSON_SHA256
        )
        if not gate_consistent:
            errors.append("SERVER_RESULT_GATE inconsistency")

    source_sidecar_valid = False
    source_sidecar_content = None
    if SOURCE_SIDECAR.is_file():
        source_sidecar_content = SOURCE_SIDECAR.read_text(encoding="utf-8").strip()
        source_sidecar_valid = (
            EXPECTED_SOURCE_SHA256 in source_sidecar_content
            and SOURCE_ZIP.name in source_sidecar_content
        )
    if not source_sidecar_valid:
        errors.append("source ZIP sidecar invalid")

    e3 = False
    e4 = False
    e5 = False
    functional_root_cause = (
        "DEFERRED_BY_USER_NATIVE_REUSE_OVERRIDE:"
        "NATIVE_EXECUTION_INTERRUPTED_AFTER_SLICE_START_WITHOUT_NATURAL_TERMINAL"
    )

    return {
        "schema": "maxpool-node0002-ndpsim-native-v5-return-analysis-v1",
        "provenance": {
            "analysis_owner_thread": "019fbe9f-3f2d-7071-806c-1ae72ae96391",
            "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
            "analysis_mode": "RECEIPT_ONLY_NATIVE_NDPSIM_USER_OVERRIDE",
            "numeric_analysis_repeated": False,
            "rtl_analysis_repeated": False,
            "mapping_or_workload_rebuilt": False,
            "server_action": False,
            "control_receipts": control_receipts,
        },
        "identity": {
            "return_zip": str(RETURN_ZIP),
            "return_bytes": RETURN_ZIP.stat().st_size,
            "return_sha256": return_sha,
            "return_adjacent_sidecar_present": adjacent_sidecar_present,
            "return_transport": (
                "USER_ATTESTED_NO_SIDECAR_EXTERNAL_RECEIPT_ONLY"
            ),
            "source_zip": str(SOURCE_ZIP.relative_to(WORKSPACE)),
            "source_bytes": SOURCE_ZIP.stat().st_size,
            "source_sha256": source_sha,
            "source_sidecar_valid": source_sidecar_valid,
            "source_json": str(SOURCE_JSON.relative_to(WORKSPACE)),
            "source_json_sha256": source_json_sha,
            "package_install_run_return_identity": identity,
            "identity_match": identity_match,
        },
        "return_receipt": {
            "zip_audit": return_zip_audit,
            "source_zip_audit": source_zip_audit,
            "return_manifest_schema": return_manifest.get("schema"),
            "return_manifest_status": return_manifest.get("status"),
            "return_manifest_required_missing": return_manifest.get(
                "required_missing"
            ),
            "return_manifest_record_count": len(records),
            "return_exact_set": exact_set,
            "return_receipt_mismatches": receipt_mismatches,
            "returned_source_manifest_byte_equal": package_manifest_equal,
            "sca_byte_equal": sca_bytes_equal,
            "sca_d_byte_equal": sca_d_bytes_equal,
            "sca_count": len(sca),
            "sca_d_count": len(sca_d),
        },
        "runtime_binding": {
            "package_preflight": package_preflight,
            "installed_preflight": installed_preflight,
            "preflight_valid": preflight_valid,
            "actual_compile_argv": actual_compile_argv,
            "actual_simulator_argv": actual_simulator_argv,
            "argv_binding": argv_binding,
            "finalizer_status": finalizer_status,
            "finalizer_valid": finalizer_valid,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "runner_exit_status": runner_status,
            "termination_signal": termination_signal,
            "simulation_started": simulation_started,
            "natural_terminal": natural_terminal,
            "markers": markers,
            "slice_start_sim_time_ps": start_ps,
            "interrupt_sim_time_ps": interrupt_ps,
            "post_slice_start_sim_time_ps": post_start_ps,
            "wall_time_seconds": None,
            "wall_time_evidence_present": False,
            "server_result_gate": result_gate,
            "server_result_gate_consistent": gate_consistent,
        },
        "formal_readback": formal_summary,
        "last_proven_good": (
            "COMPILE_PASS_TO_30_NATIVE_MATRICES_LOADED_TO_REG_STARTED_TO_SLICE_START"
        ),
        "first_divergence": (
            "SLICE_START_TO_NO_NATIVE_SLICE_COMPLETION_OR_FORMAL_D_BEFORE_EXTERNAL_INT"
        ),
        "root_cause_adjudication": {
            "classification": functional_root_cause,
            "package_infrastructure_failure": False,
            "functional_config_or_rtl_root_cause_proven": False,
            "hang_proven": False,
            "slow_or_incomplete_proven": False,
            "reason": (
                "The native package has no generic progress observer by explicit "
                "user override, and the return contains no wall-clock or qualified "
                "post-start progress evidence. It proves interruption before "
                "terminal/readback, not a unique config or RTL defect."
            ),
        },
        "e3_e4_e5": {
            "E3": e3,
            "E4": e4,
            "E5": e5,
            "boundary": (
                "User-confirmed reuse authority does not substitute for this run's "
                "natural terminal, exact D readback, or server source identity."
            ),
        },
        "blocker_delta": {
            "closed": [
                "V5_RETURN_INTERNAL_RECEIPT_AND_IDENTITY",
                "V5_PACKAGE_INSTALL_PREFLIGHT",
                "V5_COMPILE_AND_NATIVE_EXECUTION_START",
                "V5_EXIT_INT_FINALIZER_AND_PARTIAL_RETURN",
            ],
            "open": [
                "V5_NATIVE_NATURAL_TERMINAL_ABSENT",
                "V5_FORMAL_D_28_OF_28_MISSING",
                "V5_SERVER_SOURCE_IDENTITY_UNBOUND_FOR_E4_E5",
            ],
            "terminal_disposition": (
                "DEFERRED_BY_USER_NATIVE_REUSE_OVERRIDE"
            ),
        },
        "package_release": {
            "successor_generated": False,
            "status": "NONE",
            "reason": (
                "No package-local infrastructure defect was found. The remaining "
                "dynamic failure is inside the native execution boundary, which the "
                "user override explicitly forbids re-diagnosing or wrapping with a "
                "generic successor."
            ),
        },
        "valid_internal_receipt_analysis": not errors,
        "errors": errors,
    }


def main() -> int:
    report = analyze()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["valid_internal_receipt_analysis"] else 1


if __name__ == "__main__":
    sys.exit(main())
