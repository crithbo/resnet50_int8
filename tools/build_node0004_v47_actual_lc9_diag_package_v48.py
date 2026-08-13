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

import tools.build_node0004_v43_lc9_split_diag_package_v47 as prior


base = prior.builder.base
SOURCE_NAME = "r5_n4_hw_v47_lc9_split_cloudrtl"
INSTALL_NAME = "r5_n4_hw_v48_lc9_actual"
VERSION = 48
SOURCE_SHA256 = "516173e54132e2ee31cf2d4f750c46a595bb0bf31afb7f5b6661fc5a0ed6a015"
RETURN_SHA256 = "d05cca4f9d823be3c9ff0b675b2a1601ce863f5075dc29ce057eac0371d3589c"
RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
PLAN_MUTABLE_SHA256 = "a341fd49c978a742501ebb2e3909aa7804915329a2deb4aca87f501cfce5bd64"
AGENT_SHA256 = "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
INDEX_SHA256 = "bd04756ccab49e5a94843a8d9337eda35f818073ea9daa31244be1ae9903e547"
SERVER_RULE_SHA256 = "36f6596c913120c24725da95e269200ecff4b25130d4eefe8d99d21c7b2e7457"
COMMON_RULE_SHA256 = "30d0b20979e639d6bd9d0ec81f5e920da19733f0b2e3fe7ba751ef7e44b972d1"
NDP_RULE_SHA256 = "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
INT8_SA_SHA256 = "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
README_SHA256 = "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
RULE_IDS = [
    "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
    "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
    "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
    "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
    "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
    "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
    "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
    "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
    "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
    "CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001",
]


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v47 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v47 source CRC failed")
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
            raise BuildError(f"v47 root differs: {sorted(roots)}")
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


