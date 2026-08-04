`timescale 1ns/1ps

module int8_sa_stock_dot4_tb;
  reg         clk = 1'b0;
  reg         rst_n = 1'b0;
  reg         slice_rst = 1'b0;
  reg  [31:0] data_a = 32'b0;
  reg  [31:0] data_b = 32'b0;
  reg  [31:0] data_c = 32'b0;
  reg         bp0 = 1'b0;
  reg         bp1 = 1'b0;
  wire [31:0] result;
  integer     failures = 0;

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
    .FMA_Bp1       (bp1),
    .rst_n         (rst_n),
    .slice_rst     (slice_rst),
    .clk           (clk)
  );

  task automatic run_case;
    input [8*40-1:0] case_name;
    input [31:0] packed_a;
    input [31:0] packed_b;
    input [31:0] psum;
    input [31:0] mathematical_result;
    input        expect_exact;
    begin
      @(negedge clk);
      data_a = packed_a;
      data_b = packed_b;
      data_c = psum;
      bp0 = 1'b1;
      @(posedge clk);
      #1;
      bp0 = 1'b0;
      $display(
        "CASE=%0s A=%08x B=%08x C=%08x RTL=%08x MODEL=%08x MATCH=%0d EXPECT_EXACT=%0d",
        case_name,
        packed_a,
        packed_b,
        psum,
        result,
        mathematical_result,
        result === mathematical_result,
        expect_exact
      );
      if ((result === mathematical_result) !== expect_exact) begin
        failures = failures + 1;
      end
    end
  endtask

  initial begin
    repeat (2) @(posedge clk);
    rst_n = 1'b1;

    // DataA is four signed bytes, DataB is four unsigned bytes, DataC is psum32.
    run_case("four_ones_bias_off", 32'h01010101, 32'h01010101, 32'h00000000, 32'h00000004, 1'b0);
    run_case("four_ones_bias_on",  32'h01010101, 32'h01010101, 32'h00000005, 32'h00000009, 1'b0);
    run_case("positive_full_range", 32'h7f7f7f7f, 32'hffffffff, 32'h00000000, 32'h0001fa04, 1'b0);
    run_case("negative_full_range", 32'h80808080, 32'hffffffff, 32'h00000000, 32'hfffe0200, 1'b0);
    run_case("mixed_sign", 32'h7f8001ff, 32'hffffffff, 32'h00000000, 32'hffffff01, 1'b0);
    run_case("k3_tail_small", 32'h01010100, 32'h01010100, 32'h00000000, 32'h00000003, 1'b1);
    run_case("k3_tail_full_range", 32'h7f7f7f00, 32'hffffff00, 32'h00000000, 32'h00017b83, 1'b0);

    // A zero-psum one-product occurrence is the serialized arithmetic control.
    run_case("one_product_zero_psum", 32'h01000000, 32'h01000000, 32'h00000000, 32'h00000001, 1'b1);

    // K=5 requires the second occurrence to consume the first occurrence psum=4.
    run_case("k5_second_occurrence", 32'h01000000, 32'h01000000, 32'h00000004, 32'h00000005, 1'b0);

    // One-product occurrences with nonzero psum must preserve modulo-2^32 state.
    run_case("positive_psum_wrap", 32'h01000000, 32'h01000000, 32'h7fffffff, 32'h80000000, 1'b0);
    run_case("negative_psum_wrap", 32'hff000000, 32'h01000000, 32'h80000000, 32'h7fffffff, 1'b0);

    // Serialized single lane, x_zp=3, w=1, x=4, bias=7:
    // corrected initial psum = bias - x_zp*sum(w) = 4, dot=4, result=8.
    run_case("nonzero_xzp_bias_corrected", 32'h01000000, 32'h04000000, 32'h00000004, 32'h00000008, 1'b0);

    if (failures != 0) begin
      $display("TB_FAIL failures=%0d", failures);
      $fatal(1);
    end
    $display("TB_PASS");
    $finish;
  end
endmodule
