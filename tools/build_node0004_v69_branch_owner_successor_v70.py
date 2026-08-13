from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v68_branch_drain_successor_v69 as previous  # noqa: E402

SOURCE = "r5_n4_hw_v69_branch_drain_diag"
INSTALL = "r5_n4_hw_v70_branch_owner_diag"
SOURCE_SHA = "e6c94bf8b38e8e0ff7aed6984782a874a665938930dc5f91357323592c2e88eb"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v69_return_analysis/report.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v69_return_v70_successor/build"
base = previous.base


class BuildError(RuntimeError):
    pass


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"replacement count differs: {old[:100]!r} count={text.count(old)}")
    return text.replace(old, new, 1)


def configure() -> None:
    previous.SOURCE = SOURCE
    previous.INSTALL = INSTALL
    previous.SOURCE_SHA = SOURCE_SHA
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    previous.configure()


def mse(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        ".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
        + leaf
    )


def observer_block() -> str:
    return f'''

    // v70 BRANCH_OWNER_ACTUAL_CONSUMER_BEGIN
    // Qualified token-owner ledger around the v69 post-final-descriptor skew.
    // State snapshots never consume the qualified-event budget.
    bit return_obs_bo_enabled;
    integer return_obs_bo_limit;
    integer return_obs_bo_state_limit;
    integer return_obs_bo_plusarg_status;
    integer return_obs_bo_state_plusarg_status;
    integer return_obs_bo_qualified_records;
    integer return_obs_bo_state_records;
    longint unsigned return_obs_bo_desc;
    longint unsigned return_obs_bo_buf_pop;
    longint unsigned return_obs_bo_buf_req;
    longint unsigned return_obs_bo_buf_ret;
    longint unsigned return_obs_bo_prep_wr;
    longint unsigned return_obs_bo_prep_rd;

    initial begin
        return_obs_bo_enabled = $test$plusargs("RETURN_OBS_BRANCH_OWNER");
        return_obs_bo_limit = 128;
        return_obs_bo_state_limit = 8;
        return_obs_bo_plusarg_status = $value$plusargs(
            "RETURN_OBS_BRANCH_OWNER_LIMIT=%d", return_obs_bo_limit
        );
        return_obs_bo_state_plusarg_status = $value$plusargs(
            "RETURN_OBS_BRANCH_OWNER_STATE_LIMIT=%d", return_obs_bo_state_limit
        );
        return_obs_bo_qualified_records = 0;
        return_obs_bo_state_records = 0;
        return_obs_bo_desc = 0;
        return_obs_bo_buf_pop = 0;
        return_obs_bo_buf_req = 0;
        return_obs_bo_buf_ret = 0;
        return_obs_bo_prep_wr = 0;
        return_obs_bo_prep_rd = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_BRANCH_OWNER enabled=%0d qualified_limit=%0d state_limit=%0d schema=BRANCH_OWNER",
                return_obs_bo_enabled, return_obs_bo_limit,
                return_obs_bo_state_limit);
            $fflush(return_obs_fd);
        end
    end

    task automatic return_obs_write_branch_owner(input string event_name);
        if (return_obs_bo_enabled && return_obs_fd != 0 &&
            return_obs_bo_state_records < return_obs_bo_state_limit) begin
            return_obs_bo_state_records++;
            $fdisplay(return_obs_fd,
                "%0t | BRANCH_OWNER_STATE_V1 | event=%s qualified_records=%0d state_records=%0d desc=%0d buf_pop=%0d buf_req=%0d buf_ret=%0d prep_wr=%0d prep_rd=%0d mem_tag_valid=%0d mem_tag=%h buf_tag_valid=%0d buf_tag=%h buf_ob_last=%0d buf_ob_last_index=%0d buf_last_req=%0d desc_tsf=%0d desc_qempty=%0d desc_qcount=%0d prep_count=%0d prep_wptr=%0d prep_rptr=%0d hold=%0d hold_last=%0d",
                $time, event_name, return_obs_bo_qualified_records,
                return_obs_bo_state_records, return_obs_bo_desc,
                return_obs_bo_buf_pop, return_obs_bo_buf_req,
                return_obs_bo_buf_ret, return_obs_bo_prep_wr,
                return_obs_bo_prep_rd,
                {mse('mse_mem_ag_tag_valid')}, {mse('mse_mem_ag_tag')},
                {mse('mse_buf_ag_tag_valid')}, {mse('mse_buf_ag_tag')},
                {mse('u_RD_Buffer_AG.mse2buf_last')},
                {mse('u_RD_Buffer_AG.mse2buf_last_index')},
                {mse('u_RD_Buffer_AG.buf_ag_last_req_flag')},
                {mse('wr_data_chl_req_tsf_size')},
                {mse('u_WR_Data_Channel.wr_chl_queue_empty')},
                {mse('u_WR_Data_Channel.u_wr_chl_queue.fifo_counter')},
                {mse('u_WR_Data_Channel.wr_data_chl_prepared_data_cnt')},
                {mse('u_WR_Data_Channel.wr_data_chl_prepared_data_cur_base_wptr')},
                {mse('u_WR_Data_Channel.wr_data_chl_prepared_data_cur_base_rptr')},
                {mse('u_WR_Data_Channel.wr_data_chl_hold_data_vld')},
                {mse('u_WR_Data_Channel.wr_data_chl_hold_last_flag')});
            $fflush(return_obs_fd);
        end
    endtask

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit bo_desc, bo_buf_pop, bo_buf_req, bo_buf_ret, bo_prep_wr, bo_prep_rd;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_bo_qualified_records = 0;
            return_obs_bo_state_records = 0;
            return_obs_bo_desc = 0;
            return_obs_bo_buf_pop = 0;
            return_obs_bo_buf_req = 0;
            return_obs_bo_buf_ret = 0;
            return_obs_bo_prep_wr = 0;
            return_obs_bo_prep_rd = 0;
        end else if (return_obs_bo_enabled && return_obs_active) begin
            bo_desc = {mse('wr_data_chl_req_valid')} && {mse('wr_data_chl_req_ready')};
            bo_buf_pop = {mse('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en')} &&
                         !{mse('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty')};
            bo_buf_req = (|{mse('mse2buf_rreq_valid')}) && {mse('buf2mse_rreq_ready')};
            bo_buf_ret = {mse('buf2mse_rvalid')} && {mse('wr_data_chl_ready')};
            bo_prep_wr = {mse('u_WR_Data_Channel.wr_data_chl_prepared_data_wr_hs')};
            bo_prep_rd = {mse('u_WR_Data_Channel.wr_data_chl_prepared_data_rd_hs')};
            if (bo_desc) return_obs_bo_desc++;
            if (bo_buf_pop) return_obs_bo_buf_pop++;
            if (bo_buf_req) return_obs_bo_buf_req++;
            if (bo_buf_ret) return_obs_bo_buf_ret++;
            if (bo_prep_wr) return_obs_bo_prep_wr++;
            if (bo_prep_rd) return_obs_bo_prep_rd++;
            if ((bo_desc || bo_buf_pop || bo_buf_req || bo_buf_ret ||
                 bo_prep_wr || bo_prep_rd) &&
                return_obs_bo_qualified_records < return_obs_bo_limit &&
                return_obs_fd != 0) begin
                return_obs_bo_qualified_records++;
                $fdisplay(return_obs_fd,
                    "%0t | BRANCH_OWNER_EDGE_V1 | qn=%0d desc_ev=%0d buf_pop_ev=%0d buf_req_ev=%0d buf_ret_ev=%0d prep_wr_ev=%0d prep_rd_ev=%0d desc=%0d buf_pop=%0d buf_req=%0d buf_ret=%0d prep_wr=%0d prep_rd=%0d mem_tag_valid=%0d mem_tag=%h buf_tag_valid=%0d buf_tag=%h buf_ob_last=%0d buf_ob_last_index=%0d buf_row=%h buf_col=%h buf_last_req=%0d data_last=%0d desc_tsf=%0d desc_qempty=%0d desc_qcount=%0d desc_qwr=%h desc_qrd=%h prep_count=%0d prep_wptr=%0d prep_rptr=%0d hold=%0d hold_last=%0d",
                    $time, return_obs_bo_qualified_records,
                    bo_desc, bo_buf_pop, bo_buf_req, bo_buf_ret,
                    bo_prep_wr, bo_prep_rd, return_obs_bo_desc,
                    return_obs_bo_buf_pop, return_obs_bo_buf_req,
                    return_obs_bo_buf_ret, return_obs_bo_prep_wr,
                    return_obs_bo_prep_rd,
                    {mse('mse_mem_ag_tag_valid')}, {mse('mse_mem_ag_tag')},
                    {mse('mse_buf_ag_tag_valid')}, {mse('mse_buf_ag_tag')},
                    {mse('u_RD_Buffer_AG.mse2buf_last')},
                    {mse('u_RD_Buffer_AG.mse2buf_last_index')},
                    {mse('u_RD_Buffer_AG.mse2buf_rreq_row_addr')},
                    {mse('u_RD_Buffer_AG.mse2buf_rreq_col_addr')},
                    {mse('u_RD_Buffer_AG.buf_ag_last_req_flag')},
                    {mse('u_WR_Data_Channel.wr_data_chl_last_flag')},
                    {mse('wr_data_chl_req_tsf_size')},
                    {mse('u_WR_Data_Channel.wr_chl_queue_empty')},
                    {mse('u_WR_Data_Channel.u_wr_chl_queue.fifo_counter')},
                    {mse('u_WR_Data_Channel.wr_chl_queue_wr_data')},
                    {mse('u_WR_Data_Channel.wr_chl_queue_rd_data')},
                    {mse('u_WR_Data_Channel.wr_data_chl_prepared_data_cnt')},
                    {mse('u_WR_Data_Channel.wr_data_chl_prepared_data_cur_base_wptr')},
                    {mse('u_WR_Data_Channel.wr_data_chl_prepared_data_cur_base_rptr')},
                    {mse('u_WR_Data_Channel.wr_data_chl_hold_data_vld')},
                    {mse('u_WR_Data_Channel.wr_data_chl_hold_last_flag')});
                $fflush(return_obs_fd);
            end
        end
    end
    // v70 BRANCH_OWNER_ACTUAL_CONSUMER_END
'''


