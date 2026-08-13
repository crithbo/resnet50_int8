from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import deterministic_zip, write_json
from tools.gap_node0071_complete_server_runtime import file_records
from tools import build_gap_node0071_buffer_ag_idx_queue_v33_package as source_builder


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v33_buffer_ag_idx_pair_diag"
INSTALL_NAME = "r5_n71_gap_v36_dbclk_rdready_diag"
TEST_ID = "r5-gap-node0071-v36-dbclk-rdready-information-gain-diagnostic"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = "5bd5f3a4cc555f618d535aba375363cf0c041abe506d7b3589cc4265b4459c03"
TRIGGER_RETURN_SHA256 = "94e1abd19246b773cb3d3dd19c9bcfafa398da35fa09c310c27b8a4fca661daa"
TRIGGER_ANALYSIS = (
    ROOT / "artifacts/operator_config_validation/r5-gap-node0071-v33-return-analysis/report.json"
)
OBSERVER = "tb_probe/native_return_observer.svh"
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    OBSERVER,
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}
CURRENT_RECEIPTS = {
    "agent_sha256": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    "plan_sha256_mutable_provenance_only": "e7fc830496910db2aea2c87ef4bbbcfb16f2f13355e2662e3404b2106d650c23",
    "generation_index_sha256": "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2",
    "server_rule_sha256": "14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1",
    "common_operator_rule_sha256": "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    "ndp_field_rule_sha256": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    "gap_int32_rule_sha256": "4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b",
    "gap_probe_rule_sha256": "db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1",
    "exact_uint8_tail_rule_sha256": "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
}


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise BuildError(f"{label}: expected one marker, found {count}")
    return text.replace(old, new, 1)


DECLARATIONS = r'''    // v34: clk_db-owned queue -> WR conjunction -> RD supply diagnostic.
    bit return_obs_dbrr_enabled;
    int return_obs_dbrr_limit;
    int return_obs_dbrr_emit_count;
    longint unsigned return_obs_db_clock_edge_count;
    longint unsigned return_obs_dbrr_req_accept [0:1];
    longint unsigned return_obs_dbrr_queue_enqueue [0:1];
    longint unsigned return_obs_dbrr_queue_dequeue [0:1];
    longint unsigned return_obs_dbrr_ib_write [0:1];
    longint unsigned return_obs_dbrr_ib_read [0:1];
    longint unsigned return_obs_dbrr_prep_write [0:1];
    longint unsigned return_obs_dbrr_prep_read [0:1];
    longint unsigned return_obs_dbrr_wr_accept [0:1];
    longint unsigned return_obs_dbrr_first_ready_low [0:1];
    longint unsigned return_obs_dbrr_last_ready_low [0:1];
    longint unsigned return_obs_dbrr_first_data_vld_low [0:1];
    longint unsigned return_obs_dbrr_last_data_vld_low [0:1];
    longint unsigned return_obs_dbrr_first_rd_ob_full [0:1];
    longint unsigned return_obs_dbrr_last_rd_ob_full [0:1];
    longint unsigned return_obs_dbrr_first_wr_ob_full [0:1];
    longint unsigned return_obs_dbrr_last_wr_ob_full [0:1];
    longint unsigned return_obs_dbrr_first_barrier [0:1];
    longint unsigned return_obs_dbrr_last_barrier [0:1];

    task automatic return_obs_dbrr_reset;
        begin
            return_obs_db_clock_edge_count = 0;
            return_obs_dbrr_emit_count = 0;
            for (int dbrr_flow = 0; dbrr_flow < 2; dbrr_flow++) begin
                return_obs_dbrr_req_accept[dbrr_flow] = 0;
                return_obs_dbrr_queue_enqueue[dbrr_flow] = 0;
                return_obs_dbrr_queue_dequeue[dbrr_flow] = 0;
                return_obs_dbrr_ib_write[dbrr_flow] = 0;
                return_obs_dbrr_ib_read[dbrr_flow] = 0;
                return_obs_dbrr_prep_write[dbrr_flow] = 0;
                return_obs_dbrr_prep_read[dbrr_flow] = 0;
                return_obs_dbrr_wr_accept[dbrr_flow] = 0;
                return_obs_dbrr_first_ready_low[dbrr_flow] = 0;
                return_obs_dbrr_last_ready_low[dbrr_flow] = 0;
                return_obs_dbrr_first_data_vld_low[dbrr_flow] = 0;
                return_obs_dbrr_last_data_vld_low[dbrr_flow] = 0;
                return_obs_dbrr_first_rd_ob_full[dbrr_flow] = 0;
                return_obs_dbrr_last_rd_ob_full[dbrr_flow] = 0;
                return_obs_dbrr_first_wr_ob_full[dbrr_flow] = 0;
                return_obs_dbrr_last_wr_ob_full[dbrr_flow] = 0;
                return_obs_dbrr_first_barrier[dbrr_flow] = 0;
                return_obs_dbrr_last_barrier[dbrr_flow] = 0;
            end
        end
    endtask

'''


