// Read-only, rate-limited node0075 progress observer for package-local use.
// This file is included inside tb_NDP_Top_new_phy and never drives DUT state.

    logic n75_obs_cfg_start;
    logic n75_obs_cfg_finish;
    logic n75_obs_exec_start;
    logic n75_obs_slice_finish;
    logic [`MSE_REQ_CHL_NUM-1:0] n75_obs_a_request_hs;
    logic [`MSE_REQ_CHL_NUM-1:0] n75_obs_a_data_hs;
    logic n75_obs_d_write_hs;

    assign n75_obs_cfg_start =
        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
            .u_slice_with_datahub_mc_group.slice_group_gen[0]
            .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager.sem2scm_cfg_start;
    assign n75_obs_cfg_finish =
        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
            .u_slice_with_datahub_mc_group.slice_group_gen[0]
            .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager.scm2sem_cfg_finish;
    assign n75_obs_exec_start =
        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
            .u_slice_with_datahub_mc_group.slice_group_gen[0]
            .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager.sem2iga_exec_start;
    assign n75_obs_slice_finish =
        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
            .u_slice_with_datahub_mc_group.slice_group_gen[0]
            .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager.slice_cmpt_finish;
    assign n75_obs_a_request_hs =
        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
            .u_slice_with_datahub_mc_group.slice_group_gen[0]
            .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
            .MSE_INST[1].RD_MSE.u_Memory_RD_Stream_Engine
            .u_RD_Memory_AG.mem_ag_ob_chl_hs;
    assign n75_obs_a_data_hs =
        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
            .u_slice_with_datahub_mc_group.slice_group_gen[0]
            .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
            .MSE_INST[1].RD_MSE.u_Memory_RD_Stream_Engine
            .u_RD_Data_Channel.rd_chl_ib_rd_hs;
    assign n75_obs_d_write_hs =
        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
            .u_slice_with_datahub_mc_group.slice_group_gen[0]
            .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
            .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_ag_tag_valid &
        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
            .u_slice_with_datahub_mc_group.slice_group_gen[0]
            .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
            .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_ag_bp_pre;

    bit n75_obs_enabled;
    bit n75_obs_active;
    bit n75_obs_stall_reported;
    integer n75_obs_fd;
    integer n75_obs_stall_cycles;
    integer n75_obs_heartbeat_cycles;
    integer n75_obs_event_limit;
    integer n75_obs_event_lines;
    longint unsigned n75_obs_cycle;
    longint unsigned n75_obs_last_progress_cycle;
    longint unsigned n75_obs_cfg_start_count;
    longint unsigned n75_obs_cfg_finish_count;
    longint unsigned n75_obs_exec_start_count;
    longint unsigned n75_obs_finish_count;
    longint unsigned n75_obs_a_request_count;
    longint unsigned n75_obs_a_data_count;
    longint unsigned n75_obs_d_write_count;
    logic n75_obs_cfg_start_d;
    logic n75_obs_cfg_finish_d;
    logic n75_obs_exec_start_d;
    logic n75_obs_slice_finish_d;
    string n75_obs_path;

    task automatic n75_obs_record(input string kind);
        if (n75_obs_fd != 0) begin
            $fdisplay(
                n75_obs_fd,
                "%0t | %s | cycle=%0d cfg_start=%0d cfg_finish=%0d exec=%0d finish=%0d a_req=%0d a_data=%0d d_write=%0d",
                $time, kind, n75_obs_cycle, n75_obs_cfg_start_count,
                n75_obs_cfg_finish_count, n75_obs_exec_start_count,
                n75_obs_finish_count, n75_obs_a_request_count,
                n75_obs_a_data_count, n75_obs_d_write_count
            );
            $fflush(n75_obs_fd);
        end
    endtask

    initial begin
        n75_obs_enabled = $test$plusargs("RETURN_OBSERVER");
        n75_obs_active = 1'b0;
        n75_obs_stall_reported = 1'b0;
        n75_obs_fd = 0;
        n75_obs_stall_cycles = 1048576;
        n75_obs_heartbeat_cycles = 262144;
        n75_obs_event_limit = 256;
        n75_obs_event_lines = 0;
        n75_obs_cycle = 0;
        n75_obs_last_progress_cycle = 0;
        n75_obs_cfg_start_count = 0;
        n75_obs_cfg_finish_count = 0;
        n75_obs_exec_start_count = 0;
        n75_obs_finish_count = 0;
        n75_obs_a_request_count = 0;
        n75_obs_a_data_count = 0;
        n75_obs_d_write_count = 0;
        n75_obs_cfg_start_d = 1'b0;
        n75_obs_cfg_finish_d = 1'b0;
        n75_obs_exec_start_d = 1'b0;
        n75_obs_slice_finish_d = 1'b0;
        void'($value$plusargs("RETURN_OBS_STALL_CYCLES=%d", n75_obs_stall_cycles));
        void'($value$plusargs("RETURN_OBS_HEARTBEAT_CYCLES=%d", n75_obs_heartbeat_cycles));
        void'($value$plusargs("RETURN_OBS_EVENT_LIMIT=%d", n75_obs_event_limit));
        if (n75_obs_enabled) begin
            if (!$value$plusargs("RETURN_OBS_FILE=%s", n75_obs_path)) begin
                n75_obs_path = "return_observer.log";
            end
            n75_obs_fd = $fopen(n75_obs_path, "w");
            if (n75_obs_fd == 0 || n75_obs_stall_cycles <= 0 ||
                n75_obs_heartbeat_cycles <= 0 || n75_obs_event_limit <= 0) begin
                $error("N75 observer invalid file or limits");
            end else begin
                $display(
                    "N75_FEATURE_ENABLE_V1 feature=NODE0075_PROGRESS enabled=1 stall=%0d heartbeat=%0d event_limit=%0d",
                    n75_obs_stall_cycles, n75_obs_heartbeat_cycles,
                    n75_obs_event_limit
                );
                $fdisplay(
                    n75_obs_fd,
                    "N75_FEATURE_ENABLE_V1 feature=NODE0075_PROGRESS enabled=1 stall=%0d heartbeat=%0d event_limit=%0d",
                    n75_obs_stall_cycles, n75_obs_heartbeat_cycles,
                    n75_obs_event_limit
                );
                $fflush(n75_obs_fd);
            end
        end
    end

    always @(posedge clk_sg) begin : N75_PROGRESS_SAMPLER
        integer channel;
        bit progressed;
        if (n75_obs_enabled && rst_n_sg) begin
            n75_obs_cycle++;
            progressed = 1'b0;
            if (n75_obs_cfg_start && !n75_obs_cfg_start_d) begin
                n75_obs_cfg_start_count++;
                n75_obs_active = 1'b1;
                progressed = 1'b1;
                n75_obs_record("CFG_START");
            end
            if (n75_obs_cfg_finish && !n75_obs_cfg_finish_d) begin
                n75_obs_cfg_finish_count++;
                progressed = 1'b1;
                n75_obs_record("CFG_FINISH");
            end
            if (n75_obs_exec_start && !n75_obs_exec_start_d) begin
                n75_obs_exec_start_count++;
                progressed = 1'b1;
                n75_obs_record("EXEC_START");
            end
            if (n75_obs_slice_finish && !n75_obs_slice_finish_d) begin
                n75_obs_finish_count++;
                n75_obs_active = 1'b0;
                progressed = 1'b1;
                n75_obs_record("COMP_FINISH");
            end
            for (channel = 0; channel < `MSE_REQ_CHL_NUM; channel++) begin
                if (n75_obs_a_request_hs[channel]) begin
                    n75_obs_a_request_count++;
                    progressed = 1'b1;
                    if (n75_obs_event_lines < n75_obs_event_limit) begin
                        n75_obs_event_lines++;
                        n75_obs_record("A_REQUEST_ACCEPT");
                    end
                end
                if (n75_obs_a_data_hs[channel]) begin
                    n75_obs_a_data_count++;
                    progressed = 1'b1;
                    if (n75_obs_event_lines < n75_obs_event_limit) begin
                        n75_obs_event_lines++;
                        n75_obs_record("A_DATA_ACCEPT");
                    end
                end
            end
            if (n75_obs_d_write_hs) begin
                n75_obs_d_write_count++;
                progressed = 1'b1;
                if (n75_obs_event_lines < n75_obs_event_limit) begin
                    n75_obs_event_lines++;
                    n75_obs_record("D_WRITE_ACCEPT");
                end
            end
            if (progressed) begin
                n75_obs_last_progress_cycle = n75_obs_cycle;
                n75_obs_stall_reported = 1'b0;
            end
            if (n75_obs_cycle % n75_obs_heartbeat_cycles == 0) begin
                n75_obs_record("HEARTBEAT");
            end
            if (n75_obs_active && !n75_obs_stall_reported &&
                n75_obs_cycle - n75_obs_last_progress_cycle >= n75_obs_stall_cycles) begin
                n75_obs_stall_reported = 1'b1;
                n75_obs_record("LONG_RUNNING_HANG_AT_LAST_PROGRESS");
            end
            n75_obs_cfg_start_d = n75_obs_cfg_start;
            n75_obs_cfg_finish_d = n75_obs_cfg_finish;
            n75_obs_exec_start_d = n75_obs_exec_start;
            n75_obs_slice_finish_d = n75_obs_slice_finish;
        end
    end

    final begin
        if (n75_obs_enabled && n75_obs_fd != 0) begin
            n75_obs_record("FINAL_SUMMARY");
            if (n75_obs_finish_count == 24 && !n75_obs_stall_reported) begin
                $fdisplay(n75_obs_fd, "N75_CANONICAL_DECISION_V1 decision=EXPECTED_24_STAGE_PREFIX_COMPLETE");
            end else if (n75_obs_stall_reported) begin
                $fdisplay(n75_obs_fd, "N75_CANONICAL_DECISION_V1 decision=LONG_RUNNING_HANG");
            end else begin
                $fdisplay(n75_obs_fd, "N75_CANONICAL_DECISION_V1 decision=INCOMPLETE_AT_SIMULATOR_END");
            end
            $fflush(n75_obs_fd);
            $fclose(n75_obs_fd);
        end
    end
