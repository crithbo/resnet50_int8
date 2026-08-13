// Native Conv c0 public-surface order witness.
//
// This append consumes only n4d_* package-local monitors already compiled and
// exercised by p10.  It adds no DUT hierarchy reference and never drives DUT
// state.  Accepted events are captured into fixed-size arrays and emitted only
// once after the first qualified p10 no-progress window (or at simulator final).

bit n4p_enabled;
bit n4p_snapshot_emitted;
bit n4p_sa_out_raw_valid_d;
integer n4p_fd;
integer n4p_plusarg_status;
integer n4p_event_limit;
integer n4p_sa_in_saved;
integer n4p_sa_out_saved;
integer n4p_sa_out_raw_change_count;
integer n4p_sa_out_raw_active_cycles;
integer n4p_sa_out_ready_active_cycles;
integer n4p_sa_out_blocked_cycles;
integer n4p_mse4_saved;
string n4p_output_path;
logic [`ARRAY_PORT_TAG-1:0] n4p_sa_in_tag [0:63];
logic [`ARRAY_PORT_TAG-1:0] n4p_sa_out_tag [0:63];
logic [`ARRAY_PORT_TAG-1:0] n4p_sa_out_raw_tag_d;
logic [`ARRAY_PORT_TAG-1:0] n4p_sa_out_raw_tag_now;
logic n4p_sa_out_raw_valid_now;
logic n4p_sa_out_ready_now;
longint unsigned n4p_sa_in_cycle [0:63];
longint unsigned n4p_sa_out_cycle [0:63];
longint unsigned n4p_mse4_cycle [0:63];
integer n4p_sa_in_port [0:63];
integer n4p_sa_in_buf [0:63];
integer n4p_sa_out_port [0:63];
integer n4p_sa_out_buf [0:63];

task automatic n4p_reset();
    n4p_snapshot_emitted = 0;
    n4p_sa_out_raw_valid_d = 0;
    n4p_sa_in_saved = 0;
    n4p_sa_out_saved = 0;
    n4p_sa_out_raw_change_count = 0;
    n4p_sa_out_raw_active_cycles = 0;
    n4p_sa_out_ready_active_cycles = 0;
    n4p_sa_out_blocked_cycles = 0;
    n4p_mse4_saved = 0;
    n4p_sa_out_raw_tag_d = 0;
    n4p_sa_out_raw_tag_now = 0;
    n4p_sa_out_raw_valid_now = 0;
    n4p_sa_out_ready_now = 0;
endtask

task automatic n4p_emit_snapshot(input string reason);
    if (n4p_fd != 0 && !n4p_snapshot_emitted) begin
        n4p_snapshot_emitted = 1;
        $fdisplay(
            n4p_fd,
            "N4P_SNAPSHOT_V1 reason=%s stage=c0 slice=%0d sg_cycle=%0d qualified_key_total=%0d sain_saved=%0d saout_saved=%0d mse4_saved=%0d saout_raw_changes=%0d saout_raw_active=%0d saout_ready_active=%0d saout_blocked=%0d saout_raw_valid_now=%0d saout_ready_now=%0d saout_raw_tag_now=0x%0h b5_mask_now=0x%0h armfin=%0d,%0d,%0d,%0d,%0d,%0d",
            reason,
            n4d_slice_id,
            n4t_sg_cycle,
            n4t_key_total(),
            n4p_sa_in_saved,
            n4p_sa_out_saved,
            n4p_mse4_saved,
            n4p_sa_out_raw_change_count,
            n4p_sa_out_raw_active_cycles,
            n4p_sa_out_ready_active_cycles,
            n4p_sa_out_blocked_cycles,
            n4p_sa_out_raw_valid_now,
            n4p_sa_out_ready_now,
            n4p_sa_out_raw_tag_now,
            n4d_buf45_wr_en_mon[n4d_group_id][n4d_local_slice_id][1],
            n4t_arm_finish_count[0], n4t_arm_finish_count[1],
            n4t_arm_finish_count[2], n4t_arm_finish_count[3],
            n4t_arm_finish_count[4], n4t_arm_finish_count[5]
        );
        for (int idx = 0; idx < n4p_sa_in_saved; idx++) begin
            $fdisplay(
                n4p_fd,
                "N4P_EVENT_V1 kind=SA_IN_ACCEPT seq=%0d cycle=%0d port=%0d buf=%0d tag=0x%0h",
                idx,
                n4p_sa_in_cycle[idx],
                n4p_sa_in_port[idx],
                n4p_sa_in_buf[idx],
                n4p_sa_in_tag[idx]
            );
        end
        for (int idx = 0; idx < n4p_sa_out_saved; idx++) begin
            $fdisplay(
                n4p_fd,
                "N4P_EVENT_V1 kind=SA_OUT_ACCEPT seq=%0d cycle=%0d port=%0d buf=%0d tag=0x%0h",
                idx,
                n4p_sa_out_cycle[idx],
                n4p_sa_out_port[idx],
                n4p_sa_out_buf[idx],
                n4p_sa_out_tag[idx]
            );
        end
        for (int idx = 0; idx < n4p_mse4_saved; idx++) begin
            $fdisplay(
                n4p_fd,
                "N4P_EVENT_V1 kind=MSE4_INDEX_ACCEPT seq=%0d cycle=%0d",
                idx,
                n4p_mse4_cycle[idx]
            );
        end
        $fflush(n4p_fd);
    end
