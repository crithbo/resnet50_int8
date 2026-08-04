from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_RETURN_SHA256 = (
    "14ae820aeba624d92189f482603f8777f9fd8c43c01a3e9b455b03fe0e5e0983"
)
EXPECTED_RETURN_SIDECAR_SHA256 = (
    "aba44451471615d1b2a330b17e7354d352cf5e0067e805f24e4c264ae80205ba"
)
EXPECTED_SOURCE_SHA256 = (
    "61e28a7c218230869ad1a5247023edb9bf8ee9af5a0660124fc8966ce5ad239e"
)
EXPECTED_SOURCE_SIDECAR_SHA256 = (
    "9eafe4bf394ce2e5aaff650b1428313736baadb572bea7d7d5fbe5aa8ba71f08"
)
EXPECTED_SOURCE_VALIDATION_SHA256 = (
    "d22fde955b557ca40582ca2bbc0ad24efc691cc69026c6db59022ce7b30a7fdd"
)
EXPECTED_V5_SHA256 = (
    "fb7a36e380c1329c29faf9170a0e117715bdc0d0198bc0568e47298d517844cb"
)
EXPECTED_OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
SOURCE_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v4_rootbind.zip"
)
SOURCE_SIDECAR_REL = Path(str(SOURCE_REL) + ".sha256")
SOURCE_VALIDATION_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v4_rootbind.validation.json"
)
V5_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v5_observe.zip"
)
V5_SIDECAR_REL = Path(str(V5_REL) + ".sha256")
V5_VALIDATION_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v5_observe.validation.json"
)
RETURN_ROOT = "r5_n4_hw_v4_rootbind_return"
SOURCE_ROOT = "r5_n4_hw_v4_rootbind"
EXPECTED_RELATIVE_MEMBERS = {
    "RETURN_ALLOWLIST.json",
    "evidence/SERVER_RESULT_GATE.json",
    "evidence/compile_exit_status.txt",
    "evidence/install_preflight.json",
    "evidence/observer_precompile.json",
    "evidence/package_preflight.json",
    "evidence/run_exit_status.txt",
    "runs/c0/sim.log",
    "runs/compile/sim_results/compile.log",
    "runs/compile/sim_results/compile_driver.log",
}
RULE_RECEIPTS = {
    "plan_mutable_provenance": (
        "9cd2328a18ecd961e97db2baa7afa70a68b2ea01f7a92fbdcac25fae80a7e382"
    ),
    "generation_index": (
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
    ),
    "server_package_rule": (
        "153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2"
    ),
    "int8_sa_rule": (
        "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
    ),
    "exact_tail_rule": (
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"
    ),
}


class Node0004V4ReturnAnalysisError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
            raise Node0004V4ReturnAnalysisError(
                f"unsafe ZIP member: {name}"
            )
        seen.add(name)
        if not info.is_dir():
            members.append(name)
    return members


def _json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise Node0004V4ReturnAnalysisError(
            f"cannot parse JSON: {name}"
        ) from error
    if not isinstance(value, dict):
        raise Node0004V4ReturnAnalysisError(
            f"JSON root must be object: {name}"
        )
    return value


def _status(archive: zipfile.ZipFile, name: str) -> int:
    try:
        return int(archive.read(name).decode("ascii").strip())
    except (KeyError, UnicodeError, ValueError) as error:
        raise Node0004V4ReturnAnalysisError(
            f"cannot parse status: {name}"
        ) from error


