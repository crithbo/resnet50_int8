from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v78_buffer_input_owner_diag"
ROOT_NAME = PACKAGE + "_return"
RETURN_BYTES = 297405
RETURN_SHA = "1e6f2f6f4c5af952c903fb0552736cab43a027cbe9eec7a3d69d46cd63ec5b77"
SOURCE_SHA = "57044a3aef6208650681fe76076d20700fa267ddf415e91a3beb7d5daf065b56"
EXECUTION = "r1786370037540532089_657093"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def member_json(archive: zipfile.ZipFile, prefix: str, name: str):
    return json.loads(archive.read(prefix + name).decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-zip", required=True, type=Path)
    ap.add_argument("--source-zip", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    errors: list[str] = []
    rdata = args.return_zip.read_bytes()
    sdata = args.source_zip.read_bytes()
    if len(rdata) != RETURN_BYTES or sha(rdata) != RETURN_SHA:
        errors.append("external return bytes/SHA mismatch")
    if sha(sdata) != SOURCE_SHA:
        errors.append("source ZIP SHA mismatch")

    expected = {
        "RETURN_CORE_MANIFEST.json",
        "evidence/SERVER_RESULT_GATE.json",
        "evidence/compile_exit_status.txt",
        "evidence/returned_package_manifest.json",
        "evidence/run_exit_status.txt",
        "evidence/signal_status.txt",
        "evidence/source_bound_parser_receipt.json",
        "evidence/target_temporal_parser_receipt.json",
        "evidence/post_final_buffer_input_owner_parser_receipt.json",
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
        "runs/c0/post_final_buffer_input_owner_decision.json",
    }
    with zipfile.ZipFile(args.return_zip) as z:
        infos = z.infolist()
        names = [x.filename for x in infos]
        if z.testzip() is not None:
            errors.append("CRC failure")
        if len(names) != len(set(names)):
            errors.append("duplicate return member")
        for info in infos:
            p = PurePosixPath(info.filename)
            if p.is_absolute() or not p.parts or p.parts[0] != ROOT_NAME or ".." in p.parts or "\\" in info.filename or stat.S_ISLNK(info.external_attr >> 16):
                errors.append("unsafe return member: " + info.filename)
        prefix = ROOT_NAME + "/"
        actual = {n[len(prefix):] for n in names}
        if actual != expected:
            errors.append("RETURN_MANIFEST/exact-set mismatch")
        core = member_json(z, prefix, "RETURN_CORE_MANIFEST.json")
        status = member_json(z, prefix, "return_core/RETURN_CORE_STATUS.json")
        plugins = member_json(z, prefix, "return_core/RETURN_PLUGIN_STATUS.json")
        sim_exit = member_json(z, prefix, "return_core/SIM_EXIT_RECEIPT.json")
        gate = member_json(z, prefix, "evidence/SERVER_RESULT_GATE.json")
        returned_manifest = member_json(z, prefix, "evidence/returned_package_manifest.json")
        source_receipt = member_json(z, prefix, "evidence/source_bound_parser_receipt.json")
        temporal_receipt = member_json(z, prefix, "evidence/target_temporal_parser_receipt.json")
        owner_receipt = member_json(z, prefix, "evidence/post_final_buffer_input_owner_parser_receipt.json")
        source_decision = member_json(z, prefix, "runs/c0/source_bound_causal_decision.json")
        temporal = member_json(z, prefix, "runs/c0/target_temporal_decision.json")
        owner = member_json(z, prefix, "runs/c0/post_final_buffer_input_owner_decision.json")
        compile_exit = int(z.read(prefix + "evidence/compile_exit_status.txt").strip())
        run_exit = int(z.read(prefix + "evidence/run_exit_status.txt").strip())
        signal = z.read(prefix + "evidence/signal_status.txt").decode().strip()
        for receipt in core.get("core_entry_receipts", []):
            path = prefix + receipt["path"]
            if path not in names:
                if receipt.get("required"):
                    errors.append("missing required receipted member: " + receipt["path"])
            else:
                data = z.read(path)
                if len(data) != receipt["bytes"] or sha(data) != receipt["sha256"]:
                    errors.append("per-file receipt mismatch: " + receipt["path"])

    with zipfile.ZipFile(args.source_zip) as z:
        source_manifest = json.loads(z.read(PACKAGE + "/package_manifest.json"))
    identity = {
        "core package": core.get("package_id") == PACKAGE,
        "core execution": core.get("execution_id") == EXECUTION,
        "status package": status.get("package_id") == PACKAGE,
        "status execution": status.get("execution_id") == EXECUTION,
        "sim package": sim_exit.get("package_id") == PACKAGE,
        "sim execution": sim_exit.get("execution_id") == EXECUTION,
        "source manifest": returned_manifest == source_manifest,
    }
    errors += ["identity failure: " + k for k, ok in identity.items() if not ok]
    plugin = next((x for x in plugins if x.get("plugin_id") == "node0004_source_bound_collect"), {})
    plugin_ok = (
        plugin.get("required_for_adjudication") is True
        and plugin.get("exit_code") == 0 and plugin.get("pass") is True
        and plugin.get("timed_out") is False and plugin.get("launch_error") is None
        and status.get("missing_required_entries") == []
        and status.get("required_plugin_failures") == []
    )
    if not plugin_ok:
        errors.append("core/plugin joint receipt failure")
    decision_sha = sha(json.dumps(owner, indent=2, sort_keys=True).encode() + b"\n")
    checks = {
        "source parser": source_receipt.get("parser_exit_status") == 0 and source_decision.get("errors") == [],
        "target ring": temporal_receipt.get("complete_target_ring_retained") is True and temporal_receipt.get("target_ring_record_count") == 367,
        "target unique": temporal.get("matching_candidate_ids") == ["BUFFER_ACCEPTS_POST_MEMORY_TERMINAL_EPOCH"],
        "owner parser": owner_receipt.get("parser_exit_status") == 0 and owner_receipt.get("decision") == owner.get("decision"),
        "owner receipt SHA": owner_receipt.get("decision_sha256") == decision_sha,
        "owner unique": owner.get("decision") == "BUFFER_WRITE_PRECEDES_INPUT_ACK_THEN_NEXT_PAYLOAD_ACCEPTS",
        "owner pairwise": owner.get("pairwise_distinguishable") is True,
    }
    errors += ["parser/decision failure: " + k for k, ok in checks.items() if not ok]

    natural = bool(sim_exit.get("natural_terminal_observed"))
    formal = gate.get("formal_readback", {})
    present = int(formal.get("present", 0) or 0)
    missing = int(formal.get("missing", 320) or 320)
    mismatch = int(formal.get("mismatch", 0) or 0)
    e3 = compile_exit == 0 and run_exit == 0 and signal == "NONE" and natural
    e4 = e3 and bool(gate.get("formal_readback_claimed")) and present == 320 and missing == 0 and mismatch == 0
    e5 = e4 and bool(gate.get("e5_pass", False))
    post = owner.get("post_final_buffer_write_events", [])
    first = post[0] if post else None
    second = post[1] if len(post) > 1 else None
    report = {
        "schema": "conv-node0004-v78-formal-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "return": {"path": str(args.return_zip), "bytes": len(rdata), "sha256": sha(rdata)},
            "source": {"path": str(args.source_zip), "bytes": len(sdata), "sha256": sha(sdata)},
            "execution_id": EXECUTION,
            "transport_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY",
            "internal_integrity_identity_core_plugins": plugin_ok and not errors,
            "compile_exit": compile_exit, "run_exit": run_exit, "signal": signal,
            "natural_terminal": natural,
            "formal_d": {"present": present, "missing": missing, "mismatch": mismatch},
            "E3": e3, "E4": e4, "E5": e5,
            "source_bound_decision": source_decision.get("decision"),
            "target_temporal_decision": temporal.get("decision"),
            "post_final_input_owner_decision": owner.get("decision"),
        },
        "LAST_PROVEN_GOOD": "FINAL_DESCRIPTOR_EVENT_18_THEN_BUFFER_QUEUE_WRITE_AND_PAYLOAD_ADVANCE",
        "FIRST_DIVERGENCE": "FIRST_POST_FINAL_BUFFER_WRITE_SHOWS_MATCHED_VALID_INPUTS_AND_NONFULL_QUEUE_BUT_NO_REPORTED_INPUT_ACK_BEFORE_NEXT_PAYLOAD_ACCEPT",
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_AT_BUFFER_INPUT_ACK_KEEP_EQUATION_PHASE",
            "unique_observed_class": owner.get("decision"),
            "qualified_observations": {"final_descriptor": owner.get("final_descriptor_event"), "first_post_final_write": first, "next_post_final_write": second},
            "remaining_candidates": [
                "KEEP_MASK_SUPPRESSES_INPUT0_ACK",
                "WR_ACCEPT_SAMPLE_PRECEDES_COMBINATIONAL_INPUT_ACK_SETTLING",
                "WR_ACCEPT_IS_NOT_SAME_TOKEN_AS_REPORTED_INPUT_ACK",
                "BUFFER_INPUT_ACK_EQUATION_OR_OWNER_VIOLATION",
            ],
            "why_not_configuration_or_rtl_yet": "The qualified write/descriptor chronology is unique, but v78 logs only the public bp aggregate and row-state summary. It does not capture the same-instance valid/same/gotten/keep/bp-mask terms needed to prove which conjunction suppresses input0 or whether the active-edge sample is phase-aliased.",
        },
        "BLOCKER_DELTA": {
            "closed": ["B_CONV_NODE0004_POST_MEMORY_TERMINAL_BUFFER_OWNER_CLASS_UNRESOLVED"],
            "refined_open": ["B_CONV_NODE0004_BUFFER_INPUT_ACK_KEEP_EQUATION_PHASE_UNRESOLVED"],
            "invalidated_not_revived": ["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"],
        },
        "PACKAGE_NEXT": {"required": True, "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX", "information_gain": "capture the complete same-instance Buffer_AG valid/same/gotten/keep/bp-mask/full/write equation and payload around the final descriptor in one source-bound ring"},
        "claims": {"numeric_analysis_repeated": False, "workload_rebuilt": False, "configuration_rebuilt": False, "functional_rtl_modified": False, "server_action": False},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
