`include "./opcode.vh"

module ForwardUnit #(
    parameter XLEN = 64
)(
    // Hazard signals from Hazard Unit - ALU forwarding
    input wire [1:0] hazard_mem,
    input wire [1:0] hazard_wb,
    input wire [1:0] hazard_retire,

    // Hazard signals from Hazard Unit - Store data forwarding
    input wire store_hazard_mem,
    input wire store_hazard_wb,
    input wire store_hazard_retire,
    input wire store_hazard_wb_to_mem,

    // MEM stage signals 
    input wire [XLEN-1:0] MEM_imm,
    input wire [XLEN-1:0] MEM_alu_result,       
    input wire [XLEN-1:0] MEM_csr_read_data,
    input wire [XLEN-1:0] byte_enable_logic_register_file_write_data,
    input wire [XLEN-1:0] MEM_pc_plus_4,
    input wire [6:0] MEM_opcode,

    // WB stage signals 
    input wire [XLEN-1:0] WB_imm,
    input wire [XLEN-1:0] WB_alu_result,       
    input wire [XLEN-1:0] WB_csr_read_data,
    input wire [XLEN-1:0] WB_byte_enable_logic_register_file_write_data,
    input wire [XLEN-1:0] WB_pc_plus_4,
    input wire [6:0] WB_opcode,

    // Retire stage signals
    input wire [XLEN-1:0] retire_imm,
    input wire [XLEN-1:0] retire_alu_result,
    input wire [XLEN-1:0] retire_csr_read_data,
    input wire [XLEN-1:0] retire_byte_enable_logic_register_file_write_data,
    input wire [XLEN-1:0] retire_pc_plus_4,
    input wire [6:0] retire_opcode,

    // CSR hazard signals
    input wire csr_hazard_mem,
    input wire csr_hazard_wb,
    input wire [XLEN-1:0] MEM_csr_write_data,
    input wire [XLEN-1:0] WB_csr_write_data,
    input wire [XLEN-1:0] csr_read_data,

    // ALU forwarding signals 
    output wire [XLEN-1:0] alu_forward_source_data_a,
    output wire [XLEN-1:0] alu_forward_source_data_b,
    output wire [1:0] alu_forward_source_select_a,
    output wire [1:0] alu_forward_source_select_b,

    // Store data forwarding outputs
    output wire [XLEN-1:0] store_forward_data,
    output wire store_forward_enable,

    // WB→MEM store data forwarding outputs
    output wire [XLEN-1:0] store_wb_to_mem_forward_data,
    output wire store_wb_to_mem_forward_enable,

    // CSR forward output
    output wire [XLEN-1:0] csr_forward_data
);

    reg [XLEN-1:0] MEM_forward_data_value;
    reg [XLEN-1:0] WB_forward_data_value;
    reg [XLEN-1:0] retire_forward_data_value;
    reg [XLEN-1:0] csr_forward_data_value;

    // ALU source forwarding selection (priority: MEM > WB > Retire)
    // 2'b00: no forwarding, 2'b01: MEM, 2'b10: WB, 2'b11: Retire
    assign alu_forward_source_select_a = 
            hazard_mem[0] ? 2'b01 : 
            hazard_wb[0] ? 2'b10 : 
            hazard_retire[0] ? 2'b11 : 2'b00;

    assign alu_forward_source_select_b = 
            hazard_mem[1] ? 2'b01 :
            hazard_wb[1] ? 2'b10 : 
            hazard_retire[1] ? 2'b11 : 2'b00;

    assign alu_forward_source_data_a = 
            hazard_mem[0] ? MEM_forward_data_value : 
            hazard_wb[0] ? WB_forward_data_value : 
            hazard_retire[0] ? retire_forward_data_value : {XLEN{1'b0}};

    assign alu_forward_source_data_b = 
            hazard_mem[1] ? MEM_forward_data_value : 
            hazard_wb[1] ? WB_forward_data_value : 
            hazard_retire[1] ? retire_forward_data_value : {XLEN{1'b0}};

    // Store data forwarding (EX stage) - priority: MEM > WB > Retire
    assign store_forward_enable = store_hazard_mem || store_hazard_wb || store_hazard_retire;
    assign store_forward_data = store_hazard_mem ? MEM_forward_data_value : 
                                store_hazard_wb ? WB_forward_data_value : 
                                store_hazard_retire ? retire_forward_data_value : {XLEN{1'b0}};

    // WB→MEM store data forwarding (MEM stage)
    assign store_wb_to_mem_forward_enable = store_hazard_wb_to_mem;
    assign store_wb_to_mem_forward_data = WB_forward_data_value;

    assign csr_forward_data = csr_forward_data_value;

    always @(*) begin
        // MEM stage forward data selection
        case (MEM_opcode)
            `OPCODE_LOAD : MEM_forward_data_value = byte_enable_logic_register_file_write_data;
            `OPCODE_ENVIRONMENT : MEM_forward_data_value = MEM_csr_read_data;
            `OPCODE_LUI : MEM_forward_data_value = MEM_imm;
            `OPCODE_JAL : MEM_forward_data_value = MEM_pc_plus_4;
            `OPCODE_JALR : MEM_forward_data_value = MEM_pc_plus_4;
            default: MEM_forward_data_value = MEM_alu_result;
        endcase

        // WB stage forward data selection
        case (WB_opcode)
            `OPCODE_LOAD : WB_forward_data_value = WB_byte_enable_logic_register_file_write_data;
            `OPCODE_ENVIRONMENT : WB_forward_data_value = WB_csr_read_data;
            `OPCODE_LUI : WB_forward_data_value = WB_imm;
            `OPCODE_JAL : WB_forward_data_value = WB_pc_plus_4;
            `OPCODE_JALR : WB_forward_data_value = WB_pc_plus_4;
            default: WB_forward_data_value = WB_alu_result;
        endcase

        // Retire stage forward data selection
        case (retire_opcode)
            `OPCODE_LOAD : retire_forward_data_value = retire_byte_enable_logic_register_file_write_data;
            `OPCODE_ENVIRONMENT : retire_forward_data_value = retire_csr_read_data;
            `OPCODE_LUI : retire_forward_data_value = retire_imm;
            `OPCODE_JAL : retire_forward_data_value = retire_pc_plus_4;
            `OPCODE_JALR : retire_forward_data_value = retire_pc_plus_4;
            default: retire_forward_data_value = retire_alu_result;
        endcase

        // CSR Forwarding
        if (csr_hazard_mem) begin
            csr_forward_data_value = MEM_csr_write_data;
        end 
        else if (csr_hazard_wb) begin
            csr_forward_data_value = WB_csr_write_data;
        end 
        else begin
            csr_forward_data_value = csr_read_data;
        end
    end

endmodule