endtask

initial begin
    n4p_enabled = $test$plusargs("N4P_PUBLIC_ORDER_PROFILE");
    n4p_output_path = "public_order_observer.log";
    n4p_event_limit = 64;
    n4p_plusarg_status =
        $value$plusargs("N4P_FILE=%s", n4p_output_path);
    n4p_plusarg_status =
        $value$plusargs("N4P_EVENT_LIMIT=%d", n4p_event_limit);
    n4p_fd = 0;
    n4p_reset();
    if (n4p_enabled) begin
        if (n4p_event_limit <= 0 || n4p_event_limit > 64) begin
            $error("N4P event limit must be in [1,64]");
            n4p_enabled = 0;
        end
        else begin
            n4p_fd = $fopen(n4p_output_path, "w");
            if (n4p_fd == 0) begin
                $error("N4P observer output cannot be created");
                n4p_enabled = 0;
            end
            else begin
                $fdisplay(
                    n4p_fd,
                    "N4P_FEATURE_ENABLE_V1 feature=NATIVE4_PUBLIC_ORDER enabled=1 stage=c0 slice=%0d event_limit=%0d drives_dut=0 changes_timeout=0 public_monitor_reuse=1 per_event_live_io=0",
                    n4d_slice_id,
                    n4p_event_limit
                );
                $fflush(n4p_fd);
                $display(
                    "[RETURN_OBSERVER] enabled N4P_FEATURE_ENABLE_V1 feature=NATIVE4_PUBLIC_ORDER enabled=1 event_limit=%0d",
                    n4p_event_limit
                );
            end
        end
    end
end

always @(posedge u_NDP_Top_new.clk_sg or
         negedge u_NDP_Top_new.rst_n_sg) begin
    if (!u_NDP_Top_new.rst_n_sg) begin
        n4p_reset();
    end
    else if (n4p_enabled && n4d_active) begin
        n4p_sa_out_raw_valid_now = 0;
        n4p_sa_out_ready_now = 0;
        n4p_sa_out_raw_tag_now = 0;
        for (int sa_in = 0; sa_in < `SA_INPORT_GROUP_NUM; sa_in++) begin
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
                        [n4d_local_slice_id][sa_in][sa_buf] &&
                    n4p_sa_in_saved < n4p_event_limit
                ) begin
                    n4p_sa_in_cycle[n4p_sa_in_saved] = n4t_sg_cycle;
                    n4p_sa_in_port[n4p_sa_in_saved] = sa_in;
                    n4p_sa_in_buf[n4p_sa_in_saved] = sa_buf;
                    n4p_sa_in_tag[n4p_sa_in_saved] =
                        n4d_buf2sa_tag_mon[n4d_group_id]
                            [n4d_local_slice_id][sa_in][sa_buf];
                    n4p_sa_in_saved++;
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
                    |n4d_sa2buf_tag_mon[n4d_group_id]
                        [n4d_local_slice_id][sa_out][sa_buf]
                        [`ARRAY_PORT_TAG-1 -: `ARRAY_PORT_GROUP_SIZE]
                ) begin
                    n4p_sa_out_raw_valid_now = 1;
                    n4p_sa_out_raw_tag_now =
                        n4d_sa2buf_tag_mon[n4d_group_id]
                            [n4d_local_slice_id][sa_out][sa_buf];
                    if (
                        n4d_buf_accept_sa_mon[n4d_group_id]
                            [n4d_local_slice_id][sa_out][sa_buf]
                    ) begin
                        n4p_sa_out_ready_now = 1;
                        if (n4p_sa_out_saved < n4p_event_limit) begin
                            n4p_sa_out_cycle[n4p_sa_out_saved] =
                                n4t_sg_cycle;
                            n4p_sa_out_port[n4p_sa_out_saved] = sa_out;
                            n4p_sa_out_buf[n4p_sa_out_saved] = sa_buf;
                            n4p_sa_out_tag[n4p_sa_out_saved] =
                                n4d_sa2buf_tag_mon[n4d_group_id]
                                    [n4d_local_slice_id][sa_out][sa_buf];
                            n4p_sa_out_saved++;
                        end
                    end
                end
            end
        end
        if (n4p_sa_out_raw_valid_now) begin
            n4p_sa_out_raw_active_cycles++;
            if (n4p_sa_out_ready_now) begin
                n4p_sa_out_ready_active_cycles++;
            end
            else begin
                n4p_sa_out_blocked_cycles++;
            end
            if (
                !n4p_sa_out_raw_valid_d ||
                n4p_sa_out_raw_tag_now != n4p_sa_out_raw_tag_d
            ) begin
                n4p_sa_out_raw_change_count++;
            end
        end
        n4p_sa_out_raw_valid_d = n4p_sa_out_raw_valid_now;
        n4p_sa_out_raw_tag_d = n4p_sa_out_raw_tag_now;

        if (
            n4d_mse4_idx_hs_mon[n4d_group_id][n4d_local_slice_id] &&
            n4p_mse4_saved < n4p_event_limit
        ) begin
            n4p_mse4_cycle[n4p_mse4_saved] = n4t_sg_cycle;
            n4p_mse4_saved++;
        end
        if (n4t_no_progress_emissions >= 1) begin
            n4p_emit_snapshot("first_qualified_no_progress_window");
        end
    end
end

final begin
    if (n4p_fd != 0) begin
        $fclose(n4p_fd);
    end
end
