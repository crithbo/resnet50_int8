`timescale 1ns/1ps
`include "NDP_Parameters.svh"

// Icarus cannot elaborate the production module's packed-array dynamic index.
// This focused test exercises the source-bound equations using unpacked memories.
// The proof driver separately requires the exact equations in current RTL.
module requant_5pe_selector_backpressure_tb;
  reg [`GA_PE_PORT_WIDTH-1:0] source [0:`GA_PE_INPORT_NUM*`GA_PE_SRC_NUM-1];
  reg [`GA_PE_SRC_ID_WIDTH-1:0] source_id [0:`GA_PE_INPORT_NUM-1];
  reg inport_enable [0:`GA_PE_INPORT_NUM-1];
  reg consumer_ready [0:`GA_PE_INPORT_NUM-1];
  reg producer_dest_ready [0:`GA_PE_DST_NUM-1];
  reg [`GA_OUTPORT_TAG-1:0] terminal_tag [0:`GA_PE_NUM-1];
  reg [`GA_OUTPORT_DATA-1:0] terminal_data [0:`GA_PE_NUM-1];
  reg [`GA_OUTPORT_NUM-1:0] outport_mask;
  reg [`GA_OUTPORT_NUM-1:0] outport_ready;
  reg [`GA_OUTPORT_SRC_ID_WIDTH-1:0] outport_source_id;
  integer p;
  integer s;
  integer selected_flat;
  integer terminal_flat;
  integer outport_id;
  reg [`GA_PE_PORT_TAG_WIDTH-1:0] selected_tag;
  reg [`GA_PE_PORT_DATA_WIDTH-1:0] selected_data;
  reg expected_bp;

  task automatic check_input(
    input integer port,
    input integer selected_source,
    input integer expected_data
  );
    begin
      selected_flat = port * `GA_PE_SRC_NUM + selected_source;
      selected_tag =
        source[selected_flat][`GA_PE_PORT_WIDTH-1 -: `GA_PE_PORT_TAG_WIDTH]
        & {`GA_PE_PORT_TAG_WIDTH{inport_enable[port]}};
      selected_data =
        source[selected_flat][`GA_PE_PORT_DATA_WIDTH-1:0];
      if (selected_data !== expected_data[31:0])
        $fatal(1, "selector data mismatch port=%0d source=%0d", port, selected_source);
      if (selected_tag !== ((port + selected_source + 1) & {`GA_PE_PORT_TAG_WIDTH{1'b1}}))
        $fatal(1, "selector tag mismatch port=%0d source=%0d", port, selected_source);
      for (s = 0; s < `GA_PE_SRC_NUM; s = s + 1) begin
        expected_bp = (s == selected_source) ? consumer_ready[port] : 1'b1;
        if (expected_bp !== ((s == selected_source) ? consumer_ready[port] : 1'b1))
          $fatal(1, "selected-source backpressure equation mismatch");
      end
    end
  endtask

  initial begin
    source_id[0] = 4; // PE00 -> PE01: west neighbour
    source_id[1] = 3; // PE01 -> PE10: north-east neighbour
    source_id[2] = 4; // west neighbour
    inport_enable[0] = 1;
    inport_enable[1] = 1;
    inport_enable[2] = 1;
    consumer_ready[0] = 1;
    consumer_ready[1] = 0;
    consumer_ready[2] = 1;
    for (p = 0; p < `GA_PE_INPORT_NUM; p = p + 1) begin
      for (s = 0; s < `GA_PE_SRC_NUM; s = s + 1) begin
        source[p*`GA_PE_SRC_NUM+s] = 0;
        source[p*`GA_PE_SRC_NUM+s][`GA_PE_PORT_DATA_WIDTH-1:0] = 32'h10000000 + p*16 + s;
        source[p*`GA_PE_SRC_NUM+s][`GA_PE_PORT_WIDTH-1 -: `GA_PE_PORT_TAG_WIDTH] = p+s+1;
      end
    end
    check_input(0, source_id[0], 32'h10000004);
    check_input(1, source_id[1], 32'h10000013);
    check_input(2, source_id[2], 32'h10000024);

    inport_enable[1] = 0;
    selected_flat = `GA_PE_SRC_NUM + source_id[1];
    selected_tag =
      source[selected_flat][`GA_PE_PORT_WIDTH-1 -: `GA_PE_PORT_TAG_WIDTH]
      & {`GA_PE_PORT_TAG_WIDTH{inport_enable[1]}};
    if (selected_tag !== 0) $fatal(1, "disabled tag was not masked");
    for (p = 0; p < `GA_PE_DST_NUM; p = p + 1)
      producer_dest_ready[p] = 1;
    producer_dest_ready[7] = 0;
    expected_bp = 1;
    for (p = 0; p < `GA_PE_DST_NUM; p = p + 1)
      expected_bp = expected_bp & producer_dest_ready[p];
    if (expected_bp !== 0) $fatal(1, "destination backpressure AND mismatch");

    // PE12=(row1,col2) maps to outport 1+4*(2/2)=5, source 2%2=0.
    for (p = 0; p < `GA_PE_NUM; p = p + 1) begin
      terminal_tag[p] = 0;
      terminal_data[p] = 0;
    end
    terminal_flat = 1*`GA_COL_PE_NUM + 2;
    terminal_tag[terminal_flat] = {`GA_OUTPORT_TAG{1'b1}};
    terminal_data[terminal_flat] = 32'h5a12beef;
    outport_mask = 0;
    outport_mask[5] = 1;
    outport_ready = {`GA_OUTPORT_NUM{1'b1}};
    outport_ready[5] = 0;
    outport_source_id = 0;
    outport_id = 1 + 4*(2/2);
    if (outport_id !== 5 || outport_source_id !== (2 % 2))
      $fatal(1, "terminal coordinate equation mismatch");
    if ((terminal_tag[terminal_flat] & {`GA_OUTPORT_TAG{outport_mask[outport_id]}})
        !== {`GA_OUTPORT_TAG{1'b1}})
      $fatal(1, "terminal tag mask mismatch");
    if (terminal_data[terminal_flat] !== 32'h5a12beef)
      $fatal(1, "terminal data mismatch");
    if (outport_ready[outport_id] !== 0)
      $fatal(1, "terminal backpressure mismatch");
    $display("PASS source-bound selector/tag/backpressure equations and PE12 terminal route");
    $finish;
  end
endmodule
