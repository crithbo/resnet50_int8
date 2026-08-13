from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath


RETURN_SHA = "39d25e0fb99f790e019749d0d463c36a4be0d78ab5089c7ab9445efdb2b935bf"
RETURN_BYTES = 295681
PACKAGE = "r5_n4_hw_v77_terminal_temporal_ledger_diag"
SOURCE_SHA = "316d5d2a50ae3378cd7809963e5a9bb54a38e5f07763d512864e02945dcd4d91"
EXECUTION = "r1786363830598863325_590492"
ROOT_NAME = PACKAGE + "_return"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_member(archive: zipfile.ZipFile, prefix: str, relative: str):
    return json.loads(archive.read(prefix + relative).decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    errors: list[str] = []

    return_data = args.return_zip.read_bytes()
    source_data = args.source_zip.read_bytes()
    if len(return_data) != RETURN_BYTES or digest(return_data) != RETURN_SHA:
        errors.append("external return bytes/SHA mismatch")
    if digest(source_data) != SOURCE_SHA:
        errors.append("source ZIP SHA mismatch")

    with zipfile.ZipFile(args.return_zip) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if archive.testzip() is not None:
            errors.append("return CRC failure")
        if len(names) != len(set(names)):
            errors.append("duplicate return member")
        for info in infos:
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or not path.parts
                or path.parts[0] != ROOT_NAME
                or ".." in path.parts
                or "\\" in info.filename
                or stat.S_ISLNK(info.external_attr >> 16)
            ):
                errors.append(f"unsafe return member: {info.filename}")
        prefix = ROOT_NAME + "/"
        expected = {
            "RETURN_CORE_MANIFEST.json",
            "evidence/SERVER_RESULT_GATE.json",
            "evidence/compile_exit_status.txt",
            "evidence/returned_package_manifest.json",
            "evidence/run_exit_status.txt",
            "evidence/signal_status.txt",
            "evidence/source_bound_parser_receipt.json",
            "evidence/target_temporal_parser_receipt.json",
            "return_core/RETURN_CORE_STATUS.json",
            "return_core/RETURN_PLUGIN_STATUS.json",
            "return_core/SIM_EXIT_RECEIPT.json",
            "return_core/plugins/node0004_source_bound_collect.status.json",
            "return_core/plugins/node0004_source_bound_collect.stderr.log",
            "return_core/plugins/node0004_source_bound_collect.stdout.log",
            "runs/c0/return_observer.log",
            "runs/c0/sim.log",
            "runs/c0/simulator_argv.txt",
            "runs/c0/source_bound_causal.log",
            "runs/c0/source_bound_causal_decision.json",
            "runs/c0/target_temporal_decision.json",
        }
        actual = {name[len(prefix):] for name in names}
        if actual != expected:
            errors.append("RETURN_MANIFEST/exact-set mismatch")

        core = load_member(archive, prefix, "RETURN_CORE_MANIFEST.json")
        core_status = load_member(archive, prefix, "return_core/RETURN_CORE_STATUS.json")
        plugins = load_member(archive, prefix, "return_core/RETURN_PLUGIN_STATUS.json")
        sim_exit = load_member(archive, prefix, "return_core/SIM_EXIT_RECEIPT.json")
        gate = load_member(archive, prefix, "evidence/SERVER_RESULT_GATE.json")
        returned_manifest = load_member(archive, prefix, "evidence/returned_package_manifest.json")
        source_receipt = load_member(archive, prefix, "evidence/source_bound_parser_receipt.json")
        temporal_receipt = load_member(archive, prefix, "evidence/target_temporal_parser_receipt.json")
        source_decision = load_member(archive, prefix, "runs/c0/source_bound_causal_decision.json")
        temporal = load_member(archive, prefix, "runs/c0/target_temporal_decision.json")
        observer = archive.read(prefix + "runs/c0/return_observer.log").decode("utf-8", errors="replace")
        compile_exit = int(archive.read(prefix + "evidence/compile_exit_status.txt").strip())
        run_exit = int(archive.read(prefix + "evidence/run_exit_status.txt").strip())
        signal = archive.read(prefix + "evidence/signal_status.txt").decode().strip()
        for receipt in core.get("core_entry_receipts", []):
            member = prefix + receipt["path"]
            if member not in names:
                if receipt.get("required"):
                    errors.append("missing required receipted member: " + receipt["path"])
                continue
            data = archive.read(member)
            if len(data) != receipt["bytes"] or digest(data) != receipt["sha256"]:
                errors.append("per-file receipt mismatch: " + receipt["path"])

    with zipfile.ZipFile(args.source_zip) as archive:
        source_manifest = json.loads(archive.read(PACKAGE + "/package_manifest.json"))

    identities = {
        "core package": core.get("package_id") == PACKAGE,
        "core execution": core.get("execution_id") == EXECUTION,
        "core return basename": core.get("return_basename") == args.return_zip.name,
        "status package": core_status.get("package_id") == PACKAGE,
        "status execution": core_status.get("execution_id") == EXECUTION,
        "sim package": sim_exit.get("package_id") == PACKAGE,
        "sim execution": sim_exit.get("execution_id") == EXECUTION,
        "source manifest": returned_manifest == source_manifest,
    }
    for label, passed in identities.items():
        if not passed:
            errors.append("identity failure: " + label)

    plugin = next((item for item in plugins if item.get("plugin_id") == "node0004_source_bound_collect"), {})
    plugin_pass = (
        plugin.get("required_for_adjudication") is True
        and plugin.get("exit_code") == 0
        and plugin.get("pass") is True
        and plugin.get("timed_out") is False
        and plugin.get("launch_error") is None
        and core_status.get("missing_required_entries") == []
        and core_status.get("required_plugin_failures") == []
    )
    if not plugin_pass:
        errors.append("core/plugin joint receipt failure")

    temporal_checks = {
        "complete_target_ring": temporal_receipt.get("complete_target_ring_retained") is True,
        "ring_count_367": temporal_receipt.get("target_ring_record_count") == 367,
        "unique_candidate": temporal.get("matching_candidate_ids") == ["BUFFER_ACCEPTS_POST_MEMORY_TERMINAL_EPOCH"],
        "pairwise": temporal.get("pairwise_distinguishable") is True,
        "no_missing_summaries": temporal.get("missing_required_target_summaries") == [],
        "source_parser": source_receipt.get("parser_exit_status") == 0 and source_decision.get("errors") == [],
    }
    for label, passed in temporal_checks.items():
        if not passed:
            errors.append("temporal/parser check failure: " + label)

    token_rx = re.compile(
        r"^(?P<time>\d+) \| TOKEN_ORIGIN_ACCEPT_EDGE_V2 .*?buf_wr_ev=(?P<wr>[01]).*?"
        r"buf_pop_ev=(?P<pop>[01]).*?desc=(?P<desc>\d+).*?buf_row_tag=(?P<row>[0-9a-fx]+) "
        r"buf_col_tag=(?P<col>[0-9a-fx]+) buf_bp=(?P<bp>[0-9a-fx]+) buf_qwr=(?P<qwr>[0-9a-fx]+)"
    )
    token_events = []
    for line in observer.splitlines():
        match = token_rx.search(line)
        if match:
            item = match.groupdict()
            item.update({key: int(item[key]) for key in ("time", "wr", "pop", "desc")})
            token_events.append(item)
    final_desc = next((item for item in token_events if item["desc"] == 18), None)
    post_final = [item for item in token_events if final_desc and item["time"] >= final_desc["time"]]
    post_writes = [item for item in post_final if item["wr"]]
    no_ack_writes = [item for item in post_writes if item["bp"] == "0"]
    same_tag_pair_payload_changed = any(
        left["row"] == right["row"]
        and left["col"] == right["col"]
        and left["qwr"] != right["qwr"]
        for left, right in zip(post_writes, post_writes[1:])
    )

    observations = temporal.get("observations", {})
    natural = bool(sim_exit.get("natural_terminal_observed"))
    formal = gate.get("formal_readback", {})
    present = int(formal.get("present", 0) or 0)
    missing = int(formal.get("missing", 320) or 320)
    mismatch = int(formal.get("mismatch", 0) or 0)
    e3 = compile_exit == 0 and run_exit == 0 and signal == "NONE" and natural
    e4 = e3 and bool(gate.get("formal_readback_claimed")) and present == 320 and missing == 0 and mismatch == 0
    e5 = e4 and bool(gate.get("e5_pass", False))

    report = {
        "schema": "conv-node0004-v77-formal-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "return": {"path": str(args.return_zip), "bytes": len(return_data), "sha256": digest(return_data)},
            "source": {"path": str(args.source_zip), "bytes": len(source_data), "sha256": digest(source_data)},
            "execution_id": EXECUTION,
            "transport_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY",
            "internal_integrity_identity_plugin": plugin_pass and not errors,
            "compile_exit": compile_exit,
            "run_exit": run_exit,
            "signal": signal,
            "natural_terminal": natural,
            "formal_d": {"present": present, "missing": missing, "mismatch": mismatch},
            "E3": e3, "E4": e4, "E5": e5,
            "target_temporal_decision": temporal.get("decision"),
            "target_ring_records": temporal_receipt.get("target_ring_record_count"),
        },
        "LAST_PROVEN_GOOD": "MEMORY_BRANCH_LOCAL_TERMINAL_AND_QUEUE_DRAIN_9_OF_9_WHILE_BUFFER_BRANCH_CONTINUES_QUALIFIED_PROGRESS",
        "FIRST_DIVERGENCE": "AFTER_MEMORY_LOCAL_TERMINAL_BUFFER_QUEUE_ACCEPTS_EIGHT_MORE_ENTRIES_AND_RETAINS_FOUR_WITH_NO_NATURAL_D_RELEASE",
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_AFTER_UNIQUE_POST_MEMORY_BUFFER_EPOCH_CLASS",
            "unique_observed_class": "BUFFER_ACCEPTS_POST_MEMORY_TERMINAL_EPOCH",
            "observations": {
                "memory_terminal_time": observations.get("mem_terminal_time"),
                "memory_enqueue_dequeue_residual": observations.get("mem_queue_residual"),
                "buffer_enqueue_dequeue_residual": observations.get("buf_queue_residual"),
                "buffer_enqueues_after_memory_terminal": len(observations.get("buf_enqueue_after_mem_terminal", [])),
                "final_descriptor_event": final_desc,
                "post_final_buffer_writes": post_writes,
                "post_final_write_without_input_bp": no_ack_writes,
                "same_tags_but_changed_queue_payload": same_tag_pair_payload_changed,
            },
            "remaining_owner_classes": [
                "LEGITIMATE_KEEP_MODE_NEXT_COMBINATION_WITH_LOCAL_TERMINAL_ONLY",
                "BUFFER_INPUT_EPOCH_ADVANCES_BEYOND_DESCRIPTOR_OWNER",
                "BUFFER_QUEUE_WRITE_ACCEPT_NOT_ALIGNED_WITH_NONKEEP_INPUT_ACCEPT",
                "UPSTREAM_ROW_COL_TERMINAL_OR_KEEP_THRESHOLD_SCHEDULE_EXCESS",
            ],
            "why_not_rtl_bug_yet": "buf_idx_mode=2 enables keep semantics; adjacent same raw tags carry different queue payloads, so v77 does not prove exact-token replay or a violated producer/consumer equation.",
        },
        "BLOCKER_DELTA": {
            "closed": ["B_CONV_NODE0004_TARGET_TEMPORAL_RING_INCOMPLETE"],
            "refined_open": ["B_CONV_NODE0004_POST_MEMORY_TERMINAL_BUFFER_INPUT_OWNER_UNRESOLVED"],
            "invalidated_not_revived": ["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"],
        },
        "PACKAGE_NEXT": {
            "required": True,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "information_gain": "correlate true descriptor-final chronology with Buffer mode/keep/valid/same/gotten/bp and accepted queue payload in one bounded automatic decision",
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
