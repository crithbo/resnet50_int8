// node0004 v13 narrow A/B -> PE -> SA-output boundary probe.
//
// These taps are diagnostic only.  They never contribute to the monotonic
// progress counter or the stall decision.  The counters below count qualified
// PE/result handshakes; the masks are snapshots used to identify the first
// boundary that is not reachable after MSE read-data delivery.

    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][1:0]
          return_obs_abpe_masked_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_abpe_all_matched_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_abpe_alu_accept_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_abpe_out_valid_mon;
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_abpe_out_accept_mon;

    generate
        for (genvar return_obs_abpe_group = 0;
             return_obs_abpe_group < `SLICE_GROUP_SIZE;
             return_obs_abpe_group++) begin : RETURN_OBS_ABPE_GROUP_GEN
            for (genvar return_obs_abpe_slice = 0;
                 return_obs_abpe_slice < `SLICE_GROUP_NUM;
                 return_obs_abpe_slice++) begin : RETURN_OBS_ABPE_SLICE_GEN
                for (genvar return_obs_abpe_row = 0;
                     return_obs_abpe_row < `SA_ROW_PE_NUM;
                     return_obs_abpe_row++) begin : RETURN_OBS_ABPE_ROW_GEN
                    for (genvar return_obs_abpe_col = 0;
                         return_obs_abpe_col < `SA_COL_PE_NUM;
                         return_obs_abpe_col++) begin : RETURN_OBS_ABPE_COL_GEN
                        assign return_obs_abpe_masked_valid_mon
                            [return_obs_abpe_group][return_obs_abpe_slice]
                            [return_obs_abpe_row][return_obs_abpe_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_abpe_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_abpe_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_abpe_row]
                                .SA_COL_PE[return_obs_abpe_col]
                                .u_SA_PE.u_SA_PE_Control_Block
                                .sa_pe_inport_valid_bit_masked[1:0];
                        assign return_obs_abpe_all_matched_mon
                            [return_obs_abpe_group][return_obs_abpe_slice]
                            [return_obs_abpe_row][return_obs_abpe_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_abpe_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_abpe_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_abpe_row]
                                .SA_COL_PE[return_obs_abpe_col]
                                .u_SA_PE.u_SA_PE_Control_Block
                                .sa_pe_all_inport_matched;
                        assign return_obs_abpe_alu_accept_mon
                            [return_obs_abpe_group][return_obs_abpe_slice]
                            [return_obs_abpe_row][return_obs_abpe_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_abpe_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_abpe_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_abpe_row]
                                .SA_COL_PE[return_obs_abpe_col]
                                .u_SA_PE.sa_pe_cb2ob_alu_bp_pre;
                        assign return_obs_abpe_out_valid_mon
                            [return_obs_abpe_group][return_obs_abpe_slice]
                            [return_obs_abpe_row][return_obs_abpe_col] =
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_abpe_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_abpe_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_abpe_row]
                                .SA_COL_PE[return_obs_abpe_col]
                                .u_SA_PE.sa_pe_outbuffer_port
                                [`SA_PE_PORT_WIDTH-1];
                        assign return_obs_abpe_out_accept_mon
                            [return_obs_abpe_group][return_obs_abpe_slice]
                            [return_obs_abpe_row][return_obs_abpe_col] =
                            return_obs_abpe_out_valid_mon
                                [return_obs_abpe_group][return_obs_abpe_slice]
                                [return_obs_abpe_row][return_obs_abpe_col] &
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen
                                [return_obs_abpe_group]
                                .u_slice_with_datahub_mc_group
                                .slice_group_gen[return_obs_abpe_slice]
                                .u_slice_wrapper.u_Slice
                                .u_Specialized_Array.u_SA_PE_Group
                                .SA_ROW_PE[return_obs_abpe_row]
                                .SA_COL_PE[return_obs_abpe_col]
                                .u_SA_PE.sa_pe_outport_bp_post;
                    end
                end
            end
        end
    endgenerate

    bit return_obs_abpe_enabled;
    longint unsigned return_obs_abpe_group_accept_count [0:2];
    longint unsigned return_obs_abpe_alu_accept_count;
    longint unsigned return_obs_abpe_out_accept_count;
    longint unsigned return_obs_abpe_group_out_accept_count;

    initial begin
        return_obs_abpe_enabled = $test$plusargs("RETURN_OBS_ABPE");
        for (int return_obs_abpe_group_idx = 0;
             return_obs_abpe_group_idx < 3;
             return_obs_abpe_group_idx++)
            return_obs_abpe_group_accept_count[return_obs_abpe_group_idx] = 0;
        return_obs_abpe_alu_accept_count = 0;
        return_obs_abpe_out_accept_count = 0;
        return_obs_abpe_group_out_accept_count = 0;
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        if (!u_NDP_Top_new.rst_n_db) begin
            for (int return_obs_abpe_group_idx = 0;
                 return_obs_abpe_group_idx < 3;
                 return_obs_abpe_group_idx++)
                return_obs_abpe_group_accept_count
                    [return_obs_abpe_group_idx] = 0;
            return_obs_abpe_alu_accept_count = 0;
            return_obs_abpe_out_accept_count = 0;
            return_obs_abpe_group_out_accept_count = 0;
        end
        else if (
            return_obs_abpe_enabled &&
            return_obs_sem_exec_start_mon
                [return_obs_group_id][return_obs_local_slice_id] &&
            !return_obs_exec_start_d
        ) begin
            for (int return_obs_abpe_group_idx = 0;
                 return_obs_abpe_group_idx < 3;
                 return_obs_abpe_group_idx++)
                return_obs_abpe_group_accept_count
                    [return_obs_abpe_group_idx] = 0;
            return_obs_abpe_alu_accept_count = 0;
            return_obs_abpe_out_accept_count = 0;
            return_obs_abpe_group_out_accept_count = 0;
        end
        else if (return_obs_abpe_enabled && return_obs_active) begin
            for (int return_obs_abpe_group_idx = 0;
                 return_obs_abpe_group_idx < 3;
                 return_obs_abpe_group_idx++) begin
                if (
                    (|return_obs_sa_in_tag_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [return_obs_abpe_group_idx][0]
                        [`SA_INPORT_GROUP_TAG-1 -: `SA_INPORT_NUM]) &&
                    return_obs_sa_in_buf_bp_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [return_obs_abpe_group_idx][0]
                )
                    return_obs_abpe_group_accept_count
                        [return_obs_abpe_group_idx]++;
            end
            for (int return_obs_abpe_row_idx = 0;
                 return_obs_abpe_row_idx < `SA_ROW_PE_NUM;
                 return_obs_abpe_row_idx++) begin
                for (int return_obs_abpe_col_idx = 0;
                     return_obs_abpe_col_idx < `SA_COL_PE_NUM;
                     return_obs_abpe_col_idx++) begin
                    if (
                        return_obs_abpe_alu_accept_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_abpe_row_idx]
                            [return_obs_abpe_col_idx]
                    )
                        return_obs_abpe_alu_accept_count++;
                    if (
                        return_obs_abpe_out_accept_mon
                            [return_obs_group_id][return_obs_local_slice_id]
                            [return_obs_abpe_row_idx]
                            [return_obs_abpe_col_idx]
                    )
                        return_obs_abpe_out_accept_count++;
                end
            end
            if (
                (|return_obs_sa_out_tag_mon
                    [return_obs_group_id][return_obs_local_slice_id]
                    [`SA_OUTPORT_GROUP_TAG-1 -: `SA_OUTPORT_NUM]) &&
                return_obs_buf_accept_sa_mon
                    [return_obs_group_id][return_obs_local_slice_id][0][0]
            )
                return_obs_abpe_group_out_accept_count++;
        end
    end

    task automatic return_obs_write_abpe_state(input string event_name);
        begin
            if (return_obs_abpe_enabled && return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | ABPE_BOUNDARY_V1 | event=%s a_group_accept=%0d b_group_accept=%0d c_group_accept=%0d alu_accept=%0d pe_out_accept=%0d sa_group_out_accept=%0d masked_a=0x%0h masked_b=0x%0h all_matched=0x%0h out_valid=0x%0h",
                    $time,
                    event_name,
                    return_obs_abpe_group_accept_count[0],
                    return_obs_abpe_group_accept_count[1],
                    return_obs_abpe_group_accept_count[2],
                    return_obs_abpe_alu_accept_count,
                    return_obs_abpe_out_accept_count,
                    return_obs_abpe_group_out_accept_count,
                    return_obs_abpe_masked_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][0],
                    return_obs_abpe_masked_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][1],
                    return_obs_abpe_all_matched_mon
                        [return_obs_group_id][return_obs_local_slice_id],
                    return_obs_abpe_out_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                );
                $fflush(return_obs_fd);
            end
        end
    end
