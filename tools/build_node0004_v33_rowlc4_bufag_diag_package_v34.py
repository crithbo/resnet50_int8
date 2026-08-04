from __future__ import annotations

import argparse
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

import tools.build_node0004_v32_lc18_pe7_diag_package_v33 as previous  # noqa: E402


base = previous.base
SOURCE_NAME = "r5_n4_hw_v33_lc18_pe7_diag"
INSTALL_NAME = "r5_n4_hw_v35_rowlc4_bufag_diag"
SOURCE_SHA256 = "5094fc3e01a04c1931b81c4db3a67bf2f6b82f424124d0311866d03004997c90"
RETURN_SHA256 = "82c1cc545d1df6a9e0359be6902c064af30d7e9631d50fcc4182177eb904105e"
SERVER_RULE_SHA256 = "0916c655b0581cd99836d8cc1561a3f41b15b25e861692d596a4789c039b090e"
AGENT_SHA256 = "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
INDEX_SHA256 = "5146225e549942c4e25780ac4fc0120d7cac1ef355879284450dad2e48df237b"
PLAN_MUTABLE_SHA256 = "51b930a8443042ec05f213e52a7035ab289b78a502cfd94bab128282f882d999"
RTL_COMMIT = "df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727"
RTL_SYNC_REPORT = (
    ROOT / "artifacts/rtl_sync/trassic_master_df23e4d_20260804/report.json"
)
RTL_SYNC_REPORT_SHA256 = (
    "6cf79c6d461ffb73ba7554dec8056b178a81ec5018bd0068accda4efb9a366a5"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
MAPPING_CACHE = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-transout-threshold-fix-c0-v5/mapping/conv/op_w0/"
    "mapping_cache/72d2720125714878.json"
)
MAPPING_REVIEW = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-transout-threshold-fix-c0-v5/mapping/conv/op_w0/"
    "mapping_review.json"
)
RTL_LEAVES = (
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_Interconnect.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC_Inbuffer.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC_Counter.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_COL_LC/IGA_COL_LC.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_COL_LC/IGA_COL_LC_Inbuffer.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_COL_LC/IGA_COL_LC_Counter.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
)
KEPT_FEATURES = (
    "RETURN_HANG_DIAG",
    "RETURN_OBS_MSE4_DESCRIPTOR",
    "RETURN_OBS_MSE4_INDEX",
    "RETURN_OBS_LC18_PE7",
    "RETURN_OBS_ROWLC4_BUFAG",
)
DROPPED_RUNTIME_FEATURES = (
    "RETURN_OBS_DEEP",
    "RETURN_OBS_ABPE",
    "RETURN_OBS_FINAL_RELEASE",
    "RETURN_OBS_DWRITE_PATH",
    "RETURN_OBS_DATAHUB_DRAIN",
)


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v33 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v33 source CRC failed")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                raise BuildError(f"unsafe/duplicate member: {info.filename}")
            seen.add(info.filename)
            if path.parts:
                roots.add(path.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"v33 root differs: {sorted(roots)}")
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


def iga(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_slice_wrapper.u_Slice.u_Index_Generation_Array"
        f".{leaf}"
    )


def row4(leaf: str) -> str:
    return iga(f"IGA_ROW_LC[4].u_IGA_ROW_LC.{leaf}")


def col4(leaf: str) -> str:
    return iga(f"IGA_COL_LC[4].u_IGA_COL_LC.{leaf}")


