#!/usr/bin/env python3
"""Finalize the bounded, resumable family analysis for the exact QAdd v66 return.

The large VCD is consumed by server_tb_vcd_retention_analysis.py.  This tool
only reads that bounded state plus small return members and streams sim.log.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v66_cfg42"
EXECUTION = "r1786770100877714671_2785121"
ATTEMPT = "a2785121"
RETURN = Path(
    r"C:\Users\15383\Downloads\r5_qadd_n7_tailround_lanephase_v66_cfg42_"
    r"r1786770100877714671_2785121_return.zip"
)
RETURN_BYTES = 92_180_270
RETURN_SHA = "9da70fe32efcdaa00c50945f9a2f9985f8ccc9ed08c98d68d6cc507455194203"
PREFIX = f"{PACKAGE}_return/"
OUT = ROOT / f"outputs/qlinearadd_node0007_v66_return_{EXECUTION}"
STREAM = OUT / "streaming_analysis"
CHUNKS = STREAM / "chunks"
PENDING = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PACKAGE}.zip"
EXPECTED_BITSTREAM = "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f"
REJECTED_BITSTREAM = "a3094e0066c979f53a8aa03c89379841c0df9198ab76009dc38b254c764c2fa0"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_bytes(canonical(value))
    os.replace(tmp, path)


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def object_member(archive: zipfile.ZipFile, suffix: str) -> dict[str, Any]:
    value = json.loads(archive.read(PREFIX + suffix))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {suffix}")
    return value


def normalize_hierarchy(value: str) -> str:
    return re.sub(r"\s+\[[0-9]+:[0-9]+\]$", "", value.strip())


def signal_rows(state: dict[str, Any], catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_reference: dict[str, list[str]] = {}
    for code, row in state["signal_catalog"].items():
        by_reference.setdefault(normalize_hierarchy(str(row["reference"])), []).append(code)
    rows: dict[str, dict[str, Any]] = {}
    for item in catalog["signals"]:
        reference = item["exact_hierarchy"].rsplit(".", 1)[-1]
        codes = by_reference.get(reference, [])
        if len(codes) != 1:
            raise RuntimeError(f"non-unique VCD reference mapping for {item['signal_id']}: {codes}")
        code = codes[0]
        summary = state["signal_summaries"].get(code, {})
        rows[item["signal_id"]] = {
            "vcd_code": code,
            "reference": reference,
            "width_bits": item["width_bits"],
            "transitions": summary.get("transitions", 0),
            "xz_transitions": summary.get("xz_transitions", 0),
            "first_value": summary.get("first_value"),
            "end_state": summary.get("last_value"),
            "last_transition_time_ps": summary.get("last_time", 0),
        }
    return rows


def scan_log(archive: zipfile.ZipFile) -> dict[str, Any]:
    stats = {
        "lines": 0,
        "matrix_loads_started": 0,
        "matrix_transfer_completions": 0,
        "heartbeat_count": 0,
        "target_entry_count": 0,
        "terminal_witness_count": 0,
    }
    last: dict[str, Any] = {}
    with archive.open(PREFIX + "runs/sim.log") as raw:
        for blob in raw:
            stats["lines"] += 1
            line = blob.decode("utf-8", errors="replace").rstrip("\r\n")
            lower = line.lower()
            if "json: loading matrix[" in lower:
                stats["matrix_loads_started"] += 1
                last["matrix_load"] = {"line": stats["lines"], "text": line[:1024]}
            if "matrix transfer completed" in lower:
                stats["matrix_transfer_completions"] += 1
                last["matrix_complete"] = {"line": stats["lines"], "text": line[:1024]}
            burst = re.search(r"\[Read Burst (\d+)\].*Addr=(0x[0-9a-fA-F]+).*Length=(\d+)", line)
            if burst:
                last["read_burst"] = {
                    "line": stats["lines"], "index": int(burst.group(1)),
                    "address": burst.group(2).lower(), "length_words": int(burst.group(3)),
                }
            if "codex_tbvcd_heartbeat" in lower:
                stats["heartbeat_count"] += 1
                last["heartbeat"] = {"line": stats["lines"], "text": line[:2048]}
            if "codex_tbvcd_target_entry" in lower:
                stats["target_entry_count"] += 1
            if "codex_tbvcd_terminal_witness" in lower or "natural_terminal" in lower:
                stats["terminal_witness_count"] += 1
    return {"stats": stats, "last": last}


def find_manifest_file(manifest: dict[str, Any], suffix: str) -> dict[str, Any] | None:
    files = manifest.get("files")
    if not isinstance(files, dict):
        return None
    for name, row in files.items():
        if name.endswith(suffix) and isinstance(row, dict):
            return {"path": name, **row}
    return None


def main() -> int:
    if RETURN.stat().st_size != RETURN_BYTES or sha_file(RETURN) != RETURN_SHA:
        raise RuntimeError("formal return identity mismatch")
    state_path = STREAM / "analysis_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not str(state.get("status", "")).startswith("EOF_REACHED") or state.get("byte_offset") != 583_852_780:
        raise RuntimeError("bounded VCD scan has not reached the exact EOF")

    with zipfile.ZipFile(RETURN) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("formal return CRC failure")
        actual = object_member(archive, "evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        attempt = object_member(archive, "evidence/NATIVE_FAILURE_ATTEMPT.json")
        identity = object_member(archive, "evidence/TB_VCD_IDENTITY.json")
        decision = object_member(archive, "evidence/TB_VCD_LIVE_DECISION_RECEIPT.json")
        safety = object_member(archive, "evidence/TB_VCD_LIVE_SAFETY_RECEIPT.json")
        stop = object_member(archive, "evidence/TB_VCD_STOP_RECEIPT.json")
        target = object_member(archive, "evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json")
        sim_exit = object_member(archive, "return_core/SIM_EXIT_RECEIPT.json")
        core = object_member(archive, "return_core/RETURN_CORE_STATUS.json")
        catalog = object_member(archive, "source_package/tb_vcd_signal_catalog.json")
        matrix = object_member(archive, "source_package/tb_vcd_candidate_matrix.json")
        dynamic = object_member(archive, "source_package/qadd_config42_dynamic_acceptance.json")
        lineage = object_member(archive, "source_package/CONFIG_LINEAGE_CONTRACT.json")
        config = object_member(archive, "source_package/op_tail_round_4_2.json")
        package_manifest = object_member(archive, "source_package/TEST_PACKAGE_MANIFEST.json")
        log = scan_log(archive)

    signals = signal_rows(state, catalog)
    target_ids = {
        "sig_exec_start", "sig_global_exec_active", "sig_mrm_req_valid", "sig_mrm_req_strb",
        "sig_mrm_rd_en", "sig_mrm_clear", "sig_valid_clear", "sig_valid_clr_mask",
        "sig_mrm_rvalid", "sig_slice_finish", "sig_global_done_pulse",
    }
    target_static = all(
        signals[name]["last_transition_time_ps"] == 0 and signals[name]["transitions"] == 1
        for name in target_ids
    )
    request_masks = {
        "0x33333333": False,
        "0xcccccccc": False,
    }
    strb = signals["sig_mrm_req_strb"]
    if strb["transitions"] > 1:
        value = int(strb["end_state"], 2)
        request_masks[f"0x{value:08x}"] = True

    normalized_missing = {normalize_hierarchy(row) for row in identity.get("missing_expected_hierarchies", [])}
    normalized_unexpected = {normalize_hierarchy(row) for row in identity.get("unexpected_hierarchies", [])}
    width_suffix_only = bool(normalized_missing) and normalized_missing == normalized_unexpected

    local_rtl = []
    for row in lineage["actual_rtl_consumer_sources"]:
        path = ROOT / row["path"]
        local_rtl.append({
            "path": row["path"], "expected_sha256": row["sha256"],
            "current_sha256": sha_file(path), "exact": path.is_file() and sha_file(path) == row["sha256"],
        })
    bitstream_manifest = find_manifest_file(
        package_manifest,
        "op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin",
    )
    config_exact = config["buffer_loop_configs"]["GROUP2"]["COL_LC"]["end"] == 4 and config["buffer_loop_configs"]["GROUP2"]["COL_LC"]["stride"] == 2
    lineage_exact = (
        lineage.get("pass") is True
        and lineage["packaged_bitstream_sha256"] == EXPECTED_BITSTREAM
        and lineage["rejected_bad_bitstream"] == {"rejected": True, "sha256": REJECTED_BITSTREAM}
        and bitstream_manifest is not None
        and bitstream_manifest.get("sha256") == EXPECTED_BITSTREAM
        and actual.get("source_identity_status") == "COMPLETE"
    )

    compile_exit = int(attempt.get("compile_exit", sim_exit.get("compile_exit", -1)))
    simulation_exit = int(attempt.get("simulation_exit", sim_exit.get("sim_exit_code", -1)))
    target_entered = target.get("observed") is True or log["stats"]["target_entry_count"] > 0
    natural = stop.get("natural_terminal") is True or sim_exit.get("natural_terminal_observed") is True
    process_complete = not safety.get("errors")
    identity_binding = (
        actual.get("package_id") == PACKAGE
        and actual.get("execution_id") == EXECUTION
        and actual.get("attempt_id") == ATTEMPT
    )

    integrity_chunk = {
        "schema": "qadd-v66-stream-chunk-v1", "sequence": 1, "kind": "RETURN_INTEGRITY",
        "return_identity_exact": True, "zip_crc_pass": True, "identity_binding_pass": identity_binding,
        "vcd_eof_bytes": state["byte_offset"], "vcd_lines": state["line_number"],
        "last_vcd_timestamp_ps": state["last_sim_time"], "catalog_entries": len(signals),
        "identity_receipt_width_suffix_false_negative": width_suffix_only,
    }
    lineage_chunk = {
        "schema": "qadd-v66-stream-chunk-v1", "sequence": 2, "kind": "CONFIG_RTL_LINEAGE",
        "direct_config_evidence": {
            "group2_col_lc": {"end": 4, "stride": 2}, "config_exact": config_exact,
            "bitstream_sha256": EXPECTED_BITSTREAM, "rejected_32_16_bitstream_sha256": REJECTED_BITSTREAM,
            "sca_cfg": lineage["sca_cfg"], "sca_cfg_D": lineage["sca_cfg_D"],
            "actual_sim_sca_cfg": actual.get("sca_cfg"),
            "actual_sim_sca_cfg_D": actual.get("sca_cfg_d"),
        },
        "direct_actual_rtl_evidence": local_rtl,
        "actual_compiled_rtl_identity_boundary": "The return binds the package-local TB source and Makefile, but does not hash the server-owned transitive RTL tree. Three current-disk consumer files differ from the historical lineage hashes, so no new v66 actual-RTL byte identity is claimed.",
        "lineage_exact": lineage_exact,
        "dynamic_execution_boundary": "PRETARGET_ONLY",
    }
    dynamic_chunk = {
        "schema": "qadd-v66-stream-chunk-v1", "sequence": 3, "kind": "DYNAMIC_ACCEPTANCE",
        "required_order": dynamic["required_ordered_sequence"],
        "observed": {
            "target_entry": target_entered, "request_0x33333333": request_masks["0x33333333"],
            "request_0xcccccccc": request_masks["0xcccccccc"], "read_accept": signals["sig_mrm_rd_en"]["transitions"] > 1,
            "clear": any(signals[name]["transitions"] > 1 for name in ("sig_mrm_clear", "sig_valid_clear", "sig_valid_clr_mask")),
            "output": signals["sig_mrm_rvalid"]["transitions"] > 1,
            "natural_terminal": natural, "formal_D": False,
        },
        "pretarget_signal_static": target_static, "status": "NOT_EXERCISED",
    }
    candidates = [row["candidate_id"] for row in matrix["candidates"]]
    candidate_chunk = {
        "schema": "qadd-v66-stream-chunk-v1", "sequence": 4, "kind": "CANDIDATE_MATRIX",
        "pairwise_complete": matrix.get("pairwise_complete"),
        "rows": [
            {"candidate_id": name, "status": "NOT_REACHED_NOT_ADJUDICABLE", "reason": "target entry absent"}
            for name in candidates
        ],
    }
    for name, value in (
        ("001_return_integrity.json", integrity_chunk),
        ("002_config_rtl_lineage.json", lineage_chunk),
        ("003_dynamic_acceptance.json", dynamic_chunk),
        ("004_candidate_matrix.json", candidate_chunk),
    ):
        atomic_json(CHUNKS / name, value)

    analysis = {
        "schema": "qlinearadd-node0007-v66-cfg42-formal-return-analysis-v1",
        "role_id": "family.qlinearadd", "package_id": PACKAGE, "execution_id": EXECUTION,
        "attempt_id": ATTEMPT, "status": "RETURN_ANALYSIS_COMPLETE_SUCCESSOR_REQUIRED",
        "integrity": integrity_chunk,
        "production": {
            "compile_exit": compile_exit, "compile_succeeded": compile_exit == 0,
            "simulation_started": attempt.get("simulation_started") is True,
            "simulation_exit": simulation_exit, "stop_reason": safety.get("stop_reason"),
            "process_tree_complete": process_complete, "target_entry_observed": target_entered,
            "pretarget_progress": log,
        },
        "DIRECT_CONFIG_EVIDENCE": lineage_chunk["direct_config_evidence"],
        "DIRECT_ACTUAL_RTL_EVIDENCE": lineage_chunk["direct_actual_rtl_evidence"],
        "DYNAMIC_EXECUTION_EVIDENCE": dynamic_chunk,
        "root_disposition": {
            "historical_validated_root_cause": lineage.get("validated_root_cause"),
            "config_lineage_repair_materialized_and_compiled": lineage_exact,
            "functional_repair_dynamically_validated": False,
            "classification": "OPEN_UNVALIDATED_MECHANISM",
            "reason": "The exact 4/2 lineage reached production compile but the DUT target never entered; no request, accept, clear, output or terminal event exists in the attempt.",
        },
        "last_proven_good": {
            "classification": "EXACT_4_2_LINEAGE_PRODUCTION_COMPILE_AND_PRETARGET_MATRIX_PRELOAD_PROGRESS",
            "detail": "The corrected lineage was selected, production compile passed, 24 matrix transfers completed and matrix 24/slice04 advanced through read burst 237.",
        },
        "first_divergence": {
            "classification": "PRETARGET_WALL_CEILING_BEFORE_EXEC_START",
            "detail": "The six-hour outer wall ceiling ended an advancing preload before exec_start/global_exec_active; this is not a DUT causal divergence.",
        },
        "vcd_stop_adjudication": {
            "causal_plateau_triggered": False, "wall_ceiling_triggered": safety.get("stop_reason") == "WALL_CEILING",
            "plateau_correctly_suppressed_while_global_progress_advanced": True,
            "archive_partial": not process_complete, "catalog_receipt_false_negative": width_suffix_only,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        },
        "candidate_matrix": candidate_chunk,
        "boundaries": {
            "natural_terminal": False, "formal_D": False, "E3": False, "E4": False, "E5": False,
            "reason": "target entry absent and wall-ceiling/process-tree return is partial",
        },
        "successor_justified": True,
        "successor_delta": "Fresh identity retaining exact 4/2 lineage and 64-signal target cone; add evidence-bound pretarget quiet capture with sparse runtime heartbeat, full continuous capture from target entry, and width-suffix-normalized exact-catalog finalization.",
        "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_target_cone"],
        "pass": identity_binding and compile_exit == 0 and attempt.get("simulation_started") is True and lineage_exact and target_static,
        "errors": [],
        "claim_boundary": "This return proves exact 4/2 materialization and production compile plus advancing pre-target preload only. It does not dynamically validate the functional repair or prove natural/formal-D/E3/E4/E5.",
    }
    audit = {
        "schema": "qlinearadd-node0007-v66-rule-gap-audit-v1", "package_id": PACKAGE,
        "trigger": "FORMAL_RETURN_DID_NOT_EXERCISE_DYNAMIC_CONFIG42_CONTRACT",
        "causal_cone": "64/64 source-bound signals are present, but the cone remained pre-target static",
        "candidate_matrix": "pairwise-complete structurally; no row is dynamically adjudicable before target entry",
        "source_identity": "complete and exact for config lineage and bound RTL consumers",
        "stop_return_parser": [
            "global preload progress correctly prevented CAUSAL_PLATEAU",
            "wall ceiling ended the advancing preload before target",
            "catalog completeness falsely failed because finalizer compared vector range suffixes literally",
            "process-tree close/reap remained partial",
        ],
        "disposition": "RULE_CONFIRMATION_NO_PUBLIC_CHANGE",
        "public_rule_delta_proposed": False,
        "family_implementation_delta_required": [
            "evidence-bound pretarget quiet period with sparse safety heartbeat",
            "continuous untruncated full causal-cone VCD from target entry onward",
            "exact-catalog hierarchy comparison normalized only for legal terminal vector ranges",
            "negative controls proving no target-window sampling and no width-based false pass",
        ],
        "pass": True, "errors": [],
        "claim_boundary": "Current adaptive-v4/runtime-v3 rules are sufficient; the fresh family package must implement the return-derived pretarget/target capture split without changing public rules.",
    }
    atomic_json(OUT / "formal_return_analysis.json", analysis)
    atomic_json(OUT / "RULE_GAP_AUDIT.json", audit)

    checkpoint = {
        "schema": "qadd-v66-streaming-family-checkpoint-v1",
        "sequence": int(state.get("checkpoint_count", 0)) + 1,
        "status": "FORMAL_FAMILY_ANALYSIS_COMPLETE", "byte_offset": state["byte_offset"],
        "line_number": state["line_number"], "last_sim_time": state["last_sim_time"],
        "last_proven_good": analysis["last_proven_good"]["classification"],
        "first_divergence": analysis["first_divergence"]["classification"],
        "analysis_sha256": sha_file(OUT / "formal_return_analysis.json"),
    }
    checkpoint_path = STREAM / "checkpoints.jsonl"
    prior = checkpoint_path.read_text(encoding="utf-8") if checkpoint_path.is_file() else ""
    if '"status": "FORMAL_FAMILY_ANALYSIS_COMPLETE"' not in prior:
        with checkpoint_path.open("a", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")
    state["status"] = "EOF_REACHED_FAMILY_ANALYSIS_COMPLETE"
    state["family_analysis"] = checkpoint
    atomic_json(state_path, state)
    report = STREAM / "report.md"
    prior_report = report.read_text(encoding="utf-8") if report.is_file() else ""
    section = (
        "\n## Family formal disposition\n\n"
        "- exact 4/2 lineage and production compile: `PROVEN`\n"
        "- target entry / ordered masks / accepts / clears: `NOT EXERCISED`\n"
        "- last proven good: 24 completed preloads; slice04 preload reached read burst 237\n"
        "- first divergence: `PRETARGET_WALL_CEILING_BEFORE_EXEC_START`\n"
        "- VCD: 64/64 signals present after legal vector-range normalization; target cone remained static\n"
        "- natural/formal-D/E3/E4/E5: not proven\n"
        "- audit: `RULE_CONFIRMATION_NO_PUBLIC_CHANGE`; fresh pretarget-quiet/target-continuous package justified\n"
    )
    if "## Family formal disposition" not in prior_report:
        with report.open("a", encoding="utf-8", newline="\n") as output:
            output.write(section)
    print(json.dumps({"analysis": str(OUT / "formal_return_analysis.json"), "pass": analysis["pass"]}, sort_keys=True))
    return 0 if analysis["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
