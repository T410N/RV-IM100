`include "./alu_op.vh"
`include "./branch_funct3.vh"
`include "./csr_funct3.vh"
`include "./itype_funct3.vh"
`include "./opcode.vh"
`include "./rtype_funct3.vh"
`include "./rtype_mul_funct3.vh"

module ALUController (
    input [6:0] opcode,        		// opcode
	input [2:0] funct3,				// funct3
	input funct7_0,					// 0th index of funct7
    input funct7_5,					// 5th index of funct7
    input imm_10,					// 10th index of imm
	
    output reg [4:0] alu_op,		// ALU operation signal
    output input_size_word          // signal indicating if input for ALU is WORD or DWORD
);

    assign input_size_word = ((opcode == `OPCODE_ITYPE_WORD) | (opcode == `OPCODE_RTYPE_WORD));

    always @(*) begin
        case (opcode)
			`OPCODE_AUIPC, `OPCODE_JAL, `OPCODE_JALR, `OPCODE_LOAD, `OPCODE_STORE: alu_op = `ALU_OP_ADD;
			
			`OPCODE_BRANCH: begin
				case (funct3)
					`BRANCH_BEQ: alu_op = `ALU_OP_SUB; // If subtraction result is zero, equal
					`BRANCH_BNE: alu_op = `ALU_OP_SUB; // If subtraction result is not zero, not equal
					`BRANCH_BLT: alu_op = `ALU_OP_SLT; // If SLT result is not zero, less
					`BRANCH_BGE: alu_op = `ALU_OP_SLT; // If SLT result is zero, greater or equal
					`BRANCH_BLTU: alu_op = `ALU_OP_SLTU; // If SLTU result is not zero, less (unsigned)
					`BRANCH_BGEU: alu_op = `ALU_OP_SLTU; // If SLTU result is zero, greater or equal (unsigned)
					default: alu_op = `ALU_OP_NOP;
				endcase
			end
			`OPCODE_ITYPE, `OPCODE_ITYPE_WORD: begin
				case (funct3)
					`ITYPE_ADDI: alu_op = `ALU_OP_ADD;
					`ITYPE_SLLI: alu_op = `ALU_OP_SLL;
					`ITYPE_SLTI: alu_op = `ALU_OP_SLT;
					`ITYPE_SLTIU: alu_op = `ALU_OP_SLTU;
					`ITYPE_XORI: alu_op = `ALU_OP_XOR;
					`ITYPE_SRXI: begin // srli or srai
						if (imm_10) begin
							alu_op = `ALU_OP_SRA; // srai : imm[10] = 1
						end
						else begin
							alu_op = `ALU_OP_SRL; // srli : imm[10] = 0
						end
					end
					`ITYPE_ORI: alu_op = `ALU_OP_OR; // ori : 110 ; - 
					`ITYPE_ANDI: alu_op = `ALU_OP_AND; // andi : 111 ; -
				    default: alu_op = `ALU_OP_NOP;
				endcase
			end 
			`OPCODE_RTYPE, `OPCODE_RTYPE_WORD: begin
				
			/*
				if (funct7_0) begin // M extension operations
					case (funct3)
						`RTYPE_MUL: begin
							alu_op = `ALU_OP_MUL;
						end
						`RTYPE_MULH: begin
							alu_op = `ALU_OP_MULH;
						end
						`RTYPE_MULHSU: begin
							alu_op = `ALU_OP_MULHSU;
						end
						`RTYPE_MULHU: begin
							alu_op = `ALU_OP_MULHU;
						end
						`RTYPE_DIV: begin
							alu_op = `ALU_OP_DIV;
						end
						`RTYPE_DIVU: begin
							alu_op = `ALU_OP_DIVU;
						end
						`RTYPE_REM: begin
							alu_op = `ALU_OP_REM;
						end
						`RTYPE_REMU: begin
							alu_op = `ALU_OP_REMU;
						end
					endcase
				end
				*/// I extension operations
					case (funct3)
						`RTYPE_ADDSUB: begin // add or sub
							if (funct7_5) begin
								alu_op = `ALU_OP_SUB; // sub : funct7 = 0100000
							end
							else begin
								alu_op = `ALU_OP_ADD; // add : funct7 = 0000000 
							end
						end
						`RTYPE_SLL: alu_op = `ALU_OP_SLL;
						`RTYPE_SLT: alu_op = `ALU_OP_SLT;
						`RTYPE_SLTU: alu_op = `ALU_OP_SLTU;
						`RTYPE_XOR: alu_op = `ALU_OP_XOR;
						`RTYPE_SRX: begin // srl or sra
							if (funct7_5) begin
								alu_op = `ALU_OP_SRA; // sra : funct7 = 0100000
							end
							else begin
								alu_op = `ALU_OP_SRL; // srl : funct7 = 0000000
							end
						end
						`RTYPE_OR: alu_op = `ALU_OP_OR;
						`RTYPE_AND: alu_op = `ALU_OP_AND;
						default: alu_op = `ALU_OP_NOP;
					endcase
                
            end
			`OPCODE_ENVIRONMENT: begin
				case (funct3)
					`CSR_CSRRW: alu_op = `ALU_OP_ADD; // will perform +0 operation
					`CSR_CSRRS: alu_op = `ALU_OP_OR;
					`CSR_CSRRC: alu_op = `ALU_OP_ABJ;
					`CSR_CSRRWI: alu_op = `ALU_OP_ADD; // will perform +0 operation
					`CSR_CSRRSI: alu_op = `ALU_OP_OR;
					`CSR_CSRRCI: alu_op = `ALU_OP_ABJ;
					default: alu_op = `ALU_OP_NOP;
				endcase
			end
			default: begin
				alu_op = `ALU_OP_NOP;
			end
        endcase
    end

endmodule