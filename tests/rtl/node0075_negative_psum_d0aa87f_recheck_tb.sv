`timescale 1ns/1ps

module node0075_negative_psum_d0aa87f_recheck_tb;
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

  task automatic run_case(
    input [8*32-1:0] label,
    input [31:0] psum,
    input [31:0] expected
  );
    begin
      @(negedge clk);
      data_a = 32'h01fe11fe;
      data_b = 32'h1c0d0100;
      data_c = psum;
      bp0 = 1'b1;
      @(posedge clk);
      #1;
      bp0 = 1'b0;
      $display(
        "NODE0075_D0AA_CASE label=%0s psum=%08x magnitude=%08x csa_raw=%08x sign=%0d result=%08x expected=%08x",
        label,
        psum,
        dut.u_SA_PE_Float_Control.o_AddFract,
        dut.u_SA_PE_Float_CSA.c_Result0_wire,
        dut.u_SA_PE_Float_CSA.Int_Res_Sign,
        result,
        expected
      );
    end
  endtask

  initial begin
    repeat (2) @(posedge clk);
    rst_n = 1'b1;

    // Frozen node0075 lanes:
    // B/s8=[1,-2,17,-2], A/u8=[28,13,1,0], dot4=+19.
    run_case("neg20_plus19", 32'hffffffec, 32'hffffffff);
    run_case("neg19_plus19", 32'hffffffed, 32'h00000000);
    run_case("neg18_plus19", 32'hffffffee, 32'h00000001);
    run_case("zero_plus19",  32'h00000000, 32'h00000013);
    run_case("pos7_plus19",  32'h00000007, 32'h0000001a);

    $finish;
  end
endmodule
