// QLinearAdd node0007 Start_Comp -> first-request narrow observer.
//
// This file is appended to the package-local native_return_observer.svh.
// It is read-only and rate-limited to the base observer heartbeat.  Counts
// below advance only on qualified ready/valid handshakes or queue writes.

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_slice_start_run_mon;

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][4:0]
        qadd_fr_lc_enable_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][4:0]
        qadd_fr_lc_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][4:0]
        qadd_fr_lc_ready_mon;

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][2:0]
        qadd_fr_mse0_input_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][2:0]
        qadd_fr_mse0_input_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse0_match_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse0_empty_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse0_full_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse0_queue_wr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse0_ag_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse0_ag_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse0_req_enqueue_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse0_req_enqueue_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse0_req_enqueue_hs_mon;

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][2:0]
        qadd_fr_mse4_input_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][2:0]
        qadd_fr_mse4_input_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse4_match_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse4_empty_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse4_full_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        qadd_fr_mse4_queue_wr_mon;

    generate
        for (genvar qadd_fr_group = 0;
             qadd_fr_group < `SLICE_GROUP_SIZE;
             qadd_fr_group++) begin : QADD_FR_GROUP
            for (genvar qadd_fr_slice = 0;
                 qadd_fr_slice < `SLICE_GROUP_NUM;
                 qadd_fr_slice++) begin : QADD_FR_SLICE
                assign qadd_fr_slice_start_run_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.slice_start_run;

                // Frozen mapping:
                // logical LC1,LC0,LC3,LC2,LC4 -> physical LC2,4,6,13,18.
                assign qadd_fr_lc_enable_mon
                    [qadd_fr_group][qadd_fr_slice][0] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.IGA_LC[2]
                        .u_IGA_LC.iga_lc_enable;
                assign qadd_fr_lc_enable_mon
                    [qadd_fr_group][qadd_fr_slice][1] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.IGA_LC[4]
                        .u_IGA_LC.iga_lc_enable;
                assign qadd_fr_lc_enable_mon
                    [qadd_fr_group][qadd_fr_slice][2] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.IGA_LC[6]
                        .u_IGA_LC.iga_lc_enable;
                assign qadd_fr_lc_enable_mon
                    [qadd_fr_group][qadd_fr_slice][3] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.IGA_LC[13]
                        .u_IGA_LC.iga_lc_enable;
                assign qadd_fr_lc_enable_mon
                    [qadd_fr_group][qadd_fr_slice][4] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.IGA_LC[18]
                        .u_IGA_LC.iga_lc_enable;

                assign qadd_fr_lc_valid_mon
                    [qadd_fr_group][qadd_fr_slice][0] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.iga_lc_outport
                        [2][`IGA_LC_PORT_WIDTH-1];
                assign qadd_fr_lc_valid_mon
                    [qadd_fr_group][qadd_fr_slice][1] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.iga_lc_outport
                        [4][`IGA_LC_PORT_WIDTH-1];
                assign qadd_fr_lc_valid_mon
                    [qadd_fr_group][qadd_fr_slice][2] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.iga_lc_outport
                        [6][`IGA_LC_PORT_WIDTH-1];
                assign qadd_fr_lc_valid_mon
                    [qadd_fr_group][qadd_fr_slice][3] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.iga_lc_outport
                        [13][`IGA_LC_PORT_WIDTH-1];
                assign qadd_fr_lc_valid_mon
                    [qadd_fr_group][qadd_fr_slice][4] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.iga_lc_outport
                        [18][`IGA_LC_PORT_WIDTH-1];

                assign qadd_fr_lc_ready_mon
                    [qadd_fr_group][qadd_fr_slice][0] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.IGA_LC[2]
                        .u_IGA_LC.iga_lc_cnt_bp_post;
                assign qadd_fr_lc_ready_mon
                    [qadd_fr_group][qadd_fr_slice][1] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.IGA_LC[4]
                        .u_IGA_LC.iga_lc_cnt_bp_post;
                assign qadd_fr_lc_ready_mon
                    [qadd_fr_group][qadd_fr_slice][2] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.IGA_LC[6]
                        .u_IGA_LC.iga_lc_cnt_bp_post;
                assign qadd_fr_lc_ready_mon
                    [qadd_fr_group][qadd_fr_slice][3] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.IGA_LC[13]
                        .u_IGA_LC.iga_lc_cnt_bp_post;
                assign qadd_fr_lc_ready_mon
                    [qadd_fr_group][qadd_fr_slice][4] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_Index_Generation_Array.IGA_LC[18]
                        .u_IGA_LC.iga_lc_cnt_bp_post;

                assign qadd_fr_mse0_input_valid_mon
                    [qadd_fr_group][qadd_fr_slice] = {
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.mse_mem_queue_tag
                        [0][2][`SE_MEM_INPORT_TAG_WIDTH-1],
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.mse_mem_queue_tag
                        [0][1][`SE_MEM_INPORT_TAG_WIDTH-1],
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.mse_mem_queue_tag
                        [0][0][`SE_MEM_INPORT_TAG_WIDTH-1]};
                assign qadd_fr_mse0_input_ready_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.mse_mem_queue_bp_pre[0];
                assign qadd_fr_mse0_match_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_Memory_AG_Idx_Queue
                        .mem_all_idx_matched;
                assign qadd_fr_mse0_empty_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_Memory_AG_Idx_Queue
                        .mem_ag_idx_queue_empty;
                assign qadd_fr_mse0_full_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_Memory_AG_Idx_Queue
                        .mem_ag_idx_queue_full;
                assign qadd_fr_mse0_queue_wr_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_Memory_AG_Idx_Queue
                        .mem_ag_idx_queue_wr_en;
                assign qadd_fr_mse0_ag_valid_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE
                        .u_Memory_RD_Stream_Engine.mse_mem_ag_tag_valid;
                assign qadd_fr_mse0_ag_ready_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE
                        .u_Memory_RD_Stream_Engine.mse_mem_ag_bp_post;
                assign qadd_fr_mse0_req_enqueue_valid_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_RD_Memory_AG
                        .mem_ag_ob_vld_in;
                assign qadd_fr_mse0_req_enqueue_ready_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_RD_Memory_AG
                        .mem_ag_ob_bp_pre;
                assign qadd_fr_mse0_req_enqueue_hs_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    |u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[0].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_RD_Memory_AG
                        .mem_ag_ob_chl_hs;

                assign qadd_fr_mse4_input_valid_mon
                    [qadd_fr_group][qadd_fr_slice] = {
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.mse_mem_queue_tag
                        [4][2][`SE_MEM_INPORT_TAG_WIDTH-1],
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.mse_mem_queue_tag
                        [4][1][`SE_MEM_INPORT_TAG_WIDTH-1],
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.mse_mem_queue_tag
                        [4][0][`SE_MEM_INPORT_TAG_WIDTH-1]};
                assign qadd_fr_mse4_input_ready_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.mse_mem_queue_bp_pre[4];
                assign qadd_fr_mse4_match_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE
                        .u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue
                        .mem_all_idx_matched;
                assign qadd_fr_mse4_empty_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE
                        .u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue
                        .mem_ag_idx_queue_empty;
                assign qadd_fr_mse4_full_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE
                        .u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue
                        .mem_ag_idx_queue_full;
                assign qadd_fr_mse4_queue_wr_mon
                    [qadd_fr_group][qadd_fr_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [qadd_fr_group].u_slice_with_datahub_mc_group
                        .slice_group_gen[qadd_fr_slice].u_slice_wrapper
                        .u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE
                        .u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue
                        .mem_ag_idx_queue_wr_en;
            end
        end
    endgenerate

    longint unsigned qadd_fr_slice_start_count;
    longint unsigned qadd_fr_lc_hs_count [0:4];
    longint unsigned qadd_fr_mse0_input_hs_count [0:2];
    longint unsigned qadd_fr_mse4_input_hs_count [0:2];
    longint unsigned qadd_fr_mse0_queue_wr_count;
    longint unsigned qadd_fr_mse4_queue_wr_count;
    longint unsigned qadd_fr_mse0_ag_hs_count;
    longint unsigned qadd_fr_mse0_req_enqueue_count;
    logic qadd_fr_slice_start_run_prev;

    initial begin
        qadd_fr_slice_start_count = 0;
        qadd_fr_mse0_queue_wr_count = 0;
        qadd_fr_mse4_queue_wr_count = 0;
        qadd_fr_mse0_ag_hs_count = 0;
        qadd_fr_mse0_req_enqueue_count = 0;
        qadd_fr_slice_start_run_prev = 0;
        for (int qadd_fr_i = 0; qadd_fr_i < 5; qadd_fr_i++)
            qadd_fr_lc_hs_count[qadd_fr_i] = 0;
        for (int qadd_fr_i = 0; qadd_fr_i < 3; qadd_fr_i++) begin
            qadd_fr_mse0_input_hs_count[qadd_fr_i] = 0;
            qadd_fr_mse4_input_hs_count[qadd_fr_i] = 0;
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (
            u_NDP_Top_new.rst_n_sg &&
            return_obs_enabled &&
            return_obs_active &&
            return_obs_fd != 0
        ) begin
            if (
                qadd_fr_slice_start_run_mon
                    [return_obs_group_id][return_obs_local_slice_id] &&
                !qadd_fr_slice_start_run_prev
            )
                qadd_fr_slice_start_count++;
            qadd_fr_slice_start_run_prev =
                qadd_fr_slice_start_run_mon
                    [return_obs_group_id][return_obs_local_slice_id];
            for (int qadd_fr_i = 0; qadd_fr_i < 5; qadd_fr_i++) begin
                if (
                    qadd_fr_lc_enable_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [qadd_fr_i] &&
                    qadd_fr_lc_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [qadd_fr_i] &&
                    qadd_fr_lc_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [qadd_fr_i]
                )
                    qadd_fr_lc_hs_count[qadd_fr_i]++;
            end
            for (int qadd_fr_i = 0; qadd_fr_i < 3; qadd_fr_i++) begin
                if (
                    qadd_fr_mse0_input_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [qadd_fr_i] &&
                    qadd_fr_mse0_input_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [qadd_fr_i]
                )
                    qadd_fr_mse0_input_hs_count[qadd_fr_i]++;
                if (
                    qadd_fr_mse4_input_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [qadd_fr_i] &&
                    qadd_fr_mse4_input_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [qadd_fr_i]
                )
                    qadd_fr_mse4_input_hs_count[qadd_fr_i]++;
            end
            if (qadd_fr_mse0_queue_wr_mon
                [return_obs_group_id][return_obs_local_slice_id])
                qadd_fr_mse0_queue_wr_count++;
            if (qadd_fr_mse4_queue_wr_mon
                [return_obs_group_id][return_obs_local_slice_id])
                qadd_fr_mse4_queue_wr_count++;
            if (
                qadd_fr_mse0_ag_valid_mon
                    [return_obs_group_id][return_obs_local_slice_id] &&
                qadd_fr_mse0_ag_ready_mon
                    [return_obs_group_id][return_obs_local_slice_id]
            )
                qadd_fr_mse0_ag_hs_count++;
            if (qadd_fr_mse0_req_enqueue_hs_mon
                [return_obs_group_id][return_obs_local_slice_id])
                qadd_fr_mse0_req_enqueue_count++;

            if (
                return_obs_active_cycles != 0 &&
                (return_obs_active_cycles %
                    return_obs_heartbeat_period) == 0
            ) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | FIRST_REQUEST_CHAIN | slice=%0d active_cycles=%0d slice_start=%0d lc_enable=0x%0h lc_valid=0x%0h lc_ready=0x%0h lc_hs=%0d,%0d,%0d,%0d,%0d mse0_in_valid=0x%0h mse0_in_ready=0x%0h mse0_in_hs=%0d,%0d,%0d mse0_match=%0b mse0_empty=%0b mse0_full=%0b mse0_queue_wr=%0d mse0_ag_valid=%0b mse0_ag_ready=%0b mse0_ag_hs=%0d mse0_req_enq_valid=%0b mse0_req_enq_ready=%0b mse0_req_enq=%0d mse4_in_valid=0x%0h mse4_in_ready=0x%0h mse4_in_hs=%0d,%0d,%0d mse4_match=%0b mse4_empty=%0b mse4_full=%0b mse4_queue_wr=%0d",
                    $time,
                    return_obs_slice_id,
                    return_obs_active_cycles,
                    qadd_fr_slice_start_count,
                    qadd_fr_lc_enable_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_lc_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_lc_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_lc_hs_count[0],
                    qadd_fr_lc_hs_count[1],
                    qadd_fr_lc_hs_count[2],
                    qadd_fr_lc_hs_count[3],
                    qadd_fr_lc_hs_count[4],
                    qadd_fr_mse0_input_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse0_input_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse0_input_hs_count[0],
                    qadd_fr_mse0_input_hs_count[1],
                    qadd_fr_mse0_input_hs_count[2],
                    qadd_fr_mse0_match_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse0_empty_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse0_full_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse0_queue_wr_count,
                    qadd_fr_mse0_ag_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse0_ag_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse0_ag_hs_count,
                    qadd_fr_mse0_req_enqueue_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse0_req_enqueue_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse0_req_enqueue_count,
                    qadd_fr_mse4_input_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse4_input_ready_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse4_input_hs_count[0],
                    qadd_fr_mse4_input_hs_count[1],
                    qadd_fr_mse4_input_hs_count[2],
                    qadd_fr_mse4_match_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse4_empty_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse4_full_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    qadd_fr_mse4_queue_wr_count
                );
                $fflush(return_obs_fd);
            end
        end
    end
