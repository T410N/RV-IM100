`include "./alu_op.vh"

module ALU_WORD (
    input [31:0] src_A,             // source operand A
    input [31:0] src_B,             // source operand B
    input [4:0] alu_op,        		// ALU operation signal (from ALU Control module)
    
    output reg [31:0] alu_result,   // ALU result
    output reg alu_zero             // zero flag
);

    always @(*) begin
        case (alu_op)
            `ALU_OP_ADD: begin
                alu_result = src_A + src_B;
            end

            `ALU_OP_SUB: begin
                alu_result = src_A - src_B;
            end
			
			`ALU_OP_SLL: begin
				alu_result = src_A << src_B[4:0];
			end
			
			`ALU_OP_SRL: begin
				alu_result = src_A >> src_B[4:0];
			end
			
			`ALU_OP_SRA: begin
				alu_result = $signed(src_A) >>> src_B[4:0];
			end
			
			`ALU_OP_NOP: begin
				alu_result = 32'd0;
			end

            default: begin
                alu_result = 32'd0; // Default case: zero result
            end
        endcase

        alu_zero = (alu_result == 32'd0); // Zero flag: set if result is zero
    end

endmodule