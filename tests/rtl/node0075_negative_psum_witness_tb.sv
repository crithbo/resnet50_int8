`timescale 1ns/1ps

module node0075_negative_psum_witness_tb;
  reg         clk = 1'b0;
  reg         rst_n = 1'b0;
  reg         slice_rst = 1'b0;
  reg  [31:0] data_a = 32'b0;
  reg  [31:0] data_b = 32'b0;
  reg  [31:0] data_c = 32'b0;
  reg         bp0 = 1'b0;
  wire [31:0] result;

  always #5 clk = ~clk;

  SA_ALU dut (
    .FMA_Result    (result),
    .FMA_DataA     (data_a),
    .FMA_DataB     (data_b),
    .FMA_DataC     (data_c),
    .FMA_Config    (2'b10),
    .FMA_Precision (1'b0),
    .FMA_Mode      (1'b0),
    .FMA_Bp0       (bp0),
    .FMA_Bp1       (1'b0),
    .rst_n         (rst_n),
    .slice_rst     (slice_rst),
    .clk           (clk)
  );

  initial begin
    repeat (2) @(posedge clk);
    rst_n = 1'b1;

    // Frozen node0075 occurrence:
    // A/u8=[28,13,1,0], B/s8=[1,-2,17,-2], dot4=19, psum=-19.
    @(negedge clk);
    data_a = 32'h01fe11fe;
    data_b = 32'h1c0d0100;
    data_c = 32'hffffffed;
    bp0 = 1'b1;
    @(posedge clk);
    #1;
    bp0 = 1'b0;

    $display(
      "NODE0075_WITNESS PSUM=-19 DOT4=19 RESULT=%08x EXPECTED_MATH=00000000",
      result
    );
    if (result !== 32'h80000000) begin
      $display("TB_FAIL unexpected-current-rtl-result");
      $fatal(1);
    end
    $display("TB_PASS CURRENT_RTL_NEGATIVE_PSUM_SPLIT_REPRODUCED");
    $finish;
  end
endmodule
