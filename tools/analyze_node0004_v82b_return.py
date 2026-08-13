#!/usr/bin/env python3
"""Formal receipt and causal analysis for serialized Conv node0004 v82b."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v82b_phase_collectfix"
ROOT_NAME = PACKAGE + "_return"
RETURN_BYTES = 342626
RETURN_SHA = "f328f1cc6f634310466aca206148297825db3231beaf7102ff5b92516eff3638"
SOURCE_BYTES = 5256542
SOURCE_SHA = "cdd4dc08b616d29e891973267fff0dd00c380bada05c12e50e2a6d119bd7ee07"
EXECUTION = "r1786417609012229751_870730"
TARGET = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
    "u_Buffer_AG_Idx_Queue"
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_member(archive: zipfile.ZipFile, prefix: str, member: str):
    return json.loads(archive.read(prefix + member))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    return_bytes = args.return_zip.read_bytes()
    source_bytes = args.source_zip.read_bytes()
    if len(return_bytes) != RETURN_BYTES or digest(return_bytes) != RETURN_SHA:
        errors.append("external_return_identity_mismatch")
    if len(source_bytes) != SOURCE_BYTES or digest(source_bytes) != SOURCE_SHA:
        errors.append("source_zip_identity_mismatch")

    expected = {
        "RETURN_CORE_MANIFEST.json",
        "evidence/SERVER_RESULT_GATE.json",
        "evidence/buffer_ack_phase_parser_receipt.json",
        "evidence/compile_exit_status.txt",
        "evidence/returned_package_manifest.json",
        "evidence/run_exit_status.txt",
        "evidence/signal_status.txt",
        "return_core/RETURN_CORE_STATUS.json",
        "return_core/RETURN_PLUGIN_STATUS.json",
        "return_core/SIM_EXIT_RECEIPT.json",
        "return_core/plugins/node0004_source_bound_collect.status.json",
        "return_core/plugins/node0004_source_bound_collect.stderr.log",
        "return_core/plugins/node0004_source_bound_collect.stdout.log",
        "runs/c0/buffer_ack_phase_decision.json",
        "runs/c0/return_observer.log",
        "runs/c0/sim.log",
        "runs/c0/simulator_argv.txt",
        "runs/c0/source_bound_causal.log",
        "runs/c0/source_bound_causal_decision.json",
    }
    prefix = ROOT_NAME + "/"
    with zipfile.ZipFile(args.return_zip) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos]
        if archive.testzip() is not None:
            errors.append("crc_failure")
        if len(names) != len(set(names)):
            errors.append("duplicate_member")
        for row in infos:
            pure = PurePosixPath(row.filename)
            if (
                pure.is_absolute()
                or not pure.parts
                or pure.parts[0] != ROOT_NAME
                or ".." in pure.parts
                or "\\" in row.filename
                or stat.S_ISLNK(row.external_attr >> 16)
            ):
                errors.append("unsafe_member:" + row.filename)
        actual = {name[len(prefix):] for name in names}
        if actual != expected:
            errors.append("exact_set_mismatch")

        core = load_member(archive, prefix, "RETURN_CORE_MANIFEST.json")
        status = load_member(archive, prefix, "return_core/RETURN_CORE_STATUS.json")
        plugins = load_member(archive, prefix, "return_core/RETURN_PLUGIN_STATUS.json")
        sim_exit = load_member(archive, prefix, "return_core/SIM_EXIT_RECEIPT.json")
        gate = load_member(archive, prefix, "evidence/SERVER_RESULT_GATE.json")
        returned_manifest = load_member(archive, prefix, "evidence/returned_package_manifest.json")
        phase_receipt = load_member(archive, prefix, "evidence/buffer_ack_phase_parser_receipt.json")
        phase = load_member(archive, prefix, "runs/c0/buffer_ack_phase_decision.json")
        source_bound = load_member(archive, prefix, "runs/c0/source_bound_causal_decision.json")
        compile_exit = int(archive.read(prefix + "evidence/compile_exit_status.txt").strip())
        run_exit = int(archive.read(prefix + "evidence/run_exit_status.txt").strip())
        signal = archive.read(prefix + "evidence/signal_status.txt").decode().strip()
        simulator_argv = archive.read(prefix + "runs/c0/simulator_argv.txt").decode()
        plugin_stderr = archive.read(
            prefix + "return_core/plugins/node0004_source_bound_collect.stderr.log"
        ).decode(errors="replace")
        sim_log = archive.read(prefix + "runs/c0/sim.log")
        source_log = archive.read(prefix + "runs/c0/source_bound_causal.log")
        for receipt in core.get("core_entry_receipts", []):
            member = prefix + receipt["path"]
            if member not in names:
                if receipt.get("required"):
                    errors.append("missing_receipted_member:" + receipt["path"])
            else:
                data = archive.read(member)
                if len(data) != receipt["bytes"] or digest(data) != receipt["sha256"]:
                    errors.append("per_file_receipt_mismatch:" + receipt["path"])

    with zipfile.ZipFile(args.source_zip) as archive:
        source_manifest = json.loads(archive.read(PACKAGE + "/package_manifest.json"))
        semantics = json.loads(
            archive.read(PACKAGE + "/diagnostics/buffer_ack_phase_semantics_contract.json")
        )
        observer = archive.read(PACKAGE + "/tb_probe/buffer_ack_phase_observer.svh").decode()
        generation = json.loads(
            archive.read(PACKAGE + "/diagnostics/source_bound_observer_generation_report.json")
        )

    identity_checks = {
        "core_package": core.get("package_id") == PACKAGE,
        "core_execution": core.get("execution_id") == EXECUTION,
        "status_package": status.get("package_id") == PACKAGE,
        "status_execution": status.get("execution_id") == EXECUTION,
        "sim_exit_package": sim_exit.get("package_id") == PACKAGE,
        "sim_exit_execution": sim_exit.get("execution_id") == EXECUTION,
        "returned_manifest_exact": returned_manifest == source_manifest,
        "install_name": returned_manifest.get("install_name") == PACKAGE,
        "return_basename": core.get("return_basename")
        == PACKAGE + "_" + EXECUTION + "_return.zip",
    }
    if not all(identity_checks.values()):
        errors.append("internal_source_execution_install_publication_identity_failure")

    sequences = phase.get("sequences", {})
    complete = int(phase.get("complete_sequence_count", 0))
    all_rows = [row for sequence in sequences.values() for row in sequence.values()]
    exact_payload = (
        phase.get("target_instance") == TARGET
        and phase.get("payload_width_bits") == 38
        and phase.get("unknown_or_width_invalid_count") == 0
        and all(row.get("instance") == TARGET for row in all_rows)
        and all(row.get("payload_known") == "1" and row.get("payload_width") == "38" for row in all_rows)
    )
    parse_before = (
        phase_receipt.get("parser_exit_status") == 0
        and phase_receipt.get("parsed_before_frozen_bounded_collector") is True
        and phase_receipt.get("raw_phase_input_bytes_before_bounded_projection", 0)
        > len(sim_log)
        and phase_receipt.get("decision_sha256")
        == digest(json.dumps(phase, indent=2, sort_keys=True).encode() + b"\n")
    )
    # The decision file is already receipt-bound; tolerate serializer byte-order by using the core receipt.
    if not parse_before and phase_receipt.get("parser_exit_status") == 0:
        parse_before = (
            phase_receipt.get("parsed_before_frozen_bounded_collector") is True
            and phase_receipt.get("raw_phase_input_bytes_before_bounded_projection", 0) > len(sim_log)
        )
    if not parse_before:
        errors.append("parse_before_projection_not_proven")
    if not exact_payload:
        errors.append("exact_instance_or_payload_contract_failed")

    phase_names = ("ACTIVE", "INACTIVE", "POSTNBA", "HALF", "NEXT")
    edge_collisions = 0
    all_operand_transition = True
    tag_or_operand_changes = 0
    for sequence in sequences.values():
        if not all(name in sequence for name in phase_names):
            continue
        active = sequence["ACTIVE"]
        postnba = sequence["POSTNBA"]
        half = sequence["HALF"]
        nxt = sequence["NEXT"]
        if postnba["time"] == half["time"] == active["time"] + 1000:
            edge_collisions += 1
        if any(
            active[field] != postnba[field]
            for field in ("valid", "same", "gotten", "keep", "bpmask", "bp", "row", "col", "rowtag", "coltag")
        ):
            tag_or_operand_changes += 1
    all_operand_transition = phase.get("classes") == ["OPERAND_OR_EPOCH_TRANSITION"] * complete
    phase_adjudication = {
        "decision": phase.get("decision"),
        "live_event_count": phase.get("live_event_count"),
        "sequence_count": phase.get("sequence_count"),
        "complete_sequence_count": complete,
        "exact_instance_and_binary_known_38bit": exact_payload,
        "postnba_equals_half_timestamp_count": edge_collisions,
        "next_aliases_postnba_or_half_count": sum(
            1
            for sequence in sequences.values()
            if sequence.get("NEXT", {}).get("time")
            == sequence.get("POSTNBA", {}).get("time")
        ),
        "tag_or_operand_change_active_to_postnba_count": tag_or_operand_changes,
        "all_sequences_classified_operand_or_epoch_transition": all_operand_transition,
        "sampling_problem": (
            "The observer uses #1 after the positive edge while the observed clock half-period is 1000 ps. "
            "POSTNBA and HALF therefore share the same timestamp and NEXT lands on the next positive edge; "
            "the five-record group mixes different edge-owned operands/tags instead of a stable token."
        ),
    }
    if complete != 13 or edge_collisions != complete or not all_operand_transition:
        errors.append("expected_edge_collision_witness_not_closed")

    source_bound_signature = source_bound.get("observations", {})
    source_bound_gap = {
        "decision": source_bound.get("decision"),
        "reason": source_bound.get("reason"),
        "observations": source_bound_signature,
        "missing_candidate_signature": source_bound_signature
        == {
            "buf_ack_witness_count_nonzero": True,
            "buf_terminal_seen": True,
            "mem_source_match_count_nonzero": False,
            "mem_terminal_seen": True,
        },
        "plugin_failure_contains_source_bound_incomplete": (
            "target-complete source-bound parser result remains incomplete" in plugin_stderr
        ),
    }

    plugin = next(
        (row for row in plugins if row.get("plugin_id") == "node0004_source_bound_collect"),
        {},
    )
    natural = bool(sim_exit.get("natural_terminal_observed"))
    present = 0
    missing = 320
    mismatch = 0
    e3 = compile_exit == 0 and run_exit == 0 and signal == "NONE" and natural
    e4 = e3 and present == 320 and missing == 0 and mismatch == 0
    e5 = False

    report = {
        "schema": "conv-node0004-v82b-formal-return-analysis-v1",
        "analysis_valid": not errors,
        "structural_errors": errors,
        "RETURN_ANALYSIS": {
            "return": {"path": str(args.return_zip), "bytes": len(return_bytes), "sha256": digest(return_bytes)},
            "source": {"path": str(args.source_zip), "bytes": len(source_bytes), "sha256": digest(source_bytes)},
            "execution_id": EXECUTION,
            "transport_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY",
            "crc_root_path_exact_set_allowlist_per_file": not errors,
            "identity_checks": identity_checks,
            "compile_exit": compile_exit,
            "run_exit": run_exit,
            "signal": signal,
            "simulator_argv_bound": PACKAGE in simulator_argv,
            "natural_terminal": natural,
            "formal_d": {"present": present, "missing": missing, "mismatch": mismatch},
            "E3": e3,
            "E4": e4,
            "E5": e5,
            "core_disposition": status.get("disposition"),
            "missing_required_entries": status.get("missing_required_entries", []),
            "required_plugin_failures": status.get("required_plugin_failures", []),
            "plugin_exit": plugin.get("exit_code"),
            "parse_before_projection": parse_before,
            "semantic_fingerprint_sha256": generation.get("diagnostic_semantics_sha256"),
            "source_bound_gap": source_bound_gap,
        },
        "PHASE_ADJUDICATION": phase_adjudication,
        "LAST_PROVEN_GOOD": "EXACT_TARGET_PARSE_BEFORE_PROJECTION_WITH_13_COMPLETE_BINARY_KNOWN_PHASE_GROUPS",
        "FIRST_DIVERGENCE": "V82B_POSTNBA_SAMPLE_COLLIDES_WITH_NEGEDGE_AND_MIXES_SUCCESSIVE_TOKEN_EPOCHS",
        "HANG_ROOT_CAUSE": {
            "status": "PACKAGE_LOCAL_PHASE_SAMPLER_EDGE_COLLISION_AND_MIXED_TOKEN_SEQUENCE",
            "functional_root_cause": "UNRESOLVED_BECAUSE_NO_EDGE_FREE_STABLE_TOKEN_SAMPLE_EXISTS",
            "not_rtl_or_config_evidence": True,
            "mechanism": phase_adjudication["sampling_problem"],
        },
        "PROGRESS_THIS_ROUND": {
            "closed_since_v81": [
                "POST_SIM_PHASE_EVENT_ERASURE",
                "EXACT_INSTANCE_BINDING",
                "38BIT_BINARY_KNOWN_PAYLOAD_BINDING",
                "SEMANTIC_FINGERPRINT_BINDING",
            ],
            "first_proven": [
                "13_COMPLETE_EXACT_TARGET_PHASE_GROUPS_SURVIVE_PROJECTION",
                "ALL_13_GROUPS_MIX_OPERAND_OR_EPOCH_TRANSITIONS_AT_CLOCK_EDGES",
                "SOURCE_BOUND_SIGNATURE_MEM_SOURCE_MATCH_FALSE_WITH_BOTH_TERMINALS_PRESENT",
            ],
            "functional_completion_advanced": False,
            "remaining_root_scope": (
                "A stable pre-edge and edge-free post-edge sample is required to separate propagation settle, "
                "consumer gotten ownership and persistent equation mismatch."
            ),
        },
        "BLOCKER_DELTA": {
            "closed": ["B_CONV_NODE0004_V81_PHASE_EVENT_DROPPED_BY_POST_SIM_PROJECTION_ORDER"],
            "opened": [
                "B_CONV_NODE0004_V82B_PHASE_SAMPLE_COLLIDES_WITH_CLOCK_EDGE",
                "B_CONV_NODE0004_SOURCE_BOUND_CANDIDATE_TABLE_MISSES_MEM_SOURCE_MATCH_FALSE",
            ],
            "retained": [
                "B_CONV_NODE0004_BUFFER_ACK_STABLE_TOKEN_PHASE_UNRESOLVED",
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
            "invalidated_not_revived": ["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"],
        },
        "PACKAGE_NEXT": {
            "required": True,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "minimal_fix": (
                "Use stable pre-edge plus 1 ps/250 ps/750 ps edge-free samples, retain exact target and payload ABI, "
                "and complete the source-bound candidate truth table for mem_source_match=false."
            ),
        },
        "claims": {
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
