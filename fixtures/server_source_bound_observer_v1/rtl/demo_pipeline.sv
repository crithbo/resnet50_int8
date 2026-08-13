module demo_stage (
    input  logic         clk_db,
    input  logic         rst_n,
    input  logic         stage_active,
    input  logic         src_valid,
    input  logic         src_ready,
    input  logic         dst_valid,
    input  logic         dst_ready,
    input  logic [31:0]  payload,
    output logic         terminal_seen
);
    logic queue_full;
    logic [7:0] occupancy;

    always_ff @(posedge clk_db) begin
        if (!rst_n) begin
            terminal_seen <= 1'b0;
            queue_full <= 1'b0;
            occupancy <= 8'd0;
        end else begin
            if (src_valid && src_ready)
                occupancy <= occupancy + 1'b1;
            if (dst_valid && dst_ready)
                occupancy <= occupancy - 1'b1;
            queue_full <= &occupancy;
            terminal_seen <= stage_active && dst_valid && dst_ready;
        end
    end
endmodule

module unrelated_stage (
    input logic clk_other,
    input logic rst_other_n,
    input logic foreign_signal
);
endmodule