def analyze_node0004_v4_return(
    project_root: Path, return_zip: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    returned_path = return_zip.resolve()
    return_sidecar = Path(str(returned_path) + ".sha256")
    source_path = root / SOURCE_REL
    source_sidecar = root / SOURCE_SIDECAR_REL
    source_validation_path = root / SOURCE_VALIDATION_REL
    v5_path = root / V5_REL
    v5_sidecar = root / V5_SIDECAR_REL
    v5_validation_path = root / V5_VALIDATION_REL
    required = (
        returned_path,
        return_sidecar,
        source_path,
        source_sidecar,
        source_validation_path,
        v5_path,
        v5_sidecar,
        v5_validation_path,
    )
    for path in required:
        if not path.is_file():
            raise Node0004V4ReturnAnalysisError(
                f"required identity is missing: {path}"
            )
    identities = {
        "return": sha256_file(returned_path),
        "return_sidecar": sha256_file(return_sidecar),
        "source": sha256_file(source_path),
        "source_sidecar": sha256_file(source_sidecar),
        "source_validation": sha256_file(source_validation_path),
        "v5": sha256_file(v5_path),
        "v5_sidecar": sha256_file(v5_sidecar),
        "v5_validation": sha256_file(v5_validation_path),
    }
    expected = {
        "return": EXPECTED_RETURN_SHA256,
        "return_sidecar": EXPECTED_RETURN_SIDECAR_SHA256,
        "source": EXPECTED_SOURCE_SHA256,
        "source_sidecar": EXPECTED_SOURCE_SIDECAR_SHA256,
        "source_validation": EXPECTED_SOURCE_VALIDATION_SHA256,
        "v5": EXPECTED_V5_SHA256,
    }
    for name, digest in expected.items():
        if identities[name] != digest:
            raise Node0004V4ReturnAnalysisError(
                f"{name} identity differs"
            )
    if return_sidecar.read_text(encoding="ascii") != (
        f"{EXPECTED_RETURN_SHA256}  {returned_path.name}\n"
    ):
        raise Node0004V4ReturnAnalysisError(
            "return sidecar content differs"
        )
    if source_sidecar.read_text(encoding="ascii") != (
        f"{EXPECTED_SOURCE_SHA256}  {source_path.name}\n"
    ):
        raise Node0004V4ReturnAnalysisError(
            "source sidecar content differs"
        )
    if v5_sidecar.read_text(encoding="ascii") != (
        f"{EXPECTED_V5_SHA256}  {v5_path.name}\n"
    ):
        raise Node0004V4ReturnAnalysisError("v5 sidecar content differs")
    source_validation = json.loads(
        source_validation_path.read_text(encoding="utf-8")
    )
    v5_validation = json.loads(
        v5_validation_path.read_text(encoding="utf-8")
    )
    if (
        source_validation.get("status") != "PACKAGE_READY_NOT_RUN"
        or source_validation.get("zip_sha256") != EXPECTED_SOURCE_SHA256
    ):
        raise Node0004V4ReturnAnalysisError(
            "source validation differs"
        )
    if (
        v5_validation.get("status") != "PACKAGE_READY_NOT_RUN"
        or v5_validation.get("zip_sha256") != EXPECTED_V5_SHA256
        or v5_validation.get("observer_runtime_enabled") is not True
        or v5_validation.get("observer_log_return_allowlisted") is not True
        or v5_validation.get("server_rtl_entries") != 0
    ):
        raise Node0004V4ReturnAnalysisError("v5 validation differs")

    with zipfile.ZipFile(returned_path) as archive:
        members = _safe_members(archive)
        if archive.testzip() is not None:
            raise Node0004V4ReturnAnalysisError("return ZIP CRC failed")
        expected_members = {
            f"{RETURN_ROOT}/{relative}" for relative in EXPECTED_RELATIVE_MEMBERS
        }
        if set(members) != expected_members:
            raise Node0004V4ReturnAnalysisError("return exact-set differs")
        allowlist = _json(archive, f"{RETURN_ROOT}/RETURN_ALLOWLIST.json")
        records = allowlist.get("records")
        if (
            allowlist.get("schema") != "node0004-server-return-allowlist-v2"
            or allowlist.get("install_name") != SOURCE_ROOT
            or not isinstance(records, list)
            or len(records) != 9
        ):
            raise Node0004V4ReturnAnalysisError(
                "return allowlist header differs"
            )
        declared: set[str] = set()
        for record in records:
            if not isinstance(record, dict) or not isinstance(
                record.get("path"), str
            ):
                raise Node0004V4ReturnAnalysisError(
                    "return allowlist record differs"
                )
            member = f"{RETURN_ROOT}/{record['path']}"
            payload = archive.read(member)
            if (
                member not in expected_members
                or len(payload) != record.get("size_bytes")
                or hashlib.sha256(payload).hexdigest() != record.get("sha256")
            ):
                raise Node0004V4ReturnAnalysisError(
                    f"allowlist receipt differs: {record['path']}"
                )
            declared.add(member)
        if declared != expected_members - {
            f"{RETURN_ROOT}/RETURN_ALLOWLIST.json"
        }:
            raise Node0004V4ReturnAnalysisError(
                "allowlist exact-set differs"
            )
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
        gate = _json(archive, f"{evidence_root}/SERVER_RESULT_GATE.json")
        compile_status = _status(
            archive, f"{evidence_root}/compile_exit_status.txt"
        )
        run_status = _status(
            archive, f"{evidence_root}/run_exit_status.txt"
        )
        compile_log = archive.read(
            f"{RETURN_ROOT}/runs/compile/sim_results/compile.log"
        ).decode("utf-8", errors="replace")
        compile_driver = archive.read(
            f"{RETURN_ROOT}/runs/compile/sim_results/compile_driver.log"
        ).decode("utf-8", errors="replace")
        sim_log = archive.read(
            f"{RETURN_ROOT}/runs/c0/sim.log"
        ).decode("utf-8", errors="replace")

    if (
        package_preflight.get("valid") is not True
        or package_preflight.get("file_count") != 829
        or package_preflight.get("readback_target_count") != 320
        or package_preflight.get("preloaded_readback_target_count") != 0
        or install_preflight.get("valid") is not True
        or install_preflight.get("file_count") != 503
        or install_preflight.get("preloaded_readback_target_count") != 0
    ):
        raise Node0004V4ReturnAnalysisError("preflight differs")
    static_gate = observer.get("xmr_static_gate", {})
    if (
        observer.get("valid") is not True
        or observer.get("identity_match") is not True
        or observer.get("observed_sha256") != EXPECTED_OBSERVER_SHA256
        or static_gate.get("status") != "pass"
        or static_gate.get("checked_generated_instance_reference_count") != 198
        or static_gate.get(
            "runtime_indexed_generated_instance_reference_count"
        )
        != 0
    ):
        raise Node0004V4ReturnAnalysisError("observer precompile differs")
    if (
        compile_status != 0
        or "Compilation completed!" not in compile_driver
        or "0 error(s), 1 warning(s)" not in compile_driver
        or "Error-[" in compile_log
    ):
        raise Node0004V4ReturnAnalysisError("compile closure differs")

    lines = sim_log.splitlines()
    line_map: dict[str, int] = {}
    patterns = {
        "sca": "Using SCA cfg file:",
        "sca_d": "Using SCA cfg D file:",
        "matrices": "JSON config: 86 matrices loaded",
        "reg_start": "Reg Started.",
        "slice_start": "INFO: slice start",
        "interrupt": "Interrupt at time",
    }
    for key, pattern in patterns.items():
        hits = [
            index
            for index, line in enumerate(lines, start=1)
            if pattern in line
        ]
        if len(hits) != 1:
            raise Node0004V4ReturnAnalysisError(
                f"simulation marker differs: {key}={hits}"
            )
        line_map[key] = hits[0]
    if not (
        line_map["sca"]
        < line_map["sca_d"]
        < line_map["matrices"]
        < line_map["reg_start"]
        < line_map["slice_start"]
        < line_map["interrupt"]
    ):
        raise Node0004V4ReturnAnalysisError(
            "simulation marker order differs"
        )
    interrupt = lines[line_map["interrupt"] - 1]
    match = re.fullmatch(r"Interrupt at time (\d+)", interrupt)
    if match is None:
        raise Node0004V4ReturnAnalysisError("interrupt marker differs")
    command = lines[0]
    cannot_open_count = sum("Cannot open" in line for line in lines)
    error_count = sum(
        "ERROR:" in line or line.startswith("Error:") for line in lines
    )
    observer_enabled_markers = sum(
        "[RETURN_OBSERVER] enabled" in line for line in lines
    )
    natural_terminal = any(
        marker in sim_log
        for marker in ("JSON_D config:", "$finish", "RETURN_OBS FINAL")
    )
    if (
        run_status != 124
        or cannot_open_count != 0
        or error_count != 0
        or natural_terminal
        or observer_enabled_markers != 0
        or "+RETURN_OBSERVER" in command
        or "r5_node0004_hw_v2_failclosed" in sim_log
        or "r5_n4_hw_v4_rootbind" not in command
    ):
        raise Node0004V4ReturnAnalysisError(
            "v4 simulation boundary differs"
        )

    checks = gate.get("checks")
    if not isinstance(checks, list) or len(checks) != 320:
        raise Node0004V4ReturnAnalysisError(
            "formal readback inventory differs"
        )
    missing = sum(row.get("status") == "missing" for row in checks)
    mismatch_records = sum(row.get("status") == "mismatch" for row in checks)
    preloaded = sum(
        row.get("runtime_target_preloaded") is True for row in checks
    )
    conjunction = {
        "compile_exit_status_zero": compile_status == 0,
        "every_required_run_exit_status_zero": run_status == 0,
        "natural_terminal_observed": natural_terminal,
        "formal_readback_exact_set_complete": missing == 0,
        "missing_count_zero": missing == 0,
        "mismatch_count_zero": gate.get("mismatch_byte_count") == 0,
    }
    if (
        gate.get("status") != "NODE0004_SERVER_FAILURE"
        or gate.get("readback_count") != 320
        or gate.get("missing_count") != 320
        or missing != 320
        or mismatch_records != 0
        or preloaded != 0
        or gate.get("mismatch_byte_count") != 0
        or all(conjunction.values())
    ):
        raise Node0004V4ReturnAnalysisError(
            "result gate conjunction differs"
        )

    with zipfile.ZipFile(source_path) as source:
        source_members = _safe_members(source)
        if source.testzip() is not None:
            raise Node0004V4ReturnAnalysisError("source ZIP CRC failed")
        manifest = _json(source, f"{SOURCE_ROOT}/package_manifest.json")
        runner = source.read(
            f"{SOURCE_ROOT}/PREPARE_AND_RUN.sh"
        ).decode("utf-8")
        runtime = source.read(
            f"{SOURCE_ROOT}/package_tools/"
            "node0004_assumed_hardware_server_runtime.py"
        ).decode("utf-8")
    if (
        manifest.get("install_name") != SOURCE_ROOT
        or manifest.get("candidate_release") is not False
        or manifest.get("server_source_identity_bound") is not False
        or manifest.get("functional_rtl_modified") is not False
        or manifest.get("server_rtl_entries") != 0
        or "+RETURN_OBSERVER" in runner
        or "return_observer.log" in runtime
    ):
        raise Node0004V4ReturnAnalysisError(
            "source observer-runtime gap differs"
        )

    return {
        "schema": "resnet50-node0004-v4-server-return-analysis-v1",
        "status": (
            "EXTERNAL_RUNNER_TIMEOUT_WITH_PACKAGE_OBSERVER_RUNTIME_DISABLED"
        ),
        "active_rule_receipts": RULE_RECEIPTS,
        "return_identity": {
            "path": str(returned_path),
            "size_bytes": returned_path.stat().st_size,
            "sha256": identities["return"],
            "sidecar": {
                "path": str(return_sidecar),
                "sha256": identities["return_sidecar"],
                "content_match": True,
                "formal_receipt_valid": True,
            },
            "embedded_install_name": allowlist["install_name"],
        },
        "zip_crc_exact_set_allowlist": {
            "zip_crc_valid": True,
            "file_count": len(members),
            "exact_set_valid": True,
            "allowlist_record_count": len(records),
            "allowlist_valid": True,
        },
        "bound_source": {
            "package": {
                "path": SOURCE_REL.as_posix(),
                "sha256": identities["source"],
                "file_count": len(source_members),
                "install_name": manifest["install_name"],
                "server_source_identity_bound": False,
            },
            "sidecar_sha256": identities["source_sidecar"],
            "validation_sha256": identities["source_validation"],
        },
        "package_install_observer_preflight": {
            "package": package_preflight,
            "install": install_preflight,
            "observer": observer,
            "all_preflight_gates_pass": True,
        },
        "compile_and_elaboration": {
            "compile_exit_status": compile_status,
            "compile_succeeded": True,
            "elaboration_zero_errors": True,
            "elaboration_warning_count": 1,
        },
        "simulation": {
            "run_exit_status": run_status,
            "run_status_interpretation": "EXTERNAL_12H_TIMEOUT",
            "simulation_started": True,
            "all_86_matrices_loaded": True,
            "cannot_open_count": cannot_open_count,
            "reg_started": True,
            "slice_started": True,
            "natural_terminal_observed": False,
            "interrupt_sim_time_ps": int(match.group(1)),
            "markers": line_map,
        },
        "formal_d_readback": {
            "expected_count": 320,
            "produced_count": 0,
            "missing_count": missing,
            "mismatch_record_count": mismatch_records,
            "mismatch_byte_count": gate["mismatch_byte_count"],
            "preloaded_target_count": preloaded,
            "exact_set_complete": False,
            "missing_all_with_zero_mismatch_is_numeric_pass": False,
        },
        "first_divergence": {
            "last_proven_good": (
                "all 86 c0 payloads transferred; Reg Started; slice start"
            ),
            "first_observed_bad": {
                "classification": "EXTERNAL_RUNNER_TIMEOUT",
                "sim_log_line": line_map["interrupt"],
                "sim_time_ps": int(match.group(1)),
            },
            "first_evidence_gap": {
                "classification": (
                    "PACKAGE_OBSERVER_RUNTIME_BINDING_AND_RETURN_MISSING"
                ),
                "simulator_argv_has_return_observer_plusarg": False,
                "observer_enabled_marker_count": observer_enabled_markers,
                "observer_log_returned": False,
                "mechanism": (
                    "The observer source passed SHA/XMR preflight and the "
                    "design compiled, but PREPARE_AND_RUN.sh never supplied "
                    "+RETURN_OBSERVER and the collector did not allowlist "
                    "return_observer.log. Therefore the interval from slice "
                    "start to the external timeout is internally unobserved."
                ),
            },
            "functional_first_divergence_resolved": False,
            "rtl_deadlock_claim_allowed": False,
        },
        "joint_result_gate": {
            "conditions": conjunction,
            "pass": False,
        },
        "evidence_adjudication": {
            "E3": {
                "pass": False,
                "reason": (
                    "external timeout, no natural terminal, and 0/320 D"
                ),
            },
            "E4": {
                "pass": False,
                "reason": (
                    "E3 failed and compatibility profile does not bind "
                    "server RTL source identity"
                ),
            },
            "E5": {
                "pass": False,
                "reason": "E4 failed and no independent passing rerun exists",
            },
        },
        "adjudication": {
            "v4_install_root_fix_confirmed": True,
            "conv_numeric_or_lifecycle_reached": False,
            "server_rtl_or_tb_defect_proven": False,
            "package_side_legal_fix_available": True,
            "successor_package_generated": True,
        },
        "blocker_delta": {
            "close": [
                "B_NODE0004_V3_RETURN_FORMAL_SIDECAR_MISSING",
                "B_NODE0004_V3_STALE_INSTALL_NAMESPACE_IN_SCA",
            ],
            "add": [
                "B_NODE0004_V4_EXTERNAL_RUNNER_TIMEOUT",
                "B_NODE0004_V4_OBSERVER_RUNTIME_BINDING_MISSING",
                "B_NODE0004_V5_DYNAMIC_RERUN_PENDING",
            ],
            "keep": [
                "B_NODE0004_DYNAMIC_RESULT_PENDING",
                "B_NODE0004_SERVER_RTL_IDENTITY_UNBOUND",
                "B_NODE0004_NO_DYNAMIC_BASELINE",
            ],
        },
        "rule_delta_proposal": [],
        "rule_delta_reason": (
            "Existing server observer and partial-return rules already "
            "require a disabled/missing observer to fail closed and forbid "
            "classifying an external signal as RTL deadlock."
        ),
        "package_release": {
            "status": "PACKAGE_READY_NOT_RUN",
            "install_name": "r5_n4_hw_v5_observe",
            "zip": V5_REL.as_posix(),
            "zip_sha256": identities["v5"],
            "sidecar": V5_SIDECAR_REL.as_posix(),
            "sidecar_sha256": identities["v5_sidecar"],
            "validation": V5_VALIDATION_REL.as_posix(),
            "validation_sha256": identities["v5_validation"],
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
            "single_command": (
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
            ),
            "expected_return": [
                "r5_n4_hw_v5_observe_return.zip",
                "r5_n4_hw_v5_observe_return.zip.sha256",
            ],
        },
        "claim_boundary": {
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "source_package_consumed_read_only": True,
            "source_workload_reused": True,
            "server_inspection_outside_return_performed": False,
            "server_upload_or_run_performed": False,
        },
    }


__all__ = [
    "Node0004V4ReturnAnalysisError",
    "analyze_node0004_v4_return",
]
