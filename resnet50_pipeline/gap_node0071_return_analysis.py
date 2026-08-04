from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_RETURN_SHA256 = (
    "f084ccbae33a1e998ed99047da4d8f98d22ed85895b7ed4457ac090449843205"
)
EXPECTED_RETURN_BYTES = 23237
EXPECTED_SOURCE_SHA256 = (
    "bb5818c4071eacd220c669941169e181b51018d0591d85d51b01f0a7bd732b74"
)
SOURCE_RELATIVE = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0071_gap_hw_v1.zip"
)
RETURN_ROOT = "r5_node0071_gap_hw_v1_return"
SOURCE_ROOT = "r5_node0071_gap_hw_v1"
EXPECTED_RETURN_MEMBERS = {
    f"{RETURN_ROOT}/RETURN_MANIFEST.json",
    f"{RETURN_ROOT}/config/sca_cfg.json",
    f"{RETURN_ROOT}/config/sca_cfg_D.json",
    f"{RETURN_ROOT}/evidence/compile_exit_status.txt",
    f"{RETURN_ROOT}/evidence/installed_preflight.json",
    f"{RETURN_ROOT}/evidence/PACKAGE_MANIFEST.json",
    f"{RETURN_ROOT}/evidence/runner_exit_status.txt",
    f"{RETURN_ROOT}/evidence/server_command.txt",
    f"{RETURN_ROOT}/evidence/SERVER_RESULT_GATE.json",
    f"{RETURN_ROOT}/evidence/simulation_exit_status.txt",
    f"{RETURN_ROOT}/logs/compile.log",
}


class GapNode0071ReturnAnalysisError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_members(archive: zipfile.ZipFile) -> list[str]:
    members: list[str] = []
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        pure = PurePosixPath(name)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in name
            or name in seen
            or (mode and stat.S_ISLNK(mode))
        ):
            raise GapNode0071ReturnAnalysisError(
                f"unsafe or duplicate ZIP member: {name}"
            )
        seen.add(name)
        if not info.is_dir():
            members.append(name)
    return members


