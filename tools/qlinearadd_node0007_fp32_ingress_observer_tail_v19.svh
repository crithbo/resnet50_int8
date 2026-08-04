// QLinearAdd node0007 v19 narrow FP32-add ingress observer.
//
// Read-only diagnostic extension. Enable with:
//   +RETURN_OBSERVER +RETURN_OBS_DEEP +QADD_FP32_INGRESS_OBSERVER
//
// All qualified counters are accumulated in clk_sg, the source domain of the
// MSE/buffer/GA chain.  Low-rate snapshots are emitted from the continuously
// alive clk_db domain.  Levels are state only and are never progress events.

    logic qadd_ingress_enabled;
    logic qadd_ingress_marker_written;
    logic qadd_ingress_exec_start_d;
    longint unsigned qadd_ingress_stage_seq;
    longint unsigned qadd_ingress_mse_req [0:1];
    longint unsigned qadd_ingress_mse_rdata [0:1];
    longint unsigned qadd_ingress_mse_buf_accept [0:1];
    longint unsigned qadd_ingress_buf_write_accept [0:1];
    longint unsigned qadd_ingress_buf_arm_req_accept [0:1];
    longint unsigned qadd_ingress_buf_array_accept [0:1];
    longint unsigned qadd_ingress_ga_capture [0:1];
    longint unsigned qadd_ingress_ga_pair_ready;
    longint unsigned qadd_ingress_ga_consumer_accept;
    longint unsigned qadd_ingress_ga_first_output;
    longint unsigned qadd_ingress_snapshot_cycles;

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
        qadd_ingress_mse_buf_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
        qadd_ingress_buf_wr_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
        qadd_ingress_buf_arm_req_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
        qadd_ingress_buf_array_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
        qadd_ingress_buf_any_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]
        qadd_ingress_buf_arm_ready_mon;

    generate
        for (genvar qadd_ingress_group = 0;
             qadd_ingress_group < `SLICE_GROUP_SIZE;
             qadd_ingress_group++) begin : QADD_INGRESS_GROUP
            for (genvar qadd_ingress_slice = 0;
                 qadd_ingress_slice < `SLICE_GROUP_NUM;
                 qadd_ingress_slice++) begin : QADD_INGRESS_SLICE
                assign qadd_ingress_mse_buf_hs_mon
                    [qadd_ingress_group][qadd_ingress_slice][0] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_ingress_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_ingress_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE
                        .u_Memory_RD_Stream_Engine.mse2buf_wvalid &
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_ingress_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_ingress_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE
                        .u_Memory_RD_Stream_Engine.buf2mse_wreq_ready;
                assign qadd_ingress_mse_buf_hs_mon
                    [qadd_ingress_group][qadd_ingress_slice][1] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_ingress_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_ingress_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[1].RD_MSE
                        .u_Memory_RD_Stream_Engine.mse2buf_wvalid &
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_ingress_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_ingress_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[1].RD_MSE
                        .u_Memory_RD_Stream_Engine.buf2mse_wreq_ready;

                for (genvar qadd_ingress_pair = 0;
                     qadd_ingress_pair < 2;
                     qadd_ingress_pair++) begin : QADD_INGRESS_BUF_PAIR
                    localparam integer QADD_INGRESS_BUF_ID =
                        qadd_ingress_pair * 2;
                    assign qadd_ingress_buf_wr_hs_mon
                        [qadd_ingress_group][qadd_ingress_slice]
                        [qadd_ingress_pair] =
                        (|u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [qadd_ingress_group].u_slice_with_datahub_mc_group
                            .slice_group_gen[qadd_ingress_slice].u_slice_wrapper
                            .u_Slice.u_LSU.u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[QADD_INGRESS_BUF_ID]
                            .u_Buffer_Manager.u_Buffer.buf_wr_en) &&
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [qadd_ingress_group].u_slice_with_datahub_mc_group
                            .slice_group_gen[qadd_ingress_slice].u_slice_wrapper
                            .u_Slice.u_LSU.u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[QADD_INGRESS_BUF_ID]
                            .u_Buffer_Manager.u_Buffer.buf_wreq_ready;
                    assign qadd_ingress_buf_arm_req_hs_mon
                        [qadd_ingress_group][qadd_ingress_slice]
                        [qadd_ingress_pair] =
                        (|u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [qadd_ingress_group].u_slice_with_datahub_mc_group
                            .slice_group_gen[qadd_ingress_slice].u_slice_wrapper
                            .u_Slice.u_LSU.u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[QADD_INGRESS_BUF_ID]
                            .u_Buffer_Manager.arm2buf_req_valid) &&
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [qadd_ingress_group].u_slice_with_datahub_mc_group
                            .slice_group_gen[qadd_ingress_slice].u_slice_wrapper
                            .u_Slice.u_LSU.u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[QADD_INGRESS_BUF_ID]
                            .u_Buffer_Manager.buf2arm_req_ready;
                    assign qadd_ingress_buf_array_hs_mon
                        [qadd_ingress_group][qadd_ingress_slice]
                        [qadd_ingress_pair] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [qadd_ingress_group].u_slice_with_datahub_mc_group
                            .slice_group_gen[qadd_ingress_slice].u_slice_wrapper
                            .u_Slice.u_LSU.u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[QADD_INGRESS_BUF_ID]
                            .u_Buffer_Manager.buf2arm_rvalid &&
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [qadd_ingress_group].u_slice_with_datahub_mc_group
                            .slice_group_gen[qadd_ingress_slice].u_slice_wrapper
                            .u_Slice.u_LSU.u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[QADD_INGRESS_BUF_ID]
                            .u_Buffer_Manager.u_Array_Request_Manager
                            .array2arm_bp_post;
                    assign qadd_ingress_buf_any_valid_mon
                        [qadd_ingress_group][qadd_ingress_slice]
                        [qadd_ingress_pair] =
                        |u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [qadd_ingress_group].u_slice_with_datahub_mc_group
                            .slice_group_gen[qadd_ingress_slice].u_slice_wrapper
                            .u_Slice.u_LSU.u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[QADD_INGRESS_BUF_ID]
                            .u_Buffer_Manager.u_Buffer.valid_buf;
                    assign qadd_ingress_buf_arm_ready_mon
                        [qadd_ingress_group][qadd_ingress_slice]
                        [qadd_ingress_pair] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [qadd_ingress_group].u_slice_with_datahub_mc_group
                            .slice_group_gen[qadd_ingress_slice].u_slice_wrapper
                            .u_Slice.u_LSU.u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[QADD_INGRESS_BUF_ID]
                            .u_Buffer_Manager.u_Buffer.buf2arm_rreq_ready;
                end
            end
        end
    endgenerate

    initial begin
        qadd_ingress_enabled =
            $test$plusargs("QADD_FP32_INGRESS_OBSERVER");
        if (qadd_ingress_enabled)
            $display(
                "# QADD_FP32_INGRESS_OBSERVER_V19_TIME0 enabled=1 source_clock=clk_sg snapshot_clock=clk_db"
            );
        qadd_ingress_marker_written = 0;
        qadd_ingress_exec_start_d = 0;
        qadd_ingress_stage_seq = 0;
        qadd_ingress_ga_pair_ready = 0;
        qadd_ingress_ga_consumer_accept = 0;
        qadd_ingress_ga_first_output = 0;
        qadd_ingress_snapshot_cycles = 0;
        for (int qadd_ingress_i = 0; qadd_ingress_i < 2;
             qadd_ingress_i++) begin
            qadd_ingress_mse_req[qadd_ingress_i] = 0;
            qadd_ingress_mse_rdata[qadd_ingress_i] = 0;
            qadd_ingress_mse_buf_accept[qadd_ingress_i] = 0;
            qadd_ingress_buf_write_accept[qadd_ingress_i] = 0;
            qadd_ingress_buf_arm_req_accept[qadd_ingress_i] = 0;
            qadd_ingress_buf_array_accept[qadd_ingress_i] = 0;
            qadd_ingress_ga_capture[qadd_ingress_i] = 0;
        end
    end

    // Qualified event counters: source clock is clk_sg.
    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (
            u_NDP_Top_new.rst_n_sg &&
            return_obs_enabled &&
            return_obs_deep_enabled &&
            qadd_ingress_enabled &&
            return_obs_active
        ) begin
            if (
                return_obs_sem_exec_start_mon
                    [return_obs_group_id][return_obs_local_slice_id] &&
                !qadd_ingress_exec_start_d
            ) begin
                qadd_ingress_stage_seq++;
                qadd_ingress_ga_pair_ready = 0;
                qadd_ingress_ga_consumer_accept = 0;
                qadd_ingress_ga_first_output = 0;
                for (int qadd_ingress_i = 0; qadd_ingress_i < 2;
                     qadd_ingress_i++) begin
                    qadd_ingress_mse_req[qadd_ingress_i] = 0;
                    qadd_ingress_mse_rdata[qadd_ingress_i] = 0;
                    qadd_ingress_mse_buf_accept[qadd_ingress_i] = 0;
                    qadd_ingress_buf_write_accept[qadd_ingress_i] = 0;
                    qadd_ingress_buf_arm_req_accept[qadd_ingress_i] = 0;
                    qadd_ingress_buf_array_accept[qadd_ingress_i] = 0;
                    qadd_ingress_ga_capture[qadd_ingress_i] = 0;
                end
            end
            qadd_ingress_exec_start_d =
                return_obs_sem_exec_start_mon
                    [return_obs_group_id][return_obs_local_slice_id];

            for (int qadd_ingress_mse = 0; qadd_ingress_mse < 2;
                 qadd_ingress_mse++) begin
                for (int qadd_ingress_ch = 0;
                     qadd_ingress_ch < `MSE_REQ_CHL_NUM;
                     qadd_ingress_ch++) begin
                    if (local_req_hs[return_obs_group_id]
                        [return_obs_local_slice_id][qadd_ingress_mse]
                        [qadd_ingress_ch])
                        qadd_ingress_mse_req[qadd_ingress_mse]++;
                    if (local_rdata_hs[return_obs_group_id]
                        [return_obs_local_slice_id][qadd_ingress_mse]
                        [qadd_ingress_ch])
                        qadd_ingress_mse_rdata[qadd_ingress_mse]++;
                end
                if (qadd_ingress_mse_buf_hs_mon[return_obs_group_id]
                    [return_obs_local_slice_id][qadd_ingress_mse])
                    qadd_ingress_mse_buf_accept[qadd_ingress_mse]++;
                if (qadd_ingress_buf_wr_hs_mon[return_obs_group_id]
                    [return_obs_local_slice_id][qadd_ingress_mse])
                    qadd_ingress_buf_write_accept[qadd_ingress_mse]++;
                if (qadd_ingress_buf_arm_req_hs_mon[return_obs_group_id]
                    [return_obs_local_slice_id][qadd_ingress_mse])
                    qadd_ingress_buf_arm_req_accept[qadd_ingress_mse]++;
                if (qadd_ingress_buf_array_hs_mon[return_obs_group_id]
                    [return_obs_local_slice_id][qadd_ingress_mse])
                    qadd_ingress_buf_array_accept[qadd_ingress_mse]++;
            end

            for (int qadd_ingress_row = 0;
                 qadd_ingress_row < `GA_ROW_PE_NUM;
                 qadd_ingress_row++) begin
                for (int qadd_ingress_slot = 0;
                     qadd_ingress_slot < 2;
                     qadd_ingress_slot++) begin
                    if (return_obs_ga_operand_capture_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [qadd_ingress_row][qadd_ingress_slot][0])
                        qadd_ingress_ga_capture[0]++;
                    if (return_obs_ga_operand_capture_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [qadd_ingress_row][qadd_ingress_slot][1])
                        qadd_ingress_ga_capture[1]++;
                    if (
                        return_obs_ga_operand_capture_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [qadd_ingress_row][qadd_ingress_slot][0] &&
                        return_obs_ga_operand_capture_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [qadd_ingress_row][qadd_ingress_slot][1]
                    )
                        qadd_ingress_ga_pair_ready++;
                    if (
                        return_obs_ga_p0_enable_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [qadd_ingress_row][qadd_ingress_slot] &&
                        return_obs_ga_input_valid_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [qadd_ingress_row][qadd_ingress_slot]
                    )
                        qadd_ingress_ga_consumer_accept++;
                    if (return_obs_ga_outbuffer_wr_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [qadd_ingress_row][qadd_ingress_slot])
                        qadd_ingress_ga_first_output++;
                end
            end
        end
    end

    // Low-rate snapshot: continuously alive observer clock is clk_db.
    always @(posedge u_NDP_Top_new.clk_db) begin
        if (
            u_NDP_Top_new.rst_n_db &&
            return_obs_enabled &&
            return_obs_deep_enabled &&
            qadd_ingress_enabled &&
            return_obs_fd != 0
        ) begin
            if (!qadd_ingress_marker_written) begin
                qadd_ingress_marker_written = 1;
                $fdisplay(
                    return_obs_fd,
                    "# QADD_FP32_INGRESS_OBSERVER_V19 enabled=1 source_clock=clk_sg snapshot_clock=clk_db level_is_progress=0"
                );
            end
            qadd_ingress_snapshot_cycles++;
            if (
                return_obs_active &&
                return_obs_heartbeat_period != 0 &&
                (qadd_ingress_snapshot_cycles %
                    return_obs_heartbeat_period) == 0
            ) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | QADD_FP32_INGRESS | slice=%0d stage_seq=%0d snapshot_cycles=%0d mse0_req=%0d mse1_req=%0d mse0_rdata=%0d mse1_rdata=%0d mse0_buf=%0d mse1_buf=%0d buf0_wr=%0d buf2_wr=%0d buf0_arm_req=%0d buf2_arm_req=%0d buf0_array=%0d buf2_array=%0d ga0_capture=%0d ga1_capture=%0d ga_pair=%0d ga_accept=%0d ga_output=%0d buf_valid=0x%0h buf_arm_ready=0x%0h",
                    $time,
                    return_obs_slice_id,
                    qadd_ingress_stage_seq,
                    qadd_ingress_snapshot_cycles,
                    qadd_ingress_mse_req[0],
                    qadd_ingress_mse_req[1],
                    qadd_ingress_mse_rdata[0],
                    qadd_ingress_mse_rdata[1],
                    qadd_ingress_mse_buf_accept[0],
                    qadd_ingress_mse_buf_accept[1],
                    qadd_ingress_buf_write_accept[0],
                    qadd_ingress_buf_write_accept[1],
                    qadd_ingress_buf_arm_req_accept[0],
                    qadd_ingress_buf_arm_req_accept[1],
                    qadd_ingress_buf_array_accept[0],
                    qadd_ingress_buf_array_accept[1],
                    qadd_ingress_ga_capture[0],
                    qadd_ingress_ga_capture[1],
                    qadd_ingress_ga_pair_ready,
                    qadd_ingress_ga_consumer_accept,
                    qadd_ingress_ga_first_output,
                    qadd_ingress_buf_any_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_ingress_buf_arm_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                );
                $fflush(return_obs_fd);
            end
        end
    end
