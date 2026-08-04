from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from resnet50_pipeline.gap_node0071_v2_return_analysis import (
    EXPECTED_OBSERVER_SHA256,
    EXPECTED_RETURN_MEMBERS,
    EXPECTED_SOURCE_SHA256,
    RETURN_ROOT,
    SOURCE_RELATIVE,
    SOURCE_ROOT,
    SOURCE_SIDECAR_RELATIVE,
    _json,
    _json_bytes,
    _safe_members,
    _status,
    _validate_return_manifest,
    sha256_bytes,
    sha256_file,
)


EXPECTED_RETURN_SHA256 = (
    "59285a790d7f092dfa9db35c21a9ab1ea811e1d810b186bb91fc2ecc19161066"
)
EXPECTED_RETURN_BYTES = 22749


class GapNode0071V2RerunReturnAnalysisError(ValueError):
    pass


def _line_number(lines: list[str], pattern: str) -> int:
    match = next(
        (
            index + 1
            for index, line in enumerate(lines)
            if pattern in line
        ),
        None,
    )
    if match is None:
        raise GapNode0071V2RerunReturnAnalysisError(
            f"compile log lacks signature: {pattern}"
        )
    return match


def _execution_first_divergence(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    error_line = _line_number(lines, "Error-[SE] Syntax error")
    source_line = next(
        (
            index + 1
            for index, line in enumerate(lines)
            if index + 1 >= error_line
            and "SA_PE_Float_Control.v" in line
        ),
        None,
    )
    if source_line is None:
        raise GapNode0071V2RerunReturnAnalysisError(
            "compile log lacks syntax-error source location"
        )
    token_line = _line_number(lines, "51: token is ')'")
    summary_line = _line_number(lines, "1 error")
    observer_lines = [
        index + 1
        for index, line in enumerate(lines)
        if "native_return_observer.svh" in line
    ]
    if not (
        error_line <= source_line <= token_line <= summary_line
        and observer_lines == []
    ):
        raise GapNode0071V2RerunReturnAnalysisError(
            "compile syntax-error ordering differs"
        )
    return {
        "classification": (
            "SERVER_RTL_SYNTAX_ERROR_BEFORE_TESTBENCH_AND_SIMULATION"
        ),
        "compile_log_error_line": error_line,
        "source_location_line": source_line,
        "token_evidence_line": token_line,
        "compile_summary_line": summary_line,
        "reported_source": "SA_PE_Float_Control.v",
        "reported_source_line": 51,
        "reported_token": ")",
        "testbench_reached": False,
        "observer_include_parsed": False,
        "simulation_started": False,
        "terminal_observed": False,
        "formal_readback_produced": False,
    }


def analyze_gap_node0071_v2_rerun_return(
    project_root: Path, return_zip: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    supplied = return_zip.resolve()
    exact_sidecar = Path(str(supplied) + ".sha256")
    source = root / SOURCE_RELATIVE
    source_sidecar = root / SOURCE_SIDECAR_RELATIVE
    if (
        not supplied.is_file()
        or not source.is_file()
        or not source_sidecar.is_file()
    ):
        raise GapNode0071V2RerunReturnAnalysisError(
            "source package, source sidecar, or return ZIP is absent"
        )
    return_sha = sha256_file(supplied)
    source_sha = sha256_file(source)
    if (
        supplied.stat().st_size != EXPECTED_RETURN_BYTES
        or return_sha != EXPECTED_RETURN_SHA256
        or source_sha != EXPECTED_SOURCE_SHA256
    ):
        raise GapNode0071V2RerunReturnAnalysisError(
            "return content or source package identity differs"
        )
    expected_source_sidecar = (
        f"{EXPECTED_SOURCE_SHA256}  {source.name}\n"
    )
    if (
        source_sidecar.read_text(encoding="ascii")
        != expected_source_sidecar
    ):
        raise GapNode0071V2RerunReturnAnalysisError(
            "source package sidecar differs"
        )
    return_sidecar_present = exact_sidecar.is_file()
    return_sidecar_valid = False
    return_sidecar_sha256: str | None = None
    if return_sidecar_present:
        return_sidecar_sha256 = sha256_file(exact_sidecar)
        expected_return_sidecar = (
            f"{EXPECTED_RETURN_SHA256}  {supplied.name}\n"
        )
        return_sidecar_valid = (
            exact_sidecar.read_text(encoding="ascii")
            == expected_return_sidecar
        )

    with zipfile.ZipFile(supplied) as returned:
        members = _safe_members(returned)
        if returned.testzip() is not None:
            raise GapNode0071V2RerunReturnAnalysisError(
                "return ZIP CRC failed"
            )
        if set(members) != EXPECTED_RETURN_MEMBERS:
            raise GapNode0071V2RerunReturnAnalysisError(
                "return ZIP exact member set differs"
            )
        return_manifest = _json(
            returned, f"{RETURN_ROOT}/RETURN_MANIFEST.json"
        )
        required_missing = _validate_return_manifest(
            returned, return_manifest
        )
        evidence = f"{RETURN_ROOT}/evidence"
        returned_manifest_bytes = returned.read(
            f"{evidence}/PACKAGE_MANIFEST.json"
        )
        returned_manifest = _json_bytes(
            returned_manifest_bytes, "returned PACKAGE_MANIFEST"
        )
        returned_sca = returned.read(
            f"{RETURN_ROOT}/config/sca_cfg.json"
        )
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
        gate = _json(
            returned, f"{evidence}/SERVER_RESULT_GATE.json"
        )
        compile_log = returned.read(
            f"{RETURN_ROOT}/logs/compile.log"
        ).decode("utf-8", "replace")
        execution_divergence = _execution_first_divergence(
            compile_log
        )

    with zipfile.ZipFile(source) as packaged:
        source_members = _safe_members(packaged)
        if packaged.testzip() is not None:
            raise GapNode0071V2RerunReturnAnalysisError(
                "source ZIP CRC failed"
            )
        source_manifest_bytes = packaged.read(
            f"{SOURCE_ROOT}/TEST_PACKAGE_MANIFEST.json"
        )
        source_sca = packaged.read(
            f"{SOURCE_ROOT}/workload/sca_cfg.json"
        )
        source_sca_d = packaged.read(
            f"{SOURCE_ROOT}/workload/sca_cfg_D.json"
        )
        observer = packaged.read(
            f"{SOURCE_ROOT}/tb_probe/native_return_observer.svh"
        )
        source_runtime_targets = [
            name for name in source_members if "/readback/" in name
        ]
    if (
        returned_manifest_bytes != source_manifest_bytes
        or returned_sca != source_sca
        or returned_sca_d != source_sca_d
        or sha256_bytes(observer) != EXPECTED_OBSERVER_SHA256
        or source_runtime_targets
    ):
        raise GapNode0071V2RerunReturnAnalysisError(
            "returned package identity or source boundary differs"
        )

    checks = gate.get("checks")
    if not isinstance(checks, list) or len(checks) != 48:
        raise GapNode0071V2RerunReturnAnalysisError(
            "formal readback check count differs"
        )
    missing = sum(
        record.get("status") == "missing" for record in checks
    )
    missing_by_role = {
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
    xmr_gate = observer_receipt.get("xmr_static_gate")
    if (
        not isinstance(preflight, dict)
        or installed.get("valid") is not True
        or installed.get("formal_readback_targets_absent") is not True
        or installed.get("server_source_files_inspected") is not False
        or installed.get("installed_file_count") != 75
        or preflight.get("valid") is not True
        or preflight.get("file_count") != 122
        or preflight.get("preload_count") != 25
        or preflight.get("readback_count") != 48
        or preflight.get("repeat_num") != 8
        or observer_receipt.get("valid") is not True
        or observer_receipt.get("identity_match") is not True
        or observer_receipt.get("observed_sha256")
        != EXPECTED_OBSERVER_SHA256
        or not isinstance(xmr_gate, dict)
        or xmr_gate.get("status") != "pass"
        or xmr_gate.get(
            "runtime_indexed_generated_instance_reference_count"
        )
        != 0
        or compile_status != 2
        or simulation_status != 125
        or runner_status != 2
        or gate.get("status") != "NODE0071_GAP_SERVER_FAILURE"
        or gate.get("readback_count") != 48
        or gate.get("missing_count") != 48
        or gate.get("mismatch_byte_count") != 0
        or missing != 48
        or missing_by_role
        != {
            "sum_int32": 16,
            "scaled_fp32": 16,
            "final_uint8": 16,
        }
        or conjunction != expected_conjunction
        or returned_manifest.get("install_name") != SOURCE_ROOT
        or returned_manifest.get("functional_rtl_modified") is not False
        or returned_manifest.get("server_source_identity_bound") is not False
    ):
        raise GapNode0071V2RerunReturnAnalysisError(
            "preflight, observer, or result conjunction differs"
        )

    return {
        "schema": "resnet50-gap-node0071-v2-rerun-return-analysis-v1",
        "status": (
            "FORMAL_CLAIM_FAILED_MISSING_SIDECAR_AND_"
            "COMPILE_FAILED_SERVER_RTL_SYNTAX"
        ),
        "return_identity": {
            "physical_path": str(supplied),
            "physical_filename_suffix_ignored": True,
            "logical_return_name": return_manifest["install_name"]
            + "_return",
            "identity_bound_by_content_manifest_and_source_sha": True,
            "size_bytes": supplied.stat().st_size,
            "sha256": return_sha,
            "exact_sidecar_path": str(exact_sidecar),
            "exact_sidecar_present": return_sidecar_present,
            "exact_sidecar_valid": return_sidecar_valid,
            "exact_sidecar_sha256": return_sidecar_sha256,
            "formal_receipt_claim_pass": (
                return_sidecar_present and return_sidecar_valid
            ),
            "sidecar_blocker": (
                None
                if return_sidecar_present and return_sidecar_valid
                else "RETURN_SIDECAR_NOT_PROVIDED"
            ),
            "zip_crc_valid": True,
            "file_count": len(members),
            "strict_allowlist_valid": True,
            "return_manifest_status": "incomplete",
            "required_missing_count": len(required_missing),
        },
        "bound_source_package": {
            "path": SOURCE_RELATIVE.as_posix(),
            "size_bytes": source.stat().st_size,
            "sha256": source_sha,
            "source_sidecar_path": SOURCE_SIDECAR_RELATIVE.as_posix(),
            "source_sidecar_sha256": sha256_file(source_sidecar),
            "source_sidecar_valid": True,
            "returned_manifest_byte_equal": True,
            "returned_sca_byte_equal": True,
            "returned_sca_d_byte_equal": True,
            "source_zip_crc_valid": True,
            "source_runtime_readback_target_count": 0,
        },
        "preflight": {
            "package_preflight_valid": True,
            "installed_preflight_valid": True,
            "installed_file_count": 75,
            "preload_count": 25,
            "readback_count": 48,
            "repeat_num": 8,
            "runtime_readback_targets_absent_before_simulation": True,
            "observer_precompile_receipt_valid": True,
            "observer_sha256": EXPECTED_OBSERVER_SHA256,
            "xmr_static_gate_valid": True,
            "server_source_files_inspected": False,
        },
        "execution_status": {
            "compile_exit_status": compile_status,
            "runner_exit_status": runner_status,
            "simulation_exit_status": simulation_status,
            "simulation_started": False,
            "natural_completion": False,
            "terminal_observed": False,
            "loader_sca_echo": False,
            "loader_sca_d_echo": False,
            "preload_count_exact": False,
            "formal_dump_count_exact": False,
            "formal_dynamic_readback_count": 0,
        },
        "first_divergence": {
            "formal_claim_first_blocker": (
                "RETURN_SIDECAR_NOT_PROVIDED"
            ),
            "dynamic_execution_first_divergence": execution_divergence,
        },
        "fail_closed_adjudication": {
            "returned_status": gate["status"],
            "gate_conjunction": conjunction,
            "readback_check_count": len(checks),
            "missing_count": missing,
            "missing_by_role": missing_by_role,
            "mismatch_byte_count": 0,
            "returned_pass_is_dynamic_evidence": False,
            "formal_claim_pass": False,
        },
        "evidence_level_adjudication": {
            "e3_allowed": False,
            "e4_allowed": False,
            "e5_allowed": False,
            "reason": (
                "The exact return sidecar is absent and compilation fails "
                "before the testbench and simulation."
            ),
        },
        "repair_adjudication": {
            "package_side_legal_fix_confirmed": False,
            "classification": "SERVER_RTL_SYNTAX_FAILURE_OUTSIDE_PACKAGE_SCOPE",
            "fresh_next_package_authorized": False,
            "functional_rtl_modified": False,
            "server_files_outside_return_inspected": False,
        },
        "claim_boundary": {
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "workload_rebuilt": False,
            "accepted_reuse_assets_consumed": True,
            "complete_onnx_local_config_only_e2_count_remains": "3/78",
            "dynamic_or_production_claim": False,
        },
    }


__all__ = [
    "GapNode0071V2RerunReturnAnalysisError",
    "analyze_gap_node0071_v2_rerun_return",
]
