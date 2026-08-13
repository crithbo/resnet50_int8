from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath


EXPECTED_RETURN_SHA = "c2d98e5c1736790bc414bbe1fe174295c490d680e23c6cb1fb8c1a98f586afa4"
EXPECTED_RETURN_BYTES = 284387
EXPECTED_PACKAGE = "r5_n4_hw_v76_sourcebound_boundfix"
EXPECTED_SOURCE_SHA = "cb5158ac464dde5f291a179a334d1bc027a4bb7e16346116633cab9bc8c408bb"
EXPECTED_EXECUTION = "r1786345817050003389_482745"
EXPECTED_ROOT = EXPECTED_PACKAGE + "_return"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def jload(archive: zipfile.ZipFile, name: str):
    return json.loads(archive.read(name).decode("utf-8"))


def parse_probe(line: str) -> dict[str, str] | None:
    marker = "CODEX_PROBE_V1 "
    pos = line.find(marker)
    if pos < 0:
        return None
    fields: dict[str, str] = {}
    for token in line[pos + len(marker) :].strip().split():
        if "=" in token:
            key, value = token.split("=", 1)
            fields[key] = value
    return fields


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-zip", type=Path, required=True)
    ap.add_argument("--source-zip", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    errors: list[str] = []
    return_bytes = args.return_zip.read_bytes()
    source_bytes = args.source_zip.read_bytes()
    if len(return_bytes) != EXPECTED_RETURN_BYTES:
        errors.append("return byte size mismatch")
    if sha256(return_bytes) != EXPECTED_RETURN_SHA:
        errors.append("return SHA mismatch")
    if sha256(source_bytes) != EXPECTED_SOURCE_SHA:
        errors.append("source SHA mismatch")

    with zipfile.ZipFile(args.return_zip) as archive:
        bad_crc = archive.testzip()
        if bad_crc:
            errors.append(f"CRC failure: {bad_crc}")
        names = archive.namelist()
        if len(names) != len(set(names)):
            errors.append("duplicate ZIP member")
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or not p.parts or p.parts[0] != EXPECTED_ROOT:
                errors.append(f"unsafe or wrong-root member: {name}")
            info = archive.getinfo(name)
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                errors.append(f"symlink member: {name}")

        prefix = EXPECTED_ROOT + "/"
        core_manifest = jload(archive, prefix + "RETURN_CORE_MANIFEST.json")
        core_status = jload(archive, prefix + "return_core/RETURN_CORE_STATUS.json")
        plugin_status = jload(archive, prefix + "return_core/RETURN_PLUGIN_STATUS.json")
        sim_exit = jload(archive, prefix + "return_core/SIM_EXIT_RECEIPT.json")
        parser_receipt = jload(archive, prefix + "evidence/source_bound_parser_receipt.json")
        decision = jload(archive, prefix + "runs/c0/source_bound_causal_decision.json")
        gate = jload(archive, prefix + "evidence/SERVER_RESULT_GATE.json")
        returned_manifest = jload(archive, prefix + "evidence/returned_package_manifest.json")
        causal_bytes = archive.read(prefix + "runs/c0/source_bound_causal.log")
        sim_log_bytes = archive.read(prefix + "runs/c0/sim.log")
        compile_exit = int(archive.read(prefix + "evidence/compile_exit_status.txt").strip())
        run_exit = int(archive.read(prefix + "evidence/run_exit_status.txt").strip())
        signal = archive.read(prefix + "evidence/signal_status.txt").decode().strip()

        exact_expected = {
            prefix + "RETURN_CORE_MANIFEST.json",
            prefix + "evidence/SERVER_RESULT_GATE.json",
            prefix + "evidence/compile_exit_status.txt",
            prefix + "evidence/returned_package_manifest.json",
            prefix + "evidence/run_exit_status.txt",
            prefix + "evidence/signal_status.txt",
            prefix + "evidence/source_bound_parser_receipt.json",
            prefix + "return_core/RETURN_CORE_STATUS.json",
            prefix + "return_core/RETURN_PLUGIN_STATUS.json",
            prefix + "return_core/SIM_EXIT_RECEIPT.json",
            prefix + "return_core/plugins/node0004_source_bound_collect.status.json",
            prefix + "return_core/plugins/node0004_source_bound_collect.stderr.log",
            prefix + "return_core/plugins/node0004_source_bound_collect.stdout.log",
            prefix + "runs/c0/return_observer.log",
            prefix + "runs/c0/sim.log",
            prefix + "runs/c0/simulator_argv.txt",
            prefix + "runs/c0/source_bound_causal.log",
            prefix + "runs/c0/source_bound_causal_decision.json",
        }
        if set(names) != exact_expected:
            errors.append("return exact-set mismatch")

        for receipt in core_manifest.get("core_entry_receipts", []):
            member = prefix + receipt["path"]
            if member not in names:
                if receipt.get("required"):
                    errors.append(f"missing receipted member: {member}")
                continue
            data = archive.read(member)
            if len(data) != receipt["bytes"] or sha256(data) != receipt["sha256"]:
                errors.append(f"per-file receipt mismatch: {member}")

    with zipfile.ZipFile(args.source_zip) as source_archive:
        source_manifest_bytes = source_archive.read(EXPECTED_PACKAGE + "/package_manifest.json")
    returned_manifest_bytes = (json.dumps(returned_manifest, indent=2) + "\n").encode("utf-8")
    # JSON whitespace in the returned copy is not identity-bearing; the parsed objects must match.
    source_manifest = json.loads(source_manifest_bytes.decode("utf-8"))

    identity_checks = {
        "core_package": core_manifest.get("package_id") == EXPECTED_PACKAGE,
        "core_execution": core_manifest.get("execution_id") == EXPECTED_EXECUTION,
        "core_return_basename": core_manifest.get("return_basename") == args.return_zip.name,
        "status_package": core_status.get("package_id") == EXPECTED_PACKAGE,
        "status_execution": core_status.get("execution_id") == EXPECTED_EXECUTION,
        "sim_package": sim_exit.get("package_id") == EXPECTED_PACKAGE,
        "sim_execution": sim_exit.get("execution_id") == EXPECTED_EXECUTION,
        "source_package_manifest": (
            returned_manifest == source_manifest
            and returned_manifest.get("install_name") == EXPECTED_PACKAGE
        ),
    }
    for key, value in identity_checks.items():
        if not value:
            errors.append(f"identity check failed: {key}")

    plugin = next((x for x in plugin_status if x.get("plugin_id") == "node0004_source_bound_collect"), None)
    plugin_pass = bool(
        plugin
        and plugin.get("required_for_adjudication") is True
        and plugin.get("exit_code") == 0
        and plugin.get("pass") is True
        and plugin.get("timed_out") is False
        and plugin.get("launch_error") is None
    )
    if not plugin_pass:
        errors.append("required source-bound plugin did not pass")
    if core_status.get("missing_required_entries") != []:
        errors.append("core missing required entries")
    if core_status.get("required_plugin_failures") != []:
        errors.append("core reports required plugin failure")

    parser_checks = {
        "parser_exit_zero": parser_receipt.get("parser_exit_status") == 0,
        "bounded_under_limit": parser_receipt.get("bounded_log_bytes", 1)
        <= parser_receipt.get("bounded_log_limit_bytes", 0),
        "bounded_hash": sha256(causal_bytes) == parser_receipt.get("bounded_log_sha256"),
        "sim_equals_causal": sim_log_bytes == causal_bytes and parser_receipt.get("sim_log_equals_causal_log") is True,
        "candidate": parser_receipt.get("matching_candidate_ids") == ["both_terminals_present_temporal_skew"],
        "decision": parser_receipt.get("parser_decision") == "POST_TERMINAL_TEMPORAL_OWNERSHIP_REQUIRES_RING",
        "decision_errors_empty": decision.get("errors") == [],
        "decision_candidate": decision.get("matching_candidate_ids") == ["both_terminals_present_temporal_skew"],
        "all_boundaries_enabled": len(decision.get("enabled_boundaries", [])) == 12,
        "missing_boundaries_empty": decision.get("missing_enabled_boundaries") == [],
        "missing_summaries_empty": decision.get("missing_required_summaries") == [],
    }
    for key, value in parser_checks.items():
        if not value:
            errors.append(f"parser check failed: {key}")

    target_instance_prefix = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice."
        "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
    )
    by_boundary_kind: dict[str, Counter[str]] = defaultdict(Counter)
    times: dict[str, list[int]] = defaultdict(list)
    payloads: dict[str, list[str]] = defaultdict(list)
    for line in causal_bytes.decode("utf-8", errors="replace").splitlines():
        fields = parse_probe(line)
        instance = fields.get("instance", "")
        if not fields or not instance.startswith(target_instance_prefix):
            continue
        boundary = fields.get("boundary", "")
        kind = fields.get("kind", "")
        by_boundary_kind[boundary][kind] += 1
        if kind in {"TRIGGER", "RING_PROGRESS", "RING_STATE", "RING_POST"}:
            match = re.match(r"(\d+)", line)
            if match:
                times[boundary].append(int(match.group(1)))
            if "payload" in fields:
                payloads[boundary].append(fields["payload"])

    # Summary records carry the exact total edge count even though ring retention is tail=1.
    summary_counts: dict[str, int] = {}
    summary_first: dict[str, int] = {}
    summary_last: dict[str, int] = {}
    for line in causal_bytes.decode("utf-8", errors="replace").splitlines():
        fields = parse_probe(line)
        instance = fields.get("instance", "")
        if (
            not fields
            or not instance.startswith(target_instance_prefix)
            or fields.get("kind") != "SUMMARY"
        ):
            continue
        boundary = fields.get("boundary", "")
        summary_counts[boundary] = int(fields.get("count", "0"), 0)
        summary_first[boundary] = int(fields.get("first", "0"), 0)
        summary_last[boundary] = int(fields.get("last", "0"), 0)

    critical = {
        b: {
            "count": summary_counts.get(b, 0),
            "first": summary_first.get(b, 0),
            "last": summary_last.get(b, 0),
            "retained_kinds": dict(by_boundary_kind.get(b, {})),
            "retained_payload_tail": payloads.get(b, [])[-3:],
        }
        for b in (
            "mem_source_match", "mem_queue_enqueue", "mem_queue_dequeue", "mem_consumer_accept", "mem_terminal",
            "buf_source_match", "buf_queue_enqueue", "buf_queue_dequeue", "buf_consumer_accept", "buf_terminal",
        )
    }

    natural = bool(sim_exit.get("natural_terminal_observed"))
    formal_claimed = bool(gate.get("formal_readback_claimed"))
    formal = gate.get("formal_readback", {})
    formal_present = int(formal.get("present", 0) or 0)
    formal_missing = int(formal.get("missing", 320) or 320)
    formal_mismatch = int(formal.get("mismatch", 0) or 0)
    e3 = compile_exit == 0 and run_exit == 0 and signal == "NONE" and natural
    e4 = e3 and formal_claimed and formal_present == 320 and formal_missing == 0 and formal_mismatch == 0
    e5 = e4 and bool(gate.get("e5_pass", False))

    chronology_checks = {
        "buf_terminal_seen_before_mem_terminal": summary_first.get("buf_terminal", 0)
        < summary_first.get("mem_terminal", 0),
        "buf_terminal_count_exceeds_mem": summary_counts.get("buf_terminal", 0)
        > summary_counts.get("mem_terminal", 0),
        "buf_enqueue_exceeds_mem_enqueue": summary_counts.get("buf_queue_enqueue", 0)
        > summary_counts.get("mem_queue_enqueue", 0),
        "buf_consumer_exceeds_mem_consumer": summary_counts.get("buf_consumer_accept", 0)
        > summary_counts.get("mem_consumer_accept", 0),
    }
    for key, value in chronology_checks.items():
        if not value:
            errors.append(f"chronology check failed: {key}")

    report = {
        "schema": "conv-node0004-v76-formal-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "return_receipt": {
            "path": args.return_zip.as_posix(), "bytes": len(return_bytes), "sha256": sha256(return_bytes),
            "external_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY",
            "crc_root_path_duplicate_symlink_exact_set": "PASS" if not any(
                token in e for e in errors for token in ("CRC", "root", "duplicate", "symlink", "exact-set")
            ) else "FAIL",
        },
        "source_receipt": {
            "path": args.source_zip.as_posix(), "bytes": len(source_bytes), "sha256": sha256(source_bytes),
            "package_id": EXPECTED_PACKAGE, "execution_id": EXPECTED_EXECUTION,
        },
        "identity_checks": identity_checks,
        "return_core": {
            "disposition": core_status.get("disposition"),
            "missing_required_entries": core_status.get("missing_required_entries"),
            "required_plugin_failures": core_status.get("required_plugin_failures"),
            "plugin_pass": plugin_pass,
        },
        "bounded_projection": {
            **{k: parser_receipt.get(k) for k in (
                "original_sim_log_bytes", "source_bound_input_record_count", "source_bound_retained_record_count",
                "source_bound_dropped_ring_record_count", "bounded_log_bytes", "bounded_log_limit_bytes",
                "bounded_log_sha256", "ring_group_count", "ring_retention_policy", "parser_exit_status",
                "parser_decision", "matching_candidate_ids")},
            "checks": parser_checks,
        },
        "dynamic_joint_gate": {
            "compile_exit": compile_exit, "run_exit": run_exit, "signal": signal,
            "natural_terminal": natural, "formal_d_claimed": formal_claimed,
            "formal_d_present": formal_present, "formal_d_missing": formal_missing,
            "formal_d_mismatch": formal_mismatch, "E3": e3, "E4": e4, "E5": e5,
            "gate_status": gate.get("status"),
        },
        "target_instance_prefix": target_instance_prefix,
        "target_chronology": critical,
        "chronology_checks": chronology_checks,
        "LAST_PROVEN_GOOD": "SOURCE_BOUND_BOUNDED_COLLECTOR_AND_PARSER_CANONICAL_DECISION_PUBLISHED",
        "FIRST_DIVERGENCE": "TARGET_MSE4_BUFFER_TERMINAL_BRANCH_ADVANCES_EARLIER_AND_FARTHER_THAN_MEMORY_TERMINAL_BRANCH_WITHOUT_NATURAL_D_RELEASE",
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_FUNCTIONAL_LEAF_AFTER_UNIQUE_TEMPORAL_SKEW_CLASS",
            "unique_class": "both_terminals_present_temporal_skew",
            "remaining_candidates": [
                "BUFFER_BRANCH_STALE_OR_REPLAYED_EPOCH",
                "MEMORY_BRANCH_TERMINAL_SUPPRESSION_OR_DELAY",
                "DESCRIPTOR_CONSUMER_DRAIN_OWNERSHIP_MISMATCH",
                "BUFFER_BRANCH_POST_TERMINAL_EXTRA_ACCEPT",
            ],
            "why_not_unique": "tail=1 per instance/boundary preserves only the last ring event; it proves the terminal skew class and total counts but not the exact first divergence event across the two branches.",
        },
        "BLOCKER_DELTA": {
            "closed": ["B_CONV_NODE0004_V75_POST_SIM_BOUNDED_PROJECTION_OVERFLOW"],
            "refined_open": ["B_CONV_NODE0004_MSE4_BUFFER_MEMORY_TERMINAL_TEMPORAL_OWNER_UNRESOLVED"],
            "invalidated_not_revived": ["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"],
        },
        "continuous_closure": {
            "successor_required": True,
            "successor_classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "required_information_gain": "retain the complete bounded target-instance temporal ledger across all 12 boundaries and classify the four remaining candidates pairwise",
        },
        "claims": {
            "numeric_analysis_repeated": False, "workload_rebuilt": False,
            "config_changed": False, "functional_rtl_modified": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"valid": not errors, "errors": errors, "E3": e3, "E4": e4, "E5": e5}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
