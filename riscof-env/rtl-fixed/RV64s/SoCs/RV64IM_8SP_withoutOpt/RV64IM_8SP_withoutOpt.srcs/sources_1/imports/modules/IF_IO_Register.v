`include "./opcode.vh"

module IF_IO_Register #(
    parameter XLEN = 64   
)(
    // pipeline register control signals
    input wire clk,
    input wire clk_enable,
    input wire flush,
    input wire IF_IO_stall,
    input wire branch_estimation,
    input wire jump,
    input wire [6:0] ID_opcode,
    input wire [6:0] ID_funct7,
    input wire [6:0] EX2_opcode,
    input wire load_use_hazard,
    input wire exr_data_stall,
    input wire branch_prediction_miss,
    input wire [XLEN-1:0] branch_target,

    // signals from IF phase
    input wire [XLEN-1:0] IF_pc,
    input wire [XLEN-1:0] IF_pc_plus_4,
    input wire [31:0] IF_instruction,

    // signals to ID/EX register
    output reg [XLEN-1:0] IO_pc,
    output reg [XLEN-1:0] IO_pc_plus_4,
    output reg [31:0] IO_instruction
);

reg flush_reg;
reg is_load_use_hazard;
reg branch_estimation_reg;
wire is_store = (EX2_opcode == `OPCODE_STORE);
wire is_m_extend = (ID_opcode == `OPCODE_RTYPE || ID_opcode == `OPCODE_RTYPE_WORD) && (ID_funct7 == 7'b000_0001);

// ---------------------------------------------------------------------------
// Predicted-taken redirect shadow.
//
// When the predictor calls a branch taken, the PC keeps issuing sequential
// fetches until the redirect lands.  How many wrong-path fetches get issued is
// NOT fixed on this pipeline -- it depends on whether IF_IO_stall /
// exr_data_stall extend the shadow -- and the existing squash machinery covers
// only some of the cases:
//
//   * the `branch_estimation` arm below squashes the slot entering IO,
//   * `flush_reg` squashes one more, but the `exr_data_stall` arm clears it,
//   * `is_load_use_hazard` squashes one more, but only when a load-use hazard
//     happens to be live at that moment.
//
// picojpeg hits the gap: at the taken `bnez` at pc 0xb20 the shadow is two
// fetches deep and no load-use hazard is pending, so pc 0xb28 survived into IO
// and committed (2010 times, against 18 legitimate executions).
//
// Rather than trying to predict the shadow depth, track the outstanding
// redirect and refuse to admit any instruction whose PC is not the predicted
// target.  That is correct for a shadow of any depth, and unlike a blanket
// "squash one more" it cannot drop the target itself -- which would kill the
// loop head of a short backward branch such as `bne a5,a2,0x126c`.
// ---------------------------------------------------------------------------
reg est_pending = 1'b0;
reg [XLEN-1:0] est_target = {XLEN{1'b0}};

wire est_squash = branch_estimation && !IF_IO_stall && !is_m_extend;
// A redirect is outstanding and the instruction in IF is not its target.
wire est_wrong_path = est_pending && !est_squash && (IF_pc != est_target);


always @(posedge clk) begin
    if (clk_enable) begin
        if (flush || (branch_estimation && !IF_IO_stall && !is_m_extend) || (jump && !IF_IO_stall)) begin   
            flush_reg <= 1'b1;
            is_load_use_hazard <= 1'b0;
            IO_pc <= {XLEN{1'b0}};
            IO_pc_plus_4 <= {XLEN{1'b0}};
            IO_instruction <= 32'h0000_0013; // ADDI x0, x0, 0 = RISC-V NOP, HINT
        end
        else if (exr_data_stall && branch_estimation_reg && !branch_estimation) begin
            flush_reg <= 1'b0;
            IO_pc <= {XLEN{1'b0}};
            IO_pc_plus_4 <= {XLEN{1'b0}};
            IO_instruction <= 32'h0000_0013; // ADDI x0, x0, 0 = RISC-V NOP, HINT
        end
        else if (flush_reg && !IF_IO_stall) begin
            flush_reg <= 1'b0;
            IO_pc <= {XLEN{1'b0}};
            IO_pc_plus_4 <= {XLEN{1'b0}};
            IO_instruction <= 32'h0000_0013; // ADDI x0, x0, 0 = RISC-V NOP, HINT
        end
        else if (est_wrong_path && !IF_IO_stall) begin
            // Still inside the redirect shadow: this fetch is not the branch
            // target, so it must not enter IO.  is_load_use_hazard is cleared
            // with it, otherwise the hazard arm would squash the *target* on
            // the following cycle.
            is_load_use_hazard <= 1'b0;
            IO_pc <= {XLEN{1'b0}};
            IO_pc_plus_4 <= {XLEN{1'b0}};
            IO_instruction <= 32'h0000_0013; // ADDI x0, x0, 0 = RISC-V NOP, HINT
        end
        else if (is_load_use_hazard) begin
            is_load_use_hazard <= 1'b0;
            if (!is_store) begin
                IO_pc <= {XLEN{1'b0}};
                IO_pc_plus_4 <= {XLEN{1'b0}};
                IO_instruction <= 32'h0000_0013; // ADDI x0, x0, 0 = RISC-V NOP, HINT
            end
            else if (is_store) begin
                IO_pc <= IF_pc;
                IO_pc_plus_4 <= IF_pc_plus_4;
                IO_instruction <= IF_instruction;
            end
        end
        else if (!IF_IO_stall) begin
            IO_pc <= IF_pc;
            IO_pc_plus_4 <= IF_pc_plus_4;
            IO_instruction <= IF_instruction;
        end

        if (load_use_hazard && flush_reg) begin
            is_load_use_hazard <= 1'b1;
        end 

        // Outstanding-redirect bookkeeping.  Cleared once the target is
        // actually admitted, and on any real redirect (flush / jump /
        // misprediction) that supersedes the prediction -- so the shadow can
        // never stay open and starve the pipeline.
        // A real redirect outranks a prediction, and the two can assert on the
        // SAME cycle: at pc 0x1100 picojpeg raises branch_prediction_miss while
        // the predictor is calling another branch taken.  The miss wins in
        // PCController, so latching the predicted target here would leave a
        // shadow waiting for an address the PC never fetches -- the pipeline
        // then squashes forever.  Clear first, predict second.
        if (flush || (jump && !IF_IO_stall) || branch_prediction_miss) begin
            est_pending <= 1'b0;
        end
        else if (est_squash) begin
            est_pending <= 1'b1;
            est_target  <= branch_target;
        end
        else if (est_pending && !IF_IO_stall && (IF_pc == est_target)) begin
            est_pending <= 1'b0;
        end

        if (branch_estimation) begin
            branch_estimation_reg <= 1'b1;
        end
        else if (!branch_estimation && !exr_data_stall) begin
            branch_estimation_reg <= 1'b0;
        end
    end
end
    
endmodule