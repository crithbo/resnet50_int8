// Package-local observer compile repair for QLinearAdd node0007 v20.
// This is read-only instrumentation.  It binds the qualified GA inbuffer
// capture pulses consumed by the unchanged v19 diagnostic tail.
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
      [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_INPORT_NUM-1:0]
      return_obs_ga_operand_capture_mon;

generate
    for (genvar qadd_v20_group = 0;
         qadd_v20_group < `SLICE_GROUP_SIZE; qadd_v20_group++) begin
        for (genvar qadd_v20_slice = 0;
             qadd_v20_slice < `SLICE_GROUP_NUM; qadd_v20_slice++) begin
            for (genvar qadd_v20_row = 0;
                 qadd_v20_row < `GA_ROW_PE_NUM; qadd_v20_row++) begin
                assign return_obs_ga_operand_capture_mon
                    [qadd_v20_group][qadd_v20_slice][qadd_v20_row][0] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[qadd_v20_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[qadd_v20_slice]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[qadd_v20_row].GA_COL_PE[0].GA_PE
                        .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_enable;
                assign return_obs_ga_operand_capture_mon
                    [qadd_v20_group][qadd_v20_slice][qadd_v20_row][1] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[qadd_v20_group]
                        .u_slice_with_datahub_mc_group.slice_group_gen[qadd_v20_slice]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[qadd_v20_row].GA_COL_PE[2].GA_PE
                        .u_GA_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_enable;
            end
        end
    end
endgenerate

`include "qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"
