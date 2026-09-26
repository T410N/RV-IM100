// VexRiscv GenFullNoMmuNoCache (DebugPlugin removed), simple iBus/dBus.
// Zero-wait: cmd always accepted, response on the next cycle (Murax / regression timing).
module tb;
    reg clk = 0; always #5 clk = ~clk;
    reg reset = 1; initial begin repeat (20) @(posedge clk); reset <= 0; end
    wire        ic_valid, dc_valid, dc_wr;
    wire [31:0] ic_pc, dc_addr, dc_data, i_rdata, d_rdata;
    wire [3:0]  dc_mask;
    wire [1:0]  dc_size;
    reg         ir_valid = 0, dr_valid = 0;
    VexRiscv uut (
        .iBus_cmd_valid(ic_valid), .iBus_cmd_ready(1'b1), .iBus_cmd_payload_pc(ic_pc),
        .iBus_rsp_valid(ir_valid), .iBus_rsp_payload_error(1'b0), .iBus_rsp_payload_inst(i_rdata),
        .timerInterrupt(1'b0), .externalInterrupt(1'b0), .softwareInterrupt(1'b0),
        .dBus_cmd_valid(dc_valid), .dBus_cmd_ready(1'b1), .dBus_cmd_payload_wr(dc_wr),
        .dBus_cmd_payload_mask(dc_mask), .dBus_cmd_payload_address(dc_addr),
        .dBus_cmd_payload_data(dc_data), .dBus_cmd_payload_size(dc_size),
        .dBus_rsp_ready(dr_valid), .dBus_rsp_error(1'b0), .dBus_rsp_data(d_rdata),
        .clk(clk), .reset(reset));
    always @(posedge clk) begin
        ir_valid <= !reset & ic_valid;
        dr_valid <= !reset & dc_valid & !dc_wr;
    end
    wire run = !reset;
    tbmem m (.clk(clk), .run(run), .i_en(ic_valid & run), .i_addr(ic_pc), .i_rdata(i_rdata),
             .d_en(dc_valid & run), .d_real(dc_valid & run), .d_addr(dc_addr),
             .d_wstrb(dc_wr ? dc_mask : 4'b0), .d_wdata(dc_data), .d_rdata(d_rdata), .instret(64'd0));
endmodule