def mse4(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        ".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
        f".{leaf}"
    )


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "ROWLC4_BUFAG_BOUNDARY_V1" in text:
        raise BuildError("v35 row/Buffer-AG diagnostic already present")
    call = "                return_obs_write_lc18_pe7_state(event_name);"
    if text.count(call) != 1:
        raise BuildError("observer decision-hook anchor differs")
    text = text.replace(
        call,
        call + "\n                return_obs_write_rowlc4_bufag_state(event_name);",
        1,
    )
    block = f'''

    // v35: information-gain boundary for LC18 fanout bit10 through
    // ROW_LC4/COL_LC4 and WRITE_STREAM0 Buffer_AG/RD_Buffer_AG.
    bit return_obs_rb_enabled;
    integer return_obs_rb_limit;
    integer return_obs_rb_plusarg_status;
    integer return_obs_rb_edge_records;
    longint unsigned return_obs_rb_row_capture;
    longint unsigned return_obs_rb_row_complete;
    longint unsigned return_obs_rb_row_out;
    longint unsigned return_obs_rb_col_capture;
    longint unsigned return_obs_rb_col_complete;
    longint unsigned return_obs_rb_col_out;
    longint unsigned return_obs_rb_buf_row_accept;
    longint unsigned return_obs_rb_buf_col_accept;
    longint unsigned return_obs_rb_buf_match;
    longint unsigned return_obs_rb_buf_push;
    longint unsigned return_obs_rb_buf_pop;
    longint unsigned return_obs_rb_rd_write;
    longint unsigned return_obs_rb_rd_read;

    initial begin
        return_obs_rb_enabled = $test$plusargs("RETURN_OBS_ROWLC4_BUFAG");
        return_obs_rb_limit = 128;
        return_obs_rb_plusarg_status = $value$plusargs(
            "RETURN_OBS_ROWLC4_BUFAG_LIMIT=%d", return_obs_rb_limit
        );
        return_obs_rb_edge_records = 0;
        return_obs_rb_row_capture = 0;
        return_obs_rb_row_complete = 0;
        return_obs_rb_row_out = 0;
        return_obs_rb_col_capture = 0;
        return_obs_rb_col_complete = 0;
        return_obs_rb_col_out = 0;
        return_obs_rb_buf_row_accept = 0;
        return_obs_rb_buf_col_accept = 0;
        return_obs_rb_buf_match = 0;
        return_obs_rb_buf_push = 0;
        return_obs_rb_buf_pop = 0;
        return_obs_rb_rd_write = 0;
        return_obs_rb_rd_read = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_ROWLC4_BUFAG enabled=%0d limit_name=RETURN_OBS_ROWLC4_BUFAG_LIMIT limit=%0d",
                return_obs_rb_enabled, return_obs_rb_limit);
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit rb_row_capture;
        bit rb_row_complete;
        bit rb_row_out;
        bit rb_col_capture;
        bit rb_col_complete;
        bit rb_col_out;
        bit rb_buf_row_accept;
        bit rb_buf_col_accept;
        bit rb_buf_match;
        bit rb_buf_push;
        bit rb_buf_pop;
        bit rb_rd_write;
        bit rb_rd_read;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_rb_edge_records = 0;
            return_obs_rb_row_capture = 0;
            return_obs_rb_row_complete = 0;
            return_obs_rb_row_out = 0;
            return_obs_rb_col_capture = 0;
            return_obs_rb_col_complete = 0;
            return_obs_rb_col_out = 0;
            return_obs_rb_buf_row_accept = 0;
            return_obs_rb_buf_col_accept = 0;
            return_obs_rb_buf_match = 0;
            return_obs_rb_buf_push = 0;
            return_obs_rb_buf_pop = 0;
            return_obs_rb_rd_write = 0;
            return_obs_rb_rd_read = 0;
        end else if (return_obs_rb_enabled && return_obs_active) begin
            rb_row_capture =
                {row4('iga_row_lc_inbuffer_bp_pre')} &&
                {row4('u_IGA_ROW_LC_Inbuffer.iga_row_lc_inport_valid_bit_masked')};
            rb_row_complete =
                {row4('iga_row_lc_inbuffer_valid_bit')} &&
                {row4('iga_row_lc_cnt_bp_pre')};
            rb_row_out =
                {row4('u_IGA_ROW_LC_Counter.iga_row_lc_cnt_outport_valid_bit')} &&
                {row4('iga_row_lc_cnt_bp_post')};
            rb_col_capture =
                {col4('iga_col_lc_inbuffer_bp_pre')} &&
                {col4('u_IGA_COL_LC_Inbuffer.iga_col_lc_inport_valid_bit_masked')};
            rb_col_complete =
                {col4('iga_col_lc_inbuffer_valid_bit')} &&
                {col4('iga_col_lc_cnt_bp_pre')};
            rb_col_out =
                {col4('u_IGA_COL_LC_Counter.iga_col_lc_cnt_outport_valid_bit')} &&
                {col4('iga_col_lc_cnt_bp_post')};
            rb_buf_row_accept =
                {mse4('u_Buffer_AG_Idx_Queue.mse_buf_queue_bp_pre[1]')} &&
                {mse4('u_Buffer_AG_Idx_Queue.buf_idx_valid_bit_masked[1]')};
            rb_buf_col_accept =
                {mse4('u_Buffer_AG_Idx_Queue.mse_buf_queue_bp_pre[0]')} &&
                {mse4('u_Buffer_AG_Idx_Queue.buf_idx_valid_bit_masked[0]')};
            rb_buf_match = {mse4('u_Buffer_AG_Idx_Queue.buf_all_idx_matched')};
            rb_buf_push =
                {mse4('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en')} &&
                !{mse4('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full')};
            rb_buf_pop =
                {mse4('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en')} &&
                !{mse4('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty')};
            rb_rd_write =
                {mse4('u_RD_Buffer_AG.buf_ag_ob_wr_en')} &&
                !{mse4('u_RD_Buffer_AG.buf_ag_ob_full')};
            rb_rd_read =
                {mse4('u_RD_Buffer_AG.buf_ag_ob_rd_en')} &&
                !{mse4('u_RD_Buffer_AG.buf_ag_ob_empty')};
            if (rb_row_capture) return_obs_rb_row_capture++;
            if (rb_row_complete) return_obs_rb_row_complete++;
            if (rb_row_out) return_obs_rb_row_out++;
            if (rb_col_capture) return_obs_rb_col_capture++;
            if (rb_col_complete) return_obs_rb_col_complete++;
            if (rb_col_out) return_obs_rb_col_out++;
            if (rb_buf_row_accept) return_obs_rb_buf_row_accept++;
            if (rb_buf_col_accept) return_obs_rb_buf_col_accept++;
            if (rb_buf_match) return_obs_rb_buf_match++;
            if (rb_buf_push) return_obs_rb_buf_push++;
            if (rb_buf_pop) return_obs_rb_buf_pop++;
            if (rb_rd_write) return_obs_rb_rd_write++;
            if (rb_rd_read) return_obs_rb_rd_read++;
            if (return_obs_rb_edge_records < return_obs_rb_limit &&
                (rb_row_capture || rb_row_complete || rb_row_out ||
                 rb_col_capture || rb_col_complete || rb_col_out ||
                 rb_buf_row_accept || rb_buf_col_accept || rb_buf_match ||
                 rb_buf_push || rb_buf_pop || rb_rd_write || rb_rd_read)) begin
                $fdisplay(return_obs_fd,
                    "%0t | ROWLC4_BUFAG_EDGE_V1 | n=%0d edge=0x%0h row_in=0x%0h row_bp=0x%0h row_out=0x%0h row_out_bp=0x%0h row_count=%0d row_full=%0d col_in=0x%0h col_bp=0x%0h col_out=0x%0h col_out_bp=0x%0h col_count=%0d col_full=%0d buf_valid=0x%0h buf_same=0x%0h buf_gotten=0x%0h buf_bp=0x%0h buf_match=%0d bufq_full=%0d bufq_empty=%0d rd_count=%0d rd_full=%0d rd_empty=%0d wr_ready=%0d prepared_count=%0d prepared_bp=%0d",
                    $time, return_obs_rb_edge_records + 1,
                    {{rb_rd_read, rb_rd_write, rb_buf_pop, rb_buf_push,
                      rb_buf_match, rb_buf_col_accept, rb_buf_row_accept,
                      rb_col_out, rb_col_complete, rb_col_capture,
                      rb_row_out, rb_row_complete, rb_row_capture}},
                    {row4('iga_row_lc_inport_tag')},
                    {row4('iga_row_lc_inport_bp_pre')},
                    {row4('iga_row_lc_outport')},
                    {row4('iga_row_lc_outport_bp_post')},
                    {row4('u_IGA_ROW_LC_Counter.iga_row_lc_outbuf_count')},
                    {row4('u_IGA_ROW_LC_Counter.iga_row_lc_outbuf_full')},
                    {col4('iga_col_lc_inport_tag')},
                    {col4('iga_col_lc_inport_bp_pre')},
                    {col4('iga_col_lc_outport')},
                    {col4('iga_col_lc_outport_bp_post')},
                    {col4('u_IGA_COL_LC_Counter.iga_col_lc_outbuf_count')},
                    {col4('u_IGA_COL_LC_Counter.iga_col_lc_outbuf_full')},
                    {mse4('u_Buffer_AG_Idx_Queue.buf_idx_valid_bit_unmasked')},
                    {mse4('u_Buffer_AG_Idx_Queue.buf_idx_same_bit_unmasked')},
                    {mse4('u_Buffer_AG_Idx_Queue.buf_idx_gotten_bit')},
                    {mse4('u_Buffer_AG_Idx_Queue.mse_buf_queue_bp_pre')},
                    {mse4('u_Buffer_AG_Idx_Queue.buf_all_idx_matched')},
                    {mse4('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full')},
                    {mse4('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty')},
                    {mse4('u_RD_Buffer_AG.buf_ag_ob_cnt')},
                    {mse4('u_RD_Buffer_AG.buf_ag_ob_full')},
                    {mse4('u_RD_Buffer_AG.buf_ag_ob_empty')},
                    {mse4('u_RD_Buffer_AG.wr_data_chl_ready')},
                    {mse4('u_WR_Data_Channel.wr_data_chl_prepared_data_cnt')},
                    {mse4('u_WR_Data_Channel.wr_chl_prepared_data_bp_pre')});
                return_obs_rb_edge_records++;
                $fflush(return_obs_fd);
            end
        end
    end

    task automatic return_obs_write_rowlc4_bufag_state(input string event_name);
        begin
            if (return_obs_rb_enabled && return_obs_fd != 0) begin
                $fdisplay(return_obs_fd,
                    "%0t | ROWLC4_BUFAG_BOUNDARY_V1 | event=%s row_capture=%0d row_complete=%0d row_out=%0d col_capture=%0d col_complete=%0d col_out=%0d buf_row_accept=%0d buf_col_accept=%0d buf_match=%0d buf_push=%0d buf_pop=%0d rd_write=%0d rd_read=%0d row_in=0x%0h row_bp=0x%0h row_out_state=0x%0h row_out_bp=0x%0h row_count=%0d row_full=%0d row_empty=%0d col_in=0x%0h col_bp=0x%0h col_out_state=0x%0h col_out_bp=0x%0h col_count=%0d col_full=%0d col_empty=%0d buf_valid=0x%0h buf_same=0x%0h buf_gotten=0x%0h buf_bp=0x%0h buf_match_state=%0d bufq_full=%0d bufq_empty=%0d rd_count=%0d rd_full=%0d rd_empty=%0d wr_ready=%0d prepared_count=%0d prepared_vld=%0d prepared_bp=%0d",
                    $time, event_name,
                    return_obs_rb_row_capture, return_obs_rb_row_complete,
                    return_obs_rb_row_out, return_obs_rb_col_capture,
                    return_obs_rb_col_complete, return_obs_rb_col_out,
                    return_obs_rb_buf_row_accept, return_obs_rb_buf_col_accept,
                    return_obs_rb_buf_match, return_obs_rb_buf_push,
                    return_obs_rb_buf_pop, return_obs_rb_rd_write,
                    return_obs_rb_rd_read,
                    {row4('iga_row_lc_inport_tag')},
                    {row4('iga_row_lc_inport_bp_pre')},
                    {row4('iga_row_lc_outport')},
                    {row4('iga_row_lc_outport_bp_post')},
                    {row4('u_IGA_ROW_LC_Counter.iga_row_lc_outbuf_count')},
                    {row4('u_IGA_ROW_LC_Counter.iga_row_lc_outbuf_full')},
                    {row4('u_IGA_ROW_LC_Counter.iga_row_lc_outbuf_empty')},
                    {col4('iga_col_lc_inport_tag')},
                    {col4('iga_col_lc_inport_bp_pre')},
                    {col4('iga_col_lc_outport')},
                    {col4('iga_col_lc_outport_bp_post')},
                    {col4('u_IGA_COL_LC_Counter.iga_col_lc_outbuf_count')},
                    {col4('u_IGA_COL_LC_Counter.iga_col_lc_outbuf_full')},
                    {col4('u_IGA_COL_LC_Counter.iga_col_lc_outbuf_empty')},
                    {mse4('u_Buffer_AG_Idx_Queue.buf_idx_valid_bit_unmasked')},
                    {mse4('u_Buffer_AG_Idx_Queue.buf_idx_same_bit_unmasked')},
                    {mse4('u_Buffer_AG_Idx_Queue.buf_idx_gotten_bit')},
                    {mse4('u_Buffer_AG_Idx_Queue.mse_buf_queue_bp_pre')},
                    {mse4('u_Buffer_AG_Idx_Queue.buf_all_idx_matched')},
                    {mse4('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full')},
                    {mse4('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty')},
                    {mse4('u_RD_Buffer_AG.buf_ag_ob_cnt')},
                    {mse4('u_RD_Buffer_AG.buf_ag_ob_full')},
                    {mse4('u_RD_Buffer_AG.buf_ag_ob_empty')},
                    {mse4('u_RD_Buffer_AG.wr_data_chl_ready')},
                    {mse4('u_WR_Data_Channel.wr_data_chl_prepared_data_cnt')},
                    {mse4('u_WR_Data_Channel.wr_data_chl_prepared_data_vld')},
                    {mse4('u_WR_Data_Channel.wr_chl_prepared_data_bp_pre')});
                $fflush(return_obs_fd);
            end
        end
    endtask
'''
    path.write_text(text + block, encoding="utf-8", newline="\n")
    return base.sha256(path)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    for token in (
        " +RETURN_OBS_DEEP +RETURN_OBS_DEEP_LIMIT=256",
        " +RETURN_OBS_ABPE",
        " +RETURN_OBS_FINAL_RELEASE +RETURN_OBS_FINAL_RELEASE_LIMIT=256",
        " +RETURN_OBS_DWRITE_PATH +RETURN_OBS_DWRITE_PATH_LIMIT=64",
        " +RETURN_OBS_DATAHUB_DRAIN +RETURN_OBS_DATAHUB_DRAIN_LIMIT=64",
    ):
        if text.count(token) != 2:
            raise BuildError(f"runner drop token count differs: {token}")
        text = text.replace(token, "")
    token = "+RETURN_OBS_LC18_PE7_LIMIT=96"
    if text.count(token) != 2:
        raise BuildError("runner add-feature anchor differs")
    text = text.replace(
        token,
        token + " +RETURN_OBS_ROWLC4_BUFAG +RETURN_OBS_ROWLC4_BUFAG_LIMIT=128",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    text = path.read_text(encoding="utf-8")
    start = text.index("FEATURE_CONTRACTS = (")
    end = text.index("\n\n\ndef diagnostic_feature_binding", start)
    contracts = '''FEATURE_CONTRACTS = (
    {
        "feature": "RETURN_HANG_DIAG",
        "enable": "+RETURN_HANG_DIAG",
        "limits": (
            "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144",
            "+RETURN_HANG_DIAG_STALL_WINDOWS=4",
            "+RETURN_HANG_DIAG_MAX_CYCLES=8388608",
        ),
        "marker_tokens": (
            "feature=RETURN_HANG_DIAG",
            "enabled=1",
            "sample_cycles=262144",
            "stall_windows=4",
            "max_cycles=8388608",
        ),
    },
    {
        "feature": "RETURN_OBS_MSE4_DESCRIPTOR",
        "enable": "+RETURN_OBS_MSE4_DESCRIPTOR",
        "limits": ("+RETURN_OBS_MSE4_DESCRIPTOR_LIMIT=96",),
        "marker_tokens": (
            "feature=RETURN_OBS_MSE4_DESCRIPTOR", "enabled=1", "limit=96",
        ),
    },
    {
        "feature": "RETURN_OBS_MSE4_INDEX",
        "enable": "+RETURN_OBS_MSE4_INDEX",
        "limits": ("+RETURN_OBS_MSE4_INDEX_LIMIT=96",),
        "marker_tokens": (
            "feature=RETURN_OBS_MSE4_INDEX", "enabled=1", "limit=96",
        ),
    },
    {
        "feature": "RETURN_OBS_LC18_PE7",
        "enable": "+RETURN_OBS_LC18_PE7",
        "limits": ("+RETURN_OBS_LC18_PE7_LIMIT=96",),
        "marker_tokens": (
            "feature=RETURN_OBS_LC18_PE7", "enabled=1", "limit=96",
        ),
    },
    {
        "feature": "RETURN_OBS_ROWLC4_BUFAG",
        "enable": "+RETURN_OBS_ROWLC4_BUFAG",
        "limits": ("+RETURN_OBS_ROWLC4_BUFAG_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_ROWLC4_BUFAG", "enabled=1", "limit=128",
        ),
    },
)'''
    path.write_text(
        text[:start] + contracts + text[end:],
        encoding="utf-8",
        newline="\n",
    )


def rtl_binding() -> dict[str, Any]:
    if base.sha256(RTL_SYNC_REPORT) != RTL_SYNC_REPORT_SHA256:
        raise BuildError("current RTL sync report SHA differs")
    mapping = json.loads(MAPPING_CACHE.read_text(encoding="utf-8"))
    required = {
        "DRAM_LC.LC9": "LC18",
        "GROUP4.ROW_LC": "ROW_LC4",
        "GROUP4.COL_LC": "COL_LC4",
        "LC_PE.PE1": "PE7",
        "STREAM.stream4": "WRITE_STREAM0",
    }
    if any(mapping.get(key) != value for key, value in required.items()):
        raise BuildError("frozen logical-to-physical mapping differs")
    leaves = []
    for relative in RTL_LEAVES:
        path = ROOT / relative
        leaves.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": base.sha256(path),
            }
        )
    return {
        "schema": "node0004-v35-current-local-rtl-and-mapping-binding-v1",
        "current_local_rtl_commit": RTL_COMMIT,
        "sync_report_path": str(RTL_SYNC_REPORT.relative_to(ROOT)).replace("\\", "/"),
        "sync_report_sha256": RTL_SYNC_REPORT_SHA256,
        "mapping_cache": {
            "path": str(MAPPING_CACHE.relative_to(ROOT)).replace("\\", "/"),
            "sha256": base.sha256(MAPPING_CACHE),
            "required": required,
        },
        "mapping_review": {
            "path": str(MAPPING_REVIEW.relative_to(ROOT)).replace("\\", "/"),
            "sha256": base.sha256(MAPPING_REVIEW),
        },
        "focused_direct_consumers": leaves,
        "server_runtime_source_preflight": False,
        "server_run_rtl_identity_bound": False,
        "claim_boundary": (
            "local successor analysis/build identity only; compile/run "
            "naturally adjudicates the user-supplied server root"
        ),
    }


