from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v80_ack_phase_diag"
ROOT_NAME = PACKAGE + "_return"
RETURN_BYTES = 347577
RETURN_SHA = "292f5a4019f5fe76352a0ab0269c2fd87df0d2b0ef1c1c67a0c95983605f8505"
SOURCE_SHA = "cd3dd4f78f1ed75c0fc94b3113f6afb447c507e61fe9d289a20d90854e117a8a"
EXECUTION = "r1786378837752588882_729112"
EXACT_TARGET = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
    "u_Buffer_AG_Idx_Queue.codex_probe_buf_ack_phase_witness_inst"
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(z: zipfile.ZipFile, prefix: str, name: str):
    return json.loads(z.read(prefix + name))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-zip", required=True, type=Path)
    ap.add_argument("--source-zip", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    errors: list[str] = []
    rdata, sdata = args.return_zip.read_bytes(), args.source_zip.read_bytes()
    if len(rdata) != RETURN_BYTES or sha(rdata) != RETURN_SHA:
        errors.append("external_return_identity_mismatch")
    if sha(sdata) != SOURCE_SHA:
        errors.append("source_zip_identity_mismatch")
    expected = {
        "RETURN_CORE_MANIFEST.json", "evidence/SERVER_RESULT_GATE.json",
        "evidence/buffer_ack_phase_parser_receipt.json",
        "evidence/buffer_input_ack_equation_parser_receipt.json",
        "evidence/compile_exit_status.txt", "evidence/post_final_buffer_input_owner_parser_receipt.json",
        "evidence/returned_package_manifest.json", "evidence/run_exit_status.txt",
        "evidence/signal_status.txt", "evidence/source_bound_parser_receipt.json",
        "evidence/target_temporal_parser_receipt.json", "return_core/RETURN_CORE_STATUS.json",
        "return_core/RETURN_PLUGIN_STATUS.json", "return_core/SIM_EXIT_RECEIPT.json",
        "return_core/plugins/node0004_source_bound_collect.status.json",
        "return_core/plugins/node0004_source_bound_collect.stderr.log",
        "return_core/plugins/node0004_source_bound_collect.stdout.log",
        "runs/c0/buffer_ack_phase_decision.json", "runs/c0/buffer_input_ack_equation_decision.json",
        "runs/c0/post_final_buffer_input_owner_decision.json", "runs/c0/return_observer.log",
        "runs/c0/sim.log", "runs/c0/simulator_argv.txt", "runs/c0/source_bound_causal.log",
        "runs/c0/source_bound_causal_decision.json", "runs/c0/target_temporal_decision.json",
    }
    with zipfile.ZipFile(args.return_zip) as z:
        infos = z.infolist(); names = [x.filename for x in infos]
        if z.testzip() is not None: errors.append("crc_failure")
        if len(names) != len(set(names)): errors.append("duplicate_member")
        for info in infos:
            p = PurePosixPath(info.filename)
            if p.is_absolute() or not p.parts or p.parts[0] != ROOT_NAME or ".." in p.parts or "\\" in info.filename or stat.S_ISLNK(info.external_attr >> 16):
                errors.append("unsafe_member:" + info.filename)
        prefix = ROOT_NAME + "/"
        if {n[len(prefix):] for n in names} != expected: errors.append("exact_set_mismatch")
        core = read_json(z, prefix, "RETURN_CORE_MANIFEST.json")
        status = read_json(z, prefix, "return_core/RETURN_CORE_STATUS.json")
        plugins = read_json(z, prefix, "return_core/RETURN_PLUGIN_STATUS.json")
        sim_exit = read_json(z, prefix, "return_core/SIM_EXIT_RECEIPT.json")
        gate = read_json(z, prefix, "evidence/SERVER_RESULT_GATE.json")
        returned_manifest = read_json(z, prefix, "evidence/returned_package_manifest.json")
        phase = read_json(z, prefix, "runs/c0/buffer_ack_phase_decision.json")
        phase_receipt = read_json(z, prefix, "evidence/buffer_ack_phase_parser_receipt.json")
        equation = read_json(z, prefix, "runs/c0/buffer_input_ack_equation_decision.json")
        compile_exit = int(z.read(prefix + "evidence/compile_exit_status.txt").strip())
        run_exit = int(z.read(prefix + "evidence/run_exit_status.txt").strip())
        signal = z.read(prefix + "evidence/signal_status.txt").decode().strip()
        sim_log = z.read(prefix + "runs/c0/sim.log").decode("utf-8", errors="replace")
        for receipt in core.get("core_entry_receipts", []):
            member = prefix + receipt["path"]
            if member not in names:
                if receipt.get("required"): errors.append("missing_receipted_member:" + receipt["path"])
            else:
                data = z.read(member)
                if len(data) != receipt["bytes"] or sha(data) != receipt["sha256"]:
                    errors.append("per_file_receipt_mismatch:" + receipt["path"])
    with zipfile.ZipFile(args.source_zip) as z:
        source_manifest = json.loads(z.read(PACKAGE + "/package_manifest.json"))
    identity = [
        core.get("package_id") == PACKAGE, core.get("execution_id") == EXECUTION,
        status.get("package_id") == PACKAGE, status.get("execution_id") == EXECUTION,
        sim_exit.get("package_id") == PACKAGE, sim_exit.get("execution_id") == EXECUTION,
        returned_manifest == source_manifest, returned_manifest.get("install_name") == PACKAGE,
    ]
    if not all(identity): errors.append("internal_source_execution_identity_failure")
    plugin = next((x for x in plugins if x.get("plugin_id") == "node0004_source_bound_collect"), {})
    plugin_ok = plugin.get("required_for_adjudication") is True and plugin.get("exit_code") == 0 and plugin.get("pass") is True and status.get("missing_required_entries") == [] and status.get("required_plugin_failures") == []
    if not plugin_ok: errors.append("core_plugin_joint_gate_failure")

    sequences = list(phase.get("sequences", {}).values())
    parsed_instances = sorted({row[p]["instance"] for row in sequences for p in row})
    exact_target_rows = [line for line in sim_log.splitlines() if "boundary=buf_ack_phase_witness" in line and EXACT_TARGET in line and "kind=RING_STATE" in line]
    exact_target_phases = sorted({token.split("=", 1)[1] for line in exact_target_rows for token in line.split() if token.startswith("phase=")})
    phase_scope_valid = bool(sequences) and all(EXACT_TARGET in instance for instance in parsed_instances)
    if phase_scope_valid:
        errors.append("analysis_expected_wrong_instance_escape_not_observed")
    natural = bool(sim_exit.get("natural_terminal_observed"))
    formal = gate.get("formal_readback", {})
    present = int(formal.get("present", 0) or 0); missing = int(formal.get("missing", 320) or 320); mismatch = int(formal.get("mismatch", 0) or 0)
    e3 = compile_exit == 0 and run_exit == 0 and signal == "NONE" and natural
    e4 = e3 and bool(gate.get("formal_readback_claimed")) and present == 320 and missing == 0 and mismatch == 0
    e5 = e4 and bool(gate.get("e5_pass", False))
    report = {
        "schema": "conv-node0004-v80-formal-return-analysis-v1", "valid": not errors, "errors": errors,
        "RETURN_ANALYSIS": {
            "return": {"path": str(args.return_zip), "bytes": len(rdata), "sha256": sha(rdata)},
            "source": {"path": str(args.source_zip), "bytes": len(sdata), "sha256": sha(sdata)},
            "execution_id": EXECUTION, "transport_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY",
            "integrity_source_execution_install_publication_core_plugins": plugin_ok and not errors,
            "compile_exit": compile_exit, "run_exit": run_exit, "signal": signal,
            "natural_terminal": natural, "formal_d": {"present": present, "missing": missing, "mismatch": mismatch},
            "E3": e3, "E4": e4, "E5": e5,
            "reported_phase_decision": phase.get("decision"),
            "reported_phase_receipt_decision": phase_receipt.get("decision"),
            "reported_sequence_count": phase.get("sequence_count"),
            "parsed_instance_count": len(parsed_instances),
            "parsed_instances": parsed_instances,
            "exact_target_raw_event_count": len(exact_target_rows),
            "exact_target_raw_phases": exact_target_phases,
            "equation_decision": equation.get("decision"),
        },
        "LAST_PROVEN_GOOD": "V79_SAME_INSTANCE_ACTIVE_EDGE_ACK_EQUATION_CONTRADICTION_REPRODUCED_GLOBALLY_BUT_V80_PHASE_ROWS_NOT_BOUND_TO_THAT_INSTANCE",
        "FIRST_DIVERGENCE": "V80_PHASE_PARSER_TARGET_SUBSTRING_ACCEPTS_SLICE0_WHILE_REQUIRED_TARGET_IS_SLICE13_GROUP1",
        "HANG_ROOT_CAUSE": {
            "status": "PACKAGE_LOCAL_PHASE_OBSERVER_INSTANCE_SCOPE_AND_PAIRING_DEFECT",
            "reported_but_invalid_for_target": phase.get("decision"),
            "why_invalid": "Parser target is only the MSE4 suffix and groups by sequence number alone. All 13 complete sequences are slice0/group0, while the v79 contradiction target is slice13/group1. The exact target has only one returned STABLE row and no complete ACTIVE/DELTA/STABLE sequence. In addition, the old classifier calls a half-cycle result MULTI_DELTA before checking that operands changed.",
            "target_claim": "UNRESOLVED_NO_COMPLETE_SAME_INSTANCE_PHASE_SEQUENCE",
        },
        "PROGRESS_THIS_ROUND": {
            "closed_since_v79": ["V80_COMPILE_AND_PLUGIN_BINDING", "PHASE_OBSERVER_RUNTIME_ENABLE_AND_RETURN"],
            "first_proven": ["ANOTHER_MSE4_INSTANCE_CAN_SHOW_ACTIVE_AND_DELTA_STALE_THEN_HALF_CYCLE_CHANGED"],
            "not_proven": ["TARGET_SLICE13_DELTA_SETTLE", "TARGET_CONSUMER_STALE_ACK", "TARGET_PERSISTENT_EQUATION_MISMATCH", "NATURAL_TERMINAL", "FORMAL_D"],
            "functional_progress": False,
            "reason": "The new observation machinery ran, but the parser selected the wrong hardware instance; no target functional boundary advanced.",
        },
        "BLOCKER_DELTA": {
            "closed": [],
            "opened": ["B_CONV_NODE0004_V80_PHASE_PARSER_WRONG_INSTANCE_SCOPE"],
            "retained": ["B_CONV_NODE0004_BUFFER_ACK_ACTIVE_VS_SETTLED_CONSUMER_PHASE_UNRESOLVED", "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL", "B_CONV_NODE0004_FORMAL_D_320"],
            "invalidated_not_revived": ["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"],
        },
        "PACKAGE_NEXT": {
            "required": True, "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "scope": "Exact slice13/group1/MSE4 instance-only bind; ACTIVE/INACTIVE/POSTNBA/HALF/NEXT causal sequence, tag continuity and consumer gotten state; live EVENT records for INT/TERM partial return.",
        },
        "claims": {"numeric_analysis_repeated": False, "workload_rebuilt": False, "configuration_rebuilt": False, "functional_rtl_modified": False, "server_action": False},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
