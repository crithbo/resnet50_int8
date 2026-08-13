// QLinearAdd node0007 v52 bounded tail_round queue-flow observer.
//
// Package-local and read-only.  All progress records below are emitted only
// from accepted events in clk_sg.  The clk_db snapshot is state only.

    bit q52_enabled;
    bit q52_marker_emitted;
    integer q52_event_budget;

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`MSE_BQ_INPORT_NUM-1:0] q52_bag_valid_mask_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q52_bag_all_match_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [2:0] q52_rdag_count_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q52_rdag_wr_ptr_mon, q52_rdag_rd_ptr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`MSE_BUF_REQ_NUM-1:0] q52_rdag_rreq_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q52_rdag_buf_ready_mon, q52_rdag_wr_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_ROW_ADDR_WIDTH-1:0] q52_rdag_row_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`MSE_BUF_REQ_NUM-1:0][`BUFFER_COL_ADDR_WIDTH-1:0] q52_rdag_col_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [4:0] q52_wr_prepared_count_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q52_wr_data_valid_mon, q52_wr_buf_rvalid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        q52_wr_hold_valid_mon, q52_wr_sel_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`MSE_REQ_CHL_NUM-1:0] q52_wr_ob_valid_mon;

    generate
        for (genvar q52_group = 0; q52_group < `SLICE_GROUP_SIZE;
             q52_group++) begin : Q52_GROUP_GEN
            for (genvar q52_slice = 0; q52_slice < `SLICE_GROUP_NUM;
                 q52_slice++) begin : Q52_SLICE_GEN
                assign q52_bag_valid_mask_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_Buffer_AG_Idx_Queue.buf_idx_valid_bit_masked;
                assign q52_bag_all_match_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_Buffer_AG_Idx_Queue.buf_all_idx_matched;
                assign q52_rdag_count_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.buf_ag_ob_cnt;
                assign q52_rdag_wr_ptr_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.buf_ag_ob_wr_ptr;
                assign q52_rdag_rd_ptr_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.buf_ag_ob_rd_ptr;
                assign q52_rdag_rreq_valid_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.mse2buf_rreq_valid;
                assign q52_rdag_buf_ready_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.buf2mse_rreq_ready;
                assign q52_rdag_wr_ready_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.wr_data_chl_ready;
                assign q52_rdag_row_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.mse2buf_rreq_row_addr;
                assign q52_rdag_col_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_RD_Buffer_AG.mse2buf_rreq_col_addr;
                assign q52_wr_prepared_count_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_data_chl_prepared_data_cnt;
                assign q52_wr_data_valid_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_data_chl_data_vld;
                assign q52_wr_buf_rvalid_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.buf2mse_rvalid;
                assign q52_wr_hold_valid_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_data_chl_hold_data_vld;
                assign q52_wr_sel_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_chl_ob_sel;
                assign q52_wr_ob_valid_mon[q52_group][q52_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q52_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q52_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Data_Channel.wr_chl_ob_vld;
            end
        end
    endgenerate

    initial begin
        q52_enabled = $test$plusargs("QADD_TAILROUND_QUEUEFLOW");
        q52_marker_emitted = 1'b0;
        q52_event_budget = 96;
    end

    always @(posedge u_NDP_Top_new.clk_db) begin
        if (q52_enabled && return_obs_enabled && return_obs_fd != 0 &&
            !q52_marker_emitted) begin
            $fdisplay(return_obs_fd,
            "# QADD_TAILROUND_QUEUEFLOW_V52 enabled=1 event_budget=96 source_clock=clk_sg snapshot_clock=clk_db instance=%m");
            $fflush(return_obs_fd);
            q52_marker_emitted = 1'b1;
        end
        if (q52_enabled && return_obs_enabled && return_obs_active &&
            return_obs_fd != 0 && q47_stage_index == 1 &&
            (return_obs_active_cycles % return_obs_heartbeat_period) == 0) begin
            $fdisplay(return_obs_fd,
                "%0t | Q52_STATE | stage=1 bag_valid=0x%0h bag_match=%0b bag_empty=%0b bag_full=%0b rdag_count=%0d rdag_wr_ptr=%0b rdag_rd_ptr=%0b rdag_empty=%0b rdag_full=%0b rreq_valid=0x%0h buf_ready=%0b wr_ready=%0b rreq_row=0x%0h rreq_col=0x%0h prepared_count=%0d prepared_valid=%0b data_valid=%0b buf_rvalid=%0b hold_valid=%0b wr_sel=%0b ob_valid=0x%0h wr_queue_empty=%0b wr_queue_full=%0b",
                $time,
                q52_bag_valid_mask_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_bag_all_match_mon[return_obs_group_id][return_obs_local_slice_id],
                q47_bagq_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                q47_bagq_full_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_rdag_count_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_rdag_wr_ptr_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_rdag_rd_ptr_mon[return_obs_group_id][return_obs_local_slice_id],
                q47_rdag_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                q47_rdag_full_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_rdag_rreq_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_rdag_buf_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_rdag_wr_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_rdag_row_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_rdag_col_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_wr_prepared_count_mon[return_obs_group_id][return_obs_local_slice_id],
                q47_wr_prepared_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_wr_data_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_wr_buf_rvalid_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_wr_hold_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_wr_sel_mon[return_obs_group_id][return_obs_local_slice_id],
                q52_wr_ob_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                q47_wr_queue_empty_mon[return_obs_group_id][return_obs_local_slice_id],
                q47_wr_queue_full_mon[return_obs_group_id][return_obs_local_slice_id]);
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (q52_enabled && return_obs_enabled && return_obs_active &&
            return_obs_fd != 0 && q47_stage_index == 1 &&
            q52_event_budget > 0) begin
            if (q52_event_budget > 0 &&
                q47_bagq_wr_mon[return_obs_group_id][return_obs_local_slice_id] &&
                !q47_bagq_full_mon[return_obs_group_id][return_obs_local_slice_id]) begin
                $fdisplay(return_obs_fd,
                    "%0t | Q52_EVENT | inst=%m kind=BAG_ENQ row=0x%0h col=0x%0h row_tag=0x%0h col_tag=0x%0h valid=0x%0h match=%0b",
                    $time,
                    q47_bag_row_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_bag_col_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_bag_row_tag_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_bag_col_tag_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_bag_valid_mask_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_bag_all_match_mon[return_obs_group_id][return_obs_local_slice_id]);
                q52_event_budget--;
            end
            if (q52_event_budget > 0 &&
                q47_bagq_rd_mon[return_obs_group_id][return_obs_local_slice_id] &&
                !q47_bagq_empty_mon[return_obs_group_id][return_obs_local_slice_id]) begin
                $fdisplay(return_obs_fd, "%0t | Q52_EVENT | inst=%m kind=BAG_DEQ", $time);
                q52_event_budget--;
            end
            if (q52_event_budget > 0 &&
                q47_rdag_wr_mon[return_obs_group_id][return_obs_local_slice_id]) begin
                $fdisplay(return_obs_fd,
                    "%0t | Q52_EVENT | inst=%m kind=RDAG_ENQ count=%0d wr_ptr=%0b rd_ptr=%0b",
                    $time,
                    q52_rdag_count_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_rdag_wr_ptr_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_rdag_rd_ptr_mon[return_obs_group_id][return_obs_local_slice_id]);
                q52_event_budget--;
            end
            if (q52_event_budget > 0 &&
                q47_rdag_rd_mon[return_obs_group_id][return_obs_local_slice_id]) begin
                $fdisplay(return_obs_fd,
                    "%0t | Q52_EVENT | inst=%m kind=RDAG_DEQ count=%0d valid=0x%0h row=0x%0h col=0x%0h",
                    $time,
                    q52_rdag_count_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_rdag_rreq_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_rdag_row_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_rdag_col_mon[return_obs_group_id][return_obs_local_slice_id]);
                q52_event_budget--;
            end
            if (q52_event_budget > 0 &&
                q47_rdag_rreq_hs_mon[return_obs_group_id][return_obs_local_slice_id]) begin
                $fdisplay(return_obs_fd,
                    "%0t | Q52_EVENT | inst=%m kind=RDAG_RREQ valid=0x%0h row=0x%0h col=0x%0h",
                    $time,
                    q52_rdag_rreq_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_rdag_row_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_rdag_col_mon[return_obs_group_id][return_obs_local_slice_id]);
                q52_event_budget--;
            end
            if (q52_event_budget > 0 &&
                q47_wr_req_hs_mon[return_obs_group_id][return_obs_local_slice_id]) begin
                $fdisplay(return_obs_fd,
                    "%0t | Q52_EVENT | inst=%m kind=WR_REQ prepared_count=%0d prepared_valid=%0b sel=%0b queue_full=%0b",
                    $time,
                    q52_wr_prepared_count_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_wr_prepared_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_wr_sel_mon[return_obs_group_id][return_obs_local_slice_id],
                    q47_wr_queue_full_mon[return_obs_group_id][return_obs_local_slice_id]);
                q52_event_budget--;
            end
            if (q52_event_budget > 0 &&
                q47_wr_prepared_wr_hs_mon[return_obs_group_id][return_obs_local_slice_id]) begin
                $fdisplay(return_obs_fd,
                    "%0t | Q52_EVENT | inst=%m kind=WR_PREPARED prepared_count=%0d data_valid=%0b buf_rvalid=%0b hold_valid=%0b",
                    $time,
                    q52_wr_prepared_count_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_wr_data_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_wr_buf_rvalid_mon[return_obs_group_id][return_obs_local_slice_id],
                    q52_wr_hold_valid_mon[return_obs_group_id][return_obs_local_slice_id]);
                q52_event_budget--;
            end
            for (int q52_ch = 0; q52_ch < `MSE_REQ_CHL_NUM; q52_ch++) begin
                if (q52_event_budget > 0 &&
                    q47_wr_ob_wr_hs_mon[return_obs_group_id]
                        [return_obs_local_slice_id][q52_ch]) begin
                    $fdisplay(return_obs_fd,
                        "%0t | Q52_EVENT | inst=%m kind=WR_OB_ENQ channel=%0d sel=%0b ob_valid=0x%0h",
                        $time, q52_ch,
                        q52_wr_sel_mon[return_obs_group_id][return_obs_local_slice_id],
                        q52_wr_ob_valid_mon[return_obs_group_id][return_obs_local_slice_id]);
                    q52_event_budget--;
                end
                if (q52_event_budget > 0 &&
                    q47_wr_ob_rd_hs_mon[return_obs_group_id]
                        [return_obs_local_slice_id][q52_ch]) begin
                    $fdisplay(return_obs_fd,
                        "%0t | Q52_EVENT | inst=%m kind=WR_OB_DEQ channel=%0d ob_valid=0x%0h",
                        $time, q52_ch,
                        q52_wr_ob_valid_mon[return_obs_group_id][return_obs_local_slice_id]);
                    q52_event_budget--;
                end
                if (q52_event_budget > 0 &&
                    local_req_hs[return_obs_group_id][return_obs_local_slice_id]
                        [4][q52_ch]) begin
                    $fdisplay(return_obs_fd,
                        "%0t | Q52_EVENT | inst=%m kind=MSE4_REQ channel=%0d", $time, q52_ch);
                    q52_event_budget--;
                end
                if (q52_event_budget > 0 &&
                    local_wdata_hs[return_obs_group_id][return_obs_local_slice_id]
                        [4][q52_ch]) begin
                    $fdisplay(return_obs_fd,
                        "%0t | Q52_EVENT | inst=%m kind=MSE4_WDATA channel=%0d", $time, q52_ch);
                    q52_event_budget--;
                end
            end
            if (q52_event_budget < 0)
                q52_event_budget = 0;
            $fflush(return_obs_fd);
        end
    end
