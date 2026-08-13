#!/usr/bin/env python3
"""Build the GAP node0071 v51 GA-outbuffer mode-factor diagnostic.

The exact repeat-safe v50 ZIP is the source.  Numeric/config/workload/golden,
timeout, backpressure, and functional RTL bytes are frozen.  Only identity,
package-local observer/parser, runner finalizer bindings, manifest/README, and
provenance change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "r5_n71_gap_v50_ga_ob_conjunction_diag"
INSTALL = "r5_n71_gap_v51_ga_ob_mode_factor_diag"
SOURCE_ZIP = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
SOURCE_SHA = "96c23c3762b9fca323ff3d76250f8ca9482c74d536a93b843321c8be3f37252d"
RETURN_SHA = "af493115127b0040d8bec83815d0e00d2fc90a7a9c559b11758ddb42982adfc2"
SERVER_RULE_SHA = "7cf2cb4511cba04cb8a14d06473d67061deae64f602988d27053d8289c964b13"
INDEX_SHA = "d4ff32f162538574a0dd48402e299fa25a11fb95074352c19fcfb007ebb77603"


class BuildError(RuntimeError):
    pass


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"{label}: expected one anchor, got {text.count(old)}")
    return text.replace(old, new, 1)


def extract_source(destination: Path) -> Path:
    if digest(SOURCE_ZIP) != SOURCE_SHA:
        raise BuildError("repeat-safe v50 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("source CRC failure")
        roots: set[str] = set()
        names: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in names
                or stat.S_ISLNK(mode)
            ):
                raise BuildError(f"unsafe source member: {info.filename}")
            names.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {SOURCE}:
            raise BuildError(f"source root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE


def deterministic_zip(package: Path, target: Path) -> None:
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            name = f"{package.name}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


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

    // v51: all-slice GA outbuffer mode/factor information-gain observer.
    // Only sticky qualified events count as progress.  Heartbeats contain
    // state snapshots and never consume the qualified-event budget.
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0]
          return_obs_v51_normal_req_mon,
          return_obs_v51_normal_bp_mon,
          return_obs_v51_normal_hs_mon,
          return_obs_v51_transout_req_mon,
          return_obs_v51_transout_bp_mon,
          return_obs_v51_transout_hs_mon,
          return_obs_v51_is_transout_mon,
          return_obs_v51_selected_rd_mon;
    generate
        for (genvar return_obs_v51_g = 0;
             return_obs_v51_g < `SLICE_GROUP_SIZE;
             return_obs_v51_g++) begin : RETURN_OBS_V51_G
            for (genvar return_obs_v51_s = 0;
                 return_obs_v51_s < `SLICE_GROUP_NUM;
                 return_obs_v51_s++) begin : RETURN_OBS_V51_S
                for (genvar return_obs_v51_r = 0;
                     return_obs_v51_r < `GA_ROW_PE_NUM;
                     return_obs_v51_r++) begin : RETURN_OBS_V51_R
                    for (genvar return_obs_v51_slot = 0;
                         return_obs_v51_slot < 2;
                         return_obs_v51_slot++) begin : RETURN_OBS_V51_SLOT
                        localparam int RETURN_OBS_V51_COL =
                            return_obs_v51_slot * 2;
                        assign return_obs_v51_normal_req_mon
                            [return_obs_v51_g][return_obs_v51_s]
                            [return_obs_v51_r][return_obs_v51_slot] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_v51_g].u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_v51_s].u_slice_wrapper
                            .u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_v51_r]
                            .GA_COL_PE[RETURN_OBS_V51_COL].GA_PE.u_GA_PE
                            .u_GA_PE_Outbuffer.normal_mode_wr_req;
                        assign return_obs_v51_normal_bp_mon
                            [return_obs_v51_g][return_obs_v51_s]
                            [return_obs_v51_r][return_obs_v51_slot] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_v51_g].u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_v51_s].u_slice_wrapper
                            .u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_v51_r]
                            .GA_COL_PE[RETURN_OBS_V51_COL].GA_PE.u_GA_PE
                            .u_GA_PE_Outbuffer.normal_mode_bp_pre;
                        assign return_obs_v51_normal_hs_mon
                            [return_obs_v51_g][return_obs_v51_s]
                            [return_obs_v51_r][return_obs_v51_slot] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_v51_g].u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_v51_s].u_slice_wrapper
                            .u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_v51_r]
                            .GA_COL_PE[RETURN_OBS_V51_COL].GA_PE.u_GA_PE
                            .u_GA_PE_Outbuffer.normal_mode_wr_handshake;
                        assign return_obs_v51_transout_req_mon
                            [return_obs_v51_g][return_obs_v51_s]
                            [return_obs_v51_r][return_obs_v51_slot] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_v51_g].u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_v51_s].u_slice_wrapper
                            .u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_v51_r]
                            .GA_COL_PE[RETURN_OBS_V51_COL].GA_PE.u_GA_PE
                            .u_GA_PE_Outbuffer.transout_mode_wr_req;
                        assign return_obs_v51_transout_bp_mon
                            [return_obs_v51_g][return_obs_v51_s]
                            [return_obs_v51_r][return_obs_v51_slot] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_v51_g].u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_v51_s].u_slice_wrapper
                            .u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_v51_r]
                            .GA_COL_PE[RETURN_OBS_V51_COL].GA_PE.u_GA_PE
                            .u_GA_PE_Outbuffer.transout_mode_bp_pre;
                        assign return_obs_v51_transout_hs_mon
                            [return_obs_v51_g][return_obs_v51_s]
                            [return_obs_v51_r][return_obs_v51_slot] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_v51_g].u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_v51_s].u_slice_wrapper
                            .u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_v51_r]
                            .GA_COL_PE[RETURN_OBS_V51_COL].GA_PE.u_GA_PE
                            .u_GA_PE_Outbuffer.transout_mode_wr_handshake;
                        assign return_obs_v51_is_transout_mon
                            [return_obs_v51_g][return_obs_v51_s]
                            [return_obs_v51_r][return_obs_v51_slot] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_v51_g].u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_v51_s].u_slice_wrapper
                            .u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_v51_r]
                            .GA_COL_PE[RETURN_OBS_V51_COL].GA_PE.u_GA_PE
                            .u_GA_PE_Outbuffer.alu_op_is_transout;
                        assign return_obs_v51_selected_rd_mon
                            [return_obs_v51_g][return_obs_v51_s]
                            [return_obs_v51_r][return_obs_v51_slot] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_v51_g].u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_v51_s].u_slice_wrapper
                            .u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_v51_r]
                            .GA_COL_PE[RETURN_OBS_V51_COL].GA_PE.u_GA_PE
                            .u_GA_PE_Outbuffer.ga_pe_outbuffer_rd_en;
                    end
                end
            end
        end
    endgenerate

    logic [`GLB_SLICE_NUM-1:0] return_obs_v51_alu_req_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v51_normal_mode_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v51_transout_mode_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v51_normal_hs_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v51_transout_hs_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v51_selected_wr_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v51_nonempty_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v51_selected_rd_seen;
    logic [8*`GLB_SLICE_NUM-1:0] return_obs_v51_prev_qualified;
    bit return_obs_v51_enabled;
    longint unsigned return_obs_v51_db_cycles;
    longint unsigned return_obs_v51_emit_count;

    initial begin
        return_obs_v51_enabled =
            $test$plusargs("RETURN_OBS_GA_OB_MODE_FACTOR");
        return_obs_v51_db_cycles = 0;
        return_obs_v51_emit_count = 0;
        return_obs_v51_prev_qualified = '0;
        #0;
        if (return_obs_enabled && return_obs_v51_enabled &&
            return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "# ga_ob_mode_factor=1 selected_mask=0x0000ffff owner=clk_sg reporter=clk_db qualified_limit=128 heartbeat_cycles=1048576 private_xmr_target=GA_PE_Outbuffer.sv"
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin
        if (!u_NDP_Top_new.rst_n_sg) begin
            return_obs_v51_alu_req_seen <= '0;
            return_obs_v51_normal_mode_seen <= '0;
            return_obs_v51_transout_mode_seen <= '0;
            return_obs_v51_normal_hs_seen <= '0;
            return_obs_v51_transout_hs_seen <= '0;
            return_obs_v51_selected_wr_seen <= '0;
            return_obs_v51_nonempty_seen <= '0;
            return_obs_v51_selected_rd_seen <= '0;
        end
        else if (return_obs_enabled && return_obs_v51_enabled) begin
            for (int g = 0; g < `SLICE_GROUP_SIZE; g++) begin
                for (int s = 0; s < `SLICE_GROUP_NUM; s++) begin
                    int id;
                    bit req, normal_mode, transout_mode, normal_hs;
                    bit transout_hs, selected_wr, nonempty, selected_rd;
                    id = g * `SLICE_GROUP_NUM + s;
                    req = 1'b0;
                    normal_mode = 1'b0;
                    transout_mode = 1'b0;
                    normal_hs = 1'b0;
                    transout_hs = 1'b0;
                    selected_wr = 1'b0;
                    nonempty = 1'b0;
                    selected_rd = 1'b0;
                    for (int r = 0; r < `GA_ROW_PE_NUM; r++) begin
                        for (int slot = 0; slot < 2; slot++) begin
                            req |= return_obs_v51_normal_req_mon[g][s][r][slot];
                            normal_mode |=
                                return_obs_v51_normal_req_mon[g][s][r][slot] &&
                                !return_obs_v51_is_transout_mon[g][s][r][slot];
                            transout_mode |=
                                return_obs_v51_normal_req_mon[g][s][r][slot] &&
                                return_obs_v51_is_transout_mon[g][s][r][slot];
                            normal_hs |=
                                return_obs_v51_normal_hs_mon[g][s][r][slot];
                            transout_hs |=
                                return_obs_v51_transout_hs_mon[g][s][r][slot];
                            selected_wr |=
                                return_obs_ga_outbuffer_wr_mon[g][s][r][slot];
                            nonempty |=
                                return_obs_ga_ob_count_mon[g][s][r][slot] != 0;
                            selected_rd |=
                                return_obs_v51_selected_rd_mon[g][s][r][slot];
                        end
                    end
                    if (req) return_obs_v51_alu_req_seen[id] <= 1'b1;
                    if (normal_mode)
                        return_obs_v51_normal_mode_seen[id] <= 1'b1;
                    if (transout_mode)
                        return_obs_v51_transout_mode_seen[id] <= 1'b1;
                    if (normal_hs)
                        return_obs_v51_normal_hs_seen[id] <= 1'b1;
                    if (transout_hs)
                        return_obs_v51_transout_hs_seen[id] <= 1'b1;
                    if (selected_wr)
                        return_obs_v51_selected_wr_seen[id] <= 1'b1;
                    if (nonempty)
                        return_obs_v51_nonempty_seen[id] <= 1'b1;
                    if (selected_rd)
                        return_obs_v51_selected_rd_seen[id] <= 1'b1;
                end
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        logic [8*`GLB_SLICE_NUM-1:0] qualified_snapshot;
        bit qualified_changed;
        bit heartbeat;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_v51_db_cycles = 0;
            return_obs_v51_emit_count = 0;
            return_obs_v51_prev_qualified = '0;
        end
        else if (return_obs_enabled && return_obs_v51_enabled &&
                 return_obs_fd != 0) begin
            return_obs_v51_db_cycles++;
            qualified_snapshot = {
                return_obs_v51_selected_rd_seen,
                return_obs_v51_nonempty_seen,
                return_obs_v51_selected_wr_seen,
                return_obs_v51_transout_hs_seen,
                return_obs_v51_normal_hs_seen,
                return_obs_v51_transout_mode_seen,
                return_obs_v51_normal_mode_seen,
                return_obs_v51_alu_req_seen
            };
            qualified_changed =
                qualified_snapshot != return_obs_v51_prev_qualified;
            heartbeat = (return_obs_v51_db_cycles % 1048576) == 0;
            if ((qualified_changed &&
                 return_obs_v51_emit_count < 128) || heartbeat) begin
                if (qualified_changed)
                    return_obs_v51_emit_count++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | GA_OB_MODE_FACTOR_STATE_V1 | event=%s n=%0d db_cycle=%0d alu_req=0x%0h normal_mode=0x%0h transout_mode=0x%0h normal_hs=0x%0h transout_hs=0x%0h selected_wr=0x%0h nonempty=0x%0h selected_rd=0x%0h",
                    $time,
                    (qualified_changed ? "QUALIFIED_EDGE" : "HEARTBEAT"),
                    return_obs_v51_emit_count,
                    return_obs_v51_db_cycles,
                    return_obs_v51_alu_req_seen,
                    return_obs_v51_normal_mode_seen,
                    return_obs_v51_transout_mode_seen,
                    return_obs_v51_normal_hs_seen,
                    return_obs_v51_transout_hs_seen,
                    return_obs_v51_selected_wr_seen,
                    return_obs_v51_nonempty_seen,
                    return_obs_v51_selected_rd_seen
                );
                $fflush(return_obs_fd);
            end
            return_obs_v51_prev_qualified = qualified_snapshot;
        end
    end
'''


PARSER = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path

FIELDS=("alu_req","normal_mode","transout_mode","normal_hs","transout_hs",
        "selected_wr","nonempty","selected_rd")
PATTERN=re.compile(
  r"GA_OB_MODE_FACTOR_STATE_V1\s+\|\s+event=(QUALIFIED_EDGE|HEARTBEAT).*?"+
  r"\s+".join(fr"{name}=0x([0-9a-fA-F]+)" for name in FIELDS))

def decide(text:str)->dict:
    masks={name:0 for name in FIELDS}; qualified=0; heartbeat=0
    for match in PATTERN.finditer(text):
        event=match.group(1)
        values={name:int(match.group(i+2),16)
                for i,name in enumerate(FIELDS)}
        if event=="QUALIFIED_EDGE":
            qualified+=1
            for name,value in values.items(): masks[name]|=value
        else:
            heartbeat+=1
    rows=[]
    for sid in range(16):
        seen={name:bool(masks[name]&(1<<sid)) for name in FIELDS}
        if not seen["alu_req"]: boundary="ALU_RESULT_REQUEST_ABSENT"
        elif not (seen["normal_mode"] or seen["transout_mode"]):
            boundary="MODE_SELECTION_UNOBSERVED"
        elif seen["normal_mode"] and not seen["normal_hs"]:
            boundary="NORMAL_MODE_HANDSHAKE_ABSENT"
        elif seen["transout_mode"] and not seen["transout_hs"]:
            boundary="TRANSOUT_MODE_HANDSHAKE_ABSENT"
        elif not seen["selected_wr"]:
            boundary="SELECTED_OUTBUFFER_WRITE_ABSENT"
        elif not seen["nonempty"]:
            boundary="OUTBUFFER_NONEMPTY_ABSENT_AFTER_WRITE"
        elif not seen["selected_rd"]:
            boundary="SELECTED_OUTBUFFER_READ_ABSENT"
        else: boundary="SELECTED_OUTBUFFER_WRITE_READ_CHAIN_OBSERVED"
        rows.append({"slice":sid,"seen":seen,"first_missing":boundary})
    marker="# ga_ob_mode_factor=1" in text
    return {
      "schema":"gap-node0071-ga-ob-mode-factor-decision-v1",
      "feature_enabled_marker":marker,
      "qualified_record_count":qualified,
      "heartbeat_record_count":heartbeat,
      "stable_level_is_progress":False,
      "qualified_masks":{k:f"0x{v:04x}" for k,v in masks.items()},
      "per_slice":rows,
      "status":"DIAGNOSTIC_EVIDENCE_AVAILABLE"
               if marker and qualified else "FAIL_CLOSED",
      "natural_terminal":False,
    }

def self_test()->dict:
    def line(event:str,**kw)->str:
        values={name:kw.get(name,0) for name in FIELDS}
        return ("0 | GA_OB_MODE_FACTOR_STATE_V1 | event="+event+
                " n=1 db_cycle=1 "+" ".join(
                  f"{k}=0x{v:x}" for k,v in values.items()))
    marker="# ga_ob_mode_factor=1\n"
    normal=decide(marker+line("QUALIFIED_EDGE",alu_req=1,normal_mode=1,
      normal_hs=1,selected_wr=1,nonempty=1,selected_rd=1))
    trans=decide(marker+line("QUALIFIED_EDGE",alu_req=2,transout_mode=2,
      transout_hs=2,selected_wr=2,nonempty=2,selected_rd=2))
    stable=decide(marker+line("HEARTBEAT",alu_req=4,normal_mode=4,
      normal_hs=4,selected_wr=4,nonempty=4,selected_rd=4))
    blocked=decide(marker+line("QUALIFIED_EDGE",alu_req=8,normal_mode=8))
    simultaneous=decide(marker+line("QUALIFIED_EDGE",alu_req=0xffff,
      normal_mode=0x5555,transout_mode=0xaaaa,normal_hs=0x5555,
      transout_hs=0xaaaa,selected_wr=0xffff,nonempty=0xffff,
      selected_rd=0xffff))
    checks={
      "normal_chain":normal["per_slice"][0]["first_missing"]==
        "SELECTED_OUTBUFFER_WRITE_READ_CHAIN_OBSERVED",
      "transout_chain":trans["per_slice"][1]["first_missing"]==
        "SELECTED_OUTBUFFER_WRITE_READ_CHAIN_OBSERVED",
      "stable_level_not_progress":stable["qualified_record_count"]==0 and
        stable["per_slice"][2]["first_missing"]=="ALU_RESULT_REQUEST_ABSENT",
      "normal_bp_boundary":blocked["per_slice"][3]["first_missing"]==
        "NORMAL_MODE_HANDSHAKE_ABSENT",
      "simultaneous_all_slices":all(
        r["first_missing"]=="SELECTED_OUTBUFFER_WRITE_READ_CHAIN_OBSERVED"
        for r in simultaneous["per_slice"]),
    }
    return {"schema":"gap-node0071-ga-ob-mode-factor-self-test-v1",
            "checks":checks,"pass":all(checks.values())}

def main()->int:
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("analyze"); a.add_argument("--observer-log",type=Path,required=True)
    a.add_argument("--output",type=Path,required=True)
    s=sub.add_parser("self-test"); s.add_argument("--output",type=Path,required=True)
    ns=ap.parse_args()
    value=self_test() if ns.cmd=="self-test" else decide(
      ns.observer_log.read_text(encoding="utf-8",errors="replace")
      if ns.observer_log.is_file() else "")
    ns.output.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",
                         encoding="utf-8")
    return 0 if (value.get("pass",True) and
      (ns.cmd=="self-test" or value["status"]!="FAIL_CLOSED")) else 1
if __name__=="__main__": raise SystemExit(main())
'''


def patch_observer(package: Path) -> None:
    observer = package / "tb_probe/native_return_observer.svh"
    text = observer.read_text(encoding="utf-8")
    if "GA_OB_MODE_FACTOR_STATE_V1" in text:
        raise BuildError("v51 observer already present")
    observer.write_text(text + OBSERVER_EXTENSION, encoding="utf-8", newline="\n")
    parser = package / "package_tools/gap_node0071_ga_ob_mode_factor_decision.py"
    parser.write_text(PARSER, encoding="utf-8", newline="\n")


def patch_runner(package: Path) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'gaob_tool="$package_root/package_tools/'
        'gap_node0071_ga_ob_conjunction_decision.py"',
        'gaob_tool="$package_root/package_tools/'
        'gap_node0071_ga_ob_conjunction_decision.py"\n'
        'gaobmode_tool="$package_root/package_tools/'
        'gap_node0071_ga_ob_mode_factor_decision.py"',
        "v51 tool declaration",
    )
    canonical_anchor = (
        'package_root="$(cd "$package_root" && pwd -P)" || '
        'runner_fail 2 "package root cannot be resolved"'
    )
    rebound = canonical_anchor + """
