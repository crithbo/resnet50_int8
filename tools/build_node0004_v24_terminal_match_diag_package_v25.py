from __future__ import annotations

import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


SOURCE_NAME = "r5_n4_hw_v24_final_release_diag_compilefix"
INSTALL_NAME = "r5_n4_hw_v25_terminal_match_diag"
SOURCE_ZIP_SHA256 = (
    "3701226c52de41a6982dd0ac9a111ade26c26ed088eee53d62fcc038cd5980fc"
)
RETURN_ZIP_SHA256 = (
    "e403d08c5ea0b6dd252f72d4378e78b8f15c68165153d304dde7c1834fde0999"
)
PLAN_MUTABLE_SHA256 = (
    "12ff0478c8a1993733e69f544843906b53a86a492c41e9e8d72306b4395e1fcd"
)
INDEX_SHA256 = (
    "3f992273e86f02b8ea4f68f217e686a5a525a045b5fd4d6c88f2f8ef5d1ff4c5"
)
SERVER_RULE_SHA256 = (
    "de1d7d1ec298d9227b1fc8b9bf408b702e91cb318d8172a0e8c80ec5fc291991"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{SOURCE_NAME}.zip"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


class BuildError(RuntimeError):
    pass


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise BuildError(
            f"patch anchor count differs for {path}: {text.count(old)}"
        )
    path.write_text(
        text.replace(old, new, 1),
        encoding="utf-8",
        newline="\n",
    )


def safe_extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise BuildError("v24 source ZIP SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v24 source ZIP CRC failed")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                raise BuildError(f"unsafe v24 member: {info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"v24 root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE_NAME


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, INSTALL_NAME),
                encoding="utf-8",
                newline="\n",
            )


