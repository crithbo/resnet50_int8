from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_RETURN_SHA256 = (
    "6855ed551940a460dc06414a007f48d88a4abe5a4275e8ae268246e2527ec558"
)
EXPECTED_RETURN_BYTES = 25437
EXPECTED_SOURCE_SHA256 = (
    "c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f"
)
EXPECTED_OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
SOURCE_RELATIVE = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v2_obs.zip"
)
SOURCE_SIDECAR_RELATIVE = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v2_obs.zip.sha256"
)
RETURN_ROOT = "r5_n71_gap_v2_obs_return"
SOURCE_ROOT = "r5_n71_gap_v2_obs"
EXPECTED_RETURN_MEMBERS = {
    f"{RETURN_ROOT}/RETURN_MANIFEST.json",
    f"{RETURN_ROOT}/config/sca_cfg.json",
    f"{RETURN_ROOT}/config/sca_cfg_D.json",
    f"{RETURN_ROOT}/evidence/PACKAGE_MANIFEST.json",
    f"{RETURN_ROOT}/evidence/SERVER_RESULT_GATE.json",
    f"{RETURN_ROOT}/evidence/compile_exit_status.txt",
    f"{RETURN_ROOT}/evidence/installed_preflight.json",
    f"{RETURN_ROOT}/evidence/observer_precompile.json",
    f"{RETURN_ROOT}/evidence/runner_exit_status.txt",
    f"{RETURN_ROOT}/evidence/server_command.txt",
    f"{RETURN_ROOT}/evidence/simulation_exit_status.txt",
    f"{RETURN_ROOT}/logs/compile.log",
}


class GapNode0071V2ReturnAnalysisError(ValueError):
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
            raise GapNode0071V2ReturnAnalysisError(
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
        raise GapNode0071V2ReturnAnalysisError(
            f"cannot parse JSON member: {name}"
        ) from error
    if not isinstance(value, dict):
        raise GapNode0071V2ReturnAnalysisError(
            f"JSON member root is not an object: {name}"
        )
    return value


def _json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        return _json_bytes(archive.read(name), name)
    except KeyError as error:
        raise GapNode0071V2ReturnAnalysisError(
            f"required ZIP member is absent: {name}"
        ) from error


def _status(archive: zipfile.ZipFile, name: str) -> int:
    try:
        return int(archive.read(name).decode("ascii").strip())
    except (KeyError, UnicodeError, ValueError) as error:
        raise GapNode0071V2ReturnAnalysisError(
            f"cannot parse status member: {name}"
        ) from error


def _first_divergence(text: str) -> dict[str, Any]:
    lines = text.splitlines()

    def line_number(pattern: str) -> int:
        match = next(
            (
                index + 1
                for index, line in enumerate(lines)
                if pattern in line
            ),
            None,
        )
        if match is None:
            raise GapNode0071V2ReturnAnalysisError(
                f"compile log lacks signature: {pattern}"
            )
        return match

    observer_line = line_number(
        "/r5_n71_gap_v2_obs/tb_probe/native_return_observer.svh"
    )
    error_line = line_number(
        "Error-[UPIMI-E] Undefined port in module instantiation"
    )
    rtl_location_line = line_number("SA_PE_ALU/SA_ALU.v, 124")
    port_line = line_number('Port "slice_rst" is not defined')
    module_line = line_number("module 'SA_PE_Mul_Array'")
    instance_line = line_number(
        "Module instance: SA_PE_Mul_Array u_SA_PE_Mul_Array"
    )
    compile_summary_line = line_number("1 error")
    if not (
        observer_line
        < error_line
        <= rtl_location_line
        <= port_line
        <= module_line
        <= instance_line
        <= compile_summary_line
    ):
        raise GapNode0071V2ReturnAnalysisError(
            "compile divergence line ordering differs"
        )
    return {
        "classification": "SERVER_RTL_PORT_INTERFACE_MISMATCH_BEFORE_SIMULATION",
        "observer_include_parsed_line": observer_line,
        "compile_log_error_line": error_line,
        "rtl_location_line": rtl_location_line,
        "undefined_port_line": port_line,
        "module_definition_line": module_line,
        "module_instance_line": instance_line,
        "compile_summary_line": compile_summary_line,
        "reported_rtl_location": "SA_PE_ALU/SA_ALU.v:124",
        "instance_module": "SA_PE_Mul_Array",
        "undefined_port": "slice_rst",
        "simulation_started": False,
        "terminal_observed": False,
        "formal_readback_produced": False,
    }


def _validate_return_manifest(
    archive: zipfile.ZipFile, manifest: dict[str, Any]
) -> list[str]:
    records = manifest.get("files")
    if not isinstance(records, list) or len(records) != 11:
        raise GapNode0071V2ReturnAnalysisError(
            "return manifest record count differs"
        )
    manifest_name = f"{RETURN_ROOT}/RETURN_MANIFEST.json"
    declared: set[str] = set()
    for record in records:
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("path"), str)
            or not isinstance(record.get("size_bytes"), int)
            or not isinstance(record.get("sha256"), str)
        ):
            raise GapNode0071V2ReturnAnalysisError(
                "return manifest record differs"
            )
        member = f"{RETURN_ROOT}/{record['path']}"
        if member not in EXPECTED_RETURN_MEMBERS or member in declared:
            raise GapNode0071V2ReturnAnalysisError(
                "return manifest path differs"
            )
        payload = archive.read(member)
        if (
            len(payload) != record["size_bytes"]
            or sha256_bytes(payload) != record["sha256"]
        ):
            raise GapNode0071V2ReturnAnalysisError(
                f"return manifest receipt differs: {record['path']}"
            )
        declared.add(member)
    if declared != EXPECTED_RETURN_MEMBERS - {manifest_name}:
        raise GapNode0071V2ReturnAnalysisError(
            "return manifest exact-set differs"
        )
    required_missing = manifest.get("required_missing")
    if (
        manifest.get("schema")
        != "gap-node0071-complete-return-manifest-v1"
        or manifest.get("install_name") != SOURCE_ROOT
        or manifest.get("status") != "incomplete"
        or manifest.get("allowlist_only") is not True
        or not isinstance(required_missing, list)
        or len(required_missing) != 48
        or len(set(required_missing)) != 48
    ):
        raise GapNode0071V2ReturnAnalysisError(
            "return incomplete/allowlist receipt differs"
        )
    return required_missing


