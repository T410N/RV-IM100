`include "./opcode.vh"
`include "./alu_src_select.vh"
`include "./trap.vh"

module HazardUnit (
    input wire reset,
    input wire trap_done,
    input wire csr_ready,
    input wire standby_mode,
    input wire div_start,
    input wire div_busy,
    input wire mul_start,
    input wire mul_busy,
    input wire write_done,
    input wire [2:0] trap_status,
    input wire misaligned_instruction_flush,
    input wire misaligned_memory_flush,
    input wire pth_done_flush,

    // Consumer: EXR stage (was EX stage in the 7-stage pipeline)
    input wire [4:0] EXR_rs1,
    input wire [4:0] EXR_rs2,
    input wire [6:0] EXR_opcode,
    input wire [11:0] EXR_imm,
    input wire [1:0] EXR_alu_src_A_select,
    input wire [2:0] EXR_alu_src_B_select,
    input wire EXR_csr_write_enable,
    input wire EXR_jump,

    // Producer: EX stage (NEW - inserted between EXR and EX2)
    input wire [4:0] EX_rd,
    input wire [6:0] EX_opcode,
    input wire EX_register_write_enable,
    input wire EX_csr_write_enable,
    input wire EX_jump,

    // Producer: EX2/BR stage
    input wire [4:0] EX2_rd,
    input wire [6:0] EX2_opcode,
    input wire [11:0] EX2_csr_write_address,
    input wire EX2_branch,
    input wire EX2_register_write_enable,
    input wire EX2_csr_write_enable,

    // Producer: MEM stage
    input wire [4:0] MEM_rd,
    input wire [6:0] MEM_opcode,
    input wire [4:0] MEM_rs2,
    input wire MEM_register_write_enable,
    input wire MEM_csr_write_enable,
    input wire [11:0] MEM_csr_write_address,

    // Producer: WB stage
    input wire [4:0] WB_rd,
    input wire WB_register_write_enable,
    input wire WB_csr_write_enable,
    input wire [11:0] WB_csr_write_address,

    // Producer: Retire stage
    input wire [4:0] retire_rd,
    input wire retire_register_write_enable,

    input wire branch_prediction_miss,

    // to Forward Unit - ALU forwarding
    output reg [1:0] hazard_ex,         // NEW: EX->EXR (non-ALU producers only)
    output reg [1:0] hazard_ex2,        // EX2->EXR (was EX2->EX)
    output reg [1:0] hazard_mem,
    output reg [1:0] hazard_wb,
    output reg [1:0] hazard_retire,
    output wire csr_hazard_ex2,         // NEW: keeps the CSR forwarding window equal to 7-stage
    output wire csr_hazard_mem,
    output wire csr_hazard_wb,

    // to Forward Unit - Store data forwarding
    output wire store_hazard_ex,        // NEW: store data forwarding from EX
    output wire store_hazard_ex2,
    output wire store_hazard_mem,
    output wire store_hazard_wb,
    output wire store_hazard_wb_to_mem,
    output wire store_hazard_retire,

    // to ALU Controller - prevent mul/div start during load-use hazard
    output wire load_use_hazard,

    // to IF_IO Register
    output wire exr_data_stall,

    output reg IF_IO_flush,
    output reg IO_ID_flush,
    output reg ID_EXR_flush,            // was ID_EX_flush
    output reg EXR_EX_flush,            // NEW
    output reg EX_EX2_flush,
    output reg EX_MEM_flush,
    output reg MEM_WB_flush,

    output reg IF_IO_stall,
    output reg IO_ID_stall,
    output reg ID_EXR_stall,            // was ID_EX_stall
    output reg EXR_EX_stall,            // NEW
    output reg EX_EX2_stall,
    output reg EX_MEM_stall,
    output reg MEM_WB_stall,
    output reg retire_stall
);

    // Store instruction detection
    wire is_store = (EXR_opcode == `OPCODE_STORE);
    wire is_store_mem = (MEM_opcode == `OPCODE_STORE);

    wire uses_rs1 = (EXR_alu_src_A_select == `ALU_SRC_A_RD1);
    wire uses_rs2 = (EXR_alu_src_B_select == `ALU_SRC_B_RD2);
    wire ex2_is_load = (EX2_opcode == `OPCODE_LOAD);

    // EX stage producers that already hold their final result in the EXR_EX register.
    // ALU / LOAD producers have no valid result yet in EX, so they force a stall instead.
    wire ex_can_forward = (EX_opcode == `OPCODE_LUI) ||
                          (EX_opcode == `OPCODE_JAL) ||
                          (EX_opcode == `OPCODE_JALR) ||
                          (EX_opcode == `OPCODE_ENVIRONMENT);

    // Raw dependency detection - EX stage
    wire ex_dep_rs1 = EX_register_write_enable && (EX_rd != 5'd0) && (EX_rd == EXR_rs1);
    wire ex_dep_rs2 = EX_register_write_enable && (EX_rd != 5'd0) && (EX_rd == EXR_rs2);

    wire ex_hazard_rs1 = uses_rs1 && ex_dep_rs1 && ex_can_forward;
    wire ex_hazard_rs2 = uses_rs2 && ex_dep_rs2 && ex_can_forward;

    wire ex_stall_rs1 = uses_rs1 && ex_dep_rs1 && !ex_can_forward;
    wire ex_stall_rs2 = uses_rs2 && ex_dep_rs2 && !ex_can_forward;
    wire ex_stall_store = is_store && ex_dep_rs2 && !ex_can_forward;
    wire ex_data_stall = ex_stall_rs1 || ex_stall_rs2 || ex_stall_store;

    // Register ALU hazard detections
    wire ex2_hazard_rs1 = uses_rs1 && EX2_register_write_enable && (EX2_rd != 5'd0) && (EX2_rd == EXR_rs1);
    wire ex2_hazard_rs2 = uses_rs2 && EX2_register_write_enable && (EX2_rd != 5'd0) && (EX2_rd == EXR_rs2);
    wire mem_hazard_rs1 = uses_rs1 && MEM_register_write_enable && (MEM_rd != 5'd0) && (MEM_rd == EXR_rs1);
    wire mem_hazard_rs2 = uses_rs2 && MEM_register_write_enable && (MEM_rd != 5'd0) && (MEM_rd == EXR_rs2);
    wire wb_hazard_rs1 = uses_rs1 && WB_register_write_enable && (WB_rd != 5'd0) && (WB_rd == EXR_rs1);
    wire wb_hazard_rs2 = uses_rs2 && WB_register_write_enable && (WB_rd != 5'd0) && (WB_rd == EXR_rs2);
    wire retire_hazard_rs1 = uses_rs1 && retire_register_write_enable && (retire_rd != 5'd0) && (retire_rd == EXR_rs1);
    wire retire_hazard_rs2 = uses_rs2 && retire_register_write_enable && (retire_rd != 5'd0) && (retire_rd == EXR_rs2);

    // Load-use hazard detections (load in EX2, data not ready until MEM output)
    wire load_use_hazard_rs1 = ex2_is_load && uses_rs1 && (EX2_rd != 5'd0) && (EX2_rd == EXR_rs1);
    wire load_use_hazard_rs2 = ex2_is_load && uses_rs2 && (EX2_rd != 5'd0) && (EX2_rd == EXR_rs2);
    wire load_use_hazard_store = ex2_is_load && is_store && (EX2_rd != 5'd0) && (EX2_rd == EXR_rs2);
    wire load_ex2_use_hazard = load_use_hazard_rs1 || load_use_hazard_rs2 || load_use_hazard_store;

    // Any EXR operand that cannot be satisfied by forwarding
    assign exr_data_stall = ex_data_stall || load_ex2_use_hazard;
    assign load_use_hazard = exr_data_stall;

    // Store rs2 hazard detections (for store data, not ALU operand)
    wire store_ex_hazard_rs2 = is_store && ex_dep_rs2 && ex_can_forward;
    wire store_ex2_hazard_rs2 = is_store && EX2_register_write_enable && (EX2_rd != 5'd0) && (EX2_rd == EXR_rs2);
    wire store_mem_hazard_rs2 = is_store && MEM_register_write_enable && (MEM_rd != 5'd0) && (MEM_rd == EXR_rs2);
    wire store_wb_hazard_rs2 = is_store && WB_register_write_enable && (WB_rd != 5'd0) && (WB_rd == EXR_rs2);
    wire store_retire_hazard_rs2 = is_store && retire_register_write_enable && (retire_rd != 5'd0) && (retire_rd == EXR_rs2);

    // Store instruction rs2 hazard detections (EXR stage)
    // Priority: EX > EX2 > MEM > WB > Retire (use masked signals for correct priority)
    assign store_hazard_ex = store_ex_hazard_rs2;
    assign store_hazard_ex2 = store_ex2_hazard_rs2 && !ex2_is_load && !store_hazard_ex;
    assign store_hazard_mem = store_mem_hazard_rs2 && !store_hazard_ex && !store_hazard_ex2;
    assign store_hazard_wb = store_wb_hazard_rs2 && !store_hazard_ex && !store_hazard_ex2 && !store_hazard_mem;
    assign store_hazard_retire = store_retire_hazard_rs2 && !store_hazard_ex && !store_hazard_ex2 &&
                                 !store_hazard_mem && !store_hazard_wb;

    // WB - MEM store data forwarding: SD in MEM, producer in WB
    assign store_hazard_wb_to_mem = is_store_mem &&
                                    WB_register_write_enable &&
                                    (WB_rd != 5'd0) &&
                                    (WB_rd == MEM_rs2);

    // CSR hazard detection.
    // The 7-stage pipeline forwarded from MEM and WB, leaving only the immediately
    // preceding instruction uncovered.  The extra EXR stage pushes MEM/WB one slot
    // further away, so EX2 joins the chain to keep the uncovered window identical.
    assign csr_hazard_ex2 = EX2_csr_write_enable && (EX2_csr_write_address == EXR_imm);
    assign csr_hazard_mem = MEM_csr_write_enable && (MEM_csr_write_address == EXR_imm);
    assign csr_hazard_wb = WB_csr_write_enable && (WB_csr_write_address == EXR_imm);

    always @(*) begin
        hazard_ex = 2'b00;
        hazard_ex2 = 2'b00;
        hazard_mem = 2'b00;
        hazard_wb = 2'b00;
        hazard_retire = 2'b00;
        IF_IO_flush = 1'b0;
        IO_ID_flush = 1'b0;
        ID_EXR_flush = 1'b0;
        EXR_EX_flush = 1'b0;
        EX_EX2_flush = 1'b0;
        EX_MEM_flush = 1'b0;
        MEM_WB_flush = 1'b0;

        IF_IO_stall = 1'b0;
        IO_ID_stall = 1'b0;
        ID_EXR_stall = 1'b0;
        EXR_EX_stall = 1'b0;
        EX_EX2_stall = 1'b0;
        EX_MEM_stall = 1'b0;
        MEM_WB_stall = 1'b0;
        retire_stall = 1'b0;

        // ALU forwarding hazards (priority: EX > EX2 > MEM > WB > Retire)
        // For Store instructions, rs2 hazard shouldn't trigger ALUsrcB forwarding.
        // Use forwarding enables (hazard_*) for priority masking, not raw signals,
        // so that a non-forwarding stage never blocks a lower-priority stage.
        hazard_ex[0] = ex_hazard_rs1;
        hazard_ex[1] = is_store ? 1'b0 : ex_hazard_rs2;

        hazard_ex2[0] = ex2_hazard_rs1 && !ex2_is_load && !hazard_ex[0];
        hazard_ex2[1] = is_store ? 1'b0 : (ex2_hazard_rs2 && !ex2_is_load && !hazard_ex[1]);

        // MEM forwarding: enabled if MEM has dependency AND no higher-priority stage is forwarding
        hazard_mem[0] = mem_hazard_rs1 && !hazard_ex[0] && !hazard_ex2[0];
        hazard_mem[1] = is_store ? 1'b0 : (mem_hazard_rs2 && !hazard_ex[1] && !hazard_ex2[1]);

        // WB forwarding: enabled if WB has dependency AND no higher-priority stage is forwarding
        hazard_wb[0] = wb_hazard_rs1 && !hazard_ex[0] && !hazard_ex2[0] && !hazard_mem[0];
        hazard_wb[1] = is_store ? 1'b0 : (wb_hazard_rs2 && !hazard_ex[1] && !hazard_ex2[1] && !hazard_mem[1]);

        // Retire forwarding: enabled if Retire has dependency AND no higher-priority stage is forwarding
        hazard_retire[0] = retire_hazard_rs1 && !hazard_ex[0] && !hazard_ex2[0] && !hazard_mem[0] && !hazard_wb[0];
        hazard_retire[1] = is_store ? 1'b0 : (retire_hazard_rs2 && !hazard_ex[1] && !hazard_ex2[1] &&
                                              !hazard_mem[1] && !hazard_wb[1]);

        // Redirect flushes.  Every pipeline register behind the resolving stage is
        // cleared: branches resolve in EX2, jumps resolve in EX (ALU stage).
        //
        // The jump case must NOT carry the 7-stage design's !load_use_hazard
        // guard: the data-stall block below is skipped when EX_jump is asserted,
        // so gating the flush as well leaves both wrong-path instructions alive.
        // It must still be gated on write_done, because a jump resolves in EX and
        // EXR_EX_flush would otherwise clear the jump itself while EX is held.
        if (trap_done && (branch_prediction_miss || EX_jump)) begin
            IF_IO_flush = 1'b1;
            IO_ID_flush = 1'b1;
            if (branch_prediction_miss) begin
                ID_EXR_flush = 1'b1;
                EXR_EX_flush = 1'b1;
                if (write_done && csr_ready && !div_start && !div_busy && !mul_start && !mul_busy) begin
                    EX_EX2_flush = 1'b1;
                end
            end
            else if (EX_jump && !pth_done_flush && write_done) begin
                ID_EXR_flush = 1'b1;
                EXR_EX_flush = 1'b1;
            end
        end

        if (pth_done_flush || reset) begin
            IF_IO_flush = 1'b1;
            IO_ID_flush = 1'b1;
            ID_EXR_flush = 1'b1;
            EXR_EX_flush = 1'b1;
            EX_EX2_flush = 1'b1;
            EX_MEM_flush = 1'b1;
            if (reset) begin
                MEM_WB_flush = 1'b1;
            end
            else begin
                MEM_WB_flush = 1'b0;
            end
        end

        if (standby_mode) begin
            IF_IO_stall = 1'b1;
            IO_ID_stall = 1'b1;
            ID_EXR_stall = 1'b1;
            EXR_EX_stall = 1'b0;
            EX_EX2_stall = 1'b0;
            EX_MEM_stall = 1'b0;
            MEM_WB_stall = 1'b0;
        end
        else if (!trap_done || !csr_ready) begin
            IF_IO_stall = 1'b1;
            IO_ID_stall = 1'b1;
            ID_EXR_stall = 1'b1;
            EXR_EX_stall = 1'b1;
            EX_EX2_stall = 1'b1;
            EX_MEM_stall = 1'b1;
            MEM_WB_stall = 1'b1;
        end
        else if (div_start || div_busy || mul_start || mul_busy) begin
            IF_IO_stall = 1'b1;
            IO_ID_stall = 1'b1;
            ID_EXR_stall = 1'b1;
            EXR_EX_stall = 1'b1;
            EX_EX2_stall = 1'b1;
            EX_MEM_stall = 1'b1;
            MEM_WB_stall = 1'b1;
        end

        else if (!write_done) begin
            IF_IO_stall = 1'b1;
            IO_ID_stall = 1'b1;
            ID_EXR_stall = 1'b1;
            EXR_EX_stall = 1'b1;
            EX_EX2_stall = 1'b1;
            EX_MEM_stall = 1'b1;
            MEM_WB_stall = 1'b1;
        end

        // Operand not available by forwarding: hold EXR and push a bubble into EX
        if (exr_data_stall && trap_done && csr_ready && !standby_mode && !div_start && !div_busy &&
            !mul_start && !mul_busy && write_done && !branch_prediction_miss && !EX_jump) begin
            IF_IO_stall = 1'b1;
            IO_ID_stall = 1'b1;
            ID_EXR_stall = 1'b1;
            EXR_EX_flush = 1'b1;
        end

        // An instruction held in EXR can outlive the forwarding window: while it
        // waits, its rs1 producer drains EX -> EX2 -> MEM -> WB -> retire and then
        // disappears, leaving only the stale value latched at ID.  Freeze the
        // retire stage so the producer stays visible until the consumer advances.
        if (exr_data_stall && retire_hazard_rs1) begin
            retire_stall = 1'b1;
        end
    end

endmodule
