// Core-only synthesis wrapper for PicoRV32.
//
// Matches the methodology used for the RV-IM100 cores: the core alone, with its
// memory interface left at the top-level boundary so no RAM or ROM is inferred
// and the area figure is comparable across designs.
//
// ENABLE_MUL and ENABLE_DIV are turned on as specified; everything else is left
// at the core's own defaults.  ENABLE_FAST_MUL stays off -- it is a separate
// opt-in, not part of "default with mul/div".
module picorv32_top (
    input  wire        clk,
    input  wire        resetn,
    output wire        trap,
    output wire        mem_valid,
    output wire        mem_instr,
    input  wire        mem_ready,
    output wire [31:0] mem_addr,
    output wire [31:0] mem_wdata,
    output wire [ 3:0] mem_wstrb,
    input  wire [31:0] mem_rdata,
    output wire        mem_la_read,
    output wire        mem_la_write,
    output wire [31:0] mem_la_addr,
    output wire [31:0] mem_la_wdata,
    output wire [ 3:0] mem_la_wstrb,
    output wire        pcpi_valid,
    output wire [31:0] pcpi_insn,
    output wire [31:0] pcpi_rs1,
    output wire [31:0] pcpi_rs2,
    input  wire        pcpi_wr,
    input  wire [31:0] pcpi_rd,
    input  wire        pcpi_wait,
    input  wire        pcpi_ready,
    input  wire [31:0] irq,
    output wire [31:0] eoi
);
    picorv32 #(
        .ENABLE_MUL(1'b1),
        .ENABLE_DIV(1'b1)
    ) u_picorv32 (
        .clk(clk), .resetn(resetn), .trap(trap),
        .mem_valid(mem_valid), .mem_instr(mem_instr), .mem_ready(mem_ready),
        .mem_addr(mem_addr), .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb),
        .mem_rdata(mem_rdata),
        .mem_la_read(mem_la_read), .mem_la_write(mem_la_write),
        .mem_la_addr(mem_la_addr), .mem_la_wdata(mem_la_wdata), .mem_la_wstrb(mem_la_wstrb),
        .pcpi_valid(pcpi_valid), .pcpi_insn(pcpi_insn),
        .pcpi_rs1(pcpi_rs1), .pcpi_rs2(pcpi_rs2),
        .pcpi_wr(pcpi_wr), .pcpi_rd(pcpi_rd),
        .pcpi_wait(pcpi_wait), .pcpi_ready(pcpi_ready),
        .irq(irq), .eoi(eoi)
    );
endmodule
