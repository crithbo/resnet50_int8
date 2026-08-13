#!/usr/bin/env python3
"""Formally adjudicate the supplied QAdd v57h production return.

The analyzer is read-only with respect to the return ZIP.  It validates the
archive/core-manifest identities, consumes the package-owned canonical and
stage-result records, and emits a bounded machine decision.  It does not run
the DUT, alter configuration/numeric/RTL assets, or claim formal D.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


PACKAGE_ID = "r5_qadd_n7_tailround_lanephase_qual_v57h"
EXPECTED_RETURN_BYTES = 298429
EXPECTED_RETURN_SHA256 = (
    "8c273ca2a178a43a3e8578c9b597b4b44d3e067461b32155e3ca75db1e2462f7"
)
EXPECTED_ROOT = f"{PACKAGE_ID}_return"
RULE_EPOCH = "waveform-mandatory-v2-01ca6d7cd4a4a270"
RULE_ID = "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001"


class AnalysisError(RuntimeError):
    """A formal-return integrity or adjudication failure."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _safe_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    if archive.testzip() is not None:
        raise AnalysisError("return ZIP CRC validation failed")
    result: dict[str, zipfile.ZipInfo] = {}
    roots: set[str] = set()
    for info in archive.infolist():
        path = PurePosixPath(info.filename)
        mode = (info.external_attr >> 16) & 0o170000
        if (
            info.filename in result
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or "\\" in info.filename
            or mode == stat.S_IFLNK
        ):
            raise AnalysisError(f"unsafe or duplicate return member: {info.filename}")
        result[info.filename] = info
        roots.add(path.parts[0])
    if roots != {EXPECTED_ROOT}:
        raise AnalysisError(f"return root differs: {sorted(roots)}")
    return result


def _name(relative: str) -> str:
    return f"{EXPECTED_ROOT}/{relative}"


def _read(archive: zipfile.ZipFile, members: dict[str, zipfile.ZipInfo], relative: str) -> bytes:
    name = _name(relative)
    if name not in members:
        raise AnalysisError(f"required return member is absent: {name}")
    return archive.read(name)


def _json(archive: zipfile.ZipFile, members: dict[str, zipfile.ZipInfo], relative: str) -> Any:
    try:
        return json.loads(_read(archive, members, relative))
    except json.JSONDecodeError as error:
        raise AnalysisError(f"invalid JSON member {relative}: {error}") from error


def _integer_text(
    archive: zipfile.ZipFile, members: dict[str, zipfile.ZipInfo], relative: str
) -> int:
    try:
        return int(_read(archive, members, relative).decode("ascii").strip())
    except (UnicodeDecodeError, ValueError) as error:
        raise AnalysisError(f"invalid integer member {relative}") from error


