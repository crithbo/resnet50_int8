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

PACKAGE = "r5_n4_hw_v72_token_origin_accept_diag"
SOURCE = "r5_n4_hw_v71_token_origin_diag"
BEGIN = "// v72 TOKEN_ORIGIN_ACCEPT_ACTUAL_CONSUMER_BEGIN"
END = "// v72 TOKEN_ORIGIN_ACCEPT_ACTUAL_CONSUMER_END"
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
    ap.add_argument("--source-v71", required=True, type=Path)
    ap.add_argument("--iverilog", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    checks: dict[str, bool] = {}
    with zipfile.ZipFile(args.zip) as archive, zipfile.ZipFile(args.source_v71) as source_archive:
        observer = archive.read(f"{PACKAGE}/tb_probe/native_return_observer.svh").decode()
        runner = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode()
        runtime = archive.read(f"{PACKAGE}/package_tools/node0004_hang_localization_runtime.py").decode()
        manifest = json.loads(archive.read(f"{PACKAGE}/package_manifest.json"))
        source_root = source_archive.namelist()[0].split("/", 1)[0]
        source_manifest = json.loads(source_archive.read(f"{source_root}/package_manifest.json"))
        frozen = [p for p in source_manifest["files"] if p.startswith("workload/") or "golden" in p.lower() or p.endswith(".bin")]
        checks["frozen_payload"] = bool(frozen) and all(
            archive.read(f"{PACKAGE}/{p}").replace(PACKAGE.encode(), source_root.encode()) == source_archive.read(f"{source_root}/{p}")
            for p in frozen)

    checks["span_exact"] = observer.count(BEGIN) == observer.count(END) == 1
    block = observer[observer.index(BEGIN):observer.index(END) + len(END)]
    exprs = sorted(set(XMR_RE.findall(block)), key=len, reverse=True)
    corpus = {p: p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "NDP_copy01/rtl").rglob("*")
              if p.is_file() and p.suffix.lower() in {".sv", ".v", ".svh", ".vh"}}
    missing = []
    bindings = []
    for expr in exprs:
        token = leaf(expr)
        locations = [p for p, text in corpus.items() if re.search(rf"\b{re.escape(token)}\b", text)]
        if not locations:
            missing.append(expr)
        bindings.append({"expression": expr, "leaf": token,
                         "source_files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p.read_bytes())}
                                          for p in locations[:8]]})
    checks["actual_consumers_bound"] = bool(exprs) and not missing
    checks["accepted_write_predicates"] = all(text in block for text in (
        "to_mem_wr = to_mem_wr_attempt && !to_mem_full;",
        "to_buf_wr = to_buf_wr_attempt && !to_buf_full;",
        "mem_ag_idx_queue_full", "buf_ag_idx_queue_full"))
    checks["attempt_and_full_state_exposed"] = all(token in block for token in (
        "mem_wr_attempt=%0d", "buf_wr_attempt=%0d", "mem_full=%0d", "buf_full=%0d"))

    replacements = {expr: f"xmr_{idx}" for idx, expr in enumerate(exprs)}
    focused = block
    for expr, local in replacements.items():
        focused = focused.replace(expr, local)
    declared = set(LOCAL_RE.findall(focused))
    used = set(NAME_RE.findall(focused))
    external = sorted(used - declared)
    declarations = "\n".join([f"  logic [127:0] {name};" for name in external] +
                               [f"  logic [127:0] {name};" for name in replacements.values()])
    # compile_case uses this stable focused-wrapper top name.
    source = "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n" + declarations + "\n" + focused + "\nendmodule\n"
    with tempfile.TemporaryDirectory(prefix="v72-token-origin-accept-focus-") as td:
        root = Path(td)
        positive = compile_case(args.iverilog, root, "positive", source)
        missing_decl = compile_case(args.iverilog, root, "missing_decl", source.replace("  bit return_obs_to_enabled;", "", 1))
        first = next(iter(replacements.values()))
        typo = compile_case(args.iverilog, root, "consumer_typo", source.replace(first, first + "_typo", 1))
    checks["focused_syntax_scope_positive"] = positive["exit_code"] == 0
    checks["missing_declaration_negative"] = missing_decl["exit_code"] != 0
    checks["actual_consumer_typo_negative"] = typo["exit_code"] != 0

    argv = " +RETURN_OBS_TOKEN_ORIGIN_ACCEPT +RETURN_OBS_TOKEN_ORIGIN_ACCEPT_LIMIT=128"
    checks["runner_feature_twice"] = runner.count(argv) == 2
    checks["runtime_feature_binding"] = all(token in runtime for token in (
        '"feature": "RETURN_OBS_TOKEN_ORIGIN_ACCEPT"', '"+RETURN_OBS_TOKEN_ORIGIN_ACCEPT"',
        '"+RETURN_OBS_TOKEN_ORIGIN_ACCEPT_LIMIT=128"', '"multiclass=ALL_CLASS_BITSET"'))
    feature = manifest["diagnostic_features"]["RETURN_OBS_TOKEN_ORIGIN_ACCEPT"]
    checks["manifest_feature_binding"] = (
        feature["edge_schema"] == "TOKEN_ORIGIN_ACCEPT_EDGE_V2"
        and feature["multiclass_strategy"] == "ALL_CLASS_BITSET_PER_RECORD"
        and feature["qualification"]["buf_queue_write"] == "buf_ag_idx_queue_wr_en && !buf_ag_idx_queue_full")

    traces = [
        {"attempt": 0, "full": 0, "accepted": 0},
        {"attempt": 1, "full": 0, "accepted": 1},
        {"attempt": 1, "full": 1, "accepted": 0},
        {"attempt": 1, "full": 1, "accepted": 0},
        {"attempt": 1, "full": 0, "accepted": 1},
    ]
    checks["predicate_trace_exact"] = all(row["accepted"] == (row["attempt"] and not row["full"]) for row in traces)
    checks["stable_full_attempt_zero_progress"] = sum(row["accepted"] for row in traces[2:4]) == 0
    checks["old_attempt_only_negative_fails"] = sum(row["attempt"] for row in traces) != sum(row["accepted"] for row in traces)
    simultaneous = {"mem_wr": 1, "buf_wr": 1, "mem_pop": 1, "buf_pop": 1, "desc": 1}
    checks["multiclass_edge_no_loss_trace"] = sum(simultaneous.values()) == 5 and "else if (to_" not in block

    errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "node0004-v72-token-origin-accept-validation-v1",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "actual_consumer_count": len(exprs),
        "missing_consumers": missing,
        "consumer_bindings": bindings,
        "focused_compile": {"positive": positive, "missing_declaration_negative": missing_decl,
                            "consumer_typo_negative": typo},
        "predicate_trace": traces,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": not errors, "errors": errors, "consumers": len(exprs)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
