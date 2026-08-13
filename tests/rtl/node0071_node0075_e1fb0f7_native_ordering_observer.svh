// Package-local, read-only observer for the node0071 -> node0075 native-ordering
// diagnostic.  Included inside tb_NDP_Top_new_phy; it never drives DUT state.

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          n75_obs_cfg_start_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          n75_obs_cfg_finish_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          n75_obs_exec_start_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          n75_obs_slice_finish_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0] n75_obs_a_req_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0][`MSE_MEM_REQ_ADDR_WIDTH-1:0]
          n75_obs_a_req_addr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0] n75_obs_a_data_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0] n75_obs_d_req_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0] n75_obs_d_wdata_hs_mon;

    generate
        for (genvar n75_obs_group = 0;
             n75_obs_group < `SLICE_GROUP_SIZE;
             n75_obs_group++) begin : N75_OBS_GROUP_GEN
            for (genvar n75_obs_slice = 0;
                 n75_obs_slice < `SLICE_GROUP_NUM;
                 n75_obs_slice++) begin : N75_OBS_SLICE_GEN
                assign n75_obs_cfg_start_mon[n75_obs_group][n75_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[n75_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[n75_obs_slice]
                        .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager
                        .sem2scm_cfg_start;
                assign n75_obs_cfg_finish_mon[n75_obs_group][n75_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[n75_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[n75_obs_slice]
                        .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager
                        .scm2sem_cfg_finish;
                assign n75_obs_exec_start_mon[n75_obs_group][n75_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[n75_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[n75_obs_slice]
                        .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager
                        .sem2iga_exec_start;
                assign n75_obs_slice_finish_mon[n75_obs_group][n75_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[n75_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[n75_obs_slice]
                        .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager
                        .slice_cmpt_finish;
                assign n75_obs_a_req_hs_mon[n75_obs_group][n75_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[n75_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[n75_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[1].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Memory_AG.mem_ag_ob_chl_hs;
                assign n75_obs_a_req_addr_mon[n75_obs_group][n75_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[n75_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[n75_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[1].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Memory_AG.mem_ag_ob_chl_addr;
                assign n75_obs_a_data_hs_mon[n75_obs_group][n75_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[n75_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[n75_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[1].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Data_Channel.rd_chl_ib_rd_hs;
                assign n75_obs_d_req_hs_mon[n75_obs_group][n75_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[n75_obs_group]
                        .u_slice_with_datahub_mc_group.local_req_valid
                        [n75_obs_slice][4] &
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[n75_obs_group]
                        .u_slice_with_datahub_mc_group.local_req_ready
                        [n75_obs_slice][4];
                assign n75_obs_d_wdata_hs_mon[n75_obs_group][n75_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[n75_obs_group]
                        .u_slice_with_datahub_mc_group.local_wdata_valid
                        [n75_obs_slice][4] &
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[n75_obs_group]
                        .u_slice_with_datahub_mc_group.local_wdata_ready
                        [n75_obs_slice][4];
            end
        end
    endgenerate

    bit n75_obs_enabled;
    bit n75_obs_feature_enabled;
    bit n75_obs_active;
    bit n75_obs_stall_reported;
    bit n75_obs_first_a_seen;
    bit n75_obs_first_a_order_ok;
    integer n75_obs_fd;
    integer n75_obs_stall_cycles;
    integer n75_obs_heartbeat_cycles;
    integer n75_obs_a_event_limit;
    integer n75_obs_a_event_lines;
    integer n75_obs_stage_index;
    longint unsigned n75_obs_cycle;
    longint unsigned n75_obs_last_progress_cycle;
    longint unsigned n75_obs_first_a_cycle;
    longint unsigned n75_obs_cfg_start_count;
    longint unsigned n75_obs_cfg_finish_count;
    longint unsigned n75_obs_exec_start_count;
    longint unsigned n75_obs_finish_total;
    longint unsigned n75_obs_producer_req_count;
    longint unsigned n75_obs_producer_wdata_count;
    longint unsigned n75_obs_producer_finish_count;
    longint unsigned n75_obs_a_req_count;
    longint unsigned n75_obs_a_data_count;
    longint unsigned n75_obs_finish_count [0:15];
    longint unsigned n75_obs_a_req_slice_count [0:15];
    longint unsigned n75_obs_a_data_slice_count [0:15];
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          n75_obs_cfg_start_d;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          n75_obs_cfg_finish_d;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          n75_obs_exec_start_d;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          n75_obs_slice_finish_d;
    string n75_obs_path;

    task automatic n75_obs_snapshot(input string kind);
        if (n75_obs_fd != 0) begin
            $fdisplay(
                n75_obs_fd,
                "N75_SNAPSHOT_V2 kind=%s time=%0t cycle=%0d stage=%0d cfg_start=%0d cfg_finish=%0d exec=%0d finish=%0d producer_req=%0d producer_wdata=%0d producer_finish=%0d a_req=%0d a_data=%0d last_progress=%0d",
                kind, $time, n75_obs_cycle, n75_obs_stage_index,
                n75_obs_cfg_start_count, n75_obs_cfg_finish_count,
                n75_obs_exec_start_count, n75_obs_finish_total,
                n75_obs_producer_req_count, n75_obs_producer_wdata_count,
                n75_obs_producer_finish_count, n75_obs_a_req_count,
                n75_obs_a_data_count, n75_obs_last_progress_cycle
            );
            $fflush(n75_obs_fd);
        end
    endtask

    initial begin : N75_OBS_INITIALIZE
        integer n75_obs_init_slice;
        n75_obs_enabled = $test$plusargs("RETURN_OBSERVER");
        n75_obs_feature_enabled = $test$plusargs("N75_NATIVE_ORDERING");
        n75_obs_active = 1'b0;
        n75_obs_stall_reported = 1'b0;
        n75_obs_first_a_seen = 1'b0;
        n75_obs_first_a_order_ok = 1'b0;
        n75_obs_fd = 0;
        n75_obs_stall_cycles = 1048576;
        n75_obs_heartbeat_cycles = 262144;
        n75_obs_a_event_limit = 9000;
        n75_obs_a_event_lines = 0;
        n75_obs_stage_index = 0;
        n75_obs_cycle = 0;
        n75_obs_last_progress_cycle = 0;
        n75_obs_first_a_cycle = 0;
        n75_obs_cfg_start_count = 0;
        n75_obs_cfg_finish_count = 0;
        n75_obs_exec_start_count = 0;
        n75_obs_finish_total = 0;
        n75_obs_producer_req_count = 0;
        n75_obs_producer_wdata_count = 0;
        n75_obs_producer_finish_count = 0;
        n75_obs_a_req_count = 0;
        n75_obs_a_data_count = 0;
        n75_obs_cfg_start_d = '0;
        n75_obs_cfg_finish_d = '0;
        n75_obs_exec_start_d = '0;
        n75_obs_slice_finish_d = '0;
        for (n75_obs_init_slice = 0;
             n75_obs_init_slice < 16;
             n75_obs_init_slice++) begin
            n75_obs_finish_count[n75_obs_init_slice] = 0;
            n75_obs_a_req_slice_count[n75_obs_init_slice] = 0;
            n75_obs_a_data_slice_count[n75_obs_init_slice] = 0;
        end
        void'($value$plusargs(
            "RETURN_OBS_STALL_CYCLES=%d", n75_obs_stall_cycles
        ));
        void'($value$plusargs(
            "RETURN_OBS_HEARTBEAT_CYCLES=%d", n75_obs_heartbeat_cycles
        ));
        void'($value$plusargs(
            "N75_A_EVENT_LIMIT=%d", n75_obs_a_event_limit
        ));
        if (n75_obs_enabled && n75_obs_feature_enabled) begin
            if (!$value$plusargs("RETURN_OBS_FILE=%s", n75_obs_path))
                n75_obs_path = "return_observer.log";
            n75_obs_fd = $fopen(n75_obs_path, "w");
            if (n75_obs_fd == 0 || n75_obs_stall_cycles <= 0 ||
                n75_obs_heartbeat_cycles <= 0 ||
                n75_obs_a_event_limit < 8192) begin
                $error("N75 observer invalid output or limits");
            end else begin
                $display(
                    "N75_FEATURE_ENABLE_V2 feature=NATIVE_ORDERING enabled=1 stall=%0d heartbeat=%0d a_event_limit=%0d",
                    n75_obs_stall_cycles, n75_obs_heartbeat_cycles,
                    n75_obs_a_event_limit
                );
                $fdisplay(
                    n75_obs_fd,
                    "N75_FEATURE_ENABLE_V2 feature=NATIVE_ORDERING enabled=1 stall=%0d heartbeat=%0d a_event_limit=%0d",
                    n75_obs_stall_cycles, n75_obs_heartbeat_cycles,
                    n75_obs_a_event_limit
                );
                $fflush(n75_obs_fd);
            end
        end
    end

    always @(posedge clk_sg) begin : N75_OBS_PROGRESS
        integer n75_obs_group_i;
        integer n75_obs_slice_i;
        integer n75_obs_channel_i;
        integer n75_obs_linear_slice;
        integer n75_obs_pass_index;
        bit n75_obs_progressed;
        if (n75_obs_enabled && n75_obs_feature_enabled && rst_n_sg) begin
            n75_obs_cycle = n75_obs_cycle + 1;
            n75_obs_progressed = 1'b0;
            if (n75_obs_cfg_start_mon[0][0] &&
                !n75_obs_cfg_start_d[0][0]) begin
                n75_obs_cfg_start_count = n75_obs_cfg_start_count + 1;
                n75_obs_active = 1'b1;
                n75_obs_progressed = 1'b1;
            end
            if (n75_obs_cfg_finish_mon[0][0] &&
                !n75_obs_cfg_finish_d[0][0]) begin
                n75_obs_cfg_finish_count = n75_obs_cfg_finish_count + 1;
                n75_obs_progressed = 1'b1;
            end
            if (n75_obs_exec_start_mon[0][0] &&
                !n75_obs_exec_start_d[0][0]) begin
                n75_obs_exec_start_count = n75_obs_exec_start_count + 1;
                n75_obs_stage_index = n75_obs_stage_index + 1;
                n75_obs_progressed = 1'b1;
                n75_obs_snapshot("EXEC_START");
            end
            for (n75_obs_group_i = 0;
                 n75_obs_group_i < 8;
                 n75_obs_group_i++) begin
                for (n75_obs_slice_i = 0;
                     n75_obs_slice_i < 2;
                     n75_obs_slice_i++) begin
                    n75_obs_linear_slice =
                        n75_obs_group_i * 2 + n75_obs_slice_i;
                    if (n75_obs_slice_finish_mon
                            [n75_obs_group_i][n75_obs_slice_i] &&
                        !n75_obs_slice_finish_d
                            [n75_obs_group_i][n75_obs_slice_i]) begin
                        n75_obs_finish_count[n75_obs_linear_slice] =
                            n75_obs_finish_count[n75_obs_linear_slice] + 1;
                        n75_obs_finish_total = n75_obs_finish_total + 1;
                        if (n75_obs_stage_index == 8)
                            n75_obs_producer_finish_count =
                                n75_obs_producer_finish_count + 1;
                        n75_obs_progressed = 1'b1;
                    end
                    for (n75_obs_channel_i = 0;
                         n75_obs_channel_i < `MSE_REQ_CHL_NUM;
                         n75_obs_channel_i++) begin
                        if (n75_obs_stage_index == 8 &&
                            n75_obs_d_req_hs_mon
                                [n75_obs_group_i][n75_obs_slice_i]
                                [n75_obs_channel_i]) begin
                            n75_obs_producer_req_count =
                                n75_obs_producer_req_count + 1;
                            n75_obs_progressed = 1'b1;
                        end
                        if (n75_obs_stage_index == 8 &&
                            n75_obs_d_wdata_hs_mon
                                [n75_obs_group_i][n75_obs_slice_i]
                                [n75_obs_channel_i]) begin
                            n75_obs_producer_wdata_count =
                                n75_obs_producer_wdata_count + 1;
                            n75_obs_progressed = 1'b1;
                        end
                        if (n75_obs_stage_index >= 9 &&
                            n75_obs_stage_index <= 16 &&
                            n75_obs_a_req_hs_mon
                                [n75_obs_group_i][n75_obs_slice_i]
                                [n75_obs_channel_i]) begin
                            n75_obs_pass_index = n75_obs_stage_index - 9;
                            n75_obs_a_req_count = n75_obs_a_req_count + 1;
                            n75_obs_a_req_slice_count[n75_obs_linear_slice] =
                                n75_obs_a_req_slice_count[n75_obs_linear_slice] + 1;
                            if (!n75_obs_first_a_seen) begin
                                n75_obs_first_a_seen = 1'b1;
                                n75_obs_first_a_cycle = n75_obs_cycle;
                                n75_obs_first_a_order_ok =
                                    n75_obs_producer_finish_count == 16 &&
                                    n75_obs_producer_req_count == 1024 &&
                                    n75_obs_producer_wdata_count == 1024;
                            end
                            if (n75_obs_a_event_lines <
                                n75_obs_a_event_limit) begin
                                n75_obs_a_event_lines =
                                    n75_obs_a_event_lines + 1;
                                $fdisplay(
                                    n75_obs_fd,
                                    "N75_A_REQ_V1 stage=%0d pass=%0d slice=%0d channel=%0d ordinal=%0d addr=0x%0h",
                                    n75_obs_stage_index, n75_obs_pass_index,
                                    n75_obs_linear_slice, n75_obs_channel_i,
                                    n75_obs_a_req_slice_count
                                        [n75_obs_linear_slice],
                                    n75_obs_a_req_addr_mon
                                        [n75_obs_group_i][n75_obs_slice_i]
                                        [n75_obs_channel_i]
                                );
                            end
                            n75_obs_progressed = 1'b1;
                        end
                        if (n75_obs_stage_index >= 9 &&
                            n75_obs_stage_index <= 16 &&
                            n75_obs_a_data_hs_mon
                                [n75_obs_group_i][n75_obs_slice_i]
                                [n75_obs_channel_i]) begin
                            n75_obs_a_data_count = n75_obs_a_data_count + 1;
                            n75_obs_a_data_slice_count[n75_obs_linear_slice] =
                                n75_obs_a_data_slice_count[n75_obs_linear_slice] + 1;
                            n75_obs_progressed = 1'b1;
                        end
                    end
                end
            end
            if (n75_obs_progressed) begin
                n75_obs_last_progress_cycle = n75_obs_cycle;
                n75_obs_stall_reported = 1'b0;
            end
            if (n75_obs_cycle % n75_obs_heartbeat_cycles == 0)
                n75_obs_snapshot("HEARTBEAT");
            if (n75_obs_active && !n75_obs_stall_reported &&
                n75_obs_cycle - n75_obs_last_progress_cycle >=
                    n75_obs_stall_cycles) begin
                n75_obs_stall_reported = 1'b1;
                n75_obs_snapshot("LONG_RUNNING_HANG_AT_LAST_PROGRESS");
            end
            n75_obs_cfg_start_d = n75_obs_cfg_start_mon;
            n75_obs_cfg_finish_d = n75_obs_cfg_finish_mon;
            n75_obs_exec_start_d = n75_obs_exec_start_mon;
            n75_obs_slice_finish_d = n75_obs_slice_finish_mon;
        end
    end

    final begin : N75_OBS_FINAL
        integer n75_obs_final_slice;
        bit n75_obs_all_slices_finished;
        if (n75_obs_enabled && n75_obs_feature_enabled && n75_obs_fd != 0) begin
            n75_obs_all_slices_finished = 1'b1;
            for (n75_obs_final_slice = 0;
                 n75_obs_final_slice < 16;
                 n75_obs_final_slice++) begin
                if (n75_obs_finish_count[n75_obs_final_slice] != 32)
                    n75_obs_all_slices_finished = 1'b0;
            end
            n75_obs_snapshot("FINAL_SUMMARY");
            if (n75_obs_all_slices_finished &&
                n75_obs_exec_start_count == 32 &&
                n75_obs_finish_total == 512 &&
                n75_obs_producer_req_count == 1024 &&
                n75_obs_producer_wdata_count == 1024 &&
                n75_obs_producer_finish_count == 16 &&
                n75_obs_first_a_order_ok &&
                n75_obs_a_req_count == 8192 &&
                n75_obs_a_data_count == 8192 &&
                n75_obs_a_event_lines == 8192 &&
                !n75_obs_stall_reported) begin
                $fdisplay(
                    n75_obs_fd,
                    "N75_CANONICAL_DECISION_V2 decision=EXPECTED_32_STAGE_NATIVE_ORDER_COMPLETE reason=all_required_qualified_counts_exact boundary=node0071_stage08_hub_accept_to_node0075_pass00_first_read sample_begin=0 sample_end=%0d stage_start=%0d stage_finish=%0d slice_finish_total=%0d producer_req=%0d producer_wdata=%0d producer_finish=%0d first_a_cycle=%0d first_a_order_ok=%0d a_req=%0d a_data=%0d a_event_lines=%0d",
                    n75_obs_cycle, n75_obs_exec_start_count,
                    n75_obs_finish_count[0], n75_obs_finish_total,
                    n75_obs_producer_req_count,
                    n75_obs_producer_wdata_count,
                    n75_obs_producer_finish_count,
                    n75_obs_first_a_cycle, n75_obs_first_a_order_ok,
                    n75_obs_a_req_count, n75_obs_a_data_count,
                    n75_obs_a_event_lines
                );
            end else if (n75_obs_stall_reported) begin
                $fdisplay(
                    n75_obs_fd,
                    "N75_CANONICAL_DECISION_V2 decision=LONG_RUNNING_HANG_PENDING_ROOT_CAUSE reason=stall_window_without_qualified_progress boundary=last_progress sample_begin=0 sample_end=%0d stage_start=%0d stage_finish=%0d slice_finish_total=%0d producer_req=%0d producer_wdata=%0d producer_finish=%0d first_a_cycle=%0d first_a_order_ok=%0d a_req=%0d a_data=%0d a_event_lines=%0d",
                    n75_obs_cycle, n75_obs_exec_start_count,
                    n75_obs_finish_count[0], n75_obs_finish_total,
                    n75_obs_producer_req_count,
                    n75_obs_producer_wdata_count,
                    n75_obs_producer_finish_count,
                    n75_obs_first_a_cycle, n75_obs_first_a_order_ok,
                    n75_obs_a_req_count, n75_obs_a_data_count,
                    n75_obs_a_event_lines
                );
            end else begin
                $fdisplay(
                    n75_obs_fd,
                    "N75_CANONICAL_DECISION_V2 decision=INCOMPLETE_AT_SIMULATOR_END reason=required_qualified_gate_not_closed boundary=current_stage sample_begin=0 sample_end=%0d stage_start=%0d stage_finish=%0d slice_finish_total=%0d producer_req=%0d producer_wdata=%0d producer_finish=%0d first_a_cycle=%0d first_a_order_ok=%0d a_req=%0d a_data=%0d a_event_lines=%0d",
                    n75_obs_cycle, n75_obs_exec_start_count,
                    n75_obs_finish_count[0], n75_obs_finish_total,
                    n75_obs_producer_req_count,
                    n75_obs_producer_wdata_count,
                    n75_obs_producer_finish_count,
                    n75_obs_first_a_cycle, n75_obs_first_a_order_ok,
                    n75_obs_a_req_count, n75_obs_a_data_count,
                    n75_obs_a_event_lines
                );
            end
            $fflush(n75_obs_fd);
            $fclose(n75_obs_fd);
        end
    end
