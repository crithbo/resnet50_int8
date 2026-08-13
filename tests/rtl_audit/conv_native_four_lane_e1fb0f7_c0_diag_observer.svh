// Package-local read-only observer for the Conv node0004 native-four-lane
// historical-v1 c0 exec-to-slice-finish stall.  It observes the full frozen
// c0 causal slice and never drives DUT/TB state or simulation termination.

logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
    n4d_cfg_start_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
    n4d_cfg_finish_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
    n4d_exec_start_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
    n4d_slice_finish_mon;

logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_RD_STREAM_ENGINE_NUM-1:0]
      [`MSE_REQ_CHL_NUM-1:0] n4d_rd_ib_wr_hs_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_RD_STREAM_ENGINE_NUM-1:0]
      [`MSE_REQ_CHL_NUM-1:0] n4d_rd_ib_rd_hs_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_RD_STREAM_ENGINE_NUM-1:0] n4d_rd_meta_hs_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_RD_STREAM_ENGINE_NUM-1:0] n4d_rd_prep_wr_hs_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_RD_STREAM_ENGINE_NUM-1:0] n4d_rd_prep_rd_hs_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_RD_STREAM_ENGINE_NUM-1:0] n4d_rd_buf_hs_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_RD_STREAM_ENGINE_NUM-1:0] n4d_rd_queue_full_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_RD_STREAM_ENGINE_NUM-1:0] n4d_rd_queue_empty_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_RD_STREAM_ENGINE_NUM-1:0][5:0] n4d_rd_prep_count_mon;

logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_STREAM_ENGINE_NUM-1:0] n4d_bag_wr_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_STREAM_ENGINE_NUM-1:0] n4d_bag_rd_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_STREAM_ENGINE_NUM-1:0] n4d_bag_full_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`MEMORY_STREAM_ENGINE_NUM-1:0] n4d_bag_empty_mon;

logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`BUFFER_NUM-1:0] n4d_arm_req_hs_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`BUFFER_NUM-1:0] n4d_arm_resp_hs_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`BUFFER_NUM-1:0] n4d_arm_hold_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`BUFFER_NUM-1:0] n4d_arm_bp_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`BUFFER_NUM-1:0] n4d_arm_finish_mon;

logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`NEIGHBOR_STREAM_ENGINE_NUM-1:0] n4d_nse_req_hs_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`NEIGHBOR_STREAM_ENGINE_NUM-1:0] n4d_nse_in_hs_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`NEIGHBOR_STREAM_ENGINE_NUM-1:0] n4d_nse_out_hs_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`NEIGHBOR_STREAM_ENGINE_NUM-1:0] n4d_nse_full_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`NEIGHBOR_STREAM_ENGINE_NUM-1:0] n4d_nse_empty_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`NEIGHBOR_STREAM_ENGINE_NUM-1:0] n4d_nse_finish_mon;

logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`SA_INPORT_GROUP_NUM-1:0][`SA_PORT_HANDLE_BUF_NUM-1:0]
      [`ARRAY_PORT_TAG-1:0] n4d_buf2sa_tag_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`SA_INPORT_GROUP_NUM-1:0][`SA_PORT_HANDLE_BUF_NUM-1:0]
      n4d_sa_input_bp_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`SA_OUTPORT_GROUP_NUM-1:0][`SA_PORT_HANDLE_BUF_NUM-1:0]
      [`ARRAY_PORT_TAG-1:0] n4d_sa2buf_tag_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`SA_OUTPORT_GROUP_NUM-1:0][`SA_PORT_HANDLE_BUF_NUM-1:0]
      n4d_buf_accept_sa_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [1:0][`BUFFER_BANK_NUM-1:0] n4d_buf45_wr_en_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [1:0][`BUFFER_BANK_NUM-1:0] n4d_buf45_rd_en_mon;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      n4d_mse4_idx_hs_mon;

