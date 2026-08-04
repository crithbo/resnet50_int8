from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_RETURN_SHA256 = (
    "3e7cde965e5852bc6a900c688461f3498a11cc41563ca39f987cf227ea2c6277"
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
EXPECTED_V4_SHA256 = (
    "61e28a7c218230869ad1a5247023edb9bf8ee9af5a0660124fc8966ce5ad239e"
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
V4_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v4_rootbind.zip"
)
V4_SIDECAR_REL = Path(str(V4_REL) + ".sha256")
V4_VALIDATION_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v4_rootbind.validation.json"
)
RETURN_ROOT = "r5_n4_hw_v3_obs_return"
SOURCE_ROOT = "r5_n4_hw_v3_obs"
STALE_PREFIX = "install/cfg_pkg/r5_node0004_hw_v2_failclosed/"
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
        "e3e44d47121b6c567b6e4c103b60c8012bbf09e8d904aabf9f1e4a03c016d97f"
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


class Node0004V3Return2AnalysisError(ValueError):
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
            raise Node0004V3Return2AnalysisError(
                f"unsafe ZIP member: {name}"
            )
        seen.add(name)
        if not info.is_dir():
            result.append(name)
    return result


def _json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise Node0004V3Return2AnalysisError(
            f"cannot parse JSON: {name}"
        ) from error
    if not isinstance(value, dict):
        raise Node0004V3Return2AnalysisError(
            f"JSON root must be object: {name}"
        )
    return value


def _status(archive: zipfile.ZipFile, name: str) -> int:
    try:
        return int(archive.read(name).decode("ascii").strip())
    except (KeyError, UnicodeError, ValueError) as error:
        raise Node0004V3Return2AnalysisError(
            f"cannot parse status: {name}"
        ) from error


def _sca_stale_inventory(source: zipfile.ZipFile) -> dict[str, Any]:
    files = [
        info
        for info in source.infolist()
        if re.fullmatch(
            rf"{SOURCE_ROOT}/workload/runtime/runs/[^/]+/sca_cfg(?:_D)?\.json",
            info.filename,
        )
    ]
    input_count = 0
    readback_count = 0
    for info in files:
        payload = source.read(info).decode("utf-8")
        count = payload.count(STALE_PREFIX)
        if info.filename.endswith("/sca_cfg.json"):
            input_count += count
        else:
            readback_count += count
    return {
        "sca_file_count": len(files),
        "stale_path_leaf_count": input_count + readback_count,
        "input_path_leaf_count": input_count,
        "formal_readback_path_leaf_count": readback_count,
    }


