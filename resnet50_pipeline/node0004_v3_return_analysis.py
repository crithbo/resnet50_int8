from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_RETURN_SHA256 = (
    "31389aa859418d7bba866f07ee9410e00fe2e83f4ce5c53c1e45ba3c610e9750"
)
EXPECTED_SOURCE_SHA256 = (
    "84c834de989c7912edfd711cd5fb2bdfe51e40998bb493d3e4ec5b99da9a331c"
)
EXPECTED_SOURCE_VALIDATION_SHA256 = (
    "2ba469090caad4f88be675907b8683f86aa8f8335ace0f5c9568df26c3f6765c"
)
EXPECTED_SOURCE_SIDECAR_SHA256 = (
    "88506c715857b1f9c15c9c51c7a2b0cf557dffa80d31941cd0f2ed84a44c1db3"
)
EXPECTED_OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
SOURCE_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v3_obs.zip"
)
SOURCE_SIDECAR_REL = Path(str(SOURCE_REL) + ".sha256")
SOURCE_VALIDATION_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v3_obs.validation.json"
)
RETURN_ROOT = "r5_n4_hw_v3_obs_return"
SOURCE_ROOT = "r5_n4_hw_v3_obs"
EXPECTED_RELATIVE_MEMBERS = {
    "RETURN_ALLOWLIST.json",
    "evidence/SERVER_RESULT_GATE.json",
    "evidence/compile_exit_status.txt",
    "evidence/install_preflight.json",
    "evidence/observer_precompile.json",
    "evidence/package_preflight.json",
    "evidence/run_exit_status.txt",
    "runs/compile/sim_results/compile.log",
    "runs/compile/sim_results/compile_driver.log",
}


class Node0004V3ReturnAnalysisError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_members(archive: zipfile.ZipFile) -> list[str]:
    result: list[str] = []
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
            raise Node0004V3ReturnAnalysisError(f"unsafe ZIP member: {name}")
        seen.add(name)
        if not info.is_dir():
            result.append(name)
    return result


def _json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise Node0004V3ReturnAnalysisError(f"cannot parse JSON: {name}") from error
    if not isinstance(value, dict):
        raise Node0004V3ReturnAnalysisError(f"JSON root must be object: {name}")
    return value


def _status(archive: zipfile.ZipFile, name: str) -> int:
    try:
        return int(archive.read(name).decode("ascii").strip())
    except (KeyError, UnicodeError, ValueError) as error:
        raise Node0004V3ReturnAnalysisError(f"cannot parse status: {name}") from error


def _compile_divergence(text: str) -> dict[str, Any]:
    lines = text.splitlines()

    def exact(pattern: str) -> int:
        matches = [index for index, line in enumerate(lines) if pattern in line]
        if len(matches) != 1:
            raise Node0004V3ReturnAnalysisError(
                f"compile signature is not unique: {pattern}"
            )
        return matches[0] + 1

    include_line = exact(
        "Parsing included file "
        "'/home/panqs/ndp/r5_n4_hw_v3_obs/tb_probe/native_return_observer.svh'."
    )
    error_line = exact("Error-[UPIMI-E] Undefined port in module instantiation")
    caller_line = exact(
        "/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_ALU.v, 124"
    )
    undefined_line = exact(
        'Port "slice_rst" is not defined in module \'SA_PE_Mul_Array\''
    )
    callee_lines = [
        index + 1
        for index, line in enumerate(lines)
        if "SA_PE_Mul_Array.v" in line and line.rstrip().endswith('",')
    ]
    if len(callee_lines) != 1:
        raise Node0004V3ReturnAnalysisError(
            "callee definition signature is not unique"
        )
    if not include_line < error_line < caller_line < undefined_line < callee_lines[0]:
        raise Node0004V3ReturnAnalysisError("compile first-divergence order differs")
    return {
        "classification": "SERVER_RTL_INTERFACE_COMPILE_MISMATCH",
        "first_error_line": error_line,
        "caller_location_line": caller_line,
        "undefined_port_line": undefined_line,
        "callee_definition_line": callee_lines[0],
        "caller": "rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_ALU.v:124",
        "callee": (
            "rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
            "SA_PE_Mul_Array.v:module SA_PE_Mul_Array"
        ),
        "incompatible_interface": (
            "caller instantiates .slice_rst(slice_rst), but the compiled "
            "SA_PE_Mul_Array definition has no slice_rst port"
        ),
        "observer_include_proven_before_divergence": True,
        "observer_parse_line": include_line,
        "simulation_started": False,
        "natural_terminal_observed": False,
        "formal_readback_produced": False,
    }