def execution_reduction() -> dict[str, Any]:
    return {
        "schema": "node0004-v35-diagnostic-execution-reduction-v1",
        "rule_id": "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
        "causal_slice": (
            "c0 cumulative prefix through LC18 value6, ROW_LC4/COL_LC4, "
            "WRITE_STREAM0 Buffer_AG, RD_Buffer_AG, and prepared-data saturation"
        ),
        "kept": {
            "stages": ["c0"],
            "payload": ["all 86 frozen c0 input leaves"],
            "readback": ["frozen formal-D contract; not claimed before natural terminal"],
            "observer_features": list(KEPT_FEATURES),
        },
        "dropped": {
            "stages": [],
            "payload": [],
            "readback": [],
            "observer_runtime_features": list(DROPPED_RUNTIME_FEATURES),
        },
        "why_stage_payload_not_reduced": (
            "The candidate final-flush cycle depends on accumulated Buffer_AG, "
            "RD_Buffer_AG and prepared-data occupancy reached only after the "
            "frozen c0 prefix. No verified hardware checkpoint or approved "
            "byte-exact internal stimulus exists; host replay is forbidden."
        ),
        "expected_reduction": {
            "simulation_cycles": "unchanged causal prefix",
            "observer_runtime_features": "9 to 5",
            "observer_log_and_xmr_work": "reduced by disabling five irrelevant features",
        },
        "candidate_observation_matrix": {
            "ROW_LC4_SOURCE_OR_SAME_GOTTEN": [
                "row_capture",
                "row_complete",
                "row in tag/bp",
            ],
            "ROW_LC4_COUNTER_OR_OUTPUT": [
                "row_capture",
                "row_out",
                "row count/full/empty",
            ],
            "COL_LC4_FANOUT": [
                "row_out",
                "col_capture",
                "col_out",
                "col count/full/empty",
            ],
            "BUFFER_AG_QUEUE": [
                "buf_row_accept",
                "buf_col_accept",
                "buf_match/push/pop",
                "queue full/empty",
            ],
            "RD_BUFFER_AG_OR_PREPARED_SATURATION": [
                "rd_write/read/count/full/empty",
                "wr_ready",
                "prepared_count/valid/bp",
            ],
        },
        "claim_boundary": (
            "diagnostic localization only; complete E4/E5 still requires the "
            "full target and natural terminal/formal D"
        ),
    }


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v35-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    observer_sha = patch_observer(package)
    patch_runner(package)
    patch_runtime(package)
    binding = rtl_binding()
    reduction = execution_reduction()
    provenance = package / "provenance"
    base.write_json(provenance / "current_local_rtl_binding.json", binding)
    base.write_json(provenance / "v35_diagnostic_execution_reduction.json", reduction)
    (package / "README.md").write_text(
        f"# node0004 v35 ROW_LC4 / Buffer_AG diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v33 proved the PE7-to-MSE4 index path conserves all seven values and "
        "that physical LC18 is blocked only by fanout bit10, statically mapped "
        "to ROW_LC4. This package combines all low-cost discriminators from "
        "ROW_LC4 through COL_LC4, WRITE_STREAM0 Buffer_AG and RD_Buffer_AG in "
        "one run. Numeric, workload, configuration, golden, timeout, "
        "backpressure and functional RTL are unchanged.\n\n"
        f"Current local RTL analysis identity: `{RTL_COMMIT}`.\n\n"
        f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh "
        "/absolute/path/to/NDP_copy`\n\n"
        f"Expected return: `{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-rowlc4-bufag-diagnostic-package-v35",
            "install_name": INSTALL_NAME,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "candidate_release": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    manifest["active_receipts"]["server_package_rule_sha256"] = SERVER_RULE_SHA256
    manifest["active_receipts"]["agent_sha256"] = AGENT_SHA256
    manifest["active_receipts"]["plan_mutable_provenance_sha256"] = (
        PLAN_MUTABLE_SHA256
    )
    generation_receipt = manifest["active_receipts"]["generation_read_receipt"]
    receipt_updates = {
        ".agents/rules/生成前必读索引.md": INDEX_SHA256,
        ".agents/rules/服务器测试包生成规则.md": SERVER_RULE_SHA256,
    }
    for receipt in generation_receipt:
        if receipt.get("path") in receipt_updates:
            receipt["sha256"] = receipt_updates[receipt["path"]]
    rules = manifest["active_receipts"]["rules"]
    if "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001" not in rules:
        rules.append("CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001")
    manifest["v33_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "LC18_FANOUT_BLOCKED_ONLY_BY_ROW_LC4",
        "last_proven_good": (
            "PHYSICAL_LC18_VALUE6_ACCEPTED_BY_PE7_AND_CONSERVED_THROUGH_"
            "PE7_WRITE_READ_TO_MSE4_SEVENTH_INPUT1_ACCEPT"
        ),
        "first_divergence": (
            "PHYSICAL_LC18_VALUE6_GLOBAL_FANOUT_RELEASE_BLOCKED_ONLY_BY_"
            "PHYSICAL_ROW_LC4_BACKPRESSURE_BIT10"
        ),
        "root_cause": "UNRESOLVED_BELOW_UNIQUE_ROW_LC4_FANOUT_BOUNDARY",
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
        "lc18_global_release": 6,
        "pe7_in2_write_read_mse": [7, 7, 7, 7],
        "lc18_final_bp": "0x1fffffbff",
        "only_missing_fanout_bit": 10,
        "fanout_bit10_static_mapping": "ROW_LC4",
    }
    feature = {
        "feature": "RETURN_OBS_ROWLC4_BUFAG",
        "runtime_enable_parameter": "+RETURN_OBS_ROWLC4_BUFAG",
        "limit_or_budget_parameters": ["+RETURN_OBS_ROWLC4_BUFAG_LIMIT=128"],
        "time_zero_marker": (
            "DIAGNOSTIC_FEATURE_ENABLE_V1 feature=RETURN_OBS_ROWLC4_BUFAG "
            "enabled=1 limit=128"
        ),
        "expected_record_schema": "ROWLC4_BUFAG_BOUNDARY_V1",
    }
    old_features = manifest["diagnostic_feature_runtime_binding"]["features"]
    by_name = {item["feature"]: item for item in old_features}
    by_name[feature["feature"]] = feature
    manifest["diagnostic_feature_runtime_binding"]["features"] = [
        by_name[name] if name != feature["feature"] else feature
        for name in KEPT_FEATURES
    ]
    manifest["rowlc4_bufag_diagnostic"] = {
        **feature,
        "edge_record": "ROWLC4_BUFAG_EDGE_V1",
        "returned_record_target": "runs/c0/return_observer.log",
        "physical_mapping": binding["mapping_cache"]["required"],
        "qualified_events": [
            "ROW_LC4 selected-input capture and parent completion",
            "ROW_LC4 and COL_LC4 global output acceptance",
            "Buffer_AG row/col accept, match, FIFO push/pop",
            "RD_Buffer_AG outbuffer write/read",
        ],
        "state_only": [
            "raw tags/valid/same/gotten",
            "fanout backpressure vectors",
            "counter/FIFO counts and full/empty",
            "prepared-data count/valid/backpressure",
        ],
        "candidate_observation_matrix": reduction["candidate_observation_matrix"],
        "functional_fix": False,
        "configuration_changed": False,
        "timeout_changed": False,
        "backpressure_changed": False,
    }
    manifest["diagnostic_execution_reduction"] = reduction
    manifest["current_local_rtl_binding"] = binding
    manifest["superseded_v33_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA256,
        "status": "RETURN_CONSUMED_SUPERSEDED_BY_INFORMATION_GAIN_DIAGNOSTIC",
    }
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"].update(
        {
            "sha256": observer_sha,
            "size_bytes": (package / "tb_probe/native_return_observer.svh").stat().st_size,
        }
    )
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    receipt = base.observer_precompile_receipt(package, observer_sha)
    if not receipt["valid"]:
        raise BuildError(f"observer static gate failed: {receipt['errors']}")
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    targets = [
        output / INSTALL_NAME,
        output / f"{INSTALL_NAME}.zip",
        output / f"{INSTALL_NAME}.zip.sha256",
        output / f"{INSTALL_NAME}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite existing v35 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v35-repeat-") as temp:
        repeat_root = Path(temp)
        repeat = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v35 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-rowlc4-bufag-diagnostic-build-v35",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v33_sha256": SOURCE_SHA256,
        "bound_v33_return_sha256": RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "current_local_rtl_commit": RTL_COMMIT,
        "rtl_sync_report_sha256": RTL_SYNC_REPORT_SHA256,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "final_zip_rule_self_audit_pending": True,
    }
    base.write_json(output / f"{INSTALL_NAME}.validation.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
