#!/usr/bin/env python3
"""Build GAP node0071 v52 qualified GA-read to MSE4 direct-consumer diagnostic."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import build_gap_node0071_v51_ga_outbuffer_mode_factor_diag as base


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "r5_n71_gap_v51_ga_ob_mode_factor_diag"
INSTALL = "r5_n71_gap_v52_ga_read_mse4_direct_diag"
SOURCE_SHA = "76336937dd52822e948dcc81c6f35054c73d0066dfad5f964b6753a04a78f7b4"
RETURN_SHA = "819f61a97a75497d6cae0de7babe64c5a508243df4caa44ac20ea61f1e5005e0"
SERVER_RULE_SHA = "1fa6d9be4894d914e1f7b1889b0f62c7ed43f661e77de2afd1b97472b2be019c"
INDEX_SHA = "b3c5d7dcfb5a6417d38448f98e0cecac716ec05568aa454c4a99f447b1e69378"

base.SOURCE = SOURCE
base.INSTALL = INSTALL
base.SOURCE_ZIP = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
base.SOURCE_SHA = SOURCE_SHA
base.RETURN_SHA = RETURN_SHA
base.SERVER_RULE_SHA = SERVER_RULE_SHA
base.INDEX_SHA = INDEX_SHA


OBSERVER_EXTENSION = r'''

    // v52: qualified-only all-slice GA selected-read to MSE4 direct consumer.
    // Existing package-local monitor surfaces are reused; no new DUT XMR is
    // introduced. State/heartbeat records cannot consume the event budget.
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_mode_normal_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_mode_transout_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_selected_wr_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_nonempty_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_selected_rd_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_m4_idx_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_m4_req_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_m4_q_wr_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_m4_q_rd_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_m4_buf_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_m4_prep_wr_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_m4_prep_rd_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_m4_ob_wr_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_m4_ob_rd_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_m4_local_req_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_m4_local_wdata_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v52_finish_seen;
    logic [17*`GLB_SLICE_NUM-1:0] return_obs_v52_prev_qualified;
    bit return_obs_v52_enabled;
    longint unsigned return_obs_v52_db_cycles;
    longint unsigned return_obs_v52_emit_count;

    initial begin
        return_obs_v52_enabled =
            $test$plusargs("RETURN_OBS_GA_READ_MSE4_DIRECT");
        return_obs_v52_db_cycles = 0;
        return_obs_v52_emit_count = 0;
        return_obs_v52_prev_qualified = '0;
        #0;
        if (return_obs_enabled && return_obs_v52_enabled &&
            return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "# ga_read_mse4_direct=1 selected_mask=0x0000ffff owner=clk_sg reporter=clk_db qualified_limit=320 heartbeat_cycles=1048576 reused_package_local_surfaces=1"
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin
        if (!u_NDP_Top_new.rst_n_sg) begin
            return_obs_v52_mode_normal_seen <= '0;
            return_obs_v52_mode_transout_seen <= '0;
            return_obs_v52_selected_wr_seen <= '0;
            return_obs_v52_nonempty_seen <= '0;
            return_obs_v52_selected_rd_seen <= '0;
            return_obs_v52_m4_idx_seen <= '0;
            return_obs_v52_m4_req_seen <= '0;
            return_obs_v52_m4_q_wr_seen <= '0;
            return_obs_v52_m4_q_rd_seen <= '0;
            return_obs_v52_m4_buf_seen <= '0;
            return_obs_v52_m4_prep_wr_seen <= '0;
            return_obs_v52_m4_prep_rd_seen <= '0;
            return_obs_v52_m4_ob_wr_seen <= '0;
            return_obs_v52_m4_ob_rd_seen <= '0;
            return_obs_v52_m4_local_req_seen <= '0;
            return_obs_v52_m4_local_wdata_seen <= '0;
            return_obs_v52_finish_seen <= '0;
        end
        else if (return_obs_enabled && return_obs_v52_enabled) begin
            for (int g = 0; g < `SLICE_GROUP_SIZE; g++) begin
                for (int s = 0; s < `SLICE_GROUP_NUM; s++) begin
                    int id;
                    bit mode_normal, mode_transout, selected_wr;
                    bit nonempty, selected_rd;
                    id = g * `SLICE_GROUP_NUM + s;
                    mode_normal = 1'b0;
                    mode_transout = 1'b0;
                    selected_wr = 1'b0;
                    nonempty = 1'b0;
                    selected_rd = 1'b0;
                    for (int r = 0; r < `GA_ROW_PE_NUM; r++) begin
                        for (int slot = 0; slot < 2; slot++) begin
                            bit pe_selected_wr, pe_selected_rd;
                            pe_selected_wr =
                                return_obs_ga_outbuffer_wr_mon[g][s][r][slot];
                            pe_selected_rd =
                                return_obs_v51_selected_rd_mon[g][s][r][slot];
                            selected_wr |= pe_selected_wr;
                            selected_rd |= pe_selected_rd;
                            nonempty |=
                                return_obs_ga_ob_count_mon[g][s][r][slot] != 0;
                            mode_normal |=
                                (pe_selected_wr || pe_selected_rd) &&
                                !return_obs_v51_is_transout_mon[g][s][r][slot];
                            mode_transout |=
                                (pe_selected_wr || pe_selected_rd) &&
                                return_obs_v51_is_transout_mon[g][s][r][slot];
                        end
                    end
                    if (mode_normal)
                        return_obs_v52_mode_normal_seen[id] <= 1'b1;
                    if (mode_transout)
                        return_obs_v52_mode_transout_seen[id] <= 1'b1;
                    if (selected_wr)
                        return_obs_v52_selected_wr_seen[id] <= 1'b1;
                    if (nonempty)
                        return_obs_v52_nonempty_seen[id] <= 1'b1;
                    if (selected_rd)
                        return_obs_v52_selected_rd_seen[id] <= 1'b1;
                    if (return_obs_mse4_idx_hs_mon[g][s])
                        return_obs_v52_m4_idx_seen[id] <= 1'b1;
                    if (return_obs_pair_m4_req_valid_mon[g][s] &&
                        return_obs_pair_m4_req_ready_mon[g][s])
                        return_obs_v52_m4_req_seen[id] <= 1'b1;
                    if (return_obs_pair_m4_q_wr_mon[g][s])
                        return_obs_v52_m4_q_wr_seen[id] <= 1'b1;
                    if (return_obs_pair_m4_q_rd_mon[g][s])
                        return_obs_v52_m4_q_rd_seen[id] <= 1'b1;
                    if (return_obs_pair_m4_buf_accept_mon[g][s])
                        return_obs_v52_m4_buf_seen[id] <= 1'b1;
                    if (return_obs_pair_m4_prep_wr_mon[g][s])
                        return_obs_v52_m4_prep_wr_seen[id] <= 1'b1;
                    if (return_obs_pair_m4_prep_rd_mon[g][s])
                        return_obs_v52_m4_prep_rd_seen[id] <= 1'b1;
                    if (|return_obs_pair_m4_ob_wr_mon[g][s])
                        return_obs_v52_m4_ob_wr_seen[id] <= 1'b1;
                    if (|return_obs_pair_m4_ob_rd_mon[g][s])
                        return_obs_v52_m4_ob_rd_seen[id] <= 1'b1;
                    if (|local_req_hs[g][s][4])
                        return_obs_v52_m4_local_req_seen[id] <= 1'b1;
                    if (|local_wdata_hs[g][s][4])
                        return_obs_v52_m4_local_wdata_seen[id] <= 1'b1;
                    if (return_obs_pair_m4_finish_mon[g][s])
                        return_obs_v52_finish_seen[id] <= 1'b1;
                end
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        logic [17*`GLB_SLICE_NUM-1:0] qualified_snapshot;
        bit qualified_changed;
        bit heartbeat;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_v52_db_cycles = 0;
            return_obs_v52_emit_count = 0;
            return_obs_v52_prev_qualified = '0;
        end
        else if (return_obs_enabled && return_obs_v52_enabled &&
                 return_obs_fd != 0) begin
            return_obs_v52_db_cycles++;
            qualified_snapshot = {
                return_obs_v52_finish_seen,
                return_obs_v52_m4_local_wdata_seen,
                return_obs_v52_m4_local_req_seen,
                return_obs_v52_m4_ob_rd_seen,
                return_obs_v52_m4_ob_wr_seen,
                return_obs_v52_m4_prep_rd_seen,
                return_obs_v52_m4_prep_wr_seen,
                return_obs_v52_m4_buf_seen,
                return_obs_v52_m4_q_rd_seen,
                return_obs_v52_m4_q_wr_seen,
                return_obs_v52_m4_req_seen,
                return_obs_v52_m4_idx_seen,
                return_obs_v52_selected_rd_seen,
                return_obs_v52_nonempty_seen,
                return_obs_v52_selected_wr_seen,
                return_obs_v52_mode_transout_seen,
                return_obs_v52_mode_normal_seen
            };
            qualified_changed =
                qualified_snapshot != return_obs_v52_prev_qualified;
            heartbeat = (return_obs_v52_db_cycles % 1048576) == 0;
            if ((qualified_changed && return_obs_v52_emit_count < 320) ||
                heartbeat) begin
                if (qualified_changed)
                    return_obs_v52_emit_count++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | GA_READ_MSE4_DIRECT_V1 | event=%s n=%0d db_cycle=%0d mode_normal=0x%0h mode_transout=0x%0h selected_wr=0x%0h nonempty=0x%0h selected_rd=0x%0h m4_idx=0x%0h m4_req=0x%0h m4_q_wr=0x%0h m4_q_rd=0x%0h m4_buf=0x%0h m4_prep_wr=0x%0h m4_prep_rd=0x%0h m4_ob_wr=0x%0h m4_ob_rd=0x%0h m4_local_req=0x%0h m4_local_wdata=0x%0h finish=0x%0h",
                    $time,
                    (qualified_changed ? "QUALIFIED_EDGE" : "HEARTBEAT"),
                    return_obs_v52_emit_count,
                    return_obs_v52_db_cycles,
                    return_obs_v52_mode_normal_seen,
                    return_obs_v52_mode_transout_seen,
                    return_obs_v52_selected_wr_seen,
                    return_obs_v52_nonempty_seen,
                    return_obs_v52_selected_rd_seen,
                    return_obs_v52_m4_idx_seen,
                    return_obs_v52_m4_req_seen,
                    return_obs_v52_m4_q_wr_seen,
                    return_obs_v52_m4_q_rd_seen,
                    return_obs_v52_m4_buf_seen,
                    return_obs_v52_m4_prep_wr_seen,
                    return_obs_v52_m4_prep_rd_seen,
                    return_obs_v52_m4_ob_wr_seen,
                    return_obs_v52_m4_ob_rd_seen,
                    return_obs_v52_m4_local_req_seen,
                    return_obs_v52_m4_local_wdata_seen,
                    return_obs_v52_finish_seen
                );
                $fflush(return_obs_fd);
            end
            return_obs_v52_prev_qualified = qualified_snapshot;
        end
    end
'''


PARSER = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path

FIELDS=("mode_normal","mode_transout","selected_wr","nonempty","selected_rd",
        "m4_idx","m4_req","m4_q_wr","m4_q_rd","m4_buf","m4_prep_wr",
        "m4_prep_rd","m4_ob_wr","m4_ob_rd","m4_local_req",
        "m4_local_wdata","finish")
PATTERN=re.compile(
  r"GA_READ_MSE4_DIRECT_V1\s+\|\s+event=(QUALIFIED_EDGE|HEARTBEAT).*?"+
  r"\s+".join(fr"{name}=0x([0-9a-fA-F]+)" for name in FIELDS))

def decide(text:str)->dict:
    masks={name:0 for name in FIELDS}; qualified=0; heartbeat=0
    for match in PATTERN.finditer(text):
        event=match.group(1)
        values={name:int(match.group(i+2),16) for i,name in enumerate(FIELDS)}
        if event=="QUALIFIED_EDGE":
            qualified+=1
            for name,value in values.items(): masks[name]|=value
        else: heartbeat+=1
    rows=[]
    for sid in range(16):
        seen={name:bool(masks[name]&(1<<sid)) for name in FIELDS}
        if not (seen["mode_normal"] or seen["mode_transout"]):
            boundary="ACTUAL_SELECTED_MODE_UNOBSERVED"
        elif not seen["selected_wr"]: boundary="SELECTED_WRITE_ABSENT"
        elif not seen["nonempty"]: boundary="NONEMPTY_ABSENT"
        elif not seen["selected_rd"]: boundary="SELECTED_READ_ABSENT"
        elif not seen["m4_idx"]: boundary="MSE4_INDEX_ACCEPT_ABSENT"
        elif not seen["m4_req"]: boundary="MSE4_REQUEST_ACCEPT_ABSENT"
        elif not seen["m4_q_wr"]: boundary="MSE4_QUEUE_WRITE_ABSENT"
        elif not seen["m4_q_rd"]: boundary="MSE4_QUEUE_READ_ABSENT"
        elif not seen["m4_buf"]: boundary="MSE4_BUFFER_ACCEPT_ABSENT"
        elif not seen["m4_prep_wr"]: boundary="MSE4_PREPARED_WRITE_ABSENT"
        elif not seen["m4_prep_rd"]: boundary="MSE4_PREPARED_READ_ABSENT"
        elif not seen["m4_ob_wr"]: boundary="MSE4_OUTBUFFER_WRITE_ABSENT"
        elif not seen["m4_ob_rd"]: boundary="MSE4_OUTBUFFER_READ_ABSENT"
        elif not seen["m4_local_req"]: boundary="MSE4_LOCAL_REQUEST_ABSENT"
        elif not seen["m4_local_wdata"]: boundary="MSE4_LOCAL_WDATA_ABSENT"
        elif not seen["finish"]: boundary="SLICE_FINISH_ABSENT"
        else: boundary="FULL_DIRECT_CHAIN_OBSERVED"
        rows.append({"slice":sid,"seen":seen,"first_missing":boundary})
    marker="# ga_read_mse4_direct=1" in text
    return {
      "schema":"gap-node0071-ga-read-mse4-direct-decision-v1",
      "feature_enabled_marker":marker,"qualified_record_count":qualified,
      "heartbeat_record_count":heartbeat,"stable_level_is_progress":False,
      "qualified_masks":{k:f"0x{v:04x}" for k,v in masks.items()},
      "per_slice":rows,"status":"DIAGNOSTIC_EVIDENCE_AVAILABLE"
        if marker and qualified else "FAIL_CLOSED","natural_terminal":False}

def line(event:str,**kw)->str:
    values={name:kw.get(name,0) for name in FIELDS}
    return ("0 | GA_READ_MSE4_DIRECT_V1 | event="+event+
            " n=1 db_cycle=1 "+" ".join(f"{k}=0x{v:x}" for k,v in values.items()))

def self_test()->dict:
    marker="# ga_read_mse4_direct=1\n"
    full={name:1 for name in FIELDS}; full["mode_transout"]=0
    trans={name:2 for name in FIELDS}; trans["mode_normal"]=0
    stable=decide(marker+line("HEARTBEAT",**{name:4 for name in FIELDS}))
    simultaneous=decide(marker+line("QUALIFIED_EDGE",**{name:0xffff for name in FIELDS}))
    boundary={name:8 for name in FIELDS}; boundary["m4_q_rd"]=0
    checks={
      "normal_full":decide(marker+line("QUALIFIED_EDGE",**full))["per_slice"][0]["first_missing"]=="FULL_DIRECT_CHAIN_OBSERVED",
      "transout_full":decide(marker+line("QUALIFIED_EDGE",**trans))["per_slice"][1]["first_missing"]=="FULL_DIRECT_CHAIN_OBSERVED",
      "stable_level_not_progress":stable["qualified_record_count"]==0 and stable["per_slice"][2]["first_missing"]=="ACTUAL_SELECTED_MODE_UNOBSERVED",
      "queue_read_boundary":decide(marker+line("QUALIFIED_EDGE",**boundary))["per_slice"][3]["first_missing"]=="MSE4_QUEUE_READ_ABSENT",
      "simultaneous_all_slices":all(r["first_missing"]=="FULL_DIRECT_CHAIN_OBSERVED" for r in simultaneous["per_slice"]),
    }
    return {"schema":"gap-node0071-ga-read-mse4-direct-self-test-v1",
            "checks":checks,"pass":all(checks.values())}

def main()->int:
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("analyze"); a.add_argument("--observer-log",type=Path,required=True); a.add_argument("--output",type=Path,required=True)
    s=sub.add_parser("self-test"); s.add_argument("--output",type=Path,required=True)
    ns=ap.parse_args(); value=self_test() if ns.cmd=="self-test" else decide(ns.observer_log.read_text(encoding="utf-8",errors="replace") if ns.observer_log.is_file() else "")
    ns.output.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return 0 if (value.get("pass",True) and (ns.cmd=="self-test" or value["status"]!="FAIL_CLOSED")) else 1
if __name__=="__main__": raise SystemExit(main())
'''


def patch_observer(package: Path) -> None:
    observer = package / "tb_probe/native_return_observer.svh"
    text = observer.read_text(encoding="utf-8")
    if "GA_READ_MSE4_DIRECT_V1" in text:
        raise base.BuildError("v52 observer already present")
    observer.write_text(text + OBSERVER_EXTENSION, encoding="utf-8", newline="\n")
    parser = package / "package_tools/gap_node0071_ga_read_mse4_direct_decision.py"
    parser.write_text(PARSER, encoding="utf-8", newline="\n")


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    tool_line = (
        'gaobmode_tool="$package_root/package_tools/'
        'gap_node0071_ga_ob_mode_factor_decision.py"'
    )
    if text.count(tool_line) != 2:
        raise base.BuildError("v51 parser declarations differ")
    text = text.replace(
        tool_line,
        tool_line + '\ngadirect_tool="$package_root/package_tools/'
        'gap_node0071_ga_read_mse4_direct_decision.py"',
    )
    text = base.replace_once(
        text,
        "       grep -Fq 'GA_OB_MODE_FACTOR_STATE_V1' \"$observer_log\"; then",
        "       grep -Fq 'GA_OB_MODE_FACTOR_STATE_V1' \"$observer_log\" &&\n"
        "       grep -Fq 'ga_read_mse4_direct=1' \"$observer_log\" &&\n"
        "       grep -Fq 'GA_READ_MSE4_DIRECT_V1' \"$observer_log\"; then",
        "v52 observer binding positive",
    )
    text = base.replace_once(
        text,
        "ga_ob_mode_factor_records_returned=true\\n'",
        "ga_ob_mode_factor_records_returned=true\\n"
        "ga_read_mse4_direct_enabled=true\\n"
        "ga_read_mse4_direct_records_returned=true\\n'",
        "v52 observer binding true",
    )
    text = base.replace_once(
        text,
        "ga_ob_mode_factor_records_returned=false\\n'",
        "ga_ob_mode_factor_records_returned=false\\n"
        "ga_read_mse4_direct_enabled=false\\n"
        "ga_read_mse4_direct_records_returned=false\\n'",
        "v52 observer binding false",
    )
    status = (
        '      printf "ga_ob_mode_factor=%s\\n" "$?" '
        '>>"$evidence_root/decision_parser_status.txt"'
    )
    parse = (
        '      python3 "$gadirect_tool" analyze --observer-log "$observer_log" '
        '--output "$evidence_root/ga_read_mse4_direct_decision.json" '
        '>/dev/null 2>>"$evidence_root/decision_parser_stderr.log"\n'
        '      printf "ga_read_mse4_direct=%s\\n" "$?" '
        '>>"$evidence_root/decision_parser_status.txt"'
    )
    text = base.replace_once(text, status, status + "\n" + parse, "v52 parser call")
    old = (
        'python3 - "$evidence_root/stage_transition_decision.json"       '
        '"$evidence_root/multislice_pipeline_decision.json"       '
        '"$evidence_root/mse4_maskwide_decision.json"       '
        '"$evidence_root/ga_ob_conjunction_decision.json"       '
        '"$evidence_root/ga_ob_mode_factor_decision.json"       '
        '"$evidence_root/canonical_decision.json" "$signal_name" '
        '"$simulation_status" <<\'PY\''
    )
    new = old.replace(
        '"$evidence_root/canonical_decision.json"',
        '"$evidence_root/ga_read_mse4_direct_decision.json"       '
        '"$evidence_root/canonical_decision.json"',
    )
    text = base.replace_once(text, old, new, "v52 fallback argv")
    text = base.replace_once(
        text,
        '    {"schema":"canonical-diagnostic-decision-v1","decision":"FAIL_CLOSED",',
        '    {"schema":"gap-node0071-ga-read-mse4-direct-decision-v1",'
        '"status":"FAIL_CLOSED",\n     "reason":reason,"natural_terminal":False},\n'
        '    {"schema":"canonical-diagnostic-decision-v1","decision":"FAIL_CLOSED",',
        "v52 fallback payload",
    )
    text = base.replace_once(
        text, '"signal":sys.argv[7],"simulation_status":int(sys.argv[8]),',
        '"signal":sys.argv[8],"simulation_status":int(sys.argv[9]),',
        "v52 fallback indices",
    )
    text = base.replace_once(
        text, "for name,payload in zip(sys.argv[1:7],payloads):",
        "for name,payload in zip(sys.argv[1:8],payloads):",
        "v52 fallback output set",
    )
    selftest = (
        'python3 "$gaobmode_tool" self-test --output '
        '"$evidence_root/ga_ob_mode_factor_predicate_self_test.json" '
        '>/dev/null || runner_fail 8 '
        '"GA outbuffer mode-factor predicate self-test failed"'
    )
    text = base.replace_once(
        text, selftest,
        selftest + '\npython3 "$gadirect_tool" self-test --output '
        '"$evidence_root/ga_read_mse4_direct_predicate_self_test.json" '
        '>/dev/null || runner_fail 8 '
        '"GA-read MSE4 direct predicate self-test failed"',
        "v52 self-test",
    )
    text = base.replace_once(
        text, "  +RETURN_OBS_GA_OB_MODE_FACTOR",
        "  +RETURN_OBS_GA_OB_MODE_FACTOR\n  +RETURN_OBS_GA_READ_MSE4_DIRECT",
        "v52 plusarg",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/gap_node0071_complete_server_runtime.py"
    text = path.read_text(encoding="utf-8")
    text = base.replace_once(text, "len(allowlist) != 83", "len(allowlist) != 85", "return allowlist cardinality")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_contract(package: Path) -> None:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    additions = value["path_budget"]["additional_projected_paths"]
    for relative in (
        f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/ga_read_mse4_direct_decision.json",
        f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/ga_read_mse4_direct_predicate_self_test.json",
    ):
        if relative not in additions:
            additions.append(relative)
    additions.sort()
    attempt = "a" * int(value["path_budget"]["attempt_max_chars"])
    longest = max((item.replace("{attempt}", attempt).replace("{name}", INSTALL) for item in additions), key=lambda item: (len(item), item))
    root_max = int(value["path_budget"]["declared_target_root_max_chars"])
    value["path_budget"]["max_projected_absolute_path_chars"] = root_max + 1 + len(longest)
    base.write_json(path, value)


def patch_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["install_name"] = INSTALL
    value["package_name"] = f"{INSTALL}.zip"
    value["return_name"] = f"{INSTALL}_return"
    value["test_id"] = "r5-gap-node0071-v52-ga-read-mse4-direct-diagnostic"
    value["source_package"] = {
        "install_name": SOURCE,
        "sha256": SOURCE_SHA,
        "return_sha256": RETURN_SHA,
        "return_analysis": "artifacts/operator_config_validation/r5-gap-node0071-v51-return-analysis/report.json",
    }
    value["rule_receipts"]["server_package_rule_sha256"] = SERVER_RULE_SHA
    value["rule_receipts"]["generation_index_sha256"] = INDEX_SHA
    value["ga_read_mse4_direct_contract"] = {
        "feature": "GA_READ_MSE4_DIRECT_V1",
        "plusarg": "+RETURN_OBS_GA_READ_MSE4_DIRECT",
        "selected_mask": "0x0000ffff",
        "owner_clock": "clk_sg",
        "reporter_clock": "clk_db",
        "qualified_emit_limit": 320,
        "heartbeat_cycles": 1048576,
        "state_or_heartbeat_consumes_budget": False,
        "reused_package_local_surfaces_only": True,
        "new_private_xmr": False,
        "qualified_chain": [
            "actual selected normal/transout mode", "selected GA write",
            "GA outbuffer nonempty", "selected GA read", "MSE4 index accept",
            "MSE4 request accept", "MSE4 queue write/read", "MSE4 buffer accept",
            "MSE4 prepared write/read", "MSE4 outbuffer write/read",
            "MSE4 local request/write-data", "slice finish",
        ],
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
    }
    for row in (
        {"source_root":"evidence","source_path":"ga_read_mse4_direct_decision.json","target_path":"evidence/ga_read_mse4_direct_decision.json","required":True,"max_bytes":131072,"missing_meaning":"GA-read MSE4 direct decision absent"},
        {"source_root":"evidence","source_path":"ga_read_mse4_direct_predicate_self_test.json","target_path":"evidence/ga_read_mse4_direct_predicate_self_test.json","required":True,"max_bytes":32768,"missing_meaning":"GA-read MSE4 direct predicate self-test absent"},
    ):
        if row["target_path"] not in {item["target_path"] for item in value["return_allowlist"]}:
            value["return_allowlist"].append(row)
    value["budgets"]["return_extracted_max_bytes"] += 163840
    value["budgets"]["return_zip_max_bytes"] += 98304
    value["release_gate_matrix"] = [
        {"gate_id":"PACKAGE_BOOTSTRAP_RUNTIME_LAYOUT","applicability":"blocking_applicable_identity_and_runner_changed","status":"PASS_PENDING_FINAL_ZIP_VALIDATION"},
        {"gate_id":"PACKAGE_LOCAL_HDL","applicability":"blocking_applicable_observer_changed_reuses_existing_surfaces","status":"PASS_PENDING_CHANGED_SURFACE_SCOPE_VALIDATION"},
        {"gate_id":"DIAGNOSTIC_SEMANTICS","applicability":"blocking_applicable_predicate_changed","status":"PASS_PENDING_EXACT_TRACE"},
        {"gate_id":"MATERIALIZED_CONFIG","applicability":"receipt_reuse_byte_equal","status":"PASS"},
        {"gate_id":"RETURN_RESULT_CONTRACT","applicability":"blocking_applicable_parser_finalizer_changed","status":"PASS_PENDING_SIGNAL_FINALIZER_VALIDATION"},
        {"gate_id":"FROZEN_NUMERIC_GOLDEN","applicability":"record_only_byte_equal","status":"PASS"},
    ]
    value["candidate_release"] = False
    value["package_class"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    value["evidence_level"] = "E2_LOCAL_COMPLETE_NODE"
    value["status"] = "PACKAGE_READY_NOT_RUN"
    value["numeric_analysis_repeated"] = False
    value["sum_or_tail_numeric_reexecuted"] = False
    value["functional_rtl_modified"] = False
    runtime = json.loads((package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(encoding="utf-8"))
    attempt = "a" * int(runtime["path_budget"]["attempt_max_chars"])
    projected = {f"install/cfg_pkg/{INSTALL}/" + item.relative_to(package / "workload").as_posix() for item in (package / "workload").rglob("*") if item.is_file()} | {item.replace("{attempt}", attempt).replace("{name}", INSTALL) for item in runtime["path_budget"]["additional_projected_paths"]}
    longest = max(projected, key=lambda item: (len(item), item))
    root_max = int(runtime["path_budget"]["declared_target_root_max_chars"])
    value["path_length_budget"]["longest_projected_relative_path"] = longest
    value["path_length_budget"]["longest_projected_relative_path_chars"] = len(longest)
    value["path_length_budget"]["max_projected_absolute_path_chars"] = root_max + 1 + len(longest)
    value["path_length_budget"]["pass"] = root_max + 1 + len(longest) <= int(value["path_length_budget"]["absolute_path_limit_chars"])
    value["files"] = base.files_map(package)
    base.write_json(path, value)
    value["files"] = base.files_map(package)
    base.write_json(path, value)


def build(output: Path) -> Path:
    package = output / INSTALL
    if package.exists():
        raise base.BuildError(f"refusing to overwrite {package}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gap-v52-source-") as temp:
        shutil.copytree(base.extract_source(Path(temp)), package)
    base.replace_identity(package)
    patch_observer(package)
    patch_runner(package)
    patch_runtime(package)
    patch_contract(package)
    base.write_json(
        package / "provenance/v51_to_v52_ga_read_mse4_direct.json",
        {
            "schema":"gap-node0071-v51-to-v52-ga-read-mse4-direct-v1",
            "source_zip_sha256":SOURCE_SHA,"return_sha256":RETURN_SHA,
            "classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "last_proven_good":"ALL_16_SLICES_GA_SELECTED_WRITE_NONEMPTY_SELECTED_READ",
            "first_divergence":"SELECTED_GA_READ_TO_ALL_SLICE_MSE4_DIRECT_CONSUMER_UNEVALUABLE_AFTER_LEGACY_STATE_BUDGET_SATURATION",
            "changed_surface":["fresh identity","qualified-only actual-mode plus all-slice MSE4 direct-consumer observer/parser","manifest/return allowlist/provenance"],
            "frozen":["73 numeric/workload/config/golden files","sum and exact uint8 tail semantics","mapping/bitstream/execplan/SCA bytes except identity text","timeout and backpressure","functional RTL","repeat-safe owned reset and unique return semantics"],
            "server_action":False,
        },
    )
    (package / "README.md").write_text(
        "# GAP node0071 v52 GA-read to MSE4 direct-consumer diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "This successor freezes v51 numeric/config/workload/golden, timeout, backpressure and functional RTL. It adds one qualified-only all-slice chain from actual selected GA mode/write/nonempty/read through MSE4 index/request/queue/buffer/prepared/outbuffer/local request/write-data and finish. Heartbeats never consume the 320-event qualified budget.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        "Each execution publishes one unique return under `/home/panqs/ndp/simresult`.\n",
        encoding="utf-8", newline="\n",
    )
    patch_manifest(package)
    return package


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ns = ap.parse_args()
    output = ns.output.resolve()
    package = build(output)
    target = output / f"{INSTALL}.zip"
    base.deterministic_zip(package, target)
    sidecar = Path(str(target) + ".sha256")
    sidecar.write_text(f"{base.digest(target)}  {target.name}\n", encoding="ascii", newline="\n")
    print(json.dumps({"package":str(package),"zip":str(target),"bytes":target.stat().st_size,"sha256":base.digest(target),"sidecar":str(sidecar),"sidecar_sha256":base.digest(sidecar)},indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