def analyze_gap_node0071_v2_return(
    project_root: Path, return_zip: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    supplied = return_zip.resolve()
    source = root / SOURCE_RELATIVE
    sidecar = root / SOURCE_SIDECAR_RELATIVE
    if not supplied.is_file() or not source.is_file() or not sidecar.is_file():
        raise GapNode0071V2ReturnAnalysisError(
            "source package, sidecar, or return ZIP is absent"
        )
    return_sha = sha256_file(supplied)
    source_sha = sha256_file(source)
    if (
        supplied.stat().st_size != EXPECTED_RETURN_BYTES
        or return_sha != EXPECTED_RETURN_SHA256
    ):
        raise GapNode0071V2ReturnAnalysisError("return ZIP identity differs")
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise GapNode0071V2ReturnAnalysisError("source package identity differs")
    expected_sidecar = f"{EXPECTED_SOURCE_SHA256}  {source.name}\n"
    sidecar_text = sidecar.read_text(encoding="ascii")
    if sidecar_text != expected_sidecar:
        raise GapNode0071V2ReturnAnalysisError("source sidecar differs")

    with zipfile.ZipFile(supplied) as returned:
        members = _safe_members(returned)
        if returned.testzip() is not None:
            raise GapNode0071V2ReturnAnalysisError("return ZIP CRC failed")
        if set(members) != EXPECTED_RETURN_MEMBERS:
            raise GapNode0071V2ReturnAnalysisError(
                "return ZIP exact member set differs"
            )
        return_manifest = _json(
            returned, f"{RETURN_ROOT}/RETURN_MANIFEST.json"
        )
        required_missing = _validate_return_manifest(
            returned, return_manifest
        )
        evidence = f"{RETURN_ROOT}/evidence"
        package_manifest_bytes = returned.read(
            f"{evidence}/PACKAGE_MANIFEST.json"
        )
        package_manifest = _json_bytes(
            package_manifest_bytes, "returned PACKAGE_MANIFEST.json"
        )
        returned_sca = returned.read(f"{RETURN_ROOT}/config/sca_cfg.json")
        returned_sca_d = returned.read(
            f"{RETURN_ROOT}/config/sca_cfg_D.json"
        )
        installed = _json(
            returned, f"{evidence}/installed_preflight.json"
        )
        observer_receipt = _json(
            returned, f"{evidence}/observer_precompile.json"
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
        divergence = _first_divergence(compile_log)

    with zipfile.ZipFile(source) as packaged:
        source_members = _safe_members(packaged)
        if packaged.testzip() is not None:
            raise GapNode0071V2ReturnAnalysisError("source ZIP CRC failed")
        source_manifest_bytes = packaged.read(
            f"{SOURCE_ROOT}/TEST_PACKAGE_MANIFEST.json"
        )
        source_sca = packaged.read(
            f"{SOURCE_ROOT}/workload/sca_cfg.json"
        )
        source_sca_d = packaged.read(
            f"{SOURCE_ROOT}/workload/sca_cfg_D.json"
        )
        observer_bytes = packaged.read(
            f"{SOURCE_ROOT}/tb_probe/native_return_observer.svh"
        )
        runtime_readback_members = [
            name for name in source_members if "/readback/" in name
        ]
    if (
        package_manifest_bytes != source_manifest_bytes
        or returned_sca != source_sca
        or returned_sca_d != source_sca_d
    ):
        raise GapNode0071V2ReturnAnalysisError(
            "returned package/SCA identity differs from bound source package"
        )
    if (
        sha256_bytes(observer_bytes) != EXPECTED_OBSERVER_SHA256
        or runtime_readback_members
    ):
        raise GapNode0071V2ReturnAnalysisError(
            "source observer or runtime readback namespace differs"
        )

    checks = gate.get("checks")
    if not isinstance(checks, list) or len(checks) != 48:
        raise GapNode0071V2ReturnAnalysisError(
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
    preflight = installed.get("package_preflight")
    if (
        not isinstance(preflight, dict)
        or installed.get("schema")
        != "gap-node0071-complete-installed-preflight-v1"
        or installed.get("valid") is not True
        or installed.get("formal_readback_targets_absent") is not True
        or installed.get("server_source_files_inspected") is not False
        or installed.get("installed_file_count") != 75
        or preflight.get("valid") is not True
        or preflight.get("file_count") != 122
        or preflight.get("preload_count") != 25
        or preflight.get("readback_count") != 48
        or preflight.get("repeat_num") != 8
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
        raise GapNode0071V2ReturnAnalysisError(
            "preflight or fail-closed result conjunction differs"
        )
    xmr_gate = observer_receipt.get("xmr_static_gate")
    if (
        observer_receipt.get("schema")
        != "gap-node0071-package-local-observer-precompile-v1"
        or observer_receipt.get("valid") is not True
        or observer_receipt.get("errors") != []
        or observer_receipt.get("observer_readable") is not True
        or observer_receipt.get("observer_symlink") is not False
        or observer_receipt.get("expected_sha256")
        != EXPECTED_OBSERVER_SHA256
        or observer_receipt.get("observed_sha256")
        != EXPECTED_OBSERVER_SHA256
        or observer_receipt.get("identity_match") is not True
        or observer_receipt.get("server_file_written") is not False
        or observer_receipt.get("functional_rtl_modified") is not False
        or not isinstance(xmr_gate, dict)
        or xmr_gate.get("status") != "pass"
        or xmr_gate.get("checked_generated_instance_reference_count") != 198
        or xmr_gate.get("runtime_indexed_generated_instance_reference_count")
        != 0
    ):
        raise GapNode0071V2ReturnAnalysisError(
            "observer precompile receipt differs"
        )
    if (
        package_manifest.get("schema")
        != "gap-node0071-complete-server-package-v2"
        or package_manifest.get("install_name") != SOURCE_ROOT
        or package_manifest.get("functional_rtl_modified") is not False
        or package_manifest.get("server_source_identity_bound") is not False
        or package_manifest.get("candidate_release") is not False
        or package_manifest.get("evidence_level") != "E2_LOCAL_COMPLETE_NODE"
        or len(package_manifest.get("return_allowlist", [])) != 60
        or len(package_manifest.get("readback_checks", [])) != 48
    ):
        raise GapNode0071V2ReturnAnalysisError(
            "bound source manifest claim boundary differs"
        )

    return {
        "schema": "resnet50-gap-node0071-v2-return-analysis-v1",
        "status": "COMPILE_FAILED_SERVER_RTL_PORT_INTERFACE_MISMATCH",
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
            "sidecar_path": SOURCE_SIDECAR_RELATIVE.as_posix(),
            "sidecar_sha256": sha256_file(sidecar),
            "sidecar_content_valid": True,
            "manifest_install_name": package_manifest["install_name"],
            "returned_package_manifest_byte_equal": True,
            "returned_sca_byte_equal": True,
            "returned_sca_d_byte_equal": True,
            "source_zip_crc_valid": True,
            "source_zip_runtime_readback_target_count": 0,
        },
        "preflight": {
            "package_preflight_valid": True,
            "installed_preflight_valid": True,
            "installed_file_count": 75,
            "preload_count": 25,
            "formal_readback_count": 48,
            "repeat_num": 8,
            "runtime_readback_targets_absent_in_source_zip": True,
            "runtime_readback_targets_absent_post_install": True,
            "server_source_files_inspected": False,
        },
        "observer_transport": {
            "observer_include_parsed": True,
            "observer_sha256": EXPECTED_OBSERVER_SHA256,
            "precompile_receipt_valid": True,
            "xmr_static_gate_valid": True,
            "generated_instance_reference_count": 198,
            "runtime_indexed_generated_reference_count": 0,
            "server_file_written": False,
            "functional_rtl_modified": False,
            "v1_include_blocker_closed": True,
        },
        "execution_status": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "runner_exit_status": runner_status,
            "simulation_started": False,
            "natural_completion": False,
            "terminal_observed": False,
            "loader_sca_echo": False,
            "loader_sca_d_echo": False,
            "preload_count_exact": False,
            "formal_dump_count_exact": False,
            "formal_dynamic_readback_count": 0,
            "e3_e4_e5_claim_allowed": False,
        },
        "first_divergence": divergence,
        "fail_closed_adjudication": {
            "classification": "V2_RESULT_GATE_FAIL_CLOSED_CONFIRMED",
            "returned_status": gate["status"],
            "gate_conjunction": conjunction,
            "readback_check_count": len(checks),
            "missing_count": missing,
            "missing_by_role": roles,
            "mismatch_byte_count": 0,
            "returned_pass_is_dynamic_evidence": False,
        },
        "repair_adjudication": {
            "package_side_legal_fix_confirmed": False,
            "classification": "SERVER_RTL_INTERFACE_FAILURE_OUTSIDE_PACKAGE_SCOPE",
            "proof": (
                "The package-local observer is readable, hash-equal, XMR-gated, "
                "and parsed by the compiler. Compilation then fails because "
                "SA_ALU connects slice_rst to an SA_PE_Mul_Array definition "
                "that does not expose that port."
            ),
            "fresh_next_package_authorized": False,
            "functional_rtl_repair_required_to_change_observed_interface": True,
            "functional_rtl_modified": False,
            "server_files_outside_return_inspected": False,
        },
        "claim_boundary": {
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "accepted_v1_numeric_and_v2_package_assets_consumed": True,
            "compile_failure_is_not_gap_numeric_or_config_evidence": True,
            "complete_onnx_local_config_only_e2_count_remains": "3/78",
            "package_release_allowed": False,
        },
    }


__all__ = [
    "GapNode0071V2ReturnAnalysisError",
    "analyze_gap_node0071_v2_return",
]
