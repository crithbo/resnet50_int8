// node0004 c0 qualified-progress/canonical-decision localization extension.
//
// External request/read-data/write-data counters are qualified handshakes.
// Buffer4/5 monitors are persistent levels in the active RTL, so their raw
// per-cycle sample counters are diagnostic state only.  This extension keeps
// separate rising-edge witnesses for boundary localization and excludes all
// Buffer4/5 level samples from the monotonic end-to-end progress predicate.

    bit return_hang_diag_enabled;
    bit return_hang_diag_buf4_wr_d;
    bit return_hang_diag_buf4_rd_d;
    bit return_hang_diag_buf5_wr_d;
    bit return_hang_diag_buf5_rd_d;
    longint unsigned return_hang_diag_buf4_wr_edge_count;
    longint unsigned return_hang_diag_buf4_rd_edge_count;
    longint unsigned return_hang_diag_buf5_wr_edge_count;
    longint unsigned return_hang_diag_buf5_rd_edge_count;
    int unsigned return_hang_diag_sample_cycles;
    int unsigned return_hang_diag_stall_windows;
    int unsigned return_hang_diag_max_cycles;
    int unsigned return_hang_diag_windows_without_progress;
    int unsigned return_hang_diag_consecutive_progress_windows;
    longint unsigned return_hang_diag_previous_progress;
    longint unsigned return_hang_diag_current_progress;
    longint unsigned return_hang_diag_sample_index;
    integer return_hang_diag_plusarg_status;

    task automatic return_hang_diag_emit_decision(input string reason);
        string boundary;
        string decision;
        longint unsigned read_req_total;
        longint unsigned read_data_total;
        begin
            read_req_total =
                return_obs_req_count[0] +
                return_obs_req_count[1] +
                return_obs_req_count[3];
            read_data_total =
                return_obs_rdata_count[0] +
                return_obs_rdata_count[1] +
                return_obs_rdata_count[3];
            if (read_req_total == 0) begin
                boundary = "LC_TO_READ_REQUEST";
            end
            else if (read_data_total == 0) begin
                boundary = "READ_REQUEST_TO_MEMORY_DATA";
            end
            else if (return_hang_diag_buf4_rd_edge_count == 0) begin
                boundary = "READ_DATA_TO_BUFFER4_READ_WITNESS";
            end
            else if (return_hang_diag_buf5_wr_edge_count == 0) begin
                boundary = "BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS";
            end
            else if (return_hang_diag_buf5_rd_edge_count == 0) begin
                boundary = "BUFFER5_WRITE_WITNESS_TO_BUFFER5_READ_WITNESS";
            end
            else if (return_obs_req_count[4] == 0) begin
                boundary = "BUFFER5_READ_WITNESS_TO_D_WRITE_REQUEST";
            end
            else if (return_obs_wdata_count[4] == 0) begin
                boundary = "D_WRITE_REQUEST_TO_D_WRITE_DATA";
            end
            else begin
                boundary = "D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH";
            end
            if (reason == "STALL_WINDOW_EXCEEDED") begin
                decision = {"LONG_RUNNING_HANG_AT_", boundary};
            end
            else if (
                reason == "MAX_DIAGNOSTIC_CYCLE_BUDGET_PROGRESSING"
            ) begin
                decision = "STILL_PROGRESSING";
            end
            else begin
                decision = "EVIDENCE_INSUFFICIENT";
            end
            if (return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | CANONICAL_DIAG_DECISION_V1 | schema=node0004_hang_diag version=1 decision=%s reason=%s boundary=%s stage=c0 start_comp=1 completed_stages=0 active_cycles=%0d window_first=1 window_last=%0d window_cycles=%0d no_progress_windows=%0d consecutive_progress_windows=%0d qualified_progress=%0d qualified_delta=%0d req0=%0d req1=%0d req3=%0d rdata0=%0d rdata1=%0d rdata3=%0d d_req=%0d d_wdata=%0d content_digest=QIOV1_%0d_%0d_%0d buf4_wr_edge=%0d buf4_rd_edge=%0d buf5_wr_edge=%0d buf5_rd_edge=%0d buf4_wr_raw=%0d buf4_rd_raw=%0d buf5_wr_raw=%0d buf5_rd_raw=%0d slice_finish=%0b",
                    $time,
                    decision,
                    reason,
                    boundary,
                    return_obs_active_cycles,
                    return_hang_diag_sample_index,
                    return_hang_diag_sample_cycles,
                    return_hang_diag_windows_without_progress,
                    return_hang_diag_consecutive_progress_windows,
                    return_hang_diag_current_progress,
                    return_hang_diag_current_progress -
                        return_hang_diag_previous_progress,
                    return_obs_req_count[0],
                    return_obs_req_count[1],
                    return_obs_req_count[3],
                    return_obs_rdata_count[0],
                    return_obs_rdata_count[1],
                    return_obs_rdata_count[3],
                    return_obs_req_count[4],
                    return_obs_wdata_count[4],
                    return_hang_diag_current_progress,
                    return_hang_diag_current_progress -
                        return_hang_diag_previous_progress,
                    return_hang_diag_sample_index,
                    return_hang_diag_buf4_wr_edge_count,
                    return_hang_diag_buf4_rd_edge_count,
                    return_hang_diag_buf5_wr_edge_count,
                    return_hang_diag_buf5_rd_edge_count,
                    return_obs_buf45_wr_count[0],
                    return_obs_buf45_rd_count[0],
                    return_obs_buf45_wr_count[1],
                    return_obs_buf45_rd_count[1],
                    return_obs_slice_finish_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                );
                return_obs_write_internal_state("DIAG_DECISION");
                return_obs_write_summary("DIAG_SUMMARY");
                $fflush(return_obs_fd);
            end
        end
    endtask

    initial begin
        return_hang_diag_enabled = $test$plusargs("RETURN_HANG_DIAG");
        return_hang_diag_sample_cycles = 262144;
        return_hang_diag_stall_windows = 4;
        return_hang_diag_max_cycles = 8388608;
        return_hang_diag_windows_without_progress = 0;
        return_hang_diag_consecutive_progress_windows = 0;
        return_hang_diag_previous_progress = 0;
        return_hang_diag_current_progress = 0;
        return_hang_diag_sample_index = 0;
        return_hang_diag_plusarg_status = $value$plusargs(
            "RETURN_HANG_DIAG_SAMPLE_CYCLES=%d",
            return_hang_diag_sample_cycles
        );
        return_hang_diag_plusarg_status = $value$plusargs(
            "RETURN_HANG_DIAG_STALL_WINDOWS=%d",
            return_hang_diag_stall_windows
        );
        return_hang_diag_plusarg_status = $value$plusargs(
            "RETURN_HANG_DIAG_MAX_CYCLES=%d",
            return_hang_diag_max_cycles
        );
        if (
            return_hang_diag_enabled &&
            (
                return_hang_diag_sample_cycles == 0 ||
                return_hang_diag_stall_windows < 2 ||
                return_hang_diag_max_cycles == 0
            )
        ) begin
            $fatal(1, "RETURN_HANG_DIAG invalid bounded-progress plusargs");
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        if (!u_NDP_Top_new.rst_n_db) begin
            return_hang_diag_buf4_wr_d = 0;
            return_hang_diag_buf4_rd_d = 0;
            return_hang_diag_buf5_wr_d = 0;
            return_hang_diag_buf5_rd_d = 0;
            return_hang_diag_buf4_wr_edge_count = 0;
            return_hang_diag_buf4_rd_edge_count = 0;
            return_hang_diag_buf5_wr_edge_count = 0;
            return_hang_diag_buf5_rd_edge_count = 0;
            return_hang_diag_windows_without_progress = 0;
            return_hang_diag_consecutive_progress_windows = 0;
            return_hang_diag_previous_progress = 0;
            return_hang_diag_current_progress = 0;
            return_hang_diag_sample_index = 0;
        end
        else if (
            return_hang_diag_enabled &&
            return_obs_enabled &&
            return_obs_active
        ) begin
            if ((|return_obs_buf45_wr_en_mon
                [return_obs_group_id][return_obs_local_slice_id][0]) &&
                !return_hang_diag_buf4_wr_d)
                return_hang_diag_buf4_wr_edge_count++;
            if ((|return_obs_buf45_rd_en_mon
                [return_obs_group_id][return_obs_local_slice_id][0]) &&
                !return_hang_diag_buf4_rd_d)
                return_hang_diag_buf4_rd_edge_count++;
            if ((|return_obs_buf45_wr_en_mon
                [return_obs_group_id][return_obs_local_slice_id][1]) &&
                !return_hang_diag_buf5_wr_d)
                return_hang_diag_buf5_wr_edge_count++;
            if ((|return_obs_buf45_rd_en_mon
                [return_obs_group_id][return_obs_local_slice_id][1]) &&
                !return_hang_diag_buf5_rd_d)
                return_hang_diag_buf5_rd_edge_count++;
            return_hang_diag_buf4_wr_d =
                |return_obs_buf45_wr_en_mon
                    [return_obs_group_id][return_obs_local_slice_id][0];
            return_hang_diag_buf4_rd_d =
                |return_obs_buf45_rd_en_mon
                    [return_obs_group_id][return_obs_local_slice_id][0];
            return_hang_diag_buf5_wr_d =
                |return_obs_buf45_wr_en_mon
                    [return_obs_group_id][return_obs_local_slice_id][1];
            return_hang_diag_buf5_rd_d =
                |return_obs_buf45_rd_en_mon
                    [return_obs_group_id][return_obs_local_slice_id][1];

            return_hang_diag_current_progress =
                return_obs_req_count[0] +
                return_obs_req_count[1] +
                return_obs_req_count[3] +
                return_obs_rdata_count[0] +
                return_obs_rdata_count[1] +
                return_obs_rdata_count[3] +
                return_obs_req_count[4] +
                return_obs_wdata_count[4];

            if (
                (return_obs_active_cycles %
                    return_hang_diag_sample_cycles) == 0
            ) begin
                return_hang_diag_sample_index++;
                if (
                    return_hang_diag_current_progress >
                    return_hang_diag_previous_progress
                ) begin
                    return_hang_diag_windows_without_progress = 0;
                    return_hang_diag_consecutive_progress_windows++;
                end
                else begin
                    return_hang_diag_windows_without_progress++;
                    return_hang_diag_consecutive_progress_windows = 0;
                end
                if (return_obs_fd != 0) begin
                    $fdisplay(
                        return_obs_fd,
                        "%0t | PROGRESS_WINDOW | stage=c0 start_comp=1 completed_stages=0 sample=%0d qualified_progress=%0d delta=%0d no_progress_windows=%0d consecutive_progress_windows=%0d req0=%0d req1=%0d req3=%0d rdata0=%0d rdata1=%0d rdata3=%0d buf4_wr_edge=%0d buf4_rd_edge=%0d buf5_wr_edge=%0d buf5_rd_edge=%0d buf4_wr_raw=%0d buf4_rd_raw=%0d buf5_wr_raw=%0d buf5_rd_raw=%0d d_req=%0d d_wdata=%0d",
                        $time,
                        return_hang_diag_sample_index,
                        return_hang_diag_current_progress,
                        return_hang_diag_current_progress -
                            return_hang_diag_previous_progress,
                        return_hang_diag_windows_without_progress,
                        return_hang_diag_consecutive_progress_windows,
                        return_obs_req_count[0],
                        return_obs_req_count[1],
                        return_obs_req_count[3],
                        return_obs_rdata_count[0],
                        return_obs_rdata_count[1],
                        return_obs_rdata_count[3],
                        return_hang_diag_buf4_wr_edge_count,
                        return_hang_diag_buf4_rd_edge_count,
                        return_hang_diag_buf5_wr_edge_count,
                        return_hang_diag_buf5_rd_edge_count,
                        return_obs_buf45_wr_count[0],
                        return_obs_buf45_rd_count[0],
                        return_obs_buf45_wr_count[1],
                        return_obs_buf45_rd_count[1],
                        return_obs_req_count[4],
                        return_obs_wdata_count[4]
                    );
                    $fflush(return_obs_fd);
                end
                return_hang_diag_previous_progress =
                    return_hang_diag_current_progress;
                if (
                    return_hang_diag_windows_without_progress >=
                    return_hang_diag_stall_windows
                ) begin
                    return_hang_diag_emit_decision("STALL_WINDOW_EXCEEDED");
                    $fatal(
                        1,
                        "RETURN_HANG_DIAG stopped after bounded no-progress window"
                    );
                end
            end

            if (return_obs_active_cycles >= return_hang_diag_max_cycles) begin
                if (return_hang_diag_consecutive_progress_windows >= 2)
                    return_hang_diag_emit_decision(
                        "MAX_DIAGNOSTIC_CYCLE_BUDGET_PROGRESSING"
                    );
                else
                    return_hang_diag_emit_decision(
                        "MAX_DIAGNOSTIC_CYCLE_BUDGET_INSUFFICIENT_PROGRESS"
                    );
                $fatal(1, "RETURN_HANG_DIAG bounded cycle budget reached");
            end
        end
    end