SUMMARY = r'''                    if (return_obs_dbrr_enabled) begin
                        $fdisplay(
                            return_obs_fd,
                            "%0t | DBCLK_RD_READY_COUNTS_V1 | event=%s edge=%0d req=%0d/%0d q_enq=%0d/%0d q_deq=%0d/%0d ib_wr=%0d/%0d ib_rd=%0d/%0d prep_wr=%0d/%0d prep_rd=%0d/%0d wr_accept=%0d/%0d records=%0d limit=%0d",
                            $time, event_name, return_obs_db_clock_edge_count,
                            return_obs_dbrr_req_accept[0], return_obs_dbrr_req_accept[1],
                            return_obs_dbrr_queue_enqueue[0], return_obs_dbrr_queue_enqueue[1],
                            return_obs_dbrr_queue_dequeue[0], return_obs_dbrr_queue_dequeue[1],
                            return_obs_dbrr_ib_write[0], return_obs_dbrr_ib_write[1],
                            return_obs_dbrr_ib_read[0], return_obs_dbrr_ib_read[1],
                            return_obs_dbrr_prep_write[0], return_obs_dbrr_prep_write[1],
                            return_obs_dbrr_prep_read[0], return_obs_dbrr_prep_read[1],
                            return_obs_dbrr_wr_accept[0], return_obs_dbrr_wr_accept[1],
                            return_obs_dbrr_emit_count, return_obs_dbrr_limit
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | DBCLK_RD_READY_STATE_V1 | event=%s bq_wr=%0b bq_full=%0b bq_rd=%0b bq_empty=%0b bq_count=%0d bq_out_valid=%0b bp_pre=0x%0h wr_ob_full=0x%0h data_ready=0x%0h data_vld=0x%0h prep_count=0x%0h rd_ob_full=0x%0h barrier=0x%0h req_vld=0x%0h req_ready=0x%0h rd_q_full=0x%0h rd_q_empty=0x%0h ib_vld=0x%0h ib_sel=0x%0h",
                            $time, event_name,
                            return_obs_bq_wr_en_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_full_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_rd_en_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_count_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bq_out_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bp_pre_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bp_ob_full_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bp_data_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bp_data_vld_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bp_prepared_count_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bp_rd_ob_full_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_bp_barrier_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_req_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_req_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_queue_full_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_queue_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_ib_vld_mon[return_obs_group_id][return_obs_local_slice_id],
                            return_obs_rd_ib_sel_mon[return_obs_group_id][return_obs_local_slice_id]
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | DBCLK_RD_READY_WITNESS_V1 | event=%s ready_low=%0d:%0d/%0d:%0d data_vld_low=%0d:%0d/%0d:%0d rd_ob_full=%0d:%0d/%0d:%0d wr_ob_full=%0d:%0d/%0d:%0d barrier=%0d:%0d/%0d:%0d",
                            $time, event_name,
                            return_obs_dbrr_first_ready_low[0], return_obs_dbrr_last_ready_low[0],
                            return_obs_dbrr_first_ready_low[1], return_obs_dbrr_last_ready_low[1],
                            return_obs_dbrr_first_data_vld_low[0], return_obs_dbrr_last_data_vld_low[0],
                            return_obs_dbrr_first_data_vld_low[1], return_obs_dbrr_last_data_vld_low[1],
                            return_obs_dbrr_first_rd_ob_full[0], return_obs_dbrr_last_rd_ob_full[0],
                            return_obs_dbrr_first_rd_ob_full[1], return_obs_dbrr_last_rd_ob_full[1],
                            return_obs_dbrr_first_wr_ob_full[0], return_obs_dbrr_last_wr_ob_full[0],
                            return_obs_dbrr_first_wr_ob_full[1], return_obs_dbrr_last_wr_ob_full[1],
                            return_obs_dbrr_first_barrier[0], return_obs_dbrr_last_barrier[0],
                            return_obs_dbrr_first_barrier[1], return_obs_dbrr_last_barrier[1]
                        );
                    end
'''


