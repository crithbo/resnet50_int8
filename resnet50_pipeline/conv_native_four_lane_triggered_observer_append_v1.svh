// Native Conv c0 always-on triggered causal observer append.
//
// This append is concatenated after the production-compiled p9b observer.
// It introduces no new DUT hierarchy references: every sampled signal is an
// existing n4d_* monitor declared above.  It never drives DUT/TB state, never
// changes timeout, and performs text I/O only at time zero or a bounded
// trigger/stage/final transition.

bit n4t_enabled;
bit n4t_exec_seen;
bit n4t_exec_d;
bit n4t_finish_d;
bit n4t_first_queue_full_emitted;
bit n4t_first_branch_divergence_emitted;
bit n4t_terminal_gap_emitted;
integer n4t_fd;
integer n4t_plusarg_status;
integer n4t_no_progress_cycles;
integer n4t_no_progress_emissions;
string n4t_output_path;
longint unsigned n4t_sg_cycle;
longint unsigned n4t_last_key_cycle;
longint unsigned n4t_last_key_total;
longint unsigned n4t_req_count [0:`MEMORY_STREAM_ENGINE_NUM-1];
longint unsigned n4t_arm_req_count [0:`BUFFER_NUM-1];
longint unsigned n4t_arm_resp_count [0:`BUFFER_NUM-1];
longint unsigned n4t_arm_finish_count [0:`BUFFER_NUM-1];
longint unsigned n4t_sa_input_count;
longint unsigned n4t_sa_output_count;
longint unsigned n4t_mse4_index_count;
longint unsigned n4t_buffer5_write_active_cycles;
longint unsigned n4t_buffer5_write_rises;
longint unsigned n4t_first_sa_input_time;
longint unsigned n4t_last_sa_input_time;
longint unsigned n4t_first_sa_output_time;
longint unsigned n4t_last_sa_output_time;
longint unsigned n4t_first_mse4_time;
longint unsigned n4t_last_mse4_time;
longint unsigned n4t_ordered_digest;
logic [`BUFFER_BANK_NUM-1:0] n4t_buffer5_write_mask_d;
logic [`BUFFER_BANK_NUM-1:0] n4t_last_buffer5_write_mask;
logic [`ARRAY_PORT_TAG-1:0] n4t_last_sa_input_tag;
logic [`ARRAY_PORT_TAG-1:0] n4t_last_sa_output_tag;
logic [(1<<`PORT_LAST_INDEX)-1:0] n4t_sa_input_last_index_seen;
logic [(1<<`PORT_LAST_INDEX)-1:0] n4t_sa_output_last_index_seen;

function automatic longint unsigned n4t_key_total();
    longint unsigned value;
    value =
        n4t_sa_input_count +
        n4t_sa_output_count +
        n4t_mse4_index_count +
        n4t_buffer5_write_rises;
    for (int mse = 0; mse < `MEMORY_STREAM_ENGINE_NUM; mse++) begin
        value += n4t_req_count[mse];
    end
    for (int buf_id = 0; buf_id < `BUFFER_NUM; buf_id++) begin
        value +=
            n4t_arm_req_count[buf_id] +
            n4t_arm_resp_count[buf_id] +
            n4t_arm_finish_count[buf_id];
    end
    return value;
endfunction