generate
    for (genvar n4d_group = 0;
         n4d_group < `SLICE_GROUP_SIZE;
         n4d_group++) begin : N4D_GROUP_GEN
        for (genvar n4d_slice = 0;
             n4d_slice < `SLICE_GROUP_NUM;
             n4d_slice++) begin : N4D_SLICE_GEN
            assign n4d_cfg_start_mon[n4d_group][n4d_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager
                    .sem2scm_cfg_start;
            assign n4d_cfg_finish_mon[n4d_group][n4d_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager
                    .scm2sem_cfg_finish;
            assign n4d_exec_start_mon[n4d_group][n4d_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager
                    .sem2iga_exec_start;
            assign n4d_slice_finish_mon[n4d_group][n4d_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager
                    .slice_cmpt_finish;

            for (genvar n4d_rd = 0;
                 n4d_rd < `MEMORY_RD_STREAM_ENGINE_NUM;
                 n4d_rd++) begin : N4D_RD_GEN
                assign n4d_rd_ib_wr_hs_mon
                    [n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_RD_Data_Channel
                        .rd_chl_ib_wr_hs;
                assign n4d_rd_ib_rd_hs_mon
                    [n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_RD_Data_Channel
                        .rd_chl_ib_rd_hs;
                assign n4d_rd_meta_hs_mon
                    [n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.rd_data_chl_req_valid &
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.rd_data_chl_req_ready;
                assign n4d_rd_prep_wr_hs_mon
                    [n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_RD_Data_Channel
                        .rd_data_chl_prepared_data_wr_hs;
                assign n4d_rd_prep_rd_hs_mon
                    [n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_RD_Data_Channel
                        .rd_data_chl_prepared_data_rd_hs;
                assign n4d_rd_buf_hs_mon
                    [n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.mse2buf_wvalid &
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.buf2mse_wreq_ready;
                assign n4d_rd_queue_full_mon
                    [n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_RD_Data_Channel
                        .rd_chl_queue_full;
                assign n4d_rd_queue_empty_mon
                    [n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_RD_Data_Channel
                        .rd_chl_queue_empty;
                assign n4d_rd_prep_count_mon
                    [n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_RD_Data_Channel
                        .rd_data_chl_prepared_data_cnt;
                assign n4d_bag_wr_mon[n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_Buffer_AG_Idx_Queue
                        .buf_ag_idx_queue_wr_en;
                assign n4d_bag_rd_mon[n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_Buffer_AG_Idx_Queue
                        .buf_ag_idx_queue_rd_en;
                assign n4d_bag_full_mon[n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_Buffer_AG_Idx_Queue
                        .buf_ag_idx_queue_full;
                assign n4d_bag_empty_mon[n4d_group][n4d_slice][n4d_rd] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[n4d_rd].RD_MSE
                        .u_Memory_RD_Stream_Engine.u_Buffer_AG_Idx_Queue
                        .buf_ag_idx_queue_empty;
            end

            assign n4d_bag_wr_mon[n4d_group][n4d_slice][4] =
                u_NDP_Top_new
                    .slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                    .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                    .u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en;
            assign n4d_bag_rd_mon[n4d_group][n4d_slice][4] =
                u_NDP_Top_new
                    .slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                    .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                    .u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en;
            assign n4d_bag_full_mon[n4d_group][n4d_slice][4] =
                u_NDP_Top_new
                    .slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                    .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                    .u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full;
            assign n4d_bag_empty_mon[n4d_group][n4d_slice][4] =
                u_NDP_Top_new
                    .slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                    .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                    .u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty;
            assign n4d_mse4_idx_hs_mon[n4d_group][n4d_slice] =
                u_NDP_Top_new
                    .slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                    .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                    .mse_mem_ag_tag_valid &
                u_NDP_Top_new
                    .slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                    .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                    .mse_mem_ag_bp_pre;

            for (genvar n4d_buf = 0;
                 n4d_buf < `BUFFER_NUM;
                 n4d_buf++) begin : N4D_ARM_GEN
                assign n4d_arm_req_hs_mon
                    [n4d_group][n4d_slice][n4d_buf] =
                    (|u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[n4d_buf]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .arm2buf_req_valid) &
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[n4d_buf]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .buf2arm_req_ready;
                assign n4d_arm_resp_hs_mon
                    [n4d_group][n4d_slice][n4d_buf] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[n4d_buf]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .buf2arm_rvalid &
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[n4d_buf]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .array2arm_bp_post;
                assign n4d_arm_hold_mon[n4d_group][n4d_slice][n4d_buf] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[n4d_buf]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .buf2arm_valid_hold;
                assign n4d_arm_bp_mon[n4d_group][n4d_slice][n4d_buf] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[n4d_buf]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .array2arm_bp_post;
                assign n4d_arm_finish_mon[n4d_group][n4d_slice][n4d_buf] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[n4d_buf]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .arm_buf_rd_finish;
            end

            for (genvar n4d_nse = 0;
                 n4d_nse < `NEIGHBOR_STREAM_ENGINE_NUM;
                 n4d_nse++) begin : N4D_NSE_GEN
                assign n4d_nse_req_hs_mon
                    [n4d_group][n4d_slice][n4d_nse] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .NSE_INST[n4d_nse].u_Neighbor_Stream_Engine
                        .u_Neighbor_Out_AG.nse2buf_rreq_valid &
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .NSE_INST[n4d_nse].u_Neighbor_Stream_Engine
                        .u_Neighbor_Out_AG.buf2nse_rreq_ready;
                assign n4d_nse_in_hs_mon
                    [n4d_group][n4d_slice][n4d_nse] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .NSE_INST[n4d_nse].u_Neighbor_Stream_Engine
                        .u_Neighbor_Out_AG.buf2nse_rvalid;
                assign n4d_nse_out_hs_mon
                    [n4d_group][n4d_slice][n4d_nse] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .NSE_INST[n4d_nse].u_Neighbor_Stream_Engine
                        .u_Neighbor_Out_AG.nbr_out_rvalid &
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .NSE_INST[n4d_nse].u_Neighbor_Stream_Engine
                        .u_Neighbor_Out_AG.slice2nse_rready;
                assign n4d_nse_full_mon[n4d_group][n4d_slice][n4d_nse] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .NSE_INST[n4d_nse].u_Neighbor_Stream_Engine
                        .u_Neighbor_Out_AG.fifo_almost_full;
                assign n4d_nse_empty_mon[n4d_group][n4d_slice][n4d_nse] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .NSE_INST[n4d_nse].u_Neighbor_Stream_Engine
                        .u_Neighbor_Out_AG.fifo_empty;
                assign n4d_nse_finish_mon[n4d_group][n4d_slice][n4d_nse] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .NSE_INST[n4d_nse].u_Neighbor_Stream_Engine
                        .u_Neighbor_Out_AG.nbr_ag_out_finish;
            end

            assign n4d_buf2sa_tag_mon[n4d_group][n4d_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.buf2spec_array_rtag;
            assign n4d_sa_input_bp_mon[n4d_group][n4d_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.spec_array2buf_bp_post;
            assign n4d_sa2buf_tag_mon[n4d_group][n4d_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.spec_array2buf_wtag;
            assign n4d_buf_accept_sa_mon[n4d_group][n4d_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[n4d_group]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[n4d_slice]
                    .u_slice_wrapper.u_Slice.buf2spec_array_bp_pre;
            for (genvar n4d_buf45 = 0;
                 n4d_buf45 < 2;
                 n4d_buf45++) begin : N4D_BUF45_GEN
                assign n4d_buf45_wr_en_mon
                    [n4d_group][n4d_slice][n4d_buf45] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[n4d_buf45 + 4]
                        .u_Buffer_Manager.u_Buffer.buf_wr_en;
                assign n4d_buf45_rd_en_mon
                    [n4d_group][n4d_slice][n4d_buf45] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster
                        .BUFFER_MANAGER[n4d_buf45 + 4]
                        .u_Buffer_Manager.u_Buffer.buf_rd_en;
            end
        end
    end
endgenerate

bit n4d_enabled;
bit n4d_active;
bit n4d_cfg_start_d;
bit n4d_cfg_finish_d;
bit n4d_exec_start_d;
bit n4d_finish_d;
bit n4d_decision_emitted;
integer n4d_fd;
integer n4d_slice_id;
integer n4d_group_id;
integer n4d_local_slice_id;
integer n4d_heartbeat_cycles;
integer n4d_stall_cycles;
integer n4d_plusarg_status;
integer n4d_silent_windows;
string n4d_output_path;
longint unsigned n4d_db_cycles;
longint unsigned n4d_db_total;
longint unsigned n4d_sg_total;
longint unsigned n4d_window_start_cycle;
longint unsigned n4d_window_start_total;
longint unsigned n4d_delta;
longint unsigned n4d_req_count [0:`MEMORY_STREAM_ENGINE_NUM-1];
longint unsigned n4d_rdata_count [0:`MEMORY_STREAM_ENGINE_NUM-1];
longint unsigned n4d_wdata_count [0:`MEMORY_STREAM_ENGINE_NUM-1];
longint unsigned n4d_rd_meta_count [0:`MEMORY_RD_STREAM_ENGINE_NUM-1];
longint unsigned n4d_rd_ib_wr_count [0:`MEMORY_RD_STREAM_ENGINE_NUM-1];
longint unsigned n4d_rd_ib_rd_count [0:`MEMORY_RD_STREAM_ENGINE_NUM-1];
longint unsigned n4d_rd_prep_wr_count [0:`MEMORY_RD_STREAM_ENGINE_NUM-1];
longint unsigned n4d_rd_prep_rd_count [0:`MEMORY_RD_STREAM_ENGINE_NUM-1];
longint unsigned n4d_rd_buf_count [0:`MEMORY_RD_STREAM_ENGINE_NUM-1];
longint unsigned n4d_bag_wr_count [0:`MEMORY_STREAM_ENGINE_NUM-1];
longint unsigned n4d_bag_rd_count [0:`MEMORY_STREAM_ENGINE_NUM-1];
longint unsigned n4d_arm_req_count [0:`BUFFER_NUM-1];
longint unsigned n4d_arm_resp_count [0:`BUFFER_NUM-1];
longint unsigned n4d_arm_finish_count [0:`BUFFER_NUM-1];
longint unsigned n4d_nse_req_count [0:`NEIGHBOR_STREAM_ENGINE_NUM-1];
longint unsigned n4d_nse_in_count [0:`NEIGHBOR_STREAM_ENGINE_NUM-1];
longint unsigned n4d_nse_out_count [0:`NEIGHBOR_STREAM_ENGINE_NUM-1];
longint unsigned n4d_nse_finish_count [0:`NEIGHBOR_STREAM_ENGINE_NUM-1];
longint unsigned n4d_sa_input_count;
longint unsigned n4d_sa_output_count;
longint unsigned n4d_buf4_wr_count;
longint unsigned n4d_buf4_rd_count;
longint unsigned n4d_buf5_wr_count;
longint unsigned n4d_buf5_rd_count;
longint unsigned n4d_mse4_idx_count;
logic [`BUFFER_NUM-1:0] n4d_arm_finish_d;
logic [`NEIGHBOR_STREAM_ENGINE_NUM-1:0] n4d_nse_finish_d;

function automatic void n4d_emit_record(
    input bit canonical,
    input string decision,
    input string reason
);
    string record_prefix;
    if (n4d_fd != 0) begin
        record_prefix =
            canonical ? "N4D_CANONICAL_V1" : "N4D_PROGRESS_V1";
        $fdisplay(
            n4d_fd,
            "%s schema=n4d-canonical-v1 decision=%s reason=%s boundary=c0_exec_to_slice_finish sample_start=%0d sample_end=%0d delta=%0d total=%0d active=%0d silent=%0d req=%0d,%0d,%0d,%0d,%0d rdata=%0d,%0d,%0d,%0d,%0d wdata=%0d,%0d,%0d,%0d,%0d meta=%0d,%0d,%0d,%0d ibwr=%0d,%0d,%0d,%0d ibrd=%0d,%0d,%0d,%0d prepwr=%0d,%0d,%0d,%0d preprd=%0d,%0d,%0d,%0d rdbuf=%0d,%0d,%0d,%0d bagwr=%0d,%0d,%0d,%0d,%0d bagrd=%0d,%0d,%0d,%0d,%0d armreq=%0d,%0d,%0d,%0d,%0d,%0d armresp=%0d,%0d,%0d,%0d,%0d,%0d armfin=%0d,%0d,%0d,%0d,%0d,%0d nser=%0d,%0d nsein=%0d,%0d nseout=%0d,%0d nsefin=%0d,%0d sain=%0d saout=%0d b4wr=%0d b4rd=%0d b5wr=%0d b5rd=%0d m4idx=%0d qfull=0x%0h qempty=0x%0h prep=0x%0h bagfull=0x%0h bagempty=0x%0h armhold=0x%0h armbp=0x%0h nsefull=0x%0h nseempty=0x%0h",
            record_prefix,
            decision,
            reason,
            n4d_window_start_cycle,
            n4d_db_cycles,
            n4d_delta,
            n4d_db_total + n4d_sg_total,
            n4d_active,
            n4d_silent_windows,
            n4d_req_count[0], n4d_req_count[1], n4d_req_count[2],
            n4d_req_count[3], n4d_req_count[4],
            n4d_rdata_count[0], n4d_rdata_count[1],
            n4d_rdata_count[2], n4d_rdata_count[3],
            n4d_rdata_count[4],
            n4d_wdata_count[0], n4d_wdata_count[1],
            n4d_wdata_count[2], n4d_wdata_count[3],
            n4d_wdata_count[4],
            n4d_rd_meta_count[0], n4d_rd_meta_count[1],
            n4d_rd_meta_count[2], n4d_rd_meta_count[3],
            n4d_rd_ib_wr_count[0], n4d_rd_ib_wr_count[1],
            n4d_rd_ib_wr_count[2], n4d_rd_ib_wr_count[3],
            n4d_rd_ib_rd_count[0], n4d_rd_ib_rd_count[1],
            n4d_rd_ib_rd_count[2], n4d_rd_ib_rd_count[3],
            n4d_rd_prep_wr_count[0], n4d_rd_prep_wr_count[1],
            n4d_rd_prep_wr_count[2], n4d_rd_prep_wr_count[3],
            n4d_rd_prep_rd_count[0], n4d_rd_prep_rd_count[1],
            n4d_rd_prep_rd_count[2], n4d_rd_prep_rd_count[3],
            n4d_rd_buf_count[0], n4d_rd_buf_count[1],
            n4d_rd_buf_count[2], n4d_rd_buf_count[3],
            n4d_bag_wr_count[0], n4d_bag_wr_count[1],
            n4d_bag_wr_count[2], n4d_bag_wr_count[3],
            n4d_bag_wr_count[4],
            n4d_bag_rd_count[0], n4d_bag_rd_count[1],
            n4d_bag_rd_count[2], n4d_bag_rd_count[3],
            n4d_bag_rd_count[4],
            n4d_arm_req_count[0], n4d_arm_req_count[1],
            n4d_arm_req_count[2], n4d_arm_req_count[3],
            n4d_arm_req_count[4], n4d_arm_req_count[5],
            n4d_arm_resp_count[0], n4d_arm_resp_count[1],
            n4d_arm_resp_count[2], n4d_arm_resp_count[3],
            n4d_arm_resp_count[4], n4d_arm_resp_count[5],
            n4d_arm_finish_count[0], n4d_arm_finish_count[1],
            n4d_arm_finish_count[2], n4d_arm_finish_count[3],
            n4d_arm_finish_count[4], n4d_arm_finish_count[5],
            n4d_nse_req_count[0], n4d_nse_req_count[1],
            n4d_nse_in_count[0], n4d_nse_in_count[1],
            n4d_nse_out_count[0], n4d_nse_out_count[1],
            n4d_nse_finish_count[0], n4d_nse_finish_count[1],
            n4d_sa_input_count, n4d_sa_output_count,
            n4d_buf4_wr_count, n4d_buf4_rd_count,
            n4d_buf5_wr_count, n4d_buf5_rd_count,
            n4d_mse4_idx_count,
            n4d_rd_queue_full_mon[n4d_group_id][n4d_local_slice_id],
            n4d_rd_queue_empty_mon[n4d_group_id][n4d_local_slice_id],
            n4d_rd_prep_count_mon[n4d_group_id][n4d_local_slice_id],
            n4d_bag_full_mon[n4d_group_id][n4d_local_slice_id],
            n4d_bag_empty_mon[n4d_group_id][n4d_local_slice_id],
            n4d_arm_hold_mon[n4d_group_id][n4d_local_slice_id],
            n4d_arm_bp_mon[n4d_group_id][n4d_local_slice_id],
            n4d_nse_full_mon[n4d_group_id][n4d_local_slice_id],
            n4d_nse_empty_mon[n4d_group_id][n4d_local_slice_id]
        );
        $fflush(n4d_fd);
    end
endfunction

task automatic n4d_reset_counters;
    begin
        for (int mse = 0; mse < `MEMORY_STREAM_ENGINE_NUM; mse++) begin
            n4d_req_count[mse] = 0;
            n4d_rdata_count[mse] = 0;
            n4d_wdata_count[mse] = 0;
            n4d_bag_wr_count[mse] = 0;
            n4d_bag_rd_count[mse] = 0;
        end
        for (int rd = 0; rd < `MEMORY_RD_STREAM_ENGINE_NUM; rd++) begin
            n4d_rd_meta_count[rd] = 0;
            n4d_rd_ib_wr_count[rd] = 0;
            n4d_rd_ib_rd_count[rd] = 0;
            n4d_rd_prep_wr_count[rd] = 0;
            n4d_rd_prep_rd_count[rd] = 0;
            n4d_rd_buf_count[rd] = 0;
        end
        for (int buf_id = 0; buf_id < `BUFFER_NUM; buf_id++) begin
            n4d_arm_req_count[buf_id] = 0;
            n4d_arm_resp_count[buf_id] = 0;
            n4d_arm_finish_count[buf_id] = 0;
        end
        for (int nse = 0; nse < `NEIGHBOR_STREAM_ENGINE_NUM; nse++) begin
            n4d_nse_req_count[nse] = 0;
            n4d_nse_in_count[nse] = 0;
            n4d_nse_out_count[nse] = 0;
            n4d_nse_finish_count[nse] = 0;
        end
        n4d_sa_input_count = 0;
        n4d_sa_output_count = 0;
        n4d_buf4_wr_count = 0;
        n4d_buf4_rd_count = 0;
        n4d_buf5_wr_count = 0;
        n4d_buf5_rd_count = 0;
        n4d_mse4_idx_count = 0;
        n4d_arm_finish_d = 0;
        n4d_nse_finish_d = 0;
    end
endtask

initial begin
    n4d_enabled = $test$plusargs("N4D_C0_BOUNDARY_DIAG");
    n4d_slice_id = 0;
    n4d_heartbeat_cycles = 262144;
    n4d_stall_cycles = 1048576;
    n4d_output_path = "return_observer.log";
    n4d_plusarg_status =
        $value$plusargs("RETURN_OBS_SLICE=%d", n4d_slice_id);
    n4d_plusarg_status =
        $value$plusargs(
            "RETURN_OBS_HEARTBEAT_CYCLES=%d",
            n4d_heartbeat_cycles
        );
    n4d_plusarg_status =
        $value$plusargs(
            "RETURN_OBS_STALL_CYCLES=%d",
            n4d_stall_cycles
        );
    n4d_plusarg_status =
        $value$plusargs("RETURN_OBS_FILE=%s", n4d_output_path);
    n4d_fd = 0;
    n4d_active = 0;
    n4d_cfg_start_d = 0;
    n4d_cfg_finish_d = 0;
    n4d_exec_start_d = 0;
    n4d_finish_d = 0;
    n4d_decision_emitted = 0;
    n4d_silent_windows = 0;
    n4d_db_cycles = 0;
    n4d_db_total = 0;
    n4d_sg_total = 0;
    n4d_window_start_cycle = 0;
    n4d_window_start_total = 0;
    n4d_delta = 0;
    n4d_reset_counters();
    if (n4d_enabled) begin
        if (
            n4d_slice_id < 0 ||
            n4d_slice_id >=
                (`SLICE_GROUP_SIZE * `SLICE_GROUP_NUM) ||
            n4d_heartbeat_cycles <= 0 ||
            n4d_stall_cycles <= 0
        ) begin
            $error("N4D observer plusarg contract is invalid");
            n4d_enabled = 0;
        end
        else begin
            n4d_group_id = n4d_slice_id / `SLICE_GROUP_NUM;
            n4d_local_slice_id = n4d_slice_id % `SLICE_GROUP_NUM;
            n4d_fd = $fopen(n4d_output_path, "w");
            if (n4d_fd == 0) begin
                $error("N4D observer output cannot be created");
                n4d_enabled = 0;
            end
            else begin
                $fdisplay(
                    n4d_fd,
                    "N4D_FEATURE_ENABLE_V2 feature=NATIVE4_C0_BOUNDARY enabled=1 heartbeat_cycles=%0d stall_cycles=%0d slice=%0d",
                    n4d_heartbeat_cycles,
                    n4d_stall_cycles,
                    n4d_slice_id
                );
                $fflush(n4d_fd);
                $display(
                    "[RETURN_OBSERVER] enabled N4D_FEATURE_ENABLE_V2 feature=NATIVE4_C0_BOUNDARY enabled=1 heartbeat_cycles=%0d stall_cycles=%0d slice=%0d",
                    n4d_heartbeat_cycles,
                    n4d_stall_cycles,
                    n4d_slice_id
                );
            end
        end
    end
end

always @(posedge u_NDP_Top_new.clk_db or
         negedge u_NDP_Top_new.rst_n_db) begin
    if (!u_NDP_Top_new.rst_n_db) begin
        n4d_active = 0;
        n4d_cfg_start_d = 0;
        n4d_cfg_finish_d = 0;
        n4d_exec_start_d = 0;
        n4d_finish_d = 0;
        n4d_decision_emitted = 0;
        n4d_silent_windows = 0;
        n4d_db_cycles = 0;
        n4d_db_total = 0;
        n4d_window_start_cycle = 0;
        n4d_window_start_total = 0;
        n4d_delta = 0;
    end
    else if (n4d_enabled) begin
        n4d_db_cycles++;
        if (
            n4d_cfg_start_mon[n4d_group_id][n4d_local_slice_id] &&
            !n4d_cfg_start_d
        ) begin
            n4d_db_total++;
        end
        if (
            n4d_cfg_finish_mon[n4d_group_id][n4d_local_slice_id] &&
            !n4d_cfg_finish_d
        ) begin
            n4d_db_total++;
        end
        if (
            n4d_exec_start_mon[n4d_group_id][n4d_local_slice_id] &&
            !n4d_exec_start_d
        ) begin
            n4d_active = 1;
            n4d_db_total++;
            n4d_window_start_cycle = n4d_db_cycles;
            n4d_window_start_total = n4d_db_total + n4d_sg_total;
            n4d_emit_record(
                0, "EXEC_START", "qualified_exec_start"
            );
        end
        if (
            n4d_slice_finish_mon[n4d_group_id][n4d_local_slice_id] &&
            !n4d_finish_d
        ) begin
            n4d_db_total++;
            n4d_active = 0;
            n4d_decision_emitted = 1;
            n4d_emit_record(
                1, "SLICE_FINISH", "qualified_slice_finish"
            );
        end
        if (
            n4d_active &&
            ((n4d_db_cycles - n4d_window_start_cycle) %
             n4d_stall_cycles) == 0
        ) begin
            n4d_delta =
                (n4d_db_total + n4d_sg_total) -
                n4d_window_start_total;
            if (n4d_delta == 0) begin
                n4d_silent_windows++;
                n4d_emit_record(
                    0,
                    "STALL_WINDOW",
                    "qualified_delta_zero"
                );
            end
            else begin
                n4d_silent_windows = 0;
                n4d_emit_record(
                    0,
                    "STILL_PROGRESSING",
                    "qualified_delta_nonzero"
                );
            end
            n4d_window_start_total = n4d_db_total + n4d_sg_total;
        end
        else if (
            n4d_active &&
            ((n4d_db_cycles - n4d_window_start_cycle) %
             n4d_heartbeat_cycles) == 0
        ) begin
            n4d_delta =
                (n4d_db_total + n4d_sg_total) -
                n4d_window_start_total;
            n4d_emit_record(0, "HEARTBEAT", "qualified_snapshot");
        end
        n4d_cfg_start_d =
            n4d_cfg_start_mon[n4d_group_id][n4d_local_slice_id];
        n4d_cfg_finish_d =
            n4d_cfg_finish_mon[n4d_group_id][n4d_local_slice_id];
        n4d_exec_start_d =
            n4d_exec_start_mon[n4d_group_id][n4d_local_slice_id];
        n4d_finish_d =
            n4d_slice_finish_mon[n4d_group_id][n4d_local_slice_id];
    end
end

always @(posedge u_NDP_Top_new.clk_sg or
         negedge u_NDP_Top_new.rst_n_sg) begin
    if (!u_NDP_Top_new.rst_n_sg) begin
        n4d_sg_total = 0;
        n4d_reset_counters();
    end
    else if (n4d_enabled && n4d_active) begin
        for (int mse = 0; mse < `MEMORY_STREAM_ENGINE_NUM; mse++) begin
            for (int req = 0; req < `MSE_REQ_CHL_NUM; req++) begin
                if (
                    local_req_hs[n4d_group_id][n4d_local_slice_id]
                        [mse][req]
                ) begin
                    n4d_req_count[mse]++;
                    n4d_sg_total++;
                end
                if (
                    local_rdata_hs[n4d_group_id][n4d_local_slice_id]
                        [mse][req]
                ) begin
                    n4d_rdata_count[mse]++;
                    n4d_sg_total++;
                end
                if (
                    local_wdata_hs[n4d_group_id][n4d_local_slice_id]
                        [mse][req]
                ) begin
                    n4d_wdata_count[mse]++;
                    n4d_sg_total++;
                end
            end
            if (n4d_bag_wr_mon[n4d_group_id][n4d_local_slice_id][mse]) begin
                n4d_bag_wr_count[mse]++;
                n4d_sg_total++;
            end
            if (n4d_bag_rd_mon[n4d_group_id][n4d_local_slice_id][mse]) begin
                n4d_bag_rd_count[mse]++;
                n4d_sg_total++;
            end
        end
        for (int rd = 0; rd < `MEMORY_RD_STREAM_ENGINE_NUM; rd++) begin
            if (n4d_rd_meta_hs_mon[n4d_group_id][n4d_local_slice_id][rd]) begin
                n4d_rd_meta_count[rd]++;
                n4d_sg_total++;
            end
            for (int req = 0; req < `MSE_REQ_CHL_NUM; req++) begin
                if (
                    n4d_rd_ib_wr_hs_mon[n4d_group_id]
                        [n4d_local_slice_id][rd][req]
                ) begin
                    n4d_rd_ib_wr_count[rd]++;
                    n4d_sg_total++;
                end
                if (
                    n4d_rd_ib_rd_hs_mon[n4d_group_id]
                        [n4d_local_slice_id][rd][req]
                ) begin
                    n4d_rd_ib_rd_count[rd]++;
                    n4d_sg_total++;
                end
            end
            if (
                n4d_rd_prep_wr_hs_mon[n4d_group_id]
                    [n4d_local_slice_id][rd]
            ) begin
                n4d_rd_prep_wr_count[rd]++;
                n4d_sg_total++;
            end
            if (
                n4d_rd_prep_rd_hs_mon[n4d_group_id]
                    [n4d_local_slice_id][rd]
            ) begin
                n4d_rd_prep_rd_count[rd]++;
                n4d_sg_total++;
            end
            if (
                n4d_rd_buf_hs_mon[n4d_group_id][n4d_local_slice_id][rd]
            ) begin
                n4d_rd_buf_count[rd]++;
                n4d_sg_total++;
            end
        end
        for (int buf_id = 0; buf_id < `BUFFER_NUM; buf_id++) begin
            if (
                n4d_arm_req_hs_mon[n4d_group_id]
                    [n4d_local_slice_id][buf_id]
            ) begin
                n4d_arm_req_count[buf_id]++;
                n4d_sg_total++;
            end
            if (
                n4d_arm_resp_hs_mon[n4d_group_id]
                    [n4d_local_slice_id][buf_id]
            ) begin
                n4d_arm_resp_count[buf_id]++;
                n4d_sg_total++;
            end
            if (
                n4d_arm_finish_mon[n4d_group_id]
                    [n4d_local_slice_id][buf_id] &&
                !n4d_arm_finish_d[buf_id]
            ) begin
                n4d_arm_finish_count[buf_id]++;
                n4d_sg_total++;
            end
            n4d_arm_finish_d[buf_id] =
                n4d_arm_finish_mon[n4d_group_id]
                    [n4d_local_slice_id][buf_id];
        end
        for (int nse = 0; nse < `NEIGHBOR_STREAM_ENGINE_NUM; nse++) begin
            if (n4d_nse_req_hs_mon[n4d_group_id][n4d_local_slice_id][nse]) begin
                n4d_nse_req_count[nse]++;
                n4d_sg_total++;
            end
            if (n4d_nse_in_hs_mon[n4d_group_id][n4d_local_slice_id][nse]) begin
                n4d_nse_in_count[nse]++;
                n4d_sg_total++;
            end
            if (n4d_nse_out_hs_mon[n4d_group_id][n4d_local_slice_id][nse]) begin
                n4d_nse_out_count[nse]++;
                n4d_sg_total++;
            end
            if (
                n4d_nse_finish_mon[n4d_group_id]
                    [n4d_local_slice_id][nse] &&
                !n4d_nse_finish_d[nse]
            ) begin
                n4d_nse_finish_count[nse]++;
                n4d_sg_total++;
            end
            n4d_nse_finish_d[nse] =
                n4d_nse_finish_mon[n4d_group_id]
                    [n4d_local_slice_id][nse];
        end
        for (
            int sa_in = 0;
            sa_in < `SA_INPORT_GROUP_NUM;
            sa_in++
        ) begin
            for (
                int sa_buf = 0;
                sa_buf < `SA_PORT_HANDLE_BUF_NUM;
                sa_buf++
            ) begin
                if (
                    (|n4d_buf2sa_tag_mon[n4d_group_id]
                        [n4d_local_slice_id][sa_in][sa_buf]
                        [`ARRAY_PORT_TAG-1 -: `ARRAY_PORT_GROUP_SIZE]) &&
                    n4d_sa_input_bp_mon[n4d_group_id]
                        [n4d_local_slice_id][sa_in][sa_buf]
                ) begin
                    n4d_sa_input_count++;
                    n4d_sg_total++;
                end
            end
        end
        for (
            int sa_out = 0;
            sa_out < `SA_OUTPORT_GROUP_NUM;
            sa_out++
        ) begin
            for (
                int sa_buf = 0;
                sa_buf < `SA_PORT_HANDLE_BUF_NUM;
                sa_buf++
            ) begin
                if (
                    (|n4d_sa2buf_tag_mon[n4d_group_id]
                        [n4d_local_slice_id][sa_out][sa_buf]
                        [`ARRAY_PORT_TAG-1 -: `ARRAY_PORT_GROUP_SIZE]) &&
                    n4d_buf_accept_sa_mon[n4d_group_id]
                        [n4d_local_slice_id][sa_out][sa_buf]
                ) begin
                    n4d_sa_output_count++;
                    n4d_sg_total++;
                end
            end
        end
        if (|n4d_buf45_wr_en_mon[n4d_group_id][n4d_local_slice_id][0]) begin
            n4d_buf4_wr_count++;
            n4d_sg_total++;
        end
        if (|n4d_buf45_rd_en_mon[n4d_group_id][n4d_local_slice_id][0]) begin
            n4d_buf4_rd_count++;
            n4d_sg_total++;
        end
        if (|n4d_buf45_wr_en_mon[n4d_group_id][n4d_local_slice_id][1]) begin
            n4d_buf5_wr_count++;
            n4d_sg_total++;
        end
        if (|n4d_buf45_rd_en_mon[n4d_group_id][n4d_local_slice_id][1]) begin
            n4d_buf5_rd_count++;
            n4d_sg_total++;
        end
        if (n4d_mse4_idx_hs_mon[n4d_group_id][n4d_local_slice_id]) begin
            n4d_mse4_idx_count++;
            n4d_sg_total++;
        end
    end
end

final begin
    if (n4d_fd != 0) begin
        if (!n4d_decision_emitted) begin
            n4d_delta =
                (n4d_db_total + n4d_sg_total) -
                n4d_window_start_total;
            n4d_emit_record(
                1,
                n4d_active ? "INCOMPLETE_AT_SIMULATOR_END" :
                             "FINAL_INACTIVE",
                n4d_active ? "slice_finish_absent" :
                             "observer_inactive"
            );
        end
        else begin
            $fdisplay(
                n4d_fd,
                "N4D_SUMMARY_V1 decision_already_emitted=1 total=%0d",
                n4d_db_total + n4d_sg_total
            );
            $fflush(n4d_fd);
        end
        $fclose(n4d_fd);
    end
end
