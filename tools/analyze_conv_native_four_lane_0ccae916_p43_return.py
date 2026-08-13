#!/usr/bin/env python3
"""Validate the native-Conv p43 formal return and classify its time-0 escape."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p43_portablevq"
EXECUTION = "r1786512367639483307_1421638"
RETURN = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p43_portablevq_"
    r"r1786512367639483307_1421638_return.zip"
)
SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE}.zip"
)
EXPECTED_RETURN_BYTES = 8_098_284
EXPECTED_RETURN_SHA256 = "c26fdc4c191cbaa2fec244fe8fd9c1629d77fc1807186e7089324529ebccb095"
EXPECTED_SOURCE_BYTES = 6_016_442
EXPECTED_SOURCE_SHA256 = "657767774ef6762f4e93c3c0b23da71895c7ec699837ca443b0210457d55c11c"
OUTPUT_ROOT = ROOT / "outputs/conv_native_four_lane_0ccae916_p43_return_analysis"
OUTPUT = OUTPUT_ROOT / "report.json"
WAVE_INSPECTION = OUTPUT_ROOT / "waveform_inspection.json"
WAVE_EXTRACTION = OUTPUT_ROOT / "waveform_extraction_receipt.json"


class AnalysisError(RuntimeError):
    pass


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha_file(path),
    }


def safe_zip(path: Path, expected_root: str) -> tuple[zipfile.ZipFile, dict[str, zipfile.ZipInfo]]:
    archive = zipfile.ZipFile(path)
    if archive.testzip() is not None:
        archive.close()
        raise AnalysisError(f"CRC failure: {path}")
    members: dict[str, zipfile.ZipInfo] = {}
    roots: set[str] = set()
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        mode = (info.external_attr >> 16) & 0o170000
        if (
            info.filename in members
            or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
            or "\\" in info.filename
            or mode == stat.S_IFLNK
            or info.filename.lower().endswith((".zip", ".tar", ".tgz", ".tar.gz"))
        ):
            archive.close()
            raise AnalysisError(f"unsafe, duplicate, symlink, or nested archive member: {info.filename}")
        members[info.filename] = info
        roots.add(pure.parts[0])
    if roots != {expected_root}:
        archive.close()
        raise AnalysisError(f"single-root mismatch: {sorted(roots)}")
    return archive, members


def read(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    root: str,
    relative: str,
) -> bytes:
    name = f"{root}/{relative}"
    if name not in members:
        raise AnalysisError(f"required member absent: {name}")
    return archive.read(name)


def load_json(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    root: str,
    relative: str,
) -> Any:
    return json.loads(read(archive, members, root, relative))


def main() -> int:
    for path in (RETURN, SOURCE, WAVE_INSPECTION, WAVE_EXTRACTION):
        if not path.is_file():
            raise AnalysisError(f"required evidence absent: {path}")

    return_root = f"{PACKAGE}_return"
    return_zip, return_members = safe_zip(RETURN, return_root)
    source_zip, source_members = safe_zip(SOURCE, PACKAGE)
    try:
        core = load_json(return_zip, return_members, return_root, "RETURN_CORE_MANIFEST.json")
        core_status = load_json(
            return_zip, return_members, return_root, "return_core/RETURN_CORE_STATUS.json"
        )
        sim_exit = load_json(
            return_zip, return_members, return_root, "return_core/SIM_EXIT_RECEIPT.json"
        )
        gate = load_json(return_zip, return_members, return_root, "evidence/SERVER_RESULT_GATE.json")
        package_status = load_json(
            return_zip, return_members, return_root, "evidence/package_local_preflight_status.json"
        )
        production_identity = load_json(
            return_zip, return_members, return_root, "evidence/production_rtl_identity.json"
        )
        triggered = load_json(
            return_zip, return_members, return_root, "evidence/triggered_causal_summary.json"
        )
        source_bound = load_json(
            return_zip, return_members, return_root, "evidence/source_bound_causal_decision.json"
        )
        mse4 = load_json(
            return_zip, return_members, return_root, "evidence/mse4_join_decision.json"
        )
        waveform = load_json(
            return_zip,
            return_members,
            return_root,
            "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
        )
        portable = load_json(
            return_zip,
            return_members,
            return_root,
            "evidence/portable/PORTABLE_WAVEFORM_RUNTIME_RECEIPT.json",
        )
        portable_status = load_json(
            return_zip,
            return_members,
            return_root,
            "evidence/portable/PORTABLE_FIRST_FRESH_STATUS.json",
        )
        query = load_json(
            return_zip,
            return_members,
            return_root,
            "evidence/portable/SIGNAL_QUERY_RECEIPT.json",
        )
        query_source = read(
            return_zip,
            return_members,
            return_root,
            "evidence/portable/PORTABLE_QUERY_SOURCE_REPORT.json",
        )
        actual_sim_argv = load_json(
            return_zip, return_members, return_root, "runs/c0/actual_sim_argv.json"
        )
        sim_log = read(return_zip, return_members, return_root, "runs/c0/sim.log").decode(
            "utf-8", errors="replace"
        )
        dump_tcl = read(
            return_zip, return_members, return_root, "runs/run/codex_waveform_portable.tcl"
        ).decode("utf-8", errors="replace")
        source_bound_log = read(
            return_zip, return_members, return_root, "runs/c0/source_bound_causal.log"
        )
        host_progress = read(
            return_zip, return_members, return_root, "runs/c0/host_progress.log"
        ).decode("utf-8", errors="replace")

        returned_manifest = read(
            return_zip, return_members, return_root, "source_package/package_manifest.json"
        )
        returned_binding = read(
            return_zip,
            return_members,
            return_root,
            "source_package/source_bound_probe_binding.json",
        )
        returned_generation = read(
            return_zip,
            return_members,
            return_root,
            "source_package/source_bound_generation_report.json",
        )
        source_manifest = read(source_zip, source_members, PACKAGE, "package_manifest.json")
        source_binding = read(
            source_zip, source_members, PACKAGE, "diagnostics/source_bound_probe_binding.json"
        )
        source_generation = read(
            source_zip,
            source_members,
            PACKAGE,
            "diagnostics/source_bound_generation_report.json",
        )
        source_query_source = read(
            source_zip,
            source_members,
            PACKAGE,
            "diagnostics/portable_query_source_report.json",
        )

        core_receipt_mismatches: dict[str, Any] = {}
        for row in core.get("core_entry_receipts", []):
            data = read(return_zip, return_members, return_root, row["path"])
            observed = {"bytes": len(data), "sha256": sha_bytes(data)}
            expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
            if observed != expected:
                core_receipt_mismatches[row["path"]] = {
                    "expected": expected,
                    "observed": observed,
                }

        expected_tcl = (
            "dump -file install/codex_runs/r5_n4_0cc_p43_portablevq/a0/run/sim_results/wave.vpd -type VPD\n"
            "dump -add tb_NDP_Top_new_phy -depth 0 -aggregates\n"
            "dump -file install/codex_runs/r5_n4_0cc_p43_portablevq/a0/run/sim_results/wave.vcd -type VCD\n"
            "dump -add tb_NDP_Top_new_phy -depth 0 -aggregates\n"
            "run\n"
            "quit\n"
        )
        wave_members = [name for name in return_members if "/waveforms/" in name]
        vcd_members = [name for name in return_members if name.lower().endswith(".vcd")]
        candidate_coverage = query.get("candidate_coverage", {})
        query_events = query.get("events", [])
        wave_inspection = json.loads(WAVE_INSPECTION.read_text(encoding="utf-8"))
        wave_extraction = json.loads(WAVE_EXTRACTION.read_text(encoding="utf-8"))
        execution_gate = gate.get("execution_gate", {})

        checks = {
            "formal_return_identity_exact": RETURN.stat().st_size == EXPECTED_RETURN_BYTES
            and sha_file(RETURN) == EXPECTED_RETURN_SHA256,
            "source_package_identity_exact": SOURCE.stat().st_size == EXPECTED_SOURCE_BYTES
            and sha_file(SOURCE) == EXPECTED_SOURCE_SHA256,
            "return_crc_single_root_path_safe_no_nested_archive": True,
            "source_crc_single_root_path_safe_no_nested_archive": True,
            "return_core_receipts_exact": not core_receipt_mismatches,
            "execution_identity_exact": core.get("package_id") == PACKAGE
            and core.get("execution_id") == EXECUTION
            and core.get("return_basename") == RETURN.name,
            "returned_source_identity_exact": returned_manifest == source_manifest
            and returned_binding == source_binding
            and returned_generation == source_generation
            and query_source == source_query_source,
            "production_compile_success": read(
                return_zip, return_members, return_root, "evidence/compile_exit_status.txt"
            ).decode("ascii").strip()
            == "0"
            and execution_gate.get("compile_succeeded") is True
            and package_status.get("production_compile_started") is True,
            "simv_zero_is_not_dut_success": read(
                return_zip, return_members, return_root, "evidence/run_exit_status.txt"
            ).decode("ascii").strip()
            == "0"
            and sim_exit.get("sim_exit_code") == 0
            and sim_exit.get("signal") == "NONE"
            and sim_exit.get("natural_terminal_observed") is False
            and package_status.get("dut_simulation_started") is False,
            "actual_sim_argv_same_attempt_flags": all(
                token in actual_sim_argv
                for token in (
                    "DUMP_VCD=1",
                    "DUMP_FSDB=0",
                    "TB_DUMP_FSDB=0",
                    "DUMP_PORTABLE_VCD=1",
                    "-ucli",
                )
            )
            and any("/a0/" in token for token in actual_sim_argv),
            "exact_shared_direct_vcd_tcl": dump_tcl == expected_tcl,
            "production_vcs_rejects_direct_vcd_ucli": all(
                token in sim_log
                for token in (
                    "Compiler version V-2023.12-SP2_Full64",
                    "Error-[UCLI-DUMP-UNSUPP-FORMAT] Unsupported dump format",
                    "The supported formats are EVCD and VPD.",
                    "Time: 0 ps",
                )
            ),
            "tcl_aborted_before_run": sim_log.count("ucli%") == 4
            and "ucli% run" not in sim_log
            and dump_tcl.index("-type VCD") < dump_tcl.index("\nrun\n"),
            "no_dut_progress_or_rows": source_bound_log == b""
            and triggered.get("status") == "SIM_NOT_STARTED"
            and triggered.get("observer", {}).get("present") is False
            and "trigger_bytes=0 public_bytes=0" in host_progress
            and source_bound.get("raw_record_count") == 0
            and mse4.get("raw_boundary_record_count") == 0,
            "raw_vpd_partial_identity_valid": wave_inspection.get("pass") is True
            and wave_extraction.get("pass") is True
            and waveform.get("pass") is True
            and waveform.get("all_matching_collected") is True
            and waveform.get("no_size_limit") is True
            and len(waveform.get("waveforms", [])) == 1
            and waveform["waveforms"][0].get("format") == "VPD"
            and waveform["waveforms"][0].get("completeness") == "PARTIAL"
            and wave_members == [
                f"{return_root}/waveforms/run/sim_results/wave.vpd"
            ],
            "direct_vcd_absent": not vcd_members
            and portable.get("portable_vcd", {}).get("status") == "FAILED",
            "query_zero_and_incomplete": query.get("completeness") == "PARTIAL"
            and query.get("capture", {}).get("flush_complete") is False
            and query_events == []
            and candidate_coverage.get("covered") == []
            and candidate_coverage.get("missing") == candidate_coverage.get("expected"),
            "same_attempt_portable_binding": portable.get("package_id") == PACKAGE
            and portable.get("execution_id") == EXECUTION
            and portable.get("attempt_id") == "a0"
            and portable_status.get("package_id") == PACKAGE
            and portable_status.get("execution_id") == EXECUTION
            and portable_status.get("attempt_id") == "a0",
            "portable_contract_fail_closed": portable_status.get("pass") is False
            and portable_status.get("diagnostic_status") == "DIAGNOSTIC_EVIDENCE_INCOMPLETE"
            and portable_status.get("return_must_publish") is True
            and set(portable_status.get("preserve_on_failure", []))
            == {"raw_vpd", "compile_core", "sim_core", "signal_core", "return_core"}
            and core.get("disposition") == "EVIDENCE_INCOMPLETE"
            and core_status.get("disposition") == "EVIDENCE_INCOMPLETE",
            "no_result_overclaim": execution_gate.get("c0_natural_terminal") is False
            and execution_gate.get("formal_D_claimed") is False
            and execution_gate.get("E3_claimed") is False
            and execution_gate.get("E4_claimed") is False
            and execution_gate.get("E5_claimed") is False,
        }
        valid = all(checks.values())
        report = {
            "schema": "conv-native-four-lane-0ccae916-p43-return-analysis-v1",
            "status": (
                "RETURN_ANALYSIS_COMPLETE_SHARED_PORTABLE_METHOD_RUNTIME_ESCAPE_SUCCESSOR_HOLD"
                if valid
                else "RETURN_ANALYSIS_INVALID"
            ),
            "valid": valid,
            "errors": [name for name, passed in checks.items() if not passed],
            "package_id": PACKAGE,
            "execution_id": EXECUTION,
            "previous_version_progress": (
                "p41 proved production compile beyond the Datahub public-surface repair; p42 corrected "
                "the package-local two-bit valid/ready scalar-comparison false negative while retaining "
                "the MSE4 wdata/slice-finish target."
            ),
            "current_version_purpose": (
                "p43 preserves the corrected vector-handshake diagnostic and adds same-attempt raw VPD, "
                "direct VCD, and complete source-bound query/event evidence for locally actionable MSE4 "
                "causal localization."
            ),
            "formal_return": receipt(RETURN),
            "source_package": receipt(SOURCE),
            "integrity": {
                "checks": checks,
                "return_member_count": len(return_members),
                "source_member_count": len(source_members),
                "core_receipt_mismatches": core_receipt_mismatches,
                "missing_required_entries": core.get("missing_required_entries"),
            },
            "execution": {
                "compile_exit_status": 0,
                "simv_exit_status": 0,
                "signal_status": "NONE",
                "simulator_process_started": True,
                "dut_time_advanced": False,
                "final_simulation_time": "0 ps",
                "natural_terminal": False,
                "actual_compile_identity_collected": execution_gate.get(
                    "actual_compile_identity_collected"
                ),
                "actual_compile_argv_identity": portable_status.get("identities", {}).get(
                    "actual_compile_argv"
                ),
                "actual_sim_argv": actual_sim_argv,
                "production_rtl_identity": {
                    "collection_valid": production_identity.get("collection_valid"),
                    "authority_classification": production_identity.get("authority_classification"),
                    "identity_difference_blocks_simulator": production_identity.get(
                        "identity_difference_blocks_simulator"
                    ),
                },
            },
            "waveform_and_query": {
                "raw_vpd": waveform,
                "raw_vpd_return_inspection": wave_inspection,
                "raw_vpd_safe_extraction": wave_extraction,
                "direct_vcd_present": False,
                "portable_runtime": portable,
                "portable_first_fresh_status": portable_status,
                "signal_query": query,
                "portable_gap_closed": False,
                "same_attempt_binding_valid_but_payload_incomplete": True,
            },
            "causal_localization": {
                "LAST_PROVEN_GOOD": (
                    "The exact p43 source identity passed production compile; VCS V-2023.12-SP2 launched, "
                    "accepted the authoritative VPD destination and depth-0 tb_NDP_Top_new_phy dump setup, "
                    "and returned the identity-valid unbounded partial raw VPD."
                ),
                "FIRST_DIVERGENCE": (
                    "At Tcl line 3 and simulation time 0 ps, production VCS rejected "
                    "`dump -file .../wave.vcd -type VCD` as UCLI-DUMP-UNSUPP-FORMAT; only EVCD and VPD "
                    "are supported, so the later `run` command was never executed."
                ),
                "execution_root_classification": "SHARED_PORTABLE_METHOD_RUNTIME_ESCAPE",
                "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
                "root_scope": "shared portable waveform runtime method, not DUT/config/numeric/workload/RTL",
                "mse4_target_root_classification": "UNRESOLVED_NO_DUT_TIME_OR_CAUSAL_ROWS",
                "simv_zero_is_dut_success": False,
                "source_bound_rows": 0,
                "mse4_join": mse4,
                "portable_observer_local_decoder_gap_closed": False,
            },
            "result_conjunction": {
                "production_compile": True,
                "simulator_process_started": True,
                "dut_simulation_advanced": False,
                "natural_terminal": False,
                "formal_D": False,
                "E3": False,
                "E4": False,
                "E5": False,
                "passed": False,
            },
            "successor_adjudication": {
                "decision": "HOLD_FRESH_SUCCESSOR",
                "blocking_activation": "CURRENT_DISK_PORTABLE_METHOD_RUNTIME_FIX_READY",
                "reason": (
                    "The failure is repairable only after the shared direct-portable runtime method and "
                    "its public validator/dispatch contract are corrected by their owner. Family scope "
                    "must not patch shared tools or release a successor against the invalid method."
                ),
                "fresh_successor_built": False,
                "current_pending_mutated": False,
                "frozen": [
                    "config",
                    "numeric",
                    "workload",
                    "golden",
                    "functional RTL",
                    "p42 vector-handshake diagnostic",
                    "MSE4 wdata/slice-finish target",
                ],
                "server_action": False,
            },
            "rule_feedback": {
                "type": "RULE_DELTA_REQUIRED_ALREADY_DISPATCHED_TO_SHARED_METHOD_OWNER",
                "rule_id": "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001",
                "observed_invalid_assumption": (
                    "Production VCS UCLI V-2023.12-SP2 does not support `dump -type VCD`; it reports only "
                    "EVCD and VPD and exits the Tcl flow before time advance while simv still returns zero."
                ),
                "family_action": "READ_RETURN_AND_HOLD_SUCCESSOR",
            },
            "claim_boundary": (
                "This analysis proves exact return/source identity, production compile success, a time-0 "
                "shared portable-method runtime escape, raw partial VPD integrity, absent direct VCD, and "
                "zero/incomplete query evidence. It does not claim DUT success, MSE4 signal causality, "
                "natural terminal, formal D, E3/E4/E5, numeric correctness, performance, or an RTL root."
            ),
            "server_action": False,
        }
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(
            json.dumps(
                {
                    "valid": valid,
                    "status": report["status"],
                    "output": str(OUTPUT),
                    "bytes": OUTPUT.stat().st_size,
                    "sha256": sha_file(OUTPUT),
                },
                sort_keys=True,
            )
        )
        return 0 if valid else 1
    finally:
        return_zip.close()
        source_zip.close()


if __name__ == "__main__":
    raise SystemExit(main())
