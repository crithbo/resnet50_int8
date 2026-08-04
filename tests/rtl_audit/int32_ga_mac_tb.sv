`timescale 1ns/1ps

module int32_ga_mac_tb;
  reg         clk = 1'b0;
  reg         rst_n = 1'b0;
  reg         slice_rst = 1'b0;
  reg  [31:0] data_a = 32'b0;
  reg  [31:0] data_b = 32'b0;
  reg  [31:0] data_c = 32'b0;
  reg         pipeline0_enable = 1'b0;
  reg         pipeline1_enable = 1'b0;
  wire [31:0] result;
  integer     failures = 0;

  always #5 clk = ~clk;

  // 5'b01110 is the encoder's "int32_mac":
  // mode=integer, precision=int32, low opcode=MAC.
  GA_PE_ALU dut (
    .clk                    (clk),
    .rst_n                  (rst_n),
    .slice_rst              (slice_rst),
    .ga_pe_alu_opcode       (5'b01110),
    .ga_pe_alu_input_data   ({data_c, data_b, data_a}),
    .ga_pe_alu_pipeline0_enable(pipeline0_enable),
    .ga_pe_alu_pipeline1_enable(pipeline1_enable),
    .ga_pe_alu2outbuffer_data(result)
  );

  task automatic run_case;
    input [8*40-1:0] case_name;
    input [31:0] operand_a;
    input [31:0] operand_b;
    input [31:0] accumulator;
    input [31:0] expected;
    begin
      @(negedge clk);
      data_a = operand_a;
      data_b = operand_b;
      data_c = accumulator;
      pipeline0_enable = 1'b1;
      @(posedge clk);
      #1;
      pipeline0_enable = 1'b0;
      pipeline1_enable = 1'b1;
      @(posedge clk);
      #1;
      pipeline1_enable = 1'b0;
      $display(
        "CASE=%0s A=%08x B=%08x C=%08x RTL=%08x MODEL=%08x MATCH=%0d",
        case_name,
        operand_a,
        operand_b,
        accumulator,
        result,
        expected,
        result === expected
      );
      if (result !== expected) begin
        failures = failures + 1;
      end
    end
  endtask

  initial begin
    repeat (2) @(posedge clk);
    rst_n = 1'b1;

    run_case("positive", 32'd127, 32'd255, 32'd5, 32'd32390);
    run_case("negative", -32'sd128, 32'd255, 32'd7, -32'sd32633);
    run_case("mixed_negative_c", -32'sd3, 32'd11, -32'sd9, -32'sd42);
    run_case("positive_wrap", 32'd1, 32'd1, 32'h7fffffff, 32'h80000000);
    run_case("negative_wrap", -32'sd1, 32'd1, 32'h80000000, 32'h7fffffff);
    run_case("large_modulo", 32'h40000000, 32'd4, 32'd3, 32'h00000003);

    if (failures != 0) begin
      $display("TB_FAIL failures=%0d", failures);
      $fatal(1);
    end
    $display("TB_PASS");
    $finish;
  end
endmodule