task automatic n4t_mix_digest(
    input integer event_code,
    input longint unsigned event_value
);
    n4t_ordered_digest =
        ((n4t_ordered_digest << 7) |
         (n4t_ordered_digest >> 57)) ^
        event_value ^
        (64'h9e3779b97f4a7c15 * event_code);
endtask

task automatic n4t_emit(
    input string trigger_id,
    input string classification,
    input string reason
);
    if (n4t_fd != 0) begin
        $fdisplay(
            n4t_fd,
            "N4T_TRIGGER_V1 trigger=%s classification=%s reason=%s stage=c0 slice=%0d sg_cycle=%0d key_total=%0d req=%0d,%0d,%0d,%0d,%0d armreq=%0d,%0d,%0d,%0d,%0d,%0d armresp=%0d,%0d,%0d,%0d,%0d,%0d armfin=%0d,%0d,%0d,%0d,%0d,%0d sain=%0d saout=%0d mse4=%0d b5_active=%0d b5_rise=%0d b5_mask=0x%0h sa_in_tag=0x%0h sa_out_tag=0x%0h sa_in_last_seen=0x%0h sa_out_last_seen=0x%0h first_sain=%0d last_sain=%0d first_saout=%0d last_saout=%0d first_mse4=%0d last_mse4=%0d digest=0x%0h",
            trigger_id,
            classification,
            reason,
            n4d_slice_id,
            n4t_sg_cycle,
            n4t_key_total(),
            n4t_req_count[0], n4t_req_count[1],
            n4t_req_count[2], n4t_req_count[3],
            n4t_req_count[4],
            n4t_arm_req_count[0], n4t_arm_req_count[1],
            n4t_arm_req_count[2], n4t_arm_req_count[3],
            n4t_arm_req_count[4], n4t_arm_req_count[5],
            n4t_arm_resp_count[0], n4t_arm_resp_count[1],
            n4t_arm_resp_count[2], n4t_arm_resp_count[3],
            n4t_arm_resp_count[4], n4t_arm_resp_count[5],
            n4t_arm_finish_count[0], n4t_arm_finish_count[1],
            n4t_arm_finish_count[2], n4t_arm_finish_count[3],
            n4t_arm_finish_count[4], n4t_arm_finish_count[5],
            n4t_sa_input_count,
            n4t_sa_output_count,
            n4t_mse4_index_count,
            n4t_buffer5_write_active_cycles,
            n4t_buffer5_write_rises,
            n4t_last_buffer5_write_mask,
            n4t_last_sa_input_tag,
            n4t_last_sa_output_tag,
            n4t_sa_input_last_index_seen,
            n4t_sa_output_last_index_seen,
            n4t_first_sa_input_time,
            n4t_last_sa_input_time,
            n4t_first_sa_output_time,
            n4t_last_sa_output_time,
            n4t_first_mse4_time,
            n4t_last_mse4_time,
            n4t_ordered_digest
        );
        $fflush(n4t_fd);
    end
endtask

task automatic n4t_reset();
    n4t_exec_seen = 0;
    n4t_exec_d = 0;
    n4t_finish_d = 0;
    n4t_first_queue_full_emitted = 0;
    n4t_first_branch_divergence_emitted = 0;
    n4t_terminal_gap_emitted = 0;
    n4t_no_progress_emissions = 0;
    n4t_sg_cycle = 0;
    n4t_last_key_cycle = 0;
    n4t_last_key_total = 0;
    n4t_sa_input_count = 0;
    n4t_sa_output_count = 0;
    n4t_mse4_index_count = 0;
    n4t_buffer5_write_active_cycles = 0;
    n4t_buffer5_write_rises = 0;
    n4t_first_sa_input_time = 0;
    n4t_last_sa_input_time = 0;
    n4t_first_sa_output_time = 0;
    n4t_last_sa_output_time = 0;
    n4t_first_mse4_time = 0;
    n4t_last_mse4_time = 0;
    n4t_ordered_digest = 64'hcbf29ce484222325;
    n4t_buffer5_write_mask_d = 0;
    n4t_last_buffer5_write_mask = 0;
    n4t_last_sa_input_tag = 0;
    n4t_last_sa_output_tag = 0;
    n4t_sa_input_last_index_seen = 0;
    n4t_sa_output_last_index_seen = 0;
    for (int mse = 0; mse < `MEMORY_STREAM_ENGINE_NUM; mse++) begin
        n4t_req_count[mse] = 0;
    end
    for (int buf_id = 0; buf_id < `BUFFER_NUM; buf_id++) begin
        n4t_arm_req_count[buf_id] = 0;
        n4t_arm_resp_count[buf_id] = 0;
        n4t_arm_finish_count[buf_id] = 0;
    end
endtask

initial begin
    n4t_enabled = $test$plusargs("N4T_CAUSAL_PROFILE");
    n4t_output_path = "triggered_observer.log";
    n4t_no_progress_cycles = 1048576;
    n4t_plusarg_status =
        $value$plusargs("N4T_FILE=%s", n4t_output_path);
    n4t_plusarg_status =
        $value$plusargs(
            "N4T_NO_PROGRESS_CYCLES=%d",
            n4t_no_progress_cycles
        );
    n4t_fd = 0;
    n4t_reset();
    if (n4t_enabled) begin
        if (n4t_no_progress_cycles <= 0) begin
            $error("N4T observer plusarg contract is invalid");
            n4t_enabled = 0;
        end
        else begin
            n4t_fd = $fopen(n4t_output_path, "w");
            if (n4t_fd == 0) begin
                $error("N4T observer output cannot be created");
                n4t_enabled = 0;
            end
            else begin
                $fdisplay(
                    n4t_fd,
                    "N4T_FEATURE_ENABLE_V1 feature=NATIVE4_TRIGGERED_CAUSAL enabled=1 stage=c0 slice=%0d no_progress_cycles=%0d drives_dut=0 changes_timeout=0 per_event_text_io=0 full_wave_dump=0",
                    n4d_slice_id,
                    n4t_no_progress_cycles
                );
                $fflush(n4t_fd);
                $display(
                    "[RETURN_OBSERVER] enabled N4T_FEATURE_ENABLE_V1 feature=NATIVE4_TRIGGERED_CAUSAL enabled=1 stage=c0 slice=%0d",
                    n4d_slice_id
                );
            end
        end
    end
end

always @(posedge u_NDP_Top_new.clk_sg or
         negedge u_NDP_Top_new.rst_n_sg) begin
    if (!u_NDP_Top_new.rst_n_sg) begin
        n4t_reset();
    end
    else if (n4t_enabled) begin
        n4t_sg_cycle++;

        if (n4d_active && !n4t_exec_d) begin
            n4t_exec_seen = 1;
            n4t_last_key_cycle = n4t_sg_cycle;
            n4t_last_key_total = n4t_key_total();
            n4t_emit(
                "STAGE_TRANSITION",
                "EVIDENCE_INCOMPLETE",
                "qualified_c0_exec_start"
            );
        end
        if (!n4d_active && n4t_exec_d && !n4t_finish_d) begin
            n4t_finish_d = 1;
            n4t_emit(
                "STAGE_TRANSITION",
                "NATURAL_SUCCESS",
                "qualified_c0_slice_finish"
            );
        end
        n4t_exec_d = n4d_active;

        if (n4d_active) begin
            for (
                int mse = 0;
                mse < `MEMORY_STREAM_ENGINE_NUM;
                mse++
            ) begin
                for (
                    int req = 0;
                    req < `MSE_REQ_CHL_NUM;
                    req++
                ) begin
                    if (
                        local_req_hs[n4d_group_id]
                            [n4d_local_slice_id][mse][req]
                    ) begin
                        n4t_req_count[mse]++;
                        n4t_mix_digest(1 + mse, n4t_sg_cycle);
                    end
                end
            end

            for (
                int buf_id = 0;
                buf_id < `BUFFER_NUM;
                buf_id++
            ) begin
                if (
                    n4d_arm_req_hs_mon[n4d_group_id]
                        [n4d_local_slice_id][buf_id]
                ) begin
                    n4t_arm_req_count[buf_id]++;
                    n4t_mix_digest(16 + buf_id, n4t_sg_cycle);
                end
                if (
                    n4d_arm_resp_hs_mon[n4d_group_id]
                        [n4d_local_slice_id][buf_id]
                ) begin
                    n4t_arm_resp_count[buf_id]++;
                    n4t_mix_digest(24 + buf_id, n4t_sg_cycle);
                end
                if (
                    n4d_arm_finish_mon[n4d_group_id]
                        [n4d_local_slice_id][buf_id] &&
                    !n4d_arm_finish_d[buf_id]
                ) begin
                    n4t_arm_finish_count[buf_id]++;
                    n4t_mix_digest(32 + buf_id, n4t_sg_cycle);
                end
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
                            [`ARRAY_PORT_TAG-1 -:
                             `ARRAY_PORT_GROUP_SIZE]) &&
                        n4d_sa_input_bp_mon[n4d_group_id]
                            [n4d_local_slice_id][sa_in][sa_buf]
                    ) begin
                        n4t_sa_input_count++;
                        n4t_last_sa_input_tag =
                            n4d_buf2sa_tag_mon[n4d_group_id]
                                [n4d_local_slice_id][sa_in][sa_buf];
                        if (n4t_first_sa_input_time == 0) begin
                            n4t_first_sa_input_time = n4t_sg_cycle;
                        end
                        n4t_last_sa_input_time = n4t_sg_cycle;
                        if (
                            n4t_last_sa_input_tag[
                                `PORT_LAST_INDEX + `PORT_SAME_BIT
                            ]
                        ) begin
                            n4t_sa_input_last_index_seen[
                                n4t_last_sa_input_tag[
                                    0 +: `PORT_LAST_INDEX
                                ]
                            ] = 1'b1;
                        end
                        n4t_mix_digest(
                            48,
                            {50'b0, n4t_last_sa_input_tag}
                        );
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
                            [`ARRAY_PORT_TAG-1 -:
                             `ARRAY_PORT_GROUP_SIZE]) &&
                        n4d_buf_accept_sa_mon[n4d_group_id]
                            [n4d_local_slice_id][sa_out][sa_buf]
                    ) begin
                        n4t_sa_output_count++;
                        n4t_last_sa_output_tag =
                            n4d_sa2buf_tag_mon[n4d_group_id]
                                [n4d_local_slice_id][sa_out][sa_buf];
                        if (n4t_first_sa_output_time == 0) begin
                            n4t_first_sa_output_time = n4t_sg_cycle;
                        end
                        n4t_last_sa_output_time = n4t_sg_cycle;
                        if (
                            n4t_last_sa_output_tag[
                                `PORT_LAST_INDEX + `PORT_SAME_BIT
                            ]
                        ) begin
                            n4t_sa_output_last_index_seen[
                                n4t_last_sa_output_tag[
                                    0 +: `PORT_LAST_INDEX
                                ]
                            ] = 1'b1;
                        end
                        n4t_mix_digest(
                            49,
                            {50'b0, n4t_last_sa_output_tag}
                        );
                    end
                end
            end

            if (
                n4d_mse4_idx_hs_mon[n4d_group_id]
                    [n4d_local_slice_id]
            ) begin
                n4t_mse4_index_count++;
                if (n4t_first_mse4_time == 0) begin
                    n4t_first_mse4_time = n4t_sg_cycle;
                end
                n4t_last_mse4_time = n4t_sg_cycle;
                n4t_mix_digest(50, n4t_sg_cycle);
            end

            n4t_last_buffer5_write_mask =
                n4d_buf45_wr_en_mon[n4d_group_id]
                    [n4d_local_slice_id][1];
            if (|n4t_last_buffer5_write_mask) begin
                n4t_buffer5_write_active_cycles++;
                if (!(|n4t_buffer5_write_mask_d)) begin
                    n4t_buffer5_write_rises++;
                    n4t_mix_digest(
                        51,
                        {56'b0, n4t_last_buffer5_write_mask}
                    );
                end
            end
            n4t_buffer5_write_mask_d =
                n4t_last_buffer5_write_mask;

            if (
                !n4t_first_queue_full_emitted &&
                (|n4d_rd_queue_full_mon[n4d_group_id]
                    [n4d_local_slice_id])
            ) begin
                n4t_first_queue_full_emitted = 1;
                n4t_emit(
                    "FIRST_QUEUE_FULL",
                    "DYNAMIC_FLOW_CONTROL_STALL",
                    "first_rd_queue_full"
                );
            end

            if (
                !n4t_first_branch_divergence_emitted &&
                n4t_sa_input_count >= 8 &&
                (n4t_sa_input_count - n4t_sa_output_count) >= 4
            ) begin
                n4t_first_branch_divergence_emitted = 1;
                n4t_emit(
                    "FIRST_BRANCH_DIVERGENCE",
                    "DYNAMIC_FLOW_CONTROL_STALL",
                    "sa_input_minus_output_ge4"
                );
            end

            if (
                !n4t_terminal_gap_emitted &&
                n4t_sa_input_last_index_seen != 0 &&
                n4t_arm_finish_count[0] == 0 &&
                n4t_arm_finish_count[1] == 0 &&
                n4t_arm_finish_count[2] == 0 &&
                n4t_arm_finish_count[3] == 0 &&
                n4t_arm_finish_count[4] == 0 &&
                n4t_arm_finish_count[5] == 0 &&
                (n4t_sg_cycle - n4t_last_sa_input_time) >=
                    n4t_no_progress_cycles
            ) begin
                n4t_terminal_gap_emitted = 1;
                n4t_emit(
                    "TERMINAL_GAP",
                    "TERMINAL_PROPAGATION_FAILURE",
                    "input_last_seen_without_arm_finish"
                );
            end

            if (
                (n4t_sg_cycle - n4t_last_key_cycle) >=
                    n4t_no_progress_cycles
            ) begin
                if (
                    n4t_key_total() == n4t_last_key_total &&
                    n4t_no_progress_emissions < 4
                ) begin
                    n4t_no_progress_emissions++;
                    n4t_emit(
                        "NO_PROGRESS_WINDOW",
                        "DYNAMIC_FLOW_CONTROL_STALL",
                        "qualified_key_total_unchanged"
                    );
                end
                n4t_last_key_total = n4t_key_total();
                n4t_last_key_cycle = n4t_sg_cycle;
            end
        end
    end
end

final begin
    if (n4t_fd != 0) begin
        $fdisplay(
            n4t_fd,
            "N4T_TRIGGER_V1 trigger=EXIT_OR_SIGNAL classification=%0s reason=%0s stage=c0 slice=%0d sg_cycle=%0d key_total=%0d req=%0d,%0d,%0d,%0d,%0d armreq=%0d,%0d,%0d,%0d,%0d,%0d armresp=%0d,%0d,%0d,%0d,%0d,%0d armfin=%0d,%0d,%0d,%0d,%0d,%0d sain=%0d saout=%0d mse4=%0d b5_active=%0d b5_rise=%0d digest=0x%0h",
            n4t_finish_d ? "NATURAL_SUCCESS" :
                           "EVIDENCE_INCOMPLETE",
            n4t_finish_d ? "natural_final" :
                           "simulator_final_without_slice_finish",
            n4d_slice_id,
            n4t_sg_cycle,
            n4t_key_total(),
            n4t_req_count[0], n4t_req_count[1],
            n4t_req_count[2], n4t_req_count[3],
            n4t_req_count[4],
            n4t_arm_req_count[0], n4t_arm_req_count[1],
            n4t_arm_req_count[2], n4t_arm_req_count[3],
            n4t_arm_req_count[4], n4t_arm_req_count[5],
            n4t_arm_resp_count[0], n4t_arm_resp_count[1],
            n4t_arm_resp_count[2], n4t_arm_resp_count[3],
            n4t_arm_resp_count[4], n4t_arm_resp_count[5],
            n4t_arm_finish_count[0], n4t_arm_finish_count[1],
            n4t_arm_finish_count[2], n4t_arm_finish_count[3],
            n4t_arm_finish_count[4], n4t_arm_finish_count[5],
            n4t_sa_input_count,
            n4t_sa_output_count,
            n4t_mse4_index_count,
            n4t_buffer5_write_active_cycles,
            n4t_buffer5_write_rises,
            n4t_ordered_digest
        );
        $fclose(n4t_fd);
    end
end
