`timescale 1ns/1ps

module conv_native_four_lane_df23e4d_boundary_tb;
  reg         clk = 1'b0;
  reg         rst_n = 1'b0;
  reg         slice_rst = 1'b0;
  reg  [31:0] data_a = 32'b0;
  reg  [31:0] data_b = 32'b0;
  reg  [31:0] data_c = 32'b0;
  reg         bp0 = 1'b0;
  wire [31:0] result;
  integer failures = 0;

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

  task check_case;
    input [31:0] weights;
    input [31:0] activations;
    input [31:0] psum;
    input [31:0] expected;
    input [8*32-1:0] label;
    begin
      @(negedge clk);
      data_a = weights;
      data_b = activations;
      data_c = psum;
      bp0 = 1'b1;
      @(posedge clk);
      #1;
      bp0 = 1'b0;
      $display(
        "CASE=%0s A=%08x B=%08x PSUM=%08x RAW=%08x SIGNC=%0d RESULT=%08x EXPECTED=%08x",
        label,
        weights,
        activations,
        psum,
        dut.u_SA_PE_Float_CSA.c_Result0_wire,
        dut.u_SA_PE_Float_CSA.i_SignC,
        result,
        expected
      );
      if (result !== expected)
        failures = failures + 1;
    end
  endtask

  initial begin
    repeat (2) @(posedge clk);
    rst_n = 1'b1;

    // Frozen hwop-0003-00 witness: [-1,0,0,1] dot [21,24,24,26] = +5.
    check_case(32'hff000001, 32'h1518181a, 32'hfffffffa,
               32'hffffffff, "NEG6_PLUS5_CONTROL");
    check_case(32'hff000001, 32'h1518181a, 32'hfffffffb,
               32'h00000000, "NODE0003_NEG5_PLUS5");
    check_case(32'hff000001, 32'h1518181a, 32'hfffffffc,
               32'h00000001, "NEG4_PLUS5_CONTROL");

    // Second named full-width boundary.
    check_case(32'h00000000, 32'hffffffff, 32'h80000000,
               32'h80000000, "INT32_MIN_PLUS_ZERO");

    // Four-lane signed-18 extrema for uint8 activation by int8 weight.
    check_case(32'h80808080, 32'hffffffff, 32'h00000000,
               32'hfffe0200, "DOT4_SIGNED18_MIN");
    check_case(32'h7f7f7f7f, 32'hffffffff, 32'h00000000,
               32'h0001fa04, "DOT4_SIGNED18_MAX");

    // Explicit modulo-s32 wrap controls.
    check_case(32'h01000000, 32'h01000000, 32'h7fffffff,
               32'h80000000, "INT32_MAX_PLUS_ONE_WRAP");
    check_case(32'hff000000, 32'h01000000, 32'h80000000,
               32'h7fffffff, "INT32_MIN_MINUS_ONE_WRAP");

    if (failures != 0) begin
      $display("RTL_REPAIR_DIRECTED_FAIL failures=%0d", failures);
      $fatal(1);
    end
    $display("RTL_REPAIR_DIRECTED_PASS");
    $finish;
  end
endmodule