def _json_bytes(payload: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise GapNode0071ReturnAnalysisError(
            f"cannot parse JSON member: {name}"
        ) from error
    if not isinstance(value, dict):
        raise GapNode0071ReturnAnalysisError(
            f"JSON member root is not an object: {name}"
        )
    return value


def _json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        payload = archive.read(name)
    except KeyError as error:
        raise GapNode0071ReturnAnalysisError(
            f"required ZIP member is absent: {name}"
        ) from error
    return _json_bytes(payload, name)


def _status(archive: zipfile.ZipFile, name: str) -> int:
    try:
        return int(archive.read(name).decode("ascii").strip())
    except (KeyError, UnicodeError, ValueError) as error:
        raise GapNode0071ReturnAnalysisError(
            f"cannot parse status member: {name}"
        ) from error


def _compile_divergence(text: str) -> dict[str, Any]:
    lines = text.splitlines()

    def line_number(pattern: str) -> int:
        match = next(
            (
                index
                for index, line in enumerate(lines)
                if pattern in line
            ),
            None,
        )
        if match is None:
            raise GapNode0071ReturnAnalysisError(
                f"compile log lacks signature: {pattern}"
            )
        return match + 1

    error_line = line_number("Error-[SFCOR] Source file cannot be opened")
    missing_name_line = line_number(
        'Source file "native_return_observer.svh" cannot be opened'
    )
    no_file_line = line_number("'No such file or directory'.")
    include_line = line_number('`include "native_return_observer.svh"')
    tb_location = next(
        (
            index + 1
            for index, line in enumerate(lines)
            if "tb_NDP_Top_new_phy.sv" in line
            and re.search(r"\b5854\b", line)
        ),
        None,
    )
    if tb_location is None:
        raise GapNode0071ReturnAnalysisError(
            "compile log lacks TB line 5854 location"
        )
    return {
        "classification": "PACKAGE_COMPILE_INCLUDE_PATH_MISSING",
        "compile_log_error_line": error_line,
        "compile_log_missing_name_line": missing_name_line,
        "compile_log_no_file_line": no_file_line,
        "compile_log_tb_location_line": tb_location,
        "compile_log_include_line": include_line,
        "reported_tb_line": 5854,
        "missing_include": "native_return_observer.svh",
        "simulation_started": False,
        "terminal_observed": False,
        "formal_readback_produced": False,
    }


def analyze_gap_node0071_return(
    project_root: Path, return_zip: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    supplied = return_zip.resolve()
    source = root / SOURCE_RELATIVE
    if not supplied.is_file() or not source.is_file():
        raise GapNode0071ReturnAnalysisError(
            "source package or return ZIP is absent"
        )
    return_sha = sha256_file(supplied)
    source_sha = sha256_file(source)
    if (
        supplied.stat().st_size != EXPECTED_RETURN_BYTES
        or return_sha != EXPECTED_RETURN_SHA256
    ):
        raise GapNode0071ReturnAnalysisError("return ZIP identity differs")
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise GapNode0071ReturnAnalysisError("source package identity differs")

    with zipfile.ZipFile(supplied) as returned:
        members = _safe_members(returned)
        if returned.testzip() is not None:
            raise GapNode0071ReturnAnalysisError("return ZIP CRC failed")
        if set(members) != EXPECTED_RETURN_MEMBERS:
            raise GapNode0071ReturnAnalysisError(
                "return ZIP exact member set differs"
            )
        return_manifest_name = f"{RETURN_ROOT}/RETURN_MANIFEST.json"
        return_manifest = _json(returned, return_manifest_name)
        records = return_manifest.get("files")
        if not isinstance(records, list) or len(records) != 10:
            raise GapNode0071ReturnAnalysisError(
                "return manifest record count differs"
            )
        declared: set[str] = set()
        for record in records:
            if (
                not isinstance(record, dict)
                or not isinstance(record.get("path"), str)
                or not isinstance(record.get("size_bytes"), int)
                or not isinstance(record.get("sha256"), str)
            ):
                raise GapNode0071ReturnAnalysisError(
                    "return manifest record differs"
                )
            member = f"{RETURN_ROOT}/{record['path']}"
            if member not in EXPECTED_RETURN_MEMBERS or member in declared:
                raise GapNode0071ReturnAnalysisError(
                    "return manifest path differs"
                )
            payload = returned.read(member)
            if (
                len(payload) != record["size_bytes"]
                or sha256_bytes(payload) != record["sha256"]
            ):
                raise GapNode0071ReturnAnalysisError(
                    f"return manifest receipt differs: {record['path']}"
                )
            declared.add(member)
        if declared != EXPECTED_RETURN_MEMBERS - {return_manifest_name}:
            raise GapNode0071ReturnAnalysisError(
                "return manifest exact-set differs"
            )
        required_missing = return_manifest.get("required_missing")
        if (
            return_manifest.get("status") != "incomplete"
            or return_manifest.get("allowlist_only") is not True
            or not isinstance(required_missing, list)
            or len(required_missing) != 48
        ):
            raise GapNode0071ReturnAnalysisError(
                "return incomplete/allowlist receipt differs"
            )

        evidence = f"{RETURN_ROOT}/evidence"
        package_manifest_bytes = returned.read(
            f"{evidence}/PACKAGE_MANIFEST.json"
        )
        package_manifest = _json_bytes(
            package_manifest_bytes, "returned PACKAGE_MANIFEST.json"
        )
        installed = _json(
            returned, f"{evidence}/installed_preflight.json"
        )
        compile_status = _status(
            returned, f"{evidence}/compile_exit_status.txt"
        )
        simulation_status = _status(
            returned, f"{evidence}/simulation_exit_status.txt"
        )
        runner_status = _status(
            returned, f"{evidence}/runner_exit_status.txt"
        )
        gate = _json(returned, f"{evidence}/SERVER_RESULT_GATE.json")
        compile_log = returned.read(
            f"{RETURN_ROOT}/logs/compile.log"
        ).decode("utf-8", "replace")
        divergence = _compile_divergence(compile_log)
        returned_sca = returned.read(f"{RETURN_ROOT}/config/sca_cfg.json")
        returned_sca_d = returned.read(f"{RETURN_ROOT}/config/sca_cfg_D.json")

    with zipfile.ZipFile(source) as packaged:
        source_members = _safe_members(packaged)
        if packaged.testzip() is not None:
            raise GapNode0071ReturnAnalysisError("source ZIP CRC failed")
        source_manifest_bytes = packaged.read(
            f"{SOURCE_ROOT}/TEST_PACKAGE_MANIFEST.json"
        )
        source_runner = packaged.read(
            f"{SOURCE_ROOT}/PREPARE_AND_RUN.sh"
        ).decode("utf-8")
        source_sca = packaged.read(
            f"{SOURCE_ROOT}/workload/sca_cfg.json"
        )
        source_sca_d = packaged.read(
            f"{SOURCE_ROOT}/workload/sca_cfg_D.json"
        )
        observer_members = [
            name
            for name in source_members
            if PurePosixPath(name).name == "native_return_observer.svh"
        ]
    if (
        package_manifest_bytes != source_manifest_bytes
        or returned_sca != source_sca
        or returned_sca_d != source_sca_d
    ):
        raise GapNode0071ReturnAnalysisError(
            "returned package/SCA identity differs from bound source package"
        )

    checks = gate.get("checks")
    if not isinstance(checks, list) or len(checks) != 48:
        raise GapNode0071ReturnAnalysisError(
            "server result readback check count differs"
        )
    missing = sum(record.get("status") == "missing" for record in checks)
    roles = {
        role: sum(
            record.get("status") == "missing"
            and record.get("role") == role
            for record in checks
        )
        for role in ("sum_int32", "scaled_fp32", "final_uint8")
    }
    conjunction = gate.get("result_gate_conjunction")
    expected_conjunction = {
        "compile_exit_status": 2,
        "simulation_exit_status": 125,
        "natural_completion": False,
        "loader_checks": {
            "sca_cfg_echo": False,
            "sca_cfg_d_echo": False,
            "no_cannot_open": True,
            "no_skip_matrix_readback": True,
            "no_softmax_fallback": True,
            "preload_count_exact": False,
            "formal_dump_count_exact": False,
        },
        "formal_readback_exact_set_complete": False,
        "missing_count_zero": False,
        "mismatch_count_zero": True,
        "all_terms_true": False,
    }
    if (
        installed.get("valid") is not True
        or installed.get("formal_readback_targets_absent") is not True
        or compile_status != 2
        or simulation_status != 125
        or runner_status != 2
        or gate.get("status") != "NODE0071_GAP_SERVER_FAILURE"
        or gate.get("readback_count") != 48
        or gate.get("missing_count") != 48
        or gate.get("mismatch_byte_count") != 0
        or missing != 48
        or roles
        != {"sum_int32": 16, "scaled_fp32": 16, "final_uint8": 16}
        or conjunction != expected_conjunction
    ):
        raise GapNode0071ReturnAnalysisError(
            "fail-closed result conjunction differs"
        )
    if (
        package_manifest.get("install_name") != SOURCE_ROOT
        or package_manifest.get("functional_rtl_modified") is not False
        or package_manifest.get("server_source_identity_bound") is not False
        or len(package_manifest.get("return_allowlist", [])) != 59
        or len(package_manifest.get("readback_checks", [])) != 48
        or observer_members
        or "VCS_EXTRA_OPTS" in source_runner
    ):
        raise GapNode0071ReturnAnalysisError(
            "source-package observer/claim boundary differs"
        )

    return {
        "schema": "resnet50-gap-node0071-hw-v1-return-analysis-v1",
        "status": "COMPILE_FAILED_NO_DYNAMIC_GAP_EVIDENCE",
        "return_identity": {
            "path": str(supplied),
            "size_bytes": supplied.stat().st_size,
            "sha256": return_sha,
            "identity_match": True,
            "sidecar_supplied": False,
            "sidecar_blocker": "RETURN_SIDECAR_NOT_PROVIDED",
            "zip_crc_valid": True,
            "file_count": len(members),
            "strict_allowlist_valid": True,
            "return_manifest_status": "incomplete",
            "required_missing_count": len(required_missing),
        },
        "bound_source_package": {
            "path": SOURCE_RELATIVE.as_posix(),
            "sha256": source_sha,
            "identity_match": True,
            "install_name": package_manifest["install_name"],
            "returned_package_manifest_byte_equal": True,
            "returned_sca_byte_equal": True,
            "returned_sca_d_byte_equal": True,
            "source_zip_observer_entry_count": len(observer_members),
            "source_compile_has_package_local_observer_incdir": False,
        },
        "execution_status": {
            "package_preflight_valid": (
                installed.get("package_preflight", {}).get("valid") is True
            ),
            "installed_preflight_valid": True,
            "runtime_readback_targets_absent_before_simulation": True,
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "runner_exit_status": runner_status,
            "simulation_started": False,
            "natural_completion": False,
            "terminal_observed": False,
            "formal_dynamic_readback_count": 0,
            "e3_e4_e5_claim_allowed": False,
        },
        "first_divergence": divergence,
        "fail_closed_adjudication": {
            "classification": "V1_RESULT_GATE_FAIL_CLOSED_CONFIRMED",
            "returned_status": gate["status"],
            "gate_conjunction": conjunction,
            "readback_check_count": len(checks),
            "missing_count": missing,
            "missing_by_role": roles,
            "mismatch_byte_count": 0,
            "returned_pass_is_dynamic_evidence": False,
        },
        "repair_adjudication": {
            "package_side_legal_fix_confirmed": True,
            "classification": "PACKAGE_LOCAL_OBSERVER_INCLUDE_BINDING_MISSING",
            "proof": (
                "The returned compile log proves an unconditional relative "
                "include of native_return_observer.svh. The bound source "
                "package has zero observer entries and passes no package-local "
                "observer include directory."
            ),
            "legal_fix": [
                "create a fresh package/install/run/return identity",
                "ship the frozen read-only observer under package-local tb_probe/",
                "hash/XMR-check the observer immediately before compile",
                "pass +incdir+<package_root>/tb_probe through VCS_EXTRA_OPTS",
                "return the precompile observer receipt via the exact allowlist",
            ],
            "server_file_write_required": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_tb_or_observer_install_required": False,
            "v2_package_authorized_by_return_evidence": True,
        },
        "endpoint_impact": {
            "node0071_complete_local_e2_preserved": True,
            "producer_storage_base_offset_coverage_preserved": True,
            "producer_visibility_lifetime_requirements_preserved": True,
            "dequant_consumer_section_still_missing": True,
            "integrated_endpoint_closed": False,
            "reason": (
                "Compilation failed before simulation; no returned evidence "
                "contradicts the accepted local producer endpoint."
            ),
        },
        "claim_boundary": {
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "server_files_outside_return_inspected": False,
            "compile_failure_is_not_gap_numeric_or_config_evidence": True,
            "complete_onnx_local_config_only_e2_count_remains": "3/78",
        },
    }


__all__ = [
    "GapNode0071ReturnAnalysisError",
    "analyze_gap_node0071_return",
]