SAMPLER = r'''    // v34 sampler: all qualified events are sampled in their clk_db owner domain.
    always @(posedge u_NDP_Top_new.clk) begin
        if (
            u_NDP_Top_new.rst_n &&
            return_obs_enabled &&
            return_obs_dbrr_enabled &&
            return_obs_active &&
            return_obs_fd != 0
        ) begin
            return_obs_db_clock_edge_count++;
            for (int dbrr_flow = 0; dbrr_flow < 2; dbrr_flow++) begin
                bit dbrr_req;
                bit dbrr_q_enq;
                bit dbrr_q_deq;
                bit dbrr_ib_wr;
                bit dbrr_ib_rd;
                bit dbrr_prep_wr;
                bit dbrr_prep_rd;
                bit dbrr_wr_accept;
                bit dbrr_event;
                dbrr_req =
                    return_obs_rd_req_valid_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow] &&
                    return_obs_rd_req_ready_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow];
                dbrr_q_enq =
                    return_obs_flow_q_wr_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow] &&
                    !return_obs_flow_q_full_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow];
                dbrr_q_deq =
                    return_obs_flow_q_rd_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow] &&
                    !return_obs_flow_q_empty_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow];
                dbrr_ib_wr =
                    |return_obs_rd_ib_wr_hs_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow];
                dbrr_ib_rd =
                    |return_obs_rd_ib_rd_hs_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow];
                dbrr_prep_wr =
                    return_obs_rd_prep_wr_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow];
                dbrr_prep_rd =
                    return_obs_rd_prep_rd_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow];
                dbrr_wr_accept =
                    return_obs_flow_ob_wr_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow] &&
                    return_obs_flow_ob_bp_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow];
                dbrr_event = dbrr_req || dbrr_q_enq || dbrr_q_deq || dbrr_ib_wr ||
                             dbrr_ib_rd || dbrr_prep_wr || dbrr_prep_rd || dbrr_wr_accept;
                if (dbrr_req) return_obs_dbrr_req_accept[dbrr_flow]++;
                if (dbrr_q_enq) return_obs_dbrr_queue_enqueue[dbrr_flow]++;
                if (dbrr_q_deq) return_obs_dbrr_queue_dequeue[dbrr_flow]++;
                if (dbrr_ib_wr) return_obs_dbrr_ib_write[dbrr_flow]++;
                if (dbrr_ib_rd) return_obs_dbrr_ib_read[dbrr_flow]++;
                if (dbrr_prep_wr) return_obs_dbrr_prep_write[dbrr_flow]++;
                if (dbrr_prep_rd) return_obs_dbrr_prep_read[dbrr_flow]++;
                if (dbrr_wr_accept) return_obs_dbrr_wr_accept[dbrr_flow]++;
                if (!return_obs_bp_data_ready_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow]) begin
                    if (return_obs_dbrr_first_ready_low[dbrr_flow] == 0)
                        return_obs_dbrr_first_ready_low[dbrr_flow] = return_obs_db_clock_edge_count;
                    return_obs_dbrr_last_ready_low[dbrr_flow] = return_obs_db_clock_edge_count;
                end
                if (!return_obs_bp_data_vld_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow]) begin
                    if (return_obs_dbrr_first_data_vld_low[dbrr_flow] == 0)
                        return_obs_dbrr_first_data_vld_low[dbrr_flow] = return_obs_db_clock_edge_count;
                    return_obs_dbrr_last_data_vld_low[dbrr_flow] = return_obs_db_clock_edge_count;
                end
                if (return_obs_bp_rd_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow]) begin
                    if (return_obs_dbrr_first_rd_ob_full[dbrr_flow] == 0)
                        return_obs_dbrr_first_rd_ob_full[dbrr_flow] = return_obs_db_clock_edge_count;
                    return_obs_dbrr_last_rd_ob_full[dbrr_flow] = return_obs_db_clock_edge_count;
                end
                if (return_obs_bp_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow]) begin
                    if (return_obs_dbrr_first_wr_ob_full[dbrr_flow] == 0)
                        return_obs_dbrr_first_wr_ob_full[dbrr_flow] = return_obs_db_clock_edge_count;
                    return_obs_dbrr_last_wr_ob_full[dbrr_flow] = return_obs_db_clock_edge_count;
                end
                if (return_obs_bp_barrier_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow]) begin
                    if (return_obs_dbrr_first_barrier[dbrr_flow] == 0)
                        return_obs_dbrr_first_barrier[dbrr_flow] = return_obs_db_clock_edge_count;
                    return_obs_dbrr_last_barrier[dbrr_flow] = return_obs_db_clock_edge_count;
                end
                if (dbrr_event && return_obs_dbrr_emit_count < return_obs_dbrr_limit) begin
                    return_obs_dbrr_emit_count++;
                    $fdisplay(
                        return_obs_fd,
                        "%0t | DBCLK_RD_READY_EVENT_V1 | n=%0d edge=%0d mse=%0d req=%0b q_enq=%0b q_deq=%0b ib_wr=%0b ib_rd=%0b prep_wr=%0b prep_rd=%0b wr_accept=%0b prep_count=%0d spatial=%0d data_vld=%0b data_ready=%0b rd_ob_full=%0b wr_ob_full=%0b barrier=%0b",
                        $time, return_obs_dbrr_emit_count, return_obs_db_clock_edge_count,
                        (dbrr_flow == 0 ? 0 : 3),
                        dbrr_req, dbrr_q_enq, dbrr_q_deq, dbrr_ib_wr, dbrr_ib_rd,
                        dbrr_prep_wr, dbrr_prep_rd, dbrr_wr_accept,
                        return_obs_bp_prepared_count_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow],
                        return_obs_rd_spatial_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow],
                        return_obs_bp_data_vld_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow],
                        return_obs_bp_data_ready_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow],
                        return_obs_bp_rd_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow],
                        return_obs_bp_ob_full_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow],
                        return_obs_bp_barrier_mon[return_obs_group_id][return_obs_local_slice_id][dbrr_flow]
                    );
                end
            end
            if (return_obs_dbrr_emit_count != 0) $fflush(return_obs_fd);
        end
    end

'''


