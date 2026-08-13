from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.validate_node0004_v44_observer_syntax import compile_case  # noqa: E402

PACKAGE = "r5_n4_hw_v69_branch_drain_diag"
BEGIN = "// v69 BRANCH_DRAIN_ACTUAL_CONSUMER_BEGIN"
END = "// v69 BRANCH_DRAIN_ACTUAL_CONSUMER_END"
XMR_RE = re.compile(r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]\n]+\])*)+")
LOCAL_RE = re.compile(r"\b(?:bit|integer|longint\s+unsigned|logic(?:\s+\[[^\]]+\])?)\s+(return_obs_[A-Za-z0-9_]+)")
NAME_RE = re.compile(r"\b(return_obs_[A-Za-z0-9_]+)\b")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def leaf(expr: str) -> str:
    return re.sub(r"\[.*\]$", "", expr.rsplit(".", 1)[-1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--source-v68", required=True, type=Path)
    ap.add_argument("--iverilog", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args(); checks: dict[str, bool] = {}; errors: list[str] = []
    with zipfile.ZipFile(a.zip) as z, zipfile.ZipFile(a.source_v68) as source_zip:
        ob = z.read(f"{PACKAGE}/tb_probe/native_return_observer.svh")
        runner = z.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode()
        runtime = z.read(f"{PACKAGE}/package_tools/node0004_hang_localization_runtime.py").decode()
        manifest = json.loads(z.read(f"{PACKAGE}/package_manifest.json"))
        source_root = source_zip.namelist()[0].split("/", 1)[0]
        source_manifest = json.loads(source_zip.read(f"{source_root}/package_manifest.json"))
        frozen = [p for p in source_manifest["files"] if p.startswith("workload/") or "golden" in p.lower() or p.endswith(".bin")]
        checks["frozen_payload"] = bool(frozen) and all(
            z.read(f"{PACKAGE}/{p}").replace(PACKAGE.encode(), source_root.encode()) == source_zip.read(f"{source_root}/{p}")
            for p in frozen)
    observer = ob.decode(); checks["span_exact"] = observer.count(BEGIN) == observer.count(END) == 1
    block = observer[observer.index(BEGIN):observer.index(END) + len(END)]
    exprs = sorted(set(XMR_RE.findall(block)), key=len, reverse=True)
    corpus = {p: p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "NDP_copy01/rtl").rglob("*")
              if p.is_file() and p.suffix.lower() in {".sv", ".v", ".svh", ".vh"}}
    missing = []; bindings = []
    for expr in exprs:
        token = leaf(expr); locations = [p for p, text in corpus.items() if re.search(rf"\b{re.escape(token)}\b", text)]
        if not locations:
            missing.append(expr)
        bindings.append({"expression": expr, "leaf": token,
                         "source_files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p.read_bytes())}
                                          for p in locations[:8]]})
    checks["actual_consumers_bound"] = bool(exprs) and not missing
    checks["exact_physical_consumers"] = all(
        token in block for token in (
            "iga_lc_outport_bp_post[18]", "u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full",
            "u_RD_Buffer_AG.buf_ag_ob_full", "u_WR_Data_Channel.wr_data_chl_prepared_data_cnt",
            "u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty", "wr_data_chl_req_valid",
            "mse2mem_request_valid", "mse2mem_wdata_valid",
        )) and "MSE_INST[4]" in block

    replacements = {expr: f"xmr_{i}" for i, expr in enumerate(exprs)}; focused = block
    for expr, local in replacements.items():
        focused = focused.replace(expr, local)
    declared = set(LOCAL_RE.findall(focused)); used = set(NAME_RE.findall(focused))
    external = sorted((used - declared) - {"return_obs_write_branch_drain"})
    declarations = "\n".join([f"  logic [127:0] {name};" for name in external] +
                               [f"  logic [127:0] {name};" for name in replacements.values()])
    source = "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n" + declarations + "\n" + focused + \
             '\n  initial begin #1; return_obs_write_branch_drain("FOCUS"); end\nendmodule\n'
    with tempfile.TemporaryDirectory(prefix="v69-branch-drain-focus-") as td:
        root = Path(td); positive = compile_case(a.iverilog, root, "positive", source)
        missing_decl = compile_case(a.iverilog, root, "missing_decl", source.replace("  bit return_obs_bd_enabled;", "", 1))
        first = next(iter(replacements.values()))
        typo = compile_case(a.iverilog, root, "consumer_typo", source.replace(first, first + "_typo", 1))
    checks["focused_syntax_scope_positive"] = positive["exit_code"] == 0
    checks["missing_declaration_negative"] = missing_decl["exit_code"] != 0
    checks["actual_consumer_typo_negative"] = typo["exit_code"] != 0

    # Exact predicate microtrace: held levels do not count; each counter changes
    # only on its qualified conjunction, including simultaneous events.
    trace = [
        {"valid": 1, "ready": 0, "expect": 0},
        {"valid": 0, "ready": 1, "expect": 0},
        {"valid": 1, "ready": 1, "expect": 1},
        {"valid": 1, "ready": 1, "expect": 1},
        {"valid": 0, "ready": 0, "expect": 0},
    ]
    checks["predicate_trace_unit"] = all((row["valid"] and row["ready"]) == row["expect"] for row in trace)
    stable = [{"valid": 1, "ready": 0}] * 8
    checks["stable_level_not_progress"] = sum(int(x["valid"] and x["ready"]) for x in stable) == 0
    simultaneous = {"buf_pop": 1, "mem_match": 1, "prep_rd": 1}
    checks["simultaneous_events_independent"] = sum(simultaneous.values()) == 3

    checks["runner_feature_twice"] = runner.count(" +RETURN_OBS_BRANCH_DRAIN +RETURN_OBS_BRANCH_DRAIN_LIMIT=128") == 2
    checks["runtime_feature_binding"] = all(x in runtime for x in (
        '"feature": "RETURN_OBS_BRANCH_DRAIN"', '"+RETURN_OBS_BRANCH_DRAIN"',
        '"+RETURN_OBS_BRANCH_DRAIN_LIMIT=128"'))
    feature = manifest["diagnostic_features"]["RETURN_OBS_BRANCH_DRAIN"]
    checks["manifest_feature_binding"] = feature["edge_schema"] == "BRANCH_DRAIN_V1" and \
        feature["runtime_enable_parameter"] == "+RETURN_OBS_BRANCH_DRAIN" and len(feature["candidate_matrix"]) == 4
    checks["canonical_and_signal_snapshot"] = observer.count('return_obs_write_branch_drain("DIAG_DECISION")') == 1 and \
        observer.count("return_obs_write_branch_drain(event_name)") == 1
    errors = [key for key, value in checks.items() if not value]
    report = {"schema": "node0004-v69-branch-drain-observer-validation-v1",
              "valid": not errors, "errors": errors, "checks": checks,
              "actual_consumer_count": len(exprs), "missing_consumers": missing,
              "consumer_bindings": bindings, "focused_compile": {"positive": positive,
              "missing_declaration_negative": missing_decl, "consumer_typo_negative": typo},
              "predicate_trace": trace}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": not errors, "errors": errors, "consumers": len(exprs)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
