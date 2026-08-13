// QLinearAdd node0007 v53 bounded Buffer5 selected-read-ready observer.
//
// All transactional events are sampled on clk_sg.  clk_db records only state.
// The selected slice is identified by the existing return observer group/slice
// contract; no procedural-scope %m string is emitted.

    bit q53_enabled;
    bit q53_marker_emitted;
    integer q53_event_budget;

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0] q53_pingpong_sel_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0] q53_ready0_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0] q53_ready1_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0] q53_selected_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0] q53_mrm_ready5_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_BANK_NUM-1:0] q53_req_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0] q53_req_rw_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_BANK_ADDR_WIDTH-1:0] q53_req_addr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_BANK_NUM-1:0][`BUFFER_STRB_WIDTH-1:0] q53_req_strb_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_BANK_NUM-1:0] q53_rd_en_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_BANK_NUM-1:0] q53_bank_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_BANK_NUM-1:0][`VALID_BUFFER_BANK_WIDTH-1:0]
        q53_valid_at_req_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0] q53_rreq_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_BANK_NUM-1:0] q53_buffer_mask_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0] q53_nrm_barrier_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_BANK_NUM-1:0] q53_valid_wr_en_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0] q53_buf_wready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_BANK_ADDR_WIDTH-1:0] q53_buf_wr_addr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_BANK_NUM-1:0] q53_valid_clear_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_BANK_NUM-1:0][`BUFFER_BANK_ADDR_WIDTH-1:0]
        q53_valid_clr_addr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`BUFFER_BANK_NUM-1:0][`BUFFER_BANK_DATA_NUM-1:0]
        q53_valid_clr_mask_mon;

    generate
        for (genvar q53_group = 0; q53_group < `SLICE_GROUP_SIZE;
             q53_group++) begin : Q53_GROUP_GEN
            for (genvar q53_slice = 0; q53_slice < `SLICE_GROUP_NUM;
                 q53_slice++) begin : Q53_SLICE_GEN
                assign q53_pingpong_sel_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .mse_wreq_pingpong_sel[0];
                assign q53_ready0_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .buf2se_mem_rreq_ready[0][0];
                assign q53_ready1_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .buf2se_mem_rreq_ready[0][1];
                assign q53_selected_ready_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .buf2mse_rreq_ready[0];
                assign q53_mrm_ready5_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .mrm2se_req_ready[5];
                assign q53_req_valid_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.mrm2buf_req_valid;
                assign q53_req_rw_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.mrm2buf_req_rw;
                assign q53_req_addr_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.mrm2buf_req_addr;
                assign q53_req_strb_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.mrm2buf_req_strb;
                assign q53_rd_en_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.mrm2buf_rd_en;
                assign q53_bank_ready_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer
                        .buf2mrm_rreq_bank_ready;
                assign q53_rreq_ready_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer
                        .buf2mrm_rreq_ready;
                assign q53_buffer_mask_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.buffer_mask;
                assign q53_nrm_barrier_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.nrm2buf_rd_barrier;
                assign q53_valid_wr_en_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.valid_buf_wr_en;
                assign q53_buf_wready_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf_wreq_ready;
                assign q53_buf_wr_addr_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.buf_wr_addr;
                assign q53_valid_clear_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.valid_buf_clear;
                assign q53_valid_clr_addr_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.valid_buf_clr_addr;
                assign q53_valid_clr_mask_mon[q53_group][q53_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer.valid_buf_clr_mask;
                for (genvar q53_bank = 0; q53_bank < `BUFFER_BANK_NUM;
                     q53_bank++) begin : Q53_BANK_GEN
                    assign q53_valid_at_req_mon[q53_group][q53_slice][q53_bank] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[q53_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[q53_slice]
                            .u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer
                            .valid_buf[q53_bank]
                                [q53_req_addr_mon[q53_group][q53_slice]];
                end
            end
        end
    endgenerate

    initial begin
        q53_enabled = $test$plusargs("QADD_TAILROUND_BUFREADY");
        q53_marker_emitted = 1'b0;
        q53_event_budget = 96;
    end

    always @(posedge u_NDP_Top_new.clk_db) begin
        if (q53_enabled && return_obs_enabled && return_obs_fd != 0 &&
            !q53_marker_emitted) begin
            $fdisplay(return_obs_fd,
                "# QADD_TAILROUND_BUFREADY_V53 enabled=1 event_budget=96 source_clock=clk_sg snapshot_clock=clk_db owner=selected_return_observer_slice");
            $fflush(return_obs_fd);
            q53_marker_emitted = 1'b1;
        end
        if (q53_enabled && return_obs_enabled && return_obs_active &&
            return_obs_fd != 0 && q47_stage_index == 1 &&
            (return_obs_active_cycles % return_obs_heartbeat_period) == 0) begin
            $fdisplay(return_obs_fd,
                "%0t | Q53_STATE | stage=1 group=%0d local_slice=%0d pingpong=%0b ready0=%0b ready1=%0b selected_ready=%0b mrm_ready5=%0b req_valid=0x%0h req_rw=%0b req_addr=0x%0h req_strb=0x%0h rd_en=0x%0h bank_ready=0x%0h valid_at_req=0x%0h rreq_ready=%0b buffer_mask=0x%0h nrm_barrier=%0b",
                $time, return_obs_group_id, return_obs_local_slice_id,
                q53_pingpong_sel_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_ready0_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_ready1_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_selected_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_mrm_ready5_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_req_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_req_rw_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_req_addr_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_req_strb_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_rd_en_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_bank_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_valid_at_req_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_rreq_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_buffer_mask_mon[return_obs_group_id][return_obs_local_slice_id],
                q53_nrm_barrier_mon[return_obs_group_id][return_obs_local_slice_id]);
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (q53_enabled && return_obs_enabled && return_obs_active &&
            return_obs_fd != 0 && q47_stage_index == 1 &&
            q53_event_budget > 0) begin
            if ((|q53_valid_wr_en_mon[return_obs_group_id][return_obs_local_slice_id]) &&
                q53_buf_wready_mon[return_obs_group_id][return_obs_local_slice_id]) begin
                $fdisplay(return_obs_fd,
                    "%0t | Q53_EVENT | kind=BUF5_WRITE_ACCEPT wr_en=0x%0h row=0x%0h req_valid=0x%0h req_strb=0x%0h",
                    $time,
                    q53_valid_wr_en_mon[return_obs_group_id][return_obs_local_slice_id],
                    q53_buf_wr_addr_mon[return_obs_group_id][return_obs_local_slice_id],
                    q53_req_valid_mon[return_obs_group_id][return_obs_local_slice_id],
                    q53_req_strb_mon[return_obs_group_id][return_obs_local_slice_id]);
                q53_event_budget--;
            end
            if (q53_event_budget > 0 &&
                (|q53_valid_clear_mon[return_obs_group_id][return_obs_local_slice_id])) begin
                $fdisplay(return_obs_fd,
                    "%0t | Q53_EVENT | kind=BUF5_VALID_CLEAR clear=0x%0h row=0x%0h mask=0x%0h",
                    $time,
                    q53_valid_clear_mon[return_obs_group_id][return_obs_local_slice_id],
                    q53_valid_clr_addr_mon[return_obs_group_id][return_obs_local_slice_id],
                    q53_valid_clr_mask_mon[return_obs_group_id][return_obs_local_slice_id]);
                q53_event_budget--;
            end
            if (q53_event_budget > 0 &&
                (|q53_rd_en_mon[return_obs_group_id][return_obs_local_slice_id]) &&
                q53_rreq_ready_mon[return_obs_group_id][return_obs_local_slice_id]) begin
                $fdisplay(return_obs_fd,
                    "%0t | Q53_EVENT | kind=BUF5_READ_ACCEPT rd_en=0x%0h row=0x%0h strb=0x%0h bank_ready=0x%0h valid_at_req=0x%0h",
                    $time,
                    q53_rd_en_mon[return_obs_group_id][return_obs_local_slice_id],
                    q53_req_addr_mon[return_obs_group_id][return_obs_local_slice_id],
                    q53_req_strb_mon[return_obs_group_id][return_obs_local_slice_id],
                    q53_bank_ready_mon[return_obs_group_id][return_obs_local_slice_id],
                    q53_valid_at_req_mon[return_obs_group_id][return_obs_local_slice_id]);
                q53_event_budget--;
            end
            if (q53_event_budget < 0)
                q53_event_budget = 0;
            $fflush(return_obs_fd);
        end
    end