def configure_source() -> Any:
    source_builder.SOURCE_NAME = SOURCE_NAME
    source_builder.INSTALL_NAME = INSTALL_NAME
    source_builder.TEST_ID = TEST_ID
    source_builder.SOURCE_ZIP = SOURCE_ZIP
    source_builder.SOURCE_SHA256 = SOURCE_SHA256
    source_builder.TRIGGER_RETURN_SHA256 = TRIGGER_RETURN_SHA256
    source_builder.TRIGGER_ANALYSIS = TRIGGER_ANALYSIS
    source_builder.configure_source()
    root = source_builder.base.root_builder()
    root.SOURCE_NAME = SOURCE_NAME
    root.INSTALL_NAME = INSTALL_NAME
    root.SOURCE_ZIP = SOURCE_ZIP
    root.SOURCE_SHA256 = SOURCE_SHA256
    return root


def upgrade_observer(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    // v33: MSE0 Buffer_AG_Idx_Queue input/match/FIFO diagnostic.\n",
        DECLARATIONS + "    // v33: MSE0 Buffer_AG_Idx_Queue input/match/FIFO diagnostic.\n",
        "v34 declarations",
    )
    text = replace_once(
        text,
        '        return_obs_bq_enabled =\n'
        '            $test$plusargs("RETURN_OBS_BUFFER_AG_IDX_QUEUE");\n',
        '        return_obs_bq_enabled =\n'
        '            $test$plusargs("RETURN_OBS_BUFFER_AG_IDX_QUEUE");\n'
        '        return_obs_dbrr_enabled =\n'
        '            $test$plusargs("RETURN_OBS_DBCLK_RD_READY");\n',
        "v34 enable",
    )
    text = replace_once(
        text,
        "        return_obs_bq_limit = 256;\n",
        "        return_obs_bq_limit = 256;\n"
        "        return_obs_dbrr_limit = 256;\n",
        "v34 default limit",
    )
    text = replace_once(
        text,
        '                "RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=%d",\n'
        '                return_obs_bq_limit\n'
        '            );\n',
        '                "RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=%d",\n'
        '                return_obs_bq_limit\n'
        '            );\n'
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_DBCLK_RD_READY_LIMIT=%d",\n'
        '                return_obs_dbrr_limit\n'
        '            );\n',
        "v34 limit plusarg",
    )
    text = text.replace(
        "        return_obs_bq_reset();\n",
        "        return_obs_bq_reset();\n        return_obs_dbrr_reset();\n",
    )
    if text.count("return_obs_dbrr_reset();") != 2:
        raise BuildError("v34 reset call count differs")
    text = replace_once(
        text,
        "                    if (return_obs_bq_enabled) begin\n",
        SUMMARY + "                    if (return_obs_bq_enabled) begin\n",
        "v34 summary",
    )
    text = replace_once(
        text,
        "buffer_ag_idx_queue=%0d buffer_ag_idx_queue_limit=%0d",
        "buffer_ag_idx_queue=%0d buffer_ag_idx_queue_limit=%0d "
        "dbclk_rd_ready=%0d dbclk_rd_ready_limit=%0d",
        "v34 time0 format",
    )
    text = replace_once(
        text,
        "                        return_obs_bq_enabled,\n"
        "                        return_obs_bq_limit\n",
        "                        return_obs_bq_enabled,\n"
        "                        return_obs_bq_limit,\n"
        "                        return_obs_dbrr_enabled,\n"
        "                        return_obs_dbrr_limit\n",
        "v34 time0 args",
    )
    text = replace_once(
        text,
        "    // v33 sampler: qualified input accepts and FIFO accepts only.\n",
        SAMPLER + "    // v33 sampler: qualified input accepts and FIFO accepts only.\n",
        "v34 sampler",
    )
    # Correct the v33 queue sampler itself to its owner clock.
    start = text.index("    // v33 sampler: qualified input accepts and FIFO accepts only.\n")
    end = text.index("    // v31 sampler: accepted transactions only; stable levels are state.\n", start)
    block = text[start:end]
    block = replace_once(
        block,
        "always @(posedge u_NDP_Top_new.clk_sg)",
        "always @(posedge u_NDP_Top_new.clk)",
        "v33 corrected owner clock",
    )
    block = block.replace("u_NDP_Top_new.rst_n_sg", "u_NDP_Top_new.rst_n")
    block = block.replace("return_obs_sg_clock_edge_count", "return_obs_db_clock_edge_count")
    text = text[:start] + block + text[end:]
    path.write_text(text, encoding="utf-8", newline="\n")


