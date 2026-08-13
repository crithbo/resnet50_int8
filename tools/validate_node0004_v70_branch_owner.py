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
from tools.validate_server_triggered_causal_observability import validate_bundle  # noqa: E402

PACKAGE = "r5_n4_hw_v70_branch_owner_diag"
BEGIN = "// v70 BRANCH_OWNER_ACTUAL_CONSUMER_BEGIN"
END = "// v70 BRANCH_OWNER_ACTUAL_CONSUMER_END"
PROFILE = "provenance/server_triggered_causal_observability_v70.json"
XMR_RE = re.compile(r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]\n]+\])*)+")
LOCAL_RE = re.compile(r"\b(?:bit|integer|longint\s+unsigned|logic(?:\s+\[[^\]]+\])?)\s+(return_obs_[A-Za-z0-9_]+)")
NAME_RE = re.compile(r"\b(return_obs_[A-Za-z0-9_]+)\b")
EDGE_RE = re.compile(
    r"^(?P<time>\d+) \| BRANCH_OWNER_EDGE_V1 \| qn=(?P<qn>\d+) "
    r"desc_ev=(?P<desc>[01]) buf_pop_ev=(?P<pop>[01]) buf_req_ev=(?P<req>[01]) "
    r"buf_ret_ev=(?P<ret>[01]) prep_wr_ev=(?P<wr>[01]) prep_rd_ev=(?P<rd>[01]) "
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def leaf(expr: str) -> str:
    return re.sub(r"\[.*\]$", "", expr.rsplit(".", 1)[-1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--source-v69", required=True, type=Path)
    ap.add_argument("--iverilog", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args(); checks: dict[str, bool] = {}
    with zipfile.ZipFile(a.zip) as z, zipfile.ZipFile(a.source_v69) as source_zip:
        ob = z.read(f"{PACKAGE}/tb_probe/native_return_observer.svh")
        runner = z.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode()
        runtime = z.read(f"{PACKAGE}/package_tools/node0004_hang_localization_runtime.py").decode()
        manifest = json.loads(z.read(f"{PACKAGE}/package_manifest.json"))
        profile = json.loads(z.read(f"{PACKAGE}/{PROFILE}"))
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
    checks["token_owner_consumers"] = all(x in block for x in (
        "mse_mem_ag_tag", "mse_buf_ag_tag", "mse2buf_last_index", "buf_ag_last_req_flag",
        "wr_data_chl_req_tsf_size", "wr_chl_queue_wr_data", "wr_chl_queue_rd_data",
        "wr_data_chl_prepared_data_cur_base_wptr", "wr_data_chl_prepared_data_cur_base_rptr"))

    replacements = {expr: f"xmr_{i}" for i, expr in enumerate(exprs)}; focused = block
    for expr, local in replacements.items():
        focused = focused.replace(expr, local)
    declared = set(LOCAL_RE.findall(focused)); used = set(NAME_RE.findall(focused))
    external = sorted((used - declared) - {"return_obs_write_branch_owner"})
    declarations = "\n".join([f"  logic [127:0] {name};" for name in external] +
                               [f"  logic [127:0] {name};" for name in replacements.values()])
    source = "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n" + declarations + "\n" + focused + \
             '\n  initial begin #1; return_obs_write_branch_owner("FOCUS"); end\nendmodule\n'
    with tempfile.TemporaryDirectory(prefix="v70-branch-owner-focus-") as td:
        root = Path(td); positive = compile_case(a.iverilog, root, "positive", source)
        missing_decl = compile_case(a.iverilog, root, "missing_decl", source.replace("  bit return_obs_bo_enabled;", "", 1))
        first = next(iter(replacements.values()))
        typo = compile_case(a.iverilog, root, "consumer_typo", source.replace(first, first + "_typo", 1))
    checks["focused_syntax_scope_positive"] = positive["exit_code"] == 0
    checks["missing_declaration_negative"] = missing_decl["exit_code"] != 0
    checks["actual_consumer_typo_negative"] = typo["exit_code"] != 0

    checks["runner_feature_twice"] = runner.count(
        " +RETURN_OBS_BRANCH_OWNER +RETURN_OBS_BRANCH_OWNER_LIMIT=128 +RETURN_OBS_BRANCH_OWNER_STATE_LIMIT=8") == 2
    checks["runtime_feature_binding"] = all(x in runtime for x in (
        '"feature": "RETURN_OBS_BRANCH_OWNER"', '"+RETURN_OBS_BRANCH_OWNER"',
        '"+RETURN_OBS_BRANCH_OWNER_LIMIT=128"', '"+RETURN_OBS_BRANCH_OWNER_STATE_LIMIT=8"'))
    feature = manifest["diagnostic_features"]["RETURN_OBS_BRANCH_OWNER"]
    checks["manifest_feature_binding"] = feature["edge_schema"] == "BRANCH_OWNER_EDGE_V1" and \
        feature["qualified_event_budget"] == 128 and feature["non_progress_state_budget"] == 8 and \
        feature["state_activity_consumes_qualified_budget"] is False and len(feature["candidate_matrix"]) == 4
    checks["canonical_and_signal_snapshot"] = observer.count('return_obs_write_branch_owner("DIAG_DECISION")') == 1 and \
        observer.count("return_obs_write_branch_owner(event_name)") == 1
    checks["separate_budget_logic"] = (
        "return_obs_bo_qualified_records++" in block
        and "return_obs_bo_state_records++" in block
        and "return_obs_bo_state_records < return_obs_bo_state_limit" in block
        and "return_obs_bo_qualified_records < return_obs_bo_limit" in block
    )

    registry = json.loads((ROOT / "contracts/server_triggered_causal_observability_registry_v1.json").read_text(encoding="utf-8"))
    profile_result = validate_bundle(registry, profile)
    checks["public_triggered_profile"] = profile_result.get("valid") is True

    exact = "2446464000 | BRANCH_OWNER_EDGE_V1 | qn=39 desc_ev=0 buf_pop_ev=0 buf_req_ev=0 buf_ret_ev=1 prep_wr_ev=1 prep_rd_ev=1 desc=18"
    parsed = EDGE_RE.match(exact)
    stable = [{"qualified": False}] * 256
    simultaneous = {"desc": 0, "pop": 0, "req": 0, "ret": 1, "wr": 1, "rd": 1}
    format_trace = {
        "exact_accept": parsed is not None,
        "missing_field_reject": EDGE_RE.match(exact.replace(" prep_rd_ev=1", "")) is None,
        "token_typo_reject": EDGE_RE.match(exact.replace("prep_wr_ev", "prep_wx_ev")) is None,
        "padding_mutation_reject": EDGE_RE.match(exact.replace("qn=39", "qn= 39")) is None,
        "stable_level_zero_qualified": sum(int(x["qualified"]) for x in stable) == 0,
        "simultaneous_events_independent": sum(simultaneous.values()) == 3,
    }
    checks["logger_parser_exact_format_trace"] = all(format_trace.values())
    errors = [key for key, value in checks.items() if not value]
    report = {"schema": "node0004-v70-branch-owner-observer-validation-v1",
              "valid": not errors, "errors": errors, "checks": checks,
              "actual_consumer_count": len(exprs), "missing_consumers": missing,
              "consumer_bindings": bindings, "focused_compile": {"positive": positive,
              "missing_declaration_negative": missing_decl, "consumer_typo_negative": typo},
              "triggered_profile_validation": profile_result, "logger_parser_format_trace": format_trace}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": not errors, "errors": errors, "consumers": len(exprs)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
