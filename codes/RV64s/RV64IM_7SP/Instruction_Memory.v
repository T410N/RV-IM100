`include "./branch_funct3.vh"
`include "./itype_funct3.vh"
`include "./load_funct3.vh"
`include "./rtype_funct3.vh"
`include "./rtype_mul_funct3.vh"
`include "./store_funct3.vh"
`include "./opcode.vh"
`include "./csr_funct3.vh"

module InstructionMemory #(
    parameter XLEN = 64
)(
	input clk,
	input clk_enable,
	input pc_stall,
    input [XLEN-1:0] pc,
	input [XLEN-1:0] rom_address,

    output reg [31:0] instruction,
	output reg [XLEN-1:0] rom_read_data
);

	reg [31:0] data [0:8191];
	wire rom_access = (rom_address[31:16] == 16'h0000);

	always @(posedge clk) begin
		if (clk_enable && !pc_stall) begin
			instruction <= data[pc[15:2]];
		end
	end

	always @(posedge clk) begin
		if (clk_enable) begin
			if (rom_access) begin
				rom_read_data <= {data[{rom_address[15:3], 1'b1}], data[{rom_address[15:3], 1'b0}]};
			end
			else begin
				rom_read_data <= {XLEN{1'b0}};
			end
		end
	end
	
	initial begin
		 $readmemh("./dhrystone_RV64IM_48.61111.mem", data);
		 /*
		// ──────────────────────────────────────────────
		// I-타입 ALU 명령어 (9개)
		// {imm[11:0], rs1, funct3, rd, OPCODE_ITYPE}
		data[0] = {12'h2BC, 5'd0, `ITYPE_ADDI, 5'd1, `OPCODE_ITYPE};				// ADDI:  x1 = x0 + 0x2BC = 0x0000_0000_0000_02BC
		data[1] = {12'd24,  5'd1, `ITYPE_SLLI, 5'd2, `OPCODE_ITYPE};				// SLLI:  x2 = x1 << 24 = 0x0000_0002_BC00_0000
		data[2] = {12'd0,  5'd2, `ITYPE_SLTI, 5'd3, `OPCODE_ITYPE};					// SLTI:  x3 = (signed(x2) < 0) ? 1 : 0 = 0x0000_0000_0000_0000
		data[3] = {12'd0,  5'd2, `ITYPE_SLTIU, 5'd4, `OPCODE_ITYPE};				// SLTIU: x4 = (unsigned(x2) < 0) ? 1 : 0 = 0x0000_0000_0000_0000  (unsigned 비교에서 "< 0"은 항상 0)
		data[4] = {12'h653,  5'd1, `ITYPE_XORI, 5'd5, `OPCODE_ITYPE};				// XORI:  x5 = x1 XOR 0x653 = 0x0000_0000_0000_04EF
		data[5] = {7'b0000000, 5'd4, 5'd2, `ITYPE_SRXI, 5'd6, `OPCODE_ITYPE};		// SRLI:  x6 = x2 >> 4  = 0x0000_0000_2BC0_0000
		data[6] = {7'b0100000, 5'd4, 5'd2, `ITYPE_SRXI, 5'd7, `OPCODE_ITYPE};		// SRAI:  x7 = signed(x2) >>> 4 = 0x0000_0000_2BC0_0000  (x2가 양수이므로 SRLI와 동일)
		data[7] = {12'h0BC, 5'd2, `ITYPE_ORI, 5'd8, `OPCODE_ITYPE};					// ORI:   x8 = x2 OR 0x0BC = 0x0000_0002_BC00_00BC
		data[8] = {12'h0EC, 5'd5, `ITYPE_ANDI, 5'd9, `OPCODE_ITYPE};				// ANDI:  x9 = x5 AND 0x0EC = 0x0000_0000_0000_00EC

		// ──────────────────────────────────────────────
		// R-타입 명령어 (10개)
		// {funct7, rs2, rs1, funct3, rd, OPCODE_RTYPE}
		data[9]  = {7'b0000000, 5'd9, 5'd1, `RTYPE_ADDSUB, 5'd10, `OPCODE_RTYPE};	// ADD: x10 = x1 + x9 = 0x0000_0000_0000_03A8
		data[10] = {7'b0100000, 5'd5, 5'd6, `RTYPE_ADDSUB, 5'd11, `OPCODE_RTYPE};	// SUB: x11 = x6 - x5 = 0x0000_0000_2BBF_FB11
		data[11] = {7'b0000000, 5'd3, 5'd7, `RTYPE_SLL, 5'd12, `OPCODE_RTYPE};		// SLL: x12 = x7 << (x3[5:0]) = x7 << 0 = 0x0000_0000_2BC0_0000   (RV64: rs2[5:0] 사용)
		data[12] = {7'b0000000, 5'd2, 5'd1, `RTYPE_SLT, 5'd13, `OPCODE_RTYPE};		// SLT: x13 = (signed(x1) < signed(x2)) ? 1 : 0 = 0x0000_0000_0000_0001
		data[13] = {7'b0000000, 5'd2, 5'd1, `RTYPE_SLTU, 5'd14, `OPCODE_RTYPE};		// SLTU: x14 = (unsigned(x1) < unsigned(x2)) ? 1 : 0 = 0x0000_0000_0000_0001
		data[14] = {7'b0000000, 5'd8, 5'd12, `RTYPE_XOR, 5'd15, `OPCODE_RTYPE};		// XOR: x15 = x12 XOR x8 = 0x0000_0002_97C0_00BC
		data[15] = {7'b0000000, 5'd3, 5'd12, `RTYPE_SRX, 5'd16, `OPCODE_RTYPE};		// SRL: x16 = x12 >> (x3[5:0]) = x12 >> 0 = 0x0000_0000_2BC0_0000
		data[16] = {7'b0100000, 5'd3, 5'd12, `RTYPE_SRX, 5'd17, `OPCODE_RTYPE};		// SRA: x17 = signed(x12) >>> (x3[5:0]) = x12 >>> 0 = 0x0000_0000_2BC0_0000
		data[17] = {7'b0000000, 5'd7, 5'd11, `RTYPE_OR, 5'd18, `OPCODE_RTYPE};		// OR:  x18 = x11 OR x7 = 0x0000_0000_2BFF_FB11
		data[18] = {7'b0000000, 5'd11, 5'd7, `RTYPE_AND, 5'd19, `OPCODE_RTYPE};		// AND: x19 = x7 AND x11 = 0x0000_0000_2B80_0000

		// ──────────────────────────────────────────────
		// S-타입 명령어 (스토어) (3개)
		// {imm[11:5], rs2, rs1, funct3, imm[4:0], OPCODE_STORE}
		data[19] = {7'd0, 5'd11, 5'd1, `STORE_SW, 5'd4, `OPCODE_STORE};				// SW: mem[x1+4 = 0x0000_0000_0000_02C0] = x11[31:0] = 0x2BBF_FB11
		data[20] = {7'd0, 5'd10, 5'd1, `STORE_SH, 5'd7, `OPCODE_STORE};				// SH: mem[x1+7 = 0x0000_0000_0000_02C3] = x10[15:0] = 0x03A8  // Misaligned(halfword) store exception -> no store
		data[21] = {7'd0, 5'd15, 5'd1, `STORE_SB, 5'd4, `OPCODE_STORE};				// SB: mem[x1+4 = 0x0000_0000_0000_02C0] = x15[7:0] = 0xBC -> (word) 0x2BBF_FBBC  (이전 SW가 동일 주소에 반영되었다는 가정)

		// ──────────────────────────────────────────────
		// I-타입 로드 명령어 (5개) - RAM 접근을 위해 x1 주소 변경
		// {imm[11:0], rs1, funct3, rd, OPCODE_LOAD}
		
		// x1을 1000_02BC로 변경 (RAM 영역 접근용)
		data[22] = {20'h10000, 5'd31, `OPCODE_LUI};									// LUI: x31 = 0x0000_0000_1000_0000
		data[23] = {7'b0000000, 5'd31, 5'd1, `RTYPE_OR, 5'd1, `OPCODE_RTYPE};		// OR:  x1 = x1 | x31 = 0x0000_0000_1000_02BC

		data[24] = {12'd5, 5'd1, `LOAD_LW, 5'd20, `OPCODE_LOAD};					// LW:  x20 = mem[x1+5 = 0x0000_0000_1000_02C1] (misaligned word) -> Load address misaligned exception, rd not written
		data[25] = {12'd4, 5'd1, `LOAD_LH, 5'd21, `OPCODE_LOAD};					// LH:  x21 = signext16(mem[x1+4 = 0x0000_0000_1000_02C0][15:0]) = 0xFFFF_FFFF_FFFF_FBBC  (mem word=0x2BBF_FBBC 가정)
		data[26] = {12'd4, 5'd1, `LOAD_LB, 5'd22, `OPCODE_LOAD};					// LB:  x22 = signext8 (mem[x1+4 = 0x0000_0000_1000_02C0][7:0])  = 0xFFFF_FFFF_FFFF_FFBC
		data[27] = {12'd4, 5'd1, `LOAD_LHU, 5'd23, `OPCODE_LOAD};					// LHU: x23 = zeroext16(mem[x1+4 = 0x0000_0000_1000_02C0][15:0]) = 0x0000_0000_0000_FBBC
		data[28] = {12'd4, 5'd1, `LOAD_LBU, 5'd24, `OPCODE_LOAD};					// LBU: x24 = zeroext8 (mem[x1+4 = 0x0000_0000_1000_02C0][7:0])  = 0x0000_0000_0000_00BC

		// x1을 다시 0000_02BC로 복원
		data[29] = {12'h2BC, 5'd0, `ITYPE_ADDI, 5'd1, `OPCODE_ITYPE};				// ADDI: x1 = 0x0000_0000_0000_02BC

		// ──────────────────────────────────────────────
		// U-타입 명령어 (2개)
		// {imm[31:12], rd, OPCODE_LUI/OPCODE_AUIPC}
		data[30] = {20'd1, 5'd25, `OPCODE_LUI};										// LUI: x25 = 0x0000_0000_0000_1000		
		data[31] = {20'd1, 5'd26, `OPCODE_AUIPC};									// AUIPC: x26 = PC(0x0000_0000_0000_007C) + 0x0000_0000_0000_1000 = 0x0000_0000_0000_107C

		// ──────────────────────────────────────────────
		// J-타입 명령어 (1개)
		// {imm[20|10:1|11|19:12], rd, OPCODE_JAL}
		data[32] = {20'b0_0000001111_0_00000000, 5'd27, `OPCODE_JAL};				// JAL: x27 = PC + 4 = 0x0000_0000_0000_0084; target PC = 0x0000_0000_0000_009E (C 미구현 시 instruction-address-misaligned 가능)

		// ──────────────────────────────────────────────
		// B-타입 명령어 (분기) (6개)
		// {imm[12], imm[10:5], rs2, rs1, funct3, imm[4:1], imm[11], OPCODE_BRANCH}
		data[33] = {1'b0, 6'd0, 5'd2, 5'd1, `BRANCH_BEQ, 4'b0100, 1'b0, `OPCODE_BRANCH}; 	// BEQ:  if(x1 == x2)  branch offset = 8  -> Not Taken (0x...02BC != 0x...BC00_0000)
		data[34] = {1'b0, 6'd0, 5'd13, 5'd0, `BRANCH_BNE, 4'b0100, 1'b0, `OPCODE_BRANCH}; 	// BNE:  if(x0 != x13) branch offset = 8  -> Taken (x13 = 0x0000_0000_0000_0001)
		data[35] = {1'b0, 6'd0, 5'd2, 5'd1, `BRANCH_BLT, 4'b0100, 1'b0, `OPCODE_BRANCH}; 	// BLT:  if(signed(x1) < signed(x2)) branch offset = 8 -> Taken (양수 비교에서 0x2BC < 0x2BC000000)
		data[36] = {1'b0, 6'd0, 5'd1, 5'd2, `BRANCH_BGE, 4'b0100, 1'b0, `OPCODE_BRANCH}; 	// BGE:  if(signed(x2) >= signed(x1)) branch offset = 8 -> Taken
		data[37] = {1'b0, 6'd0, 5'd1, 5'd2, `BRANCH_BLTU, 4'b0100, 1'b0, `OPCODE_BRANCH}; 	// BLTU: if(unsigned(x2) < unsigned(x1)) branch offset = 8 -> Not Taken
		data[38] = {1'b0, 6'd0, 5'd1, 5'd2, `BRANCH_BGEU, 4'b0100, 1'b0, `OPCODE_BRANCH}; 	// BGEU: if(unsigned(x2) >= unsigned(x1)) branch offset = 8 -> Taken

		// ──────────────────────────────────────────────
		// I-타입 점프 (JALR) 명령어 (1개)
		// {imm[11:0], rs1, funct3, rd, OPCODE_JALR}
		data[39] = {12'd0, 5'd27, 3'b000, 5'd28, `OPCODE_JALR}; 						// JALR: x28 = PC + 4; PC = (x27 + 0) & ~1  (x27가 유효하다는 가정, RV64에서도 동일 규칙)

		// ──────────────────────────────────────────────
		// I-타입 Zicsr 확장 명령어 (6개)	[F11] == mvendorid, [341] = mepc, [342] = mcause, [305] = mtvec
		// {imm[11:0], rs1(uimm), funct3, rd, OPCODE_ENVIRONMENT}
		data[40] = {12'hF11, 5'd28, `CSR_CSRRW, 5'd20, `OPCODE_ENVIRONMENT}; 		// CSRRW : x20 = old CSR[0xF11]; CSR[0xF11] = x28  (예: CSR[0xF11]=0x0000_0000_5256_4B43 라면 x20=0x0000_0000_5256_4B43)
		data[41] = {12'h341, 5'd1, `CSR_CSRRS, 5'd21, `OPCODE_ENVIRONMENT}; 		// CSRRS: x21 = old CSR[0x341]; CSR[0x341] = CSR[0x341] | x1  (주석 내 값 표기는 64-bit로: 0x0000_0000_0000_0074 등)
		data[42] = {12'h341, 5'd20, `CSR_CSRRC, 5'd21, `OPCODE_ENVIRONMENT}; 		// CSRRC: x21 = old CSR[0x341]; CSR[0x341] = CSR[0x341] & ~x20
		data[43] = {12'h342, 5'd3, `CSR_CSRRWI, 5'd22, `OPCODE_ENVIRONMENT}; 		// CSRRWI: x22 = old CSR[0x342]; CSR[0x342] = uimm(0x3)  (rd는 64-bit로 반환/저장)
		data[44] = {12'h305, 5'd7, `CSR_CSRRSI, 5'd22, `OPCODE_ENVIRONMENT}; 		// CSRRSI: x22 = old CSR[0x305]; CSR[0x305] = CSR[0x305] | uimm(0x7)
		data[45] = {12'h305, 5'b11111, `CSR_CSRRCI, 5'd23, `OPCODE_ENVIRONMENT}; 	// CSRRCI: x23 = old CSR[0x305]; CSR[0x305] = CSR[0x305] & ~uimm(0x1F)

		// ──────────────────────────────────────────────
		// I-타입 HINT 명령어 (CSR 동작 확인)
		// {imm[11:0], rs1, funct3, rd, OPCODE_ITYPE}
		data[46] = {12'h2BC, 5'd0, `ITYPE_ADDI, 5'd0, `OPCODE_ITYPE};				// ADDI:  x0 = x0 + 0x2BC = 0x0000_0000_0000_0000  (x0는 항상 0)

		// ──────────────────────────────────────────────
		// ECALL 명령어, Misaligned Instruction address exception 발생 JALR 명령어, Misaligned Memory Address access exception 발생 SH 명령어
		data[47] = {12'd0, 5'd0, 3'd0, 5'd0, `OPCODE_ENVIRONMENT}; 					// ECALL: trap -> PC = CSR[mtvec] (예: 0x0000_0000_0000_1000 = data[1024])
		data[48] = {12'd1, 5'd27, 3'b000, 5'd28, `OPCODE_JALR}; 					// JALR: x28 = PC + 4; target PC = (x27 + 1) & ~1 = (x27 + 0)  (단, x27 LSB=0이면 +1은 &~1로 상쇄됨)
		data[49] = {7'b0, 5'd5, 5'd1, `STORE_SH, 5'd1, `OPCODE_STORE};				// SH: mem[x1+1 = 0x0000_0000_0000_02BD] = x5[15:0] = 0x04EF  // Misaligned(halfword) store exception -> no store

		// ──────────────────────────────────────────────
		// Debug Interface 명령어 수행을 위한 전초 작업. 기존 x22 값 FFFF_FFBC 값을 더하는 ADD 명령어를 DI에서 수행할 예정
		data[50] = {20'd0, 5'd22, `OPCODE_LUI};										// LUI: x22 = 0x0000_0000_0000_0000
		data[51] = {12'hFBC, 5'd22, `ITYPE_ADDI, 5'd22, `OPCODE_ITYPE};				// ADDI x22 = x22 + signext(0xFBC=-0x44) = 0xFFFF_FFFF_FFFF_FFBC
		data[52] = {20'hABADC, 5'd23, `OPCODE_LUI};									// LUI: x23 = signext(0xABADC000) = 0xFFFF_FFFF_ABAD_C000  (RV64 LUI 결과는 XLEN까지 sign-extend)
		data[53] = {12'hB02, 5'd23, `ITYPE_ADDI, 5'd23, `OPCODE_ITYPE};				// ADDI:  x23 = x23 + signext(0xB02=-0x4FE) = 0xFFFF_FFFF_ABAD_BB02

		// ──────────────────────────────────────────────
		// printf 수행을 위한 MMIO Interface 테스트벤치 명령어. SB to 0x10010000, store "ABADBEBE" = UART로 출력
		data[54] = {1'b0, 10'b0001011100, 1'b0, 8'b0, 5'd0, `OPCODE_JAL};			// JAL x0, +184: data[100]으로 분기 (RV64I 테스트 블록)

		data[55] = {12'd1, 5'd0, 3'd0, 5'd0, `OPCODE_ENVIRONMENT};					// EBREAK: 
																					// └ADD: x22 = x22 + x23. FFFF_FFBC(x22) + ABAD_BB02(x23) = ABAD_BABE(x22)

		// HINT; NOP for 'x' signal after EBREAK in pipeline
		data[56] = {12'h2BC, 5'd0, `ITYPE_ADDI, 5'd0, `OPCODE_ITYPE};				// ADDI:  x0 = x0 + 2BC = 0000_0000
		
		// ──────────────────────────────────────────────
		// UART MMIO 테스트: 0x10010000에 "ABADBEBE" 출력 (Polling 추가)
		data[57] = {20'h10010, 5'd29, `OPCODE_LUI};									// LUI: x29 = 0x10010000 (UART TX Data 주소)
		data[58] = {12'h004, 5'd29, `ITYPE_ADDI, 5'd28, `OPCODE_ITYPE};				// ADDI: x28 = x29 + 4 = 0x10010004 (UART Status 주소)

		// 'A' 전송
		data[59] = {12'h041, 5'd0, `ITYPE_ADDI, 5'd31, `OPCODE_ITYPE};							// ADDI: x31 = 'A' (0x41)
		data[60] = {12'd0, 5'd28, `LOAD_LW, 5'd30, `OPCODE_LOAD};								// LW x30, 0(x28): Status 레지스터 읽기
		data[61] = {12'd1, 5'd30, `ITYPE_ANDI, 5'd30, `OPCODE_ITYPE};							// ANDI x30, x30, 1: busy bit 마스킹
		data[62] = {1'b1, 6'b111111, 5'd0, 5'd30, `BRANCH_BNE, 4'b1100, 1'b1, `OPCODE_BRANCH}; 	// BNE x30, x0, -8: busy이면 data[60]로 재시도
		data[63] = {7'd0, 5'd31, 5'd29, `STORE_SB, 5'd0, `OPCODE_STORE};						// SB: mem[x29+0] = 'A'

		// 'B' 전송
		data[64] = {12'h042, 5'd0, `ITYPE_ADDI, 5'd31, `OPCODE_ITYPE};							// ADDI: x31 = 'B' (0x42)
		data[65] = {12'd0, 5'd28, `LOAD_LW, 5'd30, `OPCODE_LOAD};								// LW x30, 0(x28): Status 레지스터 읽기
		data[66] = {12'd1, 5'd30, `ITYPE_ANDI, 5'd30, `OPCODE_ITYPE};							// ANDI x30, x30, 1: busy bit 마스킹
		data[67] = {1'b1, 6'b111111, 5'd0, 5'd30, `BRANCH_BNE, 4'b1100, 1'b1, `OPCODE_BRANCH}; 	// BNE x30, x0, -8: busy이면 data[65]로 재시도
		data[68] = {7'd0, 5'd31, 5'd29, `STORE_SB, 5'd0, `OPCODE_STORE};						// SB: mem[x29+0] = 'B'

		// 'A' 전송
		data[69] = {12'h041, 5'd0, `ITYPE_ADDI, 5'd31, `OPCODE_ITYPE};							// ADDI: x31 = 'A' (0x41)
		data[70] = {12'd0, 5'd28, `LOAD_LW, 5'd30, `OPCODE_LOAD};								// LW x30, 0(x28): Status 레지스터 읽기
		data[71] = {12'd1, 5'd30, `ITYPE_ANDI, 5'd30, `OPCODE_ITYPE};							// ANDI x30, x30, 1: busy bit 마스킹
		data[72] = {1'b1, 6'b111111, 5'd0, 5'd30, `BRANCH_BNE, 4'b1100, 1'b1, `OPCODE_BRANCH}; 	// BNE x30, x0, -8: busy이면 data[70]로 재시도
		data[73] = {7'd0, 5'd31, 5'd29, `STORE_SB, 5'd0, `OPCODE_STORE};						// SB: mem[x29+0] = 'A'

		// 'D' 전송
		data[74] = {12'h044, 5'd0, `ITYPE_ADDI, 5'd31, `OPCODE_ITYPE};							// ADDI: x31 = 'D' (0x44)
		data[75] = {12'd0, 5'd28, `LOAD_LW, 5'd30, `OPCODE_LOAD};								// LW x30, 0(x28): Status 레지스터 읽기
		data[76] = {12'd1, 5'd30, `ITYPE_ANDI, 5'd30, `OPCODE_ITYPE};							// ANDI x30, x30, 1: busy bit 마스킹
		data[77] = {1'b1, 6'b111111, 5'd0, 5'd30, `BRANCH_BNE, 4'b1100, 1'b1, `OPCODE_BRANCH}; 	// BNE x30, x0, -8: busy이면 data[75]로 재시도
		data[78] = {7'd0, 5'd31, 5'd29, `STORE_SB, 5'd0, `OPCODE_STORE};						// SB: mem[x29+0] = 'D'
		// 'B' 전송
		data[79] = {12'h042, 5'd0, `ITYPE_ADDI, 5'd31, `OPCODE_ITYPE};							// ADDI: x31 = 'B' (0x42)
		data[80] = {12'd0, 5'd28, `LOAD_LW, 5'd30, `OPCODE_LOAD};								// LW x30, 0(x28): Status 레지스터 읽기
		data[81] = {12'd1, 5'd30, `ITYPE_ANDI, 5'd30, `OPCODE_ITYPE};							// ANDI x30, x30, 1: busy bit 마스킹
		data[82] = {1'b1, 6'b111111, 5'd0, 5'd30, `BRANCH_BNE, 4'b1100, 1'b1, `OPCODE_BRANCH}; 	// BNE x30, x0, -8: busy이면 data[80]로 재시도
		data[83] = {7'd0, 5'd31, 5'd29, `STORE_SB, 5'd0, `OPCODE_STORE};						// SB: mem[x29+0] = 'B'

		// 'E' 전송
		data[84] = {12'h045, 5'd0, `ITYPE_ADDI, 5'd31, `OPCODE_ITYPE};							// ADDI: x31 = 'E' (0x45)
		data[85] = {12'd0, 5'd28, `LOAD_LW, 5'd30, `OPCODE_LOAD};								// LW x30, 0(x28): Status 레지스터 읽기
		data[86] = {12'd1, 5'd30, `ITYPE_ANDI, 5'd30, `OPCODE_ITYPE};							// ANDI x30, x30, 1: busy bit 마스킹
		data[87] = {1'b1, 6'b111111, 5'd0, 5'd30, `BRANCH_BNE, 4'b1100, 1'b1, `OPCODE_BRANCH}; 	// BNE x30, x0, -8: busy이면 data[85]로 재시도
		data[88] = {7'd0, 5'd31, 5'd29, `STORE_SB, 5'd0, `OPCODE_STORE};						// SB: mem[x29+0] = 'E'
		// 'B' 전송
		data[89] = {12'h042, 5'd0, `ITYPE_ADDI, 5'd31, `OPCODE_ITYPE};							// ADDI: x31 = 'B' (0x42)
		data[90] = {12'd0, 5'd28, `LOAD_LW, 5'd30, `OPCODE_LOAD};								// LW x30, 0(x28): Status 레지스터 읽기
		data[91] = {12'd1, 5'd30, `ITYPE_ANDI, 5'd30, `OPCODE_ITYPE};							// ANDI x30, x30, 1: busy bit 마스킹
		data[92] = {1'b1, 6'b111111, 5'd0, 5'd30, `BRANCH_BNE, 4'b1100, 1'b1, `OPCODE_BRANCH}; 	// BNE x30, x0, -8: busy이면 data[90]로 재시도
		data[93] = {7'd0, 5'd31, 5'd29, `STORE_SB, 5'd0, `OPCODE_STORE};						// SB: mem[x29+0] = 'B'

		// 'E' 전송
		data[94] = {12'h045, 5'd0, `ITYPE_ADDI, 5'd31, `OPCODE_ITYPE};							// ADDI: x31 = 'E' (0x45)
		data[95] = {12'd0, 5'd28, `LOAD_LW, 5'd30, `OPCODE_LOAD};								// LW x30, 0(x28): Status 레지스터 읽기
		data[96] = {12'd1, 5'd30, `ITYPE_ANDI, 5'd30, `OPCODE_ITYPE};							// ANDI x30, x30, 1: busy bit 마스킹
		data[97] = {1'b1, 6'b111111, 5'd0, 5'd30, `BRANCH_BNE, 4'b1100, 1'b1, `OPCODE_BRANCH}; 	// BNE x30, x0, -8: busy이면 data[95]로 재시도
		data[98] = {7'd0, 5'd31, 5'd29, `STORE_SB, 5'd0, `OPCODE_STORE};						// SB: mem[x29+0] = 'E'

		data[99] = {1'b1, 10'b1110101000, 1'b1, 8'b11111111, 5'd0, `OPCODE_JAL};		// JAL x0, -176: data[55]로 분기 (EBREAK로 돌아가기)

		// ──────────────────────────────────────────────
		// RV64I 확장 명령어 테스트 블록 (data[100] ~)
		// - 6-bit shamt: SLLI/SRLI/SRAI 및 SLL/SRL/SRA
		// - OP-IMM-32: ADDIW/SLLIW/SRLIW/SRAIW
		// - OP-32: ADDW/SUBW/SLLW/SRLW/SRAW
		// - LOAD/STORE: LW/LWU/LD/SD
		// (data[54]에서 이 블록으로 점프 후, 마지막에 data[57]로 복귀)

		// x1 = 0x10000200 (8-byte aligned RAM base)
		data[100] = {20'h10000, 5'd1, `OPCODE_LUI};									// LUI:  x1 = 0x10000000
		data[101] = {12'h200, 5'd1, `ITYPE_ADDI, 5'd1, `OPCODE_ITYPE};				// ADDI: x1 = x1 + 0x200 = 0x10000200

		// x6 = 0x000000009ABC5678 (하위 32비트가 음수인 패턴, 상위는 0으로 정리)
		data[102] = {20'h9ABC5, 5'd6, `OPCODE_LUI};									// LUI:  x6 = 0xFFFF_FFFF_9ABC5000 (sign-extended)
		data[103] = {12'h678, 5'd6, `ITYPE_ADDI, 5'd6, `OPCODE_ITYPE};				// ADDI: x6 = x6 + 0x678 = 0xFFFF_FFFF_9ABC5678
		data[104] = {6'b000000, 6'd32, 5'd6, `ITYPE_SLLI, 5'd6, `OPCODE_ITYPE};		// SLLI: x6 = x6 << 32 = 0x9ABC5678_00000000  (6-bit shamt)
		data[105] = {6'b000000, 6'd32, 5'd6, `ITYPE_SRXI, 5'd6, `OPCODE_ITYPE};		// SRLI: x6 = x6 >> 32 = 0x00000000_9ABC5678  (6-bit shamt)

		// x5 = 0x1234567800000000 만들고, x6와 OR 해서 0x123456789ABC5678 구성
		data[106] = {20'h12345, 5'd5, `OPCODE_LUI};									// LUI:  x5 = 0x0000_0000_12345000
		data[107] = {12'h678, 5'd5, `ITYPE_ADDI, 5'd5, `OPCODE_ITYPE};				// ADDI: x5 = x5 + 0x678 = 0x0000_0000_12345678
		data[108] = {6'b000000, 6'd32, 5'd5, `ITYPE_SLLI, 5'd5, `OPCODE_ITYPE};		// SLLI: x5 = x5 << 32 = 0x12345678_00000000  (6-bit shamt)
		data[109] = {7'b0000000, 5'd6, 5'd5, `RTYPE_OR, 5'd5, `OPCODE_RTYPE};		// OR:   x5 = x5 | x6 = 0x12345678_9ABC5678

		// SD/LD/LW/LWU 테스트
		data[110] = {7'd0, 5'd5, 5'd1, `STORE_SD, 5'd0, `OPCODE_STORE};				// SD:   mem[x1+0] = x5
		data[111] = {12'd0, 5'd1, `LOAD_LD, 5'd7, `OPCODE_LOAD};					// LD:   x7  = mem[x1+0] (== x5)
		data[112] = {12'd0, 5'd1, `LOAD_LW, 5'd8, `OPCODE_LOAD};					// LW:   x8  = signext(mem[x1+0][31:0]) = 0xFFFF_FFFF_9ABC5678
		data[113] = {12'd0, 5'd1, `LOAD_LWU, 5'd9, `OPCODE_LOAD};					// LWU:  x9  = zeroext(mem[x1+0][31:0]) = 0x0000_0000_9ABC5678

		// x10 = 40 (0x28) : R-type shift에서 6-bit shamt 동작 확인
		data[114] = {12'd40, 5'd0, `ITYPE_ADDI, 5'd10, `OPCODE_ITYPE};				// ADDI: x10 = 40

		// x13 = 0x8000000000000001 만들기 (SLLI 63도 6-bit shamt 검증)
		data[115] = {12'd1, 5'd0, `ITYPE_ADDI, 5'd13, `OPCODE_ITYPE};				// ADDI: x13 = 1
		data[116] = {6'b000000, 6'd63, 5'd13, `ITYPE_SLLI, 5'd13, `OPCODE_ITYPE};	// SLLI: x13 = x13 << 63 = 0x8000_0000_0000_0000
		data[117] = {12'd1, 5'd13, `ITYPE_ORI, 5'd13, `OPCODE_ITYPE};				// ORI:  x13 = x13 | 1  = 0x8000_0000_0000_0001

		// I-type SRLI/SRAI (6-bit shamt = 40) 비교
		data[118] = {6'b000000, 6'd40, 5'd13, `ITYPE_SRXI, 5'd14, `OPCODE_ITYPE};	// SRLI: x14 = x13 >> 40  = 0x0000_0000_0080_0000
		data[119] = {6'b010000, 6'd40, 5'd13, `ITYPE_SRXI, 5'd15, `OPCODE_ITYPE};	// SRAI: x15 = x13 >>>40  = 0xFFFF_FFFF_FF80_0000

		// R-type SRL/SRA/SLL (rs2=40 -> 6-bit shamt) 비교
		data[120] = {7'b0000000, 5'd10, 5'd13, `RTYPE_SRX, 5'd16, `OPCODE_RTYPE};	// SRL:  x16 = x13 >>  x10 = 0x0000_0000_0080_0000
		data[121] = {7'b0100000, 5'd10, 5'd13, `RTYPE_SRX, 5'd17, `OPCODE_RTYPE};	// SRA:  x17 = x13 >>> x10 = 0xFFFF_FFFF_FF80_0000
		data[122] = {7'b0000000, 5'd10, 5'd13, `RTYPE_SLL, 5'd18, `OPCODE_RTYPE};	// SLL:  x18 = x13 <<  x10 = 0x0000_0100_0000_0000

		// OP-IMM-32: ADDIW (x9의 하위 32비트 부호확장 확인)
		data[123] = {12'd0, 5'd9, `ITYPE_ADDI, 5'd19, `OPCODE_ITYPE_WORD};			// ADDIW: x19 = signext32(x9 + 0) = 0xFFFF_FFFF_9ABC5678
		data[124] = {12'd1, 5'd19, `ITYPE_ADDI, 5'd20, `OPCODE_ITYPE_WORD};			// ADDIW: x20 = x19 + 1 = 0xFFFF_FFFF_9ABC5679

		// OP-32: ADDW / SUBW
		data[125] = {7'b0000000, 5'd13, 5'd19, `RTYPE_ADDSUB, 5'd21, `OPCODE_RTYPE_WORD};	// ADDW: x21 = sext32(x19[31:0] + x13[31:0]) = 0xFFFF_FFFF_9ABC5679
		data[126] = {7'b0100000, 5'd13, 5'd19, `RTYPE_ADDSUB, 5'd31, `OPCODE_RTYPE_WORD};	// SUBW: x31 = sext32(x19[31:0] - x13[31:0]) = 0xFFFF_FFFF_9ABC5677

		// W-Shift (rs2 = 8)
		data[127] = {12'd8, 5'd0, `ITYPE_ADDI, 5'd24, `OPCODE_ITYPE};						// ADDI: x24 = 8
		data[128] = {7'b0000000, 5'd24, 5'd19, `RTYPE_SLL, 5'd25, `OPCODE_RTYPE_WORD};		// SLLW: x25 = (x19[31:0] << 8)  = 0xFFFF_FFFF_BC56_7800
		data[129] = {7'b0000000, 5'd24, 5'd19, `RTYPE_SRX, 5'd26, `OPCODE_RTYPE_WORD};		// SRLW: x26 = (x19[31:0] >> 8)  = 0x0000_0000_009A_BC56
		data[130] = {7'b0100000, 5'd24, 5'd19, `RTYPE_SRX, 5'd27, `OPCODE_RTYPE_WORD};		// SRAW: x27 = (x19[31:0] >>>8)  = 0xFFFF_FFFF_FF9A_BC56

		// OP-IMM-32 Shift: SLLIW / SRLIW / SRAIW
		data[131] = {7'b0000000, 5'd8, 5'd19, `ITYPE_SLLI, 5'd28, `OPCODE_ITYPE_WORD};		// SLLIW: x28 = (x19[31:0] << 8)  = 0xFFFF_FFFF_BC56_7800
		data[132] = {7'b0000000, 5'd8, 5'd19, `ITYPE_SRXI, 5'd29, `OPCODE_ITYPE_WORD};		// SRLIW: x29 = (x19[31:0] >> 8)  = 0x0000_0000_009A_BC56
		data[133] = {7'b0100000, 5'd8, 5'd19, `ITYPE_SRXI, 5'd30, `OPCODE_ITYPE_WORD};		// SRAIW: x30 = (x19[31:0] >>>8)  = 0xFFFF_FFFF_FF9A_BC56

		// ──────────────────────────────────────────────
		// RV64M 확장 명령어 테스트 블록 (data[134] ~)
		// MUL, MULH, MULHSU, MULHU, MULW 테스트
		// M extension: funct7 = 7'b0000001

		// ── 테스트용 값 설정: 간단한 곱셈 검증용 ──
		data[134] = {12'd7, 5'd0, `ITYPE_ADDI, 5'd2, `OPCODE_ITYPE};						// ADDI: x2 = 7
		data[135] = {12'd13, 5'd0, `ITYPE_ADDI, 5'd3, `OPCODE_ITYPE};						// ADDI: x3 = 13
		data[136] = {12'hFFB, 5'd0, `ITYPE_ADDI, 5'd4, `OPCODE_ITYPE};						// ADDI: x4 = -5 = 0xFFFF_FFFF_FFFF_FFFB

		// MUL 테스트 (곱셈 결과의 하위 64비트) 
		// {funct7=0000001, rs2, rs1, funct3=000, rd, OPCODE_RTYPE}
		data[137] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE};				// MUL: x11 = x2 * x3 = 7 * 13 = 91 = 0x0000_0000_0000_005B
		data[138] = {7'b0000001, 5'd4, 5'd3, `RTYPE_MUL, 5'd12, `OPCODE_RTYPE};				// MUL: x12 = x3 * x4 = 13 * (-5) = -65 = 0xFFFF_FFFF_FFFF_FFBF
		
		// 큰 수 곱셈: x8 * x9 (기존 레지스터 활용)
		// x8 = 0xFFFF_FFFF_9ABC_5678 (signed: -1,698,898,312)
		// x9 = 0x0000_0000_9ABC_5678 (unsigned: 2,596,069,496)
		// x8 * x9 (signed 128비트) = 0xFFFF_FFFF_FFFF_FFFF_C2B5_F41B_4F5C_5840
		data[139] = {7'b0000001, 5'd9, 5'd8, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE};				// MUL: x11 = (x8 * x9)[63:0] = 0xC2CA_CC1F_7D74_D840

		// MULH 테스트 (signed × signed, 상위 64비트)
		// {funct7=0000001, rs2, rs1, funct3=001, rd, OPCODE_RTYPE}
		data[140] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MULH, 5'd12, `OPCODE_RTYPE};			// MULH: x12 = (x2 * x3)[127:64] = 0 (작은 양수 곱)
		data[141] = {7'b0000001, 5'd4, 5'd3, `RTYPE_MULH, 5'd11, `OPCODE_RTYPE};			// MULH: x11 = (x3 * x4)[127:64] = 0xFFFF_FFFF_FFFF_FFFF (음수 결과 부호확장)
		
		// x8 * x9 (signed) = -4,410,039,189,025,044,352
		// 128비트: 0xFFFF_FFFF_FFFF_FFFF_C2B5_F41B_4F5C_5840
		data[142] = {7'b0000001, 5'd9, 5'd8, `RTYPE_MULH, 5'd12, `OPCODE_RTYPE};			// MULH: x12 = (x8 * x9)[127:64] = 0xFFFF_FFFF_FFFF_FFFF

		// MULHU 테스트 (unsigned × unsigned, 상위 64비트)
		// {funct7=0000001, rs2, rs1, funct3=011, rd, OPCODE_RTYPE}
		// x4 as unsigned = 0xFFFF_FFFF_FFFF_FFFB = 18,446,744,073,709,551,611
		// x3 * x4 (unsigned) = 13 * 18,446,744,073,709,551,611
		// 128비트: 0x0000_0000_0000_000C_FFFF_FFFF_FFFF_FFC1
		data[143] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MULHU, 5'd11, `OPCODE_RTYPE};			// MULHU: x11 = 0 (작은 양수 곱, 상위 없음)
		data[144] = {7'b0000001, 5'd4, 5'd3, `RTYPE_MULHU, 5'd12, `OPCODE_RTYPE};			// MULHU: x12 = 0x0000_0000_0000_000C = 12
		
		// x8 * x9 as unsigned:
		// x8 = 0xFFFF_FFFF_9ABC_5678 = 18,446,744,071,560,653,432
		// x9 = 0x0000_0000_9ABC_5678 = 2,596,069,496
		// 곱 (128비트) = 0x0000_0000_9ABC_5677_C2B5_F41B_4F5C_5840
		data[145] = {7'b0000001, 5'd9, 5'd8, `RTYPE_MULHU, 5'd11, `OPCODE_RTYPE};			// MULHU: x11 = 0x0000_0000_9ABC_5677

		// MULHSU 테스트 (signed × unsigned, 상위 64비트)
		// rs1 (signed) × rs2 (unsigned)
		// {funct7=0000001, rs2, rs1, funct3=010, rd, OPCODE_RTYPE}
		// x4 (signed: -5) × x3 (unsigned: 13) = -65
		// 128비트: 0xFFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFBF
		data[146] = {7'b0000001, 5'd3, 5'd4, `RTYPE_MULHSU, 5'd12, `OPCODE_RTYPE};			// MULHSU: x12 = 0xFFFF_FFFF_FFFF_FFFF

		// x8 (signed: -1,698,898,312) × x9 (unsigned: 2,596,069,496)
		// = -4,410,039,189,025,044,352
		// 128비트: 0xFFFF_FFFF_FFFF_FFFF_C2B5_F41B_4F5C_5840
		data[147] = {7'b0000001, 5'd9, 5'd8, `RTYPE_MULHSU, 5'd11, `OPCODE_RTYPE};			// MULHSU: x11 = 0xFFFF_FFFF_FFFF_FFFF

		// MULW 테스트 (32비트 곱셈, 결과 부호확장)
		// MULW: opcode = OPCODE_RTYPE_WORD (0111011), funct7 = 0000001, funct3 = 000
		data[148] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd12, `OPCODE_RTYPE_WORD};		// MULW: x12 = sext32(x2[31:0] * x3[31:0]) = sext32(7 * 13) = 91 = 0x0000_0000_0000_005B
		data[149] = {7'b0000001, 5'd4, 5'd3, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE_WORD};		// MULW: x11 = sext32(x3[31:0] * x4[31:0]) = sext32(13 * 0xFFFFFFFB) = sext32(-65) = 0xFFFF_FFFF_FFFF_FFBF

		// MULW with larger 32-bit values:
		// x8[31:0] = 0x9ABC5678, x9[31:0] = 0x9ABC5678
		// 0x9ABC5678 * 0x9ABC5678 (32비트 signed 곱의 하위 32비트)
		// = (-1,698,898,312) * (-1,698,898,312) 의 하위 32비트
		// = 2,886,217,038,337,505,344 의 하위 32비트 = 0x4F5C5840
		// sext32(0x4F5C5840) = 0x0000_0000_4F5C_5840 (MSB=0, 양수)
		data[150] = {7'b0000001, 5'd9, 5'd8, `RTYPE_MUL, 5'd12, `OPCODE_RTYPE_WORD};		// MULW: x12 = sext32(0x9ABC5678 * 0x9ABC5678) = 0x0000_0000_7D74_D840

		// 큰 음수 결과 MULW 테스트:
		// x19[31:0] = 0x9ABC5678 (signed 32-bit: -1,698,898,312)
		// x3 = 13
		// (-1,698,898,312) * 13 = -22,085,678,056
		// 하위 32비트 = 0x7D2C7088 (MSB=0 -> 양수로 sign-extend)
		data[151] = {7'b0000001, 5'd3, 5'd19, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE_WORD};		// MULW: x11 = sext32(0x9ABC5678 * 13) = 0xFFFF_FFFF_DB90_6418

		// MULW: 32비트 overflow로 음수 결과 생성 테스트
		// x6[31:0] = 0x9ABC5678, x10 = 40
		// 0x9ABC5678 * 40 하위 32비트 = 0xB6D50E00 (MSB=1, 음수로 sign-extend)
		data[152] = {7'b0000001, 5'd10, 5'd6, `RTYPE_MUL, 5'd12, `OPCODE_RTYPE_WORD};		// MULW: x12 = sext32(0x9ABC5678 * 40) = 0x0000_0000_2D6D_82C0

		// ──────────────────────────────────────────────
		// RV64M 확장 명령어 테스트 블록 - Division 추가 (data[153] ~)
		// DIV, DIVU, REM, REMU, DIVW, DIVUW, REMW, REMUW 테스트
		// M extension: funct7 = 7'b0000001

		// ── 기존 레지스터 값 참조 ──
		// x2 = 7, x3 = 13, x4 = -5 (0xFFFF_FFFF_FFFF_FFFB)
		// x8 = 0xFFFF_FFFF_9ABC_5678, x9 = 0x0000_0000_9ABC_5678

		// 추가 테스트 값 설정
		data[153] = {12'd100, 5'd0, `ITYPE_ADDI, 5'd20, `OPCODE_ITYPE};					// ADDI: x20 = 100
		data[154] = {12'd0, 5'd0, `ITYPE_ADDI, 5'd21, `OPCODE_ITYPE};					// ADDI: x21 = 0 (divide by zero 테스트용)
		data[155] = {12'hFFF, 5'd0, `ITYPE_ADDI, 5'd15, `OPCODE_ITYPE};					// ADDI: x15 = -1 (0xFFFF_FFFF_FFFF_FFFF)

		// ── DIV 테스트 (signed division) ──
		// {funct7=0000001, rs2, rs1, funct3=100, rd, OPCODE_RTYPE}
		data[156] = {7'b0000001, 5'd2, 5'd20, `RTYPE_DIV, 5'd11, `OPCODE_RTYPE};			// DIV: x11 = x20 / x2 = 100 / 7 = 14 = 0x0000_0000_0000_000E
		data[157] = {7'b0000001, 5'd3, 5'd4, `RTYPE_DIV, 5'd12, `OPCODE_RTYPE};			// DIV: x12 = x4 / x3 = -5 / 13 = 0 = 0x0000_0000_0000_0000
		data[158] = {7'b0000001, 5'd4, 5'd20, `RTYPE_DIV, 5'd11, `OPCODE_RTYPE};			// DIV: x11 = x20 / x4 = 100 / (-5) = -20 = 0xFFFF_FFFF_FFFF_FFEC

		// DIV by zero: 결과 = -1 (0xFFFF_FFFF_FFFF_FFFF)
		data[159] = {7'b0000001, 5'd21, 5'd20, `RTYPE_DIV, 5'd12, `OPCODE_RTYPE};		// DIV: x12 = x20 / x21 = 100 / 0 = -1 = 0xFFFF_FFFF_FFFF_FFFF

		// DIV overflow: MIN_INT64 / -1 = MIN_INT64 (overflow case)
		// x23 = 0x8000_0000_0000_0000 (MIN_INT64)
		data[160] = {12'h800, 5'd0, `ITYPE_ADDI, 5'd16, `OPCODE_ITYPE};					// ADDI: x16 = 0xFFFF_FFFF_FFFF_F800
		data[161] = {12'd52, 5'd16, `ITYPE_SLLI, 5'd16, `OPCODE_ITYPE};					// SLLI: x16 = x16 << 52 = 0x8000_0000_0000_0000
		data[162] = {7'b0000001, 5'd15, 5'd16, `RTYPE_DIV, 5'd11, `OPCODE_RTYPE};		// DIV: x11 = MIN_INT64 / (-1) = MIN_INT64  , 0x8000_0000_0000_0000

		// ── DIVU 테스트 (unsigned division) ──
		// {funct7=0000001, rs2, rs1, funct3=101, rd, OPCODE_RTYPE}
		data[163] = {7'b0000001, 5'd2, 5'd20, `RTYPE_DIVU, 5'd12, `OPCODE_RTYPE};		// DIVU: x12 = x20 / x2 = 100 / 7 = 14 = 0x0000_0000_0000_000E
		data[164] = {7'b0000001, 5'd3, 5'd4, `RTYPE_DIVU, 5'd11, `OPCODE_RTYPE};			// DIVU: x11 = x4 / x3 = 0xFFFFFFFFFFFFFFFB / 13 = 0x13B13B13B13B13B0

		// DIVU by zero: 결과 = MAX_UINT64 (0xFFFF_FFFF_FFFF_FFFF)
		data[165] = {7'b0000001, 5'd21, 5'd20, `RTYPE_DIVU, 5'd12, `OPCODE_RTYPE};		// DIVU: x12 = x20 / x21 = 100 / 0 = 0xFFFF_FFFF_FFFF_FFFF 

		// ── REM 테스트 (signed remainder) ──
		// {funct7=0000001, rs2, rs1, funct3=110, rd, OPCODE_RTYPE}
		data[166] = {7'b0000001, 5'd2, 5'd20, `RTYPE_REM, 5'd11, `OPCODE_RTYPE};			// REM: x11 = x20 % x2 = 100 % 7 = 2 = 0x0000_0000_0000_0002
		data[167] = {7'b0000001, 5'd3, 5'd4, `RTYPE_REM, 5'd12, `OPCODE_RTYPE};			// REM: x12 = x4 % x3 = -5 % 13 = -5 = 0xFFFF_FFFF_FFFF_FFFB
		data[168] = {7'b0000001, 5'd4, 5'd20, `RTYPE_REM, 5'd11, `OPCODE_RTYPE};			// REM: x11 = x20 % x4 = 100 % (-5) = 0 = 0x0000_0000_0000_0000

		// REM by zero: 결과 = dividend (x20 = 100)
		data[169] = {7'b0000001, 5'd21, 5'd20, `RTYPE_REM, 5'd12, `OPCODE_RTYPE};		// REM: x12 = x20 % x21 = 100 % 0 = 100 = 0x0000_0000_0000_0064 

		// REM overflow: MIN_INT64 % -1 = 0
		data[170] = {7'b0000001, 5'd15, 5'd16, `RTYPE_REM, 5'd11, `OPCODE_RTYPE};		// REM: x11 = MIN_INT64 % (-1) = 0

		// ── REMU 테스트 (unsigned remainder) ──
		// {funct7=0000001, rs2, rs1, funct3=111, rd, OPCODE_RTYPE}
		data[171] = {7'b0000001, 5'd2, 5'd20, `RTYPE_REMU, 5'd12, `OPCODE_RTYPE};		// REMU: x12 = x20 % x2 = 100 % 7 = 2 = 0x0000_0000_0000_0002
		data[172] = {7'b0000001, 5'd3, 5'd4, `RTYPE_REMU, 5'd11, `OPCODE_RTYPE};			// REMU: x11 = x4 % x3 = 0xFFFFFFFFFFFFFFFB % 13 = 0x0000_0000_0000_000B = 11

		// REMU by zero: 결과 = dividend (x20 = 100)
		data[173] = {7'b0000001, 5'd21, 5'd20, `RTYPE_REMU, 5'd12, `OPCODE_RTYPE};		// REMU: x12 = x20 % x21 = 100 % 0 = 100 = 0x0000_0000_0000_0064

		// ── DIVW 테스트 (32-bit signed division, sign-extended) ──
		// DIVW: opcode = OPCODE_RTYPE_WORD (0111011), funct7 = 0000001, funct3 = 100
		data[174] = {7'b0000001, 5'd2, 5'd20, `RTYPE_DIV, 5'd11, `OPCODE_RTYPE_WORD};	// DIVW: x11 = sext32(100 / 7) = sext32(14) = 0x0000_0000_0000_000E
		data[175] = {7'b0000001, 5'd3, 5'd4, `RTYPE_DIV, 5'd12, `OPCODE_RTYPE_WORD};		// DIVW: x12 = sext32(x4[31:0] / x3[31:0]) = sext32(-5 / 13) = 0 = 0x0000_0000_0000_0000
		
		// DIVW with 32-bit values:
		// x8[31:0] = 0x9ABC5678 (signed 32-bit: -1,698,898,312)
		// x2 = 7
		// -1,698,898,312 / 7 = -242,699,759 = 0xF18AE8B1
		data[176] = {7'b0000001, 5'd2, 5'd8, `RTYPE_DIV, 5'd11, `OPCODE_RTYPE_WORD};		// DIVW: x11 = sext32(-1,698,898,312 / 7) = 0xFFFF_FFFF_F188_9EA4

		// DIVW by zero: 결과 = -1 (sign-extended)
		data[177] = {7'b0000001, 5'd21, 5'd20, `RTYPE_DIV, 5'd12, `OPCODE_RTYPE_WORD};	// DIVW: x12 = sext32(100 / 0) = 0xFFFF_FFFF_FFFF_FFFF

		// DIVW overflow: MIN_INT32 / -1 = MIN_INT32
		// x24 = 0x80000000 (MIN_INT32)
		data[178] = {12'h800, 5'd0, `ITYPE_ADDI, 5'd17, `OPCODE_ITYPE};					// ADDI: x17 = 0xFFFF_FFFF_FFFF_F800
		data[179] = {12'd20, 5'd17, `ITYPE_SLLI, 5'd17, `OPCODE_ITYPE};					// SLLI: x17 = x17 << 20
		data[180] = {20'h80000, 5'd17, `OPCODE_LUI};										// LUI: x17 = 0xFFFF_FFFF_8000_0000
		data[181] = {7'b0000001, 5'd15, 5'd17, `RTYPE_DIV, 5'd11, `OPCODE_RTYPE_WORD};	// DIVW: x11 = sext32(MIN_INT32 / -1) 

		// ── DIVUW 테스트 (32-bit unsigned division, sign-extended) ──
		// DIVUW: opcode = OPCODE_RTYPE_WORD (0111011), funct7 = 0000001, funct3 = 101
		data[182] = {7'b0000001, 5'd2, 5'd20, `RTYPE_DIVU, 5'd12, `OPCODE_RTYPE_WORD};	// DIVUW: x12 = sext32(100 / 7) = sext32(14) = 0x0000_0000_0000_000E
		
		// x8[31:0] = 0x9ABC5678 (unsigned 32-bit: 2,596,068,984)
		// 2,596,068,984 / 7 = 370,866,997 = 0x161C4DD5
		data[183] = {7'b0000001, 5'd2, 5'd8, `RTYPE_DIVU, 5'd11, `OPCODE_RTYPE_WORD};	// DIVUW: x11 = sext32(0x9ABC5678 / 7) = 0x0000_0000_161A_E7C8

		// DIVUW by zero: 결과 = 0xFFFFFFFF (sign-extended = -1)
		data[184] = {7'b0000001, 5'd21, 5'd20, `RTYPE_DIVU, 5'd12, `OPCODE_RTYPE_WORD};	// DIVUW: x12 = sext32(100 / 0) = sext32(0xFFFFFFFF) = 0xFFFF_FFFF_FFFF_FFFF

		// ── REMW 테스트 (32-bit signed remainder, sign-extended) ──
		// REMW: opcode = OPCODE_RTYPE_WORD (0111011), funct7 = 0000001, funct3 = 110
		data[185] = {7'b0000001, 5'd2, 5'd20, `RTYPE_REM, 5'd11, `OPCODE_RTYPE_WORD};	// REMW: x11 = sext32(100 % 7) = sext32(2) = 0x0000_0000_0000_0002
		data[186] = {7'b0000001, 5'd3, 5'd4, `RTYPE_REM, 5'd12, `OPCODE_RTYPE_WORD};		// REMW: x12 = sext32(x4[31:0] % x3[31:0]) = sext32(-5 % 13) = sext32(-5) = 0xFFFF_FFFF_FFFF_FFFB

		// x8[31:0] = 0x9ABC5678 (signed 32-bit: -1,698,898,312)
		// -1,698,898,312 % 7 = -6 = 0xFFFF_FFFA
		data[187] = {7'b0000001, 5'd2, 5'd8, `RTYPE_REM, 5'd11, `OPCODE_RTYPE_WORD};		// REMW: x11 = sext32(-1,698,898,312 % 7) = sext32(-6) = 0xFFFF_FFFF_FFFF_FFFC

		// REMW by zero: 결과 = dividend (x20[31:0] = 100, sign-extended)
		data[188] = {7'b0000001, 5'd21, 5'd20, `RTYPE_REM, 5'd12, `OPCODE_RTYPE_WORD};	// REMW: x12 = sext32(100 % 0) = sext32(100) = 0x0000_0000_0000_0064

		// REMW overflow: MIN_INT32 % -1 = 0
		data[189] = {7'b0000001, 5'd15, 5'd17, `RTYPE_REM, 5'd11, `OPCODE_RTYPE_WORD};	// REMW: x11 = sext32(MIN_INT32 % -1) = 0

		// ── REMUW 테스트 (32-bit unsigned remainder, sign-extended) ──
		// REMUW: opcode = OPCODE_RTYPE_WORD (0111011), funct7 = 0000001, funct3 = 111
		data[190] = {7'b0000001, 5'd2, 5'd20, `RTYPE_REMU, 5'd12, `OPCODE_RTYPE_WORD};	// REMUW: x12 = sext32(100 % 7) = sext32(2) = 0x0000_0000_0000_0002

		// x8[31:0] = 0x9ABC5678 (unsigned 32-bit: 2,596,068,984)
		// 2,596,068,984 % 7 = 5
		data[191] = {7'b0000001, 5'd2, 5'd8, `RTYPE_REMU, 5'd11, `OPCODE_RTYPE_WORD};	// REMUW: x11 = sext32(0x9ABC5678 % 7) = sext32(5) = 0x0000_0000_0000_0000

		// REMUW by zero: 결과 = dividend[31:0] (x20[31:0] = 100, sign-extended)
		data[192] = {7'b0000001, 5'd21, 5'd20, `RTYPE_REMU, 5'd12, `OPCODE_RTYPE_WORD};	// REMUW: x12 = sext32(100 % 0) = sext32(100) = 0x0000_0000_0000_0064

		// 추가 edge case: 음수 결과가 sign-extend되는 REMUW
		// x24 = 0x80000000, x3 = 13
		// 0x80000000 % 13 = 2,147,483,648 % 13 = 11
		data[193] = {7'b0000001, 5'd3, 5'd17, `RTYPE_REMU, 5'd11, `OPCODE_RTYPE_WORD};	// REMUW: x11 = sext32(0x80000000 % 13) = 0x0000_0000_0000_000B

		// ── 복귀 점프 ──
		// data[57]로 복귀: (57 - 194) * 4 = -548 바이트
		// ── 추가 파이프라인 스트레스 테스트 블록으로 점프 ──
		// data[197]로 점프: (197 - 194) * 4 = +12 바이트
		// ══════════════════════════════════════════════════════
		// TEST 1: MULW 결과를 바로 다음 명령어에서 사용 (EX2 Forwarding)
		// ══════════════════════════════════════════════════════
		// MULW x11, x2, x3  -> x11 = sext32(7 * 13) = 91
		// ADD  x12, x11, x2 -> x12 = 91 + 7 = 98 (x11 forwarding from EX2)
		data[194] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE_WORD};   // MULW: x11 = 91
		data[195] = {7'b0000000, 5'd2, 5'd11, `RTYPE_ADDSUB, 5'd12, `OPCODE_RTYPE};    // ADD:  x12 = x11 + x2 = 98 = 0x62

		// ══════════════════════════════════════════════════════
		// TEST 2: MUL(64-bit) 결과를 바로 사용 (EX2 Forwarding)
		// ══════════════════════════════════════════════════════
		data[196] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE};        // MUL:  x11 = 91
		data[197] = {7'b0000000, 5'd3, 5'd11, `RTYPE_ADDSUB, 5'd13, `OPCODE_RTYPE};    // ADD:  x13 = x11 + x3 = 104 = 0x68

		// ══════════════════════════════════════════════════════
		// TEST 3: MULW → MUL 연속 (32-bit → 64-bit 전환)
		// ══════════════════════════════════════════════════════
		data[198] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE_WORD};   // MULW: x11 = 91
		data[199] = {7'b0000001, 5'd10, 5'd2, `RTYPE_MUL, 5'd14, `OPCODE_RTYPE};       // MUL:  x14 = 7 * 40 = 280 = 0x118

		// ══════════════════════════════════════════════════════
		// TEST 4: MUL → MULW 연속 (64-bit → 32-bit 전환)
		// ══════════════════════════════════════════════════════
		data[200] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE};        // MUL:  x11 = 91
		data[201] = {7'b0000001, 5'd10, 5'd2, `RTYPE_MUL, 5'd15, `OPCODE_RTYPE_WORD};  // MULW: x15 = 280 = 0x118

		// ══════════════════════════════════════════════════════
		// TEST 5: MULW → MULW 연속 (같은 크기, 독립)
		// ══════════════════════════════════════════════════════
		data[202] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE_WORD};   // MULW: x11 = 91
		data[203] = {7'b0000001, 5'd10, 5'd3, `RTYPE_MUL, 5'd16, `OPCODE_RTYPE_WORD};  // MULW: x16 = 520 = 0x208

		// ══════════════════════════════════════════════════════
		// TEST 6: MULW → MULW with dependency (첫번째 결과를 두번째에서 사용)
		// ══════════════════════════════════════════════════════
		data[204] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE_WORD};   // MULW: x11 = 91
		data[205] = {7'b0000001, 5'd2, 5'd11, `RTYPE_MUL, 5'd17, `OPCODE_RTYPE_WORD};  // MULW: x17 = 91 * 7 = 637 = 0x27D

		// ══════════════════════════════════════════════════════
		// TEST 7: MUL → MUL with dependency
		// ══════════════════════════════════════════════════════
		data[206] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE};        // MUL:  x11 = 91
		data[207] = {7'b0000001, 5'd3, 5'd11, `RTYPE_MUL, 5'd18, `OPCODE_RTYPE};       // MUL:  x18 = 91 * 13 = 1183 = 0x49F

		// ══════════════════════════════════════════════════════
		// TEST 8: 3연속 MULW (pipeline stress test)
		// ══════════════════════════════════════════════════════
		data[208] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE_WORD};   // MULW: x11 = 91
		data[209] = {7'b0000001, 5'd10, 5'd3, `RTYPE_MUL, 5'd19, `OPCODE_RTYPE_WORD};  // MULW: x19 = 520
		data[210] = {7'b0000001, 5'd10, 5'd10, `RTYPE_MUL, 5'd25, `OPCODE_RTYPE_WORD}; // MULW: x25 = 1600 = 0x640

		// ══════════════════════════════════════════════════════
		// TEST 9: 3연속 MUL (64-bit pipeline stress test)
		// ══════════════════════════════════════════════════════
		data[211] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE};        // MUL:  x11 = 91
		data[212] = {7'b0000001, 5'd10, 5'd3, `RTYPE_MUL, 5'd25, `OPCODE_RTYPE};       // MUL:  x25 = 520
		data[213] = {7'b0000001, 5'd10, 5'd10, `RTYPE_MUL, 5'd24, `OPCODE_RTYPE};      // MUL:  x24 = 1600

		// ══════════════════════════════════════════════════════
		// TEST 10: MULW → ADD → MULW (간격 두고 연속)
		// ══════════════════════════════════════════════════════
		data[214] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE_WORD};   // MULW: x11 = 91
		data[215] = {7'b0000000, 5'd3, 5'd2, `RTYPE_ADDSUB, 5'd25, `OPCODE_RTYPE};     // ADD:  x25 = 20
		data[216] = {7'b0000001, 5'd2, 5'd25, `RTYPE_MUL, 5'd26, `OPCODE_RTYPE_WORD};  // MULW: x26 = 140 = 0x8C

		// ══════════════════════════════════════════════════════
		// TEST 11: MULW with negative result → 바로 사용
		// ══════════════════════════════════════════════════════
		data[217] = {7'b0000001, 5'd3, 5'd4, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE_WORD};   // MULW: x11 = -65 = 0xFFFF_FFFF_FFFF_FFBF
		data[218] = {7'b0000000, 5'd2, 5'd11, `RTYPE_ADDSUB, 5'd27, `OPCODE_RTYPE};    // ADD:  x27 = -65 + 7 = -58 = 0xFFFF_FFFF_FFFF_FFC6

		// ══════════════════════════════════════════════════════
		// TEST 12: MUL → MULW with forwarding (크기 전환 + 의존성)
		// ══════════════════════════════════════════════════════
		data[219] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE};        // MUL:  x11 = 91
		data[220] = {7'b0000001, 5'd2, 5'd11, `RTYPE_MUL, 5'd28, `OPCODE_RTYPE_WORD};  // MULW: x28 = 637 = 0x27D

		// ══════════════════════════════════════════════════════
		// TEST 13: MULW → MUL with forwarding (크기 전환 + 의존성)
		// ══════════════════════════════════════════════════════
		data[221] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE_WORD};   // MULW: x11 = 91
		data[222] = {7'b0000001, 5'd3, 5'd11, `RTYPE_MUL, 5'd29, `OPCODE_RTYPE};       // MUL:  x29 = 1183 = 0x49F

		// ══════════════════════════════════════════════════════
		// TEST 14: MULW 큰 값 → 바로 사용 (overflow case)
		// ══════════════════════════════════════════════════════
		// x8[31:0] = 0x9ABC5678, x10 = 40
		data[223] = {7'b0000001, 5'd10, 5'd8, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE_WORD};  // MULW: x11 = 0x2D6D82C0
		data[224] = {7'b0000000, 5'd2, 5'd11, `RTYPE_ADDSUB, 5'd30, `OPCODE_RTYPE};    // ADD:  x30 = 0x2D6D82C7

		// ══════════════════════════════════════════════════════
		// TEST 15: Double forwarding test - 두 MUL 결과 간격 후 사용
		// ══════════════════════════════════════════════════════
		data[225] = {7'b0000001, 5'd3, 5'd2, `RTYPE_MUL, 5'd11, `OPCODE_RTYPE_WORD};   // MULW: x11 = 91
		data[226] = {12'h000, 5'd0, `ITYPE_ADDI, 5'd0, `OPCODE_ITYPE};                  // NOP
		data[227] = {12'h000, 5'd0, `ITYPE_ADDI, 5'd0, `OPCODE_ITYPE};                  // NOP
		data[228] = {7'b0000001, 5'd10, 5'd2, `RTYPE_MUL, 5'd14, `OPCODE_RTYPE};       // MUL:  x14 = 280
		data[229] = {7'b0000000, 5'd14, 5'd11, `RTYPE_ADDSUB, 5'd31, `OPCODE_RTYPE};   // ADD:  x31 = 91 + 280 = 371 = 0x173

		// NOP padding
		data[230] = {12'h000, 5'd0, `ITYPE_ADDI, 5'd0, `OPCODE_ITYPE};                  // NOP

		// ── 복귀 점프 ──
		// data[57]로 복귀: (57 - 231) * 4 = -696 바이트
		data[231] = {1'b1, 10'b1010100100, 1'b1, 8'b11111111, 5'd0, `OPCODE_JAL};  // JAL x0, -696
		
		// NOP padding
		data[232] = {12'h000, 5'd0, `ITYPE_ADDI, 5'd0, `OPCODE_ITYPE};                  // NOP
		data[233] = {12'h000, 5'd0, `ITYPE_ADDI, 5'd0, `OPCODE_ITYPE};                  // NOP
        */

		// ──────────────────────────────────────────────
		// Trap Handler 시작 주소. mtvec = 0000_1000 = 4096 ÷ 4 Byte = 1024
		// Trap Handler 진입 시 기존 GPR의 레지스터 내용들을 별도의 메모리 Heap 구역에 store하고 수행해야하지만, 현재 단계에서는 생략함.
		// CSR mcause 확인해서 ecall이면 x1 = 0000_0000으로 만들기, misaligned면 x2에 FF더하기
		// 조건 분기; 비교문 작성을 위한 적재 작업
		data[7000] = {12'h342, 5'd0, 3'b010, 5'd6, `OPCODE_ENVIRONMENT}; 					// csrrs x6, mcause, x0:	레지스터 x6에 mcause값 적재
		data[7001] = {12'd11, 5'd0, `ITYPE_ADDI, 5'd7, `OPCODE_ITYPE};						// addi x7, x0, 11: 		레지스터 x7에 ECALL 코드 값 11 적재
		data[7002] = {12'd2, 5'd0, `ITYPE_ADDI, 5'd8, `OPCODE_ITYPE};						// addi x8, x0, 2: 			레지스터 x8에 ILLEGAL INSTRUCTION 코드 값 2 적재
		data[7003] = {12'd4, 5'd0, `ITYPE_ADDI, 5'd9, `OPCODE_ITYPE};						// addi x9, x0, 4: 			레지스터 x9에 MISALIGNED LOAD 코드 값 4 적재
		data[7004] = {12'd6, 5'd0, `ITYPE_ADDI, 5'd10, `OPCODE_ITYPE};						// addi x10, x0, 6: 		레지스터 x10에 MISALIGNED STORE 코드 값 6 적재

		// mcause 분석해서 해당하는 Trap Handler 주소로 분기
		data[7005] = {1'b0, 6'b0, 5'd7, 5'd6, `BRANCH_BEQ, 4'b1100, 1'b0, `OPCODE_BRANCH};	// beq x6, x7, +24: 		ECALL; x6과 x7이 같다면 24바이트 이후 주솟값으로 분기 = data[1035]
		data[7006] = {1'b0, 6'd0, 5'd0, 5'd6, `BRANCH_BEQ, 4'b1110, 1'b0, `OPCODE_BRANCH};	// beq x6, x0, +28: 		MISALIGNED INSTRUCTION; x6값이 0과 같다면 28바이트 이후 주솟값으로 분기 = data[1037]
		data[7007] = {1'b0, 6'd0, 5'd10, 5'd6, `BRANCH_BEQ, 4'b1100, 1'b0, `OPCODE_BRANCH};	// beq x6, x10, +24: 		MISALIGNED STORE; x6값이 x10과 같다면 24바이트 이후 주솟값으로 분기 = data[1037]
		data[7008] = {1'b0, 6'd0, 5'd9, 5'd6, `BRANCH_BEQ, 4'b1010, 1'b0, `OPCODE_BRANCH};	// beq x6, x9, +20: 		MISALIGNED LOAD; x6값이 x9와 같다면 20바이트 이후 주솟값으로 분기 = data[1037]
		data[7009] = {1'b0, 6'd0, 5'd8, 5'd6, `BRANCH_BEQ, 4'b1000, 1'b0, `OPCODE_BRANCH};	// beq x6, x8, +16: 		ILLEGAL; x6값이 x8과 같다면 16바이트 이후 주솟값으로 분기 = data[1037]
		data[7010] = {1'b0, 10'b000_0001_000, 1'b0, 8'b0, 5'd0, `OPCODE_JAL};				// jal x0, +16: 			TH 끝내기 (mret 명령어 주소로 가기)
		
		// ECALL Trap Handler @ data[1035]
		data[7011] = {12'd0, 5'd0, `ITYPE_ADDI, 5'd1, `OPCODE_ITYPE};						// addi x1, x0, 0: 			레지스터 x1 값 0으로 비우기
		data[7012] = {1'b0, 10'b000_0000_100, 1'b0, 8'b0, 5'd0, `OPCODE_JAL};				// jal x0, +8:				TH 끝내기 (mret 명령어 주소로 가기)

		// ILLEGAL / MISALIGNED Trap Handler @ data[1037]
		data[7013] = {12'hFF, 5'd2, `ITYPE_ADDI, 5'd30, `OPCODE_ITYPE};						// addi x30, x2, 255: 		x30 레지스터에 x2(BC00_0000) + 0xFF = bc00_00ff

		// ESCAPE Trap Handler @ data[1038]
		data[7014] = {12'b001100000010, 5'b0, 3'b0, 5'b0, `OPCODE_ENVIRONMENT};				// MRET: PC = CSR[mepc]

		// HINT; NOP for 'x' signal after MRET in pipeline
		data[7015] = {12'h2BC, 5'd0, `ITYPE_ADDI, 5'd0, `OPCODE_ITYPE};						// ADDI:  x0 = x0 + 2BC = 0000_0000
		data[7016] = {12'h2BC, 5'd0, `ITYPE_ADDI, 5'd0, `OPCODE_ITYPE};						// ADDI:  x0 = x0 + 2BC = 0000_0000
		data[7017] = {12'h2BC, 5'd0, `ITYPE_ADDI, 5'd0, `OPCODE_ITYPE};						// ADDI:  x0 = x0 + 2BC = 0000_0000
		data[7018] = {12'h2BC, 5'd0, `ITYPE_ADDI, 5'd0, `OPCODE_ITYPE};						// ADDI:  x0 = x0 + 2BC = 0000_0000
	end

endmodule