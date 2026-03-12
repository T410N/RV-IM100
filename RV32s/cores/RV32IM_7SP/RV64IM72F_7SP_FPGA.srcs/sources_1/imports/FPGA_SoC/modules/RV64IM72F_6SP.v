`include "./alu_src_select.vh"
`include "./rf_wd_select.vh"
`include "./alu_op.vh"

module RV32IM72F7SP #(
    parameter XLEN = 32
)(
    input clk,
    input clk_enable,
    input reset,
    input UART_busy,
    
    output wire [31:0] retire_instruction,
    output wire [XLEN-1:0] MMIO_data_memory_write_data,
    output wire [XLEN-1:0] MMIO_data_memory_address,
    output wire MMIO_data_memory_write_enable
);

    // Program Counter and  PC Plus 4
    wire [XLEN-1:0] pc;
    wire [XLEN-1:0] pc_plus_4_signal;
    wire [XLEN-1:0] next_pc;
    
    // Instruction Memory and Debug Interface
    wire [31:0] im_instruction;
    wire [31:0] dbg_instruction = 32'b00000001011110110000110000110011; //add x24 = x22 + x23 = FFFF_FFBC + ABAD_BB02 = ABADBABE
    reg [31:0] instruction;
    wire [XLEN-1:0] IF_imm;
    wire [6:0] IF_opcode;

    // ROM bypass signals (MEM stage instruction memory access)
    wire [XLEN-1:0] rom_read_data;

    assign IF_imm = {{20{IO_instruction[31]}}, IO_instruction[7], IO_instruction[30:25], IO_instruction[11:8], 1'b0};
    assign IF_opcode = (IO_instruction[6:0]);

    // Instruction Decoder
    wire [6:0] opcode;
    wire [2:0] funct3;
    wire [6:0] funct7;
    wire [4:0] rs1;
    wire [4:0] rs2;
	wire [4:0] rd;
    wire [19:0] raw_imm;
    
    // Immediate Generator
    wire [XLEN-1:0] imm;

    // Control Unit
    wire pc_stall;
    wire jump;
	wire branch;
	wire [1:0] alu_src_A_select;
	wire [2:0] alu_src_B_select;
    wire memory_read;
	wire memory_write;
	wire register_file_write;
	wire [2:0] register_file_write_data_select;
    wire cu_csr_write_enable;

    // Branch Logic and Branch Predictor
    wire branch_taken;
    wire [XLEN-1:0] branch_target;
    wire [XLEN-1:0] branch_target_actual;

    // Register File
    reg [XLEN-1:0] register_file_write_data;
    
    // Register File
    wire [XLEN-1:0] read_data1;
    wire [XLEN-1:0] read_data2;

    // ALU Controller
    wire [4:0] alu_op;
    wire input_size_word;

    // ALUsrcA, srcB MUX
    reg [XLEN-1:0] src_A;
    reg [XLEN-1:0] src_B;

    // ALU
    wire [XLEN-1:0] alu_result;
    wire alu_zero;

    // Divider Unit
    wire div_start;
    wire div_busy;

    // Multiplier Unit
    wire mul_start;
    wire mul_busy;
	
    // Data Memory and Byte Enable Logic
    wire [XLEN-1:0] data_memory_read_data;
	wire [XLEN-1:0] byte_enable_logic_register_file_write_data;
    wire [XLEN-1:0] data_memory_write_data;
    wire [3:0] write_mask;

    // CSR File
    wire csr_write_enable;
    reg [11:0] csr_read_address;
    reg [11:0] csr_write_address;
    reg [XLEN-1:0] csr_write_data;
    wire [XLEN-1:0] csr_read_out;
    wire csr_ready;
    reg instruction_retired;

    // Exception_Detector
    wire trapped;
    wire [2:0]  trap_status;

    // Trap Controller
    wire trap_done;
    wire debug_mode;
    wire tc_csr_write_enable;
    wire [XLEN-1:0] trap_target;
    wire [11:0] csr_trap_address;
    wire [XLEN-1:0] csr_trap_write_data;
    wire pth_done_flush;
    wire standby_mode;
    
    // IF_IO_Register
    wire [XLEN-1:0] IO_pc;
    wire [XLEN-1:0] IO_pc_plus_4;
    wire [31:0] IO_instruction;

    // IO_ID_Register
    wire [XLEN-1:0] ID_pc;
    wire [XLEN-1:0] ID_pc_plus_4;
    wire [31:0] ID_instruction;
    wire ID_branch_estimation;

    // ID_EX_Register
    wire [XLEN-1:0] EX_pc;
    wire [XLEN-1:0] EX_pc_plus_4;
    wire EX_branch_estimation;
    wire [31:0] EX_instruction;
    
    // EX_EX2_Register
    wire [XLEN-1:0] EX2_pc;
    wire [XLEN-1:0] EX2_pc_plus_4;
    wire [31:0] EX2_instruction;

    wire EX2_memory_read;
    wire EX2_memory_write;

    wire [2:0] EX2_register_file_write_data_select;
    wire EX2_register_write_enable;
    wire EX2_csr_write_enable;

    wire [6:0] EX2_opcode;
    wire [2:0] EX2_funct3;
    wire [4:0] EX2_rs1;
    wire [4:0] EX2_rs2;
    wire [4:0] EX2_rd;

    wire [XLEN-1:0] EX2_read_data1;
    wire [XLEN-1:0] EX2_read_data2;
    wire [XLEN-1:0] EX2_imm;
    wire [19:0] EX2_raw_imm;

    wire [XLEN-1:0] EX2_csr_read_data;
    wire [XLEN-1:0] EX2_alu_result;

    wire EX2_branch;
    wire EX2_branch_estimation;
    wire EX2_alu_zero;
    

    // EX_MEM_Register
    wire EX_jump;
    wire EX_memory_read;
    wire EX_memory_write;
    wire [2:0] EX_register_file_write_data_select;
    wire EX_register_write_enable;
    wire EX_csr_write_enable;
    wire EX_branch;
    wire [1:0] EX_alu_src_A_select;
    wire [2:0] EX_alu_src_B_select;
    wire [6:0] EX_opcode;
    wire [2:0] EX_funct3;
    wire [6:0] EX_funct7;
    wire [4:0] EX_rd;
    wire [19:0] EX_raw_imm;
    wire [XLEN-1:0] EX_read_data1;
    wire [XLEN-1:0] EX_read_data2;
    wire [4:0] EX_rs1;
    wire [4:0] EX_rs2;
    wire [XLEN-1:0] EX_imm;
    wire [XLEN-1:0] EX_csr_read_data;

    wire [XLEN-1:0] MEM_pc;
    wire [XLEN-1:0] MEM_pc_plus_4;
    wire [31:0] MEM_instruction;

    wire MEM_memory_read;
    wire MEM_memory_write;
    wire [2:0] MEM_register_file_write_data_select;
    wire MEM_register_write_enable;
    wire MEM_csr_write_enable;
    wire [6:0] MEM_opcode;
    wire [2:0] MEM_funct3;
    wire [4:0] MEM_rs1;
    wire [4:0] MEM_rs2;
    wire [4:0] MEM_rd;
    wire [XLEN-1:0] MEM_read_data2;
    wire [XLEN-1:0] MEM_imm;
    wire [19:0] MEM_raw_imm;
    wire [XLEN-1:0] MEM_csr_read_data;
    wire [XLEN-1:0] MEM_alu_result;
    wire [XLEN-1:0] MEM_data_memory_write_data;

    wire [XLEN-1:0] WB_pc;
    wire [XLEN-1:0] WB_pc_plus_4;
    wire [31:0] WB_instruction;
    wire [6:0] WB_opcode;

    // MEM_WB_Register
    wire MEM_WB_flush;
    wire [2:0] WB_register_file_write_data_select;
    wire [XLEN-1:0] WB_imm;
    wire [19:0] WB_raw_imm;
    wire [XLEN-1:0] WB_csr_read_data;
    wire [XLEN-1:0] WB_alu_result;
    wire WB_register_write_enable;
    wire WB_csr_write_enable;
    wire [4:0] WB_rs1;
    wire [4:0] WB_rd;

    wire [XLEN-1:0] WB_byte_enable_logic_register_file_write_data;
    wire [XLEN-1:0] WB_data_memory_write_data;
    wire WB_memory_write;

    // Retire stage registers
    reg [4:0] retire_rd;
    reg retire_register_write_enable;
    reg [6:0] retire_opcode;
    reg [XLEN-1:0] retire_alu_result;
    reg [XLEN-1:0] retire_imm;
    reg [XLEN-1:0] retire_pc_plus_4;
    reg [XLEN-1:0] retire_csr_read_data;
    reg [XLEN-1:0] retire_byte_enable_logic_register_file_write_data;

    // Hazard Unit
    wire IF_IO_flush;
    wire IO_ID_flush;
    wire ID_EX_flush;
    wire EX_EX2_flush;
    wire EX_MEM_flush;
    wire IF_IO_stall;
    wire IO_ID_stall;
    wire ID_EX_stall;
    wire EX_EX2_stall;
    wire EX_MEM_stall;
    wire MEM_WB_stall;
    wire csr_hazard_mem;
    wire csr_hazard_wb;
    wire store_hazard_ex2;
    wire store_hazard_mem;
    wire store_hazard_wb;
    wire store_hazard_retire;
    wire store_hazard_wb_to_mem;
    wire load_use_hazard;
    wire misaligned_instruction_flush;
    wire misaligned_memory_flush;

    // Forward Unit
    wire [1:0] hazard_ex2;
    wire [1:0] hazard_mem;
    wire [1:0] hazard_wb;
    wire [1:0] hazard_retire;
    wire [XLEN-1:0] csr_forward_data;
    wire [XLEN-1:0] alu_forward_source_data_a;
    wire [XLEN-1:0] alu_forward_source_data_b;
    wire [2:0] alu_forward_source_select_a;
    wire [2:0] alu_forward_source_select_b;
    reg [XLEN-1:0] alu_normal_source_a;
    reg [XLEN-1:0] alu_normal_source_b;

    wire [XLEN-1:0] store_forward_data;
    wire store_forward_enable;
    wire [XLEN-1:0] EX_read_data2_MUX;
    assign EX_read_data2_MUX = store_forward_enable ? store_forward_data : EX_read_data2;
    

    // WB->MEM store data forwarding
    wire [XLEN-1:0] store_wb_to_mem_forward_data;
    wire store_wb_to_mem_forward_enable;
    wire [XLEN-1:0] MEM_read_data2_MUX;
    assign MEM_read_data2_MUX = store_wb_to_mem_forward_enable ? store_wb_to_mem_forward_data : MEM_read_data2;

    // Branch Predictor
    wire branch_estimation;
    wire branch_prediction_miss;
    
    wire [31:0] writeback_instruction = WB_instruction;
    assign retire_instruction = writeback_instruction;

    wire csr_write_enable_source;
    assign csr_write_enable_source = tc_csr_write_enable ? tc_csr_write_enable : WB_csr_write_enable;

    // IO signals for MMIO Interface
    assign MMIO_data_memory_write_data = data_memory_write_data;
    assign MMIO_data_memory_write_enable = MEM_memory_write;
    assign MMIO_data_memory_address = MEM_alu_result;

    // MMIO Interface logics
    wire mmio_uart_status_hit;
    assign mmio_uart_status_hit = (MEM_alu_result == 32'h1001_0004);
    wire [XLEN-1:0] data_memory_read_data_muxed;
    assign data_memory_read_data_muxed = mmio_uart_status_hit ? {31'b0, UART_busy} : data_memory_read_data;

    ALU alu (
        .clk(clk),
        .clk_enable(clk_enable),
        .reset(reset),
        .src_A(src_A),
        .src_B(src_B),
        .alu_op(alu_op),
        .div_start(div_start),
        .div_busy(div_busy),
        .mul_start(mul_start),
        .mul_busy(mul_busy),

        .alu_result(alu_result),
        .alu_zero(alu_zero)
    );

    ALUController alu_controller (
        .clk(clk),
        .clk_enable(clk_enable),
        .reset(reset),
        .opcode(EX_opcode),
	    .funct3(EX_funct3),
        .funct7_5(EX_funct7[5]),
        .funct7_0(EX_funct7[0]),
        .imm_10(EX_imm[10]),
        .div_busy(div_busy),
        .mul_busy(mul_busy),
        .load_use_hazard(load_use_hazard),
        .ex_kill(ID_EX_flush),
        
        .div_start(div_start),
        .mul_start(mul_start),
        .alu_op(alu_op)
    );

    BranchLogic branch_logic (
        .branch(EX2_branch),
        .branch_estimation(EX2_branch_estimation),
        .funct3(EX2_funct3),
        .pc(EX2_pc),
        .imm(EX2_imm),

        // ALU results from EX2 stage (with forwarding already applied in EX stage)
        .alu_zero(EX2_alu_zero),
        .alu_result(EX2_alu_result),

        .branch_taken(branch_taken),
        .branch_prediction_miss(branch_prediction_miss),
        .branch_target_actual(branch_target_actual)
    );

    BranchPredictor #(.XLEN(XLEN)) branch_predictor(
        .clk(clk),
        .clk_enable(clk_enable),
        .reset(reset),
        .IF_opcode(IF_opcode),
        .IF_pc (IO_pc),
        .IF_imm (IF_imm),
        .EX_branch(EX2_branch),
        .EX_branch_taken (branch_taken),

        .branch_estimation (branch_estimation),
        .branch_target (branch_target)
    );

    ByteEnableLogic byte_enable_logic (
        .memory_read(MEM_memory_read),
        .memory_write(MEM_memory_write),
        .funct3(MEM_funct3),
	    .register_file_read_data(MEM_read_data2_MUX),
	    .data_memory_read_data(data_memory_read_data_muxed),
	    .address(MEM_alu_result[2:0]),
	
	    .register_file_write_data(byte_enable_logic_register_file_write_data),
	    .data_memory_write_data(data_memory_write_data),
        .write_mask(write_mask)
    );

    ControlUnit control_unit (
        .write_done(1'b1),
	    .opcode(opcode),
	    .funct3(funct3),
        .trap_done(trap_done),
        .csr_ready(csr_ready),
        .IF_IO_stall(IF_IO_stall),

        .pc_stall(pc_stall),
        .jump(jump),
	    .branch(branch),
	    .alu_src_A_select(alu_src_A_select),
	    .alu_src_B_select(alu_src_B_select),
	    .register_file_write(register_file_write),
	    .register_file_write_data_select(register_file_write_data_select),
	    .memory_read(memory_read),
	    .memory_write(memory_write),
        .csr_write_enable(cu_csr_write_enable)
    );

    CSRFile #(.XLEN(XLEN)) csr_file (
        .clk(clk),
        .clk_enable(clk_enable),
        .reset(reset),
        .trapped(trapped),
        .csr_write_enable(csr_write_enable_source),
        .csr_read_address(csr_read_address),
        .csr_write_address(csr_write_address),
        .csr_write_data(csr_write_data),
        .instruction_retired(instruction_retired),

        .csr_read_out(csr_read_out),
        .csr_ready(csr_ready) 
    );

    DataMemory data_memory (
        .clk(clk),
        .clk_enable(clk_enable),
        .write_enable(MEM_memory_write && !mmio_uart_status_hit),
        .address(MEM_alu_result),
        .write_data(data_memory_write_data),
        .write_mask(write_mask),
        .rom_read_data(rom_read_data_safe),
        .rom_address(),

        .read_data(data_memory_read_data)
    );

    ExceptionDetector exception_detector (
        .clk(clk),
        .clk_enable(clk_enable),
        .reset(reset),
        .ID_opcode(opcode),
        .ID_funct3(funct3),
        .EX_opcode(EX_opcode),
        .EX_funct3(EX_funct3),
        .EX2_opcode(EX2_opcode),
        .EX2_funct3(EX2_funct3),
        .MEM_opcode(MEM_opcode),
        .MEM_funct3(MEM_funct3),
        .raw_imm(raw_imm[11:0]),
        .EX_raw_imm(EX_raw_imm[11:0]),
        .EX2_raw_imm(EX2_raw_imm[11:0]),
        .csr_write_enable(cu_csr_write_enable),
        .alu_result(alu_result[1:0]),
        .EX2_alu_result(EX2_alu_result[1:0]),
        .MEM_alu_result(MEM_alu_result[1:0]),
        .branch_target_lsbs(branch_target[1:0]),
        .branch_estimation(branch_estimation),
        .branch_prediction_miss(branch_prediction_miss),

        .trapped(trapped),
        .trap_status(trap_status)
    );

    ForwardUnit forward_unit (
        .hazard_ex2(hazard_ex2),
        .hazard_mem(hazard_mem),
        .hazard_wb(hazard_wb),
        .hazard_retire(hazard_retire),
        .EX2_imm(EX2_imm),
        .EX2_alu_result(EX2_alu_result),
        .EX2_csr_read_data(EX2_csr_read_data),
        .EX2_pc_plus_4(EX2_pc_plus_4),
        .EX2_opcode(EX2_opcode),
        .MEM_imm(MEM_imm),
        .MEM_alu_result(MEM_alu_result),
        .MEM_csr_read_data(MEM_csr_read_data),
        .byte_enable_logic_register_file_write_data(byte_enable_logic_register_file_write_data),
        .MEM_pc_plus_4(MEM_pc_plus_4),
        .MEM_opcode(MEM_opcode),
        .WB_opcode(WB_opcode),
        .WB_imm(WB_imm),
        .WB_alu_result(WB_alu_result),
        .WB_csr_read_data(WB_csr_read_data),
        .WB_byte_enable_logic_register_file_write_data(WB_byte_enable_logic_register_file_write_data),
        .WB_pc_plus_4(WB_pc_plus_4),

        // Retire stage inputs
        .retire_opcode(retire_opcode),
        .retire_imm(retire_imm),
        .retire_alu_result(retire_alu_result),
        .retire_csr_read_data(retire_csr_read_data),
        .retire_byte_enable_logic_register_file_write_data(retire_byte_enable_logic_register_file_write_data),
        .retire_pc_plus_4(retire_pc_plus_4),

        .alu_forward_source_data_a(alu_forward_source_data_a),
        .alu_forward_source_data_b(alu_forward_source_data_b),
        .alu_forward_source_select_a(alu_forward_source_select_a),
        .alu_forward_source_select_b(alu_forward_source_select_b),

        .store_hazard_ex2(store_hazard_ex2),
        .store_hazard_mem(store_hazard_mem),
        .store_hazard_wb(store_hazard_wb),
        .store_hazard_retire(store_hazard_retire),
        .store_forward_data(store_forward_data),
        .store_forward_enable(store_forward_enable),

        .store_hazard_wb_to_mem(store_hazard_wb_to_mem),
        .store_wb_to_mem_forward_data(store_wb_to_mem_forward_data),
        .store_wb_to_mem_forward_enable(store_wb_to_mem_forward_enable),

        .csr_hazard_mem(csr_hazard_mem),
        .csr_hazard_wb(csr_hazard_wb),
        .MEM_csr_write_data(MEM_alu_result),
        .WB_csr_write_data(WB_alu_result),
        .csr_read_data(csr_read_out),

        .csr_forward_data(csr_forward_data)
    );

    HazardUnit hazard_unit (
        .reset(reset),
        .trap_done(trap_done),
        .standby_mode(standby_mode),
        .div_start(div_start),
        .div_busy(div_busy),
        .mul_start(mul_start),
        .mul_busy(mul_busy),
        .trap_status(trap_status),
        .misaligned_instruction_flush(misaligned_instruction_flush),
        .misaligned_memory_flush(misaligned_memory_flush),
        .pth_done_flush(pth_done_flush),
        .csr_ready(csr_ready),
        .ID_rs1(rs1),
        .ID_rs2(rs2),
        .ID_raw_imm(raw_imm[11:0]),
        .EX_csr_write_enable(EX_csr_write_enable),
        .EX2_rd(EX2_rd),
        .EX2_opcode(EX2_opcode),
        .EX2_rs1(EX2_rs1),
        .EX2_rs2(EX2_rs2),
        .EX2_branch(EX2_branch),
        .EX2_register_write_enable(EX2_register_write_enable),
        .MEM_rd(MEM_rd),
        .MEM_opcode(MEM_opcode),
        .MEM_rs2(MEM_rs2),
        .MEM_register_write_enable(MEM_register_write_enable),
        .MEM_csr_write_enable(MEM_csr_write_enable),
        .MEM_csr_write_address(MEM_raw_imm[11:0]),
        .WB_rd(WB_rd),
        .WB_register_write_enable(WB_register_write_enable),
        .WB_csr_write_enable(WB_csr_write_enable),
        .WB_csr_write_address(WB_raw_imm[11:0]),
        .EX_rs1(EX_rs1),
        .EX_rs2(EX_rs2),
        .EX_rd(EX_rd),
        .EX_opcode(EX_opcode),
        .EX_imm(EX_raw_imm[11:0]),
        .branch_prediction_miss(branch_prediction_miss),
        .EX_jump(EX_jump),
        .EX_alu_src_A_select(EX_alu_src_A_select),
        .EX_alu_src_B_select(EX_alu_src_B_select),

        // Retire stage inputs
        .retire_rd(retire_rd),
        .retire_register_write_enable(retire_register_write_enable),

        .hazard_ex2(hazard_ex2),
        .hazard_mem(hazard_mem),
        .hazard_wb(hazard_wb),
        .hazard_retire(hazard_retire),
        .csr_hazard_mem(csr_hazard_mem),
        .csr_hazard_wb(csr_hazard_wb),
        .store_hazard_ex2(store_hazard_ex2),
        .store_hazard_mem(store_hazard_mem),
        .store_hazard_wb(store_hazard_wb),
        .store_hazard_retire(store_hazard_retire),
        .store_hazard_wb_to_mem(store_hazard_wb_to_mem),
        .load_use_hazard(load_use_hazard),

        .IF_IO_flush(IF_IO_flush),
        .IO_ID_flush(IO_ID_flush),
        .ID_EX_flush(ID_EX_flush),
        .EX_EX2_flush(EX_EX2_flush),
        .EX_MEM_flush(EX_MEM_flush),
        .MEM_WB_flush(MEM_WB_flush),
        .IF_IO_stall(IF_IO_stall),
        .IO_ID_stall(IO_ID_stall),
        .ID_EX_stall(ID_EX_stall),
        .EX_EX2_stall(EX_EX2_stall),
        .EX_MEM_stall(EX_MEM_stall),
        .MEM_WB_stall(MEM_WB_stall)
    );


    ImmediateGenerator immediate_generator (
        .raw_imm(raw_imm),
        .opcode(opcode),
        .imm(imm)
    );

    InstructionDecoder instruction_decoder (
        .instruction(ID_instruction),
        .opcode(opcode),
	    .funct3(funct3),
	    .funct7(funct7),
	    .rs1(rs1),
	    .rs2(rs2),
	    .rd(rd),
	    .raw_imm(raw_imm)
    );

    InstructionMemory instruction_memory (
        .clk(clk),
        .clk_enable(clk_enable),
        .pc_stall(pc_stall),
        .pc(pc),
        .instruction(im_instruction),
        .rom_address(EX2_alu_result),
        .rom_read_data(rom_read_data)
    );

    ProgramCounter program_counter (
        .clk(clk),
        .clk_enable(clk_enable),
        .reset(reset),
        .next_pc(next_pc),
        .pc(pc)
    );

    PCPlus4 pc_plus_4 (
        .pc(pc),
        .pc_plus_4(pc_plus_4_signal)
    );

    PCController pc_controller (
        .jump(EX_jump),
        .branch_estimation(branch_estimation),
        .branch_prediction_miss(branch_prediction_miss),
        .trapped(trapped),
	    .pc(pc),
        .jump_target(alu_result),
        .branch_target(branch_target),
        .branch_target_actual(branch_target_actual),
	    .trap_target(trap_target),
        .pc_stall(pc_stall),
	    .next_pc(next_pc)
    );

    RegisterFile register_file (
        .clk(clk),
        .clk_enable(clk_enable),
        .read_reg1(rs1),
        .read_reg2(rs2),
        .write_reg(WB_rd),
        .write_data(register_file_write_data),
        .write_enable(WB_register_write_enable),
	
        .read_data1(read_data1),
        .read_data2(read_data2)
    );

    TrapController #(.XLEN(XLEN))trap_controller (
        .clk(clk),
        .clk_enable(clk_enable),
        .reset(reset),
        .trap_status(trap_status),
        .ID_pc(ID_pc),
        .EX_pc(EX_pc),
        .EX2_pc(EX2_pc),
        .MEM_pc(MEM_pc),
        .WB_pc(WB_pc),
        .csr_read_data(csr_read_out),

        .debug_mode(debug_mode),
        .trap_target(trap_target),
        .trap_done(trap_done),
        .misaligned_instruction_flush(misaligned_instruction_flush),
        .misaligned_memory_flush(misaligned_memory_flush),
        .pth_done_flush(pth_done_flush),
        .standby_mode(standby_mode),
        .csr_write_enable(tc_csr_write_enable),
        .csr_trap_address(csr_trap_address),
        .csr_trap_write_data(csr_trap_write_data)
    );

    IF_IO_Register #(.XLEN(XLEN)) if_io_register (
        .clk(clk),
        .clk_enable(clk_enable),
        .flush(IF_IO_flush),
        .IF_IO_stall(IF_IO_stall),
        .branch_estimation(branch_estimation),
        .load_use_hazard(load_use_hazard),
        .jump(EX_jump),

        .IF_pc(instruction_pc),
        .IF_pc_plus_4(instruction_pc_plus_4),
        .IF_instruction(instruction),

        .IO_pc(IO_pc),
        .IO_pc_plus_4(IO_pc_plus_4),
        .IO_instruction(IO_instruction),

        .ID_opcode(opcode),
        .ID_funct7(funct7)
    );

    IO_ID_Register #(.XLEN(XLEN)) io_id_register (
        .clk(clk),
        .clk_enable(clk_enable),
        .flush(IO_ID_flush),
        .IO_ID_stall(IO_ID_stall),

        .IO_pc(IO_pc),
        .IO_pc_plus_4(IO_pc_plus_4),
        .IO_instruction(IO_instruction),
        .branch_estimation(branch_estimation),

        .ID_pc(ID_pc),
        .ID_pc_plus_4(ID_pc_plus_4),
        .ID_instruction(ID_instruction),
        .ID_branch_estimation(ID_branch_estimation)
    );

    ID_EX_Register #(.XLEN(XLEN)) id_ex_register (
        .clk(clk),
        .clk_enable(clk_enable),
        .flush(ID_EX_flush),
        .ID_EX_stall(ID_EX_stall),
        
        .ID_pc(ID_pc),
        .ID_pc_plus_4(ID_pc_plus_4),
        .ID_branch_estimation(ID_branch_estimation),
        .ID_instruction(ID_instruction),

        .ID_jump(jump),
        .ID_branch(branch),
        .ID_alu_src_A_select(alu_src_A_select),
        .ID_alu_src_B_select(alu_src_B_select),
        .ID_memory_read(memory_read),
        .ID_memory_write(memory_write),
        .ID_register_file_write_data_select(register_file_write_data_select),
        .ID_register_write_enable(register_file_write),
        .ID_csr_write_enable(cu_csr_write_enable),
        .ID_opcode(opcode), 
        .ID_funct3(funct3),
        .ID_funct7(funct7),
        .ID_rd(rd),
        .ID_raw_imm(raw_imm),
        .ID_read_data1(read_data1),
        .ID_read_data2(read_data2),
        .ID_rs1(rs1),
        .ID_rs2(rs2),
        .ID_imm(imm),
        .ID_csr_read_data(csr_read_out),

        .EX_pc(EX_pc),
        .EX_pc_plus_4(EX_pc_plus_4),
        .EX_branch_estimation(EX_branch_estimation),
        .EX_instruction(EX_instruction),

        .EX_jump(EX_jump),
        .EX_branch(EX_branch),
        .EX_alu_src_A_select(EX_alu_src_A_select),
        .EX_alu_src_B_select(EX_alu_src_B_select),
        .EX_memory_read(EX_memory_read),
        .EX_memory_write(EX_memory_write),
        .EX_register_file_write_data_select(EX_register_file_write_data_select),
        .EX_register_write_enable(EX_register_write_enable),
        .EX_csr_write_enable(EX_csr_write_enable),
        .EX_opcode(EX_opcode),
        .EX_funct3(EX_funct3),
        .EX_funct7(EX_funct7),
        .EX_rd(EX_rd),
        .EX_raw_imm(EX_raw_imm),
        .EX_read_data1(EX_read_data1),
        .EX_read_data2(EX_read_data2),
        .EX_rs1(EX_rs1),
        .EX_rs2(EX_rs2),
        .EX_imm(EX_imm),
        .EX_csr_read_data(EX_csr_read_data)
    );
    
    EX_EX2_Register #(.XLEN(XLEN)) ex_ex2_register (
        .clk(clk),
        .clk_enable(clk_enable),
        .flush(EX_EX2_flush),
        .EX_EX2_stall(EX_EX2_stall),

        // signals from EX stage
        .EX_pc(EX_pc),
        .EX_pc_plus_4(EX_pc_plus_4),
        .EX_instruction(EX_instruction),

        .EX_register_file_write_data_select(EX_register_file_write_data_select),
        .EX_register_write_enable(EX_register_write_enable),

        .EX_memory_read(EX_memory_read),
        .EX_memory_write(EX_memory_write),

        .EX_csr_write_enable(EX_csr_write_enable),

        .EX_opcode(EX_opcode),
        .EX_funct3(EX_funct3),
        .EX_rs1(EX_rs1),
        .EX_rs2(EX_rs2),
        .EX_rd(EX_rd),

        .EX_read_data1(EX_read_data1),
        .EX_read_data2(EX_read_data2_MUX),

        .EX_imm(EX_imm),
        .EX_raw_imm(EX_raw_imm),

        .EX_csr_read_data(EX_csr_read_data),
        .EX_alu_result(alu_result),

        .EX_branch(EX_branch),
        .EX_branch_estimation(EX_branch_estimation),
        .EX_alu_zero(alu_zero),

        // outputs to EX2 stage
        .EX2_pc(EX2_pc),
        .EX2_pc_plus_4(EX2_pc_plus_4),
        .EX2_instruction(EX2_instruction),

        .EX2_memory_read(EX2_memory_read),
        .EX2_memory_write(EX2_memory_write),

        .EX2_register_file_write_data_select(EX2_register_file_write_data_select),
        .EX2_register_write_enable(EX2_register_write_enable),

        .EX2_csr_write_enable(EX2_csr_write_enable),

        .EX2_opcode(EX2_opcode),
        .EX2_funct3(EX2_funct3),
        .EX2_rs1(EX2_rs1),
        .EX2_rs2(EX2_rs2),
        .EX2_rd(EX2_rd),

        .EX2_read_data1(EX2_read_data1),
        .EX2_read_data2(EX2_read_data2),

        .EX2_imm(EX2_imm),
        .EX2_raw_imm(EX2_raw_imm),

        .EX2_csr_read_data(EX2_csr_read_data),
        .EX2_alu_result(EX2_alu_result),

        .EX2_branch(EX2_branch),
        .EX2_branch_estimation(EX2_branch_estimation),
        .EX2_alu_zero(EX2_alu_zero)
    );


    EX_MEM_Register #(.XLEN(XLEN)) ex_mem_register (
        .clk(clk),
        .clk_enable(clk_enable),
        .flush(EX_MEM_flush),
        .EX_MEM_stall(EX_MEM_stall),

        .EX_pc(EX2_pc),
        .EX_pc_plus_4(EX2_pc_plus_4),
        .EX_instruction(EX2_instruction),

        .EX_memory_read(EX2_memory_read),
        .EX_memory_write(EX2_memory_write),
        .EX_register_file_write_data_select(EX2_register_file_write_data_select),
        .EX_register_write_enable(EX2_register_write_enable),
        .EX_csr_write_enable(EX2_csr_write_enable),
        .EX_opcode(EX2_opcode),
        .EX_funct3(EX2_funct3),
        .EX_rs1(EX2_rs1),
        .EX_rs2(EX2_rs2),
        .EX_rd(EX2_rd),
        .EX_raw_imm(EX2_raw_imm),
        .EX_read_data2(EX2_read_data2),
        .EX_imm(EX2_imm),
        .EX_csr_read_data(EX2_csr_read_data),

        .EX_alu_result(EX2_alu_result),

        .MEM_pc(MEM_pc),
        .MEM_pc_plus_4(MEM_pc_plus_4),
        .MEM_instruction(MEM_instruction),
        .MEM_memory_read(MEM_memory_read),
        .MEM_memory_write(MEM_memory_write),
        .MEM_register_file_write_data_select(MEM_register_file_write_data_select),
        .MEM_register_write_enable(MEM_register_write_enable),
        .MEM_csr_write_enable(MEM_csr_write_enable),
        .MEM_opcode(MEM_opcode),
        .MEM_funct3(MEM_funct3),
        .MEM_rs1(MEM_rs1),
        .MEM_rs2(MEM_rs2),
        .MEM_rd(MEM_rd),
        .MEM_raw_imm(MEM_raw_imm),
        .MEM_read_data2(MEM_read_data2),
        .MEM_imm(MEM_imm),
        .MEM_csr_read_data(MEM_csr_read_data),
        .MEM_alu_result(MEM_alu_result)
    );

    MEM_WB_Register #(.XLEN(XLEN)) mem_wb_register (
        .clk(clk),
        .clk_enable(clk_enable),
        .MEM_WB_stall(MEM_WB_stall),
        .flush(MEM_WB_flush),

        .MEM_pc(MEM_pc),
        .MEM_pc_plus_4(MEM_pc_plus_4),
        .MEM_instruction(MEM_instruction),

        .MEM_register_file_write_data_select(MEM_register_file_write_data_select),
        .MEM_imm(MEM_imm),
        .MEM_csr_read_data(MEM_csr_read_data),
        .MEM_alu_result(MEM_alu_result),
        .MEM_register_write_enable(MEM_register_write_enable),
        .MEM_csr_write_enable(MEM_csr_write_enable),
        .MEM_rs1(MEM_rs1),
        .MEM_rd(MEM_rd),
        .MEM_raw_imm(MEM_raw_imm),
        .MEM_opcode(MEM_opcode),

        .MEM_byte_enable_logic_register_file_write_data(byte_enable_logic_register_file_write_data),
        .MEM_data_memory_write_data(data_memory_write_data),
        .MEM_memory_write(MEM_memory_write),

        .WB_pc(WB_pc),
        .WB_pc_plus_4(WB_pc_plus_4),
        .WB_instruction(WB_instruction),
        .WB_register_file_write_data_select(WB_register_file_write_data_select),
        .WB_imm(WB_imm),
        .WB_csr_read_data(WB_csr_read_data),
        .WB_alu_result(WB_alu_result),
        .WB_register_write_enable(WB_register_write_enable),
        .WB_csr_write_enable(WB_csr_write_enable),
        .WB_rs1(WB_rs1),
        .WB_rd(WB_rd),
        .WB_raw_imm(WB_raw_imm),
        .WB_opcode(WB_opcode),
        .WB_byte_enable_logic_register_file_write_data(WB_byte_enable_logic_register_file_write_data),
        .WB_data_memory_write_data(WB_data_memory_write_data),
        .WB_memory_write(WB_memory_write)
    );

    // Align PC with synchronous instruction memory output
    reg [XLEN-1:0] instruction_pc;
    wire [XLEN-1:0] instruction_pc_plus_4 = instruction_pc + 4;
    always @(posedge clk or posedge reset) begin
        if (reset) begin
            instruction_pc <= {XLEN{1'b0}};
        end
        else if (clk_enable && !pc_stall) begin
            instruction_pc <= pc;
        end
    end
    
    reg [XLEN-1:0] rom_read_data_held;
    wire [XLEN-1:0] rom_read_data_safe;
    reg EX_EX2_stall_reg;
    
    always @(posedge clk or posedge reset) begin
        if (reset) begin
            EX_EX2_stall_reg <= 1'b0;
        end
        else if (EX_EX2_stall) begin
            EX_EX2_stall_reg <= 1'b1;
        end 
        else if (!EX_EX2_stall) begin
            EX_EX2_stall_reg <= 1'b0;
        end
    end
    
    always @(posedge clk or posedge reset) begin
        if (reset) begin
            rom_read_data_held <= {XLEN{1'b0}};
        end
        else if (clk_enable && !EX_EX2_stall) begin
            rom_read_data_held <= rom_read_data;
        end
    end
    
    assign rom_read_data_safe = EX_EX2_stall_reg ? rom_read_data_held : rom_read_data;

    // Retire stage registers update
    always @(posedge clk or posedge reset) begin
        if (reset) begin
            retire_rd <= 5'b0;
            retire_register_write_enable <= 1'b0;
            retire_opcode <= 7'b0;
            retire_alu_result <= {XLEN{1'b0}};
            retire_imm <= {XLEN{1'b0}};
            retire_pc_plus_4 <= {XLEN{1'b0}};
            retire_csr_read_data <= {XLEN{1'b0}};
            retire_byte_enable_logic_register_file_write_data <= {XLEN{1'b0}};
            instruction_retired <= 1'b0;
        end 
        else if (clk_enable) begin
            retire_rd <= WB_rd;
            retire_register_write_enable <= WB_register_write_enable;
            retire_opcode <= WB_opcode;
            retire_alu_result <= WB_alu_result;
            retire_imm <= WB_imm;
            retire_pc_plus_4 <= WB_pc_plus_4;
            retire_csr_read_data <= WB_csr_read_data;
            retire_byte_enable_logic_register_file_write_data <= WB_byte_enable_logic_register_file_write_data;

            if (!MEM_WB_stall && !MEM_WB_flush && WB_instruction != 32'h00000013) begin
                instruction_retired <= 1'b1;
            end 
            else begin
                instruction_retired <= 1'b0;
            end
        end
    end

    always @(*) begin
        case (EX_alu_src_A_select)
            `ALU_SRC_A_RD1: alu_normal_source_a = EX_read_data1;
            `ALU_SRC_A_PC: alu_normal_source_a = EX_pc;
            `ALU_SRC_A_RS1: alu_normal_source_a = {27'b0, EX_rs1};
            default: alu_normal_source_a = {XLEN{1'b0}};
        endcase

        case (EX_alu_src_B_select)
            `ALU_SRC_B_RD2: alu_normal_source_b = EX_read_data2;
            `ALU_SRC_B_IMM: alu_normal_source_b = EX_imm;
            `ALU_SRC_B_SHAMT: alu_normal_source_b = {26'b0, EX_imm[5:0]};
            `ALU_SRC_B_CSR: alu_normal_source_b = csr_forward_data;
            default: alu_normal_source_b = {XLEN{1'b0}};
        endcase

        // CSR address and data selection
        if (!standby_mode && trapped) begin
            csr_write_data  = csr_trap_write_data;
            csr_write_address = csr_trap_address;
            csr_read_address = csr_trap_address;
        end
        else begin
            csr_write_data = WB_alu_result;
            csr_write_address = WB_raw_imm[11:0];
            csr_read_address = raw_imm[11:0];
        end

        // Debug mode instruction selection
        if (debug_mode) instruction = dbg_instruction;
        else instruction = im_instruction;

        // Register file write data selection
        case (WB_register_file_write_data_select)
            `RF_WD_LOAD: register_file_write_data = WB_byte_enable_logic_register_file_write_data;
            `RF_WD_ALU: register_file_write_data = WB_alu_result;
            `RF_WD_LUI: register_file_write_data = WB_imm;
            `RF_WD_JUMP: register_file_write_data = WB_pc_plus_4;
            `RF_WD_CSR: register_file_write_data = WB_csr_read_data; 
            default: register_file_write_data = {XLEN{1'b0}};
        endcase

        // ALU source A forwarding: 2'b00=normal, 2'b01=MEM, 2'b10=WB, 2'b11=Retire
        case (alu_forward_source_select_a)
            3'b001: src_A = alu_forward_source_data_a;
            3'b010: src_A = alu_forward_source_data_a;
            3'b011: src_A = alu_forward_source_data_a;
            3'b100: src_A = alu_forward_source_data_a;
            default: src_A = alu_normal_source_a;
        endcase

        // ALU source B forwarding: 2'b00=normal, 2'b01=MEM, 2'b10=WB, 2'b11=Retire
        case (alu_forward_source_select_b)
            3'b001: src_B = alu_forward_source_data_b;
            3'b010: src_B = alu_forward_source_data_b;
            3'b011: src_B = alu_forward_source_data_b;
            3'b100: src_B = alu_forward_source_data_b;
            default: src_B = alu_normal_source_b;
        endcase
    end

endmodule