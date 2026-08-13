"""Return-bound analysis of QLinearAdd node0007 isolated tail_round v51.

This tool validates only the frozen source/return receipts and recorded dynamic
evidence.  It never runs the DUT and never recomputes numeric, workload,
configuration, or golden assets.
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
NAME = "r5_qadd_n7_tailround_split_clean_v51"
RETURN_ROOT = NAME + "_return"
RETURN_BYTES = 448_574
RETURN_SHA = "6cc79a5aede9a8ebbed01f3cc2a03596e6d3b320f4661ab3fb68abf4ee0f6fb7"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{NAME}.zip"
SOURCE_BYTES = 70_643_824
SOURCE_SHA = "cf499102675dda4501e4e0c2e9cde1142985b3aca6b94a46edf7afb45f668141"
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
            if not info.filename.startswith(prefix):
                unsafe.append(info.filename)
                continue
            relative = info.filename[len(prefix):]
            if relative in files:
                duplicates.append(relative)
                continue
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
        result[key] = int(value, 16) if value.lower().startswith("0x") else int(value, 10)
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
        errors.append("returned source manifest does not byte-bind frozen v51")

    compile_exit = int(returned["evidence/compile_exit_status.txt"].decode().strip())
    simulation_exit = int(returned["evidence/simulation_exit_status.txt"].decode().strip())
    signal = returned["evidence/signal_status.txt"].decode().strip()
    canonical_exit = int(returned["evidence/canonical_decision_exit_status.txt"].decode().strip())
    timing = dict(
        line.split("=", 1)
        for line in returned["evidence/host_timing.txt"].decode().splitlines()
        if "=" in line
    )
    duration_seconds = (int(timing["run_end_ns"]) - int(timing["run_start_ns"])) / 1e9
    canonical = obj(returned, "evidence/CANONICAL_PROGRESS_DECISION.json")
    result_gate = obj(returned, "evidence/SERVER_RESULT_GATE.json")
    package_preflight = obj(returned, "evidence/package_preflight.json")
    installed_preflight = obj(returned, "evidence/installed_preflight.json")
    runtime_layout = obj(returned, "evidence/runtime_layout_receipt.json")
    fixed_publish = obj(returned, "evidence/fixed_result_preflight.json")
    root_pre = obj(returned, "evidence/ndp_root_toplevel_pre.json")
    root_post = obj(returned, "evidence/ndp_root_toplevel_post.json")
    observer = returned["runs/return_observer.log"].decode(errors="replace")
    simlog = returned["runs/sim.log"].decode(errors="replace")

    starts = events(observer, "EXEC_START")
    finishes = events(observer, "COMP_FINISH")
    flow = events(observer, "TAILROUND_FLOW")
    state = events(observer, "TAILROUND_STATE")
    sg = events(observer, "SG_COUNTS")
    monotonic = all(
        all(after.get(key, 0) >= before.get(key, 0) for key in QUALIFIED)
        for before, after in zip(flow, flow[1:])
    )
    frozen_windows = sum(
        all(after.get(key, 0) == before.get(key, 0) for key in QUALIFIED)
        for before, after in zip(flow, flow[1:])
    )
    last_flow = {key: flow[-1].get(key, 0) for key in QUALIFIED} if flow else {}
    last_state = state[-1] if state else {}
    natural = (
        compile_exit == 0
        and simulation_exit == 0
        and signal == "NONE"
        and len(starts) == 1
        and len(finishes) == 1
        and "Simulation completed successfully!" in simlog
        and result_gate.get("result_gate_conjunction", {}).get("all_terms_true") is True
    )
    expected_execution = (
        compile_exit == 0
        and simulation_exit == 124
        and signal == "NONE"
        and canonical_exit == 0
        and len(starts) == 1
        and len(finishes) == 0
        and len(flow) >= 17
        and frozen_windows >= 16
        and monotonic
    )
    if not expected_execution:
        errors.append("execution/qualified stall-window evidence differs from formal v51 return")

    formal = {
        "expected": result_gate.get("expected_readback_count"),
        "present": result_gate.get("observed_readback_count"),
        "missing": result_gate.get("missing_count"),
        "invalid": result_gate.get("invalid_count"),
        "mismatch_bytes": result_gate.get("mismatch_byte_count"),
        "mismatch_evaluable": result_gate.get("mismatch_evaluable"),
        "all_terms_true": result_gate.get("result_gate_conjunction", {}).get("all_terms_true"),
    }
    controls = {
        key: {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha(path),
            "mutable_provenance_only": key == "plan_mutable",
        }
        for key, path in RULES.items()
    }
    report = {
        "schema": "qlinearadd-node0007-tailround-split-clean-v51-return-analysis-v1",
        "status": "RETURN_ANALYSIS_COMPLETE_TAILROUND_QUEUEFLOW_NOT_UNIQUE",
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
            "return": {
                "path": str(return_path), "bytes": return_path.stat().st_size,
                "sha256": sha(return_path), "execution": "r1786345773466170577_479267",
                "attempt": "a479267",
            },
            "return_structure": return_structure,
            "source": {
                "path": SOURCE.relative_to(ROOT).as_posix(), "bytes": SOURCE.stat().st_size,
                "sha256": sha(SOURCE), "structure": source_structure,
            },
            "manifest_exact_set": exact_set,
            "manifest_per_file_errors": per_file_errors,
            "source_manifest_byte_bound": source_binding,
            "package_preflight": package_preflight,
            "installed_preflight": installed_preflight,
            "actual_compile_input": returned["evidence/actual_compile_argv.txt"].decode(errors="replace").strip(),
            "actual_simulator_input": returned["evidence/actual_simulator_argv.txt"].decode(errors="replace").strip(),
            "observer_binding": returned["evidence/observer_binding.txt"].decode(errors="replace").strip(),
            "feature_receipt": returned["evidence/feature_receipt.txt"].decode(errors="replace").strip(),
            "runtime_layout": runtime_layout,
            "fixed_publication": fixed_publish,
            "ndp_root_exact_set_unchanged": root_pre.get("direct_child_set_sha256") == root_post.get("direct_child_set_sha256"),
        },
        "RETURN_ANALYSIS": {
            "outcome": "LONG_RUNNING_HANG_AT_OP_TAIL_ROUND_AFTER_FIRST_16B_WDATA",
            "compile_exit": compile_exit,
            "simulation_exit": simulation_exit,
            "signal": signal,
            "canonical_exit": canonical_exit,
            "returned_canonical_decision": canonical.get("decision"),
            "natural_terminal": natural,
            "host_duration_seconds": duration_seconds,
            "host_duration_hours": duration_seconds / 3600,
            "ordered_stage_starts": len(starts),
            "ordered_stage_finishes": len(finishes),
            "tailround_flow_samples": len(flow),
            "qualified_frozen_windows": frozen_windows,
            "qualified_monotonic": monotonic,
            "last_flow": last_flow,
            "last_state": last_state,
            "last_sg": sg[-1] if sg else {},
        },
        "LAST_PROVEN_GOOD": "OP_TAIL_ROUND_BUFFER5_FIRST_ACCEPTED_WRITE_AND_MSE4_CH0_FIRST_WDATA",
        "FIRST_DIVERGENCE": "AFTER_BUFFER_AG_AND_RDAG_FINITE_ENQUEUE_BEFORE_RDAG_DEQUEUE_READ_REQUEST_AND_SECOND_CHANNEL_PREPARED_WDATA",
        "HANG_ROOT_CAUSE": {
            "status": "NOT_UNIQUELY_PROVEN",
            "bounded_interval": "Buffer_AG paired ROW/COL queue -> RD_Buffer_AG outbuffer/read request -> WR_Data_Channel second prepared beat/channel delivery",
            "facts": [
                "COL4/stride2 isolated configuration compiled and started but did not reach COMP_FINISH",
                "one Buffer5 accepted write and one channel-0 MSE4 wdata occurred",
                "Buffer_AG enq/deq=3/2 and RD_Buffer_AG enq/deq/rreq=2/0/0",
                "WR request/prepared=2/1, channel wdata=1/0, and all reported queues remained full",
                "all qualified counters froze for at least 16 complete stall windows",
            ],
            "candidates": [
                "Buffer_AG ROW/COL pair/tag or queue dequeue ownership",
                "RD_Buffer_AG outbuffer eligibility/read-request handshake",
                "WR_Data_Channel prepared-data capacity/second-beat selection",
                "channel-1 output-buffer request/wdata ownership",
            ],
            "not_proven": ["configuration defect", "functional RTL defect", "which candidate is the first blocking leaf"],
        },
        "formal_D": formal,
        "SERVER_RESULT_GATE": {
            "pass": False,
            "reason": "compile=0 but simulation=124, natural terminal absent, and 28/28 formal D missing; mismatch=0 is unevaluable",
        },
        "evidence_levels": {"E3": False, "E4": False, "E5": False},
        "claim_boundary": {
            "scope": "isolated op_tail_round only",
            "stimulus": "DIAGNOSTIC_STIMULUS_NOT_PRODUCER_EVIDENCE",
            "host_precomputed_internal_tensor": True,
            "producer_evidence_claimed": False,
            "full_chain_claimed": False,
        },
        "BLOCKER_DELTA": {
            "closed": ["B_QADD_TAILROUND_COL4_STRIDE2_DYNAMIC_UNTESTED"],
            "opened": ["B_QADD_TAILROUND_RDAG_WRDATA_SECOND_BEAT_FIRST_BLOCKING_LEAF_UNKNOWN"],
            "refined_from": "tail_round row-window/config candidate",
            "refined_to": "finite queue activity followed by no RDAG dequeue/read request and no second-channel prepared wdata",
        },
        "SUCCESSOR_PROPOSAL": {
            "required": True,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "fresh_identity": "r5_qadd_n7_tailround_queueflow_v52",
            "frozen": "isolated workload, COL4/stride2 config, numeric/W3/qparams/tail/golden/2h timeout/functional RTL",
            "changed_surface": "bounded qualified event logger/parser for all remaining queueflow candidates",
        },
        "RULE_CONFIRMATION": {
            "status": "CONFIRMED",
            "statement": "Current hang-first, qualified-progress, formal-D conjunction, host-stimulus claim boundary, continuous-closure, and first-fresh independent-audit rules fully cover this return and successor.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "analysis_valid": not errors, "errors": errors, "output": str(args.output),
        "bytes": args.output.stat().st_size, "sha256": sha(args.output),
    }, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
