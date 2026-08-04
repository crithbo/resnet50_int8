`timescale 1ns/1ps
`define SLICE_GROUP_SIZE 1
`define SLICE_GROUP_NUM 2
`define GA_ROW_PE_NUM 4
`define MEMORY_STREAM_ENGINE_NUM 5
`define MSE_REQ_CHL_NUM 2
`define NATIVE_RETURN_OBSERVER_ENABLE

module DummyGAInbuffer;
    logic alu_pipeline0_valid_bit;
    logic alu_pipeline0_bp_post;
    logic ga_pe_alu_pipeline0_enable;
endmodule

module DummyGAInner;
    logic ga_pe_outbuffer_wr_en;
    DummyGAInbuffer u_GA_PE_Inbuffer();
endmodule

module DummyGAWrapper;
    DummyGAInner u_GA_PE();
endmodule

module DummyGAGroup;
    generate
        for (genvar row = 0; row < `GA_ROW_PE_NUM; row++) begin : GA_ROW_PE
            for (genvar column = 0; column < 3; column++) begin : GA_COL_PE
                DummyGAWrapper GA_PE();
            end
        end
    endgenerate
endmodule

module DummyGA;
    DummyGAGroup u_GA_PE_Group();
endmodule

module DummyExec;
    logic slice_cmpt_finish;
endmodule

module DummySlice;
    DummyExec u_Slice_Execution_Manager();
    DummyGA u_General_Array();
endmodule

module DummyWrapper;
    DummySlice u_Slice();
endmodule

module DummySliceGroup;
    generate
        for (genvar slice = 0; slice < 2; slice++) begin : slice_group_gen
            DummyWrapper u_slice_wrapper();
        end
    endgenerate
endmodule

module DummyTop;
    logic clk_sg;
    logic clk_db;
    generate
        for (genvar group = 0; group < 1; group++) begin
            : slice_with_datahub_mc_group_gen
            DummySliceGroup u_slice_with_datahub_mc_group();
        end
    endgenerate
endmodule

module tb_maxpool_node0002_observer_compile;
    DummyTop u_NDP_Top_new();
    logic [0:0][1:0] gexec2slice_fire_mon;
    logic [0:0][1:0][4:0][1:0] local_req_hs;
    logic [0:0][1:0][4:0][1:0] local_rdata_hs;
    logic [0:0][1:0][4:0][1:0] local_wdata_hs;

`include "maxpool_node0002_progress_observer_v4.svh"

    initial begin
        u_NDP_Top_new.clk_sg = 0;
        u_NDP_Top_new.clk_db = 0;
        gexec2slice_fire_mon = '0;
        local_req_hs = '0;
        local_rdata_hs = '0;
        local_wdata_hs = '0;
        #1 $finish;
    end
endmodule
