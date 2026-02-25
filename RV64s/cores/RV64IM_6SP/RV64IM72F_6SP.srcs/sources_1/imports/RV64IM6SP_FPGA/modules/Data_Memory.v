module DataMemory #(
    parameter XLEN = 64
)(
    input clk,
    input clk_enable,
    input write_enable,
    input [XLEN-1:0] address,
    input [XLEN-1:0] write_data,
    input [7:0] write_mask,
    input [XLEN-1:0] rom_read_data,
    output [XLEN-1:0] rom_address,
    output reg [XLEN-1:0] read_data
);

    reg [XLEN-1:0] memory [0:8191];
    reg [XLEN-1:0] new_word;
    wire [XLEN-1:0] extended_mask = {{8{write_mask[7]}}, {8{write_mask[6]}}, {8{write_mask[5]}}, {8{write_mask[4]}}, {8{write_mask[3]}}, {8{write_mask[2]}}, {8{write_mask[1]}}, {8{write_mask[0]}}};
    wire ram_access = (address[31:16] == 16'h1000);
    wire rom_access = (address[31:16] == 16'h0000);
    wire [12:0] ram_address = address[15:3];
    assign rom_address = address;

    integer i;
    initial begin
        for (i=0; i<8192; i=i+1) begin
            memory[i] = {XLEN{1'b0}};
        end
        new_word = {XLEN{1'b0}};
    end

    always @(*) begin
        if (ram_access) begin
            read_data = memory[ram_address];
        end 
        else if (rom_access) begin
            read_data = rom_read_data;
        end 
        else begin
            read_data = {XLEN{1'b0}};
        end
        
    end

    always @(posedge clk) begin
        if (clk_enable && write_enable && ram_access) begin
            new_word = ((memory[ram_address] & ~extended_mask) | (write_data & extended_mask));
            memory[ram_address] <= new_word;
        end
    end

endmodule