def upgrade_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "  +RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256\n",
        "  +RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256\n"
        "  +RETURN_OBS_DBCLK_RD_READY\n"
        "  +RETURN_OBS_DBCLK_RD_READY_LIMIT=256\n",
        "runner v34 plusargs",
    )
    text = replace_once(
        text,
        "+RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256 +RETURN_OBS_FILE=",
        "+RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256 "
        "+RETURN_OBS_DBCLK_RD_READY "
        "+RETURN_OBS_DBCLK_RD_READY_LIMIT=256 +RETURN_OBS_FILE=",
        "runner v34 argv receipt",
    )
    marker = (
        "  if [ \"$buffer_ag_idx_queue_ok\" = true ]; then\n"
        "    printf 'buffer_ag_idx_queue_enabled=true\\n"
        "buffer_ag_idx_queue_limit=256\\n"
        "buffer_ag_idx_queue_records_returned=true\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  else\n"
        "    printf 'buffer_ag_idx_queue_enabled=false\\n"
        "buffer_ag_idx_queue_limit=UNKNOWN\\n"
        "buffer_ag_idx_queue_records_returned=false\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  fi\n"
    )
    addition = marker + (
        "  if [ \"$observer_ok\" = true ] && "
        "grep -Fq 'dbclk_rd_ready=1' \"$observer_log\" && "
        "grep -Fq 'dbclk_rd_ready_limit=256' \"$observer_log\" && "
        "grep -Fq 'DBCLK_RD_READY_COUNTS_V1' \"$observer_log\" && "
        "grep -Fq 'DBCLK_RD_READY_STATE_V1' \"$observer_log\" && "
        "grep -Fq 'DBCLK_RD_READY_WITNESS_V1' \"$observer_log\"; then\n"
        "    dbclk_rd_ready_ok=true\n"
        "  else\n"
        "    dbclk_rd_ready_ok=false\n"
        "  fi\n"
        "  if [ \"$dbclk_rd_ready_ok\" = true ]; then\n"
        "    printf 'dbclk_rd_ready_enabled=true\\n"
        "dbclk_rd_ready_limit=256\\n"
        "dbclk_rd_ready_records_returned=true\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  else\n"
        "    printf 'dbclk_rd_ready_enabled=false\\n"
        "dbclk_rd_ready_limit=UNKNOWN\\n"
        "dbclk_rd_ready_records_returned=false\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  fi\n"
    )
    text = replace_once(text, marker, addition, "runner v34 receipt")
    # Runtime-only path guard: package-controlled paths, identity and actual install root.
    insert_after = 'python3 "$runtime" preflight --package-root "$package_root" || exit 5\n'
    guard = insert_after + (
        "mkdir \"$evidence_root\"\n"
        "path_budget_status=\"$(python3 - \"$package_root/TEST_PACKAGE_MANIFEST.json\" \"$package_root\" <<'PY'\n"
        "import json, pathlib, sys\n"
        "m=json.load(open(sys.argv[1], encoding='utf-8'))\n"
        "b=m['path_length_budget']; root=pathlib.Path(sys.argv[2]).resolve()\n"
        "members=[p for p in root.rglob('*') if p.is_file()]\n"
        "suffix=max((len(str(p.relative_to(root)).replace('\\\\\\\\','/')) for p in members), default=0)\n"
        "errors=[]\n"
        "if len(str(root))+1+suffix > b['max_projected_absolute_path_chars']: errors.append('absolute_path_budget')\n"
        "if suffix > b['max_inner_suffix_chars']: errors.append('inner_suffix_budget')\n"
        "print(json.dumps({'valid':not errors,'errors':errors,'actual_root_chars':len(str(root)),'actual_max_suffix_chars':suffix},sort_keys=True))\n"
        "raise SystemExit(0 if not errors else 42)\n"
        "PY\n"
        ")\" || { printf '%s\\n' \"$path_budget_status\" >\"$evidence_root/path_budget_preflight.json\"; exit 42; }\n"
        "printf '%s\\n' \"$path_budget_status\" >\"$evidence_root/path_budget_preflight.json\"\n"
    )
    text = replace_once(text, insert_after, guard, "runtime path guard")
    text = replace_once(
        text,
        'mkdir "$evidence_root"\nmkdir -p "$cfg_root/readback"',
        'mkdir -p "$cfg_root/readback"',
        "remove duplicate evidence mkdir",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def path_budget(package: Path) -> dict[str, Any]:
    relative = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
    ]
    max_suffix = max(map(len, relative))
    max_depth = max(path.count("/") + 1 for path in relative)
    max_component = max(len(component) for path in relative for component in path.split("/"))
    return {
        "rule_id": "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
        "target_extraction_root_chars": 96,
        "max_projected_absolute_path_chars": 240,
        "max_inner_suffix_chars": 128,
        "max_inner_depth": 8,
        "max_component_chars": 48,
        "measured_max_inner_suffix_chars": max_suffix,
        "measured_max_inner_depth": max_depth,
        "measured_max_component_chars": max_component,
        "identity_repeated_in_inner_path": any(INSTALL_NAME in path for path in relative),
        "runtime_guard": "PREPARE_AND_RUN.sh package-local path_budget_preflight.json",
        "abbreviation_map": {
            "tb_probe": "package-local observer source",
            "cfg_pkg": "installed runtime configuration leaf",
        },
    }