canonical_tool="$package_root/package_tools/gap_node0071_canonical_decision.py"
stage_tool="$package_root/package_tools/gap_node0071_stage_transition_decision.py"
multislice_tool="$package_root/package_tools/gap_node0071_multislice_pipeline_decision.py"
mse4mask_tool="$package_root/package_tools/gap_node0071_mse4_maskwide_decision.py"
gaob_tool="$package_root/package_tools/gap_node0071_ga_ob_conjunction_decision.py"
gaobmode_tool="$package_root/package_tools/gap_node0071_ga_ob_mode_factor_decision.py" """
    text = replace_once(
        text, canonical_anchor, rebound.rstrip(), "absolute parser rebinding"
    )
    text = replace_once(
        text,
        "       grep -Fq 'GA_OB_CONJ_STATE_V1' \"$observer_log\"; then",
        "       grep -Fq 'GA_OB_CONJ_STATE_V1' \"$observer_log\" &&\n"
        "       grep -Fq 'ga_ob_mode_factor=1' \"$observer_log\" &&\n"
        "       grep -Fq 'GA_OB_MODE_FACTOR_STATE_V1' \"$observer_log\"; then",
        "observer binding positive",
    )
    text = replace_once(
        text,
        "ga_ob_conjunction_records_returned=true\\n'",
        "ga_ob_conjunction_records_returned=true\\n"
        "ga_ob_mode_factor_enabled=true\\n"
        "ga_ob_mode_factor_records_returned=true\\n'",
        "observer binding true",
    )
    text = replace_once(
        text,
        "ga_ob_conjunction_records_returned=false\\n'",
        "ga_ob_conjunction_records_returned=false\\n"
        "ga_ob_mode_factor_enabled=false\\n"
        "ga_ob_mode_factor_records_returned=false\\n'",
        "observer binding false",
    )
    gaob_status = (
        '      printf "ga_ob_conjunction=%s\\n" "$?" '
        '>>"$evidence_root/decision_parser_status.txt"'
    )
    mode_parse = (
        '      python3 "$gaobmode_tool" analyze --observer-log "$observer_log" '
        '--output "$evidence_root/ga_ob_mode_factor_decision.json" '
        '>/dev/null 2>>"$evidence_root/decision_parser_stderr.log"\n'
        '      printf "ga_ob_mode_factor=%s\\n" "$?" '
        '>>"$evidence_root/decision_parser_status.txt"'
    )
    text = replace_once(
        text, gaob_status, gaob_status + "\n" + mode_parse, "v51 parser call"
    )
    old_fallback = (
        'python3 - "$evidence_root/stage_transition_decision.json"       '
        '"$evidence_root/multislice_pipeline_decision.json"       '
        '"$evidence_root/mse4_maskwide_decision.json"       '
        '"$evidence_root/ga_ob_conjunction_decision.json"       '
        '"$evidence_root/canonical_decision.json" "$signal_name" '
        '"$simulation_status" <<\'PY\''
    )
    new_fallback = (
        'python3 - "$evidence_root/stage_transition_decision.json"       '
        '"$evidence_root/multislice_pipeline_decision.json"       '
        '"$evidence_root/mse4_maskwide_decision.json"       '
        '"$evidence_root/ga_ob_conjunction_decision.json"       '
        '"$evidence_root/ga_ob_mode_factor_decision.json"       '
        '"$evidence_root/canonical_decision.json" "$signal_name" '
        '"$simulation_status" <<\'PY\''
    )
    text = replace_once(text, old_fallback, new_fallback, "fallback argv")
    text = replace_once(
        text,
        '    {"schema":"canonical-diagnostic-decision-v1","decision":"FAIL_CLOSED",',
        '    {"schema":"gap-node0071-ga-ob-mode-factor-decision-v1",'
        '"status":"FAIL_CLOSED",\n'
        '     "reason":reason,"natural_terminal":False},\n'
        '    {"schema":"canonical-diagnostic-decision-v1",'
        '"decision":"FAIL_CLOSED",',
        "fallback payload",
    )
    text = replace_once(
        text,
        '"signal":sys.argv[6],"simulation_status":int(sys.argv[7]),',
        '"signal":sys.argv[7],"simulation_status":int(sys.argv[8]),',
        "fallback indices",
    )
    text = replace_once(
        text,
        "for name,payload in zip(sys.argv[1:6],payloads):",
        "for name,payload in zip(sys.argv[1:7],payloads):",
        "fallback output set",
    )
    selftest = (
        'python3 "$gaob_tool" self-test --output '
        '"$evidence_root/ga_ob_conjunction_predicate_self_test.json" '
        '>/dev/null || runner_fail 8 '
        '"GA outbuffer conjunction predicate self-test failed"'
    )
    text = replace_once(
        text,
        selftest,
        selftest + '\npython3 "$gaobmode_tool" self-test --output '
        '"$evidence_root/ga_ob_mode_factor_predicate_self_test.json" '
        '>/dev/null || runner_fail 8 '
        '"GA outbuffer mode-factor predicate self-test failed"',
        "v51 self-test",
    )
    text = replace_once(
        text,
        "  +RETURN_OBS_GA_OB_CONJUNCTION",
        "  +RETURN_OBS_GA_OB_CONJUNCTION\n"
        "  +RETURN_OBS_GA_OB_MODE_FACTOR",
        "v51 plusarg",
    )
    runner.write_text(text, encoding="utf-8", newline="\n")


def files_map(package: Path) -> dict[str, dict[str, Any]]:
    manifest = package / "TEST_PACKAGE_MANIFEST.json"
    return {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest
    }


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/gap_node0071_complete_server_runtime.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text, "len(allowlist) != 81", "len(allowlist) != 83",
        "return allowlist cardinality"
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["install_name"] = INSTALL
    value["package_name"] = f"{INSTALL}.zip"
    value["return_name"] = f"{INSTALL}_return"
    value["test_id"] = "r5-gap-node0071-v51-ga-outbuffer-mode-factor-diagnostic"
    value["source_package"] = {
        "install_name": SOURCE,
        "sha256": SOURCE_SHA,
        "return_sha256": RETURN_SHA,
        "return_analysis": (
            "artifacts/operator_config_validation/"
            "r5-gap-node0071-v50-return-analysis/report.json"
        ),
    }
    value["rule_receipts"]["server_package_rule_sha256"] = SERVER_RULE_SHA
    value["rule_receipts"]["generation_index_sha256"] = INDEX_SHA
    rtl = (
        ROOT / "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/"
        "GA_PE_Outbuffer.sv"
    )
    value["ga_outbuffer_mode_factor_contract"] = {
        "feature": "GA_OB_MODE_FACTOR_STATE_V1",
        "plusarg": "+RETURN_OBS_GA_OB_MODE_FACTOR",
        "selected_mask": "0x0000ffff",
        "qualified_chain": [
            "ALU result write request",
            "normal-vs-transout mode selection",
            "selected-mode write handshake",
            "selected GA outbuffer write",
            "outbuffer nonempty",
            "selected GA outbuffer read",
        ],
        "owner_clock": "clk_sg",
        "reporter_clock": "clk_db",
        "qualified_emit_limit": 128,
        "heartbeat_cycles": 1048576,
        "stable_level_is_progress": False,
        "observer_budget_fix": (
            "state edges cannot consume the qualified-event limit"
        ),
        "private_xmr": {
            "necessary": True,
            "target_module": "GA_PE_Outbuffer",
            "target_relative_path": (
                "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/"
                "GA_PE_Outbuffer.sv"
            ),
            "target_sha256": digest(rtl),
            "clock": "clk_sg",
            "leaves": [
                "normal_mode_wr_req",
                "normal_mode_bp_pre",
                "normal_mode_wr_handshake",
                "transout_mode_wr_req",
                "transout_mode_bp_pre",
                "transout_mode_wr_handshake",
                "alu_op_is_transout",
                "ga_pe_outbuffer_rd_en",
            ],
        },
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
    }
    additions = [
        {
            "source_root": "evidence",
            "source_path": "ga_ob_mode_factor_decision.json",
            "target_path": "evidence/ga_ob_mode_factor_decision.json",
            "required": True,
            "max_bytes": 65536,
            "missing_meaning": "GA outbuffer mode-factor decision absent",
        },
        {
            "source_root": "evidence",
            "source_path": "ga_ob_mode_factor_predicate_self_test.json",
            "target_path": "evidence/ga_ob_mode_factor_predicate_self_test.json",
            "required": True,
            "max_bytes": 32768,
            "missing_meaning": "GA outbuffer mode-factor predicate self-test absent",
        },
    ]
    targets = {row["target_path"] for row in value["return_allowlist"]}
    for row in additions:
        if row["target_path"] not in targets:
            value["return_allowlist"].append(row)
    value["budgets"]["return_extracted_max_bytes"] += 98304
    value["budgets"]["return_zip_max_bytes"] += 65536
    value["release_gate_matrix"] = [
        {
            "gate_id": "PACKAGE_BOOTSTRAP_RUNTIME_LAYOUT",
            "applicability": "blocking_applicable_identity_and_runner_changed",
            "status": "PASS_PENDING_FINAL_ZIP_VALIDATION",
        },
        {
            "gate_id": "PACKAGE_LOCAL_HDL",
            "applicability": "blocking_applicable_observer_changed",
            "status": "PASS_PENDING_CHANGED_SURFACE_SCOPE_VALIDATION",
        },
        {
            "gate_id": "DIAGNOSTIC_SEMANTICS",
            "applicability": "blocking_applicable_predicate_changed",
            "status": "PASS_PENDING_EXACT_TRACE",
        },
        {
            "gate_id": "MATERIALIZED_CONFIG",
            "applicability": "receipt_reuse_byte_equal",
            "status": "PASS",
        },
        {
            "gate_id": "RETURN_RESULT_CONTRACT",
            "applicability": "blocking_applicable_parser_finalizer_changed",
            "status": "PASS_PENDING_SIGNAL_FINALIZER_VALIDATION",
        },
        {
            "gate_id": "FROZEN_NUMERIC_GOLDEN",
            "applicability": "record_only_byte_equal",
            "status": "PASS",
        },
    ]
    value["candidate_release"] = False
    value["package_class"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    value["evidence_level"] = "E2_LOCAL_COMPLETE_NODE"
    value["status"] = "PACKAGE_READY_NOT_RUN"
    value["numeric_analysis_repeated"] = False
    value["sum_or_tail_numeric_reexecuted"] = False
    value["functional_rtl_modified"] = False
    runtime_contract = json.loads(
        (package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )
    attempt = "a" * int(
        runtime_contract["path_budget"]["attempt_max_chars"]
    )
    projected = {
        f"install/cfg_pkg/{INSTALL}/"
        + item.relative_to(package / "workload").as_posix()
        for item in (package / "workload").rglob("*")
        if item.is_file()
    } | {
        item.replace("{attempt}", attempt).replace("{name}", INSTALL)
        for item in
        runtime_contract["path_budget"]["additional_projected_paths"]
    }
    longest = max(projected, key=lambda item: (len(item), item))
    root_max = int(
        runtime_contract["path_budget"]["declared_target_root_max_chars"]
    )
    value["path_length_budget"]["longest_projected_relative_path"] = longest
    value["path_length_budget"]["longest_projected_relative_path_chars"] = len(
        longest
    )
    value["path_length_budget"]["max_projected_absolute_path_chars"] = (
        root_max + 1 + len(longest)
    )
    value["path_length_budget"]["pass"] = (
        root_max + 1 + len(longest)
        <= int(value["path_length_budget"]["absolute_path_limit_chars"])
    )
    value["files"] = files_map(package)
    write_json(path, value)
    value["files"] = files_map(package)
    write_json(path, value)


def patch_contract(package: Path) -> None:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    additions = value["path_budget"]["additional_projected_paths"]
    for relative in (
        f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/"
        "ga_ob_mode_factor_decision.json",
        f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/"
        "ga_ob_mode_factor_predicate_self_test.json",
    ):
        if relative not in additions:
            additions.append(relative)
    additions.sort()
    attempt = "a" * int(value["path_budget"]["attempt_max_chars"])
    longest = max(
        (
            item.replace("{attempt}", attempt).replace("{name}", INSTALL)
            for item in additions
        ),
        key=lambda item: (len(item), item),
    )
    root_max = int(value["path_budget"]["declared_target_root_max_chars"])
    value["path_budget"]["max_projected_absolute_path_chars"] = (
        root_max + 1 + len(longest)
    )
    write_json(path, value)


def build(output: Path) -> Path:
    package = output / INSTALL
    if package.exists():
        raise BuildError(f"refusing to overwrite {package}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gap-v51-source-") as temp:
        shutil.copytree(extract_source(Path(temp)), package)
    replace_identity(package)
    patch_observer(package)
    patch_runner(package)
    patch_runtime(package)
    patch_contract(package)
    write_json(
        package / "provenance/v50_to_v51_ga_ob_mode_factor.json",
        {
            "schema": "gap-node0071-v50-to-v51-ga-ob-mode-factor-v1",
            "source_zip_sha256": SOURCE_SHA,
            "return_sha256": RETURN_SHA,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "first_divergence": (
                "V50_GA_OB_CONJUNCTION_QUALIFIED_TRACE_SATURATED_ON_"
                "SLICE0_STATE_EDGES_BEFORE_SLICES1_15"
            ),
            "changed_surface": [
                "fresh identity",
                "qualified-only all-slice GA mode-factor observer/parser",
                "absolute package-root parser rebinding after canonicalization",
                "manifest/return allowlist/provenance",
            ],
            "frozen": [
                "73 numeric/workload/config/golden files",
                "sum and exact uint8 tail semantics",
                "mapping, bitstream, execplan and SCA bytes except identity text",
                "timeout and backpressure",
                "functional RTL",
                "repeat-safe owned reset and unique return semantics",
            ],
            "server_action": False,
        },
    )
    (package / "README.md").write_text(
        "# GAP node0071 v51 GA outbuffer mode-factor diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "This successor preserves the repeat-safe v50 workload and all numeric "
        "semantics. It fixes package-root binding for finalizer parsers and "
        "replaces state-edge budget consumption with qualified-only all-slice "
        "mode-factor evidence across ALU request, normal/transout selection, "
        "selected outbuffer write/nonempty/read, and the inherited MSE4 chain. "
        "Heartbeat state is never counted as progress.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh "
        "/absolute/path/to/NDP_copy0x`\n\n"
        "Each execution publishes a unique return under "
        "`/home/panqs/ndp/simresult`.\n",
        encoding="utf-8",
        newline="\n",
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
    deterministic_zip(package, target)
    sidecar = Path(str(target) + ".sha256")
    sidecar.write_text(
        f"{digest(target)}  {target.name}\n", encoding="ascii", newline="\n"
    )
    print(json.dumps({
        "package": str(package),
        "zip": str(target),
        "bytes": target.stat().st_size,
        "sha256": digest(target),
        "sidecar": str(sidecar),
        "sidecar_sha256": digest(sidecar),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
