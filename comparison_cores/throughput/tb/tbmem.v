// Shared zero-wait memory for the comparison-core throughput harness.
// Same map as the RV-IM100 SoC, so one image runs on every core:
//   ROM  0x0000_0000  64 KB;  BOOT 0x8000_0000: jalr x0,0(x0) for VexRiscv's reset vector
//   RAM  0x1000_0000  32 KB
//   UART 0x1001_0000 TX, 0x1001_0004 status (never busy)
//   HALT 0x1001_2000 (store ends the run)
//   TIMER 0x1002_0000 (cycles since reset release)
// Both ports read synchronously: data is registered on the clock edge after the
// address, and a same-cycle write returns the old data (BRAM read-first).
module tbmem (
    input  wire        clk,
    input  wire        run,             // high once reset is released
    input  wire        i_en,
    input  wire [31:0] i_addr,
    output reg  [31:0] i_rdata,
    input  wire        d_en,
    input  wire        d_real,          // a genuine load/store (RVCoreP reads its port every cycle)
    input  wire [31:0] d_addr,
    input  wire [3:0]  d_wstrb,         // 0 = read
    input  wire [31:0] d_wdata,
    input  wire [63:0] instret,         // retired instructions, from the core's own counter (0 if none)
    output reg  [31:0] d_rdata
);
    reg [31:0] rom [0:16383];
    reg [31:0] ram [0:8191];
    reg [31:0] cyc = 0;
    reg [8*512-1:0] image;          // up to 512 characters of path
    reg [63:0]  max_cycles;
    integer i;
    initial begin
        for (i = 0; i < 16384; i = i + 1) rom[i] = 32'h0;
        for (i = 0; i < 8192;  i = i + 1) ram[i] = 32'h0;
        if (!$value$plusargs("IMAGE=%s", image)) begin $display("FATAL no +IMAGE"); $finish; end
        $readmemh(image, rom);
        // an unreadable or truncated path leaves ROM zero and the core runs garbage: refuse it
        if (rom[0] == 32'h0) begin $display("FATAL image empty or unreadable: %0s", image); $finish; end
        if (!$value$plusargs("MAX_CYCLES=%d", max_cycles)) max_cycles = 64'd4000000000;
    end
    always @(posedge clk) if (run) begin
        cyc <= cyc + 1;
        if ({32'd0, cyc} >= max_cycles) begin $display("\nTIMEOUT cycles=%0d", cyc); $finish; end
    end

    function is_rom(input [31:0] a); is_rom = (a[31:16] == 16'd0); endfunction
    function is_ram(input [31:0] a); is_ram = (a[31:15] == 17'h02000); endfunction

    function [31:0] rd(input [31:0] a);
        if      (is_rom(a))            rd = rom[a[15:2]];
        else if (is_ram(a))            rd = ram[a[14:2]];
        else if (a == 32'h1001_0004)   rd = 32'h0;
        else if (a == 32'h1002_0000)   rd = cyc;
        else                           rd = 32'hDEAD_BEEF;
    endfunction

    always @(posedge clk) begin
        if (i_en) begin
            // 0x8000_0000 is a one-word boot ROM, jalr x0,0(x0): VexRiscv resets there and
            // must run the image at 0, where its PC-relative addressing was linked.
            i_rdata <= i_addr[31] ? 32'h0000_0067 : is_rom(i_addr) ? rom[i_addr[15:2]] : 32'h0;
        end
        if (d_en) begin
            if (d_wstrb == 4'b0) begin
                d_rdata <= rd(d_addr);
                if (d_real && d_addr == 32'h1002_0000) $display("\nTIMER %0d INSTRET %0d", cyc, instret);
                if (d_real && rd(d_addr) == 32'hDEAD_BEEF && !is_rom(d_addr) && !is_ram(d_addr))
                    begin $display("\nFATAL load unmapped %08x cycles=%0d", d_addr, cyc); $finish; end
            end else begin
                d_rdata <= rd(d_addr);
                if (is_ram(d_addr)) begin
                    if (d_wstrb[0]) ram[d_addr[14:2]][ 7: 0] <= d_wdata[ 7: 0];
                    if (d_wstrb[1]) ram[d_addr[14:2]][15: 8] <= d_wdata[15: 8];
                    if (d_wstrb[2]) ram[d_addr[14:2]][23:16] <= d_wdata[23:16];
                    if (d_wstrb[3]) ram[d_addr[14:2]][31:24] <= d_wdata[31:24];
                end else if (d_addr == 32'h1001_0000) begin
                    $write("%c", d_wdata[7:0]); $fflush;
                end else if (d_addr == 32'h1001_2000) begin
                    $display("\nHALT cycles=%0d", cyc); $finish;
                end else begin
                    $display("\nFATAL store outside RAM %08x cycles=%0d", d_addr, cyc); $finish;
                end
            end
        end
    end
endmodule