OBSERVER_BLOCK = r'''

    // v48 LC9_ACTUAL_ACTUAL_CONSUMER_BEGIN
    // Only local masked captures, queue transfers and global all-destination
    // advance are progress. Held valid/ready/full/count values are state.
    bit return_obs_la_enabled;
    integer return_obs_la_limit;
    integer return_obs_la_plusarg_status;
    integer return_obs_la_records;
    longint unsigned return_obs_la_lc9_advance;
    longint unsigned return_obs_la_lc7_capture;
    longint unsigned return_obs_la_lc7_out_accept;
    longint unsigned return_obs_la_mem3_in2_capture;
    longint unsigned return_obs_la_mem3_match;
    longint unsigned return_obs_la_mem3_push;
    longint unsigned return_obs_la_mem3_pop;
    longint unsigned return_obs_la_lc9_last0;
    bit return_obs_la_prev_bp0;
    bit return_obs_la_prev_bp26;

    initial begin
        return_obs_la_enabled = $test$plusargs("RETURN_OBS_LC9_ACTUAL");
        return_obs_la_limit = 192;
        return_obs_la_plusarg_status = $value$plusargs(
            "RETURN_OBS_LC9_ACTUAL_LIMIT=%d", return_obs_la_limit
        );
        return_obs_la_records = 0;
        return_obs_la_lc9_advance = 0;
        return_obs_la_lc7_capture = 0;
        return_obs_la_lc7_out_accept = 0;
        return_obs_la_mem3_in2_capture = 0;
        return_obs_la_mem3_match = 0;
        return_obs_la_mem3_push = 0;
        return_obs_la_mem3_pop = 0;
        return_obs_la_lc9_last0 = 0;
        return_obs_la_prev_bp0 = 1'bx;
        return_obs_la_prev_bp26 = 1'bx;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_LC9_ACTUAL enabled=%0d limit_name=RETURN_OBS_LC9_ACTUAL_LIMIT limit=%0d schema=LC9_ACTUAL",
                return_obs_la_enabled,
                return_obs_la_limit
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit la_lc9_valid;
        bit la_lc9_advance;
        bit la_lc7_capture;
        bit la_lc7_out_accept;
        bit la_mem3_in2_capture;
        bit la_mem3_match;
        bit la_mem3_push;
        bit la_mem3_pop;
        bit la_bp0;
        bit la_bp26;
        bit la_bp_change;
        bit la_any_event;
        logic [22:0] la_lc9_port;
        logic [22:0] la_lc7_port;
        logic [6:0] la_mem3_tag2;
        logic [1:0] la_mem3_mode2;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_la_records = 0;
            return_obs_la_lc9_advance = 0;
            return_obs_la_lc7_capture = 0;
            return_obs_la_lc7_out_accept = 0;
            return_obs_la_mem3_in2_capture = 0;
            return_obs_la_mem3_match = 0;
            return_obs_la_mem3_push = 0;
            return_obs_la_mem3_pop = 0;
            return_obs_la_lc9_last0 = 0;
            return_obs_la_prev_bp0 = 1'bx;
            return_obs_la_prev_bp26 = 1'bx;
        end else if (return_obs_la_enabled && return_obs_active) begin
            la_lc9_port = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[9];
            la_lc9_valid = la_lc9_port[22];
            la_bp0 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[9][0];
            la_bp26 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[9][26];
            la_lc9_advance = la_lc9_valid &&
                (&u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[9]);
            la_lc7_capture =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_LC[7].u_IGA_LC.u_IGA_LC_Inbuffer.iga_lc_inport_valid_bit_masked &&
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_LC[7].u_IGA_LC.iga_lc_inbuffer_bp_pre &&
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.slice_start_run;
            la_lc7_port = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[7];
            la_lc7_out_accept = la_lc7_port[22] &&
                (&u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[7]);
            la_mem3_tag2 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_queue_tag[2];
            la_mem3_mode2 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_idx_mode[2];
            la_mem3_in2_capture =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_valid_same_gotten_masked[2] &&
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_queue_bp_pre[2];
            la_mem3_match = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_all_idx_matched;
            la_mem3_push =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_wr_en &&
                !u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_full;
            la_mem3_pop =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_rd_en &&
                !u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty;
            la_bp_change = (la_bp0 !== return_obs_la_prev_bp0) ||
                           (la_bp26 !== return_obs_la_prev_bp26);
            la_any_event = la_lc9_advance || la_lc7_capture ||
                           la_lc7_out_accept || la_mem3_in2_capture ||
                           la_mem3_push || la_mem3_pop || la_bp_change ||
                           (la_lc9_valid && la_lc9_port[5] &&
                            (la_lc9_port[4:0] == 0));
            return_obs_la_lc9_advance += la_lc9_advance;
            return_obs_la_lc7_capture += la_lc7_capture;
            return_obs_la_lc7_out_accept += la_lc7_out_accept;
            return_obs_la_mem3_in2_capture += la_mem3_in2_capture;
            return_obs_la_mem3_match += la_mem3_match;
            return_obs_la_mem3_push += la_mem3_push;
            return_obs_la_mem3_pop += la_mem3_pop;
            return_obs_la_lc9_last0 +=
                la_lc9_valid && la_lc9_port[5] && (la_lc9_port[4:0] == 0);
            if (la_any_event && (return_obs_la_records < return_obs_la_limit)) begin
                return_obs_la_records += 1;
                $fdisplay(
                    return_obs_fd,
                    "%0t | LC9_ACTUAL_EDGE_V1 | lc9_adv=%0d lc9_port=%h bp0=%0d bp26=%0d bp_change=%0d lc7_capture=%0d lc7_out_accept=%0d lc7_port=%h lc7_enable=%0d lc7_src=%0d mem3_in2_capture=%0d mem3_match=%0d mem3_push=%0d mem3_pop=%0d mem3_tag2=%h mem3_mode2=%h mem3_full=%0d mem3_empty=%0d",
                    $time, la_lc9_advance, la_lc9_port, la_bp0, la_bp26,
                    la_bp_change, la_lc7_capture, la_lc7_out_accept,
                    la_lc7_port,
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_LC[7].u_IGA_LC.iga_lc_enable,
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_LC[7].u_IGA_LC.iga_lc_src_id,
                    la_mem3_in2_capture, la_mem3_match, la_mem3_push,
                    la_mem3_pop, la_mem3_tag2, la_mem3_mode2,
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_full,
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty
                );
                $fflush(return_obs_fd);
            end
            return_obs_la_prev_bp0 = la_bp0;
            return_obs_la_prev_bp26 = la_bp26;
        end
    end

    task automatic return_obs_write_lc9_actual_state(input string event_name);
        if (return_obs_la_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "%0t | LC9_ACTUAL_BOUNDARY_V1 | event=%s lc9_advance=%0d lc7_capture=%0d lc7_out_accept=%0d mem3_in2_capture=%0d mem3_match_level_cycles=%0d mem3_push=%0d mem3_pop=%0d lc9_last0=%0d lc9_port=%h lc9_bp=%h bp0=%0d bp26=%0d lc7_port=%h lc7_enable=%0d lc7_src=%0d mem3_tag2=%h mem3_mode2=%h mem3_full=%0d mem3_empty=%0d",
                $time, event_name, return_obs_la_lc9_advance,
                return_obs_la_lc7_capture, return_obs_la_lc7_out_accept,
                return_obs_la_mem3_in2_capture, return_obs_la_mem3_match,
                return_obs_la_mem3_push, return_obs_la_mem3_pop,
                return_obs_la_lc9_last0,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[9],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[9],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[9][0],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[9][26],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[7],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_LC[7].u_IGA_LC.iga_lc_enable,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_LC[7].u_IGA_LC.iga_lc_src_id,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_queue_tag[2],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_idx_mode[2],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_full,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty
            );
            $fflush(return_obs_fd);
        end
    endtask
    // v48 LC9_ACTUAL_ACTUAL_CONSUMER_END
'''


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "v48 LC9_ACTUAL_ACTUAL_CONSUMER_BEGIN" in text:
        raise BuildError("v48 observer block already present")
    anchor = '                return_obs_write_lc9_split_state("DIAG_DECISION");'
    if text.count(anchor) != 1:
        raise BuildError("v47 canonical decision call anchor differs")
    text = text.replace(
        anchor,
        anchor + '\n                return_obs_write_lc9_actual_state("DIAG_DECISION");',
        1,
    )
    text += OBSERVER_BLOCK
    path.write_text(text, encoding="utf-8", newline="\n")
    return base.sha256(path)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    token = "+RETURN_OBS_LC9_SPLIT_LIMIT=128"
    addition = token + " +RETURN_OBS_LC9_ACTUAL +RETURN_OBS_LC9_ACTUAL_LIMIT=192"
    if text.count(token) != 2:
        raise BuildError("runner LC9 split token count differs")
    path.write_text(
        text.replace(token, addition), encoding="utf-8", newline="\n"
    )


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    text = path.read_text(encoding="utf-8")
    anchor = (
        '        "feature": "RETURN_OBS_LC9_SPLIT",\n'
        '        "enable": "+RETURN_OBS_LC9_SPLIT",\n'
        '        "limits": ("+RETURN_OBS_LC9_SPLIT_LIMIT=128",),\n'
        '        "marker_tokens": (\n'
        '            "feature=RETURN_OBS_LC9_SPLIT", "enabled=1", "limit=128",\n'
        "        ),\n"
        "    },\n"
    )
    if text.count(anchor) != 1:
        raise BuildError("runtime LC9 split feature anchor differs")
    addition = anchor + (
        "    {\n"
        '        "feature": "RETURN_OBS_LC9_ACTUAL",\n'
        '        "enable": "+RETURN_OBS_LC9_ACTUAL",\n'
        '        "limits": ("+RETURN_OBS_LC9_ACTUAL_LIMIT=192",),\n'
        '        "marker_tokens": (\n'
        '            "feature=RETURN_OBS_LC9_ACTUAL", "enabled=1", "limit=192",\n'
        "        ),\n"
        "    },\n"
    )
    path.write_text(
        text.replace(anchor, addition, 1), encoding="utf-8", newline="\n"
    )


