`timescale 1ns/1ps
`include "NDP_Parameters.svh"

module node0075_df23e4d_ga_signed_ingress_tb;
  reg clk = 1'b0;
  reg rst_n = 1'b0;
  reg slice_rst = 1'b0;
  reg [`GA_INPORT_TAG-1:0] in_tag = '0;
  reg [`GA_INPORT_DATA-1:0] in_data = '0;
  wire bp_pre;
  wire [`GA_INPORT_TAG-1:0] out_tag;
  wire [`GA_INPORT_DATA-1:0] out_data;
  integer timeout;

  always #5 clk = ~clk;

  GA_Inport dut (
    .clk(clk),
    .rst_n(rst_n),
    .slice_rst(slice_rst),
    .ga_inport_fp16tofp32(1'b0),
    .ga_inport_bf16tofp32(1'b0),
    .ga_inport_int32tofp32(1'b1),
    .ga_inport_uint8tofp32(1'b0),
    .ga_inport_uint8toint32(1'b0),
    .ga_inport_bp_pre(bp_pre),
    .ga_inport_in_tag(in_tag),
    .ga_inport_in_data(in_data),
    .ga_inport_bp_post(1'b1),
    .ga_inport_out_tag(out_tag),
    .ga_inport_out_data(out_data)
  );

  task automatic run_case(
    input [8*32-1:0] label,
    input [31:0] int32_bits,
    input [31:0] expected_fp32_bits
  );
    begin
      @(negedge clk);
      in_data = int32_bits;
      in_tag = {1'b1, 1'b1, 1'b0, {`PORT_LAST_INDEX{1'b0}}};
      @(negedge clk);
      in_tag = '0;
      timeout = 0;
      while (!out_tag[`GA_INPORT_TAG-1] && timeout < 8) begin
        @(posedge clk);
        #1;
        timeout = timeout + 1;
      end
      $display(
        "NODE0075_GA_SIGNED label=%0s input=%08x observed=%08x expected=%08x match=%0d",
        label,
        int32_bits,
        out_data,
        expected_fp32_bits,
        out_data === expected_fp32_bits
      );
      @(posedge clk);
    end
  endtask

  initial begin
    repeat (2) @(posedge clk);
    rst_n = 1'b1;
    run_case("zero", 32'h00000000, 32'h00000000);
    run_case("plus_one", 32'h00000001, 32'h3f800000);
    run_case("minus_one", 32'hffffffff, 32'hbf800000);
    run_case("minus_two", 32'hfffffffe, 32'hc0000000);
    run_case("node0075_min", 32'hffff5096, 32'hc72f6a00);
    $finish;
  end
endmodule
