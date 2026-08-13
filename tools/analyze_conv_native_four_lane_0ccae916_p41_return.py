#!/usr/bin/env python3
"""Validate p41 formal-return evidence and classify its remaining observer gap."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p41_vpdfull"
EXECUTION = "r1786457691694343631_1196369"
RETURN = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p41_vpdfull_"
    r"r1786457691694343631_1196369_return.zip"
)
RETURN_BYTES = 8_660_560
RETURN_SHA256 = "d39b21af39c0c79b2b6cfe7e3546f196fd0eb432564555a3f914149eaf00a1fc"
SOURCE_BYTES = 5_986_703
SOURCE_SHA256 = "339d8f4e17cbf34132be9bc84f33dec637ea3fd6ecc8deeec5aa5620a012a95a"
OUTPUT_ROOT = ROOT / "outputs/conv_native_four_lane_0ccae916_p41_return_analysis"
OUTPUT = OUTPUT_ROOT / "report.json"
WAVE_INSPECTION = OUTPUT_ROOT / "waveform_return_inspection.json"
WAVE_EXTRACTION = OUTPUT_ROOT / "waveform_extraction.json"
WAVE_IDENTITY = OUTPUT_ROOT / "waveform_vpd_identity.json"


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


def safe_zip(path: Path, expected_root: str) -> tuple[zipfile.ZipFile, dict[str, zipfile.ZipInfo]]:
    archive = zipfile.ZipFile(path)
    if archive.testzip() is not None:
        archive.close()
        raise AnalysisError(f"CRC validation failed: {path}")
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
            raise AnalysisError(f"unsafe, duplicate, or nested archive member: {info.filename}")
        members[info.filename] = info
        roots.add(pure.parts[0])
    if roots != {expected_root}:
        archive.close()
        raise AnalysisError(f"single-root mismatch: {sorted(roots)}")
    return archive, members


def read(archive: zipfile.ZipFile, members: dict[str, zipfile.ZipInfo], root: str, relative: str) -> bytes:
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


def source_path() -> Path:
    candidates = [
        ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PACKAGE}.zip",
        ROOT
        / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane"
        / PACKAGE
        / f"{PACKAGE}.zip",
    ]
    present = [path for path in candidates if path.is_file()]
    if len(present) != 1:
        raise AnalysisError(f"exactly one p41 source ZIP is required, found: {present}")
    return present[0]


def marker_summary(text: str, marker: str) -> dict[str, Any]:
    lines = [line for line in text.splitlines() if marker in line]
    return {
        "count": len(lines),
        "first": lines[0] if lines else None,
        "last": lines[-1] if lines else None,
    }


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha_file(path),
    }


def main() -> int:
    source = source_path()
    for path in (RETURN, source, WAVE_INSPECTION, WAVE_EXTRACTION, WAVE_IDENTITY):
        if not path.is_file():
            raise AnalysisError(f"required evidence is absent: {path}")

    return_root = f"{PACKAGE}_return"
    return_zip, return_members = safe_zip(RETURN, return_root)
    source_zip, source_members = safe_zip(source, PACKAGE)
    try:
        core = load_json(return_zip, return_members, return_root, "RETURN_CORE_MANIFEST.json")
        core_status = load_json(
            return_zip, return_members, return_root, "return_core/RETURN_CORE_STATUS.json"
        )
        sim_exit = load_json(
            return_zip, return_members, return_root, "return_core/SIM_EXIT_RECEIPT.json"
        )
        plugins = load_json(
            return_zip, return_members, return_root, "return_core/RETURN_PLUGIN_STATUS.json"
        )
        waveform = load_json(
            return_zip,
            return_members,
            return_root,
            "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
        )
        gate = load_json(return_zip, return_members, return_root, "evidence/SERVER_RESULT_GATE.json")
        mse4 = load_json(return_zip, return_members, return_root, "evidence/mse4_join_decision.json")
        source_bound = load_json(
            return_zip, return_members, return_root, "evidence/source_bound_causal_decision.json"
        )
        trigger = load_json(
            return_zip, return_members, return_root, "evidence/triggered_causal_summary.json"
        )
        buffer5 = load_json(
            return_zip, return_members, return_root, "evidence/buffer5_public_summary.json"
        )
        production_identity = load_json(
            return_zip, return_members, return_root, "evidence/production_rtl_identity.json"
        )
        package_status = load_json(
            return_zip,
            return_members,
            return_root,
            "evidence/package_local_preflight_status.json",
        )
        observer_precompile = load_json(
            return_zip, return_members, return_root, "evidence/observer_precompile.json"
        )
        returned_manifest = read(
            return_zip, return_members, return_root, "source_package/package_manifest.json"
        )
        returned_generation = read(
            return_zip,
            return_members,
            return_root,
            "source_package/source_bound_generation_report.json",
        )
        returned_binding = read(
            return_zip,
            return_members,
            return_root,
            "source_package/source_bound_probe_binding.json",
        )
        source_manifest_bytes = read(source_zip, source_members, PACKAGE, "package_manifest.json")
        source_generation = read(
            source_zip,
            source_members,
            PACKAGE,
            "diagnostics/source_bound_generation_report.json",
        )
        source_binding = read(
            source_zip, source_members, PACKAGE, "diagnostics/source_bound_probe_binding.json"
        )
        source_plan = load_json(
            source_zip, source_members, PACKAGE, "diagnostics/source_bound_probe_plan.json"
        )
        source_catalog = load_json(
            source_zip, source_members, PACKAGE, "diagnostics/source_bound_probe_catalog.json"
        )
        generated_observer = read(
            source_zip, source_members, PACKAGE, "tb_probe/source_bound_causal_observer.svh"
        ).decode("utf-8")
        simulator_argv = read(
            return_zip, return_members, return_root, "runs/c0/simulator_argv.txt"
        ).decode("utf-8", errors="replace")
        observer_log = read(
            return_zip, return_members, return_root, "runs/c0/return_observer.log"
        ).decode("utf-8", errors="replace")

        core_receipts = {
            row["path"]: {"bytes": row["bytes"], "sha256": row["sha256"]}
            for row in core.get("core_entry_receipts", [])
        }
        receipt_mismatches: dict[str, Any] = {}
        for relative, expected in core_receipts.items():
            data = read(return_zip, return_members, return_root, relative)
            observed = {"bytes": len(data), "sha256": sha_bytes(data)}
            if observed != expected:
                receipt_mismatches[relative] = {"expected": expected, "observed": observed}

        expected_members = {
            f"{return_root}/RETURN_CORE_MANIFEST.json",
            f"{return_root}/return_core/RETURN_CORE_STATUS.json",
            f"{return_root}/return_core/RETURN_PLUGIN_STATUS.json",
            f"{return_root}/return_core/SIM_EXIT_RECEIPT.json",
            *(f"{return_root}/{path}" for path in core_receipts),
        }
        plugin_mismatches: dict[str, Any] = {}
        for row in plugins:
            plugin_id = row["plugin_id"]
            for suffix in ("status.json", "stdout.log", "stderr.log"):
                expected_members.add(f"{return_root}/return_core/plugins/{plugin_id}.{suffix}")
            member = load_json(
                return_zip,
                return_members,
                return_root,
                f"return_core/plugins/{plugin_id}.status.json",
            )
            if member != row:
                plugin_mismatches[plugin_id] = {"aggregate": row, "member": member}

        source_manifest = json.loads(source_manifest_bytes)
        source_actual = {
            name[len(PACKAGE) + 1 :]: {
                "sha256": sha_bytes(source_zip.read(name)),
                "size_bytes": source_members[name].file_size,
            }
            for name in source_members
            if name != f"{PACKAGE}/package_manifest.json"
        }

        wdata_boundary = next(
            row for row in source_plan["boundaries"] if row["boundary_id"] == "mse4_wdata_output_accept"
        )
        wdata_class = next(
            row for row in wdata_boundary["classes"] if row["class_id"] == "MSE4_WDATA_OUTPUT_ACCEPT"
        )
        symbols = {row["symbol_id"]: row for row in source_catalog["symbols"]}
        predicate_ids = [
            row["symbol_id"] for row in wdata_class["predicate"]["args"]
        ]
        vector_widths = [symbols[symbol_id]["width_bits"] for symbol_id in predicate_ids]
        generated_scalar_predicate = (
            "wire codex_progress_now = ((p_0 === 1'b1) && (p_2 === 1'b1));"
            in generated_observer
        )

        markers = {
            marker: marker_summary(observer_log, marker)
            for marker in (
                "N4D_PROGRESS_V1",
                "DWRITE_PATH_EDGE_V1",
                "MSE4_DESCRIPTOR_EDGE_V1",
                "DSKEW_EDGE_V1",
                "ROWLC4_BUFAG_EDGE_V1",
                "DATAHUB_DRAIN_EDGE_V1",
            )
        }
        last_progress = markers["N4D_PROGRESS_V1"]["last"] or ""
        native_mse4_wdata_18 = "wdata=0,0,0,0,18" in last_progress
        source_bound_missing = source_bound.get("missing_required_summaries", [])
        missing_wdata = any("mse4_wdata_output_accept@" in row for row in source_bound_missing)
        missing_finish = any("mse4_slice_finish@" in row for row in source_bound_missing)
        source_bound_plugin = next(
            row for row in plugins if row.get("plugin_id") == "source_bound_parser"
        )

        wave_inspection = json.loads(WAVE_INSPECTION.read_text(encoding="utf-8"))
        wave_extraction = json.loads(WAVE_EXTRACTION.read_text(encoding="utf-8"))
        wave_identity = json.loads(WAVE_IDENTITY.read_text(encoding="utf-8"))

        checks = {
            "formal_return_identity_exact": RETURN.stat().st_size == RETURN_BYTES
            and sha_file(RETURN) == RETURN_SHA256,
            "source_package_identity_exact": source.stat().st_size == SOURCE_BYTES
            and sha_file(source) == SOURCE_SHA256,
            "return_crc_single_root_path_safe_no_nested_archive": True,
            "source_crc_single_root_path_safe_no_nested_archive": True,
            "return_exact_set": set(return_members) == expected_members,
            "return_core_per_member_receipts": not receipt_mismatches,
            "plugin_status_receipts": not plugin_mismatches,
            "source_manifest_exact_set": source_manifest.get("files") == source_actual,
            "returned_source_identity_exact": returned_manifest == source_manifest_bytes
            and returned_generation == source_generation
            and returned_binding == source_binding,
            "execution_identity_exact": core.get("package_id") == PACKAGE
            and core.get("execution_id") == EXECUTION
            and core.get("return_basename") == RETURN.name,
            "production_compile_passed": read(
                return_zip, return_members, return_root, "evidence/compile_exit_status.txt"
            ).decode("ascii").strip()
            == "0"
            and gate.get("execution_gate", {}).get("compile_succeeded") is True,
            "public_surface_repair_crossed": package_status.get("dut_simulation_started") is True
            and observer_precompile.get("identity_match") is True
            and observer_precompile.get("valid") is True,
            "simulation_int_partial_exact": sim_exit.get("sim_started") is True
            and sim_exit.get("signal") == "INT"
            and sim_exit.get("sim_exit_code") == 255
            and core_status.get("disposition") == "PARTIAL_EXECUTION_RETURN",
            "mandatory_waveform_actual_argv": all(
                token in simulator_argv
                for token in ("DUMP_VCD=1", "DUMP_FSDB=0", "TB_DUMP_FSDB=0", "-ucli")
            ),
            "mandatory_waveform_return_exact": wave_inspection.get("pass") is True
            and wave_extraction.get("pass") is True
            and wave_identity.get("pass") is True
            and waveform.get("pass") is True
            and waveform.get("exit_kind") == "INT"
            and len(waveform.get("waveforms", [])) == 1,
            "mse4_descriptor_buffer_units_balanced": mse4.get("decision")
            == "MSE4_DESCRIPTOR_DATA_BALANCED_TERMINAL_ELSEWHERE"
            and mse4.get("counts", {}).get("descriptor") == 18
            and mse4.get("counts", {}).get("buffer_data") == 18,
            "native_mse4_wdata_progress_proved": native_mse4_wdata_18,
            "source_bound_wdata_false_negative": source_bound.get("decision") == "EVIDENCE_INCOMPLETE"
            and missing_wdata
            and missing_finish
            and source_bound_plugin.get("exit_code") == 1,
            "generated_vector_scalar_predicate_root_cause": vector_widths == [2, 2]
            and generated_scalar_predicate,
            "dynamic_stall_preserved": trigger.get("status") == "DYNAMIC_FLOW_CONTROL_STALL"
            and buffer5.get("last", {}).get("blocked_cycles") == "786432",
            "no_formal_result_overclaim": gate.get("execution_gate", {}).get("formal_D_claimed") is False
            and gate.get("execution_gate", {}).get("E4_claimed") is False
            and gate.get("execution_gate", {}).get("E5_claimed") is False,
        }
        valid = all(checks.values())
        report = {
            "schema": "conv-native-four-lane-0ccae916-p41-return-analysis-v1",
            "status": (
                "RETURN_ANALYSIS_COMPLETE_PACKAGE_LOCAL_VECTOR_HANDSHAKE_OBSERVER_SUCCESSOR_REQUIRED"
                if valid
                else "RETURN_ANALYSIS_INVALID"
            ),
            "valid": valid,
            "errors": [name for name, passed in checks.items() if not passed],
            "package_id": PACKAGE,
            "execution_id": EXECUTION,
            "previous_version_progress": (
                "p39 localized production compile exit=2 to two package-local observer XMR sites; "
                "p40 repaired the Datahub public surface and structured first-error path but was withdrawn "
                "for old dump=0 semantics; p41 preserved that repair and added mandatory full-hierarchy VPD."
            ),
            "current_version_purpose": (
                "Prove production compile beyond the public-surface repair and use the mandatory VPD-bound "
                "dynamic return to localize the retained MSE4 causal blocker."
            ),
            "formal_return": receipt(RETURN),
            "source_package": receipt(source),
            "integrity": {
                "checks": checks,
                "return_member_count": len(return_members),
                "source_member_count": len(source_members),
                "return_missing": sorted(expected_members - set(return_members)),
                "return_extra": sorted(set(return_members) - expected_members),
                "core_receipt_mismatches": receipt_mismatches,
                "plugin_status_mismatches": plugin_mismatches,
            },
            "execution": {
                "compile_exit_status": 0,
                "run_exit_status": 255,
                "signal_status": "INT",
                "sim_started": True,
                "natural_terminal": False,
                "actual_compile_identity_collected": gate.get("execution_gate", {}).get(
                    "actual_compile_identity_collected"
                ),
                "actual_rtl_identity": {
                    "collection_valid": production_identity.get("collection_valid"),
                    "authority_classification": production_identity.get("authority_classification"),
                    "identity_difference_blocks_simulator": production_identity.get(
                        "identity_difference_blocks_simulator"
                    ),
                },
            },
            "waveform": {
                "runtime_receipt": waveform,
                "inspection": wave_inspection,
                "extraction": wave_extraction,
                "identity": wave_identity,
                "semantic_decode_available": any(
                    wave_identity.get("discovered_tools", {}).values()
                ),
                "viewer_absence_is_not_acceptance_failure": True,
            },
            "dynamic_localization": {
                "mse4_join": mse4,
                "native_marker_summary": markers,
                "triggered_status": trigger.get("status"),
                "buffer5_last": buffer5.get("last"),
                "source_bound_decision": {
                    "decision": source_bound.get("decision"),
                    "reason": source_bound.get("reason"),
                    "missing_required_summaries": source_bound_missing,
                    "plugin_exit_code": source_bound_plugin.get("exit_code"),
                },
            },
            "failure_localization": {
                "LAST_PROVEN_GOOD": (
                    "Exact p41 production compile passed the p40 Datahub public-surface repair, simulation "
                    "started with full-hierarchy VPD, and the native ledger recorded 18 MSE4 descriptors, "
                    "18 Buffer-data accepts and 18 MSE4 wdata handshakes."
                ),
                "FIRST_DIVERGENCE": (
                    "The generated source-bound MSE4 wdata probe observes zero events and omits its required "
                    "summary even though the independent native ledger records 18 MSE4 wdata handshakes."
                ),
                "HANG_ROOT_CAUSE": {
                    "status": "PACKAGE_LOCAL_SOURCE_BOUND_VECTOR_HANDSHAKE_SCALAR_CASE_EQUALITY",
                    "source_member": "tb_probe/source_bound_causal_observer.svh",
                    "boundary": "mse4_wdata_output_accept",
                    "operand_widths": vector_widths,
                    "faulty_expression": "(p_0 === 1'b1) && (p_2 === 1'b1)",
                    "required_expression_semantics": "any same-channel bit in (valid & ready) is known one",
                    "functional_rtl_fix_required": False,
                },
            },
            "result_conjunction": {
                "compile": True,
                "simulator_started": True,
                "natural_terminal_27_of_27": False,
                "formal_D_320_of_320": False,
                "mismatch_zero_claim": False,
                "E3": False,
                "E4": False,
                "E5": False,
                "passed": False,
            },
            "successor_adjudication": {
                "decision": "BUILD_FRESH_PACKAGE_LOCAL_OBSERVER_SUCCESSOR",
                "tentative_package_id": "r5_n4_0cc_p42_vecjoinfix",
                "changed_surfaces": [
                    "fresh package identity",
                    "source-bound predicate operator/tool",
                    "generated source-bound observer/binding/parser receipts",
                ],
                "frozen": [
                    "config",
                    "numeric",
                    "workload",
                    "golden",
                    "functional RTL",
                    "MSE4 target diagnostic",
                    "mandatory VPD/runtime-return semantics",
                ],
                "server_action": False,
            },
            "rule_feedback": {
                "type": "RULE_CONFIRMATION",
                "confirmed_rule_ids": [
                    "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                    "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001",
                    "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
                ],
                "proposal": None,
            },
            "claim_boundary": (
                "p41 closes production compile and waveform-return plumbing, and proves a package-local "
                "source-bound vector-handshake observation defect. It does not establish natural terminal, "
                "formal D, numeric correctness, E3/E4/E5, performance, or a functional RTL root cause."
            ),
            "server_action": False,
        }
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
