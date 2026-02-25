`include "./opcode.vh"

module ForwardUnit #(
    parameter XLEN = 64
)(
    input wire clk,
    input wire clk_enable,
    input wire EX_MEM_stall,
    input wire EX_MEM_flush,

    // Hazard signals from Hazard Unit - ALU forwarding
    input wire [1:0] hazard_ex2,
    input wire [1:0] hazard_mem,
    input wire [1:0] hazard_wb,

    // Hazard signals from Hazard Unit - Store data forwarding
    input wire store_hazard_ex2,
    input wire store_hazard_mem,
    input wire store_hazard_wb,
    input wire store_hazard_wb_to_mem,

    // EX2 stage signals
    input wire [XLEN-1:0] EX2_imm,
    input wire [XLEN-1:0] EX2_alu_result,
    input wire [XLEN-1:0] EX2_csr_read_data,
    input wire [XLEN-1:0] EX2_pc_plus_4,
    input wire [6:0] EX2_opcode,

    // MEM stage signals
    input wire [XLEN-1:0] byte_enable_logic_register_file_write_data,

    // WB stage forward data (pre-registered in MEM_WB register)
    input wire [XLEN-1:0] WB_forward_data_value,

    // CSR hazard signals
    input wire csr_hazard_mem,
    input wire csr_hazard_wb,
    input wire [XLEN-1:0] MEM_csr_write_data,
    input wire [XLEN-1:0] WB_csr_write_data,
    input wire [XLEN-1:0] csr_read_data,

    // ALU forwarding signals
    output wire [XLEN-1:0] alu_forward_source_data_a,
    output wire [XLEN-1:0] alu_forward_source_data_b,
    output wire [2:0] alu_forward_source_select_a,
    output wire [2:0] alu_forward_source_select_b,
    output wire [XLEN-1:0] MEM_forward_data_value_out,

    // Store data forwarding outputs
    output wire [XLEN-1:0] store_forward_data,
    output wire store_forward_enable,

    // WB->MEM store data forwarding outputs
    output wire [XLEN-1:0] store_wb_to_mem_forward_data,
    output wire store_wb_to_mem_forward_enable,

    // CSR forward output
    output wire [XLEN-1:0] csr_forward_data
);

    // EX2 stage forward data selection
    reg [XLEN-1:0] EX2_forward_data_value;

    always @(*) begin
        case (EX2_opcode)
            `OPCODE_ENVIRONMENT : EX2_forward_data_value = EX2_csr_read_data;
            `OPCODE_LUI         : EX2_forward_data_value = EX2_imm;
            `OPCODE_JAL         : EX2_forward_data_value = EX2_pc_plus_4;
            `OPCODE_JALR        : EX2_forward_data_value = EX2_pc_plus_4;
            default             : EX2_forward_data_value = EX2_alu_result;
        endcase
    end

    wire MEM_forward_is_load_next = (EX2_opcode == `OPCODE_LOAD);

    reg [XLEN-1:0] MEM_non_load_forward_data_next;
    always @(*) begin
        case (EX2_opcode)
            `OPCODE_LUI         : MEM_non_load_forward_data_next = EX2_imm;
            `OPCODE_JAL         : MEM_non_load_forward_data_next = EX2_pc_plus_4;
            `OPCODE_JALR        : MEM_non_load_forward_data_next = EX2_pc_plus_4;
            `OPCODE_ENVIRONMENT : MEM_non_load_forward_data_next = EX2_csr_read_data;
            default             : MEM_non_load_forward_data_next = EX2_alu_result;
        endcase
    end

    reg MEM_forward_is_load;
    reg [XLEN-1:0] MEM_non_load_forward_data;

    always @(posedge clk) begin
        if (EX_MEM_flush) begin
            MEM_forward_is_load <= 1'b0;
            MEM_non_load_forward_data <= {XLEN{1'b0}};
        end
        else if (clk_enable && !EX_MEM_stall) begin
            MEM_forward_is_load <= MEM_forward_is_load_next;
            MEM_non_load_forward_data <= MEM_non_load_forward_data_next;
        end
    end

    wire [XLEN-1:0] MEM_forward_data_value = MEM_forward_is_load 
        ? byte_enable_logic_register_file_write_data 
        : MEM_non_load_forward_data;

    assign MEM_forward_data_value_out = MEM_forward_data_value;

    // ALU source forwarding selection
    assign alu_forward_source_select_a = 
        hazard_ex2[0] ? 3'b001 :
        hazard_mem[0] ? 3'b010 :
        hazard_wb[0]  ? 3'b011 : 3'b000;

    assign alu_forward_source_select_b = 
        hazard_ex2[1] ? 3'b001 :
        hazard_mem[1] ? 3'b010 :
        hazard_wb[1]  ? 3'b011 : 3'b000;

    assign alu_forward_source_data_a = 
        ({XLEN{hazard_ex2[0]}} & EX2_forward_data_value) |
        ({XLEN{hazard_mem[0]}} & MEM_forward_data_value) |
        ({XLEN{hazard_wb[0]}}  & WB_forward_data_value);

    assign alu_forward_source_data_b = 
        ({XLEN{hazard_ex2[1]}} & EX2_forward_data_value) |
        ({XLEN{hazard_mem[1]}} & MEM_forward_data_value) |
        ({XLEN{hazard_wb[1]}}  & WB_forward_data_value);

    assign store_forward_enable = store_hazard_ex2 || store_hazard_mem || store_hazard_wb;
    assign store_forward_data = 
        ({XLEN{store_hazard_ex2}} & EX2_forward_data_value) |
        ({XLEN{store_hazard_mem}} & MEM_forward_data_value) |
        ({XLEN{store_hazard_wb}}  & WB_forward_data_value);

    assign store_wb_to_mem_forward_enable = store_hazard_wb_to_mem;
    assign store_wb_to_mem_forward_data = WB_forward_data_value;

    reg [XLEN-1:0] csr_forward_data_value;
    assign csr_forward_data = csr_forward_data_value;

    always @(*) begin
        if (csr_hazard_mem)
            csr_forward_data_value = MEM_csr_write_data;
        else if (csr_hazard_wb)
            csr_forward_data_value = WB_csr_write_data;
        else
            csr_forward_data_value = csr_read_data;
    end

endmodule