def add_runtime_feature(runtime: str) -> str:
    anchor = '''    {
        "feature": "RETURN_OBS_BRANCH_DRAIN",
        "enable": "+RETURN_OBS_BRANCH_DRAIN",
        "limits": ("+RETURN_OBS_BRANCH_DRAIN_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_BRANCH_DRAIN", "enabled=1", "limit=128",
        ),
    },
)'''
    replacement = anchor[:-2] + '''    {
        "feature": "RETURN_OBS_BRANCH_OWNER",
        "enable": "+RETURN_OBS_BRANCH_OWNER",
        "limits": (
            "+RETURN_OBS_BRANCH_OWNER_LIMIT=128",
            "+RETURN_OBS_BRANCH_OWNER_STATE_LIMIT=8",
        ),
        "marker_tokens": (
            "feature=RETURN_OBS_BRANCH_OWNER", "enabled=1",
            "qualified_limit=128", "state_limit=8",
        ),
    },
)'''
    return once(runtime, anchor, replacement)


def observability_profile() -> dict:
    boundaries = [
        ("runtime_feature_binding", "infrastructure", "compile argv plus time0 feature marker"),
        ("lc18_source_accept", "source_produce", "LC18 valid and all configured consumers ready"),
        ("final_descriptor_accept", "queue_enqueue", "wr_data_chl_req_valid && wr_data_chl_req_ready"),
        ("buffer_tag_dequeue", "queue_dequeue", "buf_ag_idx_queue_rd_en && !buf_ag_idx_queue_empty"),
        ("buffer_read_request_accept", "consumer_request", "|mse2buf_rreq_valid && buf2mse_rreq_ready"),
        ("buffer_read_return_accept", "consumer_accept", "buf2mse_rvalid && wr_data_chl_ready"),
        ("prepared_group_enqueue", "queue_enqueue", "wr_data_chl_prepared_data_wr_hs"),
        ("prepared_descriptor_join", "internal_match_compute", "wr_data_chl_prepared_data_rd_hs"),
        ("natural_terminal", "terminal_propagation", "DUT natural terminal event"),
        ("formal_d_320", "formal_d_collection", "formal D collector exact-set"),
    ]
    return {
        "schema": "server_triggered_causal_observability_profiles_v1",
        "version": 1,
        "bundle_scope": "FRESH_SUCCESSOR_BOUND_PROFILE",
        "policy": {
            "application_scope": "NEXT_FRESH_SUCCESSOR_ONLY",
            "decision_priority": "ONE_ROUND_HYPOTHESIS_DISCRIMINATION_FIRST",
            "preferred_max_slowdown_percent": 50,
            "slowdown_limit_hard": False,
            "over_preferred_action": "REPORT_JUSTIFY_AND_OPTIMIZE_WITHOUT_DROPPING_REQUIRED_BOUNDARIES",
            "default_log_budget_bytes": 16777216,
            "default_active_boundary_budget": 64,
            "default_ring_event_budget": 128,
            "no_per_event_text_io": True,
            "full_wave_dump": False,
            "first_version_auto_terminate": False,
        },
        "profiles": [{
            "profile_id": "conv_serialized_node0004_v70_branch_owner",
            "family": "conv_int32_accumulate_serialized",
            "maturity": "BOUND_CALIBRATION_PENDING",
            "release_eligible": False,
            "current_package": {"path": f"pending/{SOURCE}.zip", "sha256": SOURCE_SHA,
                                "disposition": "READ_ONLY_NOT_MODIFIED"},
            "runtime_behavior": {"read_only": True, "drives_dut": False, "changes_input": False,
                                 "changes_ready_backpressure": False, "changes_timing": False,
                                 "changes_timeout": False, "host_internal_tensor_replay": False,
                                 "stage_gating": True},
            "performance_budget": {"decision_priority": "ONE_ROUND_HYPOTHESIS_DISCRIMINATION_FIRST",
                                   "preferred_max_slowdown_percent": 50, "slowdown_limit_hard": False,
                                   "calibration_status": "PENDING_FRESH_BOUND_PROFILE",
                                   "calibration_method": "SAME_EVENT_TRACE_AB_WALLCLOCK"},
            "storage": {"per_event_text_io": False, "full_wave_dump": False,
                        "max_log_bytes": 16777216, "ring_events": 128,
                        "diagnostic_budget_separation": {
                            "accounting_mode": "SEPARATE_QUALIFIED_AND_NON_PROGRESS",
                            "qualified_event_budget": 128, "non_progress_state_budget": 8,
                            "state_activity_consumes_qualified_budget": False,
                            "state_overflow_policy": "COALESCE_OR_DROP_STATE_ONLY",
                            "late_qualified_event_policy": "REMAINS_ELIGIBLE_AFTER_STATE_BUDGET_EXHAUSTION"},
                        "flush_policy": "TIME0_TRIGGER_STAGE_TRANSITION_EXIT_FINAL_ONLY"},
            "no_progress": {"qualified_progress_only": True, "qualified_measured_rate_required": True,
                            "auto_terminate": False, "on_trigger": "SNAPSHOT_AND_CONTINUE_EXISTING_TIMEOUT"},
            "boundaries": [{"boundary_id": i, "role": r, "stage_gate": "c0 active",
                            "owner_clock_binding": "EXACT_FINAL_SOURCE_REQUIRED",
                            "qualification": q, "direct_consumer_binding": "EXACT_FINAL_SOURCE_REQUIRED",
                            "records": ["count", "first_time", "last_time", "outstanding", "last_tag"]}
                           for i, r, q in boundaries],
            "hypotheses": [
                {"hypothesis_id": "H_CONFIG_SCHEDULE_EXCESS", "classification": "DYNAMIC_FLOW_CONTROL_STALL",
                 "distinguished_by": ["final_descriptor_accept", "buffer_tag_dequeue"],
                 "decision": "buffer last/index advances beyond final descriptor last/index"},
                {"hypothesis_id": "H_DESCRIPTOR_TAG_MISMATCH", "classification": "TERMINAL_PROPAGATION_FAILURE",
                 "distinguished_by": ["final_descriptor_accept", "buffer_read_request_accept"],
                 "decision": "corresponding terminal tags differ before any replay"},
                {"hypothesis_id": "H_DESCRIPTOR_UNAWARE_PREFETCH", "classification": "DYNAMIC_FLOW_CONTROL_STALL",
                 "distinguished_by": ["buffer_read_request_accept", "prepared_group_enqueue"],
                 "decision": "new buffer request accepted after descriptor owner retired"},
                {"hypothesis_id": "H_STALE_RETURN_REPLAY", "classification": "DYNAMIC_FLOW_CONTROL_STALL",
                 "distinguished_by": ["buffer_read_return_accept", "prepared_group_enqueue"],
                 "decision": "prepared enqueue duplicates a request tag/pointer without new request"},
            ],
            "triggers": [
                {"trigger_id": "FIRST_QUEUE_FULL", "condition": "prepared count reaches 32",
                 "snapshot_boundaries": ["prepared_group_enqueue", "prepared_descriptor_join"], "one_shot": True},
                {"trigger_id": "FIRST_BRANCH_DIVERGENCE", "condition": "prepared count exceeds descriptor count",
                 "snapshot_boundaries": ["final_descriptor_accept", "prepared_group_enqueue"], "one_shot": True},
                {"trigger_id": "NO_PROGRESS_WINDOW", "condition": "four qualified zero-delta windows",
                 "snapshot_boundaries": ["buffer_read_request_accept", "prepared_descriptor_join"], "one_shot": False},
                {"trigger_id": "TERMINAL_GAP", "condition": "descriptor terminal without natural terminal",
                 "snapshot_boundaries": ["final_descriptor_accept", "natural_terminal"], "one_shot": True},
                {"trigger_id": "STAGE_TRANSITION", "condition": "c0 stage transition",
                 "snapshot_boundaries": ["natural_terminal"], "one_shot": False},
                {"trigger_id": "EXIT_OR_SIGNAL", "condition": "normal exit or caught signal",
                 "snapshot_boundaries": ["prepared_descriptor_join", "formal_d_320"], "one_shot": False},
            ],
            "canonical_classifications": ["TEST_INFRASTRUCTURE_FAILURE", "SIM_NOT_STARTED",
                "TARGET_STAGE_NOT_REACHED", "DYNAMIC_FLOW_CONTROL_STALL", "TERMINAL_PROPAGATION_FAILURE",
                "RESULT_COLLECTION_FAILURE", "NUMERIC_MISMATCH", "NATURAL_SUCCESS", "EVIDENCE_INCOMPLETE"],
            "claim_boundary": "Read-only qualified token-owner localization; does not prove DUT correctness or authorize config/RTL changes."
        }],
        "claim_boundary": "Fresh v70 diagnostic profile only; source v69 remains read-only and numeric/config/RTL are frozen."
    }


