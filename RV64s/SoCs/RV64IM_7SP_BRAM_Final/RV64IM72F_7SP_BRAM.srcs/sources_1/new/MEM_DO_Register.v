module MEM_DO_Register #(
    parameter XLEN = 64
) (
    input wire clk,
    input wire clk_enable,
    input wire reset,
    input wire flush,
    input wire MEM_DO_stall,

    input wire [XLEN-1:0] MEM_pc,
    input wire [XLEN-1:0] MEM_pc_plus_4,
    input wire [31:0] MEM_instruction,

    input wire [2:0] MEM_register_file_write_data_select,
    input wire [XLEN-1:0] MEM_imm,
    input wire [19:0] MEM_raw_imm,
    input wire [XLEN-1:0] MEM_csr_read_data,
    input wire [XLEN-1:0] MEM_alu_result,
    input wire MEM_register_write_enable,
    input wire MEM_csr_write_enable,
    input wire [4:0] MEM_rs1,
    input wire [4:0] MEM_rd,
    input wire [6:0] MEM_opcode,
    input wire [XLEN-1:0] MEM_byte_enable_logic_register_file_write_data,

    output reg [XLEN-1:0] DO_pc,
    output reg [XLEN-1:0] DO_pc_plus_4,
    output reg [31:0] DO_instruction,

    output reg [2:0] DO_register_file_write_data_select,
    output reg [XLEN-1:0] DO_imm,
    output reg [19:0] DO_raw_imm,
    output reg [XLEN-1:0] DO_csr_read_data,
    output reg [XLEN-1:0] DO_alu_result,
    output reg DO_register_write_enable,
    output reg DO_csr_write_enable,
    output reg [4:0] DO_rs1,
    output reg [4:0] DO_rd,
    output reg [6:0] DO_opcode,

    output reg [XLEN-1:0] DO_byte_enable_logic_register_file_write_data
);

  always @(posedge clk or posedge reset) begin
    if (reset) begin
        DO_pc <= {XLEN{1'b0}};
        DO_pc_plus_4 <= {XLEN{1'b0}};
        DO_instruction <= 32'h0000_0013; // ADDI x0, x0, 0 = RISC-V NOP, HINT

        DO_register_file_write_data_select <= 3'b0;
        DO_imm <= {XLEN{1'b0}};
        DO_raw_imm <= 20'b0;
        DO_csr_read_data <= {XLEN{1'b0}};
        DO_alu_result <= {XLEN{1'b0}};
        DO_register_write_enable <= 1'b0;
        DO_csr_write_enable <= 1'b0;
        DO_rs1 <= 5'b0;
        DO_rd <= 5'b0;
        DO_opcode <= 7'b0;

        DO_byte_enable_logic_register_file_write_data <= {XLEN{1'b0}};
    end 
    else if (clk_enable) begin
        if (flush) begin
            DO_pc <= {XLEN{1'b0}};
            DO_pc_plus_4 <= {XLEN{1'b0}};
            DO_instruction <= 32'h0000_0013; // ADDI x0, x0, 0 = RISC-V NOP, HINT

            DO_register_file_write_data_select <= 3'b0;
            DO_imm <= {XLEN{1'b0}};
            DO_raw_imm <= 20'b0;
            DO_csr_read_data <= {XLEN{1'b0}};
            DO_alu_result <= {XLEN{1'b0}};
            DO_register_write_enable <= 1'b0;
            DO_csr_write_enable <= 1'b0;
            DO_rs1 <= 5'b0;
            DO_rd <= 5'b0;
            DO_opcode <= 7'b0;

            DO_byte_enable_logic_register_file_write_data <= {XLEN{1'b0}};
        end 
        else if (!MEM_DO_stall) begin
                DO_pc <= MEM_pc;
                DO_pc_plus_4 <= MEM_pc_plus_4;
                DO_instruction <= MEM_instruction;

                DO_register_file_write_data_select <= MEM_register_file_write_data_select;
                DO_imm <= MEM_imm;
                DO_raw_imm <= MEM_raw_imm;
                DO_csr_read_data <= MEM_csr_read_data;
                DO_alu_result <= MEM_alu_result;
                DO_register_write_enable <= MEM_register_write_enable;
                DO_csr_write_enable <= MEM_csr_write_enable;
                DO_rs1 <= MEM_rs1;
                DO_rd <= MEM_rd;
                DO_opcode <= MEM_opcode;
                DO_byte_enable_logic_register_file_write_data <= MEM_byte_enable_logic_register_file_write_data;
            end
        end
    end
endmodule