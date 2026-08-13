"""Formal, receipt-bound analysis of the QAdd node0007 v54 return.

The analyzer is read-only with respect to the return/source ZIPs.  It does not
run the DUT or recompute numeric, workload, configuration, or golden assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OWNER = "019fa2c0-b647-7a91-93bf-d21a173487e3"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"
NAME = "r5_qadd_n7_tailround_bufready_v54"
RETURN_ROOT = NAME + "_return"
RETURN_BYTES = 451_585
RETURN_SHA = "6a48715d6aed813d5c028b62f5a0386a2c8e2b906996175650d728c57b0d1594"
EXECUTION = "r1786374087773700902_678285"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{NAME}.zip"
SOURCE_BYTES = 70_649_173
SOURCE_SHA = "e0b4cc00cbd29716c3399b5fcb95265ae10a1d2d67765466a023312b8cde3f26"
RULES = {
    "agent": ROOT / ".agents/agent.md",
    "plan_mutable": ROOT / ".agents/plan.md",
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
    "hardware_sim_readme": ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
}
RTL = {
    "buffer": ROOT / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "mrm": ROOT / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Memory_Req_Manager.sv",
    "cluster": ROOT / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster.sv",
}
QUALIFIED = (
    "mse0_addr", "mse0_req", "mse0_meta", "mse0_consume", "mse0_buf",
    "ga_in", "ga_out", "buf5_wr", "buf5_rd", "bag_enq", "bag_deq",
    "rdag_enq", "rdag_deq", "rdag_rreq", "wr_req", "wr_prepared",
    "wr_ob_enq0", "wr_ob_enq1", "wr_ob_deq0", "wr_ob_deq1",
    "mse4_req0", "mse4_req1", "mse4_wdata0", "mse4_wdata1",
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def inventory(path: Path) -> tuple[str, dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    seen: set[str] = set()
    duplicates: list[str] = []
    unsafe: list[str] = []
    symlinks: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad_crc = archive.testzip()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if info.filename in seen:
                duplicates.append(info.filename)
            seen.add(info.filename)
            if not pure.parts:
                unsafe.append(info.filename)
                continue
            roots.add(pure.parts[0])
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                unsafe.append(info.filename)
            if stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF):
                symlinks.append(info.filename)
        if len(roots) != 1:
            raise ValueError(f"single ZIP root required: {sorted(roots)}")
        root = next(iter(roots))
        prefix = root + "/"
        for info in archive.infolist():
            if not info.is_dir():
                files[info.filename[len(prefix):]] = archive.read(info)
    return root, files, {
        "crc_valid": bad_crc is None,
        "root": root,
        "entry_count": len(files),
        "duplicates": duplicates,
        "unsafe_paths": unsafe,
        "symlinks": symlinks,
    }


def obj(files: dict[str, bytes], name: str) -> dict[str, Any]:
    value = json.loads(files[name])
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {name}")
    return value


def parse_fields(body: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for key, value in re.findall(r"(\w+)=(0x[0-9a-fA-F]+|\d+)", body):
        result[key] = int(value, 16) if value.lower().startswith("0x") else int(value)
    return result


def events(text: str, event: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pattern = re.compile(r"^(\d+)\s+\|\s+([A-Z0-9_]+)\s+\|\s*(.*)$")
    for line_no, line in enumerate(text.splitlines(), 1):
        match = pattern.match(line)
        if match and match.group(2) == event:
            rows.append({"line": line_no, "time_ps": int(match.group(1)), **parse_fields(match.group(3))})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    return_path = args.return_zip.resolve()
    if return_path.stat().st_size != RETURN_BYTES or sha(return_path) != RETURN_SHA:
        errors.append("formal return bytes/SHA differ")
    if SOURCE.stat().st_size != SOURCE_BYTES or sha(SOURCE) != SOURCE_SHA:
        errors.append("frozen source bytes/SHA differ")

    return_root, returned, return_structure = inventory(return_path)
    source_root, source, source_structure = inventory(SOURCE)
    if return_root != RETURN_ROOT or source_root != NAME:
        errors.append("return/source root identity differs")
    for label, structure in (("return", return_structure), ("source", source_structure)):
        if not structure["crc_valid"] or structure["duplicates"] or structure["unsafe_paths"] or structure["symlinks"]:
            errors.append(f"{label} ZIP structural gate failed")

    rmanifest = obj(returned, "RETURN_MANIFEST.json")
    smanifest = obj(source, "TEST_PACKAGE_MANIFEST.json")
    returned_smanifest = obj(returned, "evidence/PACKAGE_MANIFEST.json")
    declared = {row["path"]: row for row in rmanifest.get("files", [])}
    actual = set(returned) - {"RETURN_MANIFEST.json"}
    allowlist = {row["target_path"]: row for row in smanifest.get("return_allowlist", [])}
    required_missing = set(rmanifest.get("required_missing", []))
    per_file_errors: list[str] = []
    for name, row in declared.items():
        if name not in returned:
            per_file_errors.append(f"missing:{name}")
        elif len(returned[name]) != int(row["size_bytes"]):
            per_file_errors.append(f"size:{name}")
        elif sha_bytes(returned[name]) != row["sha256"]:
            per_file_errors.append(f"sha:{name}")
        elif name not in allowlist or len(returned[name]) > int(allowlist[name]["max_bytes"]):
            per_file_errors.append(f"allowlist:{name}")
    exact_set = actual == set(declared) == (set(allowlist) - required_missing)
    source_binding = (
        returned["evidence/PACKAGE_MANIFEST.json"] == source["TEST_PACKAGE_MANIFEST.json"]
        and returned_smanifest == smanifest
        and rmanifest.get("install_name") == smanifest.get("install_name") == NAME
    )
    if not exact_set or per_file_errors:
        errors.append("RETURN_MANIFEST exact-set/per-file/allowlist gate failed")
    if not source_binding:
        errors.append("returned source manifest does not byte-bind frozen v54")

    compile_exit = int(returned["evidence/compile_exit_status.txt"].decode().strip())
    simulation_exit = int(returned["evidence/simulation_exit_status.txt"].decode().strip())
    signal = returned["evidence/signal_status.txt"].decode().strip()
    canonical_exit = int(returned["evidence/canonical_decision_exit_status.txt"].decode().strip())
    canonical = obj(returned, "evidence/CANONICAL_PROGRESS_DECISION.json")
    result_gate = obj(returned, "evidence/SERVER_RESULT_GATE.json")
    package_preflight = obj(returned, "evidence/package_preflight.json")
    installed_preflight = obj(returned, "evidence/installed_preflight.json")
    runtime_layout = obj(returned, "evidence/runtime_layout_receipt.json")
    fixed_publish = obj(returned, "evidence/fixed_result_preflight.json")
    root_pre = obj(returned, "evidence/ndp_root_toplevel_pre.json")
    root_post = obj(returned, "evidence/ndp_root_toplevel_post.json")
    timing = dict(line.split("=", 1) for line in returned["evidence/host_timing.txt"].decode().splitlines() if "=" in line)
    duration_seconds = (int(timing["run_end_ns"]) - int(timing["run_start_ns"])) / 1e9
    observer = returned["runs/return_observer.log"].decode(errors="replace")
    starts = events(observer, "EXEC_START")
    finishes = events(observer, "COMP_FINISH")
    flow = events(observer, "TAILROUND_FLOW")
    states = events(observer, "Q53_STATE")
    q53_events = [line for line in observer.splitlines() if " | Q53_EVENT | " in line]
    monotonic = all(all(after.get(key, 0) >= before.get(key, 0) for key in QUALIFIED) for before, after in zip(flow, flow[1:]))
    frozen_windows = sum(all(after.get(key, 0) == before.get(key, 0) for key in QUALIFIED) for before, after in zip(flow, flow[1:]))
    last_flow = {key: flow[-1].get(key, 0) for key in QUALIFIED} if flow else {}
    last_state = states[-1] if states else {}

    request_mask = last_state.get("req_strb")
    valid_mask = last_state.get("valid_at_req")
    full_mask = (1 << 32) - 1
    mask_proof = {
        "request_mask_hex": f"0x{request_mask:08x}" if request_mask is not None else None,
        "valid_at_request_hex": f"0x{valid_mask:08x}" if valid_mask is not None else None,
        "intersection_hex": f"0x{(request_mask & valid_mask):08x}" if request_mask is not None and valid_mask is not None else None,
        "union_hex": f"0x{(request_mask | valid_mask):08x}" if request_mask is not None and valid_mask is not None else None,
        "disjoint": request_mask is not None and valid_mask is not None and (request_mask & valid_mask) == 0,
        "complementary_full_row": request_mask is not None and valid_mask is not None and (request_mask | valid_mask) == full_mask,
        "all_banks_failed_ready": last_state.get("bank_ready") == 0,
    }
    expected_execution = (
        compile_exit == 0 and simulation_exit == 124 and signal == "NONE" and canonical_exit == 1
        and len(starts) == 1 and len(finishes) == 0 and len(states) >= 20
        and frozen_windows >= 20 and monotonic
        and mask_proof["disjoint"] and mask_proof["complementary_full_row"]
        and last_flow.get("buf5_wr") == 1 and last_flow.get("buf5_rd") == 0
    )
    if not expected_execution:
        errors.append("execution/qualified Buffer5 lane-phase evidence differs from formal v54 return")

    formal = {
        "expected": result_gate.get("expected_readback_count"),
        "present": result_gate.get("observed_readback_count"),
        "missing": result_gate.get("missing_count"),
        "invalid": result_gate.get("invalid_count"),
        "mismatch_bytes": result_gate.get("mismatch_byte_count"),
        "mismatch_evaluable": result_gate.get("mismatch_evaluable"),
        "all_terms_true": result_gate.get("result_gate_conjunction", {}).get("all_terms_true"),
    }
    if formal != {"expected": 28, "present": 0, "missing": 28, "invalid": 0, "mismatch_bytes": 0, "mismatch_evaluable": False, "all_terms_true": False}:
        errors.append("formal D/result conjunction differs from expected incomplete return")

    controls = {
        key: {
            "path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
            "sha256": sha(path), "mutable_provenance_only": key == "plan_mutable",
        }
        for key, path in RULES.items()
    }
    rtl_receipts = {
        key: {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}
        for key, path in RTL.items()
    }
    feature = returned["evidence/feature_receipt.txt"].decode(errors="replace").strip()
    observer_binding = returned["evidence/observer_binding.txt"].decode(errors="replace").strip()
    argv = returned["evidence/actual_simulator_argv.txt"].decode(errors="replace").strip()
    feature_four_way = all(token in (feature + "\n" + observer_binding + "\n" + argv) for token in (
        "QADD_TAILROUND_BUFREADY", "qlinearadd_node0007_tailround_bufready_v53.svh", "NATIVE_RETURN_OBSERVER_ENABLE"
    )) and "QADD_TAILROUND_BUFREADY_V53" in observer
    if not feature_four_way:
        errors.append("observer source/macro/argv/time0 feature binding differs")

    report = {
        "schema": "qlinearadd-node0007-tailround-bufready-v54-return-analysis-v1",
        "status": "RETURN_ANALYSIS_COMPLETE_SUCCESSOR_HELD_WAIT_NEXT_FRESH_RULE_SYNC",
        "analysis_valid": not errors,
        "errors": errors,
        "analysis_owner_thread": OWNER,
        "return_target_thread": TARGET,
        "numeric_analysis_repeated": False,
        "workload_config_golden_repeated": False,
        "dut_rerun": False,
        "control_receipts": controls,
        "rtl_consumer_receipts": rtl_receipts,
        "transport_and_identity": {
            "external_sidecar": "NOT_REQUIRED_USER_ATTESTED_TRANSPORT",
            "return": {"path": str(return_path), "bytes": return_path.stat().st_size, "sha256": sha(return_path), "execution": EXECUTION},
            "return_structure": return_structure,
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "bytes": SOURCE.stat().st_size, "sha256": sha(SOURCE), "structure": source_structure},
            "manifest_exact_set": exact_set,
            "manifest_per_file_errors": per_file_errors,
            "source_manifest_byte_bound": source_binding,
            "package_preflight": package_preflight,
            "installed_preflight": installed_preflight,
            "actual_compile_argv": returned["evidence/actual_compile_argv.txt"].decode(errors="replace").strip(),
            "actual_simulator_argv": argv,
            "observer_binding": observer_binding,
            "feature_receipt": feature,
            "feature_four_way_bound": feature_four_way,
            "runtime_layout": runtime_layout,
            "fixed_publication": fixed_publish,
            "ndp_root_exact_set_unchanged": root_pre.get("direct_child_set_sha256") == root_post.get("direct_child_set_sha256"),
            "core_plugin_scope": "V54_RETURN_SCHEMA_HAS_NO_SEPARATE_POST_SIM_CORE_OR_PLUGIN_RECEIPT; compile0 and actual simulator execution are proven, but no additional plugin claim is made",
        },
        "RETURN_ANALYSIS": {
            "outcome": "LONG_RUNNING_HANG_AT_OP_TAIL_ROUND_BUFFER5_SELECTED_LANE_VALIDITY",
            "compile_exit": compile_exit,
            "simulation_exit": simulation_exit,
            "signal": signal,
            "canonical_exit": canonical_exit,
            "returned_canonical_decision": canonical.get("decision"),
            "raw_qualified_evidence_consumable": True,
            "natural_terminal": False,
            "host_duration_seconds": duration_seconds,
            "host_duration_hours": duration_seconds / 3600,
            "ordered_stage_starts": len(starts),
            "ordered_stage_finishes": len(finishes),
            "flow_samples": len(flow),
            "state_samples": len(states),
            "qualified_frozen_windows": frozen_windows,
            "qualified_monotonic": monotonic,
            "last_flow": last_flow,
            "last_state": last_state,
            "q53_qualified_event_count": len(q53_events),
        },
        "LAST_PROVEN_GOOD": "OP_TAIL_ROUND_BUFFER5_FIRST_ACCEPTED_WRITE_AND_MSE4_ROW0_REQUEST_DECODE",
        "FIRST_DIVERGENCE": "BUFFER5_ROW0_REQUEST_MASK_33333333_DISJOINT_FROM_VALID_MASK_CCCCCCCC",
        "HANG_ROOT_CAUSE": {
            "status": "UNIQUE_TEMPORAL_LANE_PHASE_SUPPLY_CONSUMER_MISMATCH_PROVEN_FIX_LEAF_REQUIRES_CHANGED_CONFIG_MICROTRACE",
            "rtl_equations": [
                "buf2mrm_rreq_bank_ready[BANK_IDX] = &(valid_buf[BANK_IDX][req_addr] | ~req_strb[BANK_IDX])",
                "buf2mrm_rreq_ready = &(~mrm2buf_rd_en | buf2mrm_rreq_bank_ready)",
                "mrm2buf_clear = req_valid & buf2mrm_req_ready & ~req_rw",
            ],
            "mask_proof": mask_proof,
            "dynamic_snapshot": {
                "pingpong": last_state.get("pingpong"), "selected_ready": last_state.get("selected_ready"),
                "mrm_ready5": last_state.get("mrm_ready5"), "req_valid": last_state.get("req_valid"),
                "req_rw": last_state.get("req_rw"), "req_addr": last_state.get("req_addr"),
                "rd_en": last_state.get("rd_en"), "bank_ready": last_state.get("bank_ready"),
                "write_accepts": last_flow.get("buf5_wr"), "read_accepts": last_flow.get("buf5_rd"),
                "valid_clears": canonical.get("candidate_matrix", {}).get("C_BUFFER5_WRITE_CLEAR_ORDER", {}).get("valid_clears"),
            },
            "excluded_candidates": [
                "pingpong selection ambiguity", "request decode absent", "wrong Buffer5 row", "read barrier asserted",
                "held level counted as progress", "WR_Data_Channel-only backpressure",
            ],
            "fix_surface_frozen": [
                "buffer_loop_configs.GROUP2.COL_LC start/end/stride temporal phase",
                "stream_engine.stream2 Buffer5 column/spatial mapping only if the changed microtrace proves ownership",
            ],
            "no_config_leaf_materialized_yet": True,
        },
        "PROGRESS_VS_V52": {
            "functional_transaction_progress_after_v52_lpg": "ZERO",
            "diagnostic_information_gain": "NONZERO_UNIQUE_BOUNDARY",
            "closed": ["selected pingpong port ambiguity", "request-decode ambiguity", "row/bank/lane-validity ambiguity", "read-barrier candidate"],
            "advanced_boundary": "from generic buf2mse_rreq_ready low to exact disjoint requested-vs-valid byte-lane masks in Buffer5 row0",
        },
        "formal_D": formal,
        "SERVER_RESULT_GATE": {"pass": False, "reason": "compile=0 but simulation=124, natural terminal absent, and 28/28 D missing; mismatch=0 is unevaluable"},
        "evidence_levels": {"E3": False, "E4": False, "E5": False},
        "claim_boundary": {
            "scope": "isolated op_tail_round only",
            "stimulus": "DIAGNOSTIC_STIMULUS_NOT_PRODUCER_EVIDENCE",
            "host_precomputed_internal_tensor": True,
            "producer_evidence_claimed": False,
            "full_chain_claimed": False,
        },
        "BLOCKER_DELTA": {
            "closed": ["B_QADD_TAILROUND_BUFFER5_SELECTED_READ_READY_CAUSE_AMBIGUOUS"],
            "opened": ["B_QADD_TAILROUND_BUFFER5_TEMPORAL_LANE_PHASE_MISMATCH_3333_VS_CCCC"],
            "refined_to": "selected row0 request demands exactly the complementary invalid lanes for at least 20 complete qualified stall windows",
        },
        "SUCCESSOR": {
            "required": True,
            "release": "HOLD_WAIT_NEXT_FRESH_EXACT_RULE_TOOL_SCHEMA_SYNC",
            "classification": "CONFIG_CORRECTION_CANDIDATE_PENDING_CHANGED_BOUNDARY_MICROTRACE",
            "frozen": "isolated workload, numeric/W3/qparams/tail/golden/2h timeout/functional RTL",
            "publication_forbidden_until_current_sync": True,
        },
        "RULE_DELTA_PROPOSAL": {
            "status": "PROPOSED_NON_SYNONYMOUS",
            "statement": "A static no-gap/no-overlap union of Buffer ROW/COL byte windows is insufficient when producer writes and MSE reads interleave. The transaction-supply proof must preserve accepted-event order and prove that each consumer request is a subset of the valid byte mask visible before that request; residual valid lanes must not block the next producer write.",
            "counterexample": "v54 accepted one Buffer5 write, then stabilized at requested=0x33333333, valid=0xcccccccc, intersection=0, read_accept=0 for >=20 windows despite the old static union being 32/32B.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"analysis_valid": not errors, "errors": errors, "output": str(args.output), "bytes": args.output.stat().st_size, "sha256": sha(args.output)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
