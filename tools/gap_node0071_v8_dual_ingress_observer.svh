// Optional low-volume observer for native NDP server-return triage.
//
// Enable with:
//   +RETURN_OBSERVER
//   +RETURN_OBS_SLICE=<0..27>
//   +RETURN_OBS_STALL_CYCLES=<positive cycles>
//   +RETURN_OBS_HEARTBEAT_CYCLES=<positive cycles>
//   +RETURN_OBS_DEEP
//   +RETURN_OBS_DEEP_LIMIT=<positive events per checkpoint class>
//   +RETURN_OBS_ACCUM_STATE
//   +RETURN_OBS_ACCUM_LIMIT=<positive accepted GA inputs>
//   +RETURN_OBS_FILE=<output path; parent directory must already exist>
//
// This observer is read-only.  It does not drive DUT or testbench functional
// signals.  It records a compact checkpoint stream that remains useful when a
// long simulation is externally terminated before final blocks execute.
// RETURN_OBS_DEEP is effective only together with RETURN_OBSERVER.
//
// v8 dual-ingress extension: uncapped counters distinguish the qualified
// READ_STREAM0/MSE0->Buffer0 and READ_STREAM3/MSE3->Buffer4 handshakes from
// per-operand GA inbuffer captures.  These counters localize the v7 evidence
// gap; they do not alter the canonical hang-decision progress predicate.

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        return_obs_sem_cfg_start_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        return_obs_sem_cfg_finish_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        return_obs_sem_exec_start_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        return_obs_slice_finish_mon;

    // Two regular GA PEs per row: columns 0 and 2.
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_enable_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][4:0] return_obs_ga_opcode_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_input_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_p0_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_p0_bp_post_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_p0_enable_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_INPORT_NUM-1:0]
          return_obs_ga_bp_pre_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_INPORT_NUM-1:0]
          [`GA_PE_ALU_DATA_WIDTH-1:0] return_obs_ga_input_data_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_ALU_DATA_WIDTH-1:0]
          return_obs_ga_alu_output_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_outbuffer_wr_mon;

    // SA/buffer4/buffer5 checkpoints cover the earlier Conv start-without-
    // completion failure without enabling high-frequency per-cycle printing.
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_INPORT_GROUP_NUM-1:0][`SA_INPORT_SRC_NUM-1:0]
          [`SA_INPORT_GROUP_TAG-1:0] return_obs_sa_in_tag_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_OUTPORT_GROUP_TAG-1:0] return_obs_sa_out_tag_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_INPORT_GROUP_NUM-1:0][`SA_PORT_HANDLE_BUF_NUM-1:0]
          [`ARRAY_PORT_TAG-1:0] return_obs_buf2sa_rtag_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_INPORT_GROUP_NUM-1:0][`SA_PORT_HANDLE_BUF_NUM-1:0]
          return_obs_sa_in_buf_bp_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_OUTPORT_GROUP_NUM-1:0][`SA_PORT_HANDLE_BUF_NUM-1:0]
          [`ARRAY_PORT_TAG-1:0] return_obs_sa2buf_wtag_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_OUTPORT_GROUP_NUM-1:0][`SA_PORT_HANDLE_BUF_NUM-1:0]
          return_obs_buf_accept_sa_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [1:0][`BUFFER_BANK_NUM-1:0] return_obs_buf45_wr_en_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [1:0][`BUFFER_BANK_NUM-1:0] return_obs_buf45_rd_en_mon;

    // Deep numeric-path probes.  These are hierarchical read-only taps in the
    // TB include, never DUT drivers.  Runtime logging is separately gated by
    // +RETURN_OBS_DEEP and a finite event limit.
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0] return_obs_mse0_ob_vld_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0] return_obs_mse0_ob_vld_d_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0] return_obs_mse0_out_vld_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0] return_obs_mse0_ob_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0] return_obs_mse0_ob_clr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0] return_obs_mse0_mem_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0][`MSE_MEM_REQ_ADDR_WIDTH-1:0]
          return_obs_mse0_ob_addr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_MEM_REQ_ADDR_WIDTH-1:0] return_obs_mse0_addr_in_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_mse0_meta_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_mse0_meta_ready_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_MEM_AG_INPORT_NUM-1:0][`MSE_TSA_IDX_WIDTH-1:0]
          return_obs_mse0_meta_idx_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_TSF_ADDR_WIDTH-1:0] return_obs_mse0_meta_bias_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_TSF_SIZE_WIDTH-1:0] return_obs_mse0_meta_size_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_VALID_MASK_WIDTH-1:0] return_obs_mse0_meta_mask_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`DDR_ADDR_OFFSET_WIDTH-1:0] return_obs_mse0_meta_pos_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0] return_obs_mse0_data_consume_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_mse0_data_sel_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0][`DDR_COL_DATA_WIDTH-1:0]
          return_obs_mse0_ib_data_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_VALID_MASK_WIDTH-1:0] return_obs_mse0_data_mask_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_PADDING_MASK_WIDTH-1:0] return_obs_mse0_padding_mask_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_BUF_REQ_NUM-1:0][`MSE_BUF_REQ_DATA_WIDTH-1:0]
          return_obs_mse0_reordered_data_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_mse0_buf_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_BUF_REQ_NUM-1:0][`MSE_BUF_REQ_DATA_WIDTH-1:0]
          return_obs_mse0_buf_data_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_mse3_buf_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_BUF_REQ_NUM-1:0][`MSE_BUF_REQ_DATA_WIDTH-1:0]
          return_obs_mse3_buf_data_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_INPORT_NUM-1:0]
          return_obs_ga_operand_capture_mon;

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`IGA_LC_PORT_WIDTH-1:0] return_obs_lc0_port_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`IGA_LC_PORT_WIDTH-1:0] return_obs_lc2_port_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`IGA_PE_PORT_WIDTH-1:0] return_obs_lc_pe1_port_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_mse4_idx_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          return_obs_mse4_idx_hs_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_MEM_AG_INPORT_NUM-1:0][`MSE_MEM_AG_INPORT_IDX_WIDTH-1:0]
          return_obs_mse4_idx_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_TSA_ADDR_WIDTH-1:0] return_obs_mse4_addr_bias_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0][`MSE_MEM_REQ_ADDR_WIDTH-1:0]
          return_obs_mse4_local_req_addr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`MSE_REQ_CHL_NUM-1:0][`DDR_COL_DATA_WIDTH-1:0]
          return_obs_mse4_local_wdata_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_ALU_TAG_WIDTH-1:0]
          return_obs_ga_result_tag_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_matched_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][1:0]
          return_obs_ga_transout_initial_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_calculate_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_calculate_reg_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_calculate_done_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_calculate_v0_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_calculate_v2_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_ob_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_ob_wr_req_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0] return_obs_ga_ob_rd_req_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][2:0] return_obs_ga_calc_cnt_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_OUTBUFFER_PTR_WIDTH-1:0]
          return_obs_ga_ob_wr_ptr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_OUTBUFFER_PTR_WIDTH-1:0]
          return_obs_ga_ob_rd_ptr_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_OUTBUFFER_CNT_WIDTH-1:0]
          return_obs_ga_ob_count_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_OUTBUFFER_DEPTH-1:0]
          [`GA_PE_OUTBUFFER_TAG_WIDTH-1:0] return_obs_ga_ob_tag_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_OUTBUFFER_DEPTH-1:0]
          [`GA_PE_OUTBUFFER_DATA_WIDTH-1:0] return_obs_ga_ob_data_mon;

    generate
        for (genvar return_obs_group = 0;
             return_obs_group < `SLICE_GROUP_SIZE;
             return_obs_group++) begin : RETURN_OBS_GROUP_GEN
            for (genvar return_obs_slice = 0;
                 return_obs_slice < `SLICE_GROUP_NUM;
                 return_obs_slice++) begin : RETURN_OBS_SLICE_GEN
                assign return_obs_sem_cfg_start_mon[return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager.sem2scm_cfg_start;
                assign return_obs_sem_cfg_finish_mon[return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager.scm2sem_cfg_finish;
                assign return_obs_sem_exec_start_mon[return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager.sem2iga_exec_start;
                assign return_obs_slice_finish_mon[return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_Slice_Execution_Manager.slice_cmpt_finish;
                assign return_obs_mse0_ob_vld_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Memory_AG.mem_ag_ob_chl_vld;
                assign return_obs_mse0_ob_vld_d_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Memory_AG.mem_ag_ob_chl_vld_d;
                assign return_obs_mse0_out_vld_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Memory_AG.mem_ag_ob_vld;
                assign return_obs_mse0_ob_hs_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Memory_AG.mem_ag_ob_chl_hs;
                assign return_obs_mse0_ob_clr_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Memory_AG.mem_ag_ob_chl_clr;
                assign return_obs_mse0_mem_ready_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .mem2mse_request_ready;
                assign return_obs_mse0_ob_addr_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Memory_AG.mem_ag_ob_chl_addr;
                assign return_obs_mse0_addr_in_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Memory_AG.mem_ag_ob_addr_in;
                assign return_obs_mse0_meta_valid_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .rd_data_chl_req_valid;
                assign return_obs_mse0_meta_ready_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .rd_data_chl_req_ready;
                assign return_obs_mse0_meta_idx_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .rd_data_chl_req_tsa_idx;
                assign return_obs_mse0_meta_bias_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .rd_data_chl_req_tsf_bias_addr;
                assign return_obs_mse0_meta_size_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .rd_data_chl_req_tsf_size;
                assign return_obs_mse0_meta_mask_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .rd_data_chl_req_valid_mask;
                assign return_obs_mse0_meta_pos_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .rd_data_chl_req_position;
                assign return_obs_mse0_data_consume_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Data_Channel.rd_chl_ib_rd_hs;
                assign return_obs_mse0_data_sel_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Data_Channel.rd_chl_ib_sel;
                assign return_obs_mse0_ib_data_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Data_Channel.rd_chl_ib_data;
                assign return_obs_mse0_data_mask_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Data_Channel.rd_chl_queue_rd_valid_mask;
                assign return_obs_mse0_padding_mask_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Data_Channel.rd_chl_queue_rd_padding_mask;
                assign return_obs_mse0_reordered_data_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .u_RD_Data_Channel.rd_data_chl_data_reorder;
                assign return_obs_mse0_buf_hs_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .mse2buf_wvalid &
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .buf2mse_wreq_ready;
                assign return_obs_mse0_buf_data_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[0].RD_MSE.u_Memory_RD_Stream_Engine
                        .mse2buf_wdata;
                assign return_obs_mse3_buf_hs_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[3].RD_MSE.u_Memory_RD_Stream_Engine
                        .mse2buf_wvalid &
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[3].RD_MSE.u_Memory_RD_Stream_Engine
                        .buf2mse_wreq_ready;
                assign return_obs_mse3_buf_data_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[3].RD_MSE.u_Memory_RD_Stream_Engine
                        .mse2buf_wdata;
                assign return_obs_lc0_port_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_Index_Generation_Array
                        .iga_lc_outport[0];
                assign return_obs_lc2_port_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_Index_Generation_Array
                        .iga_lc_outport[2];
                assign return_obs_lc_pe1_port_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_Index_Generation_Array
                        .iga_pe_outport[1];
                assign return_obs_mse4_idx_valid_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .mse_mem_ag_tag_valid;
                assign return_obs_mse4_idx_hs_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .mse_mem_ag_tag_valid &
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .mse_mem_ag_bp_pre;
                assign return_obs_mse4_idx_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .mse_mem_ag_idx;
                assign return_obs_mse4_addr_bias_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                        .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                        .u_WR_Memory_AG.transaction_addr_bias;
                assign return_obs_mse4_local_req_addr_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_group].u_slice_with_datahub_mc_group
                        .local_req_addr[return_obs_slice][4];
                assign return_obs_mse4_local_wdata_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen
                        [return_obs_group].u_slice_with_datahub_mc_group
                        .local_wdata[return_obs_slice][4];
                assign return_obs_sa_in_tag_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.sa_inport_group_in_tag;
                assign return_obs_sa_out_tag_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.sa_outport_group_out_tag;
                assign return_obs_buf2sa_rtag_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.buf2spec_array_rtag;
                assign return_obs_sa_in_buf_bp_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.spec_array2buf_bp_post;
                assign return_obs_sa2buf_wtag_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.spec_array2buf_wtag;
                assign return_obs_buf_accept_sa_mon
                    [return_obs_group][return_obs_slice] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                        .u_slice_wrapper.u_Slice.buf2spec_array_bp_pre;

                for (genvar return_obs_buf_slot = 0;
                     return_obs_buf_slot < 2;
                     return_obs_buf_slot++) begin : RETURN_OBS_BUF45_GEN
                    assign return_obs_buf45_wr_en_mon
                        [return_obs_group][return_obs_slice]
                        [return_obs_buf_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_group].u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_slice].u_slice_wrapper
                            .u_Slice.u_LSU.u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[return_obs_buf_slot + 4]
                            .u_Buffer_Manager.u_Buffer.buf_wr_en;
                    assign return_obs_buf45_rd_en_mon
                        [return_obs_group][return_obs_slice]
                        [return_obs_buf_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen
                            [return_obs_group].u_slice_with_datahub_mc_group
                            .slice_group_gen[return_obs_slice].u_slice_wrapper
                            .u_Slice.u_LSU.u_Buffer_Manager_Cluster
                            .BUFFER_MANAGER[return_obs_buf_slot + 4]
                            .u_Buffer_Manager.u_Buffer.buf_rd_en;
                end

                for (genvar return_obs_row = 0;
                     return_obs_row < `GA_ROW_PE_NUM;
                     return_obs_row++) begin : RETURN_OBS_GA_ROW_GEN
                    assign return_obs_ga_enable_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_enable;
                    assign return_obs_ga_opcode_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_alu_opcode;
                    assign return_obs_ga_input_valid_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.alu_input_valid_bit;
                    assign return_obs_ga_p0_valid_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.alu_pipeline0_valid_bit;
                    assign return_obs_ga_p0_bp_post_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.alu_pipeline0_bp_post;
                    assign return_obs_ga_p0_enable_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_alu_pipeline0_enable;
                    assign return_obs_ga_bp_pre_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_bp_pre;
                    assign return_obs_ga_operand_capture_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_enable;
                    assign return_obs_ga_input_data_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.ga_pe_alu_input_data;
                    assign return_obs_ga_alu_output_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.ga_pe_alu2outbuffer_data;
                    assign return_obs_ga_outbuffer_wr_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.ga_pe_outbuffer_wr_en;
                    assign return_obs_ga_result_tag_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.ga_pe_alu_result_tag;
                    assign return_obs_ga_matched_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_matched;
                    assign return_obs_ga_transout_initial_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.transout_initial;
                    assign return_obs_ga_calculate_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.ga_pe_transout_calculate;
                    assign return_obs_ga_calculate_reg_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.ga_pe_transout_calculate_reg;
                    assign return_obs_ga_calculate_done_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.ga_pe_transout_calculate_done;
                    assign return_obs_ga_calculate_v0_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.ga_pe_transout_calculate_valid_port0;
                    assign return_obs_ga_calculate_v2_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.ga_pe_transout_calculate_valid_port2;
                    assign return_obs_ga_ob_valid_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.ga_pe_outbuffer2alu_valid_bit;
                    assign return_obs_ga_ob_wr_req_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.ga_pe_outbuffer_wr_enable;
                    assign return_obs_ga_ob_rd_req_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.ga_pe_outbuffer_rd_enable;
                    assign return_obs_ga_calc_cnt_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Outbuffer.transout_calculate_cnt;
                    assign return_obs_ga_ob_wr_ptr_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Outbuffer.alu2ob_wr_ptr;
                    assign return_obs_ga_ob_rd_ptr_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Outbuffer.ob2alu_rd_ptr;
                    assign return_obs_ga_ob_count_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Outbuffer.ga_pe_outbuffer_count;
                    assign return_obs_ga_ob_tag_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Outbuffer.ga_pe_outbuffer_tag;
                    assign return_obs_ga_ob_data_mon
                        [return_obs_group][return_obs_slice][return_obs_row][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[0].GA_PE
                            .u_GA_PE.u_GA_PE_Outbuffer.ga_pe_outbuffer_data;

                    assign return_obs_ga_enable_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_enable;
                    assign return_obs_ga_opcode_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_alu_opcode;
                    assign return_obs_ga_input_valid_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.alu_input_valid_bit;
                    assign return_obs_ga_p0_valid_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.alu_pipeline0_valid_bit;
                    assign return_obs_ga_p0_bp_post_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.alu_pipeline0_bp_post;
                    assign return_obs_ga_p0_enable_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_alu_pipeline0_enable;
                    assign return_obs_ga_bp_pre_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_bp_pre;
                    assign return_obs_ga_operand_capture_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_enable;
                    assign return_obs_ga_input_data_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.ga_pe_alu_input_data;
                    assign return_obs_ga_alu_output_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.ga_pe_alu2outbuffer_data;
                    assign return_obs_ga_outbuffer_wr_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.ga_pe_outbuffer_wr_en;
                    assign return_obs_ga_result_tag_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.ga_pe_alu_result_tag;
                    assign return_obs_ga_matched_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_matched;
                    assign return_obs_ga_transout_initial_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Inbuffer.transout_initial;
                    assign return_obs_ga_calculate_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.ga_pe_transout_calculate;
                    assign return_obs_ga_calculate_reg_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.ga_pe_transout_calculate_reg;
                    assign return_obs_ga_calculate_done_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.ga_pe_transout_calculate_done;
                    assign return_obs_ga_calculate_v0_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.ga_pe_transout_calculate_valid_port0;
                    assign return_obs_ga_calculate_v2_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.ga_pe_transout_calculate_valid_port2;
                    assign return_obs_ga_ob_valid_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.ga_pe_outbuffer2alu_valid_bit;
                    assign return_obs_ga_ob_wr_req_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.ga_pe_outbuffer_wr_enable;
                    assign return_obs_ga_ob_rd_req_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.ga_pe_outbuffer_rd_enable;
                    assign return_obs_ga_calc_cnt_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Outbuffer.transout_calculate_cnt;
                    assign return_obs_ga_ob_wr_ptr_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Outbuffer.alu2ob_wr_ptr;
                    assign return_obs_ga_ob_rd_ptr_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Outbuffer.ob2alu_rd_ptr;
                    assign return_obs_ga_ob_count_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Outbuffer.ga_pe_outbuffer_count;
                    assign return_obs_ga_ob_tag_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Outbuffer.ga_pe_outbuffer_tag;
                    assign return_obs_ga_ob_data_mon
                        [return_obs_group][return_obs_slice][return_obs_row][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]
                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[return_obs_row].GA_COL_PE[2].GA_PE
                            .u_GA_PE.u_GA_PE_Outbuffer.ga_pe_outbuffer_data;
                end
            end
        end
    endgenerate

    bit return_obs_enabled;
    bit return_obs_deep_enabled;
    bit return_obs_accum_state_enabled;
    bit return_obs_active;
    int return_obs_slice_id;
    int return_obs_group_id;
    int return_obs_local_slice_id;
    int return_obs_stall_limit;
    int return_obs_heartbeat_period;
    int return_obs_deep_limit;
    int return_obs_accum_limit;
    int return_obs_accum_count;
    integer return_obs_fd;
    string return_obs_output_path;
    integer return_obs_plusarg_status;
    integer return_obs_mkdir_status;
    longint unsigned return_obs_total_cycles;
    longint unsigned return_obs_active_cycles;
    longint unsigned return_obs_gexec_count;
    longint unsigned return_obs_gconfig_count;
    longint unsigned return_obs_req_count [0:`MEMORY_STREAM_ENGINE_NUM-1];
    longint unsigned return_obs_rdata_count [0:`MEMORY_STREAM_ENGINE_NUM-1];
    longint unsigned return_obs_wdata_count [0:`MEMORY_STREAM_ENGINE_NUM-1];
    longint unsigned return_obs_bank_frame_count [0:`BANK_NUM_PER_SLICE-1];
    longint unsigned return_obs_buf45_wr_count [0:1];
    longint unsigned return_obs_buf45_rd_count [0:1];
    longint unsigned return_obs_deep_addr_enqueue_count;
    longint unsigned return_obs_deep_req_hs_count;
    longint unsigned return_obs_deep_meta_count;
    longint unsigned return_obs_deep_consume_count;
    longint unsigned return_obs_deep_buf_count;
    longint unsigned return_obs_deep_ga_count;
    longint unsigned return_obs_deep_mse4_count;
    longint unsigned return_obs_sg_ga_input_count;
    longint unsigned return_obs_sg_ga_output_count;
    longint unsigned return_obs_sg_mse4_req_count [0:`MSE_REQ_CHL_NUM-1];
    longint unsigned return_obs_sg_mse4_wdata_count [0:`MSE_REQ_CHL_NUM-1];
    longint unsigned return_obs_mse0_buf_accept_count;
    longint unsigned return_obs_mse3_buf_accept_count;
    longint unsigned return_obs_ga_operand0_capture_count;
    longint unsigned return_obs_ga_operand2_capture_count;
    longint unsigned return_obs_ga_accept_count;
    int unsigned return_obs_ga_stall_cycles [0:`GA_ROW_PE_NUM-1][0:1];
    bit return_obs_ga_stall_reported [0:`GA_ROW_PE_NUM-1][0:1];
    logic return_obs_cfg_start_d;
    logic return_obs_cfg_finish_d;
    logic return_obs_exec_start_d;
    logic return_obs_finish_d;

    task automatic return_obs_write_summary(input string event_name);
        longint unsigned request_total;
        longint unsigned rdata_total;
        longint unsigned wdata_total;
        begin
            request_total = 0;
            rdata_total = 0;
            wdata_total = 0;
            for (int mse = 0; mse < `MEMORY_STREAM_ENGINE_NUM; mse++) begin
                request_total += return_obs_req_count[mse];
                rdata_total += return_obs_rdata_count[mse];
                wdata_total += return_obs_wdata_count[mse];
            end
            if (return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | %s | slice=%0d active_cycles=%0d gexec=%0d gconfig=%0d req=%0d rdata=%0d wdata=%0d buf4_wr=%0d buf4_rd=%0d buf5_wr=%0d buf5_rd=%0d",
                    $time,
                    event_name,
                    return_obs_slice_id,
                    return_obs_active_cycles,
                    return_obs_gexec_count,
                    return_obs_gconfig_count,
                    request_total,
                    rdata_total,
                    wdata_total,
                    return_obs_buf45_wr_count[0],
                    return_obs_buf45_rd_count[0],
                    return_obs_buf45_wr_count[1],
                    return_obs_buf45_rd_count[1]
                );
                if (return_obs_deep_enabled) begin
                    $fdisplay(
                        return_obs_fd,
                        "%0t | DEEP_COUNTS | event=%s addr_enqueue=%0d req_hs=%0d meta=%0d consume=%0d buffer=%0d ga=%0d mse4_idx=%0d limit=%0d",
                        $time,
                        event_name,
                        return_obs_deep_addr_enqueue_count,
                        return_obs_deep_req_hs_count,
                        return_obs_deep_meta_count,
                        return_obs_deep_consume_count,
                        return_obs_deep_buf_count,
                        return_obs_deep_ga_count,
                        return_obs_deep_mse4_count,
                        return_obs_deep_limit
                    );
                    $fdisplay(
                        return_obs_fd,
                        "%0t | SG_COUNTS | event=%s ga_input=%0d ga_output=%0d mse4_req0=%0d mse4_req1=%0d mse4_wdata0=%0d mse4_wdata1=%0d mse4_outstanding0=%0d mse4_outstanding1=%0d",
                        $time,
                        event_name,
                        return_obs_sg_ga_input_count,
                        return_obs_sg_ga_output_count,
                        return_obs_sg_mse4_req_count[0],
                        return_obs_sg_mse4_req_count[1],
                        return_obs_sg_mse4_wdata_count[0],
                        return_obs_sg_mse4_wdata_count[1],
                        return_obs_sg_mse4_req_count[0] -
                            return_obs_sg_mse4_wdata_count[0],
                        return_obs_sg_mse4_req_count[1] -
                            return_obs_sg_mse4_wdata_count[1]
                    );
                    $fdisplay(
                        return_obs_fd,
                        "%0t | DUAL_INGRESS_COUNTS | event=%s mse0_buf_accept=%0d mse3_buf_accept=%0d ga_operand0_capture=%0d ga_operand2_capture=%0d ga_accept=%0d",
                        $time,
                        event_name,
                        return_obs_mse0_buf_accept_count,
                        return_obs_mse3_buf_accept_count,
                        return_obs_ga_operand0_capture_count,
                        return_obs_ga_operand2_capture_count,
                        return_obs_ga_accept_count
                    );
                end
                $fflush(return_obs_fd);
            end
        end
    endtask

    task automatic return_obs_write_internal_state(input string event_name);
        begin
            if (return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | INTERNAL_STATE | event=%s slice=%0d sa_in_tag=0x%0h buf2sa_rtag=0x%0h sa_in_buf_bp=0x%0h sa_out_tag=0x%0h sa2buf_wtag=0x%0h buf_accept_sa=0x%0h buf4_wr_en=0x%0h buf4_rd_en=0x%0h buf5_wr_en=0x%0h buf5_rd_en=0x%0h",
                    $time,
                    event_name,
                    return_obs_slice_id,
                    return_obs_sa_in_tag_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_buf2sa_rtag_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_sa_in_buf_bp_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_sa_out_tag_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_sa2buf_wtag_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_buf_accept_sa_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_buf45_wr_en_mon
                        [return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_buf45_rd_en_mon
                        [return_obs_group_id][return_obs_local_slice_id][0],
                    return_obs_buf45_wr_en_mon
                        [return_obs_group_id][return_obs_local_slice_id][1],
                    return_obs_buf45_rd_en_mon
                        [return_obs_group_id][return_obs_local_slice_id][1]
                );
                $fflush(return_obs_fd);
            end
        end
    endtask

    initial begin
        return_obs_enabled = $test$plusargs("RETURN_OBSERVER");
        return_obs_deep_enabled = $test$plusargs("RETURN_OBS_DEEP");
        return_obs_accum_state_enabled =
            $test$plusargs("RETURN_OBS_ACCUM_STATE");
        return_obs_slice_id = 0;
        return_obs_stall_limit = 4096;
        return_obs_heartbeat_period = 4096;
        return_obs_deep_limit = 256;
        return_obs_accum_limit = 512;
        return_obs_output_path =
            "sim_results/return_observer/return_observer.log";
        return_obs_plusarg_status =
            $value$plusargs("RETURN_OBS_SLICE=%d", return_obs_slice_id);
        return_obs_plusarg_status =
            $value$plusargs(
                "RETURN_OBS_STALL_CYCLES=%d", return_obs_stall_limit
            );
        return_obs_plusarg_status =
            $value$plusargs(
                "RETURN_OBS_HEARTBEAT_CYCLES=%d",
                return_obs_heartbeat_period
            );
        return_obs_plusarg_status =
            $value$plusargs(
                "RETURN_OBS_DEEP_LIMIT=%d",
                return_obs_deep_limit
            );
        return_obs_plusarg_status =
            $value$plusargs(
                "RETURN_OBS_ACCUM_LIMIT=%d",
                return_obs_accum_limit
            );
        return_obs_plusarg_status =
            $value$plusargs(
                "RETURN_OBS_FILE=%s",
                return_obs_output_path
            );
        return_obs_fd = 0;
        return_obs_active = 1'b0;
        return_obs_total_cycles = 0;
        return_obs_active_cycles = 0;
        return_obs_gexec_count = 0;
        return_obs_gconfig_count = 0;
        return_obs_cfg_start_d = 1'b0;
        return_obs_cfg_finish_d = 1'b0;
        return_obs_exec_start_d = 1'b0;
        return_obs_finish_d = 1'b0;
        return_obs_deep_addr_enqueue_count = 0;
        return_obs_deep_req_hs_count = 0;
        return_obs_deep_meta_count = 0;
        return_obs_deep_consume_count = 0;
        return_obs_deep_buf_count = 0;
        return_obs_deep_ga_count = 0;
        return_obs_deep_mse4_count = 0;
        return_obs_sg_ga_input_count = 0;
        return_obs_sg_ga_output_count = 0;
        return_obs_mse0_buf_accept_count = 0;
        return_obs_mse3_buf_accept_count = 0;
        return_obs_ga_operand0_capture_count = 0;
        return_obs_ga_operand2_capture_count = 0;
        return_obs_ga_accept_count = 0;
        return_obs_accum_count = 0;
        for (int channel = 0; channel < `MSE_REQ_CHL_NUM; channel++) begin
            return_obs_sg_mse4_req_count[channel] = 0;
            return_obs_sg_mse4_wdata_count[channel] = 0;
        end
        for (int mse = 0; mse < `MEMORY_STREAM_ENGINE_NUM; mse++) begin
            return_obs_req_count[mse] = 0;
            return_obs_rdata_count[mse] = 0;
            return_obs_wdata_count[mse] = 0;
        end
        for (int bank = 0; bank < `BANK_NUM_PER_SLICE; bank++) begin
            return_obs_bank_frame_count[bank] = 0;
        end
        for (int slot = 0; slot < 2; slot++) begin
            return_obs_buf45_wr_count[slot] = 0;
            return_obs_buf45_rd_count[slot] = 0;
        end
        for (int row = 0; row < `GA_ROW_PE_NUM; row++) begin
            for (int slot = 0; slot < 2; slot++) begin
                return_obs_ga_stall_cycles[row][slot] = 0;
                return_obs_ga_stall_reported[row][slot] = 1'b0;
            end
        end

        if (return_obs_enabled) begin
            if (return_obs_slice_id < 0 ||
                return_obs_slice_id >=
                    (`SLICE_GROUP_SIZE * `SLICE_GROUP_NUM) ||
                return_obs_stall_limit <= 0 ||
                return_obs_heartbeat_period <= 0 ||
                return_obs_deep_limit <= 0 ||
                return_obs_accum_limit <= 0) begin
                $error(
                    "RETURN_OBSERVER invalid plusargs: slice=%0d stall=%0d heartbeat=%0d deep_limit=%0d accum_limit=%0d",
                    return_obs_slice_id,
                    return_obs_stall_limit,
                    return_obs_heartbeat_period,
                    return_obs_deep_limit,
                    return_obs_accum_limit
                );
                return_obs_enabled = 1'b0;
            end
            else begin
                return_obs_group_id =
                    return_obs_slice_id / `SLICE_GROUP_NUM;
                return_obs_local_slice_id =
                    return_obs_slice_id % `SLICE_GROUP_NUM;
                return_obs_mkdir_status =
                    $system("mkdir -p sim_results/return_observer");
                return_obs_fd = $fopen(return_obs_output_path, "w");
                if (return_obs_fd == 0) begin
                    $error("RETURN_OBSERVER cannot create return_observer.log");
                    return_obs_enabled = 1'b0;
                end
                else begin
                    $fdisplay(
                        return_obs_fd,
                        "# Native NDP return observer v4"
                    );
                    $fdisplay(
                        return_obs_fd,
                        "# slice=%0d stall_cycles=%0d heartbeat_cycles=%0d deep=%0d deep_limit=%0d accum_state=%0d accum_limit=%0d",
                        return_obs_slice_id,
                        return_obs_stall_limit,
                        return_obs_heartbeat_period,
                        return_obs_deep_enabled,
                        return_obs_deep_limit,
                        return_obs_accum_state_enabled,
                        return_obs_accum_limit
                    );
                    $fdisplay(
                        return_obs_fd,
                        "# checkpoints: cfg/exec memory buffer SA GA; deep=MSE0 context plus clk_sg GA input/output and MSE4 request/write-data accounting"
                    );
                    $fflush(return_obs_fd);
                    $display(
                        "[%0t] [RETURN_OBSERVER] enabled for slice %0d",
                        $time,
                        return_obs_slice_id
                    );
                end
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_active = 1'b0;
            return_obs_total_cycles = 0;
            return_obs_active_cycles = 0;
            return_obs_cfg_start_d = 1'b0;
            return_obs_cfg_finish_d = 1'b0;
            return_obs_exec_start_d = 1'b0;
            return_obs_finish_d = 1'b0;
        end
        else if (return_obs_enabled) begin
            return_obs_total_cycles++;

            if (gexec2slice_fire_mon
                [return_obs_group_id][return_obs_local_slice_id]) begin
                return_obs_gexec_count++;
            end
            if (gconfig2slice_fire_mon
                [return_obs_group_id][return_obs_local_slice_id]) begin
                return_obs_gconfig_count++;
            end
            for (int mse = 0; mse < `MEMORY_STREAM_ENGINE_NUM; mse++) begin
                for (int req = 0; req < `MSE_REQ_CHL_NUM; req++) begin
                    if (local_req_hs
                        [return_obs_group_id][return_obs_local_slice_id]
                        [mse][req]) begin
                        return_obs_req_count[mse]++;
                    end
                    if (local_rdata_hs
                        [return_obs_group_id][return_obs_local_slice_id]
                        [mse][req]) begin
                        return_obs_rdata_count[mse]++;
                    end
                    if (local_wdata_hs
                        [return_obs_group_id][return_obs_local_slice_id]
                        [mse][req]) begin
                        return_obs_wdata_count[mse]++;
                    end
                end
            end
            for (int bank = 0; bank < `BANK_NUM_PER_SLICE; bank++) begin
                if (bank_frame_hs
                    [return_obs_group_id][return_obs_local_slice_id][bank]) begin
                    return_obs_bank_frame_count[bank]++;
                end
            end
            for (int slot = 0; slot < 2; slot++) begin
                if (|return_obs_buf45_wr_en_mon
                    [return_obs_group_id][return_obs_local_slice_id][slot]) begin
                    return_obs_buf45_wr_count[slot]++;
                end
                if (|return_obs_buf45_rd_en_mon
                    [return_obs_group_id][return_obs_local_slice_id][slot]) begin
                    return_obs_buf45_rd_count[slot]++;
                end
            end

            if (return_obs_sem_cfg_start_mon
                [return_obs_group_id][return_obs_local_slice_id] &&
                !return_obs_cfg_start_d) begin
                return_obs_write_summary("CFG_START");
            end
            if (return_obs_sem_cfg_finish_mon
                [return_obs_group_id][return_obs_local_slice_id] &&
                !return_obs_cfg_finish_d) begin
                return_obs_write_summary("CFG_FINISH");
            end
            if (return_obs_sem_exec_start_mon
                [return_obs_group_id][return_obs_local_slice_id] &&
                !return_obs_exec_start_d) begin
                return_obs_active = 1'b1;
                return_obs_active_cycles = 0;
                for (int row = 0; row < `GA_ROW_PE_NUM; row++) begin
                    for (int slot = 0; slot < 2; slot++) begin
                        return_obs_ga_stall_cycles[row][slot] = 0;
                        return_obs_ga_stall_reported[row][slot] = 1'b0;
                    end
                end
                return_obs_deep_addr_enqueue_count = 0;
                return_obs_deep_req_hs_count = 0;
                return_obs_deep_meta_count = 0;
                return_obs_deep_consume_count = 0;
                return_obs_deep_buf_count = 0;
                return_obs_deep_ga_count = 0;
                return_obs_deep_mse4_count = 0;
                return_obs_sg_ga_input_count = 0;
                return_obs_sg_ga_output_count = 0;
                return_obs_mse0_buf_accept_count = 0;
                return_obs_mse3_buf_accept_count = 0;
                return_obs_ga_operand0_capture_count = 0;
                return_obs_ga_operand2_capture_count = 0;
                return_obs_ga_accept_count = 0;
                for (int channel = 0;
                     channel < `MSE_REQ_CHL_NUM;
                     channel++) begin
                    return_obs_sg_mse4_req_count[channel] = 0;
                    return_obs_sg_mse4_wdata_count[channel] = 0;
                end
                return_obs_write_summary("EXEC_START");
                return_obs_write_internal_state("EXEC_START");
            end

            if (return_obs_active) begin
                return_obs_active_cycles++;
                if (return_obs_deep_enabled) begin
                    for (int channel = 0;
                         channel < `MSE_REQ_CHL_NUM;
                         channel++) begin
                        if (
                            return_obs_mse0_ob_hs_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][channel] &&
                            return_obs_deep_addr_enqueue_count <
                                return_obs_deep_limit
                        ) begin
                            return_obs_deep_addr_enqueue_count++;
                            $fdisplay(
                                return_obs_fd,
                                "%0t | DEEP_RD_ADDR_ENQUEUE | n=%0d ch=%0d addr_in=0x%0h addr_latched=0x%0h vld=0x%0h vld_d=0x%0h out_vld=0x%0h ready=0x%0h clr=0x%0h",
                                $time,
                                return_obs_deep_addr_enqueue_count,
                                channel,
                                return_obs_mse0_addr_in_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id],
                                return_obs_mse0_ob_addr_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id][channel],
                                return_obs_mse0_ob_vld_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id],
                                return_obs_mse0_ob_vld_d_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id],
                                return_obs_mse0_out_vld_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id],
                                return_obs_mse0_mem_ready_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id],
                                return_obs_mse0_ob_clr_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id]
                            );
                        end
                        if (
                            local_req_hs
                                [return_obs_group_id]
                                [return_obs_local_slice_id][0][channel] &&
                            return_obs_deep_req_hs_count <
                                return_obs_deep_limit
                        ) begin
                            return_obs_deep_req_hs_count++;
                            $fdisplay(
                                return_obs_fd,
                                "%0t | DEEP_RD_REQ_HANDSHAKE | n=%0d ch=%0d addr=0x%0h vld=0x%0h vld_d=0x%0h out_vld=0x%0h ready=0x%0h hs=0x%0h clr=0x%0h",
                                $time,
                                return_obs_deep_req_hs_count,
                                channel,
                                return_obs_mse0_ob_addr_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id][channel],
                                return_obs_mse0_ob_vld_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id],
                                return_obs_mse0_ob_vld_d_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id],
                                return_obs_mse0_out_vld_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id],
                                return_obs_mse0_mem_ready_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id],
                                return_obs_mse0_ob_hs_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id],
                                return_obs_mse0_ob_clr_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id]
                            );
                        end
                    end
                    if (
                        return_obs_mse0_meta_valid_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id] &&
                        return_obs_mse0_meta_ready_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id] &&
                        return_obs_deep_meta_count < return_obs_deep_limit
                    ) begin
                        return_obs_deep_meta_count++;
                        $fdisplay(
                            return_obs_fd,
                            "%0t | DEEP_RD_META | n=%0d idx=0x%0h bias=%0d size=%0d position=%0d valid_mask=0x%0h",
                            $time,
                            return_obs_deep_meta_count,
                            return_obs_mse0_meta_idx_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_mse0_meta_bias_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_mse0_meta_size_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_mse0_meta_pos_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_mse0_meta_mask_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                        );
                    end
                    if (
                        |return_obs_mse0_data_consume_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id] &&
                        return_obs_deep_consume_count < return_obs_deep_limit
                    ) begin
                        return_obs_deep_consume_count++;
                        $fdisplay(
                            return_obs_fd,
                            "%0t | DEEP_RD_CONSUME | n=%0d sel=%0d hs=0x%0h raw0=0x%032h raw1=0x%032h valid_mask=0x%0h padding_mask=0x%0h reordered=0x%032h",
                            $time,
                            return_obs_deep_consume_count,
                            return_obs_mse0_data_sel_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_mse0_data_consume_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_mse0_ib_data_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][0],
                            return_obs_mse0_ib_data_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][1],
                            return_obs_mse0_data_mask_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_mse0_padding_mask_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_mse0_reordered_data_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                        );
                    end
                    if (
                        return_obs_mse0_buf_hs_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id]
                    ) begin
                        return_obs_mse0_buf_accept_count++;
                    end
                    if (
                        return_obs_mse0_buf_hs_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id] &&
                        return_obs_deep_buf_count < return_obs_deep_limit
                    ) begin
                        return_obs_deep_buf_count++;
                        $fdisplay(
                            return_obs_fd,
                            "%0t | DEEP_MSE0_TO_BUFFER0 | n=%0d data=0x%032h",
                            $time,
                            return_obs_deep_buf_count,
                            return_obs_mse0_buf_data_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                        );
                    end
                    if (
                        return_obs_mse3_buf_hs_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id]
                    ) begin
                        return_obs_mse3_buf_accept_count++;
                        if (
                            return_obs_mse3_buf_accept_count <=
                                return_obs_deep_limit
                        ) begin
                            $fdisplay(
                                return_obs_fd,
                                "%0t | DEEP_MSE3_TO_BUFFER4 | n=%0d data=0x%032h",
                                $time,
                                return_obs_mse3_buf_accept_count,
                                return_obs_mse3_buf_data_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id]
                            );
                        end
                    end
                    for (int deep_row = 0;
                         deep_row < `GA_ROW_PE_NUM;
                         deep_row++) begin
                        for (int deep_slot = 0;
                             deep_slot < 2;
                             deep_slot++) begin
                            if (
                                return_obs_ga_p0_enable_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id]
                                    [deep_row][deep_slot] &&
                                return_obs_ga_input_valid_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id]
                                    [deep_row][deep_slot] &&
                                return_obs_deep_ga_count <
                                    return_obs_deep_limit
                            ) begin
                                return_obs_deep_ga_count++;
                                $fdisplay(
                                    return_obs_fd,
                                    "%0t | DEEP_GA | n=%0d pe=%0d%0d opcode=0x%0h input=0x%0h alu_out=0x%08h out_wr=%0b",
                                    $time,
                                    return_obs_deep_ga_count,
                                    deep_row,
                                    deep_slot * 2,
                                    return_obs_ga_opcode_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id]
                                        [deep_row][deep_slot],
                                    return_obs_ga_input_data_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id]
                                        [deep_row][deep_slot],
                                    return_obs_ga_alu_output_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id]
                                        [deep_row][deep_slot],
                                    return_obs_ga_outbuffer_wr_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id]
                                        [deep_row][deep_slot]
                                );
                            end
                        end
                    end
                    if (
                        return_obs_mse4_idx_hs_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id] &&
                        return_obs_deep_mse4_count < return_obs_deep_limit
                    ) begin
                        return_obs_deep_mse4_count++;
                        $fdisplay(
                            return_obs_fd,
                            "%0t | DEEP_MSE4_INDEX | n=%0d lc0=0x%0h lc2=0x%0h pe1=0x%0h idx=0x%0h addr_bias=%0d idx_valid=%0b",
                            $time,
                            return_obs_deep_mse4_count,
                            return_obs_lc0_port_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_lc2_port_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_lc_pe1_port_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_mse4_idx_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_mse4_addr_bias_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id],
                            return_obs_mse4_idx_valid_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id]
                        );
                    end
                    $fflush(return_obs_fd);
                end
                for (int row = 0; row < `GA_ROW_PE_NUM; row++) begin
                    for (int slot = 0; slot < 2; slot++) begin
                        if (
                            return_obs_ga_enable_mon
                                [return_obs_group_id][return_obs_local_slice_id]
                                [row][slot] &&
                            return_obs_ga_p0_valid_mon
                                [return_obs_group_id][return_obs_local_slice_id]
                                [row][slot] &&
                            !return_obs_ga_p0_bp_post_mon
                                [return_obs_group_id][return_obs_local_slice_id]
                                [row][slot] &&
                            !return_obs_ga_p0_enable_mon
                                [return_obs_group_id][return_obs_local_slice_id]
                                [row][slot]
                        ) begin
                            return_obs_ga_stall_cycles[row][slot]++;
                            if (
                                return_obs_ga_stall_cycles[row][slot] >=
                                    return_obs_stall_limit &&
                                !return_obs_ga_stall_reported[row][slot]
                            ) begin
                                return_obs_ga_stall_reported[row][slot] = 1'b1;
                                $fdisplay(
                                    return_obs_fd,
                                    "%0t | STALL | slice=%0d pe=%0d%0d cycles=%0d opcode=0x%02h input_valid=%0b p0_valid=%0b bp_post=%0b p0_enable=%0b bp_pre=0x%0h",
                                    $time,
                                    return_obs_slice_id,
                                    row,
                                    slot * 2,
                                    return_obs_ga_stall_cycles[row][slot],
                                    return_obs_ga_opcode_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id][row][slot],
                                    return_obs_ga_input_valid_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id][row][slot],
                                    return_obs_ga_p0_valid_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id][row][slot],
                                    return_obs_ga_p0_bp_post_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id][row][slot],
                                    return_obs_ga_p0_enable_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id][row][slot],
                                    return_obs_ga_bp_pre_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id][row][slot]
                                );
                                return_obs_write_internal_state("GA_STALL");
                                $fflush(return_obs_fd);
                            end
                        end
                        else begin
                            return_obs_ga_stall_cycles[row][slot] = 0;
                        end
                    end
                end

                if (
                    (return_obs_active_cycles %
                        return_obs_heartbeat_period) == 0
                ) begin
                    return_obs_write_summary("HEARTBEAT");
                    return_obs_write_internal_state("HEARTBEAT");
                    for (int row = 0; row < `GA_ROW_PE_NUM; row++) begin
                        for (int slot = 0; slot < 2; slot++) begin
                            if (
                                return_obs_ga_enable_mon
                                    [return_obs_group_id]
                                    [return_obs_local_slice_id][row][slot]
                            ) begin
                                $fdisplay(
                                    return_obs_fd,
                                    "%0t | GA_STATE | pe=%0d%0d opcode=0x%02h input_valid=%0b p0_valid=%0b bp_post=%0b p0_enable=%0b bp_pre=0x%0h stall_cycles=%0d",
                                    $time,
                                    row,
                                    slot * 2,
                                    return_obs_ga_opcode_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id][row][slot],
                                    return_obs_ga_input_valid_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id][row][slot],
                                    return_obs_ga_p0_valid_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id][row][slot],
                                    return_obs_ga_p0_bp_post_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id][row][slot],
                                    return_obs_ga_p0_enable_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id][row][slot],
                                    return_obs_ga_bp_pre_mon
                                        [return_obs_group_id]
                                        [return_obs_local_slice_id][row][slot],
                                    return_obs_ga_stall_cycles[row][slot]
                                );
                            end
                        end
                    end
                    $fflush(return_obs_fd);
                end
            end

            if (return_obs_slice_finish_mon
                [return_obs_group_id][return_obs_local_slice_id] &&
                !return_obs_finish_d) begin
                return_obs_write_internal_state("COMP_FINISH");
                return_obs_write_summary("COMP_FINISH");
                return_obs_active = 1'b0;
            end

            return_obs_cfg_start_d =
                return_obs_sem_cfg_start_mon
                    [return_obs_group_id][return_obs_local_slice_id];
            return_obs_cfg_finish_d =
                return_obs_sem_cfg_finish_mon
                    [return_obs_group_id][return_obs_local_slice_id];
            return_obs_exec_start_d =
                return_obs_sem_exec_start_mon
                    [return_obs_group_id][return_obs_local_slice_id];
            return_obs_finish_d =
                return_obs_slice_finish_mon
                    [return_obs_group_id][return_obs_local_slice_id];
        end
    end

    // Targeted int32 SUM accumulator-state probe.  One record is emitted for
    // each accepted regular-GA input, up to a finite global limit.  The two
    // outbuffer slots are printed even when their tags are invalid because
    // the v5 return showed stale slot data being selected as input C at the
    // first spatial positions of the next block.
    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (
            u_NDP_Top_new.rst_n_sg &&
            return_obs_enabled &&
            return_obs_accum_state_enabled &&
            return_obs_active &&
            return_obs_fd != 0
        ) begin
            for (int row = 0; row < `GA_ROW_PE_NUM; row++) begin
                for (int slot = 0; slot < 2; slot++) begin
                    if (
                        return_obs_ga_operand_capture_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id][row][slot][0]
                    ) begin
                        return_obs_ga_operand0_capture_count++;
                    end
                    if (
                        return_obs_ga_operand_capture_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id][row][slot][2]
                    ) begin
                        return_obs_ga_operand2_capture_count++;
                    end
                    if (
                        return_obs_ga_p0_enable_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id][row][slot] &&
                        return_obs_ga_input_valid_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id][row][slot]
                    ) begin
                        return_obs_ga_accept_count++;
                    end
                    if (
                        return_obs_ga_p0_enable_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id][row][slot] &&
                        return_obs_ga_input_valid_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id][row][slot] &&
                        return_obs_accum_count < return_obs_accum_limit
                    ) begin
                        return_obs_accum_count++;
                        $fdisplay(
                            return_obs_fd,
                            "%0t | GA_ACCUM_STATE | n=%0d pe=%0d%0d opcode=0x%0h result_tag=0x%0h input0=0x%08h input1=0x%08h input2=0x%08h matched=%0b trans_init=0x%0h calc=%0b calc_reg=%0b calc_done=%0b calc_v0=%0b calc_v2=%0b ob_valid=%0b ob_count=%0d wr_ptr=%0d rd_ptr=%0d ob_wr_req=%0b ob_rd_req=%0b ob_wr=%0b ob_tag0=0x%0h ob_tag1=0x%0h ob_data0=0x%08h ob_data1=0x%08h",
                            $time,
                            return_obs_accum_count,
                            row,
                            slot * 2,
                            return_obs_ga_opcode_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_result_tag_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_input_data_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot][0],
                            return_obs_ga_input_data_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot][1],
                            return_obs_ga_input_data_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot][2],
                            return_obs_ga_matched_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_transout_initial_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_calculate_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_calculate_reg_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_calculate_done_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_calculate_v0_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_calculate_v2_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_ob_valid_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_ob_count_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_ob_wr_ptr_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_ob_rd_ptr_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_ob_wr_req_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_ob_rd_req_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_outbuffer_wr_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_ob_tag_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot][0],
                            return_obs_ga_ob_tag_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot][1],
                            return_obs_ga_ob_data_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot][0],
                            return_obs_ga_ob_data_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot][1]
                        );
                    end
                end
            end
            $fflush(return_obs_fd);
        end
    end

    // The Slice/GA/local-memory interface is clocked by clk_sg.  Keep the
    // decisive post-MSE0 probes in that domain; the older clk_db snapshots
    // remain for backward-compatible context only.
    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (
            u_NDP_Top_new.rst_n_sg &&
            return_obs_enabled &&
            return_obs_deep_enabled &&
            return_obs_active &&
            return_obs_fd != 0
        ) begin
            for (int row = 0; row < `GA_ROW_PE_NUM; row++) begin
                for (int slot = 0; slot < 2; slot++) begin
                    if (
                        return_obs_ga_p0_enable_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id][row][slot] &&
                        return_obs_ga_input_valid_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id][row][slot] &&
                        return_obs_sg_ga_input_count < return_obs_deep_limit
                    ) begin
                        return_obs_sg_ga_input_count++;
                        $fdisplay(
                            return_obs_fd,
                            "%0t | SG_GA_INPUT | n=%0d pe=%0d%0d opcode=0x%0h tag=0x%0h input0=0x%08h input1=0x%08h input2=0x%08h",
                            $time,
                            return_obs_sg_ga_input_count,
                            row,
                            slot * 2,
                            return_obs_ga_opcode_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_result_tag_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_input_data_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot][0],
                            return_obs_ga_input_data_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot][1],
                            return_obs_ga_input_data_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot][2]
                        );
                    end
                    if (
                        return_obs_ga_outbuffer_wr_mon
                            [return_obs_group_id]
                            [return_obs_local_slice_id][row][slot] &&
                        return_obs_sg_ga_output_count < return_obs_deep_limit
                    ) begin
                        return_obs_sg_ga_output_count++;
                        $fdisplay(
                            return_obs_fd,
                            "%0t | SG_GA_OUTPUT | n=%0d pe=%0d%0d tag=0x%0h data=0x%08h",
                            $time,
                            return_obs_sg_ga_output_count,
                            row,
                            slot * 2,
                            return_obs_ga_result_tag_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot],
                            return_obs_ga_alu_output_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][row][slot]
                        );
                    end
                end
            end
            for (int channel = 0;
                 channel < `MSE_REQ_CHL_NUM;
                 channel++) begin
                if (
                    local_req_hs
                        [return_obs_group_id]
                        [return_obs_local_slice_id][4][channel]
                ) begin
                    return_obs_sg_mse4_req_count[channel]++;
                    if (
                        return_obs_sg_mse4_req_count[channel] <=
                            return_obs_deep_limit
                    ) begin
                        $fdisplay(
                            return_obs_fd,
                            "%0t | SG_MSE4_REQ | n=%0d ch=%0d addr=0x%0h req_ch=%0d wdata_ch=%0d outstanding=%0d",
                            $time,
                            return_obs_sg_mse4_req_count[0] +
                                return_obs_sg_mse4_req_count[1],
                            channel,
                            return_obs_mse4_local_req_addr_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][channel],
                            return_obs_sg_mse4_req_count[channel],
                            return_obs_sg_mse4_wdata_count[channel],
                            return_obs_sg_mse4_req_count[channel] -
                                return_obs_sg_mse4_wdata_count[channel]
                        );
                    end
                end
                if (
                    local_wdata_hs
                        [return_obs_group_id]
                        [return_obs_local_slice_id][4][channel]
                ) begin
                    return_obs_sg_mse4_wdata_count[channel]++;
                    if (
                        return_obs_sg_mse4_wdata_count[channel] <=
                            return_obs_deep_limit
                    ) begin
                        $fdisplay(
                            return_obs_fd,
                            "%0t | SG_MSE4_WDATA | n=%0d ch=%0d data=0x%032h req_ch=%0d wdata_ch=%0d outstanding=%0d",
                            $time,
                            return_obs_sg_mse4_wdata_count[0] +
                                return_obs_sg_mse4_wdata_count[1],
                            channel,
                            return_obs_mse4_local_wdata_mon
                                [return_obs_group_id]
                                [return_obs_local_slice_id][channel],
                            return_obs_sg_mse4_req_count[channel],
                            return_obs_sg_mse4_wdata_count[channel],
                            return_obs_sg_mse4_req_count[channel] -
                                return_obs_sg_mse4_wdata_count[channel]
                        );
                    end
                end
            end
            $fflush(return_obs_fd);
        end
    end

    final begin
        if (return_obs_fd != 0) begin
            return_obs_write_summary("FINAL");
            $fclose(return_obs_fd);
        end
    end
