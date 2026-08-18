module codex_tb_bounded_causal_vcd;
  string codex_vcd_path;
  initial begin
    if ($value$plusargs("CODEX_VCD_PATH=%s", codex_vcd_path)) begin
      $dumpfile(codex_vcd_path);
      $dumpvars(0, tb_NDP_Top_new_phy.clk);
      $dumpvars(0, tb_NDP_Top_new_phy.rst_n);
      $dumpvars(0, tb_NDP_Top_new_phy.NDP_Top_phy_INST.slice13.req_valid_ready);
      $dumpvars(0, tb_NDP_Top_new_phy.NDP_Top_phy_INST.slice13.fifo_state);
      $dumpvars(0, tb_NDP_Top_new_phy.NDP_Top_phy_INST.slice13.payload_state);
      $dumpvars(0, tb_NDP_Top_new_phy.NDP_Top_phy_INST.slice13.bank_state);
      $dumpvars(0, tb_NDP_Top_new_phy.NDP_Top_phy_INST.slice13.control_state);
      $dumpvars(0, tb_NDP_Top_new_phy.NDP_Top_phy_INST.slice13.output_wdata);
      $dumpon;
    end
  end
  final begin
    $dumpoff;
    $dumpflush;
  end
endmodule