def xmr_leaf(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen\n"
        "                                [return_obs_tm_group]\n"
        "                                .u_slice_with_datahub_mc_group\n"
        "                                .slice_group_gen[return_obs_tm_slice]\n"
        "                                .u_slice_wrapper.u_Slice\n"
        "                                .u_Specialized_Array.u_SA_PE_Group\n"
        "                                .SA_ROW_PE[return_obs_tm_row]\n"
        "                                .SA_COL_PE[return_obs_tm_col]\n"
        "                                .u_SA_PE.u_SA_PE_Control_Block\n"
        f"                                .{leaf}"
    )


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "TERMINAL_MATCH_BOUNDARY_V1" in text:
        raise BuildError("v25 terminal-match diagnostic already present")

    block = f"""

    // v25: exact raw-last -> qualified terminal-match boundary.
    // Levels are state only. Counters increment only on a raw edge or an
    // accepted operand tuple.
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_INPORT_NUM-1:0] return_obs_tm_raw_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_INPORT_NUM-1:0] return_obs_tm_raw_last_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_INPORT_NUM-1:0] return_obs_tm_raw_same_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_INPORT_NUM-1:0] return_obs_tm_gotten_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_INPORT_NUM-1:0] return_obs_tm_masked_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_INPORT_NUM-1:0] return_obs_tm_masked_last_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_INPORT_NUM-1:0][`PORT_LAST_INDEX-1:0]
          return_obs_tm_raw_last_index_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_tm_all_matched_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_tm_pipeline_enable_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`PORT_LAST_INDEX-1:0] return_obs_tm_transout_cfg_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`PORT_LAST_INDEX:0] return_obs_tm_diff_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_tm_ignore_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_tm_matched_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_tm_out_mon;

    generate
        for (genvar return_obs_tm_group = 0;
             return_obs_tm_group < `SLICE_GROUP_SIZE;
             return_obs_tm_group++) begin : RETURN_OBS_TM_GROUP_GEN
            for (genvar return_obs_tm_slice = 0;
                 return_obs_tm_slice < `SLICE_GROUP_NUM;
                 return_obs_tm_slice++) begin : RETURN_OBS_TM_SLICE_GEN
                for (genvar return_obs_tm_row = 0;
                     return_obs_tm_row < `SA_ROW_PE_NUM;
                     return_obs_tm_row++) begin : RETURN_OBS_TM_ROW_GEN
                    for (genvar return_obs_tm_col = 0;
                         return_obs_tm_col < `SA_COL_PE_NUM;
                         return_obs_tm_col++) begin : RETURN_OBS_TM_COL_GEN
                        assign return_obs_tm_raw_valid_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_inport_valid_bit_unmasked")};
                        assign return_obs_tm_raw_last_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_inport_last_bit_unmasked")};
                        assign return_obs_tm_raw_same_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_inport_same_bit_unmasked")};
                        assign return_obs_tm_gotten_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_inport_gotten_bit")};
                        assign return_obs_tm_masked_valid_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_inport_valid_bit_masked")};
                        assign return_obs_tm_masked_last_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_inport_last_bit_masked")};
                        assign return_obs_tm_raw_last_index_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_inport_last_index")};
                        assign return_obs_tm_all_matched_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_all_inport_matched")};
                        assign return_obs_tm_pipeline_enable_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_alu_pipeline0_enable")};
                        assign return_obs_tm_transout_cfg_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_transout_last_index")};
                        assign return_obs_tm_diff_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_transout_last_index_diff")};
                        assign return_obs_tm_ignore_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_transout_last_ignore")};
                        assign return_obs_tm_matched_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_transout_last_matched")};
                        assign return_obs_tm_out_mon
                            [return_obs_tm_group][return_obs_tm_slice]
                            [return_obs_tm_row][return_obs_tm_col] =
                            {xmr_leaf("sa_pe_transout_last_out")};
                    end
                end
            end
        end
    endgenerate

    logic [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          [`SA_PE_INPORT_NUM-1:0] return_obs_tm_prev_raw_last;
    longint unsigned return_obs_tm_raw_last_edge [0:1];
    longint unsigned return_obs_tm_raw_last_mask_suppressed [0:1];
    longint unsigned return_obs_tm_qualified_accepts;
    longint unsigned return_obs_tm_qualified_terminal_accepts;
    longint unsigned return_obs_tm_qualified_terminal_equal;
    longint unsigned return_obs_tm_qualified_terminal_ignore;
    longint unsigned return_obs_tm_qualified_terminal_out;
    longint unsigned return_obs_tm_terminal_hist [0:15];
    integer return_obs_tm_edge_records;

    initial begin
        return_obs_tm_edge_records = 0;
        return_obs_tm_raw_last_edge[0] = 0;
        return_obs_tm_raw_last_edge[1] = 0;
        return_obs_tm_raw_last_mask_suppressed[0] = 0;
        return_obs_tm_raw_last_mask_suppressed[1] = 0;
        return_obs_tm_qualified_accepts = 0;
        return_obs_tm_qualified_terminal_accepts = 0;
        return_obs_tm_qualified_terminal_equal = 0;
        return_obs_tm_qualified_terminal_ignore = 0;
        return_obs_tm_qualified_terminal_out = 0;
        for (int return_obs_tm_h = 0; return_obs_tm_h < 16;
             return_obs_tm_h++)
            return_obs_tm_terminal_hist[return_obs_tm_h] = 0;
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_tm_prev_raw_last = 0;
            return_obs_tm_edge_records = 0;
            return_obs_tm_raw_last_edge[0] = 0;
            return_obs_tm_raw_last_edge[1] = 0;
            return_obs_tm_raw_last_mask_suppressed[0] = 0;
            return_obs_tm_raw_last_mask_suppressed[1] = 0;
            return_obs_tm_qualified_accepts = 0;
            return_obs_tm_qualified_terminal_accepts = 0;
            return_obs_tm_qualified_terminal_equal = 0;
            return_obs_tm_qualified_terminal_ignore = 0;
            return_obs_tm_qualified_terminal_out = 0;
            for (int return_obs_tm_h = 0; return_obs_tm_h < 16;
                 return_obs_tm_h++)
                return_obs_tm_terminal_hist[return_obs_tm_h] = 0;
        end
        else if (return_obs_fr_enabled && return_obs_active) begin
            for (int return_obs_tm_r = 0;
                 return_obs_tm_r < `SA_ROW_PE_NUM;
                 return_obs_tm_r++) begin
                for (int return_obs_tm_c = 0;
                     return_obs_tm_c < `SA_COL_PE_NUM;
                     return_obs_tm_c++) begin
                    bit return_obs_tm_accept;
                    bit return_obs_tm_terminal_accept;
                    bit return_obs_tm_raw_edge_any;
                    return_obs_tm_accept =
                        return_obs_tm_all_matched_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_tm_r][return_obs_tm_c] &&
                        return_obs_tm_pipeline_enable_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_tm_r][return_obs_tm_c];
                    return_obs_tm_terminal_accept =
                        return_obs_tm_accept &&
                        (|return_obs_tm_masked_last_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_tm_r][return_obs_tm_c][1:0]);
                    return_obs_tm_raw_edge_any = 1'b0;
                    for (int return_obs_tm_p = 0; return_obs_tm_p < 2;
                         return_obs_tm_p++) begin
                        if (
                            return_obs_tm_raw_last_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c]
                                [return_obs_tm_p] &&
                            !return_obs_tm_prev_raw_last
                                [return_obs_tm_r][return_obs_tm_c]
                                [return_obs_tm_p]
                        ) begin
                            return_obs_tm_raw_last_edge[return_obs_tm_p]++;
                            return_obs_tm_raw_edge_any = 1'b1;
                            if (
                                !return_obs_tm_masked_last_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id]
                                    [return_obs_tm_r][return_obs_tm_c]
                                    [return_obs_tm_p]
                            )
                                return_obs_tm_raw_last_mask_suppressed
                                    [return_obs_tm_p]++;
                        end
                    end
                    if (return_obs_tm_accept)
                        return_obs_tm_qualified_accepts++;
                    if (return_obs_tm_terminal_accept) begin
                        return_obs_tm_qualified_terminal_accepts++;
                        return_obs_tm_terminal_hist[
                            return_obs_fr_input_last_index_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c]
                        ]++;
                        if (
                            return_obs_tm_matched_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c]
                        )
                            return_obs_tm_qualified_terminal_equal++;
                        if (
                            return_obs_tm_ignore_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c]
                        )
                            return_obs_tm_qualified_terminal_ignore++;
                        if (
                            return_obs_tm_out_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c]
                        )
                            return_obs_tm_qualified_terminal_out++;
                    end
                    if (
                        return_obs_fd != 0 &&
                        return_obs_tm_edge_records < return_obs_fr_limit &&
                        (return_obs_tm_raw_edge_any ||
                         return_obs_tm_terminal_accept)
                    ) begin
                        $fdisplay(
                            return_obs_fd,
                            "%0t | TERMINAL_MATCH_EDGE_V1 | n=%0d row=%0d col=%0d raw_edge=%0b accepted=%0b terminal_accept=%0b raw_valid=0x%0h raw_last=0x%0h raw_same=0x%0h gotten=0x%0h masked_valid=0x%0h masked_last=0x%0h raw_index=0x%0h buffer_last=%0b buffer_index=%0d all_matched=%0b pipeline_enable=%0b transout_cfg=%0d diff=0x%0h ignore=%0b matched=%0b out=%0b",
                            $time,
                            return_obs_tm_edge_records + 1,
                            return_obs_tm_r,
                            return_obs_tm_c,
                            return_obs_tm_raw_edge_any,
                            return_obs_tm_accept,
                            return_obs_tm_terminal_accept,
                            return_obs_tm_raw_valid_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_raw_last_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_raw_same_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_gotten_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_masked_valid_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_masked_last_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_raw_last_index_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_fr_input_last_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_fr_input_last_index_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_all_matched_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_pipeline_enable_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_transout_cfg_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_diff_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_ignore_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_matched_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c],
                            return_obs_tm_out_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                                [return_obs_tm_r][return_obs_tm_c]
                        );
                        $fflush(return_obs_fd);
                        return_obs_tm_edge_records++;
                    end
                end
            end
            return_obs_tm_prev_raw_last =
                return_obs_tm_raw_last_mon
                    [return_obs_group_id][return_obs_local_slice_id];
        end
    end

    task automatic return_obs_write_terminal_match_state(
        input string event_name
    );
        begin
            if (return_obs_fr_enabled && return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | TERMINAL_MATCH_BOUNDARY_V1 | event=%s raw_last_edge0=%0d raw_last_edge1=%0d raw_last_mask_suppressed0=%0d raw_last_mask_suppressed1=%0d qualified_accepts=%0d qualified_terminal_accepts=%0d terminal_equal=%0d terminal_ignore=%0d terminal_out=%0d hist0=%0d hist1=%0d hist2=%0d hist3=%0d hist4=%0d hist5=%0d hist6=%0d hist7=%0d hist8=%0d hist9=%0d hist10=%0d hist11=%0d hist12=%0d hist13=%0d hist14=%0d hist15=%0d",
                    $time,
                    event_name,
                    return_obs_tm_raw_last_edge[0],
                    return_obs_tm_raw_last_edge[1],
                    return_obs_tm_raw_last_mask_suppressed[0],
                    return_obs_tm_raw_last_mask_suppressed[1],
                    return_obs_tm_qualified_accepts,
                    return_obs_tm_qualified_terminal_accepts,
                    return_obs_tm_qualified_terminal_equal,
                    return_obs_tm_qualified_terminal_ignore,
                    return_obs_tm_qualified_terminal_out,
                    return_obs_tm_terminal_hist[0],
                    return_obs_tm_terminal_hist[1],
                    return_obs_tm_terminal_hist[2],
                    return_obs_tm_terminal_hist[3],
                    return_obs_tm_terminal_hist[4],
                    return_obs_tm_terminal_hist[5],
                    return_obs_tm_terminal_hist[6],
                    return_obs_tm_terminal_hist[7],
                    return_obs_tm_terminal_hist[8],
                    return_obs_tm_terminal_hist[9],
                    return_obs_tm_terminal_hist[10],
                    return_obs_tm_terminal_hist[11],
                    return_obs_tm_terminal_hist[12],
                    return_obs_tm_terminal_hist[13],
                    return_obs_tm_terminal_hist[14],
                    return_obs_tm_terminal_hist[15]
                );
                $fflush(return_obs_fd);
            end
        end
    endtask
"""
    task_start = text.index(
        "    task automatic return_obs_write_final_release_state("
    )
    task_end = text.index("    endtask", task_start)
    task_text = text[task_start:task_end]
    flush = "                $fflush(return_obs_fd);\n"
    flush_at = task_text.rfind(flush)
    if flush_at < 0:
        raise BuildError("final-release task flush anchor absent")
    flush_at += len(flush)
    task_text = (
        task_text[:flush_at]
        + "                return_obs_write_terminal_match_state(event_name);\n"
        + task_text[flush_at:]
    )
    text = text[:task_start] + task_text + text[task_end:]
    path.write_text(text + block, encoding="utf-8", newline="\n")
    final = path.read_text(encoding="utf-8")
    required = (
        "TERMINAL_MATCH_EDGE_V1",
        "TERMINAL_MATCH_BOUNDARY_V1",
        "return_obs_tm_qualified_terminal_accepts",
        ".sa_pe_inport_last_bit_unmasked",
        ".sa_pe_inport_last_bit_masked",
        ".sa_pe_transout_last_index_diff",
        "return_obs_write_terminal_match_state(event_name);",
    )
    if not all(token in final for token in required):
        raise BuildError("v25 terminal-match observer closure incomplete")
    return base.sha256(path)


