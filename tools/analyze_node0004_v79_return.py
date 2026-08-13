from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v79_buffer_ack_equation_diag"
ROOT_NAME = PACKAGE + "_return"
RETURN_BYTES = 337252
RETURN_SHA = "b130f1b0b1bcde8ece6c20f1746f847c68566dd2d60ba210e7dc501a8ceaf571"
SOURCE_SHA = "447b5a5647b94d914093ec660134ad99ec5ab5e6fc194227bb4e7e9c21484d65"
EXECUTION = "r1786374110391704069_681582"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def member_json(archive: zipfile.ZipFile, prefix: str, name: str):
    return json.loads(archive.read(prefix + name).decode("utf-8"))


def canonical_json_sha(value: object) -> str:
    return sha(json.dumps(value, indent=2, sort_keys=True).encode() + b"\n")


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
        "evidence/buffer_input_ack_equation_parser_receipt.json",
        "evidence/compile_exit_status.txt",
        "evidence/post_final_buffer_input_owner_parser_receipt.json",
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
        "runs/c0/buffer_input_ack_equation_decision.json",
        "runs/c0/post_final_buffer_input_owner_decision.json",
        "runs/c0/return_observer.log",
        "runs/c0/sim.log",
        "runs/c0/simulator_argv.txt",
        "runs/c0/source_bound_causal.log",
        "runs/c0/source_bound_causal_decision.json",
        "runs/c0/target_temporal_decision.json",
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
            if (
                p.is_absolute()
                or not p.parts
                or p.parts[0] != ROOT_NAME
                or ".." in p.parts
                or "\\" in info.filename
                or stat.S_ISLNK(info.external_attr >> 16)
            ):
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
        equation_receipt = member_json(z, prefix, "evidence/buffer_input_ack_equation_parser_receipt.json")
        source_decision = member_json(z, prefix, "runs/c0/source_bound_causal_decision.json")
        temporal = member_json(z, prefix, "runs/c0/target_temporal_decision.json")
        owner = member_json(z, prefix, "runs/c0/post_final_buffer_input_owner_decision.json")
        equation = member_json(z, prefix, "runs/c0/buffer_input_ack_equation_decision.json")
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
        "source manifest SHA": returned_manifest.get("source_package_sha256") == "57044a3aef6208650681fe76076d20700fa267ddf415e91a3beb7d5daf065b56",
        "install name": returned_manifest.get("install_name") == PACKAGE,
    }
    errors += ["identity failure: " + key for key, ok in identity.items() if not ok]
    plugin = next((x for x in plugins if x.get("plugin_id") == "node0004_source_bound_collect"), {})
    plugin_ok = (
        plugin.get("required_for_adjudication") is True
        and plugin.get("exit_code") == 0
        and plugin.get("pass") is True
        and plugin.get("timed_out") is False
        and plugin.get("launch_error") is None
        and status.get("missing_required_entries") == []
        and status.get("required_plugin_failures") == []
    )
    if not plugin_ok:
        errors.append("core/plugin joint receipt failure")
    checks = {
        "source parser": source_receipt.get("parser_exit_status") == 0 and source_decision.get("errors") == [],
        "bounded projection": source_receipt.get("bounded_log_bytes", 1 << 30) <= source_receipt.get("bounded_log_limit_bytes", 0),
        "target ring": temporal_receipt.get("complete_target_ring_retained") is True and temporal_receipt.get("target_ring_record_count") == 422,
        "target unique": temporal.get("matching_candidate_ids") == ["BUFFER_ACCEPTS_POST_MEMORY_TERMINAL_EPOCH"],
        "owner parser": owner_receipt.get("parser_exit_status") == 0 and owner_receipt.get("decision") == owner.get("decision"),
        "owner receipt SHA": owner_receipt.get("decision_sha256") == canonical_json_sha(owner),
        "owner unique": owner.get("decision") == "BUFFER_WRITE_PRECEDES_INPUT_ACK_THEN_NEXT_PAYLOAD_ACCEPTS",
        "equation parser": equation_receipt.get("parser_exit_status") == 0 and equation_receipt.get("decision") == equation.get("decision"),
        "equation receipt SHA": equation_receipt.get("decision_sha256") == canonical_json_sha(equation),
        "equation unique": equation.get("decision") == "BP_MASK_PRESENT_BUT_OUTPUT_ACK_ZERO",
        "equation pairwise": equation.get("pairwise_distinguishable") is True,
        "equation writes": equation_receipt.get("target_write_witness_count") == 41,
    }
    errors += ["parser/decision failure: " + key for key, ok in checks.items() if not ok]

    natural = bool(sim_exit.get("natural_terminal_observed"))
    formal = gate.get("formal_readback", {})
    present = int(formal.get("present", 0) or 0)
    missing = int(formal.get("missing", 320) or 320)
    mismatch = int(formal.get("mismatch", 0) or 0)
    e3 = compile_exit == 0 and run_exit == 0 and signal == "NONE" and natural
    e4 = e3 and bool(gate.get("formal_readback_claimed")) and present == 320 and missing == 0 and mismatch == 0
    e5 = e4 and bool(gate.get("e5_pass", False))
    target_instance = "MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue"
    target_writes = [x for x in equation.get("target_write_witnesses", []) if target_instance in x.get("instance", "")]
    contradictions = [x for x in target_writes if (x.get("mask_int", 0) & 0x1C1) == 0x141 and not (x.get("mask_int", 0) & 0x80)]
    # Exact useful mask is bit0(write&&!full), bit6(bp-mask==3), bit7(public-bp==3), bit8(mode==2).
    contradictions = [x for x in target_writes if (x.get("mask_int", 0) & 0x141) == 0x141 and not (x.get("mask_int", 0) & 0x80)]
    report = {
        "schema": "conv-node0004-v79-formal-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "return": {"path": str(args.return_zip), "bytes": len(rdata), "sha256": sha(rdata)},
            "source": {"path": str(args.source_zip), "bytes": len(sdata), "sha256": sha(sdata)},
            "execution_id": EXECUTION,
            "transport_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY",
            "internal_integrity_identity_core_plugins": plugin_ok and not errors,
            "compile_exit": compile_exit,
            "run_exit": run_exit,
            "signal": signal,
            "natural_terminal": natural,
            "formal_d": {"present": present, "missing": missing, "mismatch": mismatch},
            "E3": e3,
            "E4": e4,
            "E5": e5,
            "source_bound_decision": source_decision.get("decision"),
            "target_temporal_decision": temporal.get("decision"),
            "post_final_input_owner_decision": owner.get("decision"),
            "ack_equation_decision": equation.get("decision"),
            "actual_compile_rtl_identity": "NOT_EXPLICITLY_RECEIPTED_IN_RETURN",
            "claimed_cloud_authority_commit": returned_manifest.get("cloud_rtl_authority", {}).get("approved_commit"),
        },
        "LAST_PROVEN_GOOD": "SAME_INSTANCE_BUFFER_WRITE_ACCEPT_WITH_NOT_FULL_AND_BP_MASK_EQ3",
        "FIRST_DIVERGENCE": "SAME_ACTIVE_EDGE_PUBLIC_BP_VECTOR_NOT_EQ3_DESPITE_NOT_FULL_AND_BP_MASK_EQ3",
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_ACTIVE_REGION_DELTA_SETTLING_VS_CONSUMER_VISIBLE_ACK",
            "unique_observed_class": equation.get("decision"),
            "target_write_witness_count": len(target_writes),
            "bp_mask_without_public_ack_witness_count": len(contradictions),
            "source_equation": "mse_buf_queue_bp_pre[i] = !buf_ag_idx_queue_full && buf_idx_bp_pre_mask[i]",
            "remaining_equivalence": [
                "ACTIVE_REGION_SAMPLE_PRECEDES_CONTINUOUS_ASSIGNMENT_SETTLING",
                "CONSUMER_SAMPLES_STALE_PUBLIC_BP_AT_CLOCK_EDGE",
                "PERSISTENT_PUBLIC_BP_EQUATION_OR_COMPILED_SOURCE_MISMATCH",
            ],
            "why_not_rtl_or_configuration_yet": "The generated bitmap proves the operands and public result disagree in the active-edge sample. A SystemVerilog active-region/delta-cycle transient can produce this observation even when the continuous equation settles later. v79 has no post-delta or half-cycle stable sample, and the return does not explicitly receipt the compiled Buffer_AG_Idx_Queue bytes; therefore neither RTL defect nor configuration correction is yet authorized.",
        },
        "BLOCKER_DELTA": {
            "closed": ["B_CONV_NODE0004_BUFFER_INPUT_ACK_KEEP_EQUATION_PHASE_UNRESOLVED"],
            "refined_open": ["B_CONV_NODE0004_BUFFER_ACK_ACTIVE_VS_SETTLED_CONSUMER_PHASE_UNRESOLVED"],
            "invalidated_not_revived": ["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"],
        },
        "PACKAGE_NEXT": {
            "required": True,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "information_gain": "compare active-edge, post-delta and stable half-cycle Buffer_AG equation operands/result plus upstream consumer acknowledgement for the same target instance and token",
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
