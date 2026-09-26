// PicoRV32 as synthesized: ENABLE_MUL=1, ENABLE_DIV=1, everything else default.
// +define+LA: look-ahead memory, as picorv32/dhrystone/testbench.v (README 0.516 DMIPS/MHz)
// default   : registered-ready memory, as picorv32/dhrystone/testbench_nola.v
module tb;
    reg clk = 0; always #5 clk = ~clk;
    reg resetn = 0; initial begin repeat (20) @(posedge clk); resetn <= 1; end
    wire trap, mem_valid, mem_instr, mem_la_read, mem_la_write;
    wire [31:0] mem_addr, mem_wdata, mem_la_addr, mem_la_wdata, d_rdata;
    wire [3:0]  mem_wstrb, mem_la_wstrb;
    wire        mem_ready;
`ifdef PUBCFG  // the configuration behind the README's published Dhrystone figure
    picorv32 #(.BARREL_SHIFTER(1), .ENABLE_FAST_MUL(1), .ENABLE_DIV(1)) uut (
`else
    picorv32 #(.ENABLE_MUL(1), .ENABLE_DIV(1)) uut (
`endif
        .clk(clk), .resetn(resetn), .trap(trap),
        .mem_valid(mem_valid), .mem_instr(mem_instr), .mem_ready(mem_ready),
        .mem_addr(mem_addr), .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb), .mem_rdata(d_rdata),
        .mem_la_read(mem_la_read), .mem_la_write(mem_la_write), .mem_la_addr(mem_la_addr),
        .mem_la_wdata(mem_la_wdata), .mem_la_wstrb(mem_la_wstrb),
        .pcpi_wr(1'b0), .pcpi_rd(32'b0), .pcpi_wait(1'b0), .pcpi_ready(1'b0), .irq(32'b0));
`ifdef LA
    assign mem_ready = 1'b1;
    wire        d_en    = mem_la_read | mem_la_write;
    wire [31:0] d_addr  = mem_la_addr;
    wire [3:0]  d_wstrb = mem_la_write ? mem_la_wstrb : 4'b0;
    wire [31:0] d_wdata = mem_la_wdata;
`else
    reg ready_r = 0;
    assign mem_ready = ready_r;
    wire        d_en    = mem_valid & !ready_r;
    wire [31:0] d_addr  = mem_addr;
    wire [3:0]  d_wstrb = mem_wstrb;
    wire [31:0] d_wdata = mem_wdata;
    always @(posedge clk) ready_r <= resetn & d_en;
`endif
    wire [31:0] unused_i;
    tbmem m (.clk(clk), .run(resetn), .i_en(1'b0), .i_addr(32'b0), .i_rdata(unused_i),
             .d_en(d_en & resetn), .d_real(d_en & resetn), .d_addr(d_addr), .d_wstrb(d_wstrb),
             .d_wdata(d_wdata), .d_rdata(d_rdata), .instret(uut.count_instr));
    always @(posedge clk) if (resetn && trap) begin $display("\nFATAL trap cycles=%0d", m.cyc); $finish; end
endmodule