def update_manifest(package: Path, observer_sha: str) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-terminal-match-diagnostic-package-v25",
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_READY_NOT_RUN",
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    receipts = manifest["active_receipts"]
    receipts["plan_mutable_provenance_sha256"] = PLAN_MUTABLE_SHA256
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    for item in receipts["generation_read_receipt"]:
        if item.get("reason") == "server package routing":
            item["sha256"] = INDEX_SHA256
        elif item.get("reason") == "common server package gates":
            item["sha256"] = SERVER_RULE_SHA256
    rules = receipts.setdefault("rules", [])
    for rule in (
        "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
        "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
    ):
        if rule not in rules:
            rules.append(rule)
    rules.sort()
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"]["sha256"] = observer_sha
    manifest["v24_return_analysis"] = {
        "return_zip_sha256": RETURN_ZIP_SHA256,
        "source_v24_zip_sha256": SOURCE_ZIP_SHA256,
        "status": "LONG_RUNNING_HANG_AT_SA_TERMINAL_MATCH_GATE",
        "compile_exit_status": 0,
        "run_exit_status": 0,
        "signal_status": "NONE",
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
        "last_proven_good": (
            "SA_NONTERMINAL_OPERAND_ACCEPT_AND_ALU_OUTBUFFER_UPDATE"
        ),
        "first_divergence": (
            "RAW_INPUT_TERMINAL_TO_QUALIFIED_TRANSOUT_MATCH_OR_OUT"
        ),
        "qualified_evidence": {
            "raw_input_terminal_edges": 256,
            "input_matched_edges": 0,
            "input_out_edges": 0,
            "alu_terminal_writes": 0,
            "ready_set_edges": 0,
            "pe_accepts": 0,
            "buffer5_write_edges": 0,
        },
    }
    manifest["terminal_match_diagnostic"] = {
        "feature": "RETURN_OBS_FINAL_RELEASE",
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "record_schemas": [
            "TERMINAL_MATCH_EDGE_V1",
            "TERMINAL_MATCH_BOUNDARY_V1",
        ],
        "qualified_boundary": (
            "raw per-port last edge -> same/gotten mask -> simultaneous A/B "
            "valid -> pipeline accept -> transout diff/equal/ignore/out"
        ),
        "qualified_counters": [
            "raw last rising edge per A/B port",
            "accepted operand tuple",
            "accepted terminal tuple",
            "accepted terminal equal/ignore/out classification",
            "accepted terminal last-index histogram",
        ],
        "state_only_fields": [
            "raw valid/last/same/index",
            "gotten and masked valid/last",
            "configured transout_last_index and combinational diff",
        ],
        "decision_table": {
            "qualified_terminal_accepts=0": (
                "terminal operand alignment/masking interval"
            ),
            "terminal_ignore>0": (
                "materialized transout_last_index is below accepted terminal "
                "last_index; config threshold mismatch"
            ),
            "terminal_equal_or_out>0_and_no_terminal_alu_write": (
                "control-to-ALU terminal tag propagation interval"
            ),
            "terminal_alu_write>0_and_no_ready": (
                "outbuffer final-release interval"
            ),
        },
        "timeout_changed": False,
        "backpressure_changed": False,
        "configuration_changed": False,
        "functional_fix": False,
    }
    manifest["package_audit_escape_claim_correction"] = {
        "v23_escape_root_cause": (
            "safe compile stub proved runner reachability/finalizers but not "
            "SystemVerilog declaration/use or scope resolution"
        ),
        "still_valid": [
            "runner reachability",
            "safe EXIT/TERM finalizer",
            "identity and feature binding negatives",
            "deterministic ZIP and exact-set validation",
        ],
        "withdrawn_for_v23": [
            "claim that package-local observer was compile ready",
            "claim that text/XMR constant scan proved identifier scope",
        ],
        "v25_new_gate_scope": (
            "new/modified terminal-match observer declarations, uses and XMR "
            "leaf names only; no full-design elaboration claim"
        ),
    }
    manifest["superseded_v24_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_ZIP_SHA256,
        "status": "CONSUMED_RETURN_SUPERSEDED_BY_NARROWER_DIAGNOSTIC",
    }
    manifest["files"] = base.package_records(package)
    base.write_json(path, manifest)


