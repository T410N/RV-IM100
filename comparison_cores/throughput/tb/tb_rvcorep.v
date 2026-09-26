// RVCoreP 0.5.3, config.vh as shipped, wrapped at the RVCore boundary we synthesized.
// Memory timing follows its own D_SYNC_IMEM / D_SYNC_DMEM models: one-cycle
// synchronous read on both ports, the data port read every cycle.
module tb;
    reg clk = 0; always #5 clk = ~clk;
    reg rst_x = 0; initial begin repeat (20) @(posedge clk); rst_x <= 1; end
    wire [31:0] rout, I_ADDR, D_ADDR, I_IN, D_IN, D_OUT;
    wire [3:0]  D_WE;
    wire        halt;
    RVCore p (clk, rst_x, rout, halt, I_ADDR, D_ADDR, I_IN, D_IN, D_OUT, D_WE);
    // a load in Ex is squashed in the same cycle by a misprediction resolved in Ma (w_bmis),
    // exactly as RVCore masks D_WE; such a load is not a real access.
    wire real_d = (p.IdEx_op_ld & !p.w_bmis) | (|D_WE);
    reg [63:0] icnt = 0;  // as RVCoreP's top.v r_ICNT
    always @(posedge clk) if (rst_x && p.ExMa_v) icnt <= icnt + 1;
    tbmem m (.clk(clk), .run(rst_x), .i_en(rst_x), .i_addr(I_ADDR), .i_rdata(I_IN),
             .d_en(rst_x), .d_real(real_d & rst_x), .d_addr(D_ADDR), .d_wstrb(D_WE),
             .d_wdata(D_OUT), .d_rdata(D_IN), .instret(icnt));
    always @(posedge clk) if (rst_x && halt) begin $display("\nFATAL rvcore halt opcode cycles=%0d", m.cyc); $finish; end
endmodule
