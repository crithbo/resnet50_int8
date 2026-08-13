`timescale 1ns/1ps

// Evidence-only monitor for the exact serialized-Conv ACK target.  This bind
// reads DUT state and creates no DUT driver.  It is deliberately separate from
// the frozen v87b phase observer.
module codex_probe_ack_portable_query(
  input wire       clk,
  input wire       rst_n,
  input wire       slice_rst,
  input wire       buf_ag_idx_queue_wr_en,
  input wire       buf_ag_idx_queue_full,
  input wire       buf_all_idx_matched,
  input wire [1:0] buf_idx_same_bit_masked,
  input wire [1:0] buf_idx_gotten_bit,
  input wire [1:0] buf_idx_bp_pre_mask,
  input wire [1:0] mse_buf_queue_bp_pre
);
  integer codex_enabled;
  integer codex_sequence;
  integer codex_time_tick;
  reg codex_previous_valid;
  reg       codex_prev_clk;
  reg       codex_prev_rst_n;
  reg       codex_prev_slice_rst;
  reg       codex_prev_wr_en;
  reg       codex_prev_full;
  reg       codex_prev_all_matched;
  reg [1:0] codex_prev_same_masked;
  reg [1:0] codex_prev_gotten;
  reg [1:0] codex_prev_bp_mask;
  reg [1:0] codex_prev_public_ack;
  reg [1:0] codex_prev_inline_rhs;
  reg [1:0] codex_prev_public_xor;
  reg [1:0] codex_prev_positive_control;
  reg [1:0] codex_prev_negative_control;

  wire [1:0] codex_inline_rhs = {2{!buf_ag_idx_queue_full}} & buf_idx_bp_pre_mask;
  wire [1:0] codex_public_xor = mse_buf_queue_bp_pre ^ codex_inline_rhs;
  wire [1:0] codex_positive_control =
      codex_inline_rhs ^ ({2{!buf_ag_idx_queue_full}} & buf_idx_bp_pre_mask);
  // Deliberately flip bit 1.  The registered parser must preserve this 2'b10
  // negative control and distinguish it from the 2'b00 positive control.
  wire [1:0] codex_negative_control =
      codex_inline_rhs ^ (({2{!buf_ag_idx_queue_full}} & buf_idx_bp_pre_mask) ^ 2'b10);

  task automatic codex_emit_1(input string candidate_id, input logic value);
    begin
      $display("CODEX_PORTABLE_QUERY_V1 kind=EVENT sequence=%0d time_tick=%0d candidate=%0s width=1 value=%b",
        codex_sequence, codex_time_tick, candidate_id, value);
      codex_sequence = codex_sequence + 1;
    end
  endtask

  task automatic codex_emit_2(input string candidate_id, input logic [1:0] value);
    begin
      $display("CODEX_PORTABLE_QUERY_V1 kind=EVENT sequence=%0d time_tick=%0d candidate=%0s width=2 value=%b",
        codex_sequence, codex_time_tick, candidate_id, value);
      codex_sequence = codex_sequence + 1;
    end
  endtask

  task automatic codex_capture;
    begin
      codex_time_tick = $rtoi($realtime * 1000.0);
      if (!codex_previous_valid || clk !== codex_prev_clk)
        codex_emit_1("target_clk", clk);
      if (!codex_previous_valid || rst_n !== codex_prev_rst_n)
        codex_emit_1("target_rst_n", rst_n);
      if (!codex_previous_valid || slice_rst !== codex_prev_slice_rst)
        codex_emit_1("target_slice_rst", slice_rst);
      if (!codex_previous_valid || buf_ag_idx_queue_wr_en !== codex_prev_wr_en)
        codex_emit_1("queue_wr_en", buf_ag_idx_queue_wr_en);
      if (!codex_previous_valid || buf_ag_idx_queue_full !== codex_prev_full)
        codex_emit_1("queue_full", buf_ag_idx_queue_full);
      if (!codex_previous_valid || buf_all_idx_matched !== codex_prev_all_matched)
        codex_emit_1("all_idx_matched", buf_all_idx_matched);
      if (!codex_previous_valid || buf_idx_same_bit_masked !== codex_prev_same_masked)
        codex_emit_2("same_bit_masked", buf_idx_same_bit_masked);
      if (!codex_previous_valid || buf_idx_gotten_bit !== codex_prev_gotten)
        codex_emit_2("gotten_bit", buf_idx_gotten_bit);
      if (!codex_previous_valid || buf_idx_bp_pre_mask !== codex_prev_bp_mask)
        codex_emit_2("bp_pre_mask", buf_idx_bp_pre_mask);
      if (!codex_previous_valid || mse_buf_queue_bp_pre !== codex_prev_public_ack)
        codex_emit_2("public_ack", mse_buf_queue_bp_pre);
      if (!codex_previous_valid || codex_inline_rhs !== codex_prev_inline_rhs)
        codex_emit_2("inline_rhs", codex_inline_rhs);
      if (!codex_previous_valid || codex_public_xor !== codex_prev_public_xor)
        codex_emit_2("public_xor_inline_rhs", codex_public_xor);
      if (!codex_previous_valid || codex_positive_control !== codex_prev_positive_control)
        codex_emit_2("positive_ack_control", codex_positive_control);
      if (!codex_previous_valid || codex_negative_control !== codex_prev_negative_control)
        codex_emit_2("deliberate_negative_ack_control", codex_negative_control);

      codex_prev_clk = clk;
      codex_prev_rst_n = rst_n;
      codex_prev_slice_rst = slice_rst;
      codex_prev_wr_en = buf_ag_idx_queue_wr_en;
      codex_prev_full = buf_ag_idx_queue_full;
      codex_prev_all_matched = buf_all_idx_matched;
      codex_prev_same_masked = buf_idx_same_bit_masked;
      codex_prev_gotten = buf_idx_gotten_bit;
      codex_prev_bp_mask = buf_idx_bp_pre_mask;
      codex_prev_public_ack = mse_buf_queue_bp_pre;
      codex_prev_inline_rhs = codex_inline_rhs;
      codex_prev_public_xor = codex_public_xor;
      codex_prev_positive_control = codex_positive_control;
      codex_prev_negative_control = codex_negative_control;
      codex_previous_valid = 1'b1;
    end
  endtask

  initial begin
    codex_enabled = $test$plusargs("CODEX_PORTABLE_ACK_QUERY");
    codex_sequence = 0;
    codex_previous_valid = 1'b0;
    if (codex_enabled) begin
      #0;
      codex_capture();
    end
  end

  always @(clk or rst_n or slice_rst or buf_ag_idx_queue_wr_en or
           buf_ag_idx_queue_full or buf_all_idx_matched or
           buf_idx_same_bit_masked or buf_idx_gotten_bit or
           buf_idx_bp_pre_mask or mse_buf_queue_bp_pre or
           codex_inline_rhs or codex_public_xor or
           codex_positive_control or codex_negative_control) begin
    if (codex_enabled)
      codex_capture();
  end

  final if (codex_enabled)
    $display("CODEX_PORTABLE_QUERY_V1 kind=SUMMARY event_count=%0d time_tick=%0d",
      codex_sequence, codex_time_tick);
endmodule

bind tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue codex_probe_ack_portable_query codex_probe_ack_portable_inst (
  .clk(clk),
  .rst_n(rst_n),
  .slice_rst(slice_rst),
  .buf_ag_idx_queue_wr_en(buf_ag_idx_queue_wr_en),
  .buf_ag_idx_queue_full(buf_ag_idx_queue_full),
  .buf_all_idx_matched(buf_all_idx_matched),
  .buf_idx_same_bit_masked(buf_idx_same_bit_masked),
  .buf_idx_gotten_bit(buf_idx_gotten_bit),
  .buf_idx_bp_pre_mask(buf_idx_bp_pre_mask),
  .mse_buf_queue_bp_pre(mse_buf_queue_bp_pre)
);
