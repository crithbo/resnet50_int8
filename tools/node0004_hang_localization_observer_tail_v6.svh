// node0004 c0 long-run progress localization extension.
//
// This code is appended to the already source-bound, read-only native return
// observer in the diagnostic package.  It observes qualified handshakes only;
// it never drives DUT ready/valid, data, clocks, resets, or configuration.

    bit return_hang_diag_enabled;
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
            else if (return_obs_buf45_rd_count[0] == 0) begin
                boundary = "READ_DATA_TO_SA_INPUT_C";
            end
            else if (return_obs_buf45_wr_count[1] == 0) begin
                boundary = "SA_INPUT_MATCH_TO_SA_OUTPUT_BUFFER5";
            end
            else if (return_obs_buf45_rd_count[1] == 0) begin
                boundary = "BUFFER5_WRITE_TO_BUFFER5_READ";
            end
            else if (return_obs_req_count[4] == 0) begin
                boundary = "BUFFER5_READ_TO_D_WRITE_REQUEST";
            end
            else if (return_obs_wdata_count[4] == 0) begin
                boundary = "D_WRITE_REQUEST_TO_D_WRITE_DATA";
            end
            else begin
                boundary = "D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH";
            end
            if (return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | DIAG_DECISION | reason=%s boundary=%s stage=c0 start_comp=1 completed_stages=0 active_cycles=%0d sample=%0d no_progress_windows=%0d consecutive_progress_windows=%0d req0=%0d req1=%0d req3=%0d rdata0=%0d rdata1=%0d rdata3=%0d buf4_wr=%0d buf4_rd=%0d buf5_wr=%0d buf5_rd=%0d d_req=%0d d_wdata=%0d slice_finish=%0b",
                    $time,
                    reason,
                    boundary,
                    return_obs_active_cycles,
                    return_hang_diag_sample_index,
                    return_hang_diag_windows_without_progress,
                    return_hang_diag_consecutive_progress_windows,
                    return_obs_req_count[0],
                    return_obs_req_count[1],
                    return_obs_req_count[3],
                    return_obs_rdata_count[0],
                    return_obs_rdata_count[1],
                    return_obs_rdata_count[3],
                    return_obs_buf45_wr_count[0],
                    return_obs_buf45_rd_count[0],
                    return_obs_buf45_wr_count[1],
                    return_obs_buf45_rd_count[1],
                    return_obs_req_count[4],
                    return_obs_wdata_count[4],
                    return_obs_slice_finish_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                );
                return_obs_write_internal_state("DIAG_DECISION");
                return_obs_write_summary("DIAG_DECISION");
                $fflush(return_obs_fd);
            end
        end
    endtask

    initial begin
        return_hang_diag_enabled =
            $test$plusargs("RETURN_HANG_DIAG");
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
            return_hang_diag_current_progress =
                return_obs_req_count[0] +
                return_obs_req_count[1] +
                return_obs_req_count[3] +
                return_obs_rdata_count[0] +
                return_obs_rdata_count[1] +
                return_obs_rdata_count[3] +
                return_obs_buf45_wr_count[0] +
                return_obs_buf45_rd_count[0] +
                return_obs_buf45_wr_count[1] +
                return_obs_buf45_rd_count[1] +
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
                        "%0t | PROGRESS_WINDOW | stage=c0 start_comp=1 completed_stages=0 sample=%0d progress=%0d delta=%0d no_progress_windows=%0d consecutive_progress_windows=%0d req0=%0d req1=%0d req3=%0d rdata0=%0d rdata1=%0d rdata3=%0d buf4_rd=%0d buf5_wr=%0d buf5_rd=%0d d_req=%0d d_wdata=%0d",
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
                    return_hang_diag_emit_decision(
                        "STALL_WINDOW_EXCEEDED"
                    );
                    $fatal(
                        1,
                        "RETURN_HANG_DIAG stopped after bounded no-progress window"
                    );
                end
            end

            if (
                return_obs_active_cycles >=
                return_hang_diag_max_cycles
            ) begin
                if (
                    return_hang_diag_consecutive_progress_windows >= 2
                ) begin
                    return_hang_diag_emit_decision(
                        "MAX_DIAGNOSTIC_CYCLE_BUDGET_PROGRESSING"
                    );
                end
                else begin
                    return_hang_diag_emit_decision(
                        "MAX_DIAGNOSTIC_CYCLE_BUDGET_INSUFFICIENT_PROGRESS"
                    );
                end
                $fatal(
                    1,
                    "RETURN_HANG_DIAG bounded cycle budget reached"
                );
            end
        end
    end
