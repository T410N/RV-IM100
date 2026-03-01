`include "./csr_funct3.vh"

module CSRFile #(
    parameter XLEN = 64
)(
    input clk,                            // clock signal
    input clk_enable,
    input reset,                          // reset signal
    input trapped,
    input csr_write_enable,               // write enable signal
    input [11:0] csr_read_address,        // address to read
    input [11:0] csr_write_address,       // address to write
    input [XLEN-1:0] csr_write_data,      // data to write
    input instruction_retired,
    input valid_csr_address,

    output reg [XLEN-1:0] csr_read_out,   // data from CSR Unit
    output reg csr_ready                  // signal to stall the process while accessing the CSR until it outputs the desired value.
    );

    wire [XLEN-1:0] mvendorid = 64'h52_49_53_43_2D_4B_43_21;    // RISC-KC!
    wire [XLEN-1:0] marchid   = 64'h52_56_36_34_49_4D_37_32;    // RV64IM72
    wire [XLEN-1:0] mhartid   = 64'h42_41_4E_41_4E_41_4E_41;    // BANANANA
    wire [XLEN-1:0] mstatus   = 64'h00000000_00001800;          // MPP[12:11] = 11
    wire [XLEN-1:0] misa      = 64'h80000000_00000080;          // MXL = 2; XLEN = 64; misa[63:62] = 10. RV32"I"; misa[8] = 1.
    reg [XLEN-1:0] mtvec;
    reg [XLEN-1:0] mepc;
    reg [XLEN-1:0] mcause;

    reg [XLEN-1:0] mcycle;
    reg [XLEN-1:0] minstret;

    reg csr_processing;
    reg [XLEN-1:0] csr_read_data;

    wire csr_access;

    assign csr_access = valid_csr_address;

    localparam [XLEN-1:0] DEFAULT_mtvec  = 64'h00006D60;
    localparam [XLEN-1:0] DEFAULT_mepc   = {XLEN{1'b0}};
    localparam [XLEN-1:0] DEFAULT_mcause = {XLEN{1'b0}};
    localparam [XLEN-1:0] DEFAULT_mcycle = 64'b0;
    localparam [XLEN-1:0] DEFAULT_minstret = 64'b0;
    // Read Operation.
    always @(*) begin
        case (csr_read_address)
            12'hB00: csr_read_data = mcycle[XLEN-1:0];
            12'hB02: csr_read_data = minstret[XLEN-1:0];
            12'hF11: csr_read_data = mvendorid;
            12'hF12: csr_read_data = marchid;
            12'hF14: csr_read_data = mhartid;
            12'h300: csr_read_data = mstatus;
            12'h301: csr_read_data = misa;
            12'h305: csr_read_data = mtvec;
            12'h341: csr_read_data = mepc;
            12'h342: csr_read_data = mcause;
            default: csr_read_data = {XLEN{1'b0}};
        endcase

        if (reset) begin
            csr_ready = 1'b1;
        end 
        else begin
            if (csr_access && !csr_processing) begin
                csr_ready = 1'b0;
            end 
            else if (csr_processing) begin
                csr_ready = 1'b1;
            end 
            else begin
                csr_ready = 1'b1;
            end
        end
    end

    // Reset Operation
    always @(posedge clk or posedge reset) begin
        if (reset) begin
            mtvec   <= DEFAULT_mtvec;
            mepc    <= DEFAULT_mepc;
            mcause  <= DEFAULT_mcause;
            mcycle  <= DEFAULT_mcycle;
            minstret <= DEFAULT_minstret;

            csr_processing <= 1'b0;
            csr_read_out <= {XLEN{1'b0}};
        end 
        else if (clk_enable) begin
            mcycle <= mcycle + 1;
          
            if (instruction_retired) begin
                minstret <= minstret + 1;
            end

            if (csr_access && !csr_processing) begin
                csr_processing <= 1'b1;
                csr_read_out <= csr_read_data;
            end 
            else if (csr_processing) begin
                csr_processing <= 1'b0;
                csr_read_out <= csr_read_data;
            end 
            else if (csr_write_enable) begin
                csr_read_out <= csr_read_data;
            end

            // Write Operation
            if ((trapped && csr_write_enable) || (csr_write_enable)) begin
            case (csr_write_address)
                12'h305: mtvec  <= csr_write_data;
                12'h341: mepc   <= csr_write_data;
                12'h342: mcause <= csr_write_data;
                default: ;
            endcase
            end
        end
    end


endmodule