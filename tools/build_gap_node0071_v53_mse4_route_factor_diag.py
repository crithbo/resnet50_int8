#!/usr/bin/env python3
"""Build GAP node0071 v53 MSE4 local/global route-factor diagnostic."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import build_gap_node0071_v52_ga_read_mse4_direct_diag as base


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "r5_n71_gap_v52_ga_read_mse4_direct_diag"
INSTALL = "r5_n71_gap_v53_mse4_route_factor_diag"
SOURCE_SHA = "1dfa3f28687f2725ea22579a05871b0353d2302914062225ecd13ac5784938ef"
RETURN_SHA = "8cc238e12154f0ef8a671ea7be4c2df60b68d42c27a2c10d62517dd864ae987d"
SERVER_RULE_SHA = "1fa6d9be4894d914e1f7b1889b0f62c7ed43f661e77de2afd1b97472b2be019c"
INDEX_SHA = "b3c5d7dcfb5a6417d38448f98e0cecac716ec05568aa454c4a99f447b1e69378"

base.SOURCE = SOURCE
base.INSTALL = INSTALL
base.base.SOURCE = SOURCE
base.base.INSTALL = INSTALL
base.base.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
base.base.SOURCE_SHA = SOURCE_SHA
base.base.RETURN_SHA = RETURN_SHA
base.base.SERVER_RULE_SHA = SERVER_RULE_SHA
base.base.INDEX_SHA = INDEX_SHA

PAIR_NAMES = (
    "pre_req", "pre_wdata", "local_req", "local_wdata",
    "global_req_in", "global_wdata_in", "global_req_out", "global_wdata_out",
)
PROGRESS_FIELDS = ("ob_rd",) + tuple(
    f"{name}_{suffix}{ch}" for name in PAIR_NAMES for suffix in ("hs",) for ch in range(2)
) + ("finish",)
FACTOR_FIELDS = ("remote",) + tuple(
    f"{name}_{suffix}{ch}" for name in PAIR_NAMES for suffix in ("v", "r") for ch in range(2)
)
FIELDS = PROGRESS_FIELDS + FACTOR_FIELDS


def xmr(group: str, slice_: str, leaf: str) -> str:
    return (
        f"u_NDP_Top_new.slice_with_datahub_mc_group_gen[{group}]"
        f".u_slice_with_datahub_mc_group.slice_group_gen[{slice_}]"
        f".u_slice_wrapper{leaf}"
    )


def make_observer_extension() -> str:
    out = [
        "", "    // v53: owner-clock qualified MSE4 local/global route factors.",
        "    // Stable factor levels and heartbeats are diagnostic state only.",
        "    logic [`GLB_SLICE_NUM-1:0] return_obs_v53_ob_rd_seen;",
        "    logic [`GLB_SLICE_NUM-1:0] return_obs_v53_finish_seen;",
        "    logic [`GLB_SLICE_NUM-1:0] return_obs_v53_remote_seen;",
    ]
    for name in PAIR_NAMES:
        for kind in ("v_seen", "r_seen", "hs_seen"):
            out.append(f"    logic [`GLB_SLICE_NUM-1:0] return_obs_v53_{name}_{kind} [0:1];")
    out += [
        f"    logic [{len(PROGRESS_FIELDS)}*`GLB_SLICE_NUM-1:0] return_obs_v53_prev_progress;",
        f"    logic [{len(FACTOR_FIELDS)}*`GLB_SLICE_NUM-1:0] return_obs_v53_prev_factor;",
        "    bit return_obs_v53_enabled;",
        "    longint unsigned return_obs_v53_db_cycles;",
        "    longint unsigned return_obs_v53_qualified_emit_count;",
        "    longint unsigned return_obs_v53_factor_emit_count;",
        "",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] return_obs_v53_pre_req_v_mon;",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] return_obs_v53_pre_req_r_mon;",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] return_obs_v53_pre_wdata_v_mon;",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] return_obs_v53_pre_wdata_r_mon;",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0] return_obs_v53_remote_mon;",
    ]
    for name in ("local_req", "local_wdata", "global_req_in", "global_wdata_in", "global_req_out", "global_wdata_out"):
        out.append(f"    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] return_obs_v53_{name}_v_mon;")
        out.append(f"    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] return_obs_v53_{name}_r_mon;")
    out += ["", "    generate", "        for (genvar v53_g=0; v53_g<`SLICE_GROUP_SIZE; v53_g++) begin : RETURN_OBS_V53_G", "            for (genvar v53_s=0; v53_s<`SLICE_GROUP_NUM; v53_s++) begin : RETURN_OBS_V53_S"]
    assign = {
        "pre_req_v": ".slice_mse2hub_req_valid[4][v53_ch]",
        "pre_req_r": ".slice_hub2mse_req_ready[4][v53_ch]",
        "pre_wdata_v": ".slice_mse2hub_wdata_valid[4][v53_ch]",
        "pre_wdata_r": ".slice_hub2mse_wdata_ready[4][v53_ch]",
        "local_req_v": ".slice_local_req_valid[4][v53_ch]",
        "local_req_r": ".slice_local_req_ready[4][v53_ch]",
        "local_wdata_v": ".slice_local_wdata_valid[4][v53_ch]",
        "local_wdata_r": ".slice_local_wdata_ready[4][v53_ch]",
        "global_req_in_v": ".u_slice2hub_crossbar.slice_global_req_fifo_in_valid[v53_ch]",
        "global_req_in_r": ".u_slice2hub_crossbar.slice_global_req_fifo_in_ready[v53_ch]",
        "global_wdata_in_v": ".u_slice2hub_crossbar.slice_global_wdata_fifo_in_valid[v53_ch]",
        "global_wdata_in_r": ".u_slice2hub_crossbar.slice_global_wdata_fifo_in_ready[v53_ch]",
        "global_req_out_v": ".slice_global_req_valid[v53_ch]",
        "global_req_out_r": ".slice_global_req_ready[v53_ch]",
        "global_wdata_out_v": ".slice_global_wdata_valid[v53_ch]",
        "global_wdata_out_r": ".slice_global_wdata_ready[v53_ch]",
    }
    out.append("                assign return_obs_v53_remote_mon[v53_g][v53_s] = " + xmr("v53_g", "v53_s", ".u_slice2hub_crossbar.slice_remote_req_flag[4]") + ";")
    out.append("                for (genvar v53_ch=0; v53_ch<2; v53_ch++) begin : RETURN_OBS_V53_CH")
    for name, leaf in assign.items():
        out.append(f"                    assign return_obs_v53_{name}_mon[v53_g][v53_s][v53_ch] = {xmr('v53_g','v53_s',leaf)};")
    out += ["                end", "            end", "        end", "    endgenerate", ""]
    out += [
        "    initial begin",
        "        return_obs_v53_enabled = $test$plusargs(\"RETURN_OBS_MSE4_ROUTE_FACTOR\");",
        "        return_obs_v53_db_cycles = 0; return_obs_v53_qualified_emit_count = 0; return_obs_v53_factor_emit_count = 0;",
        "        return_obs_v53_prev_progress = '0; return_obs_v53_prev_factor = '0;",
        "        #0;",
        "        if (return_obs_enabled && return_obs_v53_enabled && return_obs_fd != 0) begin",
        "            $fdisplay(return_obs_fd, \"# mse4_route_factor=1 selected_mask=0x0000ffff owner=clk_sg reporter=clk_db qualified_limit=384 factor_limit=128 heartbeat_cycles=1048576 state_or_heartbeat_is_progress=0 private_xmr=slice2hub_crossbar_fifo_only\");",
        "            $fflush(return_obs_fd);",
        "        end",
        "    end", "",
        "    always @(posedge u_NDP_Top_new.clk_sg or negedge u_NDP_Top_new.rst_n_sg) begin",
        "        if (!u_NDP_Top_new.rst_n_sg) begin",
        "            return_obs_v53_ob_rd_seen <= '0; return_obs_v53_finish_seen <= '0; return_obs_v53_remote_seen <= '0;",
    ]
    for name in PAIR_NAMES:
        for kind in ("v_seen", "r_seen", "hs_seen"):
            out.append(f"            return_obs_v53_{name}_{kind}[0] <= '0; return_obs_v53_{name}_{kind}[1] <= '0;")
    out += [
        "        end else if (return_obs_enabled && return_obs_v53_enabled) begin",
        "            for (int g=0; g<`SLICE_GROUP_SIZE; g++) begin",
        "                for (int s=0; s<`SLICE_GROUP_NUM; s++) begin",
        "                    int id; id = g*`SLICE_GROUP_NUM+s;",
        "                    if (|return_obs_pair_m4_ob_rd_mon[g][s]) return_obs_v53_ob_rd_seen[id] <= 1'b1;",
        "                    if (return_obs_pair_m4_finish_mon[g][s]) return_obs_v53_finish_seen[id] <= 1'b1;",
        "                    if (return_obs_v53_remote_mon[g][s]) return_obs_v53_remote_seen[id] <= 1'b1;",
        "                    for (int ch=0; ch<2; ch++) begin",
    ]
    for name in PAIR_NAMES:
        out.append(f"                        if (return_obs_v53_{name}_v_mon[g][s][ch]) return_obs_v53_{name}_v_seen[ch][id] <= 1'b1;")
        out.append(f"                        if (return_obs_v53_{name}_r_mon[g][s][ch]) return_obs_v53_{name}_r_seen[ch][id] <= 1'b1;")
        out.append(f"                        if (return_obs_v53_{name}_v_mon[g][s][ch] && return_obs_v53_{name}_r_mon[g][s][ch]) return_obs_v53_{name}_hs_seen[ch][id] <= 1'b1;")
    out += ["                    end", "                end", "            end", "        end", "    end", ""]
    progress_expr = ["return_obs_v53_ob_rd_seen"] + [f"return_obs_v53_{name}_hs_seen[{ch}]" for name in PAIR_NAMES for ch in range(2)] + ["return_obs_v53_finish_seen"]
    factor_expr = ["return_obs_v53_remote_seen"] + [f"return_obs_v53_{name}_{kind}_seen[{ch}]" for name in PAIR_NAMES for kind in ("v", "r") for ch in range(2)]
    out += [
        "    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin",
        f"        logic [{len(PROGRESS_FIELDS)}*`GLB_SLICE_NUM-1:0] progress_snapshot;",
        f"        logic [{len(FACTOR_FIELDS)}*`GLB_SLICE_NUM-1:0] factor_snapshot;",
        "        bit progress_changed, factor_changed, heartbeat;",
        "        if (!u_NDP_Top_new.rst_n_db) begin",
        "            return_obs_v53_db_cycles = 0; return_obs_v53_qualified_emit_count = 0; return_obs_v53_factor_emit_count = 0;",
        "            return_obs_v53_prev_progress = '0; return_obs_v53_prev_factor = '0;",
        "        end else if (return_obs_enabled && return_obs_v53_enabled && return_obs_fd != 0) begin",
        "            return_obs_v53_db_cycles++;",
        "            progress_snapshot = {" + ",".join(progress_expr) + "};",
        "            factor_snapshot = {" + ",".join(factor_expr) + "};",
        "            progress_changed = progress_snapshot != return_obs_v53_prev_progress;",
        "            factor_changed = factor_snapshot != return_obs_v53_prev_factor;",
        "            heartbeat = (return_obs_v53_db_cycles % 1048576) == 0;",
        "            if ((progress_changed && return_obs_v53_qualified_emit_count < 384) ||",
        "                (!progress_changed && factor_changed && return_obs_v53_factor_emit_count < 128) || heartbeat) begin",
        "                if (progress_changed) return_obs_v53_qualified_emit_count++;",
        "                else if (factor_changed) return_obs_v53_factor_emit_count++;",
    ]
    fmt = "%0t | MSE4_ROUTE_FACTOR_V1 | event=%s qn=%0d fn=%0d db_cycle=%0d " + " ".join(f"{name}=0x%0h" for name in FIELDS)
    args = ["$time", "(progress_changed ? \"QUALIFIED_EDGE\" : (factor_changed ? \"FACTOR_EDGE\" : \"HEARTBEAT\"))", "return_obs_v53_qualified_emit_count", "return_obs_v53_factor_emit_count", "return_obs_v53_db_cycles"]
    for name in FIELDS:
        if name == "ob_rd": args.append("return_obs_v53_ob_rd_seen")
        elif name == "finish": args.append("return_obs_v53_finish_seen")
        elif name == "remote": args.append("return_obs_v53_remote_seen")
        else:
            stem, ch = name[:-1], name[-1]
            pair, kind = stem.rsplit("_", 1)
            args.append(f"return_obs_v53_{pair}_{kind}_seen[{ch}]")
    out += [
        f"                $fdisplay(return_obs_fd, \"{fmt}\",",
        "                    " + ",\n                    ".join(args) + ");",
        "                $fflush(return_obs_fd);",
        "            end",
        "            return_obs_v53_prev_progress = progress_snapshot; return_obs_v53_prev_factor = factor_snapshot;",
        "        end",
        "    end",
    ]
    return "\n".join(out) + "\n"


def make_parser() -> str:
    fields = repr(FIELDS)
    progress = repr(PROGRESS_FIELDS)
    return f'''#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
FIELDS={fields}
PROGRESS_FIELDS={progress}
PATTERN=re.compile(r"MSE4_ROUTE_FACTOR_V1\\s+\\|\\s+event=(QUALIFIED_EDGE|FACTOR_EDGE|HEARTBEAT).*?"+r"\\s+".join(fr"{{n}}=0x([0-9a-fA-F]+)" for n in FIELDS))
def decide(text):
    progress={{n:0 for n in PROGRESS_FIELDS}}; factors={{n:0 for n in FIELDS if n not in PROGRESS_FIELDS}}
    counts={{"QUALIFIED_EDGE":0,"FACTOR_EDGE":0,"HEARTBEAT":0}}; witnesses={{}}
    for m in PATTERN.finditer(text):
        event=m.group(1); counts[event]+=1; vals={{n:int(m.group(i+2),16) for i,n in enumerate(FIELDS)}}
        if event=="QUALIFIED_EDGE":
            for n in PROGRESS_FIELDS: progress[n]|=vals[n]
        for n in factors:
            factors[n]|=vals[n]
            if vals[n] and n not in witnesses: witnesses[n]={{"first_record_event":event,"first_record_ordinal":sum(counts.values())}}
            if vals[n]: witnesses[n]["last_record_event"]=event; witnesses[n]["last_record_ordinal"]=sum(counts.values())
    rows=[]
    for sid in range(16):
        bit=1<<sid; p={{n:bool(v&bit) for n,v in progress.items()}}; f={{n:bool(v&bit) for n,v in factors.items()}}
        ch=lambda prefix:any(p.get(prefix+str(c),False) for c in range(2))
        sf=lambda prefix:any(f.get(prefix+str(c),False) for c in range(2))
        if not p["ob_rd"]: boundary="MSE4_OUTBUFFER_READ_ABSENT"
        elif not sf("pre_req_v"): boundary="MSE4_PRECROSSBAR_REQUEST_VALID_ABSENT"
        elif f["remote"]:
            if not sf("global_req_in_v"): boundary="GLOBAL_REQUEST_FIFO_INPUT_VALID_ABSENT"
            elif not ch("global_req_in_hs"): boundary="GLOBAL_REQUEST_FIFO_INPUT_READY_BLOCK"
            elif sf("pre_wdata_v") and not ch("global_wdata_in_hs"): boundary="GLOBAL_WDATA_FIFO_INPUT_READY_BLOCK"
            elif not sf("global_req_out_v"): boundary="GLOBAL_REQUEST_FIFO_TO_OUTPUT_VALID_ABSENT"
            elif not ch("global_req_out_hs"): boundary="GLOBAL_REQUEST_OUTPUT_READY_BLOCK"
            elif sf("pre_wdata_v") and not ch("global_wdata_out_hs"): boundary="GLOBAL_WDATA_OUTPUT_READY_BLOCK"
            elif not p["finish"]: boundary="REMOTE_ROUTE_ACCEPTED_FINISH_ABSENT"
            else: boundary="REMOTE_ROUTE_AND_FINISH_OBSERVED"
        else:
            if not sf("local_req_v"): boundary="LOCAL_REQUEST_VALID_ABSENT_AFTER_ROUTE_SELECT"
            elif not ch("local_req_hs"): boundary="LOCAL_REQUEST_READY_BLOCK"
            elif sf("pre_wdata_v") and not ch("local_wdata_hs"): boundary="LOCAL_WDATA_READY_BLOCK"
            elif not p["finish"]: boundary="LOCAL_ROUTE_ACCEPTED_FINISH_ABSENT"
            else: boundary="LOCAL_ROUTE_AND_FINISH_OBSERVED"
        rows.append({{"slice":sid,"route":"REMOTE" if f["remote"] else "LOCAL_OR_UNSEEN","first_missing":boundary,"progress":p,"factor_seen_high":f}})
    marker="# mse4_route_factor=1" in text
    return {{"schema":"gap-node0071-mse4-route-factor-decision-v1","feature_enabled_marker":marker,"record_counts":counts,
      "stable_level_or_heartbeat_is_progress":False,"progress_masks":{{k:f"0x{{v:04x}}" for k,v in progress.items()}},
      "factor_seen_high_masks":{{k:f"0x{{v:04x}}" for k,v in factors.items()}},"factor_witnesses":witnesses,"per_slice":rows,
      "status":"DIAGNOSTIC_EVIDENCE_AVAILABLE" if marker and counts["QUALIFIED_EDGE"] else "FAIL_CLOSED","natural_terminal":False}}
def line(event,**kw):
    vals={{n:kw.get(n,0) for n in FIELDS}}
    return "0 | MSE4_ROUTE_FACTOR_V1 | event="+event+" qn=1 fn=1 db_cycle=1 "+" ".join(f"{{n}}=0x{{vals[n]:x}}" for n in FIELDS)
def self_test():
    marker="# mse4_route_factor=1\\n"; local={{"ob_rd":1,"pre_req_v0":1,"pre_req_r0":1,"pre_req_hs0":1,"local_req_v0":1,"local_req_r0":1,"local_req_hs0":1,"finish":1}}
    remote={{"ob_rd":2,"remote":2,"pre_req_v0":2,"pre_req_r0":2,"pre_req_hs0":2,"global_req_in_v0":2,"global_req_in_r0":2,"global_req_in_hs0":2,"global_req_out_v0":2,"global_req_out_r0":2,"global_req_out_hs0":2,"finish":2}}
    stable=decide(marker+line("HEARTBEAT",**{{n:4 for n in FIELDS}})); block=dict(remote); block.pop("global_req_in_r0"); block.pop("global_req_in_hs0")
    sim={{n:0xffff for n in FIELDS}}; checks={{
      "local_route":decide(marker+line("QUALIFIED_EDGE",**local))["per_slice"][0]["first_missing"]=="LOCAL_ROUTE_AND_FINISH_OBSERVED",
      "remote_route":decide(marker+line("QUALIFIED_EDGE",**remote))["per_slice"][1]["first_missing"]=="REMOTE_ROUTE_AND_FINISH_OBSERVED",
      "fifo_ready_block":decide(marker+line("QUALIFIED_EDGE",**block))["per_slice"][1]["first_missing"]=="GLOBAL_REQUEST_FIFO_INPUT_READY_BLOCK",
      "stable_not_progress":stable["record_counts"]["QUALIFIED_EDGE"]==0 and stable["status"]=="FAIL_CLOSED",
      "simultaneous":len(decide(marker+line("QUALIFIED_EDGE",**sim))["per_slice"])==16,
    }}
    return {{"schema":"gap-node0071-mse4-route-factor-self-test-v1","checks":checks,"pass":all(checks.values())}}
def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("analyze"); a.add_argument("--observer-log",type=Path,required=True); a.add_argument("--output",type=Path,required=True)
    s=sub.add_parser("self-test"); s.add_argument("--output",type=Path,required=True); ns=ap.parse_args()
    value=self_test() if ns.cmd=="self-test" else decide(ns.observer_log.read_text(encoding="utf-8",errors="replace") if ns.observer_log.is_file() else "")
    ns.output.write_text(json.dumps(value,indent=2,sort_keys=True)+"\\n",encoding="utf-8")
    return 0 if (value.get("pass",True) and (ns.cmd=="self-test" or value["status"]!="FAIL_CLOSED")) else 1
if __name__=="__main__": raise SystemExit(main())
'''


def patch_observer(package: Path) -> None:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "MSE4_ROUTE_FACTOR_V1" in text:
        raise base.base.BuildError("v53 observer already present")
    path.write_text(text + make_observer_extension(), encoding="utf-8", newline="\n")
    (package / "package_tools/gap_node0071_mse4_route_factor_decision.py").write_text(make_parser(), encoding="utf-8", newline="\n")


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    tool = 'gadirect_tool="$package_root/package_tools/gap_node0071_ga_read_mse4_direct_decision.py"'
    if text.count(tool) != 2:
        raise base.base.BuildError("v52 tool declaration differs")
    text = text.replace(tool, tool + '\nroutefactor_tool="$package_root/package_tools/gap_node0071_mse4_route_factor_decision.py"')
    text = base.base.replace_once(text,
        "       grep -Fq 'GA_READ_MSE4_DIRECT_V1' \"$observer_log\"; then",
        "       grep -Fq 'GA_READ_MSE4_DIRECT_V1' \"$observer_log\" &&\n       grep -Fq 'mse4_route_factor=1' \"$observer_log\" &&\n       grep -Fq 'MSE4_ROUTE_FACTOR_V1' \"$observer_log\"; then", "v53 binding positive")
    text = base.base.replace_once(text, "ga_read_mse4_direct_records_returned=true\\n'", "ga_read_mse4_direct_records_returned=true\\nmse4_route_factor_enabled=true\\nmse4_route_factor_records_returned=true\\n'", "v53 binding true")
    text = base.base.replace_once(text, "ga_read_mse4_direct_records_returned=false\\n'", "ga_read_mse4_direct_records_returned=false\\nmse4_route_factor_enabled=false\\nmse4_route_factor_records_returned=false\\n'", "v53 binding false")
    status = '      printf "ga_read_mse4_direct=%s\\n" "$?" >>"$evidence_root/decision_parser_status.txt"'
    parse = '      python3 "$routefactor_tool" analyze --observer-log "$observer_log" --output "$evidence_root/mse4_route_factor_decision.json" >/dev/null 2>>"$evidence_root/decision_parser_stderr.log"\n      printf "mse4_route_factor=%s\\n" "$?" >>"$evidence_root/decision_parser_status.txt"'
    text = base.base.replace_once(text, status, status + "\n" + parse, "v53 parser call")
    old = '"$evidence_root/ga_read_mse4_direct_decision.json"       "$evidence_root/canonical_decision.json"'
    text = base.base.replace_once(text, old, '"$evidence_root/ga_read_mse4_direct_decision.json"       "$evidence_root/mse4_route_factor_decision.json"       "$evidence_root/canonical_decision.json"', "v53 fallback argv")
    text = base.base.replace_once(text,
        '{"schema":"canonical-diagnostic-decision-v1","decision":"FAIL_CLOSED",',
        '{"schema":"gap-node0071-mse4-route-factor-decision-v1","status":"FAIL_CLOSED",\n     "reason":reason,"natural_terminal":False},\n    {"schema":"canonical-diagnostic-decision-v1","decision":"FAIL_CLOSED",', "v53 fallback payload")
    text = base.base.replace_once(text, '"signal":sys.argv[8],"simulation_status":int(sys.argv[9]),', '"signal":sys.argv[9],"simulation_status":int(sys.argv[10]),', "v53 fallback indices")
    text = base.base.replace_once(text, "for name,payload in zip(sys.argv[1:8],payloads):", "for name,payload in zip(sys.argv[1:9],payloads):", "v53 fallback output set")
    selftest = 'python3 "$gadirect_tool" self-test --output "$evidence_root/ga_read_mse4_direct_predicate_self_test.json" >/dev/null || runner_fail 8 "GA-read MSE4 direct predicate self-test failed"'
    text = base.base.replace_once(text, selftest, selftest + '\npython3 "$routefactor_tool" self-test --output "$evidence_root/mse4_route_factor_predicate_self_test.json" >/dev/null || runner_fail 8 "MSE4 route-factor predicate self-test failed"', "v53 self-test")
    text = base.base.replace_once(text, "  +RETURN_OBS_GA_READ_MSE4_DIRECT", "  +RETURN_OBS_GA_READ_MSE4_DIRECT\n  +RETURN_OBS_MSE4_ROUTE_FACTOR", "v53 plusarg")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/gap_node0071_complete_server_runtime.py"
    text = path.read_text(encoding="utf-8")
    text = base.base.replace_once(text, "len(allowlist) != 85", "len(allowlist) != 87", "v53 return allowlist")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_contract(package: Path) -> None:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    additions = value["path_budget"]["additional_projected_paths"]
    for rel in (
        f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/mse4_route_factor_decision.json",
        f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/mse4_route_factor_predicate_self_test.json",
    ):
        if rel not in additions: additions.append(rel)
    additions.sort()
    attempt = "a" * int(value["path_budget"]["attempt_max_chars"])
    longest=max((x.replace("{attempt}",attempt).replace("{name}",INSTALL) for x in additions),key=lambda x:(len(x),x))
    value["path_budget"]["max_projected_absolute_path_chars"] = int(value["path_budget"]["declared_target_root_max_chars"])+1+len(longest)
    base.base.write_json(path,value)


def patch_manifest(package: Path) -> None:
    path=package/"TEST_PACKAGE_MANIFEST.json"; value=json.loads(path.read_text(encoding="utf-8"))
    value.update({"install_name":INSTALL,"package_name":f"{INSTALL}.zip","return_name":f"{INSTALL}_return","test_id":"r5-gap-node0071-v53-mse4-route-factor-diagnostic"})
    value["source_package"]={"install_name":SOURCE,"sha256":SOURCE_SHA,"return_sha256":RETURN_SHA,"return_analysis":"artifacts/operator_config_validation/r5-gap-node0071-v52-return-analysis/report.json"}
    value["rule_receipts"]["server_package_rule_sha256"]=SERVER_RULE_SHA; value["rule_receipts"]["generation_index_sha256"]=INDEX_SHA
    value["mse4_route_factor_contract"]={
      "feature":"MSE4_ROUTE_FACTOR_V1","plusarg":"+RETURN_OBS_MSE4_ROUTE_FACTOR","selected_mask":"0x0000ffff",
      "owner_clock":"clk_sg","reporter_clock":"clk_db","qualified_emit_limit":384,"factor_emit_limit":128,"heartbeat_cycles":1048576,
      "state_factor_or_heartbeat_is_progress":False,"candidate_matrix":[
        {"candidate":"MSE4 pre-crossbar valid absent","observations":["pre_req_v","pre_wdata_v"]},
        {"candidate":"local route ready block","observations":["remote","local_req_v/r/hs","local_wdata_v/r/hs"]},
        {"candidate":"global FIFO input block","observations":["remote","global_req_in_v/r/hs","global_wdata_in_v/r/hs"]},
        {"candidate":"global output block","observations":["global_req_out_v/r/hs","global_wdata_out_v/r/hs"]},
        {"candidate":"accepted route but no completion","observations":["finish"]}],
      "public_surface_or_xmr":{"public_or_wrapper":["Slice_Wrapper slice_mse2hub_* and slice_hub2mse_*","Slice_Wrapper slice_local_*","Slice_Wrapper slice_global_*"],"private_xmr":["slice2hub_crossbar.slice_remote_req_flag[4]","slice_global_{req,wdata}_fifo_in_{valid,ready}"],"private_xmr_reason":"no equivalent exported pre-FIFO route/fill surface"},
      "classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"}
    for row in (
      {"source_root":"evidence","source_path":"mse4_route_factor_decision.json","target_path":"evidence/mse4_route_factor_decision.json","required":True,"max_bytes":196608,"missing_meaning":"MSE4 route-factor decision absent"},
      {"source_root":"evidence","source_path":"mse4_route_factor_predicate_self_test.json","target_path":"evidence/mse4_route_factor_predicate_self_test.json","required":True,"max_bytes":32768,"missing_meaning":"MSE4 route-factor predicate self-test absent"},):
        if row["target_path"] not in {x["target_path"] for x in value["return_allowlist"]}: value["return_allowlist"].append(row)
    value["budgets"]["return_extracted_max_bytes"]+=229376; value["budgets"]["return_zip_max_bytes"]+=131072
    value["release_gate_matrix"]=[
      {"gate_id":"PACKAGE_BOOTSTRAP_RUNTIME_LAYOUT","applicability":"blocking_applicable_identity_and_runner_changed","status":"PASS_PENDING_FINAL_ZIP_VALIDATION"},
      {"gate_id":"PACKAGE_LOCAL_HDL","applicability":"blocking_applicable_observer_changed_public_plus_exact_private_xmr","status":"PASS_PENDING_CHANGED_SURFACE_SCOPE_VALIDATION"},
      {"gate_id":"DIAGNOSTIC_SEMANTICS","applicability":"blocking_applicable_predicate_changed","status":"PASS_PENDING_EXACT_TRACE"},
      {"gate_id":"MATERIALIZED_CONFIG","applicability":"receipt_reuse_byte_equal","status":"PASS"},
      {"gate_id":"RETURN_RESULT_CONTRACT","applicability":"blocking_applicable_parser_finalizer_changed","status":"PASS_PENDING_SIGNAL_FINALIZER_VALIDATION"},
      {"gate_id":"FROZEN_NUMERIC_GOLDEN","applicability":"record_only_byte_equal","status":"PASS"}]
    value.update({"candidate_release":False,"package_class":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","evidence_level":"E2_LOCAL_COMPLETE_NODE","numeric_analysis_repeated":False,"sum_or_tail_numeric_reexecuted":False,"functional_rtl_modified":False})
    runtime=json.loads((package/"SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(encoding="utf-8")); attempt="a"*int(runtime["path_budget"]["attempt_max_chars"])
    projected={f"install/cfg_pkg/{INSTALL}/"+p.relative_to(package/"workload").as_posix() for p in (package/"workload").rglob("*") if p.is_file()}|{x.replace("{attempt}",attempt).replace("{name}",INSTALL) for x in runtime["path_budget"]["additional_projected_paths"]}
    longest=max(projected,key=lambda x:(len(x),x)); root_max=int(runtime["path_budget"]["declared_target_root_max_chars"])
    value["path_length_budget"].update({"longest_projected_relative_path":longest,"longest_projected_relative_path_chars":len(longest),"max_projected_absolute_path_chars":root_max+1+len(longest),"pass":root_max+1+len(longest)<=int(value["path_length_budget"]["absolute_path_limit_chars"])})
    value["files"]=base.base.files_map(package); base.base.write_json(path,value); value["files"]=base.base.files_map(package); base.base.write_json(path,value)


def build(output: Path) -> Path:
    package=output/INSTALL
    if package.exists(): raise base.base.BuildError(f"refusing to overwrite {package}")
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gap-v53-source-") as temp: shutil.copytree(base.base.extract_source(Path(temp)),package)
    base.base.replace_identity(package); patch_observer(package); patch_runner(package); patch_runtime(package); patch_contract(package)
    base.base.write_json(package/"provenance/v52_to_v53_mse4_route_factor.json",{
      "schema":"gap-node0071-v52-to-v53-mse4-route-factor-v1","source_zip_sha256":SOURCE_SHA,"return_sha256":RETURN_SHA,
      "classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","last_proven_good":"ALL_16_SLICES_MSE4_OUTPUT_BUFFER_READ_ACCEPTED",
      "first_divergence":"MSE4_OUTPUT_BUFFER_READ_TO_LOCAL_OR_GLOBAL_REQUEST_ACCEPTANCE_SLICES1_15",
      "changed_surface":["fresh identity","owner-clock MSE4 local/global route-factor observer/parser","manifest/return allowlist/provenance"],
      "frozen":["73 numeric/workload/config/golden files","sum and exact uint8 tail semantics","final JSON/mapping/bitstream/execplan/SCA except identity text","timeout and backpressure","functional RTL","repeat-safe owned reset and unique return semantics"],
      "server_action":False})
    (package/"README.md").write_text(
      "# GAP node0071 v53 MSE4 route-factor diagnostic\n\nClassification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
      "This successor freezes v52 numeric/config/workload/golden, timeout, backpressure and functional RTL. It distinguishes MSE4 pre-crossbar, local, global FIFO-input, global-output and finish boundaries for both request channels in one run. Stable factor state and heartbeats never count as qualified progress.\n\n"
      f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\nEach execution publishes one unique return under `/home/panqs/ndp/simresult`.\n",encoding="utf-8",newline="\n")
    patch_manifest(package); return package


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,required=True); ns=ap.parse_args(); output=ns.output.resolve(); package=build(output)
    target=output/f"{INSTALL}.zip"; base.base.deterministic_zip(package,target); sidecar=Path(str(target)+".sha256")
    sidecar.write_text(f"{base.base.digest(target)}  {target.name}\n",encoding="ascii",newline="\n")
    print(json.dumps({"package":str(package),"zip":str(target),"bytes":target.stat().st_size,"sha256":base.base.digest(target),"sidecar":str(sidecar),"sidecar_sha256":base.base.digest(sidecar)},indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
