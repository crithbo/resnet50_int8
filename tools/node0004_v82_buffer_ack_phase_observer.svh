module codex_probe_buf_ack_phase_target(
  input wire clk,
  input wire rst_n,
  input wire mse_enable,
  input wire [1:0] mse_buf_idx_mode,
  input wire buf_ag_idx_queue_wr_en,
  input wire buf_ag_idx_queue_full,
  input wire buf_all_idx_matched,
  input wire [1:0] buf_idx_valid_bit_masked,
  input wire [1:0] buf_idx_same_bit_masked,
  input wire [1:0] buf_idx_gotten_bit,
  input wire [1:0] buf_idx_bp_pre_keep_mask,
  input wire [1:0] buf_idx_bp_pre_mask,
  input wire [1:0] mse_buf_queue_bp_pre,
  input wire [`SE_BUF_ROW_INPORT_IDX_WIDTH-1:0] mse_buf_queue_row_idx,
  input wire [`SE_BUF_COL_INPORT_IDX_WIDTH-1:0] mse_buf_queue_col_idx,
  input wire [`SE_BUF_INPORT_TAG_WIDTH-1:0] mse_buf_queue_row_tag,
  input wire [`SE_BUF_INPORT_TAG_WIDTH-1:0] mse_buf_queue_col_tag
);
  integer codex_enabled, codex_limit, codex_count, codex_seq;
  integer codex_half_pending, codex_next_pending, codex_pending_seq;
  localparam integer CODEX_PAYLOAD_WIDTH = 38;
  localparam string CODEX_TARGET = "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue";
  wire [CODEX_PAYLOAD_WIDTH-1:0] codex_payload = {
    buf_ag_idx_queue_wr_en, buf_ag_idx_queue_full, buf_all_idx_matched,
    buf_idx_valid_bit_masked, buf_idx_same_bit_masked, buf_idx_gotten_bit,
    buf_idx_bp_pre_keep_mask, buf_idx_bp_pre_mask, mse_buf_queue_bp_pre,
    mse_buf_idx_mode, mse_buf_queue_row_idx, mse_buf_queue_col_idx,
    mse_buf_queue_row_tag, mse_buf_queue_col_tag
  };
  wire codex_payload_known = !$isunknown(codex_payload);

  task automatic codex_emit(input [63:0] phase_name, input integer seq_value);
    $display("CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_phase_target instance=%0s time=%0t mask=1 payload=%0h payload_known=%0d payload_width=%0d seq=%0d phase=%0s wr=%b full=%b all=%b valid=%h same=%h gotten=%h keep=%h bpmask=%h bp=%h mode=%h row=%h col=%h rowtag=%h coltag=%h",
      CODEX_TARGET, $time, codex_payload, codex_payload_known, CODEX_PAYLOAD_WIDTH,
      seq_value, phase_name, buf_ag_idx_queue_wr_en, buf_ag_idx_queue_full,
      buf_all_idx_matched, buf_idx_valid_bit_masked, buf_idx_same_bit_masked,
      buf_idx_gotten_bit, buf_idx_bp_pre_keep_mask, buf_idx_bp_pre_mask,
      mse_buf_queue_bp_pre, mse_buf_idx_mode, mse_buf_queue_row_idx,
      mse_buf_queue_col_idx, mse_buf_queue_row_tag, mse_buf_queue_col_tag);
  endtask

  initial begin
    codex_enabled = $test$plusargs("CODEX_CAUSAL_OBSERVER");
    if (!$value$plusargs("RETURN_OBS_BUF_ACK_PHASE_LIMIT=%d", codex_limit)) codex_limit = 128;
    codex_count = 0; codex_seq = 0; codex_half_pending = 0;
    codex_next_pending = 0; codex_pending_seq = 0;
    if (codex_enabled)
      $display("CODEX_PROBE_V1 kind=ENABLED boundary=buf_ack_phase_target instance=%0s feature=RETURN_OBS_BUF_ACK_PHASE limit=%0d payload_width=%0d",
        CODEX_TARGET, codex_limit, CODEX_PAYLOAD_WIDTH);
  end

  always @(posedge clk) begin
    if (!rst_n) begin
      codex_half_pending = 0; codex_next_pending = 0;
    end else if (codex_enabled) begin
      if (codex_next_pending) begin
        codex_emit("NEXT", codex_pending_seq);
        codex_next_pending = 0;
      end
      if (mse_enable && codex_count < codex_limit &&
          (buf_ag_idx_queue_wr_en === 1'b1) &&
          (buf_ag_idx_queue_full === 1'b0) &&
          (buf_idx_bp_pre_mask === 2'b11) &&
          (mse_buf_queue_bp_pre !== 2'b11)) begin
        codex_pending_seq = codex_seq; codex_seq = codex_seq + 1;
        codex_count = codex_count + 1; codex_half_pending = 1;
        codex_next_pending = 1;
        codex_emit("ACTIVE", codex_pending_seq);
        #0 codex_emit("INACTIVE", codex_pending_seq);
        #1 codex_emit("POSTNBA", codex_pending_seq);
      end
    end
  end

  always @(negedge clk) begin
    if (codex_enabled && codex_half_pending) begin
      codex_emit("HALF", codex_pending_seq);
      codex_half_pending = 0;
    end
  end

  final begin
    if (codex_enabled)
      $display("CODEX_PROBE_V1 kind=SUMMARY boundary=buf_ack_phase_target instance=%0s count=%0d state=0 first=0 last=%0t maxgap=0 sticky=0 xor=0 payload_width=%0d",
        CODEX_TARGET, codex_count, $time, CODEX_PAYLOAD_WIDTH);
  end
endmodule

`ifndef CODEX_SOURCE_BOUND_FOCUS
bind tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue codex_probe_buf_ack_phase_target codex_probe_buf_ack_phase_target_inst (
  .clk(clk), .rst_n(rst_n), .mse_enable(mse_enable), .mse_buf_idx_mode(mse_buf_idx_mode),
  .buf_ag_idx_queue_wr_en(buf_ag_idx_queue_wr_en), .buf_ag_idx_queue_full(buf_ag_idx_queue_full),
  .buf_all_idx_matched(buf_all_idx_matched), .buf_idx_valid_bit_masked(buf_idx_valid_bit_masked),
  .buf_idx_same_bit_masked(buf_idx_same_bit_masked), .buf_idx_gotten_bit(buf_idx_gotten_bit),
  .buf_idx_bp_pre_keep_mask(buf_idx_bp_pre_keep_mask), .buf_idx_bp_pre_mask(buf_idx_bp_pre_mask),
  .mse_buf_queue_bp_pre(mse_buf_queue_bp_pre), .mse_buf_queue_row_idx(mse_buf_queue_row_idx),
  .mse_buf_queue_col_idx(mse_buf_queue_col_idx), .mse_buf_queue_row_tag(mse_buf_queue_row_tag),
  .mse_buf_queue_col_tag(mse_buf_queue_col_tag)
);
`endif