def analyze_node0004_v3_return2(
    project_root: Path, return_zip: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    returned_path = return_zip.resolve()
    return_sidecar = Path(str(returned_path) + ".sha256")
    source_path = root / SOURCE_REL
    source_sidecar_path = root / SOURCE_SIDECAR_REL
    source_validation_path = root / SOURCE_VALIDATION_REL
    v4_path = root / V4_REL
    v4_sidecar_path = root / V4_SIDECAR_REL
    v4_validation_path = root / V4_VALIDATION_REL
    required = (
        returned_path,
        source_path,
        source_sidecar_path,
        source_validation_path,
        v4_path,
        v4_sidecar_path,
        v4_validation_path,
    )
    for path in required:
        if not path.is_file():
            raise Node0004V3Return2AnalysisError(
                f"required identity is missing: {path}"
            )
    identities = {
        "return": sha256_file(returned_path),
        "source": sha256_file(source_path),
        "source_sidecar": sha256_file(source_sidecar_path),
        "source_validation": sha256_file(source_validation_path),
        "v4": sha256_file(v4_path),
        "v4_sidecar": sha256_file(v4_sidecar_path),
        "v4_validation": sha256_file(v4_validation_path),
    }
    if identities["return"] != EXPECTED_RETURN_SHA256:
        raise Node0004V3Return2AnalysisError("return identity differs")
    if (
        identities["source"] != EXPECTED_SOURCE_SHA256
        or identities["source_sidecar"] != EXPECTED_SOURCE_SIDECAR_SHA256
        or identities["source_validation"]
        != EXPECTED_SOURCE_VALIDATION_SHA256
    ):
        raise Node0004V3Return2AnalysisError("source identity differs")
    if identities["v4"] != EXPECTED_V4_SHA256:
        raise Node0004V3Return2AnalysisError("v4 identity differs")
    if source_sidecar_path.read_text(encoding="ascii") != (
        f"{EXPECTED_SOURCE_SHA256}  {source_path.name}\n"
    ):
        raise Node0004V3Return2AnalysisError("source sidecar content differs")
    if v4_sidecar_path.read_text(encoding="ascii") != (
        f"{EXPECTED_V4_SHA256}  {v4_path.name}\n"
    ):
        raise Node0004V3Return2AnalysisError("v4 sidecar content differs")

    source_validation = json.loads(
        source_validation_path.read_text(encoding="utf-8")
    )
    v4_validation = json.loads(
        v4_validation_path.read_text(encoding="utf-8")
    )
    if (
        source_validation.get("status") != "PACKAGE_READY_NOT_RUN"
        or source_validation.get("zip_sha256") != EXPECTED_SOURCE_SHA256
        or source_validation.get("observer_sha256") != EXPECTED_OBSERVER_SHA256
    ):
        raise Node0004V3Return2AnalysisError(
            "source validation identity differs"
        )
    if (
        v4_validation.get("status") != "PACKAGE_READY_NOT_RUN"
        or v4_validation.get("zip_sha256") != EXPECTED_V4_SHA256
        or v4_validation.get("numeric_analysis_repeated") is not False
        or v4_validation.get("node0004_workload_rebuilt") is not False
        or v4_validation.get("server_rtl_entries") != 0
        or v4_validation.get("path_resolution", {}).get(
            "stale_install_path_count"
        )
        != 0
    ):
        raise Node0004V3Return2AnalysisError("v4 validation differs")

    with zipfile.ZipFile(returned_path) as archive:
        members = _safe_members(archive)
        if archive.testzip() is not None:
            raise Node0004V3Return2AnalysisError("return ZIP CRC failed")
        expected_members = {
            f"{RETURN_ROOT}/{relative}" for relative in EXPECTED_RELATIVE_MEMBERS
        }
        if set(members) != expected_members:
            raise Node0004V3Return2AnalysisError("return exact-set differs")
        allowlist = _json(archive, f"{RETURN_ROOT}/RETURN_ALLOWLIST.json")
        records = allowlist.get("records")
        if (
            allowlist.get("schema") != "node0004-server-return-allowlist-v2"
            or allowlist.get("install_name") != SOURCE_ROOT
            or not isinstance(records, list)
            or len(records) != 9
        ):
            raise Node0004V3Return2AnalysisError(
                "return allowlist header differs"
            )
        declared: set[str] = set()
        for record in records:
            if not isinstance(record, dict) or not isinstance(
                record.get("path"), str
            ):
                raise Node0004V3Return2AnalysisError(
                    "return allowlist record differs"
                )
            relative = record["path"]
            member = f"{RETURN_ROOT}/{relative}"
            payload = archive.read(member)
            if (
                member not in expected_members
                or len(payload) != record.get("size_bytes")
                or hashlib.sha256(payload).hexdigest() != record.get("sha256")
            ):
                raise Node0004V3Return2AnalysisError(
                    f"return allowlist receipt differs: {relative}"
                )
            declared.add(member)
        if declared != expected_members - {
            f"{RETURN_ROOT}/RETURN_ALLOWLIST.json"
        }:
            raise Node0004V3Return2AnalysisError(
                "return allowlist exact-set differs"
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
        compile_driver_log = archive.read(
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
        raise Node0004V3Return2AnalysisError("preflight differs")
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
        or static_gate.get(
            "runtime_indexed_generated_instance_reference_count"
        )
        != 0
    ):
        raise Node0004V3Return2AnalysisError("observer guard differs")
    if (
        compile_status != 0
        or "Compilation completed!" not in compile_driver_log
        or "0 error(s), 1 warning(s)" not in compile_driver_log
        or "Error-[" in compile_log
        or "Undefined port" in compile_log
    ):
        raise Node0004V3Return2AnalysisError("compile closure differs")

    sim_lines = sim_log.splitlines()
    first_load = next(
        (
            index
            for index, line in enumerate(sim_lines, start=1)
            if "JSON: Loading matrix[0]:" in line
        ),
        None,
    )
    first_error = next(
        (
            index
            for index, line in enumerate(sim_lines, start=1)
            if f"ERROR: Cannot open file {STALE_PREFIX}" in line
        ),
        None,
    )
    cannot_open_count = sum(
        f"ERROR: Cannot open file {STALE_PREFIX}" in line
        for line in sim_lines
    )
    if (
        run_status != 124
        or first_load != 2221
        or first_error != 2235
        or cannot_open_count != 86
        or STALE_PREFIX not in sim_lines[first_load - 1]
        or f"/install/cfg_pkg/{SOURCE_ROOT}/runs/c0/sca_cfg.json"
        not in sim_lines[2216]
    ):
        raise Node0004V3Return2AnalysisError(
            "simulation first divergence differs"
        )
    terminal_markers = (
        "RETURN_OBS FINAL",
        "JSON_D config:",
        "$finish",
        "UVM_FATAL",
    )
    terminal_observed = any(marker in sim_log for marker in terminal_markers)
    if terminal_observed:
        raise Node0004V3Return2AnalysisError(
            "unexpected natural terminal evidence"
        )

    checks = gate.get("checks")
    if not isinstance(checks, list) or len(checks) != 320:
        raise Node0004V3Return2AnalysisError(
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
        "natural_terminal_observed": terminal_observed,
        "formal_readback_exact_set_complete": missing == 0,
        "missing_count_zero": missing == 0,
        "mismatch_count_zero": gate.get("mismatch_byte_count") == 0,
    }
    if (
        gate.get("status") != "NODE0004_SERVER_FAILURE"
        or gate.get("execution_gate", {}).get("compile_succeeded") is not True
        or gate.get("execution_gate", {}).get(
            "all_simulations_exited_zero"
        )
        is not False
        or gate.get("readback_count") != 320
        or gate.get("missing_count") != 320
        or missing != 320
        or mismatch_records != 0
        or preloaded != 0
        or gate.get("mismatch_byte_count") != 0
        or all(conjunction.values())
    ):
        raise Node0004V3Return2AnalysisError(
            "fail-closed conjunction differs"
        )

    with zipfile.ZipFile(source_path) as source:
        source_members = _safe_members(source)
        if source.testzip() is not None:
            raise Node0004V3Return2AnalysisError("source ZIP CRC failed")
        manifest = _json(source, f"{SOURCE_ROOT}/package_manifest.json")
        stale_inventory = _sca_stale_inventory(source)
    if (
        manifest.get("install_name") != SOURCE_ROOT
        or manifest.get("candidate_release") is not False
        or manifest.get("functional_rtl_modified") is not False
        or manifest.get("server_rtl_entries") != 0
        or manifest.get("server_source_identity_bound") is not False
        or stale_inventory
        != {
            "sca_file_count": 54,
            "stale_path_leaf_count": 846,
            "input_path_leaf_count": 526,
            "formal_readback_path_leaf_count": 320,
        }
    ):
        raise Node0004V3Return2AnalysisError(
            "source package stale-path proof differs"
        )

    return {
        "schema": "resnet50-node0004-v3-return2-analysis-v1",
        "status": (
            "FORMAL_RECEIPT_REJECTED_AND_PACKAGE_INSTALL_NAMESPACE_MISMATCH"
        ),
        "active_rule_receipts": RULE_RECEIPTS,
        "return_identity": {
            "path": str(returned_path),
            "size_bytes": returned_path.stat().st_size,
            "sha256": identities["return"],
            "filename_suffix_is_identity": False,
            "embedded_install_name": allowlist["install_name"],
        },
        "external_sidecar_and_formal_receipt": {
            "adjacent_sidecar_path": str(return_sidecar),
            "adjacent_sidecar_supplied": return_sidecar.is_file(),
            "formal_receipt_valid": False,
            "classification": "ADJACENT_RETURN_SIDECAR_MISSING",
        },
        "zip_crc_exact_set_allowlist": {
            "zip_crc_valid": True,
            "file_count": len(members),
            "exact_set_valid": True,
            "allowlist_schema": allowlist["schema"],
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
            "sidecar": {
                "path": SOURCE_SIDECAR_REL.as_posix(),
                "sha256": identities["source_sidecar"],
                "content_match": True,
            },
            "validation": {
                "path": SOURCE_VALIDATION_REL.as_posix(),
                "sha256": identities["source_validation"],
                "status": source_validation["status"],
            },
            "observer_sha256": EXPECTED_OBSERVER_SHA256,
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
            "simv_built": True,
            "prior_slice_rst_failure_inherited": False,
        },
        "simulation_and_natural_terminal": {
            "run_exit_status": run_status,
            "run_status_interpretation": "GNU_TIMEOUT_EXPIRED",
            "simulation_started": True,
            "natural_terminal_observed": False,
            "c0_sim_log_line_count": len(sim_lines),
            "stale_path_cannot_open_count": cannot_open_count,
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
            "formal_receipt": {
                "classification": "ADJACENT_RETURN_SIDECAR_MISSING",
                "occurs_before_zip_consumption": True,
            },
            "execution": {
                "classification": "PACKAGE_SCA_INSTALL_NAMESPACE_MISMATCH",
                "sca_loaded_from": (
                    "/home/panqs/ndp/NDP_copy01/install/cfg_pkg/"
                    "r5_n4_hw_v3_obs/runs/c0/sca_cfg.json"
                ),
                "first_stale_leaf_line": first_load,
                "first_stale_leaf": (
                    "install/cfg_pkg/r5_node0004_hw_v2_failclosed/"
                    "runs/c0/install/execplan.txt"
                ),
                "first_cannot_open_line": first_error,
                "source_package_stale_inventory": stale_inventory,
                "mechanism": (
                    "The v3 runner installed the workload under the v3 "
                    "namespace, while every SCA/SCA_D path leaf still named "
                    "the v2 namespace. The TB therefore resolved c0 inputs "
                    "against a directory this package did not install."
                ),
            },
        },
        "joint_result_gate": {
            "conditions": conjunction,
            "pass": False,
        },
        "evidence_adjudication": {
            "E3": {
                "pass": False,
                "reason": (
                    "simulation timed out without natural completion and "
                    "without any formal D readback"
                ),
            },
            "E4": {
                "pass": False,
                "reason": (
                    "E3 failed; return sidecar is absent; compatibility "
                    "profile does not bind server RTL source identity"
                ),
            },
            "E5": {
                "pass": False,
                "reason": "E4 failed and no independent passing rerun exists",
            },
        },
        "adjudication": {
            "classification": "PACKAGE_SIDE_INSTALL_ROOT_RELOCATION_DEFECT",
            "conv_numeric_or_lifecycle_reached": False,
            "server_rtl_or_tb_defect_proven": False,
            "package_side_legal_fix_available": True,
            "successor_package_generated": True,
            "reason": (
                "The compile/elaboration gate passed. The first simulator "
                "failure is a stale package install prefix in frozen SCA "
                "path strings, which is a package relocation defect and can "
                "be repaired without changing numeric data, addresses, RTL, "
                "or observer semantics."
            ),
        },
        "blocker_delta": {
            "close_from_latest_return": [
                "B_NODE0004_SERVER_RTL_COMPILE_INTERFACE_MISMATCH"
            ],
            "locally_remediated_by_v4": [
                "B_NODE0004_V3_STALE_INSTALL_NAMESPACE_IN_SCA"
            ],
            "add": [
                "B_NODE0004_V3_RETURN_FORMAL_SIDECAR_MISSING",
                "B_NODE0004_V4_DYNAMIC_RERUN_PENDING",
            ],
            "keep": [
                "B_NODE0004_DYNAMIC_RESULT_PENDING",
                "B_NODE0004_SERVER_RTL_IDENTITY_UNBOUND",
                "B_NODE0004_NO_DYNAMIC_BASELINE",
            ],
        },
        "rule_delta_proposal": [],
        "rule_delta_reason": (
            "Existing CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001 "
            "and section 5 already require package-local paths to resolve "
            "from the server root. This was a validator/build omission, not "
            "a missing normative rule."
        ),
        "package_release": {
            "status": "PACKAGE_READY_NOT_RUN",
            "install_name": "r5_n4_hw_v4_rootbind",
            "zip": V4_REL.as_posix(),
            "zip_sha256": identities["v4"],
            "sidecar": V4_SIDECAR_REL.as_posix(),
            "sidecar_sha256": identities["v4_sidecar"],
            "validation": V4_VALIDATION_REL.as_posix(),
            "validation_sha256": identities["v4_validation"],
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
            "single_command": (
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
            ),
            "expected_return": [
                "r5_n4_hw_v4_rootbind_return.zip",
                "r5_n4_hw_v4_rootbind_return.zip.sha256",
            ],
        },
        "claim_boundary": {
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "source_package_consumed_read_only": True,
            "source_workload_reused": True,
            "non_conv_retested": False,
            "server_inspection_outside_return_performed": False,
            "server_upload_or_run_performed": False,
        },
    }


__all__ = [
    "Node0004V3Return2AnalysisError",
    "analyze_node0004_v3_return2",
]