def readme() -> str:
    return f"""# ResNet50 node0004 v25 terminal-match diagnostic

This is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

The frozen v24 numeric inputs, configuration, bitstream, execplan, SCA,
golden and functional RTL are unchanged. The existing low-cost progress and
final-release diagnostics remain enabled. The only new observation splits the
v24 boundary into:

1. raw A/B last edges and same/gotten masking;
2. simultaneous accepted A/B terminal tuples;
3. accepted last-index versus configured `transout_last_index`; and
4. equal/ignore/out classification.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip`.
"""


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v25-source-") as temp:
        source = safe_extract(Path(temp))
        shutil.copytree(source, package)
    replace_identity(package)
    observer_sha = patch_observer(package)
    (package / "README.md").write_text(
        readme(), encoding="utf-8", newline="\n"
    )
    update_manifest(package, observer_sha)
    receipt = base.observer_precompile_receipt(package, observer_sha)
    if not receipt["valid"]:
        raise BuildError(f"observer XMR text gate failed: {receipt['errors']}")
    return package


def main() -> int:
    output = OUTPUT_ROOT.resolve()
    package = output / INSTALL_NAME
    zip_path = output / f"{INSTALL_NAME}.zip"
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    validation = output / f"{INSTALL_NAME}.validation.json"
    for target in (package, zip_path, sidecar, validation):
        if target.exists():
            raise BuildError(f"refusing to overwrite: {target}")
    package = build_directory(output)
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v25-repeat-") as temp:
        repeat = Path(temp)
        repeat_package = build_directory(repeat)
        repeat_zip = repeat / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v25 deterministic repeat differs")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    report: dict[str, Any] = {
        "schema": "node0004-terminal-match-diagnostic-build-v25",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "source_v24_sha256": SOURCE_ZIP_SHA256,
        "v24_return_sha256": RETURN_ZIP_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "deterministic_rebuild_equal": deterministic,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    base.write_json(validation, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