def release_gate_matrix() -> list[dict[str, Any]]:
    return [
        {
            "gate_id": "PACKAGE_BOOTSTRAP_PATH_RUNTIME_D",
            "applicability": "blocking_applicable",
            "reason": "fresh identity and one added diagnostic feature",
            "changed_surface": ["identity", "manifest", "README"],
            "evidence": ["exact-set", "path budget", "runtime-D absent"],
            "blocking": True,
        },
        {
            "gate_id": "RUNNER_TO_COMPILE_AND_FINALIZER",
            "applicability": "blocking_applicable",
            "reason": "runner receives LC9 actual-consumer argv",
            "changed_surface": ["PREPARE_AND_RUN.sh", "runtime feature parser"],
            "evidence": ["safe compile", "EXIT/TERM", "feature negatives"],
            "blocking": True,
        },
        {
            "gate_id": "ACTUALLY_REFERENCED_PACKAGE_LOCAL_HDL",
            "applicability": "blocking_applicable",
            "reason": "observer uses exact 0cc LC7 and MSE3 actual consumers",
            "changed_surface": ["native_return_observer.svh v48 span"],
            "evidence": ["actual consumer closure", "scope negatives"],
            "blocking": True,
        },
        {
            "gate_id": "CHANGED_MATERIALIZED_CONFIG_CONSUMER_CONTRACT",
            "applicability": "receipt_reuse",
            "reason": "config/address artifacts are identity-normalized byte equal",
            "changed_surface": [],
            "evidence": [
                "causal ledger receipt reuse",
                "boundary microtrace not applicable",
                "physical bank-row receipt reuse",
            ],
            "blocking": False,
        },
        {
            "gate_id": "CHANGED_OBSERVER_OR_CANONICAL_SEMANTICS",
            "applicability": "blocking_applicable",
            "reason": "new qualified LC9 actual-consumer trace",
            "changed_surface": ["LC9_ACTUAL_EDGE_V1", "LC9_ACTUAL_BOUNDARY_V1"],
            "evidence": ["predicate trace", "candidate matrix"],
            "blocking": True,
        },
        {
            "gate_id": "RETURN_RESULT_JOINT_GATE",
            "applicability": "blocking_applicable",
            "reason": "new feature receipt and expected return identity",
            "changed_surface": ["return feature schema"],
            "evidence": ["feature negatives", "formal-D joint gate"],
            "blocking": True,
        },
        {
            "gate_id": "FROZEN_NUMERIC_W3_GOLDEN",
            "applicability": "receipt_reuse",
            "reason": "frozen byte-equal payload",
            "changed_surface": [],
            "evidence": ["identity-normalized byte comparison"],
            "blocking": False,
        },
        {
            "gate_id": "UNRELATED_FUNCTIONAL_RTL",
            "applicability": "not_applicable",
            "reason": "server_rtl_entries=0",
            "changed_surface": [],
            "evidence": ["manifest classification"],
            "blocking": False,
        },
        {
            "gate_id": "REPORT_STYLE_OR_SYNONYMOUS_NEGATIVES",
            "applicability": "record_only",
            "reason": "no causal impact",
            "changed_surface": [],
            "evidence": ["release record"],
            "blocking": False,
        },
    ]


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v48-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    patch_runner(package)
    patch_runtime(package)
    observer_sha = patch_observer(package)

    provenance = package / "provenance"
    base.write_json(
        provenance / "v47_return_v48_lc9_actual.json",
        {
            "schema": "node0004-v47-return-v48-lc9-actual-v1",
            "bound_return_sha256": RETURN_SHA256,
            "source_v47_sha256": SOURCE_SHA256,
            "last_proven_good": (
                "LC9_VALID_HELD_AND_NONBLOCKING_BRANCHES_CAPTURE_WHILE_"
                "GLOBAL_LC9_ADVANCE_REMAINS_ZERO"
            ),
            "first_divergence": (
                "LC9_ACTUAL_BACKPRESSURE_BITS_0_AND_26_DEASSERT_AT_LC7_"
                "SOURCE8_AND_MSE3_SOURCE5_INPUT2"
            ),
            "root_cause": (
                "PACKAGE_OBSERVER_CAUSAL_CONSUMER_MISBIND_REQUIRES_"
                "FRESH_DIAGNOSTIC"
            ),
            "v47_false_progress": {
                "reported_pe1_in2_accept": 1310717,
                "global_lc9_advance": 0,
                "reason": "held valid level was counted without global advance",
            },
            "actual_backpressure_decode": {
                "bit0": "iga_lc_inport_bp_pre[7][8]",
                "bit26": "se2iga_mem_bp_pre[3][5][2]",
            },
            "release_gate_matrix": release_gate_matrix(),
        },
    )
    (package / "README.md").write_text(
        "# node0004 v48 LC9 actual-consumer diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v47 compiled and ran but observed the wrong downstream branches and "
        "counted a held valid level as repeated PE acceptance. v48 preserves "
        "all frozen workload/config/numeric/golden data and adds one bounded "
        "qualified trace for the actual low LC9 backpressure bits: LC7 source "
        "slot 8 and MSE3 source slot 5/input 2.\n\n"
        f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`\n\n"
        f"Expected return: `{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-lc9-actual-diagnostic-package-v48",
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "candidate_release": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    receipts = manifest["active_receipts"]
    receipts.update(
        {
            "agent_sha256": AGENT_SHA256,
            "plan_mutable_provenance_sha256": PLAN_MUTABLE_SHA256,
            "server_package_rule_sha256": SERVER_RULE_SHA256,
            "common_operator_rule_sha256": COMMON_RULE_SHA256,
            "ndp_hardware_fields_rule_sha256": NDP_RULE_SHA256,
        }
    )
    for item in receipts["generation_read_receipt"]:
        reason = item.get("reason")
        if reason == "server package routing":
            item["sha256"] = INDEX_SHA256
        elif reason == "common server package gates":
            item["sha256"] = SERVER_RULE_SHA256
        elif reason == "Conv INT8 SA accumulate release gate":
            item["sha256"] = INT8_SA_SHA256
        elif reason == "active server entry":
            item["sha256"] = README_SHA256
    for rule_id in RULE_IDS:
        if rule_id not in receipts["rules"]:
            receipts["rules"].append(rule_id)

    feature = {
        "feature": "RETURN_OBS_LC9_ACTUAL",
        "runtime_enable_parameter": "+RETURN_OBS_LC9_ACTUAL",
        "limit_or_budget_parameters": ["+RETURN_OBS_LC9_ACTUAL_LIMIT=192"],
        "time_zero_marker": (
            "DIAGNOSTIC_FEATURE_ENABLE_V1 feature=RETURN_OBS_LC9_ACTUAL "
            "enabled=1 limit_name=RETURN_OBS_LC9_ACTUAL_LIMIT "
            "limit=192 schema=LC9_ACTUAL"
        ),
        "expected_record_schema": "LC9_ACTUAL_BOUNDARY_V1",
        "edge_record_schema": "LC9_ACTUAL_EDGE_V1",
        "returned_record_target": "runs/c0/return_observer.log",
    }
    features = manifest["diagnostic_feature_runtime_binding"]["features"]
    if any(item.get("feature") == feature["feature"] for item in features):
        raise BuildError("LC9 actual feature already present")
    features.append(feature)
    manifest["lc9_actual_consumer_diagnostic"] = {
        **feature,
        "candidate_observation_matrix": {
            "LC7_INPUT_CAPTURE_OR_DOWNSTREAM_BLOCK": [
                "LC7 masked capture",
                "LC7 output accept",
                "bp bit0 transition",
            ],
            "MSE3_INPUT2_MATCH_OR_QUEUE_FULL": [
                "MSE3 input2 masked capture",
                "all-input match",
                "qualified queue push/pop",
                "queue full/empty state",
                "bp bit26 transition",
            ],
            "GLOBAL_TERMINAL_LOSS": [
                "qualified LC9 all-destination advance",
                "LC9 global last0",
            ],
        },
        "progress_definition": (
            "global all-destination advance or consumer-local masked capture/"
            "qualified queue transfer"
        ),
        "level_only_state": ["bp bits", "valid", "full", "empty", "mode"],
        "functional_fix": False,
        "configuration_changed": False,
    }
    manifest["v47_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "LC9_SPLIT_OBSERVER_MISBOUND_ACTUAL_CONSUMERS_UNRESOLVED",
        "compile_exit": 0,
        "run_exit": 0,
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
        "final_lc9_bp": "1fbfffffe",
        "zero_bp_bits": [0, 26],
        "old_outbuffer_occupancy": "INVALIDATED_NOT_RTL_BUG",
    }
    manifest["release_gate_matrix"] = release_gate_matrix()
    manifest["materialized_config_rule_applicability"] = {
        "causal_transaction_ledger": "RECEIPT_REUSE_BYTE_EQUAL",
        "boundary_microtrace": "NOT_APPLICABLE_NO_CHANGED_CONFIG_PREDICATE",
        "physical_bank_row_validity": "RECEIPT_REUSE_BYTE_EQUAL_ADDRESS",
    }
    manifest["cloud_rtl_authority"] = {
        "repository": "xlsjdjdk/Trassic2.0_RTL",
        "branch": "master",
        "approved_commit": RTL_COMMIT,
        "local_disk_commit": RTL_COMMIT,
        "identity_difference_blocks_compile_or_simulation": False,
        "actual_compile_identity_required_in_return": True,
    }
    manifest["observer_public_surface_or_xmr_proof"] = {
        "rule_id": "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
        "public_or_module_port_consumers": [
            "Index_Generation_Array.iga_lc_outport[9/7]",
            "Index_Generation_Array.iga_lc_outport_bp_post[9][0/26]",
            "Memory_WR_Stream_Engine.mse_mem_queue_tag/bp_pre",
        ],
        "private_consumers_required": [
            "IGA_LC7 masked-valid/inbuffer ready/config source",
            "MSE3 Memory_AG_Idx_Queue masked-valid/match/FIFO transfers",
        ],
        "focused_wrapper_fabricates_target_leaf": False,
    }
    manifest["superseded_v47_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA256,
        "status": "RETURN_CONSUMED_SUPERSEDED_BY_V48_DIAGNOSTIC",
    }
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"].update(
        {
            "sha256": observer_sha,
            "size_bytes": (
                package / "tb_probe/native_return_observer.svh"
            ).stat().st_size,
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
        raise BuildError("refusing to overwrite existing v48 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v48-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v48 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-v47-return-v48-lc9-actual-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v47_sha256": SOURCE_SHA256,
        "bound_v47_return_sha256": RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "current_common_rule_sha256": COMMON_RULE_SHA256,
        "builder_plan_mutable_provenance_sha256": PLAN_MUTABLE_SHA256,
        "current_cloud_rtl_authority_commit": RTL_COMMIT,
        "release_gate_matrix_entry_count": len(release_gate_matrix()),
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
