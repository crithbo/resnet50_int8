#!/usr/bin/env python3
"""Stream and summarize the exact serialized Conv v97b formal return."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

import analyze_node0004_v95b_tbvcd_return as core


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v97b_tbvcd_memtuple_xmrefix"
RETURN_ROOT = f"{PACKAGE}_return/"
ANALYSIS = ROOT / "outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_return_r1786793347853153460_2912853"
STREAM = ANALYSIS / "streaming"
PENDING = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PACKAGE}.zip"


def configure_core() -> None:
    core.PACKAGE = PACKAGE
    core.RETURN_ROOT = RETURN_ROOT
    core.ANALYSIS = ANALYSIS
    core.STREAM = STREAM
    core.PENDING = PENDING


def load_json(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    with archive.open(RETURN_ROOT + relative) as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {relative}")
    return value


def waveform_manifest_check(manifest: dict[str, Any], vcd: dict[str, Any]) -> dict[str, Any]:
    # TB-VCD returns bind the causal VCD as a required core member.  Older
    # waveform-specific transports used waveform_entry_receipts, so accept
    # either exact receipt location while still requiring one unique identity.
    rows = list(manifest.get("waveform_entry_receipts", []))
    rows.extend(manifest.get("core_entry_receipts", []))
    exact = [row for row in rows if row.get("path") == "waveforms/causal_cone.vcd"]
    errors: list[str] = []
    if len(exact) != 1:
        errors.append(f"waveform manifest multiplicity:{len(exact)}")
    elif exact[0].get("bytes") != vcd["bytes"] or exact[0].get("sha256") != vcd["sha256"]:
        errors.append("waveform manifest identity mismatch")
    return {"pass": not errors, "checked": len(exact), "errors": errors}


def append_checkpoint(state: dict[str, Any], vcd: dict[str, Any], source_sha: str) -> None:
    checkpoint_path = STREAM / "checkpoints.jsonl"
    prior = checkpoint_path.read_text(encoding="utf-8") if checkpoint_path.is_file() else ""
    kind = "family_v97b_exact_hierarchy_causal_stream"
    if f'"kind": "{kind}"' in prior:
        return
    sequence = int(state.get("checkpoint_count", 0)) + 1
    checkpoint = {
        "catalog_count": vcd["catalog_count"],
        "kind": kind,
        "last_nonclock_time": vcd["last_nonclock_time"],
        "last_sim_time": vcd["last_timestamp"],
        "mapped_catalog_count": vcd["mapped_catalog_count"],
        "member_sha256": vcd["sha256"],
        "missing_catalog_count": len(vcd["missing_catalog_hierarchies"]),
        "non_clock_events": vcd["non_clock_event_count"],
        "schema": "server-tb-vcd-retention-analysis-v1",
        "sequence": sequence,
        "source_sha256": source_sha,
        "status": "EOF_REACHED",
    }
    with checkpoint_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")
    state["checkpoint_count"] = sequence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    args = parser.parse_args()
    source = args.return_zip.resolve(strict=True)
    configure_core()

    state_path = STREAM / "analysis_state.json"
    if not state_path.is_file():
        raise RuntimeError("shared bounded streaming state is absent")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") != "EOF_REACHED":
        raise RuntimeError("shared bounded streaming state has not reached EOF")
    source_bytes, source_sha = core.sha_path(source)

    with zipfile.ZipFile(source) as archive:
        manifest = load_json(archive, "RETURN_CORE_MANIFEST.json")
        returned_manifest = archive.read(RETURN_ROOT + "evidence/returned_package_manifest.json")
        catalog = load_json(archive, "evidence/vcd/VCD_SIGNAL_CATALOG.json")
        manifest_check = core.verify_return_manifest(archive, manifest)
        source_package = core.verify_source_package(returned_manifest)
        sim_log = core.scan_log(archive, "runs/c0/sim.log")
        sim_log["counts"] = core.count_log_patterns(archive, "runs/c0/sim.log")
        compile_log = core.scan_log(archive, "evidence/compile_rootcause/compile_driver.full.log")
        compile_log["counts"] = core.count_log_patterns(archive, "evidence/compile_rootcause/compile_driver.full.log")
        vcd = core.stream_vcd(archive, catalog)
        waveform_check = waveform_manifest_check(manifest, vcd)
        sources = core.extract_sources(archive)
        receipts = {
            "argv": load_json(archive, "evidence/ACTUAL_COMPILE_SIM_ARGV.json"),
            "archive_timestamp": load_json(archive, "evidence/vcd/TB_VCD_ARCHIVE_TIMESTAMP_RECEIPT.json"),
            "candidate_matrix": load_json(archive, "evidence/vcd/VCD_CANDIDATE_MATRIX.json"),
            "compile_core": load_json(archive, "evidence/compile_rootcause/COMPILE_CORE.json"),
            "compile_source_identity": load_json(archive, "evidence/compile_rootcause/compile_source_identity.json"),
            "dump_control": load_json(archive, "evidence/vcd/TB_VCD_DUMP_CONTROL_RECEIPT.json"),
            "native_attempt": load_json(archive, "evidence/NATIVE_FLOW_ATTEMPT.json"),
            "process_tree": load_json(archive, "evidence/PROCESS_TREE_RECEIPT.json"),
            "return_core_status": load_json(archive, "return_core/RETURN_CORE_STATUS.json"),
            "return_exact_set": load_json(archive, "evidence/vcd/TB_VCD_RETURN_EXACT_SET.json"),
            "runtime": load_json(archive, "evidence/vcd/VCD_RUNTIME_RECEIPT.json"),
            "sim_exit_core": load_json(archive, "return_core/SIM_EXIT_RECEIPT.json"),
            "sim_exit_evidence": load_json(archive, "evidence/SIM_EXIT_RECEIPT.json"),
            "source_identity": load_json(archive, "evidence/compiled_source/source_identity.json"),
            "stop": load_json(archive, "evidence/vcd/VCD_STOP_RECEIPT.json"),
            "vcd_identity": load_json(archive, "evidence/vcd/VCD_IDENTITY.json"),
        }

    report = {
        "actual_sources": sources,
        "claim_boundary": "Exact-return identity, bounded logs, and complete local stream of every present VCD variable. Missing catalog leaves remain unobserved and cannot support a tuple-leaf root claim.",
        "compile_log": compile_log,
        "integrity": {
            "return_manifest": manifest_check,
            "source_package": source_package,
            "waveform_manifest": waveform_check,
        },
        "package_id": PACKAGE,
        "pass": manifest_check["pass"] and source_package["pass"] and waveform_check["pass"],
        "receipts": receipts,
        "schema": "node0004-v97b-tbvcd-return-streaming-analysis-v1",
        "shared_streaming_state": state,
        "sim_log": sim_log,
        "source": {"bytes": source_bytes, "path": str(source), "sha256": source_sha},
        "vcd": vcd,
    }
    core.atomic_json(ANALYSIS / "streaming_summary.json", report)

    append_checkpoint(state, vcd, source_sha)
    state["family_causal_pass"] = {
        "catalog_count": vcd["catalog_count"],
        "mapped_catalog_count": vcd["mapped_catalog_count"],
        "member_sha256": vcd["sha256"],
        "missing_catalog_count": len(vcd["missing_catalog_hierarchies"]),
        "non_clock_events": vcd["non_clock_event_count"],
        "status": "EOF_REACHED_WITH_CATALOG_GAP" if vcd["missing_catalog_hierarchies"] else "EOF_REACHED",
        "summary": "../streaming_summary.json",
        "transitions": "causal_transitions.jsonl",
    }
    core.atomic_json(state_path, state)
    report_path = STREAM / "report.md"
    text = report_path.read_text(encoding="utf-8")
    text += (
        "\n## Family exact-hierarchy causal stream\n\n"
        f"- catalog mapped: `{vcd['mapped_catalog_count']}/{vcd['catalog_count']}`\n"
        f"- missing exact leaves: `{len(vcd['missing_catalog_hierarchies'])}`\n"
        f"- VCD last timestamp: `{vcd['last_timestamp']}`\n"
        f"- last non-clock transition: `{vcd['last_nonclock_time']}`\n"
        f"- retained non-clock transitions: `{vcd['non_clock_event_count']}`\n"
        f"- runtime stop: `{receipts['runtime'].get('stop_reason')}`\n"
        f"- natural terminal: `{receipts['runtime'].get('natural_terminal')}`\n"
    )
    report_path.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({
        "catalog": [vcd["mapped_catalog_count"], vcd["catalog_count"]],
        "last_nonclock": vcd["last_nonclock_time"],
        "last_timestamp": vcd["last_timestamp"],
        "missing": len(vcd["missing_catalog_hierarchies"]),
        "nonclock_events": vcd["non_clock_event_count"],
        "pass": report["pass"],
        "summary": str(ANALYSIS / "streaming_summary.json"),
    }, sort_keys=True))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
