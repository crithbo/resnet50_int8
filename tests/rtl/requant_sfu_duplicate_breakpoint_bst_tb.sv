`timescale 1ns/1ps
`include "NDP_Parameters.svh"

module requant_sfu_duplicate_breakpoint_bst_tb;
  reg clk = 0;
  reg rst_n = 0;
  reg slice_rst = 0;
  reg search_en = 0;
  reg [31:0] search_data = 0;
  reg [31:0] breakpoint_0;
  reg [31:0] breakpoint_1;
  reg [31:0] breakpoint_2;
  reg [31:0] breakpoint_3;
  reg [31:0] breakpoint_4;
  reg [31:0] breakpoint_5;
  reg [31:0] breakpoint_6;
  wire [0:0] addr_0;
  wire [0:0] addr_1;
  wire [1:0] addr_2;
  wire [2:0] addr_3;
  wire [3:0] addr_4;
  wire [4:0] addr_5;
  wire [0:0] addr_6;
  wire [31:0] search_data_o;
  wire [6:0] search_addr_o;
  integer checks = 0;

  always #5 clk = ~clk;

  function automatic [31:0] threshold_at_rank(input integer rank);
    begin
      // upper_bound([-256] * 32 + [+256] * 33)
      threshold_at_rank = (rank < 32) ? 32'hc3800000 : 32'h43800000;
    end
  endfunction

  always @* begin
    breakpoint_0 = threshold_at_rank(32);
    breakpoint_1 = threshold_at_rank(16 + 32 * addr_1);
    breakpoint_2 = threshold_at_rank(8  + 16 * addr_2);
    breakpoint_3 = threshold_at_rank(4  + 8  * addr_3);
    breakpoint_4 = threshold_at_rank(2  + 4  * addr_4);
    breakpoint_5 = threshold_at_rank(1  + 2  * addr_5);
    breakpoint_6 = threshold_at_rank(addr_6 ? 64 : 0);
  end

  Binary_Search_Tree dut (
    .clk(clk),
    .rst_n(rst_n),
    .slice_rst(slice_rst),
    .bst_search_en_i(search_en),
    .bst_search_data_i(search_data),
    .bst_pipeline0_enable(1'b1),
    .bst_pipeline1_enable(1'b1),
    .bst_pipeline2_enable(1'b1),
    .bst_pipeline3_enable(1'b1),
    .bst_pipeline4_enable(1'b1),
    .bst_pipeline5_enable(1'b1),
    .bst_breakpoint_data_i_0(breakpoint_0),
    .bst_breakpoint_data_i_1(breakpoint_1),
    .bst_breakpoint_data_i_2(breakpoint_2),
    .bst_breakpoint_data_i_3(breakpoint_3),
    .bst_breakpoint_data_i_4(breakpoint_4),
    .bst_breakpoint_data_i_5(breakpoint_5),
    .bst_breakpoint_data_i_6(breakpoint_6),
    .bst_search_addr_0(addr_0),
    .bst_search_addr_1(addr_1),
    .bst_search_addr_2(addr_2),
    .bst_search_addr_3(addr_3),
    .bst_search_addr_4(addr_4),
    .bst_search_addr_5(addr_5),
    .bst_search_addr_6(addr_6),
    .bst_search_data_o(search_data_o),
    .bst_search_addr_o(search_addr_o)
  );

  task automatic check_search(input [31:0] bits, input [6:0] expected_addr);
    begin
      @(negedge clk);
      search_data = bits;
      search_en = 1;
      @(negedge clk);
      search_en = 0;
      repeat (5) @(posedge clk);
      #1;
      if (search_addr_o !== expected_addr || search_data_o !== bits) begin
        $display("FAIL bits=%08x got_addr=%0d expected_addr=%0d got_data=%08x",
                 bits, search_addr_o, expected_addr, search_data_o);
        $fatal(1);
      end
      checks = checks + 1;
    end
  endtask

  initial begin
    repeat (2) @(posedge clk);
    rst_n = 1;
    check_search(32'hff7fffff, 7'd0);   // most-negative finite
    check_search(32'hc3808000, 7'd0);   // -257
    check_search(32'hc3800000, 7'd32);  // -256 equality goes right
    check_search(32'hc37f0000, 7'd32);  // -255
    check_search(32'h80000000, 7'd32);  // -0
    check_search(32'h00000000, 7'd32);  // +0
    check_search(32'h437f0000, 7'd32);  // +255
    check_search(32'h43800000, 7'd65);  // +256 equality goes right
    check_search(32'h43808000, 7'd65);  // +257
    check_search(32'h7f7fffff, 7'd65);  // largest finite
    $display("PASS duplicate-breakpoint BST checks=%0d", checks);
    $finish;
  end
endmodule
