// QLinearAdd node0007 v47 tail-round qualified flow observer.
//
// Read-only package-local observer.  Qualified counters advance only on the
// accepted edge in the owning clk_sg domain.  Stable ready/valid/full/empty
// levels are emitted only as state snapshots and never count as progress.

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q47_buf5_wready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q47_buf5_rready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q47_bagq_wr_mon, q47_bagq_rd_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q47_bagq_empty_mon, q47_bagq_full_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q47_rdag_wr_mon, q47_rdag_rd_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q47_rdag_empty_mon, q47_rdag_full_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q47_rdag_rreq_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q47_wr_req_hs_mon, q47_wr_prepared_wr_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q47_wr_prepared_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q47_wr_queue_empty_mon, q47_wr_queue_full_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`MSE_REQ_CHL_NUM-1:0] q47_wr_ob_wr_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`MSE_REQ_CHL_NUM-1:0] q47_wr_ob_rd_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`SE_BUF_ROW_INPORT_IDX_WIDTH-1:0] q47_bag_row_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`SE_BUF_COL_INPORT_IDX_WIDTH-1:0] q47_bag_col_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`SE_BUF_INPORT_TAG_WIDTH-1:0] q47_bag_row_tag_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`SE_BUF_INPORT_TAG_WIDTH-1:0] q47_bag_col_tag_mon;

    generate
        for (genvar q47_group = 0; q47_group < `SLICE_GROUP_SIZE;
             q47_group++) begin : Q47_GROUP_GEN
            for (genvar q47_slice = 0; q47_slice < `SLICE_GROUP_NUM;
                 q47_slice++) begin : Q47_SLICE_GEN
                assign q47_buf5_wready_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[5]
                        .u_Buffer_Manager.u_Buffer.buf_wreq_ready;
                assign q47_buf5_rready_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[5]
                        .u_Buffer_Manager.u_Buffer.buf_rreq_ready;
                assign q47_bagq_wr_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en;
                assign q47_bagq_rd_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en;
                assign q47_bagq_empty_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty;
                assign q47_bagq_full_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full;
                assign q47_bag_row_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_Buffer_AG_Idx_Queue.mse_buf_queue_row_idx;
                assign q47_bag_col_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_Buffer_AG_Idx_Queue.mse_buf_queue_col_idx;
                assign q47_bag_row_tag_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_Buffer_AG_Idx_Queue.mse_buf_queue_row_tag;
                assign q47_bag_col_tag_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_Buffer_AG_Idx_Queue.mse_buf_queue_col_tag;
                assign q47_rdag_wr_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.buf_ag_ob_wr_en &
                    !u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.buf_ag_ob_full;
                assign q47_rdag_rd_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.buf_ag_ob_rd_en &
                    !u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.buf_ag_ob_empty;
                assign q47_rdag_empty_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.buf_ag_ob_empty;
                assign q47_rdag_full_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.buf_ag_ob_full;
                assign q47_rdag_rreq_hs_mon[q47_group][q47_slice] =
                    (|u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.mse2buf_rreq_valid) &
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.buf2mse_rreq_ready;
                assign q47_wr_req_hs_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_data_chl_req_valid &
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_data_chl_req_ready;
                assign q47_wr_prepared_wr_hs_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_data_chl_prepared_data_wr_hs;
                assign q47_wr_prepared_valid_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_data_chl_prepared_data_vld;
                assign q47_wr_queue_empty_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_chl_queue_empty;
                assign q47_wr_queue_full_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_chl_queue_full;
                assign q47_wr_ob_wr_hs_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_chl_ob_wr_hs;
                assign q47_wr_ob_rd_hs_mon[q47_group][q47_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q47_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q47_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_chl_ob_rd_hs;
            end
        end
    endgenerate

    integer q47_stage_index;
    integer q47_stage_seen_sg;
    logic q47_exec_d;
    longint unsigned q47_mse0_addr_hs, q47_mse0_req_hs;
    longint unsigned q47_mse0_meta_hs, q47_mse0_consume_hs;
    longint unsigned q47_mse0_buf_hs, q47_ga_input_hs, q47_ga_output_hs;
    longint unsigned q47_buf5_wr_hs, q47_buf5_rd_hs;
    longint unsigned q47_bagq_enq, q47_bagq_deq;
    longint unsigned q47_rdag_enq, q47_rdag_deq, q47_rdag_rreq;
    longint unsigned q47_wr_req_hs, q47_wr_prepared_hs;
    longint unsigned q47_wr_ob_enq [0:`MSE_REQ_CHL_NUM-1];
    longint unsigned q47_wr_ob_deq [0:`MSE_REQ_CHL_NUM-1];
    longint unsigned q47_mse4_req_hs [0:`MSE_REQ_CHL_NUM-1];
    longint unsigned q47_mse4_wdata_hs [0:`MSE_REQ_CHL_NUM-1];

    initial begin
        q47_stage_index = 0;
        q47_stage_seen_sg = 0;
        q47_exec_d = 1'b0;
    end

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        if (!u_NDP_Top_new.rst_n_db) begin
            q47_stage_index = 0;
            q47_exec_d = 1'b0;
        end
        else if (return_obs_enabled) begin
            if (return_obs_sem_exec_start_mon[return_obs_group_id]
                    [return_obs_local_slice_id] && !q47_exec_d)
                q47_stage_index++;
            q47_exec_d = return_obs_sem_exec_start_mon[return_obs_group_id]
                [return_obs_local_slice_id];
            if (return_obs_active && q47_stage_index == 6 &&
                (return_obs_active_cycles % return_obs_heartbeat_period) == 0) begin
                $fdisplay(return_obs_fd,
                    "%0t | TAILROUND_FLOW | stage=6 active_cycles=%0d mse0_addr=%0d mse0_req=%0d mse0_meta=%0d mse0_consume=%0d mse0_buf=%0d ga_in=%0d ga_out=%0d buf5_wr=%0d buf5_rd=%0d bag_enq=%0d bag_deq=%0d rdag_enq=%0d rdag_deq=%0d rdag_rreq=%0d wr_req=%0d wr_prepared=%0d wr_ob_enq0=%0d wr_ob_enq1=%0d wr_ob_deq0=%0d wr_ob_deq1=%0d mse4_req0=%0d mse4_req1=%0d mse4_wdata0=%0d mse4_wdata1=%0d",
                    $time, return_obs_active_cycles, q47_mse0_addr_hs,
                    q47_mse0_req_hs, q47_mse0_meta_hs,
                    q47_mse0_consume_hs, q47_mse0_buf_hs,
                    q47_ga_input_hs, q47_ga_output_hs, q47_buf5_wr_hs,
                    q47_buf5_rd_hs, q47_bagq_enq, q47_bagq_deq,
                    q47_rdag_enq, q47_rdag_deq, q47_rdag_rreq,
                    q47_wr_req_hs, q47_wr_prepared_hs,
                    q47_wr_ob_enq[0], q47_wr_ob_enq[1],
                    q47_wr_ob_deq[0], q47_wr_ob_deq[1],
                    q47_mse4_req_hs[0], q47_mse4_req_hs[1],
                    q47_mse4_wdata_hs[0], q47_mse4_wdata_hs[1]);
                $fdisplay(return_obs_fd,
                    "%0t | TAILROUND_STATE | buf5_wready=%0b buf5_rready=%0b bag_empty=%0b bag_full=%0b rdag_empty=%0b rdag_full=%0b wr_queue_empty=%0b wr_queue_full=%0b wr_prepared_valid=%0b row=0x%0h col=0x%0h row_tag=0x%0h col_tag=0x%0h",
                    $time,
                    q47_buf5_wready_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_buf5_rready_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_bagq_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_bagq_full_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_rdag_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_rdag_full_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_wr_queue_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_wr_queue_full_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_wr_prepared_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_bag_row_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_bag_col_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_bag_row_tag_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_bag_col_tag_mon[return_obs_group_id][return_obs_local_slice_id]);
                $fflush(return_obs_fd);
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or negedge u_NDP_Top_new.rst_n_sg) begin
        if (!u_NDP_Top_new.rst_n_sg || q47_stage_seen_sg != q47_stage_index) begin
            q47_stage_seen_sg = q47_stage_index;
            q47_mse0_addr_hs = 0; q47_mse0_req_hs = 0;
            q47_mse0_meta_hs = 0; q47_mse0_consume_hs = 0;
            q47_mse0_buf_hs = 0; q47_ga_input_hs = 0; q47_ga_output_hs = 0;
            q47_buf5_wr_hs = 0; q47_buf5_rd_hs = 0;
            q47_bagq_enq = 0; q47_bagq_deq = 0;
            q47_rdag_enq = 0; q47_rdag_deq = 0; q47_rdag_rreq = 0;
            q47_wr_req_hs = 0; q47_wr_prepared_hs = 0;
            for (int q47_ch = 0; q47_ch < `MSE_REQ_CHL_NUM; q47_ch++) begin
                q47_wr_ob_enq[q47_ch] = 0; q47_wr_ob_deq[q47_ch] = 0;
                q47_mse4_req_hs[q47_ch] = 0; q47_mse4_wdata_hs[q47_ch] = 0;
            end
        end
        else if (return_obs_enabled && return_obs_active && q47_stage_index == 6) begin
            for (int q47_ch = 0; q47_ch < `MSE_REQ_CHL_NUM; q47_ch++) begin
                if (return_obs_mse0_ob_hs_mon[return_obs_group_id]
                        [return_obs_local_slice_id][q47_ch]) q47_mse0_addr_hs++;
                if (local_req_hs[return_obs_group_id][return_obs_local_slice_id]
                        [0][q47_ch]) q47_mse0_req_hs++;
                if (local_req_hs[return_obs_group_id][return_obs_local_slice_id]
                        [4][q47_ch]) q47_mse4_req_hs[q47_ch]++;
                if (local_wdata_hs[return_obs_group_id][return_obs_local_slice_id]
                        [4][q47_ch]) q47_mse4_wdata_hs[q47_ch]++;
                if (q47_wr_ob_wr_hs_mon[return_obs_group_id]
                        [return_obs_local_slice_id][q47_ch]) q47_wr_ob_enq[q47_ch]++;
                if (q47_wr_ob_rd_hs_mon[return_obs_group_id]
                        [return_obs_local_slice_id][q47_ch]) q47_wr_ob_deq[q47_ch]++;
            end
            if (return_obs_mse0_meta_valid_mon[return_obs_group_id]
                    [return_obs_local_slice_id] &&
                return_obs_mse0_meta_ready_mon[return_obs_group_id]
                    [return_obs_local_slice_id]) q47_mse0_meta_hs++;
            if (|return_obs_mse0_data_consume_mon[return_obs_group_id]
                    [return_obs_local_slice_id]) q47_mse0_consume_hs++;
            if (return_obs_mse0_buf_hs_mon[return_obs_group_id]
                    [return_obs_local_slice_id]) q47_mse0_buf_hs++;
            for (int q47_row = 0; q47_row < `GA_ROW_PE_NUM; q47_row++) begin
                for (int q47_slot = 0; q47_slot < 2; q47_slot++) begin
                    if (return_obs_ga_p0_enable_mon[return_obs_group_id]
                            [return_obs_local_slice_id][q47_row][q47_slot] &&
                        return_obs_ga_input_valid_mon[return_obs_group_id]
                            [return_obs_local_slice_id][q47_row][q47_slot])
                        q47_ga_input_hs++;
                    if (return_obs_ga_outbuffer_wr_mon[return_obs_group_id]
                            [return_obs_local_slice_id][q47_row][q47_slot])
                        q47_ga_output_hs++;
                end
            end
            if ((|return_obs_buf45_wr_en_mon[return_obs_group_id]
                    [return_obs_local_slice_id][1]) &&
                q47_buf5_wready_mon[return_obs_group_id][return_obs_local_slice_id])
                q47_buf5_wr_hs++;
            if ((|return_obs_buf45_rd_en_mon[return_obs_group_id]
                    [return_obs_local_slice_id][1]) &&
                q47_buf5_rready_mon[return_obs_group_id][return_obs_local_slice_id])
                q47_buf5_rd_hs++;
            if (q47_bagq_wr_mon[return_obs_group_id][return_obs_local_slice_id] &&
                !q47_bagq_full_mon[return_obs_group_id][return_obs_local_slice_id])
                q47_bagq_enq++;
            if (q47_bagq_rd_mon[return_obs_group_id][return_obs_local_slice_id] &&
                !q47_bagq_empty_mon[return_obs_group_id][return_obs_local_slice_id])
                q47_bagq_deq++;
            if (q47_rdag_wr_mon[return_obs_group_id][return_obs_local_slice_id])
                q47_rdag_enq++;
            if (q47_rdag_rd_mon[return_obs_group_id][return_obs_local_slice_id])
                q47_rdag_deq++;
            if (q47_rdag_rreq_hs_mon[return_obs_group_id][return_obs_local_slice_id])
                q47_rdag_rreq++;
            if (q47_wr_req_hs_mon[return_obs_group_id][return_obs_local_slice_id])
                q47_wr_req_hs++;
            if (q47_wr_prepared_wr_hs_mon[return_obs_group_id]
                    [return_obs_local_slice_id]) q47_wr_prepared_hs++;
        end
    end
