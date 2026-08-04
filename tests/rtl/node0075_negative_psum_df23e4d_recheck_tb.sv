`timescale 1ns/1ps

module node0075_negative_psum_df23e4d_recheck_tb;
  localparam integer MAX_CASES = 131072;

  reg         clk = 1'b0;
  reg         rst_n = 1'b0;
  reg         slice_rst = 1'b0;
  reg  [31:0] data_a = 32'b0;
  reg  [31:0] data_b = 32'b0;
  reg  [31:0] data_c = 32'b0;
  reg         bp0 = 1'b0;
  wire [31:0] result;

  reg [31:0] data_a_cases [0:MAX_CASES-1];
  reg [31:0] data_b_cases [0:MAX_CASES-1];
  reg [31:0] data_c_cases [0:MAX_CASES-1];
  reg [31:0] expected_cases [0:MAX_CASES-1];
  string data_a_path;
  string data_b_path;
  string data_c_path;
  string expected_path;
  integer case_count;
  integer index;
  integer mismatch_count;

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
    if (!$value$plusargs("DATA_A=%s", data_a_path)) $fatal(1, "missing DATA_A");
    if (!$value$plusargs("DATA_B=%s", data_b_path)) $fatal(1, "missing DATA_B");
    if (!$value$plusargs("DATA_C=%s", data_c_path)) $fatal(1, "missing DATA_C");
    if (!$value$plusargs("EXPECTED=%s", expected_path)) $fatal(1, "missing EXPECTED");
    if (!$value$plusargs("COUNT=%d", case_count)) $fatal(1, "missing COUNT");
    if (case_count < 1 || case_count > MAX_CASES) $fatal(1, "invalid COUNT");

    $readmemh(data_a_path, data_a_cases, 0, case_count - 1);
    $readmemh(data_b_path, data_b_cases, 0, case_count - 1);
    $readmemh(data_c_path, data_c_cases, 0, case_count - 1);
    $readmemh(expected_path, expected_cases, 0, case_count - 1);

    mismatch_count = 0;
    repeat (2) @(posedge clk);
    rst_n = 1'b1;

    for (index = 0; index < case_count; index = index + 1) begin
      @(negedge clk);
      data_a = data_a_cases[index];
      data_b = data_b_cases[index];
      data_c = data_c_cases[index];
      bp0 = 1'b1;
      @(posedge clk);
      #1;
      bp0 = 1'b0;
      if (result !== expected_cases[index]) mismatch_count = mismatch_count + 1;
      $display(
        "NODE0075_DF23_CASE index=%0d data_a=%08x data_b=%08x psum=%08x raw=%08x result=%08x expected=%08x match=%0d",
        index,
        data_a,
        data_b,
        data_c,
        dut.u_SA_PE_Float_CSA.c_Result0_wire,
        result,
        expected_cases[index],
        result === expected_cases[index]
      );
    end

    $display(
      "NODE0075_DF23_SUMMARY count=%0d mismatches=%0d marker=%0s",
      case_count,
      mismatch_count,
      mismatch_count == 0 ? "RTL_REPAIR_FULL_REACHABLE_PASS" : "RTL_REPAIR_FULL_REACHABLE_FAIL"
    );
    if (mismatch_count != 0) $fatal(1, "node0075 df23e4d mismatch");
    $finish;
  end
endmodule
