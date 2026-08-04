// Package-local, read-only progress observer for the frozen Conv node0004
// native-four-lane performance candidate.  This include never drives DUT/TB
// functional state and never controls simulation termination.

logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
    n4_obs_cfg_start_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
    n4_obs_cfg_finish_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
    n4_obs_exec_start_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
    n4_obs_slice_finish_mon;

generate
    for (genvar n4_obs_group = 0;
         n4_obs_group < `SLICE_GROUP_SIZE;
         n4_obs_group++) begin : N4_OBS_GROUP_GEN
        for (genvar n4_obs_slice = 0;
             n4_obs_slice < `SLICE_GROUP_NUM;
             n4_obs_slice++) begin : N4_OBS_SLICE_GEN
            assign n4_obs_cfg_start_mon[n4_obs_group][n4_obs_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4_obs_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4_obs_slice]
                    .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager
                    .sem2scm_cfg_start;
            assign n4_obs_cfg_finish_mon[n4_obs_group][n4_obs_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4_obs_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4_obs_slice]
                    .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager
                    .scm2sem_cfg_finish;
            assign n4_obs_exec_start_mon[n4_obs_group][n4_obs_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4_obs_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4_obs_slice]
                    .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager
                    .sem2iga_exec_start;
            assign n4_obs_slice_finish_mon[n4_obs_group][n4_obs_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4_obs_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4_obs_slice]
                    .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager
                    .slice_cmpt_finish;
        end
    end
endgenerate

bit n4_obs_enabled;
bit n4_obs_active;
bit n4_obs_cfg_start_d;
bit n4_obs_cfg_finish_d;
bit n4_obs_exec_start_d;
bit n4_obs_slice_finish_d;
integer n4_obs_fd;
integer n4_obs_slice_id;
integer n4_obs_group_id;
integer n4_obs_local_slice_id;
integer n4_obs_heartbeat_cycles;
integer n4_obs_stall_window_cycles;
integer n4_obs_expected_stages;
integer n4_obs_plusarg_status;
integer n4_obs_silent_windows;
string n4_obs_output_path;
longint unsigned n4_obs_cycles;
longint unsigned n4_obs_window_start_cycle;
longint unsigned n4_obs_window_start_total;
longint unsigned n4_obs_delta;
longint unsigned n4_obs_raw_sample_count;
longint unsigned n4_obs_cfg_start_count;
longint unsigned n4_obs_cfg_finish_count;
longint unsigned n4_obs_exec_start_count;
longint unsigned n4_obs_slice_finish_count;
longint unsigned n4_obs_req_accept_count;
longint unsigned n4_obs_rdata_accept_count;
longint unsigned n4_obs_wdata_accept_count;
longint unsigned n4_obs_bank_accept_count;
longint unsigned n4_obs_qualified_total;

function automatic void n4_obs_emit_canonical(
    input string decision,
    input string reason,
    input string boundary
);
    if (n4_obs_fd != 0) begin
        $fdisplay(
            n4_obs_fd,
            "N4PERF_CANONICAL_DECISION_V1 schema=conv-native4-progress-v1 decision=%s reason=%s boundary=%s sample_start=%0d sample_end=%0d delta=%0d qualified_total=%0d raw_samples=%0d cfg_start=%0d cfg_finish=%0d exec_start=%0d finish=%0d req_accept=%0d rdata_accept=%0d wdata_accept=%0d bank_accept=%0d expected_stages=%0d active=%0d silent_windows=%0d",
            decision,
            reason,
            boundary,
            n4_obs_window_start_cycle,
            n4_obs_cycles,
            n4_obs_delta,
            n4_obs_qualified_total,
            n4_obs_raw_sample_count,
            n4_obs_cfg_start_count,
            n4_obs_cfg_finish_count,
            n4_obs_exec_start_count,
            n4_obs_slice_finish_count,
            n4_obs_req_accept_count,
            n4_obs_rdata_accept_count,
            n4_obs_wdata_accept_count,
            n4_obs_bank_accept_count,
            n4_obs_expected_stages,
            n4_obs_active,
            n4_obs_silent_windows
        );
        $fflush(n4_obs_fd);
    end
endfunction

