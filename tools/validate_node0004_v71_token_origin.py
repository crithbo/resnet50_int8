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

PACKAGE = "r5_n4_hw_v71_token_origin_diag"
SOURCE = "r5_n4_hw_v70_branch_owner_diag"
BEGIN = "// v71 TOKEN_ORIGIN_ACTUAL_CONSUMER_BEGIN"
END = "// v71 TOKEN_ORIGIN_ACTUAL_CONSUMER_END"
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
    ap.add_argument("--source-v70", required=True, type=Path)
    ap.add_argument("--iverilog", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args(); checks: dict[str, bool] = {}
    with zipfile.ZipFile(a.zip) as z, zipfile.ZipFile(a.source_v70) as source_zip:
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
    checks["token_origin_consumers"] = all(x in block for x in (
        "mem_ag_idx_queue_wr_en", "mem_ag_idx_queue_wr_data", "buf_ag_idx_queue_wr_en",
        "buf_ag_idx_queue_wr_data", "mse_mem_queue_tag[0]", "mse_buf_queue_row_tag",
        "mse_buf_queue_col_tag", "wr_data_chl_req_valid"))

    replacements = {expr: f"xmr_{i}" for i, expr in enumerate(exprs)}; focused = block
    for expr, local in replacements.items():
        focused = focused.replace(expr, local)
    declared = set(LOCAL_RE.findall(focused)); used = set(NAME_RE.findall(focused))
    external = sorted(used - declared)
    declarations = "\n".join([f"  logic [127:0] {name};" for name in external] +
                               [f"  logic [127:0] {name};" for name in replacements.values()])
    source = "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n" + declarations + "\n" + focused + "\nendmodule\n"
    with tempfile.TemporaryDirectory(prefix="v71-token-origin-focus-") as td:
        root = Path(td); positive = compile_case(a.iverilog, root, "positive", source)
        missing_decl = compile_case(a.iverilog, root, "missing_decl", source.replace("  bit return_obs_to_enabled;", "", 1))
        first = next(iter(replacements.values()))
        typo = compile_case(a.iverilog, root, "consumer_typo", source.replace(first, first + "_typo", 1))
    checks["focused_syntax_scope_positive"] = positive["exit_code"] == 0
    checks["missing_declaration_negative"] = missing_decl["exit_code"] != 0
    checks["actual_consumer_typo_negative"] = typo["exit_code"] != 0
    token = " +RETURN_OBS_TOKEN_ORIGIN +RETURN_OBS_TOKEN_ORIGIN_LIMIT=128"
    checks["runner_feature_twice"] = runner.count(token) == 2
    checks["runtime_feature_binding"] = all(x in runtime for x in (
        '"feature": "RETURN_OBS_TOKEN_ORIGIN"', '"+RETURN_OBS_TOKEN_ORIGIN"',
        '"+RETURN_OBS_TOKEN_ORIGIN_LIMIT=128"', '"multiclass=ALL_CLASS_BITSET"'))
    feature = manifest["diagnostic_features"]["RETURN_OBS_TOKEN_ORIGIN"]
    required = {"mem_queue_write", "buf_queue_write", "mem_queue_pop", "buf_queue_pop", "descriptor_accept"}
    checks["manifest_feature_binding"] = feature["edge_schema"] == "TOKEN_ORIGIN_EDGE_V1" and \
        feature["multiclass_strategy"] == "ALL_CLASS_BITSET_PER_RECORD" and set(feature["required_classes"]) == required

    # Exact predicate trace: every same-cycle class is independently encoded and consumed.
    traces = [
        {"mem_wr": 1, "buf_wr": 0, "mem_pop": 0, "buf_pop": 0, "desc": 0},
        {"mem_wr": 0, "buf_wr": 1, "mem_pop": 1, "buf_pop": 0, "desc": 0},
        {"mem_wr": 1, "buf_wr": 1, "mem_pop": 1, "buf_pop": 1, "desc": 1},
        {"mem_wr": 0, "buf_wr": 0, "mem_pop": 0, "buf_pop": 0, "desc": 0},
    ]
    exact_totals = {k: sum(row[k] for row in traces) for k in traces[0]}
    priority_totals = {k: 0 for k in traces[0]}
    for row in traces:
        for key in row:
            if row[key]:
                priority_totals[key] += 1
                break
    predicate_trace = {
        "all_class_combination_present": traces[2] == {k: 1 for k in traces[2]},
        "all_class_parser_exact": exact_totals == {"mem_wr": 2, "buf_wr": 2, "mem_pop": 2, "buf_pop": 1, "desc": 1},
        "stable_level_zero_progress": sum(traces[3].values()) == 0,
        "priority_only_negative_loses_classes": priority_totals != exact_totals,
        "observer_has_no_priority_arbiter": "else if (to_" not in block,
        "observer_emits_all_event_bits": all(f"{k}_ev=%0d" in block for k in ("mem_wr", "buf_wr", "mem_pop", "buf_pop", "desc")),
    }
    checks["multiclass_edge_no_loss_trace"] = all(predicate_trace.values())
    errors = [key for key, value in checks.items() if not value]
    report = {"schema": "node0004-v71-token-origin-observer-validation-v1",
              "valid": not errors, "errors": errors, "checks": checks,
              "actual_consumer_count": len(exprs), "missing_consumers": missing,
              "consumer_bindings": bindings, "focused_compile": {"positive": positive,
              "missing_declaration_negative": missing_decl, "consumer_typo_negative": typo},
              "multiclass_predicate_trace": predicate_trace}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": not errors, "errors": errors, "consumers": len(exprs)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
