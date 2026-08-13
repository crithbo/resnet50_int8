"""Receipt-bound analysis of the QAdd node0007 v52 queue-flow return.

This script is deliberately read-only with respect to the source/return ZIPs and
does not run the DUT or recompute numeric, workload, configuration, or golden
assets.
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
TARGET_THREAD = "019fbec2-fe93-7e03-9314-cff6f222f33d"
NAME = "r5_qadd_n7_tailround_queueflow_v52"
RETURN_ROOT = NAME + "_return"
RETURN_BYTES = 450_246
RETURN_SHA = "595f31705a463f83c6b3af1a0920d2dcca8a3d694050d32b4bc865103dc20493"
EXECUTION = "r1786363786427884298_586990"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{NAME}.zip"
SOURCE_BYTES = 70_648_125
SOURCE_SHA = "7ed0e6e84d32900b015f70091b7b8bbefae074a63f019d75026f8b25bf9f52d0"
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
            if info.is_dir():
                continue
            relative = info.filename[len(prefix):]
            files[relative] = archive.read(info)
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


def fields(body: str) -> dict[str, int]:
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
            rows.append({"line": line_no, "time_ps": int(match.group(1)), **fields(match.group(3))})
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
        errors.append("returned source manifest does not byte-bind frozen v52")

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
    simlog = returned["runs/sim.log"].decode(errors="replace")
    starts = events(observer, "EXEC_START")
    finishes = events(observer, "COMP_FINISH")
    flow = events(observer, "TAILROUND_FLOW")
    state = events(observer, "Q52_STATE")
    monotonic = all(all(after.get(key, 0) >= before.get(key, 0) for key in QUALIFIED) for before, after in zip(flow, flow[1:]))
    frozen_windows = sum(all(after.get(key, 0) == before.get(key, 0) for key in QUALIFIED) for before, after in zip(flow, flow[1:]))
    last_flow = {key: flow[-1].get(key, 0) for key in QUALIFIED} if flow else {}
    last_state = state[-1] if state else {}
    detail_instances = canonical.get("detail_instances", [])
    expected_execution = (
        compile_exit == 0 and simulation_exit == 124 and signal == "NONE" and canonical_exit == 1
        and len(starts) == 1 and len(finishes) == 0 and len(flow) == 16
        and frozen_windows >= 15 and monotonic
    )
    if not expected_execution:
        errors.append("execution/qualified stall-window evidence differs from formal v52 return")
    if detail_instances != ["tb_NDP_Top_new_phy", "tb_NDP_Top_new_phy.unnamed$$_47"]:
        errors.append("returned canonical instance-scope evidence differs")

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
    report = {
        "schema": "qlinearadd-node0007-tailround-queueflow-v52-return-analysis-v1",
        "status": "RETURN_ANALYSIS_COMPLETE_BUF2MSE_READ_READY_FIRST_DIVERGENCE",
        "analysis_valid": not errors,
        "errors": errors,
        "analysis_owner_thread": OWNER,
        "return_target_thread": TARGET_THREAD,
        "numeric_analysis_repeated": False,
        "workload_config_golden_repeated": False,
        "dut_rerun": False,
        "control_receipts": controls,
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
            "actual_simulator_argv": returned["evidence/actual_simulator_argv.txt"].decode(errors="replace").strip(),
            "observer_binding": returned["evidence/observer_binding.txt"].decode(errors="replace").strip(),
            "feature_receipt": returned["evidence/feature_receipt.txt"].decode(errors="replace").strip(),
            "runtime_layout": runtime_layout,
            "fixed_publication": fixed_publish,
            "ndp_root_exact_set_unchanged": root_pre.get("direct_child_set_sha256") == root_post.get("direct_child_set_sha256"),
        },
        "RETURN_ANALYSIS": {
            "outcome": "LONG_RUNNING_HANG_AT_OP_TAIL_ROUND_BUF2MSE_READ_READY_LOW",
            "compile_exit": compile_exit,
            "simulation_exit": simulation_exit,
            "signal": signal,
            "canonical_exit": canonical_exit,
            "returned_canonical_decision": canonical.get("decision"),
            "canonical_package_defect": "Q52_EVENT uses %m from two procedural scopes, producing a false multiple-instance failure",
            "raw_qualified_evidence_consumable": True,
            "natural_terminal": False,
            "host_duration_seconds": duration_seconds,
            "host_duration_hours": duration_seconds / 3600,
            "ordered_stage_starts": len(starts),
            "ordered_stage_finishes": len(finishes),
            "flow_samples": len(flow),
            "qualified_frozen_windows": frozen_windows,
            "qualified_monotonic": monotonic,
            "last_flow": last_flow,
            "last_state": last_state,
            "candidate_matrix": canonical.get("candidate_matrix", {}),
        },
        "LAST_PROVEN_GOOD": "OP_TAIL_ROUND_BUFFER_AG_PAIR_DEQUEUE_AND_RD_BUFFER_AG_VALID_QUEUE_FILL",
        "FIRST_DIVERGENCE": "RD_BUFFER_AG_VALID_REQUEST_WITH_WR_DATA_CHANNEL_READY_BUT_BUF2MSE_RREQ_READY_LOW",
        "HANG_ROOT_CAUSE": {
            "status": "FIRST_BLOCKING_EQUATION_PROVEN_LEAF_SOURCE_NOT_YET_UNIQUE",
            "equation": "buf_ag_ob_rd_en = buf2mse_rreq_ready && wr_data_chl_ready",
            "dynamic_snapshot": {
                "rdag_count": last_state.get("rdag_count"), "rdag_full": last_state.get("rdag_full"),
                "rreq_valid": last_state.get("rreq_valid"), "buf2mse_rreq_ready": last_state.get("buf_ready"),
                "wr_data_chl_ready": last_state.get("wr_ready"), "rdag_deq": last_flow.get("rdag_deq"),
                "rdag_rreq": last_flow.get("rdag_rreq"),
            },
            "remaining_candidates": [
                "mse_wreq_pingpong_sel chooses Buffer5 port whose mrm2se_req_ready[5] is low",
                "Buffer5 per-bank valid_buf bits do not cover the selected ROW/COL request mask",
                "Buffer5 request address/mask selects a hole or stale row",
                "Buffer5 read barrier/ownership suppresses selected read readiness",
            ],
            "excluded": ["Buffer_AG pair/tag mismatch", "RDAG empty", "WR_Data_Channel backpressure", "configuration or RTL root cause beyond the observed ready leaf"],
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
            "closed": ["B_QADD_TAILROUND_BUFFER_AG_PAIR_DEQUEUE_UNKNOWN"],
            "opened": ["B_QADD_TAILROUND_BUFFER5_SELECTED_READ_READY_LOW"],
            "package_defect": "v52 canonical instance ownership falsely split by procedural-scope %m",
            "refined_to": "RD_Buffer_AG full valid request blocked specifically by buf2mse_rreq_ready=0",
        },
        "SUCCESSOR_PROPOSAL": {
            "required": True,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "fresh_identity": "r5_qadd_n7_tailround_bufready_v53",
            "first_fresh_after_change": False,
            "prior_first_fresh_pass_sha256": "ed8e31a08cb76f0b8994ebaf29247dd1f0b603f0861acf710afcbb5219e4e976",
            "frozen": "isolated workload, COL4/stride2 config, numeric/W3/qparams/tail/golden/2h timeout/functional RTL",
            "changed_surface": "stable observer instance identity plus selected Buffer5/pingpong/read-ready/valid-bank/mask/address/barrier qualified chain",
        },
        "RULE_CONFIRMATION": {
            "status": "CONFIRMED",
            "statement": "Current return integrity, hang-first, qualified-progress, formal-D conjunction, diagnostic stimulus boundary, continuous-closure, and changed-surface audit rules cover this adjudication.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"analysis_valid": not errors, "errors": errors, "output": str(args.output), "bytes": args.output.stat().st_size, "sha256": sha(args.output)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