def analyze_node0004_v3_return(
    project_root: Path, return_zip: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    returned_path = return_zip.resolve()
    source_path = root / SOURCE_REL
    sidecar_path = root / SOURCE_SIDECAR_REL
    validation_path = root / SOURCE_VALIDATION_REL
    for path in (returned_path, source_path, sidecar_path, validation_path):
        if not path.is_file():
            raise Node0004V3ReturnAnalysisError(f"required identity is missing: {path}")
    identities = {
        "return": sha256_file(returned_path),
        "source": sha256_file(source_path),
        "sidecar": sha256_file(sidecar_path),
        "validation": sha256_file(validation_path),
    }
    expected = {
        "return": EXPECTED_RETURN_SHA256,
        "source": EXPECTED_SOURCE_SHA256,
        "sidecar": EXPECTED_SOURCE_SIDECAR_SHA256,
        "validation": EXPECTED_SOURCE_VALIDATION_SHA256,
    }
    if identities != expected:
        raise Node0004V3ReturnAnalysisError(
            f"bound identity differs: observed={identities}"
        )
    sidecar_text = sidecar_path.read_text(encoding="ascii")
    if sidecar_text != f"{EXPECTED_SOURCE_SHA256}  {source_path.name}\n":
        raise Node0004V3ReturnAnalysisError("source sidecar content differs")
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if (
        validation.get("status") != "PACKAGE_READY_NOT_RUN"
        or validation.get("zip_sha256") != EXPECTED_SOURCE_SHA256
        or validation.get("observer_sha256") != EXPECTED_OBSERVER_SHA256
        or validation.get("preloaded_runtime_readback_target_count") != 0
        or validation.get("result_gate_fail_closed") is not True
        or validation.get("functional_rtl_modified") is not False
        or validation.get("server_rtl_entries") != 0
    ):
        raise Node0004V3ReturnAnalysisError("source validation identity differs")

    with zipfile.ZipFile(returned_path) as archive:
        members = _safe_members(archive)
        if archive.testzip() is not None:
            raise Node0004V3ReturnAnalysisError("return ZIP CRC failed")
        expected_members = {
            f"{RETURN_ROOT}/{relative}" for relative in EXPECTED_RELATIVE_MEMBERS
        }
        if set(members) != expected_members:
            raise Node0004V3ReturnAnalysisError("return exact-set differs")
        allowlist = _json(archive, f"{RETURN_ROOT}/RETURN_ALLOWLIST.json")
        records = allowlist.get("records")
        if (
            allowlist.get("schema") != "node0004-server-return-allowlist-v2"
            or allowlist.get("install_name") != "r5_n4_hw_v3_obs"
            or not isinstance(records, list)
            or len(records) != 8
        ):
            raise Node0004V3ReturnAnalysisError("return allowlist header differs")
        declared: set[str] = set()
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                raise Node0004V3ReturnAnalysisError("return allowlist record differs")
            relative = record["path"]
            member = f"{RETURN_ROOT}/{relative}"
            if relative == "RETURN_ALLOWLIST.json" or member not in expected_members:
                raise Node0004V3ReturnAnalysisError("return allowlist path differs")
            payload = archive.read(member)
            if (
                len(payload) != record.get("size_bytes")
                or hashlib.sha256(payload).hexdigest() != record.get("sha256")
            ):
                raise Node0004V3ReturnAnalysisError(
                    f"return allowlist receipt differs: {relative}"
                )
            declared.add(member)
        if declared != expected_members - {f"{RETURN_ROOT}/RETURN_ALLOWLIST.json"}:
            raise Node0004V3ReturnAnalysisError("return allowlist exact-set differs")

        evidence_root = f"{RETURN_ROOT}/evidence"
        package_preflight = _json(
            archive, f"{evidence_root}/package_preflight.json"
        )
        install_preflight = _json(
            archive, f"{evidence_root}/install_preflight.json"
        )
        observer = _json(
            archive, f"{evidence_root}/observer_precompile.json"
        )
        compile_status = _status(
            archive, f"{evidence_root}/compile_exit_status.txt"
        )
        run_status = _status(
            archive, f"{evidence_root}/run_exit_status.txt"
        )
        gate = _json(archive, f"{evidence_root}/SERVER_RESULT_GATE.json")
        compile_log = archive.read(
            f"{RETURN_ROOT}/runs/compile/sim_results/compile.log"
        ).decode("utf-8", errors="replace")
        compile_driver_log = archive.read(
            f"{RETURN_ROOT}/runs/compile/sim_results/compile_driver.log"
        ).decode("utf-8", errors="replace")
        divergence = _compile_divergence(compile_log)
        driver_divergence = _compile_divergence(compile_driver_log)

    if (
        package_preflight
        != {
            "schema": "node0004-assumed-hardware-package-preflight-v2",
            "valid": True,
            "file_count": 829,
            "readback_target_count": 320,
            "preloaded_readback_target_count": 0,
        }
        or install_preflight
        != {
            "schema": "node0004-assumed-hardware-install-preflight-v2",
            "valid": True,
            "file_count": 503,
            "preloaded_readback_target_count": 0,
        }
    ):
        raise Node0004V3ReturnAnalysisError("package/install preflight differs")
    static_gate = observer.get("xmr_static_gate", {})
    if (
        observer.get("valid") is not True
        or observer.get("identity_match") is not True
        or observer.get("expected_sha256") != EXPECTED_OBSERVER_SHA256
        or observer.get("observed_sha256") != EXPECTED_OBSERVER_SHA256
        or observer.get("server_file_written") is not False
        or observer.get("functional_rtl_modified") is not False
        or static_gate.get("status") != "pass"
        or static_gate.get("checked_generated_instance_reference_count") != 198
        or static_gate.get("runtime_indexed_generated_instance_reference_count")
        != 0
    ):
        raise Node0004V3ReturnAnalysisError("observer guard differs")
    if driver_divergence["incompatible_interface"] != divergence["incompatible_interface"]:
        raise Node0004V3ReturnAnalysisError("compile logs disagree")

    checks = gate.get("checks")
    if not isinstance(checks, list) or len(checks) != 320:
        raise Node0004V3ReturnAnalysisError("formal readback check inventory differs")
    missing = sum(row.get("status") == "missing" for row in checks)
    preloaded = sum(
        row.get("runtime_target_preloaded") is True for row in checks
    )
    conjunction = {
        "compile_exit_status_zero": compile_status == 0,
        "every_required_run_exit_status_zero": run_status == 0,
        "natural_terminal_observed": False,
        "formal_readback_exact_set_complete": missing == 0,
        "missing_count_zero": missing == 0,
        "mismatch_count_zero": gate.get("mismatch_byte_count") == 0,
    }
    conjunction_pass = all(conjunction.values())
    if (
        compile_status != 2
        or run_status != 125
        or gate.get("status") != "NODE0004_SERVER_FAILURE"
        or gate.get("execution_gate")
        != {
            "compile_exit_status": 2,
            "run_exit_status": 125,
            "compile_succeeded": False,
            "all_simulations_exited_zero": False,
            "terminal_and_readback_gate_satisfied": False,
        }
        or gate.get("readback_count") != 320
        or gate.get("missing_count") != 320
        or missing != 320
        or preloaded != 0
        or conjunction_pass
    ):
        raise Node0004V3ReturnAnalysisError("v3 fail-closed conjunction differs")

    with zipfile.ZipFile(source_path) as package:
        source_members = _safe_members(package)
        if package.testzip() is not None:
            raise Node0004V3ReturnAnalysisError("source ZIP CRC failed")
        manifest = _json(package, f"{SOURCE_ROOT}/package_manifest.json")
        observer_payload = package.read(
            f"{SOURCE_ROOT}/tb_probe/native_return_observer.svh"
        )
        runtime_targets = [
            name
            for name in source_members
            if re.search(
                r"/workload/runtime/runs/.+/matrix_D_linearized_128bit\.txt$",
                name,
            )
        ]
    if (
        manifest.get("install_name") != "r5_n4_hw_v3_obs"
        or manifest.get("candidate_release") is not False
        or manifest.get("functional_rtl_modified") is not False
        or manifest.get("server_rtl_entries") != 0
        or manifest.get("return_collection_policy") != "EXPLICIT_ALLOWLIST_ONLY"
        or hashlib.sha256(observer_payload).hexdigest()
        != EXPECTED_OBSERVER_SHA256
        or runtime_targets
    ):
        raise Node0004V3ReturnAnalysisError("source package contract differs")

    return {
        "schema": "resnet50-node0004-v3-server-return-analysis-v1",
        "status": "SERVER_RTL_COMPILE_INTERFACE_MISMATCH_NO_DYNAMIC_EVIDENCE",
        "return_identity": {
            "path": str(returned_path),
            "size_bytes": returned_path.stat().st_size,
            "sha256": identities["return"],
            "sidecar_supplied": False,
            "zip_crc_valid": True,
            "file_count": len(members),
            "exact_set_valid": True,
            "allowlist_valid": True,
        },
        "bound_source": {
            "package": {
                "path": SOURCE_REL.as_posix(),
                "sha256": identities["source"],
                "file_count": len(source_members),
            },
            "sidecar": {
                "path": SOURCE_SIDECAR_REL.as_posix(),
                "sha256": identities["sidecar"],
                "content_match": True,
            },
            "validation": {
                "path": SOURCE_VALIDATION_REL.as_posix(),
                "sha256": identities["validation"],
                "status": validation["status"],
            },
            "observer_sha256": EXPECTED_OBSERVER_SHA256,
            "source_runtime_d_target_count": len(runtime_targets),
        },
        "preflight_and_observer": {
            "package_preflight": package_preflight,
            "install_preflight": install_preflight,
            "observer_precompile": observer,
            "observer_include_parsed_by_compiler": True,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "simulation_started": False,
            "natural_terminal_observed": False,
            "formal_readback_produced_count": 0,
            "formal_readback_expected_count": 320,
            "missing_count": missing,
            "mismatch_byte_count": gate.get("mismatch_byte_count"),
            "joint_gate_conditions": conjunction,
            "joint_gate_pass": conjunction_pass,
            "e4_e5_claim_allowed": False,
        },
        "first_divergence": divergence,
        "adjudication": {
            "classification": "SERVER_SOURCE_RTL_INTERFACE_INCONSISTENCY",
            "observer_package_fix_confirmed": True,
            "conv_numeric_or_lifecycle_reached": False,
            "package_side_legal_fix_available": False,
            "reason": (
                "The compiler successfully consumed the package-local observer, "
                "then rejected an interface mismatch between two server RTL "
                "files. The package carries zero RTL entries and has no authority "
                "to modify server RTL or mask the compile error."
            ),
            "successor_package_authorized": False,
        },
        "blocker_delta": {
            "close": ["B_NODE0004_PACKAGE_OBSERVER_INCLUDE_PATH"],
            "add": ["B_NODE0004_SERVER_RTL_COMPILE_INTERFACE_MISMATCH"],
            "keep": [
                "B_NODE0004_DYNAMIC_RESULT_PENDING",
                "B_NODE0004_SERVER_RTL_IDENTITY_UNBOUND",
                "B_NODE0004_NO_DYNAMIC_BASELINE",
            ],
        },
        "rule_delta_proposal": [],
        "package_release": "NONE",
        "claim_boundary": {
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "source_package_reused_read_only": True,
            "non_conv_retested": False,
            "server_inspection_outside_return_performed": False,
            "compile_failure_is_not_operator_numeric_evidence": True,
        },
    }


__all__ = [
    "Node0004V3ReturnAnalysisError",
    "analyze_node0004_v3_return",
]
