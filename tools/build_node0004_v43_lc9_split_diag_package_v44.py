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

import tools.build_node0004_v40_wrterm2_diag_package_v41 as previous


base = previous.base
SOURCE_NAME = "r5_n4_hw_v43_wrterm2_compilefix"
INSTALL_NAME = "r5_n4_hw_v44_lc9_split_diag"
VERSION = 44
SOURCE_SHA256 = "ba3c2df775c8f7f7bef47eec15d079651eb7c60e20145aca7dedef7345fe54e2"
RETURN_SHA256 = "5ed315d6121dba0a7e2bc81b9672ab8604c66a5b32b280b647dbc2e5af6b4e11"
RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
PLAN_MUTABLE_SHA256 = "58be3123e7d11890403f6d9fae2ffde133c2aa2df2cfef8733cdd8fe60738a5a"
SERVER_RULE_SHA256 = "68fafe7c33e8ac037d94308a0902cdb52afec32f1325d6cee9bc14f70ca9d69d"
COMMON_RULE_SHA256 = "d4069167000ae5e0076401afbc6c8db20965965ef4f5da30914f40297f59cba0"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
RULE_IDS = [
    "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
    "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
    "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
    "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
    "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
    "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
    "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
    "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
]


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v43 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v43 source CRC failed")
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
            raise BuildError(f"v43 root differs: {sorted(roots)}")
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

    // v44 LC9_SPLIT_ACTUAL_CONSUMER_BEGIN
    // Qualified handshakes are progress. Full/count/valid levels are state only.
    bit return_obs_ls_enabled;
    integer return_obs_ls_limit;
    integer return_obs_ls_plusarg_status;
    integer return_obs_ls_records;
    longint unsigned return_obs_ls_lc9_advance;
    longint unsigned return_obs_ls_pe1_in2_accept;
    longint unsigned return_obs_ls_pe1_match;
    longint unsigned return_obs_ls_pe1_out_accept;
    longint unsigned return_obs_ls_mem1_accept;
    longint unsigned return_obs_ls_row4_accept;
    longint unsigned return_obs_ls_row4_out_accept;
    longint unsigned return_obs_ls_buf_source_push;
    longint unsigned return_obs_ls_lc9_last0;
    longint unsigned return_obs_ls_pe1_last0;
    longint unsigned return_obs_ls_mem1_last0;
    longint unsigned return_obs_ls_row4_last0;

    initial begin
        return_obs_ls_enabled = $test$plusargs("RETURN_OBS_LC9_SPLIT");
        return_obs_ls_limit = 128;
        return_obs_ls_plusarg_status = $value$plusargs(
            "RETURN_OBS_LC9_SPLIT_LIMIT=%d", return_obs_ls_limit
        );
        return_obs_ls_records = 0;
        return_obs_ls_lc9_advance = 0;
        return_obs_ls_pe1_in2_accept = 0;
        return_obs_ls_pe1_match = 0;
        return_obs_ls_pe1_out_accept = 0;
        return_obs_ls_mem1_accept = 0;
        return_obs_ls_row4_accept = 0;
        return_obs_ls_row4_out_accept = 0;
        return_obs_ls_buf_source_push = 0;
        return_obs_ls_lc9_last0 = 0;
        return_obs_ls_pe1_last0 = 0;
        return_obs_ls_mem1_last0 = 0;
        return_obs_ls_row4_last0 = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_LC9_SPLIT enabled=%0d limit_name=RETURN_OBS_LC9_SPLIT_LIMIT limit=%0d schema=LC9_SPLIT",
                return_obs_ls_enabled,
                return_obs_ls_limit
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit ls_lc9_valid;
        bit ls_lc9_ready;
        bit ls_lc9_advance;
        bit ls_pe1_in2_ready;
        bit ls_pe1_in2_accept;
        bit ls_pe1_match;
        bit ls_pe1_out_valid;
        bit ls_pe1_out_ready;
        bit ls_pe1_out_accept;
        bit ls_mem1_valid;
        bit ls_mem1_ready;
        bit ls_mem1_accept;
        bit ls_row4_accept;
        bit ls_row4_out_accept;
        bit ls_buf_source_push;
        bit ls_any_event;
        logic [22:0] ls_lc9_port;
        logic [22:0] ls_pe1_port;
        logic [6:0] ls_mem1_tag;
        logic [22:0] ls_row4_port;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_ls_records = 0;
            return_obs_ls_lc9_advance = 0;
            return_obs_ls_pe1_in2_accept = 0;
            return_obs_ls_pe1_match = 0;
            return_obs_ls_pe1_out_accept = 0;
            return_obs_ls_mem1_accept = 0;
            return_obs_ls_row4_accept = 0;
            return_obs_ls_row4_out_accept = 0;
            return_obs_ls_buf_source_push = 0;
            return_obs_ls_lc9_last0 = 0;
            return_obs_ls_pe1_last0 = 0;
            return_obs_ls_mem1_last0 = 0;
            return_obs_ls_row4_last0 = 0;
        end else if (return_obs_ls_enabled && return_obs_active) begin
            ls_lc9_port = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[9];
            ls_lc9_valid = ls_lc9_port[22];
            ls_lc9_ready = &u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[9];
            ls_lc9_advance = ls_lc9_valid && ls_lc9_ready;
            ls_pe1_in2_ready = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_pe_inport_bp_pre[1][9][2];
            ls_pe1_in2_accept = ls_lc9_valid && ls_pe1_in2_ready;
            ls_pe1_match = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inbuffer_matched;
            ls_pe1_port = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_pe_outport[1];
            ls_pe1_out_valid = ls_pe1_port[22];
            ls_pe1_out_ready = &u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_pe_outport_bp_post[1];
            ls_pe1_out_accept = ls_pe1_out_valid && ls_pe1_out_ready;
            ls_mem1_tag = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_queue_tag[1];
            ls_mem1_valid = ls_mem1_tag[6];
            ls_mem1_ready = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_queue_bp_pre[1];
            ls_mem1_accept = ls_mem1_valid && ls_mem1_ready;
            ls_row4_accept = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_ROW_LC[4].u_IGA_ROW_LC.iga_row_lc_inbuffer_bp_pre &&
                             u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_ROW_LC[4].u_IGA_ROW_LC.u_IGA_ROW_LC_Inbuffer.iga_row_lc_inport_valid_bit_masked;
            ls_row4_out_accept = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_ROW_LC[4].u_IGA_ROW_LC.u_IGA_ROW_LC_Counter.iga_row_lc_cnt_outport_valid_bit &&
                                 u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_ROW_LC[4].u_IGA_ROW_LC.iga_row_lc_cnt_bp_post;
            ls_row4_port = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_ROW_LC[4].u_IGA_ROW_LC.iga_row_lc_outport;
            ls_buf_source_push = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en &&
                                 !u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full;
            ls_any_event = ls_lc9_advance || ls_pe1_in2_accept || ls_pe1_match ||
                           ls_pe1_out_accept || ls_mem1_accept || ls_row4_accept ||
                           ls_row4_out_accept || ls_buf_source_push;

            if (ls_lc9_advance) return_obs_ls_lc9_advance = return_obs_ls_lc9_advance + 1;
            if (ls_pe1_in2_accept) return_obs_ls_pe1_in2_accept = return_obs_ls_pe1_in2_accept + 1;
            if (ls_pe1_match) return_obs_ls_pe1_match = return_obs_ls_pe1_match + 1;
            if (ls_pe1_out_accept) return_obs_ls_pe1_out_accept = return_obs_ls_pe1_out_accept + 1;
            if (ls_mem1_accept) return_obs_ls_mem1_accept = return_obs_ls_mem1_accept + 1;
            if (ls_row4_accept) return_obs_ls_row4_accept = return_obs_ls_row4_accept + 1;
            if (ls_row4_out_accept) return_obs_ls_row4_out_accept = return_obs_ls_row4_out_accept + 1;
            if (ls_buf_source_push) return_obs_ls_buf_source_push = return_obs_ls_buf_source_push + 1;
            if (ls_lc9_advance && ls_lc9_port[21] && (ls_lc9_port[19:16] == 0)) return_obs_ls_lc9_last0 = return_obs_ls_lc9_last0 + 1;
            if (ls_pe1_out_accept && ls_pe1_port[21] && (ls_pe1_port[19:16] == 0)) return_obs_ls_pe1_last0 = return_obs_ls_pe1_last0 + 1;
            if (ls_mem1_accept && ls_mem1_tag[5] && (ls_mem1_tag[3:0] == 0)) return_obs_ls_mem1_last0 = return_obs_ls_mem1_last0 + 1;
            if (ls_row4_out_accept && ls_row4_port[21] && (ls_row4_port[19:16] == 0)) return_obs_ls_row4_last0 = return_obs_ls_row4_last0 + 1;

            if (ls_any_event && return_obs_ls_records < return_obs_ls_limit &&
                return_obs_fd != 0) begin
                return_obs_ls_records = return_obs_ls_records + 1;
                $fdisplay(
                    return_obs_fd,
                    "%0t | LC9_SPLIT_EDGE_V1 | lc9_adv=%0d lc9_port=%h lc9_bp=%h pe1_in2_ready=%0d pe1_in2_accept=%0d pe1_match=%0d pe1_out_accept=%0d pe1_port=%h pe1_bp=%h mem1_accept=%0d mem1_tag=%h mem1_ready=%0d row4_accept=%0d row4_out_accept=%0d row4_port=%h buf_source_push=%0d",
                    $time, ls_lc9_advance, ls_lc9_port,
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[9],
                    ls_pe1_in2_ready, ls_pe1_in2_accept, ls_pe1_match,
                    ls_pe1_out_accept, ls_pe1_port,
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_pe_outport_bp_post[1],
                    ls_mem1_accept, ls_mem1_tag, ls_mem1_ready,
                    ls_row4_accept, ls_row4_out_accept, ls_row4_port,
                    ls_buf_source_push
                );
                $fflush(return_obs_fd);
            end
        end
    end

    task automatic return_obs_write_lc9_split_state(input string event_name);
        if (return_obs_ls_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "%0t | LC9_SPLIT_BOUNDARY_V1 | event=%s lc9_advance=%0d pe1_in2_accept=%0d pe1_match=%0d pe1_out_accept=%0d mem1_accept=%0d row4_accept=%0d row4_out_accept=%0d buf_source_push=%0d lc9_last0=%0d pe1_last0=%0d mem1_last0=%0d row4_last0=%0d lc9_port=%h lc9_bp=%h pe1_port=%h pe1_bp=%h mem1_tag=%h mem1_ready=%0d row4_port=%h",
                $time, event_name, return_obs_ls_lc9_advance,
                return_obs_ls_pe1_in2_accept, return_obs_ls_pe1_match,
                return_obs_ls_pe1_out_accept, return_obs_ls_mem1_accept,
                return_obs_ls_row4_accept, return_obs_ls_row4_out_accept,
                return_obs_ls_buf_source_push, return_obs_ls_lc9_last0,
                return_obs_ls_pe1_last0, return_obs_ls_mem1_last0,
                return_obs_ls_row4_last0,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[9],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[9],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_pe_outport[1],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_pe_outport_bp_post[1],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_queue_tag[1],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_queue_bp_pre[1],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_ROW_LC[4].u_IGA_ROW_LC.iga_row_lc_outport
            );
            $fflush(return_obs_fd);
        end
    endtask
    // v44 LC9_SPLIT_ACTUAL_CONSUMER_END
