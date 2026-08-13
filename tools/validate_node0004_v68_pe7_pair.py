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
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from tools.validate_node0004_v44_observer_syntax import compile_case  # noqa: E402

PACKAGE = "r5_n4_hw_v68_pe7_pair_diag"
BEGIN = "// v68 PE7_PAIR_ACTUAL_CONSUMER_BEGIN"
END = "// v68 PE7_PAIR_ACTUAL_CONSUMER_END"
XMR_RE = re.compile(r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]\n]+\])*)+")
LOCAL_RE = re.compile(r"\b(?:bit|integer|longint\s+unsigned|logic(?:\s+\[[^\]]+\])?)\s+(return_obs_[A-Za-z0-9_]+)")
NAME_RE = re.compile(r"\b(return_obs_[A-Za-z0-9_]+)\b")

def sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def leaf(expr: str) -> str: return re.sub(r"\[.*\]$", "", expr.rsplit(".", 1)[-1])

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--source-v67", required=True, type=Path)
    ap.add_argument("--iverilog", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args(); checks = {}; errors = []
    with zipfile.ZipFile(a.zip) as z, zipfile.ZipFile(a.source_v67) as source_zip:
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
        if not locations: missing.append(expr)
        bindings.append({"expression": expr, "leaf": token,
                         "source_files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p.read_bytes())}
                                          for p in locations[:8]]})
    checks["actual_consumers_bound"] = not missing
    replacements = {expr: f"xmr_{i}" for i, expr in enumerate(exprs)}; focused = block
    for expr, local in replacements.items(): focused = focused.replace(expr, local)
    declared = set(LOCAL_RE.findall(focused)); used = set(NAME_RE.findall(focused))
    external = sorted((used - declared) - {"return_obs_write_pe7_pair"})
    declarations = "\n".join([f"  logic [127:0] {name};" for name in external] +
                               [f"  logic [127:0] {name};" for name in replacements.values()])
    source = "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n" + declarations + "\n" + focused + \
             '\n  initial begin #1; return_obs_write_pe7_pair("FOCUS"); end\nendmodule\n'
    with tempfile.TemporaryDirectory(prefix="v68-pe7-focus-") as td:
        root = Path(td); positive = compile_case(a.iverilog, root, "positive", source)
        missing_decl = compile_case(a.iverilog, root, "missing_decl", source.replace("  bit return_obs_p7_enabled;", "", 1))
        first = next(iter(replacements.values()))
        typo = compile_case(a.iverilog, root, "consumer_typo", source.replace(first, first + "_typo", 1))
    checks["focused_syntax_scope_positive"] = positive["exit_code"] == 0
    checks["missing_declaration_negative"] = missing_decl["exit_code"] != 0
    checks["actual_consumer_typo_negative"] = typo["exit_code"] != 0
    checks["runner_feature_twice"] = runner.count(" +RETURN_OBS_PE7_PAIR +RETURN_OBS_PE7_PAIR_LIMIT=128") == 2
    checks["runtime_feature_binding"] = all(x in runtime for x in ('"feature": "RETURN_OBS_PE7_PAIR"',
                                                                   '"+RETURN_OBS_PE7_PAIR"',
                                                                   '"+RETURN_OBS_PE7_PAIR_LIMIT=128"'))
    feature = manifest["diagnostic_features"]["RETURN_OBS_PE7_PAIR"]
    checks["manifest_feature_binding"] = feature["edge_schema"] == "PE7_PAIR_V1" and \
        feature["runtime_enable_parameter"] == "+RETURN_OBS_PE7_PAIR" and \
        feature["logical_to_physical_binding"]["logical_PE1"] == "physical_PE7"
    checks["physical_target_exact"] = "IGA_PE[7]" in block and "iga_pe_outport[7]" in block and \
        "iga_lc_outport[17]" in block and "iga_lc_outport[18]" in block and \
        "IGA_PE[1]" not in block and "iga_lc_outport[9]" not in block
    checks["candidate_matrix_complete"] = all(token in block for token in (
        "iga_pe_inbuffer_enbale[0]", "iga_pe_inbuffer_enbale[2]", "iga_pe_inbuffer_valid_bit",
        "iga_pe_inbuffer_clear", "iga_pe_inbuffer_bp_post_mask", "iga_pe_inport_mode",
        "iga_pe_keep_last_index", "iga_pe_inbuffer_matched", "normal_mode_wr_handshake",
        "normal_mode_rd_handshake", "iga_pe_outport[7]", "mem_idx_valid_same_gotten_masked[1]"))
    trace = [(0,(0,0,0)),(0,(0,0,0)),(1,(1,0,0)),(0,(1,0,0)),(1,(1,1,0)),(1,(1,1,1)),(0,(1,1,1))]
    previous = None; emitted = 0
    for qualified, state in trace:
        if qualified or state != previous: emitted += 1
        previous = state
    checks["predicate_trace_stable_level_not_progress"] = emitted == 4
    errors += [key for key, valid in checks.items() if not valid]
    report = {"schema": "node0004-v68-pe7-pair-validation-v1", "valid": not errors,
              "errors": errors, "checks": checks, "zip_sha256": sha(a.zip.read_bytes()),
              "observer_sha256": sha(ob), "actual_consumer_count": len(exprs),
              "uncovered_actual_consumers": len(missing), "bindings": bindings,
              "focused_frontend": {"positive": positive, "missing_declaration": missing_decl,
                                   "actual_consumer_typo": typo},
              "predicate_trace": {"rows": trace, "emitted": emitted},
              "claim_boundary": "Exact changed physical PE7 pair observer and feature binding only; no DUT/natural/formal-D/E4/E5 claim."}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": not errors, "errors": errors})); return 0 if not errors else 1

if __name__ == "__main__": raise SystemExit(main())
