`timescale 1ns/1ps
`include "NDP_Parameters.svh"

module requant_ga_int32_full_domain_witness_tb;
  reg clk = 1'b0;
  reg rst_n = 1'b0;
  reg slice_rst = 1'b0;
  reg [`GA_INPORT_TAG-1:0] in_tag = '0;
  reg [`GA_INPORT_DATA-1:0] in_data = '0;
  wire bp_pre;
  wire [`GA_INPORT_TAG-1:0] out_tag;
  wire [`GA_INPORT_DATA-1:0] out_data;
  integer timeout;
  integer errors = 0;
  integer cases = 0;

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

  task automatic check_case(
    input [8*40-1:0] label,
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
      cases = cases + 1;
      if (out_data !== expected_fp32_bits) begin
        errors = errors + 1;
        $display(
          "GA_INT32_WITNESS_FAIL label=%0s input=%08x observed=%08x expected=%08x",
          label, int32_bits, out_data, expected_fp32_bits
        );
      end
      else begin
        $display(
          "GA_INT32_WITNESS_PASS label=%0s input=%08x output=%08x",
          label, int32_bits, out_data
        );
      end
      @(posedge clk);
    end
  endtask

  initial begin
    repeat (2) @(posedge clk);
    rst_n = 1'b1;

    check_case("zero",                 32'h00000000, 32'h00000000);
    check_case("plus_one",             32'h00000001, 32'h3f800000);
    check_case("minus_one",            32'hffffffff, 32'hbf800000);
    check_case("int32_min",            32'h80000000, 32'hcf000000);
    check_case("int32_max",            32'h7fffffff, 32'h4f000000);
    check_case("minus_int32_max",      32'h80000001, 32'hcf000000);
    check_case("positive_tie_even",    32'h01000001, 32'h4b800000);
    check_case("positive_tie_odd",     32'h01000003, 32'h4b800002);
    check_case("negative_tie_even",    32'hfeffffff, 32'hcb800000);
    check_case("negative_tie_odd",     32'hfefffffd, 32'hcb800002);
    check_case("carry_predecessor",    32'h01fffffe, 32'h4bffffff);
    check_case("positive_exp_carry",   32'h01ffffff, 32'h4c000000);
    check_case("negative_predecessor", 32'hfe000002, 32'hcbffffff);
    check_case("negative_exp_carry",   32'hfe000001, 32'hcc000000);
    check_case("node0075_negative",    32'hffff5096, 32'hc72f6a00);

    $display("GA_INT32_WITNESS_SUMMARY cases=%0d errors=%0d", cases, errors);
    if (errors != 0) begin
      $fatal(1, "GA INT32-to-FP32 witness mismatch");
    end
    $finish;
  end
endmodule