def build_directory(output: Path) -> Path:
    configure()
    with tempfile.TemporaryDirectory(prefix="node0004-v70-source-") as td:
        source = base.extract_source(Path(td))
        package = output / INSTALL
        if package.exists():
            raise BuildError(f"refusing to overwrite {package}")
        shutil.copytree(source, package)
    base.replace_identity(package)

    op = package / "tb_probe/native_return_observer.svh"
    observer = op.read_text(encoding="utf-8")
    observer = once(observer, '                return_obs_write_branch_drain("DIAG_DECISION");',
                    '                return_obs_write_branch_drain("DIAG_DECISION");\n                return_obs_write_branch_owner("DIAG_DECISION");')
    observer = once(observer, '                return_obs_write_branch_drain(event_name);',
                    '                return_obs_write_branch_drain(event_name);\n                return_obs_write_branch_owner(event_name);')
    observer = observer.rstrip() + observer_block() + "\n"
    op.write_text(observer, encoding="utf-8", newline="\n")

    rp = package / "PREPARE_AND_RUN.sh"
    runner = rp.read_text(encoding="utf-8")
    anchor = " +RETURN_OBS_BRANCH_DRAIN +RETURN_OBS_BRANCH_DRAIN_LIMIT=128"
    if runner.count(anchor) != 2:
        raise BuildError("v69 branch-drain runner binding count differs")
    addition = " +RETURN_OBS_BRANCH_OWNER +RETURN_OBS_BRANCH_OWNER_LIMIT=128 +RETURN_OBS_BRANCH_OWNER_STATE_LIMIT=8"
    runner = runner.replace(anchor, anchor + addition)
    rp.write_text(runner, encoding="utf-8", newline="\n")

    runtime_path = package / "package_tools/node0004_hang_localization_runtime.py"
    runtime_path.write_text(add_runtime_feature(runtime_path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    profile_path = package / "provenance/server_triggered_causal_observability_v70.json"
    base.write_json(profile_path, observability_profile())

    manifest_path = package / "package_manifest.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_sha, new_sha = old["observer_sha256"], base.sha256(op)
    manifest = base.replace_hash(old, old_sha, new_sha)
    manifest.setdefault("diagnostic_features", {})["RETURN_OBS_BRANCH_OWNER"] = {
        "runtime_enable_parameter": "+RETURN_OBS_BRANCH_OWNER",
        "limit_parameters": ["+RETURN_OBS_BRANCH_OWNER_LIMIT=128", "+RETURN_OBS_BRANCH_OWNER_STATE_LIMIT=8"],
        "edge_schema": "BRANCH_OWNER_EDGE_V1", "state_schema": "BRANCH_OWNER_STATE_V1",
        "owner_clock": "u_NDP_Top_new.clk_db", "owner_reset": "u_NDP_Top_new.rst_n_db",
        "qualified_event_budget": 128, "non_progress_state_budget": 8,
        "state_activity_consumes_qualified_budget": False,
        "causal_scope": ["descriptor accept/tag/size", "Buffer_AG tag/last/index request",
                         "read return and prepared write pointers", "descriptor/prepared join"],
        "candidate_matrix": {
            "configured_buffer_schedule_exceeds_descriptor_schedule": "buffer last/index advances beyond descriptor terminal",
            "descriptor_terminal_tag_mismatch": "corresponding descriptor and buffer terminal tags differ",
            "descriptor_unaware_prefetch": "new read request after descriptor owner retires",
            "buffer_return_replay_or_stale_lifetime": "duplicate return/prepared pointer without new request",
        },
    }
    manifest.update({
        "install_name": INSTALL, "source_package_sha256": SOURCE_SHA,
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "observer_sha256": new_sha, "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False, "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False, "configuration_rebuilt": False,
        "configuration_rebuilt_in_this_successor": False, "mapping_rebuilt": False,
        "bitstream_rebuilt": False, "execplan_rebuilt": False,
        "sca_semantics_rebuilt": False, "functional_rtl_modified": False,
        "server_action": False,
    })
    base.write_json(package / "provenance/v69_to_v70_branch_owner.json", {
        "schema": "node0004-v69-to-v70-branch-owner-v1", "source_v69_sha256": SOURCE_SHA,
        "v69_return_sha256": "ac7ccf08989db2b7afebaa1937ce7b337acfb16e94fffa39878bcf6b86f36ddb",
        "analysis_sha256": base.sha256(ANALYSIS),
        "last_proven_good": "FINAL_18TH_DESCRIPTOR_AND_18TH_PREPARED_GROUP_JOIN_AND_DRAIN",
        "first_divergence": "BUFFER_BRANCH_ACCEPTS_PREPARED_GROUP_19_AFTER_DESCRIPTOR_COUNT_STOPS_AT_18",
        "changed_surface": ["fresh identity", "qualified BRANCH_OWNER token ledger", "runtime feature binding"],
        "frozen": ["numeric/W3/qparams/tail/workload/config/golden", "timeout/backpressure",
                   "functional RTL/ISA/hardware/active ndp-sim"],
    })
    base.refresh_receipts(manifest)
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    base.update_path_budget(package)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    a = ap.parse_args()
    out = a.output_root.resolve(); out.mkdir(parents=True, exist_ok=True)
    package = build_directory(out)
    archive = out / f"{INSTALL}.zip"; base.deterministic_zip(package, archive)
    digest = base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix="node0004-v70-repeat-") as td:
        repeat = build_directory(Path(td)); rz = Path(td) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, rz); deterministic = base.sha256(rz) == digest
    if not deterministic:
        raise BuildError("deterministic rebuild differs")
    sidecar = out / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    report = {"schema": "node0004-v69-to-v70-branch-owner-build-v1",
              "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
              "zip": str(archive), "zip_bytes": archive.stat().st_size, "zip_sha256": digest,
              "sidecar": str(sidecar), "deterministic_rebuild_equal": deterministic,
              "source_v69_sha256": SOURCE_SHA, "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
              "numeric_analysis_repeated": False, "node0004_workload_rebuilt": False,
              "configuration_rebuilt": False, "functional_rtl_modified": False, "server_action": False}
    base.write_json(out / f"{INSTALL}.build.json", report)
    print(json.dumps(report, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