'''


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    marker = f"v{VERSION} LC9_SPLIT_ACTUAL_CONSUMER_BEGIN"
    if marker in text:
        raise BuildError(f"v{VERSION} observer block already present")
    anchor = '                return_obs_write_wrterm_state("DIAG_DECISION");'
    if text.count(anchor) != 1:
        raise BuildError("canonical decision call anchor differs")
    text = text.replace(
        anchor,
        anchor + '\n                return_obs_write_lc9_split_state("DIAG_DECISION");',
        1,
    )
    text += OBSERVER_BLOCK
    path.write_text(text, encoding="utf-8", newline="\n")
    return base.sha256(path)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    token = "+RETURN_OBS_WRTERM_LIMIT=96"
    addition = token + " +RETURN_OBS_LC9_SPLIT +RETURN_OBS_LC9_SPLIT_LIMIT=128"
    if text.count(token) != 2:
        raise BuildError("runner WRTERM token count differs")
    text = text.replace(token, addition)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    text = path.read_text(encoding="utf-8")
    anchor = (
        '        "feature": "RETURN_OBS_WRTERM",\n'
        '        "enable": "+RETURN_OBS_WRTERM",\n'
        '        "limits": ("+RETURN_OBS_WRTERM_LIMIT=96",),\n'
        '        "marker_tokens": (\n'
        '            "feature=RETURN_OBS_WRTERM", "enabled=1", "limit=96",\n'
        "        ),\n"
        "    },\n"
    )
    if text.count(anchor) != 1:
        raise BuildError("runtime WRTERM feature anchor differs")
    addition = anchor + (
        "    {\n"
        '        "feature": "RETURN_OBS_LC9_SPLIT",\n'
        '        "enable": "+RETURN_OBS_LC9_SPLIT",\n'
        '        "limits": ("+RETURN_OBS_LC9_SPLIT_LIMIT=128",),\n'
        '        "marker_tokens": (\n'
        '            "feature=RETURN_OBS_LC9_SPLIT", "enabled=1", "limit=128",\n'
        "        ),\n"
        "    },\n"
    )
    text = text.replace(anchor, addition, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def release_gate_matrix() -> list[dict[str, Any]]:
    return [
        {
            "gate_id": "PACKAGE_BOOTSTRAP_PATH_RUNTIME_D",
            "applicable": True,
            "reason": "fresh package identity and one added diagnostic feature",
            "changed_surface": ["install identity", "manifest", "README"],
            "evidence": ["exact-set", "path budget", "runtime-D absent"],
            "blocking": True,
        },
        {
            "gate_id": "RUNNER_TO_COMPILE_AND_FINALIZER",
            "applicable": True,
            "reason": "runner receives the new feature argv",
            "changed_surface": ["PREPARE_AND_RUN.sh", "runtime feature parser"],
            "evidence": ["safe compile", "EXIT/TERM finalizer", "feature negatives"],
            "blocking": True,
        },
        {
            "gate_id": "ACTUALLY_REFERENCED_PACKAGE_LOCAL_HDL",
            "applicable": True,
            "reason": "LC9 split observer adds exact current RTL consumers",
            "changed_surface": [
                f"native_return_observer.svh v{VERSION} span"
            ],
            "evidence": ["actual-consumer closure", "typo/delete/sibling negatives"],
            "blocking": True,
        },
        {
            "gate_id": "CHANGED_MATERIALIZED_CONFIG_CONSUMER_CONTRACT",
            "applicable": False,
            "reason": "final config/mapping/bitstream/execplan/SCA byte-equal after identity normalization",
            "changed_surface": [],
            "evidence": [
                "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001 receipt-reuse",
                "CDA-CONFIG-BOUNDARY-MICROTRACE-001 not_applicable",
            ],
            "blocking": False,
        },
        {
            "gate_id": "CHANGED_OBSERVER_OR_CANONICAL_SEMANTICS",
            "applicable": True,
            "reason": "new qualified LC9 split trace and boundary summary",
            "changed_surface": ["LC9_SPLIT_EDGE_V1", "LC9_SPLIT_BOUNDARY_V1"],
            "evidence": ["predicate trace", "candidate observation matrix"],
            "blocking": True,
        },
        {
            "gate_id": "RETURN_RESULT_JOINT_GATE",
            "applicable": True,
            "reason": "new feature receipts and expected return identity",
            "changed_surface": ["return allowlist/schema/identity"],
            "evidence": ["feature binding negatives", "formal-D joint gate"],
            "blocking": True,
        },
        {
            "gate_id": "FROZEN_NUMERIC_W3_GOLDEN",
            "applicable": False,
            "reason": "byte-equal frozen payload",
            "changed_surface": [],
            "evidence": ["identity-normalized byte comparison"],
            "blocking": False,
        },
        {
            "gate_id": "UNRELATED_FUNCTIONAL_RTL",
            "applicable": False,
            "reason": "server_rtl_entries=0 and functional RTL unchanged",
            "changed_surface": [],
            "evidence": ["manifest classification"],
            "blocking": False,
        },
        {
            "gate_id": "REPORT_STYLE_OR_SYNONYMOUS_NEGATIVES",
            "applicable": False,
            "reason": "record_only",
            "changed_surface": [],
            "evidence": ["release record"],
            "blocking": False,
        },
    ]


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v44-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    patch_runner(package)
    patch_runtime(package)
    observer_sha = patch_observer(package)

    provenance = package / "provenance"
    base.write_json(
        provenance / f"v43_return_v{VERSION}_lc9_split.json",
        {
            "schema": f"node0004-v43-return-v{VERSION}-lc9-split-v1",
            "bound_return_sha256": RETURN_SHA256,
            "source_v43_sha256": SOURCE_SHA256,
            "last_proven_good": (
                "32_MEMORY_DESCRIPTORS_CONSUMED_AND_DESCRIPTOR_FIFO_"
                "DRAINS_WHILE_BUFFER_DATA_PATH_REMAINS_ACTIVE"
            ),
            "first_divergence": (
                "MSE4_MEMORY_BUFFER_CARRIER_STOPS_BEFORE_GLOBAL_LAST0_"
                "WHILE_BUFFER_AG_SOURCE_CONTINUES_TO_CAPACITY"
            ),
            "root_cause": "UNRESOLVED_REQUIRES_SHARED_LC9_BRANCH_DIAGNOSTIC",
            "false_final_descriptor": {
                "last": 1,
                "last_index": 5,
                "global_last0": False,
            },
            "release_gate_matrix": release_gate_matrix(),
        },
    )
    (package / "README.md").write_text(
        f"# node0004 v{VERSION} LC9 split diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v43 compiled and ran, proving the v41 private-XMR failure closed. "
        "Its descriptor FIFO 1->0 pop carried last_index=5, not global "
        "last_index=0. This successor adds one low-overhead qualified trace "
        "covering the shared LC9 producer, PE1/Memory-AG branch, and D "
        "Buffer-AG row branch. Numeric, workload, materialized config, golden, "
        "timeout, backpressure, and functional RTL are unchanged.\n\n"
        f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`\n\n"
        f"Expected return: `{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": (
                f"resnet50-node0004-lc9-split-diagnostic-package-v{VERSION}"
            ),
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
    receipts["plan_mutable_provenance_sha256"] = PLAN_MUTABLE_SHA256
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    receipts["common_operator_rule_sha256"] = COMMON_RULE_SHA256
    for rule_id in RULE_IDS:
        if rule_id not in receipts["rules"]:
            receipts["rules"].append(rule_id)
    for item in receipts["generation_read_receipt"]:
        reason = item.get("reason", "")
        if reason == "common server package gates":
            item["sha256"] = SERVER_RULE_SHA256
        elif reason == "common operator configuration gates":
            item["sha256"] = COMMON_RULE_SHA256

    feature = {
        "feature": "RETURN_OBS_LC9_SPLIT",
        "runtime_enable_parameter": "+RETURN_OBS_LC9_SPLIT",
        "limit_or_budget_parameters": ["+RETURN_OBS_LC9_SPLIT_LIMIT=128"],
        "time_zero_marker": (
            "DIAGNOSTIC_FEATURE_ENABLE_V1 feature=RETURN_OBS_LC9_SPLIT "
            "enabled=1 limit_name=RETURN_OBS_LC9_SPLIT_LIMIT "
            "limit=128 schema=LC9_SPLIT"
        ),
        "expected_record_schema": "LC9_SPLIT_BOUNDARY_V1",
        "edge_record_schema": "LC9_SPLIT_EDGE_V1",
        "returned_record_target": "runs/c0/return_observer.log",
    }
    features = manifest["diagnostic_feature_runtime_binding"]["features"]
    if any(item.get("feature") == feature["feature"] for item in features):
        raise BuildError("LC9 split feature already present")
    features.append(feature)
    manifest["lc9_split_diagnostic"] = {
        **feature,
        "candidate_observation_matrix": {
            "SHARED_LC9_BRANCH_BACKPRESSURE": [
                "lc9 valid with PE1-in2 ready != ROW4 ready",
                "lc9 all-destination accept",
            ],
            "PE1_BUFFER_KEEP_MATCH": [
                "PE1 in2 accept without PE1 match/output",
            ],
            "MEMORY_AG_PORT1_ACCEPT": [
                "PE1 output accept versus MSE4 memory port1 accept",
            ],
            "BUFFER_AG_ROW_PIPELINE": [
                "ROW4 accept/output versus Buffer-AG source push",
            ],
            "GLOBAL_LAST0_LOSS": [
                "global last0 at LC9, PE1, memory port1, and ROW4",
            ],
        },
        "progress_definition": "qualified valid-and-ready handshake only",
        "level_only_state": ["backpressure vectors", "valid", "count", "full"],
        "functional_fix": False,
        "configuration_changed": False,
    }
    manifest["v43_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "COMPILE_FIX_CROSSED_DYNAMIC_STALL_REFINED",
        "compile_exit": 0,
        "run_exit": 0,
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
        "last_proven_good": (
            "32_MEMORY_DESCRIPTORS_CONSUMED_AND_DESCRIPTOR_FIFO_DRAINS_"
            "WHILE_BUFFER_DATA_PATH_REMAINS_ACTIVE"
        ),
        "first_divergence": (
            "MSE4_MEMORY_BUFFER_CARRIER_STOPS_BEFORE_GLOBAL_LAST0_WHILE_"
            "BUFFER_AG_SOURCE_CONTINUES_TO_CAPACITY"
        ),
        "root_cause": "UNRESOLVED_REQUIRES_SHARED_LC9_BRANCH_DIAGNOSTIC",
        "old_outbuffer_occupancy": "INVALIDATED_NOT_RTL_BUG",
    }
    manifest["release_gate_matrix"] = release_gate_matrix()
    manifest["materialized_config_rule_applicability"] = {
        "causal_transaction_ledger": "RECEIPT_REUSE_BYTE_EQUAL",
        "boundary_microtrace": "NOT_APPLICABLE_NO_CHANGED_CONFIG_PREDICATE",
    }
    manifest["cloud_rtl_authority"] = {
        "repository": "xlsjdjdk/Trassic2.0_RTL",
        "branch": "master",
        "approved_commit": RTL_COMMIT,
        "identity_difference_blocks_compile_or_simulation": False,
        "actual_compile_identity_required_in_return": True,
        "causal_cone_receipt": (
            f"outputs/conv_node0004_v{VERSION}_package_validation/"
            "cloud_rtl_causal_cone.json"
        ),
    }
    manifest["observer_public_surface_or_xmr_proof"] = {
        "rule_id": "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
        "public_or_module_port_consumers": [
            "Index_Generation_Array.iga_lc_outport/bp_post",
            "Index_Generation_Array.iga_pe_outport/bp_post",
            "Memory_WR_Stream_Engine.mse_mem_queue_tag/bp_pre",
        ],
        "private_consumers_required": [
            "IGA_PE_Inbuffer.iga_pe_inbuffer_matched",
            "IGA_ROW_LC inbuffer/counter handshake leaves",
            "Buffer_AG_Idx_Queue FIFO push/full",
        ],
        "proof_receipt": (
            f"outputs/conv_node0004_v{VERSION}_package_validation/"
            "actual_hdl_consumers.json"
        ),
        "focused_wrapper_fabricates_target_leaf": False,
    }
    manifest["superseded_v43_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA256,
        "status": f"RETURN_CONSUMED_SUPERSEDED_BY_V{VERSION}_DIAGNOSTIC",
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
        raise BuildError(f"refusing to overwrite existing v{VERSION} target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(
        prefix=f"node0004-v{VERSION}-repeat-"
    ) as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError(f"v{VERSION} deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": (
            f"node0004-v43-return-v{VERSION}-lc9-split-build-v1"
        ),
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v43_sha256": SOURCE_SHA256,
        "bound_v43_return_sha256": RETURN_SHA256,
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