def update_manifest(package: Path, source_manifest: dict[str, Any]) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "gap-node0071-dbclk-rdready-diagnostic-package-v36",
            "test_id": TEST_ID,
            "install_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "evidence_ceiling": "E2_LOCAL_ONLY",
            "rule_receipts": {**manifest.get("rule_receipts", {}), **CURRENT_RECEIPTS, "current_match": True},
        }
    )
    manifest["dbclk_rdready_information_gain_contract"] = {
        "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        "trigger_analysis_sha256": sha256(TRIGGER_ANALYSIS),
        "first_divergence_repaired": (
            "package observer Buffer_AG queue accepted-event sampler moved "
            "from clk_sg to the clk_db owner domain"
        ),
        "runtime_enable": "+RETURN_OBS_DBCLK_RD_READY",
        "runtime_limit": "+RETURN_OBS_DBCLK_RD_READY_LIMIT=256",
        "time0_marker": "dbclk_rd_ready=1 dbclk_rd_ready_limit=256",
        "records": [
            "DBCLK_RD_READY_EVENT_V1",
            "DBCLK_RD_READY_COUNTS_V1",
            "DBCLK_RD_READY_STATE_V1",
            "DBCLK_RD_READY_WITNESS_V1",
        ],
        "owner_clock": "u_NDP_Top_new.clk (Slice clk_db)",
        "candidate_observation_matrix": {
            "request_generation_or_acceptance": ["req", "q_enq", "rd_q_full"],
            "memory_return_or_inbuffer_supply": ["ib_wr", "ib_rd", "ib_vld", "ib_sel"],
            "prepared_data_formation": ["prep_wr", "prep_rd", "prep_count", "spatial"],
            "rd_output_backpressure": ["data_vld", "data_ready", "rd_ob_full"],
            "wr_buffer_or_barrier": ["wr_accept", "wr_ob_full", "barrier"],
            "buffer_ag_direct_consumer": ["bq_rd", "bq_empty", "bq_count", "bq_out_valid"],
        },
        "qualified_events_only": True,
        "stable_levels_count_as_progress": False,
        "first_last_blocking_witness": True,
        "read_only": True,
        "drives_dut": False,
        "changes_timeout_or_backpressure": False,
        "causal_slice": {
            "keep": "all eight existing ordered stages and frozen payloads",
            "drop": [],
            "reason": (
                "the first ordered sum_s1 stage is the failing prefix; no legal "
                "external typed checkpoint exists before the observed internal boundary, "
                "so later stage removal cannot reduce time-to-first-divergence"
            ),
            "estimated_stage_reduction": "0/8",
            "estimated_payload_reduction": "0 bytes",
            "estimated_runtime_reduction": "none before first divergence",
        },
        "observer_budget": {
            "qualified_event_record_limit": 256,
            "summary_records": 3,
            "waveform": False,
            "per_cycle_logging": False,
        },
    }
    manifest["buffer_ag_index_pair_diagnostic_contract"].update(
        {
            "clock": "u_NDP_Top_new.clk (Slice clk_db)",
            "qualified_event_counts_evaluable_when_feature_enabled": True,
            "v33_clk_sg_occurrence_evidence_superseded": True,
        }
    )
    features = manifest["diagnostic_feature_runtime_enable_contract"]["features"]
    features = [feature for feature in features if feature["name"] != "dbclk_rd_ready"]
    features.append(
        {
            "name": "dbclk_rd_ready",
            "runtime_enable": "+RETURN_OBS_DBCLK_RD_READY",
            "runtime_limit": "+RETURN_OBS_DBCLK_RD_READY_LIMIT=256",
            "time0_marker": "dbclk_rd_ready=1 dbclk_rd_ready_limit=256",
            "returned_binding_receipt": "evidence/observer_binding.txt",
            "return_target": "runs/return_observer.log",
            "zero_when_disabled": "DISABLED_INSTRUMENTATION_ZERO",
        }
    )
    manifest["diagnostic_feature_runtime_enable_contract"]["features"] = features
    manifest["path_length_budget"] = path_budget(package)
    manifest["applicable_rule_ids"] = sorted(
        set(manifest.get("applicable_rule_ids") or [])
        | {
            "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
            "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
            "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
            "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
            "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001",
            "CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001",
        }
    )
    manifest["generation_provenance"].update(
        {
            "tool": "tools/build_gap_node0071_dbclk_rdready_v34_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
            "trigger_analysis_sha256": sha256(TRIGGER_ANALYSIS),
            "package_side_change": (
                "correct Buffer_AG queue sampler clock and add bounded same-domain "
                "queue/WR/RD information-gain evidence plus runtime path budget guard"
            ),
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "functional_rtl_modified": False,
        }
    )
    manifest["files"] = file_records(package)
    write_json(path, manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    root = configure_source()
    package = root.extract_source(destination)
    source_records = file_records(package, exclude_manifest=False)
    numeric_before = {
        name: record
        for name, record in file_records(package / "workload", exclude_manifest=False).items()
        if name not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    source_manifest = json.loads((package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    root.rewrite_identity(package)
    upgrade_observer(package / OBSERVER)
    upgrade_runner(package / "PREPARE_AND_RUN.sh")
    (package / "README.md").write_text(
        "# GAP node0071 v36 clk_db RD-readiness diagnostic\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. The package preserves "
        "the frozen 73-file numeric/workload/config/golden payload and functional "
        "RTL inputs. It corrects the package-local Buffer_AG queue sampler to its "
        "clk_db owner domain and adds one bounded information-gain matrix across "
        "queue, WR conjunction and RD request/return/prepared-data consumers.\n\n"
        "Run exactly:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest)
    numeric_after = {
        name: record
        for name, record in file_records(package / "workload", exclude_manifest=False).items()
        if name not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if numeric_before != numeric_after or len(numeric_after) != 73:
        raise BuildError("frozen 73-file numeric/workload set drifted")
    final_records = file_records(package, exclude_manifest=False)
    if set(source_records) != set(final_records):
        raise BuildError("package file exact-set changed")
    changed = {name for name in source_records if source_records[name] != final_records[name]}
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path allowlist differs: {sorted(changed)}")
    budget = path_budget(package)
    if (
        budget["measured_max_inner_suffix_chars"] > budget["max_inner_suffix_chars"]
        or budget["measured_max_inner_depth"] > budget["max_inner_depth"]
        or budget["measured_max_component_chars"] > budget["max_component_chars"]
        or budget["identity_repeated_in_inner_path"]
    ):
        raise BuildError(f"path budget failed: {budget}")
    return package, {
        "source_zip_sha256": SOURCE_SHA256,
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
        "frozen_numeric_workload_file_count": 73,
        "frozen_numeric_workload_tree_equal": True,
        "frozen_other_tree_equal": all(
            source_records[name] == final_records[name]
            for name in set(source_records) - ALLOWED_CHANGED
        ),
        "path_length_budget": budget,
    }


def build_zip(output_root: Path) -> dict[str, Any]:
    package, proof = build_directory(output_root)
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="gap-node0071-v34-repeat-") as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeated_zip = Path(temporary) / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeated, repeated_zip, archive_root=INSTALL_NAME)
        if sha256(repeated_zip) != digest:
            raise BuildError("deterministic second ZIP differs")
        if file_records(repeated, exclude_manifest=False) != file_records(package, exclude_manifest=False):
            raise BuildError("deterministic second tree differs")
    sidecar = Path(str(zip_path) + ".sha256")
    sidecar.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    return {
        "schema": "gap-node0071-dbclk-rdready-v36-build-v1",
        "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "test_id": TEST_ID,
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "package": str(package),
        "zip": str(zip_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "sidecar_sha256": sha256(sidecar),
        **proof,
        "repeat_build": {"package_tree_equal": True, "zip_equal": True, "repeat_zip_sha256": digest},
        "numeric_analysis_repeated": False,
        "workload_rebuilt": False,
        "config_semantics_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PACKAGE_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package, zip_path, sidecar, validation):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        result = build_zip(output_root)
        write_json(validation, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as error:
        import traceback

        traceback.print_exc()
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
