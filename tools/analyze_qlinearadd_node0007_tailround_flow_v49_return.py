"""Formal, return-bound analysis of QLinearAdd node0007 v49.

The tool validates the returned archive and its frozen source binding, then
replays the package-local progress predicate with a decimal-safe parser.  It
does not run the DUT or recompute numeric/workload/golden assets.
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
NAME = "r5_qadd_n7_tailround_flow_v49"
RETURN_ROOT = NAME + "_return"
RETURN_BYTES = 407_651
RETURN_SHA = "8bf7864bd7fc5ee8e4ac5509a4e8b1e37705e3aeea9c54e419faeb51e7a6bdd3"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{NAME}.zip"
SOURCE_BYTES = 38_066_331
SOURCE_SHA = "b5fe58fff8401fb60284951859be975931e8744e1e0235b60847973513abf071"
NATIVE = ROOT / "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json"
FINAL_JSON = ROOT / "artifacts/operator_config_validation/qadd_n7_full_v38/assembled_execplan/pipeline_output/jsons/op_tail_round_resnet50_qadd_node0007_tail_round.json"
RULES = {
    "agent": ROOT / ".agents/agent.md",
    "plan_mutable": ROOT / ".agents/plan.md",
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}
STAGES = ("op_a_dequant", "op_b_dequant", "op_relocation_pad", "op_fp32_add", "op_tail_mul", "op_tail_round")
QUALIFIED = (
    "mse0_addr", "mse0_req", "mse0_meta", "mse0_consume", "mse0_buf",
    "ga_in", "ga_out", "buf5_wr", "buf5_rd", "bag_enq", "bag_deq",
    "rdag_enq", "rdag_deq", "rdag_rreq", "wr_req", "wr_prepared",
    "wr_ob_enq0", "wr_ob_enq1", "wr_ob_deq0", "wr_ob_deq1",
    "mse4_req0", "mse4_req1", "mse4_wdata0", "mse4_wdata1",
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
            mode = (info.external_attr >> 16) & 0xFFFF
            if info.filename in seen:
                duplicates.append(info.filename)
            seen.add(info.filename)
            if not pure.parts:
                unsafe.append(info.filename)
                continue
            roots.add(pure.parts[0])
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                unsafe.append(info.filename)
            if stat.S_ISLNK(mode):
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
    """Parse decimal with base 10 and explicit 0x values with base 16.

    In particular, decimal observer values such as ``02`` are valid and must
    not be fed to ``int(value, 0)``.
    """
    result: dict[str, int] = {}
    for key, value in re.findall(r"(\w+)=(0x[0-9a-fA-F]+|\d+)", body):
        result[key] = int(value, 16) if value.lower().startswith("0x") else int(value, 10)
    return result


def events(text: str, event: str) -> list[dict[str, Any]]:
    rows = []
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
    per_file_errors = []
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
        errors.append("returned source manifest does not byte-bind frozen v49")

    compile_exit = int(returned["evidence/compile_exit_status.txt"].decode().strip())
    simulation_exit = int(returned["evidence/simulation_exit_status.txt"].decode().strip())
    signal = returned["evidence/signal_status.txt"].decode().strip()
    canonical_exit = int(returned["evidence/canonical_decision_exit_status.txt"].decode().strip())
    timing = dict(line.split("=", 1) for line in returned["evidence/host_timing.txt"].decode().splitlines() if "=" in line)
    duration_seconds = (int(timing["run_end_ns"]) - int(timing["run_start_ns"])) / 1e9
    result_gate = obj(returned, "evidence/SERVER_RESULT_GATE.json")
    runtime_layout = obj(returned, "evidence/runtime_layout_receipt.json")
    observer = returned["runs/return_observer.log"].decode(errors="replace")
    simlog = returned["runs/sim.log"].decode(errors="replace")
    starts = events(observer, "EXEC_START")
    finishes = events(observer, "COMP_FINISH")
    flow = events(observer, "TAILROUND_FLOW")
    state = events(observer, "TAILROUND_STATE")
    sg = events(observer, "SG_COUNTS")
    frozen_windows = sum(
        all(after.get(key, 0) == before.get(key, 0) for key in QUALIFIED)
        for before, after in zip(flow, flow[1:])
    )
    monotonic = all(
        all(after.get(key, 0) >= before.get(key, 0) for key in QUALIFIED)
        for before, after in zip(flow, flow[1:])
    )
    last_flow = {key: flow[-1].get(key, 0) for key in QUALIFIED} if flow else {}
    last_state = state[-1] if state else {}
    parser_defect_reproduced = fields("mse4_req0=02 row=0x0") == {"mse4_req0": 2, "row": 0}
    natural = (
        compile_exit == 0 and simulation_exit == 0 and signal == "NONE"
        and len(starts) == 6 and len(finishes) == 6
        and "Simulation completed successfully!" in simlog
        and result_gate.get("result_gate_conjunction", {}).get("all_terms_true") is True
    )
    if (compile_exit, simulation_exit, signal, canonical_exit) != (0, 124, "NONE", 1):
        errors.append("execution/canonical exit tuple differs")
    if len(starts) != 6 or len(finishes) != 5 or len(flow) != 47 or frozen_windows < 46 or not monotonic:
        errors.append("ordered stage/tail-round qualified evidence differs")
    if not parser_defect_reproduced:
        errors.append("decimal-safe parser control failed")

    native = json.loads(NATIVE.read_text(encoding="utf-8"))
    final = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    native_col = native["buffer_loop_configs"]["GROUP2"]["COL_LC"]
    final_col = final["buffer_loop_configs"]["GROUP2"]["COL_LC"]
    strides = final["stream_engine"]["stream2"]["buf_spatial_stride"]
    width = 32
    window0 = sorted({(0 + value) % width for value in strides})
    window1_current = sorted({(final_col["stride"] + value) % width for value in strides})
    window1_native = sorted({(native_col["stride"] + value) % width for value in strides})
    overlap_current = sorted(set(window0) & set(window1_current))
    union_native = sorted(set(window0) | set(window1_native))
    config_counterexample = {
        "native_oracle": {"path": NATIVE.relative_to(ROOT).as_posix(), "sha256": sha(NATIVE)},
        "final_json": {"path": FINAL_JSON.relative_to(ROOT).as_posix(), "sha256": sha(FINAL_JSON)},
        "buffer_row_bytes": 32,
        "mse_read_bytes": 16,
        "spatial_stride": strides,
        "current_col_loop": final_col,
        "native_col_loop": native_col,
        "current_window0": window0,
        "current_window1": window1_current,
        "current_overlap": overlap_current,
        "current_union_size": len(set(window0) | set(window1_current)),
        "native_window1": window1_native,
        "native_union": union_native,
        "native_union_exact_0_31": union_native == list(range(32)),
        "claim": "current COL stride 16 aliases the same interleaved 16-byte set modulo the 32-byte Buffer row; native stride 2 supplies the complementary byte offsets",
    }
    root_unique = (
        len(overlap_current) == 16
        and len(set(window0) | set(window1_current)) == 16
        and union_native == list(range(32))
        and last_flow.get("wr_req") == 2
        and last_flow.get("wr_prepared") == 1
        and last_flow.get("rdag_deq") == 0
        and last_state.get("bag_full") == 1
        and last_state.get("rdag_full") == 1
        and last_state.get("wr_queue_full") == 1
        and last_state.get("wr_prepared_valid") == 0
    )
    if not root_unique:
        errors.append("tail-round row-window counterexample did not close")

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
        key: {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path), "mutable_provenance_only": key == "plan_mutable"}
        for key, path in RULES.items()
    }
    report = {
        "schema": "qlinearadd-node0007-tailround-flow-v49-return-analysis-v1",
        "status": "RETURN_ANALYSIS_COMPLETE_UNIQUE_TAILROUND_COLUMN_ALIAS_ROOT_CAUSE",
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
            "return": {"path": str(return_path), "bytes": return_path.stat().st_size, "sha256": sha(return_path), "execution": "r1786169131743745543_3998251", "attempt": "a3998251"},
            "return_structure": return_structure,
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "bytes": SOURCE.stat().st_size, "sha256": sha(SOURCE), "structure": source_structure},
            "manifest_exact_set": exact_set,
            "manifest_per_file_errors": per_file_errors,
            "source_manifest_byte_bound": source_binding,
            "runtime_layout": {"server_root": runtime_layout.get("server_root"), "attempt": runtime_layout.get("attempt"), "root_exact_set_unchanged": runtime_layout.get("root_exact_set_unchanged"), "all_package_owned_paths_under_install": runtime_layout.get("all_package_owned_paths_under_install")},
        },
        "RETURN_ANALYSIS": {
            "outcome": "LONG_RUNNING_HANG_AT_OP_TAIL_ROUND_COLUMN_ALIAS",
            "compile_exit": compile_exit,
            "simulation_exit": simulation_exit,
            "signal": signal,
            "canonical_exit": canonical_exit,
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
        "canonical_adjudication": {
            "returned_record_present": "evidence/CANONICAL_PROGRESS_DECISION.json" in returned,
            "parser_exit": canonical_exit,
            "package_parser_defect": "int(value, 0) rejects decimal observer token '02'",
            "decimal_safe_replay_control": parser_defect_reproduced,
            "manual_canonical_decision": "LONG_RUNNING_HANG_AT_OP_TAIL_ROUND",
            "manual_boundary": "AFTER_ONE_PREPARED_16B_SET_BEFORE_SECOND_DISJOINT_SET",
        },
        "LAST_PROVEN_GOOD": "OP_TAIL_ROUND_FIRST_16B_PREPARED_DATA_ACCEPT",
        "FIRST_DIVERGENCE": "OP_TAIL_ROUND_SECOND_COL_OCCURRENCE_ALIASES_FIRST_16B_BUFFER5_SET",
        "HANG_ROOT_CAUSE": {
            "status": "UNIQUELY_PROVEN_CONFIG_CONSUMER_MISMATCH",
            "root": "GROUP2.COL_LC stride/end were generalized to 16/32 while uint8 stream2 retains native interleaved spatial strides; modulo a 32B row both occurrences request the same 16 byte positions",
            "counterexample": config_counterexample,
            "dynamic_binding": "wr_req=2, wr_prepared=1, prepared_valid=0 with Buffer_AG/RDAG/WR queues full for 46 complete qualified windows",
            "separate_package_defect": "canonical decimal parser rejects zero-padded decimal values",
        },
        "formal_D": formal,
        "SERVER_RESULT_GATE": {"pass": False, "reason": "compile0 but simulation124, natural terminal absent, formal D missing 28/28; mismatch=0 unevaluable"},
        "evidence_levels": {"E3": False, "E4": False, "E5": False},
        "BLOCKER_DELTA": {
            "closed": ["B_QADD_V49_TAILROUND_FIRST_BLOCKING_EDGE_NOT_UNIQUE"],
            "opened": ["B_QADD_TAILROUND_INTERLEAVED_COL_ALIAS", "B_QADD_V49_CANONICAL_DECIMAL_PARSE"],
            "refined_to": "tail_round GROUP2.COL_LC interleaved byte-set alias plus independent package parser defect",
        },
        "SUCCESSOR_PROPOSAL": {
            "required": True,
            "classification": "CONFIG_ONLY_CORRECTNESS_BASELINE_FUNCTIONAL_FIX_WITH_DIAGNOSTICS",
            "fresh_identity": "r5_qadd_n7_tailround_colfix_v50",
            "authorized_config_delta": {"GROUP2.COL_LC.end": [32, 4], "GROUP2.COL_LC.stride": [16, 2]},
            "parser_delta": "decimal tokens base10; explicit 0x tokens base16",
            "frozen": "all other six-stage config, numeric/W3/qparams/tail/workload/golden/timeout/functional RTL",
        },
        "RULE_DELTA_PROPOSAL": {
            "status": "PROPOSE",
            "proposal": "Clarify CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001: derive each accepted byte set from COL base plus the complete stream buf_spatial_stride modulo physical row width. COL stride=16 is valid only for contiguous [0..15] spatial offsets; the native uint8 interleaved offsets require COL stride=2. Do not list stride=2 as an unconditional negative independent of stream layout.",
            "evidence": "native quant template gives end/stride=4/2; final v49 gives 32/16; static sets alias 16/16 bytes and dynamic return shows exactly 2 requests but only 1 prepared beat before permanent full queues",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"analysis_valid": not errors, "errors": errors, "output": str(args.output), "bytes": args.output.stat().st_size, "sha256": sha(args.output)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
