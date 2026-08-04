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

from tools.build_gap_node0071_complete_server_package import (
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import file_records
from tools import build_gap_node0071_ga_mse4_final_pair_v28_package as base


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v28_ga_mse4_final_pair_diag"
INSTALL_NAME = "r5_n71_gap_v29_mse0_buffer_prep_group0_diag"
TEST_ID = "r5-gap-node0071-v29-mse0-buffer-prepared-group0-diagnostic"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = "7b34ef0b592ebfd86d3e75a0983a91c8d87271454139e609174cdce8afc7d422"
TRIGGER_RETURN_SHA256 = "875a9ec0ade4f1957025e0b7cefb0e843830f6dca57db8c078d462c5df40b0ff"
TRIGGER_ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-node0071-v28-return-analysis/report.json"
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


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"marker differs: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


def configure_source() -> None:
    base.SOURCE_NAME = SOURCE_NAME
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.configure_source()


DECLARATIONS = r'''    // v29: bounded MSE0 Buffer0-to-prepared-to-GA-group0 diagnostic.
    bit return_obs_m0path_enabled;
    int return_obs_m0path_limit;
    int return_obs_m0path_emit_count;
    longint unsigned return_obs_m0path_buf_accept_count;
    longint unsigned return_obs_m0path_arm_accept_count;
    longint unsigned return_obs_m0path_arm_clear_count;
    longint unsigned return_obs_m0path_prep_wr_count;
    longint unsigned return_obs_m0path_prep_rd_count;
    longint unsigned return_obs_m0path_data_vld_count;
    longint unsigned return_obs_m0path_group0_accept_count;
    longint unsigned return_obs_m0path_last_buf_accept;
    longint unsigned return_obs_m0path_last_arm_accept;
    longint unsigned return_obs_m0path_last_arm_clear;
    longint unsigned return_obs_m0path_last_prep_wr;
    longint unsigned return_obs_m0path_last_prep_rd;
    longint unsigned return_obs_m0path_last_data_vld;
    longint unsigned return_obs_m0path_last_group0_accept;

    task automatic return_obs_m0path_reset;
        begin
            return_obs_m0path_emit_count = 0;
            return_obs_m0path_buf_accept_count = 0;
            return_obs_m0path_arm_accept_count = 0;
            return_obs_m0path_arm_clear_count = 0;
            return_obs_m0path_prep_wr_count = 0;
            return_obs_m0path_prep_rd_count = 0;
            return_obs_m0path_data_vld_count = 0;
            return_obs_m0path_group0_accept_count = 0;
            return_obs_m0path_last_buf_accept = 0;
            return_obs_m0path_last_arm_accept = 0;
            return_obs_m0path_last_arm_clear = 0;
            return_obs_m0path_last_prep_wr = 0;
            return_obs_m0path_last_prep_rd = 0;
            return_obs_m0path_last_data_vld = 0;
            return_obs_m0path_last_group0_accept = 0;
        end
    endtask

'''


SUMMARY = r'''                    if (return_obs_m0path_enabled) begin
                        $fdisplay(
                            return_obs_fd,
                            "%0t | MSE0_BUFFER_PREP_GROUP0_COUNTS_V1 | event=%s buf_accept=%0d arm_accept=%0d arm_clear=%0d prep_wr=%0d prep_rd=%0d data_vld=%0d group0_accept=%0d records=%0d limit=%0d",
                            $time, event_name,
                            return_obs_m0path_buf_accept_count,
                            return_obs_m0path_arm_accept_count,
                            return_obs_m0path_arm_clear_count,
                            return_obs_m0path_prep_wr_count,
                            return_obs_m0path_prep_rd_count,
                            return_obs_m0path_data_vld_count,
                            return_obs_m0path_group0_accept_count,
                            return_obs_m0path_emit_count,
                            return_obs_m0path_limit
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | MSE0_BUFFER_PREP_GROUP0_STATE_V1 | event=%s buf_vld=0x%0h arm_req=0x%0h arm_ready=%0b arm_rw=%0b arm_clear=0x%0h arm_addr=0x%0h arm_count=%0d/%0d rd_q_empty=%0b ib_vld=0x%0h ib_sel=%0b prep_wr=%0b prep_rd=%0b prep_count=%0d data_vld=%0b buf_rtag=0x%0h buf_bp=%0b group0_tag=0x%0h group0_bp=%0b",
                            $time, event_name,
                            return_obs_flow_buf_valid_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_flow_arm_req_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_flow_arm_ready_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_flow_arm_rw_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_flow_arm_clear_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_flow_arm_counter0_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_flow_arm_counter1_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_rd_queue_empty_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_rd_ib_vld_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_rd_ib_sel_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_rd_prep_wr_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_rd_prep_rd_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_rd_prep_count_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_rd_data_vld_path_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_buf_to_ga_rtag_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_buf_to_ga_bp_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_ga_group_out_tag_mon[return_obs_group_id][return_obs_local_slice_id][0],
                            return_obs_ga_group_bp_post_mon[return_obs_group_id][return_obs_local_slice_id][0]
                        );
                        $fdisplay(
                            return_obs_fd,
                            "%0t | MSE0_BUFFER_PREP_GROUP0_WITNESS_V1 | event=%s last_buf_accept=%0d last_arm_accept=%0d last_arm_clear=%0d last_prep_wr=%0d last_prep_rd=%0d last_data_vld=%0d last_group0_accept=%0d",
                            $time, event_name,
                            return_obs_m0path_last_buf_accept,
                            return_obs_m0path_last_arm_accept,
                            return_obs_m0path_last_arm_clear,
                            return_obs_m0path_last_prep_wr,
                            return_obs_m0path_last_prep_rd,
                            return_obs_m0path_last_data_vld,
                            return_obs_m0path_last_group0_accept
                        );
                    end
'''


SAMPLER = r'''    // v29 qualified edge/event sampler; stable levels are state only.
    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (
            u_NDP_Top_new.rst_n_sg &&
            return_obs_enabled &&
            return_obs_m0path_enabled &&
            return_obs_active &&
            return_obs_fd != 0
        ) begin
            bit m0_buf_accept;
            bit m0_arm_accept;
            bit m0_arm_clear;
            bit m0_prep_wr;
            bit m0_prep_rd;
            bit m0_data_vld;
            bit m0_group0_accept;
            bit m0_any_event;
            m0_buf_accept =
                return_obs_mse0_buf_hs_mon[return_obs_group_id][return_obs_local_slice_id];
            m0_arm_accept =
                (|return_obs_flow_arm_req_mon[return_obs_group_id][return_obs_local_slice_id][0]) &&
                !return_obs_flow_arm_rw_mon[return_obs_group_id][return_obs_local_slice_id][0] &&
                return_obs_flow_arm_ready_mon[return_obs_group_id][return_obs_local_slice_id][0];
            m0_arm_clear =
                |return_obs_flow_arm_clear_mon[return_obs_group_id][return_obs_local_slice_id][0];
            m0_prep_wr =
                return_obs_rd_prep_wr_mon[return_obs_group_id][return_obs_local_slice_id][0];
            m0_prep_rd =
                return_obs_rd_prep_rd_mon[return_obs_group_id][return_obs_local_slice_id][0];
            m0_data_vld =
                return_obs_rd_data_vld_path_mon[return_obs_group_id][return_obs_local_slice_id][0];
            m0_group0_accept =
                (|return_obs_ga_group_out_tag_mon[return_obs_group_id][return_obs_local_slice_id][0][0]) &&
                return_obs_ga_group_bp_post_mon[return_obs_group_id][return_obs_local_slice_id][0];
            m0_any_event = m0_buf_accept || m0_arm_accept || m0_arm_clear ||
                m0_prep_wr || m0_prep_rd || m0_data_vld || m0_group0_accept;
            if (m0_buf_accept) begin
                return_obs_m0path_buf_accept_count++;
                return_obs_m0path_last_buf_accept = return_obs_sg_clock_edge_count;
            end
            if (m0_arm_accept) begin
                return_obs_m0path_arm_accept_count++;
                return_obs_m0path_last_arm_accept = return_obs_sg_clock_edge_count;
            end
            if (m0_arm_clear) begin
                return_obs_m0path_arm_clear_count++;
                return_obs_m0path_last_arm_clear = return_obs_sg_clock_edge_count;
            end
            if (m0_prep_wr) begin
                return_obs_m0path_prep_wr_count++;
                return_obs_m0path_last_prep_wr = return_obs_sg_clock_edge_count;
            end
            if (m0_prep_rd) begin
                return_obs_m0path_prep_rd_count++;
                return_obs_m0path_last_prep_rd = return_obs_sg_clock_edge_count;
            end
            if (m0_data_vld) begin
                return_obs_m0path_data_vld_count++;
                return_obs_m0path_last_data_vld = return_obs_sg_clock_edge_count;
            end
            if (m0_group0_accept) begin
                return_obs_m0path_group0_accept_count++;
                return_obs_m0path_last_group0_accept = return_obs_sg_clock_edge_count;
            end
            if (m0_any_event && return_obs_m0path_emit_count < return_obs_m0path_limit) begin
                return_obs_m0path_emit_count++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | MSE0_BUFFER_PREP_GROUP0_EVENT_V1 | n=%0d sg_edge=%0d buf_accept=%0b arm_accept=%0b arm_clear=%0b prep_wr=%0b prep_rd=%0b data_vld=%0b group0_accept=%0b buf_vld=0x%0h arm_req=0x%0h arm_ready=%0b arm_rw=%0b arm_addr=0x%0h arm_count=%0d/%0d ib_vld=0x%0h ib_sel=%0b prep_count=%0d buf_rtag=0x%0h group0_tag=0x%0h",
                    $time, return_obs_m0path_emit_count,
                    return_obs_sg_clock_edge_count,
                    m0_buf_accept, m0_arm_accept, m0_arm_clear,
                    m0_prep_wr, m0_prep_rd, m0_data_vld, m0_group0_accept,
                    return_obs_flow_buf_valid_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_flow_arm_req_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_flow_arm_ready_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_flow_arm_rw_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_flow_arm_addr_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_flow_arm_counter0_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_flow_arm_counter1_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_rd_ib_vld_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_rd_ib_sel_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_rd_prep_count_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_buf_to_ga_rtag_mon[return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_ga_group_out_tag_mon[return_obs_group_id][return_obs_local_slice_id][0]
                );
            end
            $fflush(return_obs_fd);
        end
    end

'''


def upgrade_observer(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text, "    bit return_obs_enabled;\n",
        DECLARATIONS + "    bit return_obs_enabled;\n", "v29 declarations",
    )
    text = replace_once(
        text,
        '        return_obs_pair_enabled =\n'
        '            $test$plusargs("RETURN_OBS_GA_MSE4_FINAL_PAIR");\n',
        '        return_obs_pair_enabled =\n'
        '            $test$plusargs("RETURN_OBS_GA_MSE4_FINAL_PAIR");\n'
        '        return_obs_m0path_enabled =\n'
        '            $test$plusargs("RETURN_OBS_MSE0_BUFFER_PREP_GROUP0");\n',
        "v29 plusarg",
    )
    text = replace_once(
        text, "        return_obs_pair_limit = 512;\n",
        "        return_obs_pair_limit = 512;\n"
        "        return_obs_m0path_limit = 512;\n", "v29 default limit",
    )
    text = replace_once(
        text,
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_FILE=%s",\n',
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=%d",\n'
        '                return_obs_m0path_limit\n'
        '            );\n'
        '        return_obs_plusarg_status =\n'
        '            $value$plusargs(\n'
        '                "RETURN_OBS_FILE=%s",\n',
        "v29 limit plusarg",
    )
    text = text.replace(
        "        return_obs_pair_reset();\n",
        "        return_obs_pair_reset();\n"
        "        return_obs_m0path_reset();\n",
    )
    if text.count("return_obs_m0path_reset();") != 2:
        raise BuildError("v29 reset call count differs")
    text = replace_once(
        text,
        "                    if (return_obs_pair_enabled) begin\n",
        SUMMARY + "                    if (return_obs_pair_enabled) begin\n",
        "v29 summary",
    )
    text = replace_once(
        text,
        "ga_mse4_final_pair=%0d ga_mse4_final_pair_limit=%0d",
        "ga_mse4_final_pair=%0d ga_mse4_final_pair_limit=%0d "
        "mse0_buffer_prep_group0=%0d mse0_buffer_prep_group0_limit=%0d",
        "v29 time0 format",
    )
    text = replace_once(
        text,
        "                        return_obs_pair_enabled,\n"
        "                        return_obs_pair_limit\n",
        "                        return_obs_pair_enabled,\n"
        "                        return_obs_pair_limit,\n"
        "                        return_obs_m0path_enabled,\n"
        "                        return_obs_m0path_limit\n",
        "v29 time0 args",
    )
    text = replace_once(
        text, "    final begin\n", SAMPLER + "    final begin\n", "v29 sampler",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def upgrade_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "  +RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512\n",
        "  +RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512\n"
        "  +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0\n"
        "  +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512\n",
        "runner v29 plusargs",
    )
    text = replace_once(
        text,
        "+RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512 +RETURN_OBS_FILE=",
        "+RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512 "
        "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0 "
        "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512 +RETURN_OBS_FILE=",
        "runner v29 command receipt",
    )
    marker = (
        "  if [ \"$ga_mse4_pair_ok\" = true ]; then\n"
        "    printf 'ga_mse4_final_pair_enabled=true\\n"
        "ga_mse4_final_pair_limit=512\\n"
        "ga_mse4_final_pair_records_returned=true\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  else\n"
        "    printf 'ga_mse4_final_pair_enabled=false\\n"
        "ga_mse4_final_pair_limit=UNKNOWN\\n"
        "ga_mse4_final_pair_records_returned=false\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  fi\n"
    )
    addition = marker + (
        "  if [ \"$observer_ok\" = true ] && "
        "grep -Fq 'mse0_buffer_prep_group0=1' \"$observer_log\" && "
        "grep -Fq 'mse0_buffer_prep_group0_limit=512' \"$observer_log\" && "
        "grep -Fq 'MSE0_BUFFER_PREP_GROUP0_COUNTS_V1' \"$observer_log\" && "
        "grep -Fq 'MSE0_BUFFER_PREP_GROUP0_STATE_V1' \"$observer_log\" && "
        "grep -Fq 'MSE0_BUFFER_PREP_GROUP0_WITNESS_V1' \"$observer_log\"; then\n"
        "    mse0_path_ok=true\n"
        "  else\n"
        "    mse0_path_ok=false\n"
        "  fi\n"
        "  if [ \"$mse0_path_ok\" = true ]; then\n"
        "    printf 'mse0_buffer_prep_group0_enabled=true\\n"
        "mse0_buffer_prep_group0_limit=512\\n"
        "mse0_buffer_prep_group0_records_returned=true\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  else\n"
        "    printf 'mse0_buffer_prep_group0_enabled=false\\n"
        "mse0_buffer_prep_group0_limit=UNKNOWN\\n"
        "mse0_buffer_prep_group0_records_returned=false\\n' "
        '>>"$evidence_root/observer_binding.txt"\n'
        "  fi\n"
    )
    text = replace_once(text, marker, addition, "runner v29 receipt")
    path.write_text(text, encoding="utf-8", newline="\n")


def current_receipts(source_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    receipts = []
    for item in source_manifest["final_zip_rule_self_audit_contract"]["read_receipt"]:
        receipt = dict(item)
        receipt["sha256"] = sha256(ROOT / receipt["path"])
        receipt["current_match"] = True
        receipts.append(receipt)
    return receipts


def update_manifest(package: Path, source_manifest: dict[str, Any]) -> None:
    manifest = base.base.base.base.replace_identity(source_manifest)
    receipts = current_receipts(source_manifest)
    manifest.update(
        {
            "schema": "gap-node0071-mse0-buffer-prepared-group0-diagnostic-package-v29",
            "test_id": TEST_ID,
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "read-only MSE0 Buffer0 accepted row through ARM read, RD "
                "prepared data and GA group0 qualified capture"
            ),
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "source_numeric_payload_reused_without_rebuild": True,
            "functional_fix": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
        }
    )
    audit = manifest["final_zip_rule_self_audit_contract"]
    audit["read_receipt"] = receipts
    audit["all_current_match"] = True
    audit["plan_sha256_mutable_provenance_only"] = sha256(ROOT / ".agents/plan.md")
    audit["final_zip_rule_self_audit_pass"] = "PENDING_EXTERNAL_RELEASE_REPORT"
    rule_map = {item["path"]: item["sha256"] for item in receipts}
    manifest["rule_receipts"]["server_rule_sha256"] = sha256(
        ROOT / ".agents/rules/服务器测试包生成规则.md"
    )
    manifest["rule_receipts"]["generation_index_sha256"] = sha256(
        ROOT / ".agents/rules/生成前必读索引.md"
    )
    manifest["rule_receipts"]["current_match"] = True
    manifest["rule_receipts"]["plan_sha256_mutable_provenance_only"] = sha256(
        ROOT / ".agents/plan.md"
    )
    manifest["post_generation_rule_drift"] = {
        "content_neutral": False,
        "current_server_rule_sha256": sha256(
            ROOT / ".agents/rules/服务器测试包生成规则.md"
        ),
        "resolution": "fresh v29 exact final bytes bind current rules",
    }
    manifest["mse0_buffer_prepared_group0_diagnostic_contract"] = {
        "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        "trigger_analysis_sha256": sha256(TRIGGER_ANALYSIS),
        "last_proven_good": (
            "MSE0/MSE3 each reach buffer accept 13 times; all 48 GA accepts "
            "retire and MSE4 consumes all 12 available write-data transactions"
        ),
        "first_divergence": (
            "MSE0_BUFFER_ACCEPT_13_TO_PREPARED_WRITE_8_TO_"
            "GA_GROUP0_CAPTURE_6_VERSUS_MSE3_13_TO_13_TO_8"
        ),
        "runtime_enable": "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0",
        "runtime_limit": "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512",
        "time0_marker": (
            "mse0_buffer_prep_group0=1 "
            "mse0_buffer_prep_group0_limit=512"
        ),
        "records": [
            "MSE0_BUFFER_PREP_GROUP0_EVENT_V1",
            "MSE0_BUFFER_PREP_GROUP0_COUNTS_V1",
            "MSE0_BUFFER_PREP_GROUP0_STATE_V1",
            "MSE0_BUFFER_PREP_GROUP0_WITNESS_V1",
        ],
        "clock": "clk_sg",
        "qualified_events": [
            "MSE0 producer-to-Buffer0 accept",
            "Buffer0 ARM read request and ready accept",
            "Buffer0 ARM clear",
            "MSE0 RD prepared-data write/read handshake",
            "MSE0 RD data_vld",
            "GA group0 valid-tag and bp_post accept",
        ],
        "state_only": [
            "stable valid/ready/full/empty level",
            "stable address/count/tag level",
        ],
        "stable_level_counts_as_progress": False,
        "read_only": True,
        "drives_dut": False,
        "changes_timeout": False,
        "reuses_existing_package_local_xmr_taps": True,
        "hdl_positive_control_scope": (
            "v29 declarations/reset/update/use leaves and result-critical "
            "MSE0 event record; inherited XMR taps remain v28-proven"
        ),
    }
    feature = manifest["diagnostic_feature_runtime_enable_contract"]
    feature["features"] = list(feature.get("features", [])) + [
        {
            "name": "mse0_buffer_prep_group0",
            "runtime_enable": "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0",
            "runtime_limit": "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512",
            "time0_marker": (
                "mse0_buffer_prep_group0=1 "
                "mse0_buffer_prep_group0_limit=512"
            ),
            "returned_binding_receipt": "evidence/observer_binding.txt",
            "return_target": "runs/return_observer.log",
            "zero_when_disabled": "DISABLED_INSTRUMENTATION_ZERO",
        }
    ]
    manifest["generation_provenance"].update(
        {
            "tool": "tools/build_gap_node0071_mse0_buffer_prep_group0_v29_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "fresh identity plus bounded read-only MSE0 Buffer0/ARM/"
                "prepared-data/GA-group0 correlation observer"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    package = base.base.base.base.extract_source(destination)
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    source_records = file_records(package, exclude_manifest=False)
    numeric_before = {
        path: record
        for path, record in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    base.base.base.base.rewrite_identity(package)
    upgrade_observer(package / OBSERVER)
    upgrade_runner(package / "PREPARE_AND_RUN.sh")
    (package / "README.md").write_text(
        "# GAP node0071 v29 MSE0 Buffer-to-prepared-to-GA diagnostic\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves "
        "the frozen 73 numeric/workload files, config, golden, execplan and "
        "functional RTL. It adds bounded read-only qualified correlation "
        "across MSE0 Buffer0, ARM read, prepared data and GA group0 capture.\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest)
    numeric_after = {
        path: record
        for path, record in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if numeric_before != numeric_after or len(numeric_after) != 73:
        raise BuildError("frozen 73-file numeric/workload tree drifted")
    final_records = file_records(package, exclude_manifest=False)
    if set(source_records) != set(final_records):
        raise BuildError("package relative file set changed")
    changed = {
        path for path in source_records if source_records[path] != final_records[path]
    }
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path set differs: {sorted(changed)}")
    frozen = sorted(set(source_records) - ALLOWED_CHANGED)
    return package, {
        "source_v28_zip_sha256": SOURCE_SHA256,
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
        "frozen_numeric_workload_file_count": len(numeric_after),
        "frozen_numeric_workload_tree_equal": True,
        "frozen_other_file_count": len(frozen),
        "frozen_other_tree_equal": all(
            source_records[path] == final_records[path] for path in frozen
        ),
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    digest = sha256(zip_path)
    tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(prefix="gap-node0071-v29-repeat-") as temp:
        repeated, _ = build_directory(Path(temp))
        repeated_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeated, repeated_zip, archive_root=INSTALL_NAME)
        if sha256(repeated_zip) != digest:
            raise BuildError("repeat ZIP differs")
        if file_records(repeated, exclude_manifest=False) != tree:
            raise BuildError("repeat package tree differs")
    return {"package_tree_equal": True, "zip_equal": True, "repeat_zip_sha256": digest}


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
        package, proof = build_directory(output_root)
        repeated = repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
        )
        result = {
            "schema": "gap-node0071-mse0-buffer-prep-group0-v29-build-v1",
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
            "repeat_build": repeated,
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        }
        write_json(validation, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
