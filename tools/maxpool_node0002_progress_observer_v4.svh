// Read-only, low-volume progress observer for the native MaxPool node0002 test.
// The include is selected at compile time by NATIVE_RETURN_OBSERVER_ENABLE and
// enabled at runtime with +RETURN_OBSERVER.  It never drives DUT/TB signals.
`ifdef NATIVE_RETURN_OBSERVER_ENABLE

    logic [1:0] return_mp_slice_finish_mon;
    logic [1:0][`GA_ROW_PE_NUM-1:0][1:0]
        return_mp_p0_valid_mon;
    logic [1:0][`GA_ROW_PE_NUM-1:0][1:0]
        return_mp_p0_ready_mon;
    logic [1:0][`GA_ROW_PE_NUM-1:0][1:0]
        return_mp_p0_capture_mon;
    logic [1:0][`GA_ROW_PE_NUM-1:0][1:0]
        return_mp_ga_output_mon;
    logic [1:0] return_mp_req_any_mon;
    logic [1:0] return_mp_rdata_any_mon;
    logic [1:0] return_mp_wdata_any_mon;
    logic [1:0] return_mp_capture_any_mon;
    logic [1:0] return_mp_ga_output_any_mon;
    logic [1:0] return_mp_p0_valid_any_mon;
    logic [1:0] return_mp_p0_ready_any_mon;

    generate
        for (genvar return_mp_slice = 0;
             return_mp_slice < 2;
             return_mp_slice++) begin : RETURN_MP_SLICE_GEN
            assign return_mp_slice_finish_mon[return_mp_slice] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group
                    .slice_group_gen[return_mp_slice]
                    .u_slice_wrapper.u_Slice
                    .u_Slice_Execution_Manager.slice_cmpt_finish;
            assign return_mp_req_any_mon[return_mp_slice] =
                |local_req_hs[0][return_mp_slice];
            assign return_mp_rdata_any_mon[return_mp_slice] =
                |local_rdata_hs[0][return_mp_slice];
            assign return_mp_wdata_any_mon[return_mp_slice] =
                |local_wdata_hs[0][return_mp_slice];
            assign return_mp_capture_any_mon[return_mp_slice] =
                |return_mp_p0_capture_mon[return_mp_slice];
            assign return_mp_ga_output_any_mon[return_mp_slice] =
                |return_mp_ga_output_mon[return_mp_slice];
            assign return_mp_p0_valid_any_mon[return_mp_slice] =
                |return_mp_p0_valid_mon[return_mp_slice];
            assign return_mp_p0_ready_any_mon[return_mp_slice] =
                |return_mp_p0_ready_mon[return_mp_slice];
            for (genvar return_mp_row = 0;
                 return_mp_row < `GA_ROW_PE_NUM;
                 return_mp_row++) begin : RETURN_MP_ROW_GEN
                assign return_mp_p0_valid_mon
                    [return_mp_slice][return_mp_row][0] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_mp_slice]
                        .u_slice_wrapper.u_Slice.u_General_Array
                        .u_GA_PE_Group.GA_ROW_PE[return_mp_row]
                        .GA_COL_PE[0].GA_PE.u_GA_PE
                        .u_GA_PE_Inbuffer.alu_pipeline0_valid_bit;
                assign return_mp_p0_valid_mon
                    [return_mp_slice][return_mp_row][1] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_mp_slice]
                        .u_slice_wrapper.u_Slice.u_General_Array
                        .u_GA_PE_Group.GA_ROW_PE[return_mp_row]
                        .GA_COL_PE[2].GA_PE.u_GA_PE
                        .u_GA_PE_Inbuffer.alu_pipeline0_valid_bit;
                assign return_mp_p0_ready_mon
                    [return_mp_slice][return_mp_row][0] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_mp_slice]
                        .u_slice_wrapper.u_Slice.u_General_Array
                        .u_GA_PE_Group.GA_ROW_PE[return_mp_row]
                        .GA_COL_PE[0].GA_PE.u_GA_PE
                        .u_GA_PE_Inbuffer.alu_pipeline0_bp_post;
                assign return_mp_p0_ready_mon
                    [return_mp_slice][return_mp_row][1] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_mp_slice]
                        .u_slice_wrapper.u_Slice.u_General_Array
                        .u_GA_PE_Group.GA_ROW_PE[return_mp_row]
                        .GA_COL_PE[2].GA_PE.u_GA_PE
                        .u_GA_PE_Inbuffer.alu_pipeline0_bp_post;
                assign return_mp_p0_capture_mon
                    [return_mp_slice][return_mp_row][0] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_mp_slice]
                        .u_slice_wrapper.u_Slice.u_General_Array
                        .u_GA_PE_Group.GA_ROW_PE[return_mp_row]
                        .GA_COL_PE[0].GA_PE.u_GA_PE
                        .u_GA_PE_Inbuffer.ga_pe_alu_pipeline0_enable;
                assign return_mp_p0_capture_mon
                    [return_mp_slice][return_mp_row][1] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_mp_slice]
                        .u_slice_wrapper.u_Slice.u_General_Array
                        .u_GA_PE_Group.GA_ROW_PE[return_mp_row]
                        .GA_COL_PE[2].GA_PE.u_GA_PE
                        .u_GA_PE_Inbuffer.ga_pe_alu_pipeline0_enable;
                assign return_mp_ga_output_mon
                    [return_mp_slice][return_mp_row][0] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_mp_slice]
                        .u_slice_wrapper.u_Slice.u_General_Array
                        .u_GA_PE_Group.GA_ROW_PE[return_mp_row]
                        .GA_COL_PE[0].GA_PE.u_GA_PE.ga_pe_outbuffer_wr_en;
                assign return_mp_ga_output_mon
                    [return_mp_slice][return_mp_row][1] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[return_mp_slice]
                        .u_slice_wrapper.u_Slice.u_General_Array
                        .u_GA_PE_Group.GA_ROW_PE[return_mp_row]
                        .GA_COL_PE[2].GA_PE.u_GA_PE.ga_pe_outbuffer_wr_en;
            end
        end
    endgenerate

    integer return_mp_fd;
    string return_mp_file;
    integer return_mp_enabled;
    integer return_mp_active;
    integer return_mp_active_slice;
    integer return_mp_sample_cycles;
    integer return_mp_stall_windows;
    integer return_mp_zero_windows;
    integer return_mp_plusarg_status;
    longint unsigned return_mp_active_cycles;
    longint unsigned return_mp_clk_sg_edges;
    longint unsigned return_mp_req;
    longint unsigned return_mp_rdata;
    longint unsigned return_mp_wdata;
    longint unsigned return_mp_capture;
    longint unsigned return_mp_ga_output;
    longint unsigned return_mp_finish;
    longint unsigned return_mp_previous_progress;
    longint unsigned return_mp_progress;
    longint unsigned return_mp_delta;
    logic return_mp_raw_p0_valid;
    logic return_mp_raw_p0_ready;
    string return_mp_boundary;

    initial begin
        return_mp_fd = 0;
        return_mp_file = "return_observer.log";
        return_mp_enabled = 0;
        return_mp_active = 0;
        return_mp_active_slice = 0;
        return_mp_sample_cycles = 262144;
        return_mp_stall_windows = 4;
        return_mp_zero_windows = 0;
        return_mp_active_cycles = 0;
        return_mp_clk_sg_edges = 0;
        return_mp_req = 0;
        return_mp_rdata = 0;
        return_mp_wdata = 0;
        return_mp_capture = 0;
        return_mp_ga_output = 0;
        return_mp_finish = 0;
        return_mp_previous_progress = 0;
        if ($test$plusargs("RETURN_OBSERVER")) begin
            return_mp_enabled = 1;
            return_mp_plusarg_status =
                $value$plusargs("RETURN_OBS_FILE=%s", return_mp_file);
            return_mp_plusarg_status =
                $value$plusargs(
                    "RETURN_OBS_SAMPLE_CYCLES=%d", return_mp_sample_cycles);
            return_mp_plusarg_status =
                $value$plusargs(
                    "RETURN_OBS_STALL_WINDOWS=%d", return_mp_stall_windows);
            if (return_mp_sample_cycles <= 0 ||
                return_mp_stall_windows <= 0) begin
                $fatal(1, "invalid MaxPool observer sampling contract");
            end
            return_mp_fd = $fopen(return_mp_file, "w");
            if (return_mp_fd == 0) begin
                $fatal(1, "cannot open MaxPool return observer file");
            end
            $fdisplay(
                return_mp_fd,
                "[MAXPOOL_RETURN_OBSERVER] enabled sample_cycles=%0d stall_windows=%0d",
                return_mp_sample_cycles,
                return_mp_stall_windows
            );
            $fflush(return_mp_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg) begin
        if (return_mp_enabled != 0) begin
            return_mp_clk_sg_edges = return_mp_clk_sg_edges + 1;
            if (return_mp_active != 0) begin
                if (return_mp_req_any_mon[return_mp_active_slice])
                    return_mp_req = return_mp_req + 1;
                if (return_mp_rdata_any_mon[return_mp_active_slice])
                    return_mp_rdata = return_mp_rdata + 1;
                if (return_mp_wdata_any_mon[return_mp_active_slice])
                    return_mp_wdata = return_mp_wdata + 1;
                if (return_mp_capture_any_mon[return_mp_active_slice])
                    return_mp_capture = return_mp_capture + 1;
                if (return_mp_ga_output_any_mon[return_mp_active_slice])
                    return_mp_ga_output = return_mp_ga_output + 1;
                if (return_mp_slice_finish_mon[return_mp_active_slice])
                    return_mp_finish = return_mp_finish + 1;
            end
        end
    end

    always @(negedge u_NDP_Top_new.clk_db) begin
        if (return_mp_enabled != 0) begin
            if (gexec2slice_fire_mon[0][0]) begin
                return_mp_active = 1;
                return_mp_active_slice = 0;
                return_mp_active_cycles = 0;
                return_mp_previous_progress =
                    return_mp_req + return_mp_rdata + return_mp_wdata +
                    return_mp_capture + return_mp_ga_output + return_mp_finish;
                return_mp_zero_windows = 0;
                $fdisplay(
                    return_mp_fd,
                    "| MAXPOOL_EXEC_START_V1 | slice=0 sim_time=%0t clk_sg_edges=%0d",
                    $time, return_mp_clk_sg_edges
                );
                $fflush(return_mp_fd);
            end else if (gexec2slice_fire_mon[0][1]) begin
                return_mp_active = 1;
                return_mp_active_slice = 1;
                return_mp_active_cycles = 0;
                return_mp_previous_progress =
                    return_mp_req + return_mp_rdata + return_mp_wdata +
                    return_mp_capture + return_mp_ga_output + return_mp_finish;
                return_mp_zero_windows = 0;
                $fdisplay(
                    return_mp_fd,
                    "| MAXPOOL_EXEC_START_V1 | slice=1 sim_time=%0t clk_sg_edges=%0d",
                    $time, return_mp_clk_sg_edges
                );
                $fflush(return_mp_fd);
            end
            if (return_mp_active != 0) begin
                return_mp_active_cycles = return_mp_active_cycles + 1;
                if (return_mp_slice_finish_mon[return_mp_active_slice]) begin
                    $fdisplay(
                        return_mp_fd,
                        "| MAXPOOL_STAGE_FINISH_V1 | slice=%0d active_cycles=%0d sim_time=%0t",
                        return_mp_active_slice,
                        return_mp_active_cycles,
                        $time
                    );
                    $fflush(return_mp_fd);
                    return_mp_active = 0;
                end else if (
                    (return_mp_active_cycles % return_mp_sample_cycles) == 0
                ) begin
                    return_mp_progress =
                        return_mp_req + return_mp_rdata + return_mp_wdata +
                        return_mp_capture + return_mp_ga_output +
                        return_mp_finish;
                    return_mp_delta =
                        return_mp_progress - return_mp_previous_progress;
                    return_mp_raw_p0_valid =
                        return_mp_p0_valid_any_mon[return_mp_active_slice];
                    return_mp_raw_p0_ready =
                        return_mp_p0_ready_any_mon[return_mp_active_slice];
                    if (return_mp_delta == 0)
                        return_mp_zero_windows = return_mp_zero_windows + 1;
                    else
                        return_mp_zero_windows = 0;
                    $fdisplay(
                        return_mp_fd,
                        "| MAXPOOL_PROGRESS_WINDOW_V1 | slice=%0d active_cycles=%0d sim_time=%0t clk_sg_edges=%0d progress=%0d delta=%0d req=%0d rdata=%0d wdata=%0d p0_capture=%0d ga_output=%0d finish=%0d raw_p0_valid=%0d raw_p0_ready=%0d",
                        return_mp_active_slice,
                        return_mp_active_cycles,
                        $time,
                        return_mp_clk_sg_edges,
                        return_mp_progress,
                        return_mp_delta,
                        return_mp_req,
                        return_mp_rdata,
                        return_mp_wdata,
                        return_mp_capture,
                        return_mp_ga_output,
                        return_mp_finish,
                        return_mp_raw_p0_valid,
                        return_mp_raw_p0_ready
                    );
                    $fflush(return_mp_fd);
                    return_mp_previous_progress = return_mp_progress;
                    if (return_mp_zero_windows >= return_mp_stall_windows) begin
                        if (return_mp_req == 0)
                            return_mp_boundary =
                                "EXEC_START_TO_FIRST_MSE_REQUEST";
                        else if (return_mp_rdata == 0)
                            return_mp_boundary =
                                "MSE_REQUEST_TO_READ_DATA";
                        else if (return_mp_capture == 0)
                            return_mp_boundary =
                                "READ_DATA_TO_GA_PIPELINE0_CAPTURE";
                        else if (return_mp_ga_output == 0)
                            return_mp_boundary =
                                "GA_PIPELINE0_CAPTURE_TO_GA_OUTBUFFER_WRITE";
                        else if (return_mp_wdata == 0)
                            return_mp_boundary =
                                "GA_OUTPUT_TO_D_WRITE_DATA";
                        else
                            return_mp_boundary =
                                "D_WRITE_DATA_TO_SLICE_FINISH";
                        $fdisplay(
                            return_mp_fd,
                            "| CANONICAL_MAXPOOL_DIAG_DECISION_V1 | schema=maxpool_node0002_diag version=1 decision=LONG_RUNNING_HANG_AT_%s reason=STALL_WINDOW_EXCEEDED boundary=%s slice=%0d window_cycles=%0d zero_windows=%0d qualified_progress=%0d qualified_delta=%0d req=%0d rdata=%0d wdata=%0d p0_capture=%0d ga_output=%0d finish=%0d content_digest=MPQV1_%0d_%0d_%0d",
                            return_mp_boundary,
                            return_mp_boundary,
                            return_mp_active_slice,
                            return_mp_sample_cycles,
                            return_mp_zero_windows,
                            return_mp_progress,
                            return_mp_delta,
                            return_mp_req,
                            return_mp_rdata,
                            return_mp_wdata,
                            return_mp_capture,
                            return_mp_ga_output,
                            return_mp_finish,
                            return_mp_progress,
                            return_mp_delta,
                            return_mp_active_slice
                        );
                        $fflush(return_mp_fd);
                        $fatal(
                            1,
                            "MaxPool bounded progress diagnostic localized stall"
                        );
                    end
                end
            end
        end
    end

    final begin
        if (return_mp_fd != 0) begin
            $fflush(return_mp_fd);
            $fclose(return_mp_fd);
        end
    end

`endif
