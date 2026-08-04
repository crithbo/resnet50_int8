`timescale 1ns/1ps

module ga_sfu_affine_identity_tb;
  reg         clk = 1'b0;
  reg         rst_n = 1'b0;
  reg         slice_rst = 1'b0;
  reg  [31:0] data_a = 32'b0;
  reg  [31:0] data_b = 32'b0;
  reg  [31:0] data_c = 32'b0;
  wire [31:0] result;

  always #5 clk = ~clk;

  GA_ALU dut (
    .FMA_Result    (result),
    .FMA_Opcode    (3'b110),
    .FMA_DataA     (data_a),
    .FMA_DataB     (data_b),
    .FMA_DataC     (data_c),
    .FMA_Config    (2'b10),
    .FMA_Precision (1'b1),
    .FMA_Mode      (1'b1),
    .FMA_Bp0       (1'b1),
    .FMA_Bp1       (1'b1),
    .rst_n         (rst_n),
    .slice_rst     (slice_rst),
    .clk           (clk)
  );

  task automatic check_affine;
    input [31:0] a;
    input [31:0] b;
    input [31:0] c;
    input [31:0] expected;
    begin
      @(negedge clk);
      data_a = a;
      data_b = b;
      data_c = c;
      repeat (5) @(posedge clk);
      #1;
      if (result !== expected) begin
        $display(
          "FAIL a=%08x b=%08x c=%08x result=%08x expected=%08x",
          a, b, c, result, expected
        );
        $fatal(1);
      end
      $display(
        "PASS a=%08x b=%08x c=%08x result=%08x",
        a, b, c, result
      );
    end
  endtask

  initial begin
    repeat (2) @(posedge clk);
    rst_n = 1'b1;

    // Stage-0 negative-domain guard: finite negative converter outputs are
    // multiplied by +0 and must become exact +0.
    check_affine(32'hcf000000, 32'h00000000, 32'h00000000, 32'h00000000);
    check_affine(32'hce800000, 32'h00000000, 32'h00000000, 32'h00000000);
    check_affine(32'hc1200000, 32'h00000000, 32'h00000000, 32'h00000000);

    // Stage-0 non-negative identity branch: multiply by 1 and add +0.
    check_affine(32'h00000000, 32'h3f800000, 32'h00000000, 32'h00000000);
    check_affine(32'h3f800000, 32'h3f800000, 32'h00000000, 32'h3f800000);
    check_affine(32'h4b800000, 32'h3f800000, 32'h00000000, 32'h4b800000);
    check_affine(32'h4f000000, 32'h3f800000, 32'h00000000, 32'h4f000000);

    $display("GA_SFU_AFFINE_IDENTITY_PASS");
    $finish;
  end
endmodule
