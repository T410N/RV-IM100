`include "./alu_op.vh"

module ALU #(
    parameter XLEN = 64
)(
    input [XLEN-1:0] src_A,             // source operand A
    input [XLEN-1:0] src_B,             // source operand B
    input [4:0] alu_op,        		// ALU operation signal (from ALU Control module)
    input input_size_word,

    output reg [XLEN-1:0] alu_result,   // ALU result
    output reg alu_zero             // zero flag
);
    wire [31:0] alu_word_result;
    wire alu_word_zero;

    wire [XLEN-1:0] alu_dword_result;
    wire alu_dword_zero;

    /*wire [31:0] prod_high_word;
    wire [31:0] prod_low_word;

    wire [63:0] prod_high_dword;
    wire [63:0] prod_low_dword;
*/
    ALU_WORD alu_word (
        .src_A(src_A[31:0]),
        .src_B(src_B[31:0]),
        .alu_op(alu_op),
        
        .alu_result(alu_word_result),
        .alu_zero(alu_word_zero)
    );

    ALU_DWORD alu_dword (
        .src_A(src_A),
        .src_B(src_B),
        .alu_op(alu_op),
        
        .alu_result(alu_dword_result),
        .alu_zero(alu_dword_zero)
    );
/*
    Multiplier_WORD multiplier_word (
        .src_A(src_A[31:0]),
        .src_B(src_B[31:0]),
        .signed_A(alu_op == `ALU_OP_MULH | alu_op == `ALU_OP_MULHSU),
        .signed_B(alu_op == `ALU_OP_MULH),

        .prod_high(prod_high_word),
        .prod_low(prod_low_word)
    );

    Multiplier_DWORD multiplier_dword (
        .src_A(src_A),
        .src_B(src_B),
        .signed_A(alu_op == `ALU_OP_MULH | alu_op == `ALU_OP_MULHSU),
        .signed_B(alu_op == `ALU_OP_MULH),

        .prod_high(prod_high_dword),
        .prod_low(prod_low_dword)
    );
*/
    always @(*) begin
        case (alu_op)
            /*
            `ALU_OP_MUL: begin
                if (input_size_word) begin
                    alu_result = {{32{prod_low_word[31]}}, prod_low_word};
                    alu_zero = (prod_low_word == 0);
                end
                else begin
                    alu_result = prod_low_dword;
                    alu_zero = (prod_low_dword == 0);
                end
            end
            `ALU_OP_MULH, `ALU_OP_MULHSU, `ALU_OP_MULHU: begin
                if (input_size_word) begin
                    alu_result = {{32{prod_high_word[31]}}, prod_high_word};
                    alu_zero = (prod_high_word == 0);
                end
                else begin
                    alu_result = prod_high_dword;
                    alu_zero = (prod_high_dword == 0);
                end
            end
            */
            default: begin
                if (input_size_word) begin
                    alu_result = {{32{alu_word_result[31]}}, alu_word_result};
                    alu_zero = alu_word_zero;
                end
                else begin
                    alu_result = alu_dword_result;
                    alu_zero = alu_dword_zero;
                end
            end
        endcase
    end

endmodule