def _receipt(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def analyze(return_zip: Path) -> dict[str, Any]:
    errors: list[str] = []
    if not return_zip.is_file():
        raise AnalysisError(f"return ZIP is absent: {return_zip}")
    identity = _receipt(return_zip)
    if identity["bytes"] != EXPECTED_RETURN_BYTES:
        errors.append("formal return byte count differs from dispatch")
    if identity["sha256"] != EXPECTED_RETURN_SHA256:
        errors.append("formal return SHA-256 differs from dispatch")

    with zipfile.ZipFile(return_zip) as archive:
        members = _safe_members(archive)
        core_manifest = _json(archive, members, "RETURN_CORE_MANIFEST.json")
        core_status = _json(archive, members, "return_core/RETURN_CORE_STATUS.json")
        sim_receipt = _json(archive, members, "return_core/SIM_EXIT_RECEIPT.json")
        canonical = _json(
            archive, members, "evidence/CANONICAL_PROGRESS_DECISION.json"
        )
        source_bound = _json(
            archive, members, "evidence/source_bound_causal_decision.json"
        )
        source_filter = _json(
            archive, members, "evidence/source_bound_stage_filter_receipt.json"
        )
        result_gate = _json(archive, members, "evidence/SERVER_RESULT_GATE.json")
        compile_exit = _integer_text(
            archive, members, "evidence/compile_exit_status.txt"
        )
        simulation_exit = _integer_text(
            archive, members, "evidence/simulation_exit_status.txt"
        )
        compile_argv = _read(
            archive, members, "evidence/actual_compile_argv.txt"
        ).decode("utf-8", errors="replace").strip()
        simulator_argv = _read(
            archive, members, "evidence/actual_simulator_argv.txt"
        ).decode("utf-8", errors="replace").strip()

        manifest_errors: list[str] = []
        for row in core_manifest.get("core_entry_receipts", []):
            relative = row.get("path")
            name = _name(relative) if isinstance(relative, str) else ""
            if name not in members:
                if row.get("required") is True:
                    manifest_errors.append(f"missing required core member: {relative}")
                continue
            data = archive.read(name)
            if len(data) != row.get("bytes") or sha256_bytes(data) != row.get("sha256"):
                manifest_errors.append(f"core identity mismatch: {relative}")
        errors.extend(manifest_errors)

        waveform_members = [
            name
            for name in members
            if PurePosixPath(name).name == "wave.vpd"
            or PurePosixPath(name).name.startswith("wave.vpd.")
        ]

    last_state = canonical.get("last_state", {})
    last_flow = canonical.get("last_flow", {})
    matrix = canonical.get("candidate_matrix", {})
    request_decode = matrix.get("C_BUFFER5_MRM_REQUEST_DECODE", {})
    read_accept = matrix.get("C_BUFFER5_READ_ACCEPT", {})
    lane_validity = matrix.get("C_BUFFER5_ROW_BANK_LANE_VALIDITY", {})
    port_selection = matrix.get("C_PINGPONG_PORT_SELECTION", {})
    conjunction = result_gate.get("result_gate_conjunction", {})

    adjudication_checks = {
        "compile_succeeded": compile_exit == 0,
        "simulation_started": sim_receipt.get("sim_started") is True,
        "simulation_timed_out": simulation_exit == 124,
        "natural_terminal_absent": sim_receipt.get("natural_terminal_observed") is False,
        "tailround_stage1_entered": canonical.get("ordered_start_count") == 1
        and last_state.get("stage") == 1,
        "tailround_stage1_not_finished": canonical.get("ordered_finish_count") == 0,
        "buffer5_request_decoded": request_decode.get("observed") is True
        and last_state.get("req_valid") == 0xFF
        and last_state.get("rd_en") == 0xFF,
        "buffer5_read_never_accepted": read_accept.get("observed") is False
        and read_accept.get("read_accepts") == 0
        and last_flow.get("buf5_rd") == 0,
        "selected_port_not_ready": port_selection.get("observed") is True
        and last_state.get("selected_ready") == 0
        and last_state.get("ready0") == 0
        and last_state.get("pingpong") == 0,
        "required_bank_lanes_not_ready": lane_validity.get("observed") is True
        and last_state.get("bank_ready") == 0
        and last_state.get("req_strb") == 0x33333333
        and last_state.get("valid_at_req") == 0xCCCCCCCC,
        "formal_d_absent": result_gate.get("observed_readback_count") == 0
        and result_gate.get("missing_count") == 28
        and conjunction.get("output_exact_set_complete") is False,
        "core_return_complete": not core_status.get("missing_required_entries")
        and not core_manifest.get("missing_required_entries"),
    }
    errors.extend(name for name, passed in adjudication_checks.items() if passed is not True)

    return {
        "schema": "qlinearadd-node0007-v57h-formal-return-analysis-v1",
        "status": "RETURN_ANALYSIS_COMPLETE_SUCCESSOR_REQUIRED" if not errors else "RETURN_ANALYSIS_INVALID",
        "pass": not errors,
        "errors": errors,
        "family": "qlinearadd_node0007",
        "package_id": PACKAGE_ID,
        "execution_id": core_status.get("execution_id"),
        "formal_return": identity,
        "integrity": {
            "safe_single_root_crc_clean": True,
            "core_manifest_identity_errors": manifest_errors,
            "required_core_missing": core_status.get("missing_required_entries", []),
            "member_count": len(members),
        },
        "execution": {
            "compile_exit_status": compile_exit,
            "simulation_started": sim_receipt.get("sim_started"),
            "simulation_exit_status": simulation_exit,
            "signal": sim_receipt.get("signal"),
            "natural_terminal_observed": sim_receipt.get("natural_terminal_observed"),
            "actual_compile_argv": compile_argv,
            "actual_simulator_argv": simulator_argv,
            "old_waveform_semantics": {
                "DUMP_VCD": 0,
                "DUMP_FSDB": 0,
                "TB_DUMP_FSDB": 0,
                "waveform_member_count": len(waveform_members),
                "claim_boundary": "Historical v57h execution only; it is not compliant with the activated next-fresh waveform gate.",
            },
        },
        "adjudication_checks": adjudication_checks,
        "LAST_PROVEN_GOOD": {
            "boundary": "C_BUFFER5_MRM_REQUEST_DECODE",
            "time_ps": last_state.get("time_ps"),
            "stage": "op_tail_round/stage1/slice0",
            "fact": "The first tail-round stage started and decoded a Buffer5 read request.",
            "evidence": {
                "ordered_start_count": canonical.get("ordered_start_count"),
                "req_valid": last_state.get("req_valid"),
                "rd_en": last_state.get("rd_en"),
                "req_addr": last_state.get("req_addr"),
                "req_strb": last_state.get("req_strb"),
                "mse0_req": last_flow.get("mse0_req"),
                "buffer5_write_accepts": last_flow.get("buf5_wr"),
            },
        },
        "FIRST_DIVERGENCE": {
            "boundary": "C_BUFFER5_ROW_BANK_LANE_VALIDITY_TO_C_BUFFER5_READ_ACCEPT",
            "classification": "SELECTED_PINGPONG_PORT_REQUIRED_LANES_NOT_READY",
            "fact": "The decoded read targets ping-pong port 0, but its required bank/lane conjunction never becomes ready, so no Buffer5 read is accepted.",
            "evidence": {
                "pingpong": last_state.get("pingpong"),
                "ready0": last_state.get("ready0"),
                "ready1": last_state.get("ready1"),
                "selected_ready": last_state.get("selected_ready"),
                "bank_ready": last_state.get("bank_ready"),
                "req_strb": last_state.get("req_strb"),
                "valid_at_req": last_state.get("valid_at_req"),
                "missing_lanes": lane_validity.get("missing_lanes"),
                "failed_banks": lane_validity.get("failed_banks"),
                "read_accepts": read_accept.get("read_accepts"),
            },
            "causal_limit": "The old return has no waveform, so the exact temporal producer/clear/port-ready cause inside this boundary remains unresolved.",
        },
        "formal_D": {
            "expected": result_gate.get("expected_readback_count"),
            "observed": result_gate.get("observed_readback_count"),
            "missing": result_gate.get("missing_count"),
            "mismatch_evaluable": result_gate.get("mismatch_evaluable"),
            "claimed": False,
        },
        "diagnostic_progress": {
            "canonical_decision": canonical.get("decision"),
            "source_bound_decision": source_bound.get("decision"),
            "source_bound_stage_start_found": source_filter.get("stage_start_found"),
            "qualified_frozen_windows": canonical.get("qualified_frozen_windows"),
            "stable_window_active_cycles": 2097152,
            "preserved_target": "tail-round/lane-phase Buffer5 request-decode to read-accept gap",
        },
        "previous_progress": (
            "v57h passed production compile, entered simulation and reached the first "
            "tail-round stage; it timed out without a natural terminal and produced no formal D."
        ),
        "fresh_successor_purpose": (
            "Preserve the v57h tail-round/lane-phase diagnostic and capture mandatory, "
            "unbounded, full-hierarchy depth-0 VPD plus formal-return evidence in one "
            "attempt to resolve the selected-port/bank-lane readiness stall."
        ),
        "successor_directive": {
            "shared_gate_epoch": RULE_EPOCH,
            "rule_id": RULE_ID,
            "make_arguments": {
                "DUMP_VCD": 1,
                "DUMP_FSDB": 0,
                "TB_DUMP_FSDB": 0,
            },
            "scope": "tb_NDP_Top_new_phy",
            "hierarchy_depth": 0,
            "excluded_scopes": [],
            "waveform_size_limit_bytes": None,
            "changed_surfaces": ["fresh identity", "waveform", "runtime/formal return"],
            "frozen": [
                "config",
                "numeric",
                "workload semantics",
                "golden",
                "functional RTL",
                "target diagnostic",
            ],
            "server_action": False,
        },
        "claim_boundary": (
            "Formal analysis of the exact returned compile/simulation/log evidence. "
            "The first missing causal conjunction is localized, but waveform-free v57h "
            "cannot resolve its internal temporal cause and does not establish formal D/E4/E5."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = analyze(args.return_zip)
    except (OSError, zipfile.BadZipFile, AnalysisError) as error:
        result = {
            "schema": "qlinearadd-node0007-v57h-formal-return-analysis-v1",
            "status": "RETURN_ANALYSIS_INVALID",
            "pass": False,
            "errors": [f"{type(error).__name__}: {error}"],
        }
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("pass") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
