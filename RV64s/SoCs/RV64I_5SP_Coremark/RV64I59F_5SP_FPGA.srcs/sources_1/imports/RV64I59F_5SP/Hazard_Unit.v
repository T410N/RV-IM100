`include "./opcode.vh"
`include "./alu_src_select.vh"
`include "./trap.vh"

module HazardUnit (
    input clk,
    input reset, 

    input wire trap_done,
    input wire csr_ready,
    input wire standby_mode,
    input wire [2:0] trap_status,
    input wire misaligned_instruction_flush,
    input wire misaligned_memory_flush,
    input wire pth_done_flush,

    input wire [4:0] ID_rs1,
    input wire [4:0] ID_rs2,
    input wire [11:0] ID_raw_imm,
    
    input wire [4:0] MEM_rd,
    input wire [6:0] MEM_opcode,
    input wire [4:0] MEM_rs2,
    input wire MEM_register_write_enable,
    input wire MEM_csr_write_enable,
    input wire [11:0] MEM_csr_write_address,

    input wire [4:0] WB_rd,
    input wire WB_register_write_enable,
    input wire WB_csr_write_enable,
    input wire [11:0] WB_csr_write_address,

    input wire [4:0] EX_rd,
    input wire [6:0] EX_opcode,
    input wire [4:0] EX_rs1,
    input wire [4:0] EX_rs2,
    input wire [11:0] EX_imm,

    input wire EX_csr_write_enable,

    input wire EX_jump,
    input wire branch_prediction_miss,

    input wire [1:0] EX_alu_src_A_select,
    input wire [2:0] EX_alu_src_B_select,

    // Retire stage inputs
    input wire [4:0] retire_rd,
    input wire retire_register_write_enable,

    // to Forward Unit - ALU forwarding
    output reg [1:0] hazard_mem,
    output reg [1:0] hazard_wb,
    output reg [1:0] hazard_retire,
    output wire csr_hazard_mem,
    output wire csr_hazard_wb,

    // to Forward Unit - Store data forwarding
    output wire store_hazard_mem,
    output wire store_hazard_wb,
    output wire store_hazard_wb_to_mem,
    output wire store_hazard_retire,

    output reg IF_ID_flush,
    output reg ID_EX_flush,
    output reg EX_MEM_flush,
    output reg MEM_WB_flush,
    
    output reg IF_ID_stall,
    output reg ID_EX_stall,
    output reg EX_MEM_stall,
    output reg MEM_WB_stall
);

    // Store instruction detection
    wire is_store = (EX_opcode == `OPCODE_STORE);
    wire is_store_mem = (MEM_opcode == `OPCODE_STORE);

    wire uses_rs1 = (EX_alu_src_A_select == `ALU_SRC_A_RD1);
    wire uses_rs2 = (EX_alu_src_B_select == `ALU_SRC_B_RD2);

    // Register ALU hazard detections
    wire mem_hazard_rs1 = uses_rs1 && MEM_register_write_enable && (MEM_rd != 5'd0) && (MEM_rd == EX_rs1);
    wire mem_hazard_rs2 = uses_rs2 && MEM_register_write_enable && (MEM_rd != 5'd0) && (MEM_rd == EX_rs2);
    wire wb_hazard_rs1 = uses_rs1 && WB_register_write_enable && (WB_rd != 5'd0) && (WB_rd == EX_rs1);
    wire wb_hazard_rs2 = uses_rs2 && WB_register_write_enable && (WB_rd != 5'd0) && (WB_rd == EX_rs2);
    wire retire_hazard_rs1 = uses_rs1 && retire_register_write_enable && (retire_rd != 5'd0) && (retire_rd == EX_rs1);
    wire retire_hazard_rs2 = uses_rs2 && retire_register_write_enable && (retire_rd != 5'd0) && (retire_rd == EX_rs2);

    // Store rs2 hazard detections (for store data, not ALU operand)
    wire store_mem_hazard_rs2 = is_store && MEM_register_write_enable && (MEM_rd != 5'd0) && (MEM_rd == EX_rs2);
    wire store_wb_hazard_rs2 = is_store && WB_register_write_enable && (WB_rd != 5'd0) && (WB_rd == EX_rs2);
    wire store_retire_hazard_rs2 = is_store && retire_register_write_enable && (retire_rd != 5'd0) && (retire_rd == EX_rs2);

    // Store instruction rs2 hazard detections (EX stage)
    assign store_hazard_mem = store_mem_hazard_rs2;
    assign store_hazard_wb = store_wb_hazard_rs2 && !store_mem_hazard_rs2;
    assign store_hazard_retire = store_retire_hazard_rs2 && !store_mem_hazard_rs2 && !store_wb_hazard_rs2;

    // WB→MEM store data forwarding: SD in MEM, producer in WB
    assign store_hazard_wb_to_mem = is_store_mem && 
                                    WB_register_write_enable && 
                                    (WB_rd != 5'd0) && 
                                    (WB_rd == MEM_rs2);

    // CSR hazard detection
    assign csr_hazard_mem = MEM_csr_write_enable && (MEM_csr_write_address == EX_imm);
    assign csr_hazard_wb = WB_csr_write_enable && (WB_csr_write_address == EX_imm);

    always @(*) begin
        hazard_mem = 2'b00;
        hazard_wb = 2'b00;
        hazard_retire = 2'b00;
        IF_ID_flush = 1'b0;
        ID_EX_flush = 1'b0;
        EX_MEM_flush = 1'b0;
        MEM_WB_flush = 1'b0;
        
        IF_ID_stall = 1'b0;
        ID_EX_stall = 1'b0;
        EX_MEM_stall = 1'b0;
        MEM_WB_stall = 1'b0;

        // ALU forwarding hazards (priority: MEM > WB > Retire)
        // For Store instructions, rs2 hazard shouldn't trigger ALUsrcB forwarding.
        hazard_mem[0] = mem_hazard_rs1;
        hazard_mem[1] = is_store ? 1'b0 : mem_hazard_rs2;
        
        hazard_wb[0] = wb_hazard_rs1 && !mem_hazard_rs1;
        hazard_wb[1] = is_store ? 1'b0 : (wb_hazard_rs2 && !mem_hazard_rs2);
        
        hazard_retire[0] = retire_hazard_rs1 && !mem_hazard_rs1 && !wb_hazard_rs1;
        hazard_retire[1] = is_store ? 1'b0 : (retire_hazard_rs2 && !mem_hazard_rs2 && !wb_hazard_rs2);

        if (trap_done && (branch_prediction_miss || EX_jump)) begin
            IF_ID_flush = 1'b1;
            ID_EX_flush = 1'b1;
        end

        if (pth_done_flush) begin
            IF_ID_flush = 1'b1;
            ID_EX_flush = 1'b1;
            EX_MEM_flush = 1'b1;
            MEM_WB_flush = 1'b1;
        end

        if (standby_mode) begin
            IF_ID_stall = 1'b1;
            ID_EX_stall = 1'b1;
            EX_MEM_stall = 1'b0;
            MEM_WB_stall = 1'b0;
        end 
        else if (!trap_done || !csr_ready) begin
            IF_ID_stall = 1'b1;
            ID_EX_stall = 1'b1;
            EX_MEM_stall = 1'b1;
            MEM_WB_stall = 1'b1;
        end
    end

endmodule