from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v81_ack_phase_targetfix"
ROOT_NAME = PACKAGE + "_return"
RETURN_BYTES = 336256
RETURN_SHA = "9702b2d926c04476368ff78e865d6dcc8bc602b997d2530323bfe724d905aff6"
SOURCE_SHA = "fc3e7049822af17d956bfed7b95c9c13abdf9d151ef2881e2b68107d7b0c0389"
EXECUTION = "r1786384658245449969_758671"
EXACT_TARGET = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
    "u_Buffer_AG_Idx_Queue"
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(z: zipfile.ZipFile, prefix: str, name: str):
    return json.loads(z.read(prefix + name))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-zip", required=True, type=Path)
    ap.add_argument("--source-zip", required=True, type=Path)
    ap.add_argument("--source-tree", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    structural_errors: list[str] = []
    rdata = args.return_zip.read_bytes()
    sdata = args.source_zip.read_bytes()
    if len(rdata) != RETURN_BYTES or sha(rdata) != RETURN_SHA:
        structural_errors.append("external_return_identity_mismatch")
    if sha(sdata) != SOURCE_SHA:
        structural_errors.append("source_zip_identity_mismatch")

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
        "runs/c0/buffer_ack_phase_decision.json",
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
            structural_errors.append("crc_failure")
        if len(names) != len(set(names)):
            structural_errors.append("duplicate_member")
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
                structural_errors.append("unsafe_member:" + info.filename)
        prefix = ROOT_NAME + "/"
        actual = {n[len(prefix) :] for n in names}
        if actual != expected:
            structural_errors.append("exact_set_mismatch")

        core = read_json(z, prefix, "RETURN_CORE_MANIFEST.json")
        status = read_json(z, prefix, "return_core/RETURN_CORE_STATUS.json")
        plugins = read_json(z, prefix, "return_core/RETURN_PLUGIN_STATUS.json")
        sim_exit = read_json(z, prefix, "return_core/SIM_EXIT_RECEIPT.json")
        gate = read_json(z, prefix, "evidence/SERVER_RESULT_GATE.json")
        returned_manifest = read_json(z, prefix, "evidence/returned_package_manifest.json")
        phase = read_json(z, prefix, "runs/c0/buffer_ack_phase_decision.json")
        source_bound_receipt = read_json(z, prefix, "evidence/source_bound_parser_receipt.json")
        equation = read_json(z, prefix, "runs/c0/buffer_input_ack_equation_decision.json")
        compile_exit = int(z.read(prefix + "evidence/compile_exit_status.txt").strip())
        run_exit = int(z.read(prefix + "evidence/run_exit_status.txt").strip())
        signal = z.read(prefix + "evidence/signal_status.txt").decode().strip()
        sim_log_bytes = z.read(prefix + "runs/c0/sim.log")
        source_bound_bytes = z.read(prefix + "runs/c0/source_bound_causal.log")
        sim_log = sim_log_bytes.decode("utf-8", errors="replace")
        plugin_stderr = z.read(
            prefix + "return_core/plugins/node0004_source_bound_collect.stderr.log"
        ).decode("utf-8", errors="replace")
        for receipt in core.get("core_entry_receipts", []):
            member = prefix + receipt["path"]
            if member not in names:
                if receipt.get("required"):
                    structural_errors.append("missing_receipted_member:" + receipt["path"])
            else:
                data = z.read(member)
                if len(data) != receipt["bytes"] or sha(data) != receipt["sha256"]:
                    structural_errors.append("per_file_receipt_mismatch:" + receipt["path"])

    with zipfile.ZipFile(args.source_zip) as z:
        source_manifest = json.loads(z.read(PACKAGE + "/package_manifest.json"))

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
        structural_errors.append("internal_source_execution_install_publication_identity_failure")

    plugin = next(
        (x for x in plugins if x.get("plugin_id") == "node0004_source_bound_collect"), {}
    )
    required_missing = status.get("missing_required_entries", [])
    required_failures = status.get("required_plugin_failures", [])
    expected_failure_shape = (
        status.get("disposition") == "EVIDENCE_INCOMPLETE"
        and required_missing
        == ["missing entry: attempt:evidence/buffer_ack_phase_parser_receipt.json"]
        and required_failures == ["node0004_source_bound_collect"]
        and plugin.get("exit_code") == 1
        and plugin.get("pass") is False
        and "exact target live phase parser failed" in plugin_stderr
    )

    enabled_rows = [
        line
        for line in sim_log.splitlines()
        if "kind=ENABLED boundary=buf_ack_phase_target" in line and EXACT_TARGET in line
    ]
    summary_rows = [
        line
        for line in sim_log.splitlines()
        if "kind=SUMMARY boundary=buf_ack_phase_target" in line and EXACT_TARGET in line
    ]
    event_rows = [
        line
        for line in sim_log.splitlines()
        if "kind=EVENT boundary=buf_ack_phase_target" in line and EXACT_TARGET in line
    ]
    summary_count = None
    if summary_rows:
        m = re.search(r"(?:^| )count=(\d+)(?: |$)", summary_rows[-1])
        summary_count = int(m.group(1)) if m else None
    projection_proof = {
        "sim_log_equals_source_bound_log": sim_log_bytes == source_bound_bytes,
        "receipt_says_sim_log_equals_causal_log": source_bound_receipt.get(
            "sim_log_equals_causal_log"
        )
        is True,
        "original_sim_log_bytes": source_bound_receipt.get("original_sim_log_bytes"),
        "bounded_sim_log_bytes": len(sim_log_bytes),
        "original_sim_log_sha256": source_bound_receipt.get("original_sim_log_sha256"),
        "bounded_sim_log_sha256": sha(sim_log_bytes),
        "exact_target_enabled_count": len(enabled_rows),
        "exact_target_summary_count": len(summary_rows),
        "exact_target_internal_trigger_count": summary_count,
        "exact_target_returned_event_count": len(event_rows),
    }
    if not (
        projection_proof["sim_log_equals_source_bound_log"]
        and projection_proof["receipt_says_sim_log_equals_causal_log"]
        and summary_count == 13
        and len(event_rows) == 0
    ):
        structural_errors.append("expected_projection_loss_witness_not_observed")

    plugin_path = args.source_tree / "package_tools/node0004_v81_post_sim_plugin.py"
    collector_path = args.source_tree / "package_tools/node0004_hang_localization_runtime_v7.py"
    plugin_text = plugin_path.read_text(encoding="utf-8")
    collector_text = collector_path.read_text(encoding="utf-8")
    static_mechanism = {
        "plugin_sha256": sha(plugin_path.read_bytes()),
        "collector_sha256": sha(collector_path.read_bytes()),
        "frozen_collector_precedes_phase_parser": plugin_text.find("subprocess.run([sys.executable,str(old)")
        < plugin_text.find("buffer_ack_phase_parser.py"),
        "collector_filters_event_kind": 'core_kinds = {"ENABLED", "SUMMARY", "CLASS", "TRIGGER", "STALL"}'
        in collector_text
        and 'ring_kinds = {"RING_PROGRESS", "RING_STATE", "RING_POST"}' in collector_text,
        "collector_overwrites_sim_log": "sim_log.write_bytes(compact)" in collector_text,
    }
    if not all(static_mechanism.values()):
        structural_errors.append("package_local_static_escape_mechanism_not_closed")

    natural = bool(sim_exit.get("natural_terminal_observed"))
    formal = gate.get("formal_readback", {})
    present = int(formal.get("present", 0) or 0)
    missing = int(formal.get("missing", 320) or 320)
    mismatch = int(formal.get("mismatch", 0) or 0)
    e3 = compile_exit == 0 and run_exit == 0 and signal == "NONE" and natural
    e4 = e3 and present == 320 and missing == 0 and mismatch == 0
    e5 = e4 and bool(gate.get("e5_pass", False))

    report = {
        "schema": "conv-node0004-v81-formal-return-analysis-v1",
        "analysis_valid": not structural_errors,
        "structural_errors": structural_errors,
        "RETURN_ANALYSIS": {
            "return": {
                "path": str(args.return_zip),
                "bytes": len(rdata),
                "sha256": sha(rdata),
            },
            "source": {
                "path": str(args.source_zip),
                "bytes": len(sdata),
                "sha256": sha(sdata),
            },
            "execution_id": EXECUTION,
            "transport_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY",
            "identity_checks": identity_checks,
            "crc_root_path_exact_set_allowlist_per_file": not structural_errors,
            "compile_exit": compile_exit,
            "run_exit": run_exit,
            "signal": signal,
            "natural_terminal": natural,
            "formal_d": {"present": present, "missing": missing, "mismatch": mismatch},
            "E3": e3,
            "E4": e4,
            "E5": e5,
            "core_disposition": status.get("disposition"),
            "required_missing_entries": required_missing,
            "required_plugin_failures": required_failures,
            "expected_package_local_failure_shape": expected_failure_shape,
            "joint_gate_pass": False,
            "reported_phase_decision": phase.get("decision"),
            "equation_decision": equation.get("decision"),
        },
        "LAST_PROVEN_GOOD": "EXACT_SLICE13_GROUP1_MSE4_PHASE_TRIGGER_CONDITION_OCCURRED_13_TIMES",
        "FIRST_DIVERGENCE": "EXACT_TARGET_PHASE_EVENT_TO_POST_SIM_PHASE_PARSER_INPUT_PRESERVATION",
        "HANG_ROOT_CAUSE": {
            "status": "PACKAGE_LOCAL_POST_SIM_COLLECTOR_ORDER_AND_LOG_MUTATION_DEFECT",
            "mechanism": (
                "node0004_v81_post_sim_plugin invokes the frozen v79 collector before the exact phase parser. "
                "The collector retains only ENABLED/SUMMARY/CLASS/TRIGGER/STALL and RING_* records and then "
                "overwrites c0/sim.log. The phase observer's EVENT records are therefore removed before the "
                "phase parser reads the same path."
            ),
            "projection_witness": projection_proof,
            "static_package_source_witness": static_mechanism,
            "functional_root_cause": "UNRESOLVED_BECAUSE_REQUIRED_PHASE_VALUES_WERE_DROPPED_PACKAGE_SIDE",
            "not_rtl_or_config_evidence": True,
        },
        "PROGRESS_THIS_ROUND": {
            "closed_since_v80": [
                "WRONG_INSTANCE_PHASE_BINDING",
                "EXACT_TARGET_OBSERVER_COMPILE_RUNTIME_ENABLE",
                "EXACT_TARGET_TRIGGER_ABSENCE_HYPOTHESIS",
            ],
            "first_proven": [
                "EXACT_SLICE13_GROUP1_MSE4_TRIGGER_CONDITION_OCCURRED_13_TIMES",
                "PHASE_EVENT_LOSS_IS_PACKAGE_LOCAL_POST_SIM_ORDERING",
            ],
            "target_functional_boundary_advanced": True,
            "natural_or_formal_completion_advanced": False,
            "remaining_root_scope": (
                "Exact target ACTIVE/INACTIVE/POSTNBA/HALF/NEXT operand/tag/gotten values remain unknown; "
                "delta-settle, stale consumer ACK and persistent compiled-equation mismatch remain live."
            ),
        },
        "BLOCKER_DELTA": {
            "closed": ["B_CONV_NODE0004_V80_PHASE_PARSER_WRONG_INSTANCE_SCOPE"],
            "opened": ["B_CONV_NODE0004_V81_PHASE_EVENT_DROPPED_BY_POST_SIM_PROJECTION_ORDER"],
            "retained": [
                "B_CONV_NODE0004_BUFFER_ACK_ACTIVE_VS_SETTLED_CONSUMER_PHASE_UNRESOLVED",
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
            "invalidated_not_revived": [
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ],
        },
        "PACKAGE_NEXT": {
            "required": True,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "minimal_fix": (
                "Parse/persist exact phase EVENT records from immutable raw sim output before the frozen "
                "source-bound collector overwrites sim.log, then run the existing collector; preserve the "
                "same exact target, workload, config, numeric, golden, timeout and RTL."
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
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not structural_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