initial begin
    n4_obs_enabled = $test$plusargs("RETURN_OBSERVER");
    n4_obs_slice_id = 0;
    n4_obs_heartbeat_cycles = 262144;
    n4_obs_stall_window_cycles = 1048576;
    n4_obs_expected_stages = 1;
    n4_obs_output_path = "return_observer.log";
    n4_obs_plusarg_status =
        $value$plusargs("RETURN_OBS_SLICE=%d", n4_obs_slice_id);
    n4_obs_plusarg_status =
        $value$plusargs(
            "RETURN_OBS_HEARTBEAT_CYCLES=%d",
            n4_obs_heartbeat_cycles
        );
    n4_obs_plusarg_status =
        $value$plusargs(
            "RETURN_OBS_STALL_CYCLES=%d",
            n4_obs_stall_window_cycles
        );
    n4_obs_plusarg_status =
        $value$plusargs(
            "RETURN_OBS_EXPECTED_STAGES=%d",
            n4_obs_expected_stages
        );
    n4_obs_plusarg_status =
        $value$plusargs("RETURN_OBS_FILE=%s", n4_obs_output_path);
    n4_obs_fd = 0;
    n4_obs_active = 1'b0;
    n4_obs_cfg_start_d = 1'b0;
    n4_obs_cfg_finish_d = 1'b0;
    n4_obs_exec_start_d = 1'b0;
    n4_obs_slice_finish_d = 1'b0;
    n4_obs_silent_windows = 0;
    n4_obs_cycles = 0;
    n4_obs_window_start_cycle = 0;
    n4_obs_window_start_total = 0;
    n4_obs_delta = 0;
    n4_obs_raw_sample_count = 0;
    n4_obs_cfg_start_count = 0;
    n4_obs_cfg_finish_count = 0;
    n4_obs_exec_start_count = 0;
    n4_obs_slice_finish_count = 0;
    n4_obs_req_accept_count = 0;
    n4_obs_rdata_accept_count = 0;
    n4_obs_wdata_accept_count = 0;
    n4_obs_bank_accept_count = 0;
    n4_obs_qualified_total = 0;
    if (n4_obs_enabled) begin
        if (
            n4_obs_slice_id < 0 ||
            n4_obs_slice_id >=
                (`SLICE_GROUP_SIZE * `SLICE_GROUP_NUM) ||
            n4_obs_heartbeat_cycles <= 0 ||
            n4_obs_stall_window_cycles <= 0 ||
            n4_obs_expected_stages <= 0
        ) begin
            $error("N4PERF observer plusarg contract is invalid");
            n4_obs_enabled = 1'b0;
        end
        else begin
            n4_obs_group_id = n4_obs_slice_id / `SLICE_GROUP_NUM;
            n4_obs_local_slice_id =
                n4_obs_slice_id % `SLICE_GROUP_NUM;
            n4_obs_fd = $fopen(n4_obs_output_path, "w");
            if (n4_obs_fd == 0) begin
                $error("N4PERF observer output cannot be created");
                n4_obs_enabled = 1'b0;
            end
            else begin
                $fdisplay(
                    n4_obs_fd,
                    "# Conv native four-lane progress observer v1"
                );
                $fdisplay(
                    n4_obs_fd,
                    "N4PERF_FEATURE_ENABLE_V1 feature=NATIVE4_PROGRESS enabled=1 heartbeat_cycles=%0d stall_window_cycles=%0d expected_stages=%0d",
                    n4_obs_heartbeat_cycles,
                    n4_obs_stall_window_cycles,
                    n4_obs_expected_stages
                );
                $fflush(n4_obs_fd);
                $display(
                    "[RETURN_OBSERVER] enabled N4PERF_FEATURE_ENABLE_V1 feature=NATIVE4_PROGRESS enabled=1 heartbeat_cycles=%0d stall_window_cycles=%0d expected_stages=%0d",
                    n4_obs_heartbeat_cycles,
                    n4_obs_stall_window_cycles,
                    n4_obs_expected_stages
                );
            end
        end
    end
end

