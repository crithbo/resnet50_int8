`timescale 1ns/1ps

module conv_native_four_lane_d0aa87f_witness_tb;
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
    input [31:0] psum;
    input [31:0] expected;
    input [8*24-1:0] label;
    begin
      @(negedge clk);
      // Frozen hwop-0003-00 witness lanes:
      // weight=[-1,0,0,1], activation=[21,24,24,26], dot4=+5.
      data_a = 32'hff000001;
      data_b = 32'h1518181a;
      data_c = psum;
      bp0 = 1'b1;
      @(posedge clk);
      #1;
      bp0 = 1'b0;
      $display(
        "CASE=%0s PSUM=%08x DOT4=00000005 RAW=%08x SIGNC=%0d RESULT=%08x EXPECTED=%08x",
        label,
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

    check_case(32'hfffffffa, 32'hffffffff, "NEG6_PLUS5_CONTROL");
    check_case(32'hfffffffb, 32'h00000000, "NODE0003_NEG5_PLUS5");
    check_case(32'hfffffffc, 32'h00000001, "NEG4_PLUS5_CONTROL");

    if (failures != 0) begin
      $display("CAPABILITY_OPEN failures=%0d", failures);
      $fatal(1);
    end
    $display("CAPABILITY_CLOSED");
    $finish;
  end
endmodule
