from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "r5_n71_gap_v48_multislice_pipeline_diag"
INSTALL = "r5_n71_gap_v49_mse4_maskwide_diag"
SOURCE_SHA = "122257a3b7441e9af2a036f8d8fff1bb7339f014f9c6177f607587525ef359d3"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
SERVER_RULE_SHA = "89d27141f1a151ef5e6cc98603238050c9b0442a3d1937b2ec23cf92e55a27a2"
INDEX_SHA = "3c2bd9017f351b6456eac49c966063cc9b76e96420d71162a1ca57d1b62b552c"
RETURN_REPORT_SHA = "03dc7c568ac5bfcad61967880e07e52ae8aaca31e46cfe0c071f4fc18654a0eb"


class BuildError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


def deterministic_zip(source: Path, target: Path) -> None:
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            relative = f"{source.name}/{path.relative_to(source).as_posix()}"
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def extract(destination: Path) -> Path:
    if sha(SOURCE_ZIP) != SOURCE_SHA:
        raise BuildError("source v48 SHA mismatch")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("source v48 CRC failure")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
                or (info.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise BuildError(f"unsafe source member: {info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {SOURCE}:
            raise BuildError(f"unexpected source roots: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE in text:
            path.write_text(
                text.replace(SOURCE, INSTALL), encoding="utf-8", newline="\n"
            )


OBSERVER_EXTENSION = r'''

    // v49: all-slice GA-outbuffer to MSE4 request/write/finish information gain.
    // This extension consumes only package-local monitor surfaces already
    // compiled in v48. It never drives DUT state. Qualified handshakes update
    // sticky masks in clk_sg; level masks are state-only and never progress.
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_ga_rd_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_idx_hs_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_req_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_q_wr_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_q_rd_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_buf_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_prep_wr_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_prep_rd_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_ob_wr_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_ob_rd_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_local_req_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_local_wdata_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_m4mw_finish_seen;
    logic [13*`GLB_SLICE_NUM-1:0] return_obs_m4mw_prev_qualified;
    logic [13*`GLB_SLICE_NUM-1:0] return_obs_m4mw_prev_state;
    bit return_obs_m4mw_enabled;
    longint unsigned return_obs_m4mw_db_cycles;
    longint unsigned return_obs_m4mw_emit_count;
    longint unsigned return_obs_m4mw_heartbeat_cycles;

    initial begin
        return_obs_m4mw_enabled =
            $test$plusargs("RETURN_OBS_MSE4_MASKWIDE");
        return_obs_m4mw_db_cycles = 0;
        return_obs_m4mw_emit_count = 0;
        return_obs_m4mw_heartbeat_cycles = 1048576;
        return_obs_m4mw_prev_qualified = '0;
        return_obs_m4mw_prev_state = '0;
        return_obs_plusarg_status = $value$plusargs(
            "RETURN_OBS_MSE4_MASKWIDE_HEARTBEAT_CYCLES=%d",
            return_obs_m4mw_heartbeat_cycles
        );
        #0;
        if (return_obs_enabled && return_obs_m4mw_enabled &&
            return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "# mse4_maskwide=1 selected_mask=0x0000ffff divergence_mask=0x0000fffe owner=clk_sg reporter=clk_db qualified_limit=256"
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin
        if (!u_NDP_Top_new.rst_n_sg) begin
            return_obs_m4mw_ga_rd_seen <= '0;
            return_obs_m4mw_idx_hs_seen <= '0;
            return_obs_m4mw_req_seen <= '0;
            return_obs_m4mw_q_wr_seen <= '0;
            return_obs_m4mw_q_rd_seen <= '0;
            return_obs_m4mw_buf_seen <= '0;
            return_obs_m4mw_prep_wr_seen <= '0;
            return_obs_m4mw_prep_rd_seen <= '0;
            return_obs_m4mw_ob_wr_seen <= '0;
            return_obs_m4mw_ob_rd_seen <= '0;
            return_obs_m4mw_local_req_seen <= '0;
            return_obs_m4mw_local_wdata_seen <= '0;
            return_obs_m4mw_finish_seen <= '0;
        end
        else if (return_obs_enabled && return_obs_m4mw_enabled) begin
            for (int g = 0; g < `SLICE_GROUP_SIZE; g++) begin
                for (int s = 0; s < `SLICE_GROUP_NUM; s++) begin
                    bit any_ga_rd;
                    any_ga_rd = 1'b0;
                    for (int row = 0; row < `GA_ROW_PE_NUM; row++)
                        for (int slot = 0; slot < 2; slot++)
                            any_ga_rd |=
                                return_obs_pair_ga_normal_rd_hs_mon
                                    [g][s][row][slot];
                    if (any_ga_rd)
                        return_obs_m4mw_ga_rd_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (return_obs_mse4_idx_hs_mon[g][s])
                        return_obs_m4mw_idx_hs_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (return_obs_pair_m4_req_valid_mon[g][s] &&
                        return_obs_pair_m4_req_ready_mon[g][s])
                        return_obs_m4mw_req_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (return_obs_pair_m4_q_wr_mon[g][s])
                        return_obs_m4mw_q_wr_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (return_obs_pair_m4_q_rd_mon[g][s])
                        return_obs_m4mw_q_rd_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (return_obs_pair_m4_buf_accept_mon[g][s])
                        return_obs_m4mw_buf_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (return_obs_pair_m4_prep_wr_mon[g][s])
                        return_obs_m4mw_prep_wr_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (return_obs_pair_m4_prep_rd_mon[g][s])
                        return_obs_m4mw_prep_rd_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (|return_obs_pair_m4_ob_wr_mon[g][s])
                        return_obs_m4mw_ob_wr_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (|return_obs_pair_m4_ob_rd_mon[g][s])
                        return_obs_m4mw_ob_rd_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (|local_req_hs[g][s][4])
                        return_obs_m4mw_local_req_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (|local_wdata_hs[g][s][4])
                        return_obs_m4mw_local_wdata_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (return_obs_pair_m4_finish_mon[g][s])
                        return_obs_m4mw_finish_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                end
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        logic [13*`GLB_SLICE_NUM-1:0] qualified_snapshot;
        logic [13*`GLB_SLICE_NUM-1:0] state_snapshot;
        logic [`GLB_SLICE_NUM-1:0] idx_valid_mask, req_valid_mask;
        logic [`GLB_SLICE_NUM-1:0] req_ready_mask, q_full_mask;
        logic [`GLB_SLICE_NUM-1:0] q_empty_mask, buf_valid_mask;
        logic [`GLB_SLICE_NUM-1:0] buf_ready_mask, hold_mask;
        logic [`GLB_SLICE_NUM-1:0] prep_valid_mask, ob_valid_mask;
        logic [`GLB_SLICE_NUM-1:0] ob_valid_o_mask, mem_ready_mask;
        logic [`GLB_SLICE_NUM-1:0] last_mask;
        bit qualified_changed, state_changed, heartbeat;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_m4mw_db_cycles = 0;
            return_obs_m4mw_emit_count = 0;
            return_obs_m4mw_prev_qualified = '0;
            return_obs_m4mw_prev_state = '0;
        end
        else if (return_obs_enabled && return_obs_m4mw_enabled &&
                 return_obs_fd != 0) begin
            return_obs_m4mw_db_cycles++;
            idx_valid_mask = '0; req_valid_mask = '0; req_ready_mask = '0;
            q_full_mask = '0; q_empty_mask = '0; buf_valid_mask = '0;
            buf_ready_mask = '0; hold_mask = '0; prep_valid_mask = '0;
            ob_valid_mask = '0; ob_valid_o_mask = '0; mem_ready_mask = '0;
            last_mask = '0;
            for (int g = 0; g < `SLICE_GROUP_SIZE; g++) begin
                for (int s = 0; s < `SLICE_GROUP_NUM; s++) begin
                    int id;
                    id = g * `SLICE_GROUP_NUM + s;
                    idx_valid_mask[id] = return_obs_mse4_idx_valid_mon[g][s];
                    req_valid_mask[id] = return_obs_pair_m4_req_valid_mon[g][s];
                    req_ready_mask[id] = return_obs_pair_m4_req_ready_mon[g][s];
                    q_full_mask[id] = return_obs_pair_m4_q_full_mon[g][s];
                    q_empty_mask[id] = return_obs_pair_m4_q_empty_mon[g][s];
                    buf_valid_mask[id] = return_obs_pair_m4_buf_vld_mon[g][s];
                    buf_ready_mask[id] = return_obs_pair_m4_buf_ready_mon[g][s];
                    hold_mask[id] = return_obs_pair_m4_hold_vld_mon[g][s];
                    prep_valid_mask[id] = return_obs_pair_m4_prep_vld_mon[g][s];
                    ob_valid_mask[id] =
                        |return_obs_pair_m4_ob_vld_mon[g][s];
                    ob_valid_o_mask[id] =
                        |return_obs_pair_m4_ob_vld_o_mon[g][s];
                    mem_ready_mask[id] =
                        |return_obs_pair_m4_mem_ready_mon[g][s];
                    last_mask[id] = |return_obs_pair_m4_last_mon[g][s];
                end
            end
            qualified_snapshot = {
                return_obs_m4mw_finish_seen,
                return_obs_m4mw_local_wdata_seen,
                return_obs_m4mw_local_req_seen,
                return_obs_m4mw_ob_rd_seen,
                return_obs_m4mw_ob_wr_seen,
                return_obs_m4mw_prep_rd_seen,
                return_obs_m4mw_prep_wr_seen,
                return_obs_m4mw_buf_seen,
                return_obs_m4mw_q_rd_seen,
                return_obs_m4mw_q_wr_seen,
                return_obs_m4mw_req_seen,
                return_obs_m4mw_idx_hs_seen,
                return_obs_m4mw_ga_rd_seen
            };
            state_snapshot = {
                last_mask, mem_ready_mask, ob_valid_o_mask, ob_valid_mask,
                prep_valid_mask, hold_mask, buf_ready_mask, buf_valid_mask,
                q_empty_mask, q_full_mask, req_ready_mask, req_valid_mask,
                idx_valid_mask
            };
            qualified_changed =
                qualified_snapshot != return_obs_m4mw_prev_qualified;
            state_changed = state_snapshot != return_obs_m4mw_prev_state;
            heartbeat = (return_obs_m4mw_db_cycles %
                         return_obs_m4mw_heartbeat_cycles) == 0;
            if ((qualified_changed || state_changed || heartbeat) &&
                return_obs_m4mw_emit_count < 256) begin
                return_obs_m4mw_emit_count++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | MSE4_MASKWIDE_STATE_V1 | event=%s n=%0d db_cycle=%0d ga_rd=0x%0h idx_hs=0x%0h req=0x%0h q_wr=0x%0h q_rd=0x%0h buf=0x%0h prep_wr=0x%0h prep_rd=0x%0h ob_wr=0x%0h ob_rd=0x%0h local_req=0x%0h local_wdata=0x%0h finish=0x%0h idx_v=0x%0h req_v=0x%0h req_r=0x%0h q_full=0x%0h q_empty=0x%0h buf_v=0x%0h buf_r=0x%0h hold=0x%0h prep_v=0x%0h ob_v=0x%0h ob_vo=0x%0h mem_r=0x%0h last=0x%0h",
                    $time,
                    (qualified_changed ? "QUALIFIED_EDGE" :
                     state_changed ? "STATE_EDGE" : "HEARTBEAT"),
                    return_obs_m4mw_emit_count,
                    return_obs_m4mw_db_cycles,
                    return_obs_m4mw_ga_rd_seen,
                    return_obs_m4mw_idx_hs_seen,
                    return_obs_m4mw_req_seen,
                    return_obs_m4mw_q_wr_seen,
                    return_obs_m4mw_q_rd_seen,
                    return_obs_m4mw_buf_seen,
                    return_obs_m4mw_prep_wr_seen,
                    return_obs_m4mw_prep_rd_seen,
                    return_obs_m4mw_ob_wr_seen,
                    return_obs_m4mw_ob_rd_seen,
                    return_obs_m4mw_local_req_seen,
                    return_obs_m4mw_local_wdata_seen,
                    return_obs_m4mw_finish_seen,
                    idx_valid_mask, req_valid_mask, req_ready_mask,
                    q_full_mask, q_empty_mask, buf_valid_mask,
                    buf_ready_mask, hold_mask, prep_valid_mask,
                    ob_valid_mask, ob_valid_o_mask, mem_ready_mask, last_mask
                );
                $fflush(return_obs_fd);
            end
            return_obs_m4mw_prev_qualified = qualified_snapshot;
            return_obs_m4mw_prev_state = state_snapshot;
        end
    end
'''


PARSER = r'''from __future__ import annotations
import argparse,json,re
from pathlib import Path
QUAL=("ga_rd","idx_hs","req","q_wr","q_rd","buf","prep_wr","prep_rd",
      "ob_wr","ob_rd","local_req","local_wdata","finish")
STATE=("idx_v","req_v","req_r","q_full","q_empty","buf_v","buf_r","hold",
       "prep_v","ob_v","ob_vo","mem_r","last")
FIELDS=QUAL+STATE
PATTERN=re.compile(r"MSE4_MASKWIDE_STATE_V1\s+\|\s+event=(QUALIFIED_EDGE|STATE_EDGE|HEARTBEAT).*?"+
    r"\s".join(fr"{name}=0x([0-9a-fA-F]+)" for name in FIELDS))
def decide(text:str)->dict:
    rows=[]
    for line in text.splitlines():
        m=PATTERN.search(line)
        if m:
            rows.append({"event":m.group(1),**{
                name:int(value,16) for name,value in zip(FIELDS,m.groups()[1:])
            }})
    last=rows[-1] if rows else {name:0 for name in FIELDS}
    per_slice=[]
    for sid in range(16):
        q={name:bool(last[name]&(1<<sid)) for name in QUAL}
        state={name:bool(last[name]&(1<<sid)) for name in STATE}
        first=next((name for name in QUAL if not q[name]),None)
        per_slice.append({"slice":sid,"qualified":q,"state":state,
                          "first_missing_qualified":first})
    return {
      "schema":"gap-node0071-mse4-maskwide-decision-v1",
      "feature_enabled_marker":"# mse4_maskwide=1" in text,
      "record_count":len(rows),
      "qualified_record_count":sum(r["event"]=="QUALIFIED_EDGE" for r in rows),
      "state_record_count":sum(r["event"]=="STATE_EDGE" for r in rows),
      "heartbeat_record_count":sum(r["event"]=="HEARTBEAT" for r in rows),
      "last_qualified_masks":{name:f"0x{last[name]:04x}" for name in QUAL},
      "last_state_masks":{name:f"0x{last[name]:04x}" for name in STATE},
      "per_slice":per_slice,
      "candidate_matrix":{
        "GA_OUTBUFFER_READ":["ga_rd"],
        "MSE4_INDEX_TO_REQUEST":["idx_hs","req"],
        "MSE4_REQUEST_QUEUE":["q_wr","q_rd"],
        "MSE4_BUFFER_PREPARED":["buf","prep_wr","prep_rd"],
        "MSE4_OUTPUT_BUFFER":["ob_wr","ob_rd"],
        "LOCAL_REQUEST_WRITE_PAIR":["local_req","local_wdata"],
        "TERMINAL_RELEASE":["finish"]},
      "claim_boundary":"Only QUALIFIED_EDGE advances progress; STATE_EDGE and "
        "HEARTBEAT are state. Zero without bound feature/records is unevaluable."
    }
def self_test()->dict:
    allq={name:"fffe" for name in QUAL}; alls={name:"0000" for name in STATE}
    line=lambda event,q,s:("1 | MSE4_MASKWIDE_STATE_V1 | event="+event+
      " n=1 db_cycle=1 "+" ".join(f"{k}=0x{q[k]}" for k in QUAL)+" "+
      " ".join(f"{k}=0x{s[k]}" for k in STATE))
    marker="# mse4_maskwide=1\n"
    stable=decide(marker+line("HEARTBEAT",allq,alls))
    state=decide(marker+line("STATE_EDGE",allq,{**alls,"idx_v":"fffe"}))
    cut={**allq,"q_rd":"0002"}
    qualified=decide(marker+line("QUALIFIED_EDGE",cut,alls))
    checks={
      "stable_level_not_progress":stable["qualified_record_count"]==0,
      "state_edge_not_progress":state["qualified_record_count"]==0,
      "qualified_edge_progress":qualified["qualified_record_count"]==1,
      "nearest_escape":next(x for x in qualified["per_slice"]
        if x["slice"]==2)["first_missing_qualified"]=="q_rd",
      "simultaneous_event":next(x for x in stable["per_slice"]
        if x["slice"]==1)["first_missing_qualified"] is None,
      "absent_marker_fail_closed":not decide("")["feature_enabled_marker"],
    }
    return {"schema":"gap-node0071-mse4-maskwide-predicate-test-v1",
            "pass":all(checks.values()),"checks":checks}
def main():
    p=argparse.ArgumentParser(); sp=p.add_subparsers(dest="cmd",required=True)
    a=sp.add_parser("analyze"); a.add_argument("--observer-log",type=Path,required=True)
    a.add_argument("--output",type=Path,required=True)
    s=sp.add_parser("self-test"); s.add_argument("--output",type=Path,required=True)
    ns=p.parse_args()
    value=self_test() if ns.cmd=="self-test" else decide(
        ns.observer_log.read_text(encoding="utf-8",errors="replace")
        if ns.observer_log.is_file() else "")
    ns.output.write_text(json.dumps(value,indent=2,sort_keys=True)+chr(10),
                         encoding="utf-8")
    return 0 if (value.get("pass",True) and
      (ns.cmd=="self-test" or value["feature_enabled_marker"])) else 1
if __name__=="__main__": raise SystemExit(main())
'''


def patch_observer(package: Path) -> None:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "MSE4_MASKWIDE_STATE_V1" in text:
        raise BuildError("v49 observer already present")
    path.write_text(text + OBSERVER_EXTENSION, encoding="utf-8", newline="\n")
    (package / "package_tools/gap_node0071_mse4_maskwide_decision.py").write_text(
        PARSER, encoding="utf-8", newline="\n"
    )


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'multislice_tool="$package_root/package_tools/'
        'gap_node0071_multislice_pipeline_decision.py"',
        'multislice_tool="$package_root/package_tools/'
        'gap_node0071_multislice_pipeline_decision.py"\n'
        'mse4mask_tool="$package_root/package_tools/'
        'gap_node0071_mse4_maskwide_decision.py"',
        1,
    )
    old = (
        'python3 "$multislice_tool" analyze --observer-log "$observer_log" '
        '        --output "$evidence_root/multislice_pipeline_decision.json" '
        '>/dev/null 2>&1 || true'
    )
    if old not in text:
        raise BuildError("multislice parser invocation anchor absent")
    text = text.replace(
        old,
        old + '\n      python3 "$mse4mask_tool" analyze '
        '--observer-log "$observer_log" '
        '--output "$evidence_root/mse4_maskwide_decision.json" '
        '>/dev/null 2>&1 || true',
        1,
    )
    old_args = (
        'python3 - "$evidence_root/stage_transition_decision.json"       '
        '"$evidence_root/multislice_pipeline_decision.json"       '
        '"$evidence_root/canonical_decision.json" "$signal_name" '
        '"$simulation_status" <<\'PY\''
    )
    new_args = (
        'python3 - "$evidence_root/stage_transition_decision.json"       '
        '"$evidence_root/multislice_pipeline_decision.json"       '
        '"$evidence_root/mse4_maskwide_decision.json"       '
        '"$evidence_root/canonical_decision.json" "$signal_name" '
        '"$simulation_status" <<\'PY\''
    )
    if old_args not in text:
        raise BuildError("fallback argv anchor absent")
    text = text.replace(old_args, new_args, 1)
    text = text.replace(
        '{"schema":"canonical-diagnostic-decision-v1","decision":"FAIL_CLOSED",',
        '{"schema":"gap-mse4-maskwide-decision-v1","status":"FAIL_CLOSED",\n'
        '     "reason":reason,"natural_terminal":False},\n'
        '    {"schema":"canonical-diagnostic-decision-v1","decision":"FAIL_CLOSED",',
        1,
    )
    text = text.replace(
        '"signal":sys.argv[4],"simulation_status":int(sys.argv[5]),',
        '"signal":sys.argv[5],"simulation_status":int(sys.argv[6]),',
        1,
    )
    broken = (
        'path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",'
        'encoding="utf-8")'
    )
    if broken not in text:
        raise BuildError("v48 generated fallback SyntaxError anchor absent")
    text = text.replace(
        broken,
        'path.write_text(json.dumps(payload,indent=2,sort_keys=True)+chr(10),'
        'encoding="utf-8")',
        1,
    )
    text = text.replace(
        "for name,payload in zip(sys.argv[1:4],payloads):",
        "for name,payload in zip(sys.argv[1:5],payloads):",
        1,
    )
    old_binding = (
        "grep -Fq 'multislice_pipeline=1' \"$observer_log\" &&\n"
        "       grep -Fq 'MULTISLICE_PIPELINE_STATE_V1' \"$observer_log\"; then\n"
        "      printf 'observer_enabled_and_returned=true\\n"
        "multislice_pipeline_enabled=true\\n"
        "multislice_pipeline_records_returned=true\\n' "
        ">\"$evidence_root/observer_binding.txt\""
    )
    new_binding = (
        "grep -Fq 'multislice_pipeline=1' \"$observer_log\" &&\n"
        "       grep -Fq 'MULTISLICE_PIPELINE_STATE_V1' \"$observer_log\" &&\n"
        "       grep -Fq 'mse4_maskwide=1' \"$observer_log\" &&\n"
        "       grep -Fq 'MSE4_MASKWIDE_STATE_V1' \"$observer_log\"; then\n"
        "      printf 'observer_enabled_and_returned=true\\n"
        "multislice_pipeline_enabled=true\\n"
        "multislice_pipeline_records_returned=true\\n"
        "mse4_maskwide_enabled=true\\n"
        "mse4_maskwide_records_returned=true\\n' "
        ">\"$evidence_root/observer_binding.txt\""
    )
    if old_binding not in text:
        raise BuildError("observer binding anchor absent")
    text = text.replace(old_binding, new_binding, 1)
    text = text.replace(
        "printf 'observer_enabled_and_returned=false\\n"
        "multislice_pipeline_enabled=false\\n"
        "multislice_pipeline_records_returned=false\\n' "
        ">\"$evidence_root/observer_binding.txt\"",
        "printf 'observer_enabled_and_returned=false\\n"
        "multislice_pipeline_enabled=false\\n"
        "multislice_pipeline_records_returned=false\\n"
        "mse4_maskwide_enabled=false\\n"
        "mse4_maskwide_records_returned=false\\n' "
        ">\"$evidence_root/observer_binding.txt\"",
        1,
    )
    text = text.replace(
        'python3 "$multislice_tool" self-test --output '
        '"$evidence_root/multislice_pipeline_predicate_self_test.json" '
        '>/dev/null || exit 8',
        'python3 "$multislice_tool" self-test --output '
        '"$evidence_root/multislice_pipeline_predicate_self_test.json" '
        '>/dev/null || exit 8\n'
        'python3 "$mse4mask_tool" self-test --output '
        '"$evidence_root/mse4_maskwide_predicate_self_test.json" '
        '>/dev/null || exit 8',
        1,
    )
    text = text.replace(
        '+RETURN_OBS_MULTISLICE_HEARTBEAT_CYCLES=1048576',
        '+RETURN_OBS_MULTISLICE_HEARTBEAT_CYCLES=1048576\n'
        '  +RETURN_OBS_MSE4_MASKWIDE '
        '+RETURN_OBS_MSE4_MASKWIDE_HEARTBEAT_CYCLES=1048576',
        1,
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/gap_node0071_complete_server_runtime.py"
    text = path.read_text(encoding="utf-8")
    if "len(allowlist) != 75" not in text:
        raise BuildError("v48 allowlist count anchor absent")
    path.write_text(
        text.replace("len(allowlist) != 75", "len(allowlist) != 77", 1),
        encoding="utf-8", newline="\n",
    )


def refresh_runtime_path_budget(package: Path) -> None:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    attempt = "a" * int(contract["path_budget"]["attempt_max_chars"])
    projected = {
        f"install/cfg_pkg/{INSTALL}/"
        + item.relative_to(package / "workload").as_posix()
        for item in (package / "workload").rglob("*")
        if item.is_file()
    }
    additions = list(contract["path_budget"]["additional_projected_paths"])
    additions.append(
        f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/"
        "mse4_maskwide_decision.json"
    )
    contract["path_budget"]["additional_projected_paths"] = additions
    candidates = projected | {
        item.replace("{attempt}", attempt) for item in additions
    }
    longest = max(candidates, key=lambda item: (len(item), item))
    root_max = int(contract["path_budget"]["declared_target_root_max_chars"])
    contract["path_budget"]["max_projected_absolute_path_chars"] = (
        root_max + 1 + len(longest)
    )
    write_json(path, contract)


def records(package: Path) -> dict[str, object]:
    manifest = package / "TEST_PACKAGE_MANIFEST.json"
    return {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest
    }


def patch_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["install_name"] = INSTALL
    manifest["package_name"] = f"{INSTALL}.zip"
    manifest["return_name"] = f"{INSTALL}_return"
    manifest["test_id"] = "r5-gap-node0071-v49-mse4-maskwide-diagnostic"
    manifest["source_package"] = {
        "install_name": SOURCE,
        "sha256": SOURCE_SHA,
        "return_analysis_sha256": RETURN_REPORT_SHA,
    }
    manifest["rule_receipts"]["server_package_rule_sha256"] = SERVER_RULE_SHA
    manifest["rule_receipts"]["generation_index_sha256"] = INDEX_SHA
    manifest["mse4_maskwide_information_gain_contract"] = {
        "feature": "MSE4_MASKWIDE_STATE_V1",
        "plusarg": "+RETURN_OBS_MSE4_MASKWIDE",
        "selected_mask": "0x0000ffff",
        "divergence_mask": "0x0000fffe",
        "qualified_chain": [
            "GA outbuffer read",
            "MSE4 index handshake",
            "MSE4 request accept",
            "request queue write/read",
            "buffer accept",
            "prepared write/read",
            "output buffer write/read",
            "local request/write-data pair",
            "finish",
        ],
        "state_only": [
            "index valid", "request valid/ready", "queue full/empty",
            "buffer valid/ready", "hold", "prepared valid",
            "output-buffer valid", "memory ready", "last",
        ],
        "owner_clock": "clk_sg",
        "reporter_clock": "clk_db",
        "emit_limit": 256,
        "stable_level_is_progress": False,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
    }
    manifest["finalizer_fallback_fix"] = {
        "source_return_sha256":
            "94c448d3cc14e51afb7daad9b41a04f38de87d31fc960b6216506cfd1589a508",
        "classification":
            "PACKAGE_LOCAL_FINALIZER_HEREDOC_STRING_LITERAL_FIX",
        "mechanism": "use chr(10) in generated fallback Python",
        "shared_signal_and_exit_path": True,
    }
    additions = [
        {
            "source_root": "evidence",
            "source_path": "mse4_maskwide_decision.json",
            "target_path": "evidence/mse4_maskwide_decision.json",
            "required": True,
            "max_bytes": 65536,
            "missing_meaning": "mask-wide MSE4 decision absent or parser failed",
        },
        {
            "source_root": "evidence",
            "source_path": "mse4_maskwide_predicate_self_test.json",
            "target_path": "evidence/mse4_maskwide_predicate_self_test.json",
            "required": True,
            "max_bytes": 32768,
            "missing_meaning": "mask-wide MSE4 predicate self-test absent",
        },
    ]
    targets = {row["target_path"] for row in manifest["return_allowlist"]}
    for row in additions:
        if row["target_path"] not in targets:
            manifest["return_allowlist"].append(row)
    manifest["budgets"]["return_extracted_max_bytes"] += 98304
    manifest["budgets"]["return_zip_max_bytes"] += 65536
    manifest["release_gate_matrix"] = [
        {
            "gate_id": "PACKAGE_BOOTSTRAP_RUNTIME_LAYOUT",
            "applicability": "blocking_applicable_identity_and_runner_changed",
            "status": "PASS_PENDING_FINAL_ZIP_SHARED_VALIDATION",
        },
        {
            "gate_id": "PACKAGE_LOCAL_HDL",
            "applicability": "blocking_applicable_observer_changed",
            "status": "PASS_PENDING_FAMILY_HDL_SCOPE_VALIDATION",
        },
        {
            "gate_id": "DIAGNOSTIC_SEMANTICS",
            "applicability": "blocking_applicable_predicate_changed",
            "status": "PASS_PENDING_EXACT_TRACE",
        },
        {
            "gate_id": "MATERIALIZED_CONFIG",
            "applicability": "receipt_reuse_identity_only_paths",
            "status": "PASS",
        },
        {
            "gate_id": "RETURN_RESULT_CONTRACT",
            "applicability": "blocking_applicable_finalizer_and_allowlist_changed",
            "status": "PASS_PENDING_SIGNAL_FINALIZER_VALIDATION",
        },
        {
            "gate_id": "FROZEN_NUMERIC_GOLDEN",
            "applicability": "record_only_byte_equal",
            "status": "PASS",
        },
    ]
    manifest["candidate_release"] = False
    manifest["package_class"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    manifest["evidence_level"] = "E2_LOCAL_COMPLETE_NODE"
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["numeric_analysis_repeated"] = False
    manifest["sum_or_tail_numeric_reexecuted"] = False
    manifest["functional_rtl_modified"] = False
    runtime_contract = json.loads(
        (package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )
    attempt = "a" * runtime_contract["path_budget"]["attempt_max_chars"]
    projected = {
        f"install/cfg_pkg/{INSTALL}/"
        + item.relative_to(package / "workload").as_posix()
        for item in (package / "workload").rglob("*")
        if item.is_file()
    } | {
        item.replace("{attempt}", attempt)
        for item in runtime_contract["path_budget"]["additional_projected_paths"]
    }
    longest = max(projected, key=lambda item: (len(item), item))
    root_max = runtime_contract["path_budget"]["declared_target_root_max_chars"]
    manifest["path_length_budget"] = {
        "declared_target_root_max_chars": root_max,
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": root_max + 1 + len(longest),
        "absolute_path_limit_chars":
            runtime_contract["path_budget"]["absolute_path_limit_chars"],
        "pass":
            root_max + 1 + len(longest)
            <= runtime_contract["path_budget"]["absolute_path_limit_chars"],
    }
    manifest["files"] = records(package)
    write_json(path, manifest)
    manifest["files"] = records(package)
    write_json(path, manifest)


def build(output: Path) -> Path:
    package = output / INSTALL
    if package.exists():
        raise BuildError(f"refusing to overwrite {package}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gap-v48-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    patch_observer(package)
    patch_runner(package)
    patch_runtime(package)
    refresh_runtime_path_budget(package)
    old_provenance = package / "provenance/v47_to_v48_multislice_pipeline.json"
    if old_provenance.exists():
        old_provenance.unlink()
    write_json(
        package / "provenance/v48_to_v49_mse4_maskwide.json",
        {
            "schema": "gap-node0071-v48-to-v49-mse4-maskwide-v1",
            "source_zip_sha256": SOURCE_SHA,
            "return_analysis_sha256": RETURN_REPORT_SHA,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "changed_surface": [
                "fresh identity",
                "read-only mask-wide MSE4 observer/parser",
                "finalizer fallback Python quoting",
                "manifest and return allowlist",
            ],
            "frozen": [
                "73 numeric/workload/config/golden files",
                "sum and exact uint8 tail semantics",
                "mapping, bitstream and execplan bytes",
                "timeout", "backpressure", "functional RTL",
            ],
            "server_action": False,
        },
    )
    (package / "README.md").write_text(
        "# GAP node0071 v49 MSE4 mask-wide diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "This successor preserves the v48 workload and all established "
        "checkpoints. It separates every remaining slice across GA outbuffer "
        "read, MSE4 index/request/queue/buffer/prepared/output-buffer, local "
        "request/write-data, and finish. State-only levels never count as "
        "progress. It also fixes the v48 finalizer fallback heredoc quoting.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh "
        "/absolute/path/to/NDP_copy0x`\n\n"
        f"Return: `/home/panqs/ndp/simresult/{INSTALL}_return.zip`.\n",
        encoding="utf-8", newline="\n",
    )
    patch_manifest(package)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    package = build(output)
    target = output / f"{INSTALL}.zip"
    deterministic_zip(package, target)
    digest = sha(target)
    sidecar = Path(str(target) + ".sha256")
    sidecar.write_text(
        f"{digest}  {target.name}\n", encoding="ascii", newline="\n"
    )
    print(json.dumps({
        "package": str(package),
        "zip": str(target),
        "bytes": target.stat().st_size,
        "sha256": digest,
        "sidecar": str(sidecar),
        "sidecar_sha256": sha(sidecar),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