always @(posedge u_NDP_Top_new.clk_db or
         negedge u_NDP_Top_new.rst_n_db) begin
    if (!u_NDP_Top_new.rst_n_db) begin
        n4_obs_active = 1'b0;
        n4_obs_cfg_start_d = 1'b0;
        n4_obs_cfg_finish_d = 1'b0;
        n4_obs_exec_start_d = 1'b0;
        n4_obs_slice_finish_d = 1'b0;
        n4_obs_silent_windows = 0;
        n4_obs_cycles = 0;
        n4_obs_window_start_cycle = 0;
        n4_obs_window_start_total = 0;
        n4_obs_delta = 0;
        n4_obs_raw_sample_count = 0;
        n4_obs_cfg_start_count = 0;
        n4_obs_cfg_finish_count = 0;
        n4_obs_exec_start_count = 0;
        n4_obs_slice_finish_count = 0;
        n4_obs_req_accept_count = 0;
        n4_obs_rdata_accept_count = 0;
        n4_obs_wdata_accept_count = 0;
        n4_obs_bank_accept_count = 0;
        n4_obs_qualified_total = 0;
    end
    else if (n4_obs_enabled) begin
        n4_obs_cycles++;
        n4_obs_raw_sample_count++;
        if (
            n4_obs_cfg_start_mon
                [n4_obs_group_id][n4_obs_local_slice_id] &&
            !n4_obs_cfg_start_d
        ) begin
            n4_obs_cfg_start_count++;
            n4_obs_qualified_total++;
        end
        if (
            n4_obs_cfg_finish_mon
                [n4_obs_group_id][n4_obs_local_slice_id] &&
            !n4_obs_cfg_finish_d
        ) begin
            n4_obs_cfg_finish_count++;
            n4_obs_qualified_total++;
        end
        if (
            n4_obs_exec_start_mon
                [n4_obs_group_id][n4_obs_local_slice_id] &&
            !n4_obs_exec_start_d
        ) begin
            n4_obs_exec_start_count++;
            n4_obs_qualified_total++;
            n4_obs_active = 1'b1;
        end
        if (
            n4_obs_slice_finish_mon
                [n4_obs_group_id][n4_obs_local_slice_id] &&
            !n4_obs_slice_finish_d
        ) begin
            n4_obs_slice_finish_count++;
            n4_obs_qualified_total++;
            if (
                n4_obs_slice_finish_count >=
                n4_obs_expected_stages
            ) begin
                n4_obs_active = 1'b0;
            end
        end
        for (
            int n4_obs_mse = 0;
            n4_obs_mse < `MEMORY_STREAM_ENGINE_NUM;
            n4_obs_mse++
        ) begin
            for (
                int n4_obs_req = 0;
                n4_obs_req < `MSE_REQ_CHL_NUM;
                n4_obs_req++
            ) begin
                if (
                    local_req_hs
                        [n4_obs_group_id][n4_obs_local_slice_id]
                        [n4_obs_mse][n4_obs_req]
                ) begin
                    n4_obs_req_accept_count++;
                    n4_obs_qualified_total++;
                end
                if (
                    local_rdata_hs
                        [n4_obs_group_id][n4_obs_local_slice_id]
                        [n4_obs_mse][n4_obs_req]
                ) begin
                    n4_obs_rdata_accept_count++;
                    n4_obs_qualified_total++;
                end
                if (
                    local_wdata_hs
                        [n4_obs_group_id][n4_obs_local_slice_id]
                        [n4_obs_mse][n4_obs_req]
                ) begin
                    n4_obs_wdata_accept_count++;
                    n4_obs_qualified_total++;
                end
            end
        end
        for (
            int n4_obs_bank = 0;
            n4_obs_bank < `BANK_NUM_PER_SLICE;
            n4_obs_bank++
        ) begin
            if (
                bank_frame_hs
                    [n4_obs_group_id][n4_obs_local_slice_id][n4_obs_bank]
            ) begin
                n4_obs_bank_accept_count++;
                n4_obs_qualified_total++;
            end
        end
        if (
            n4_obs_active &&
            (n4_obs_cycles % n4_obs_stall_window_cycles) == 0
        ) begin
            n4_obs_delta =
                n4_obs_qualified_total - n4_obs_window_start_total;
            if (n4_obs_delta > 0) begin
                n4_obs_silent_windows = 0;
                n4_obs_emit_canonical(
                    "STILL_PROGRESSING",
                    "qualified_delta_nonzero",
                    "exec_to_slice_finish"
                );
            end
            else begin
                n4_obs_silent_windows++;
                n4_obs_emit_canonical(
                    "LONG_RUNNING_HANG_AT_EXEC_TO_SLICE_FINISH",
                    "qualified_delta_zero",
                    "exec_to_slice_finish"
                );
            end
            n4_obs_window_start_cycle = n4_obs_cycles;
            n4_obs_window_start_total = n4_obs_qualified_total;
        end
        else if (
            n4_obs_active &&
            (n4_obs_cycles % n4_obs_heartbeat_cycles) == 0
        ) begin
            n4_obs_delta =
                n4_obs_qualified_total - n4_obs_window_start_total;
            n4_obs_emit_canonical(
                "HEARTBEAT",
                "qualified_snapshot",
                "exec_to_slice_finish"
            );
        end
        n4_obs_cfg_start_d =
            n4_obs_cfg_start_mon
                [n4_obs_group_id][n4_obs_local_slice_id];
        n4_obs_cfg_finish_d =
            n4_obs_cfg_finish_mon
                [n4_obs_group_id][n4_obs_local_slice_id];
        n4_obs_exec_start_d =
            n4_obs_exec_start_mon
                [n4_obs_group_id][n4_obs_local_slice_id];
        n4_obs_slice_finish_d =
            n4_obs_slice_finish_mon
                [n4_obs_group_id][n4_obs_local_slice_id];
    end
end

final begin
    if (n4_obs_fd != 0) begin
        n4_obs_delta =
            n4_obs_qualified_total - n4_obs_window_start_total;
        if (
            n4_obs_exec_start_count ==
                n4_obs_expected_stages &&
            n4_obs_slice_finish_count ==
                n4_obs_expected_stages
        ) begin
            n4_obs_emit_canonical(
                "EXPECTED_STAGE_PREFIX_COMPLETE",
                "ordered_exec_and_finish_counts_match",
                "slice_finish"
            );
        end
        else begin
            n4_obs_emit_canonical(
                "INCOMPLETE_AT_SIMULATOR_END",
                "ordered_exec_and_finish_counts_differ",
                "exec_to_slice_finish"
            );
        end
        $fclose(n4_obs_fd);
    end
end
