# T11 — Read-only RTL explanations

Paths are relative to `RV-IM100_RTL/project_files/RV32s/SoCs/<project>/…/modules/` (RV64 copies are equivalent).
No files were edited.

## 1. Why JAL/JALR cost +1 cycle on the timing-optimised builds
The jump redirect moves one stage later. JAL and JALR share it: the JAL target is also
formed by the ALU, and there is no early ID-stage JAL redirect.

| build | `PCController` jump inputs | stage |
|---|---|---|
| 7SP_BRAM (`RV64IM72F_6SP.v`, inherited name) | `.jump(EX_jump)` l.648, `.jump_target(alu_result)` l.653 | EX, combinational |
| 7SP_BRAM_Opt (`RV32IM72F_7SP.v`) | `.jump(EX2_jump)` l.643, `.jump_target(EX2_alu_result)` l.648 | EX2, registered |
| 8SP_withoutOpt (`RV64IM72F_8SP.v`) | `.jump(EX_jump)` l.777, `.jump_target(alu_result)` l.782 | EX |
| 8SP (`RV64IM72F_8SP.v`) | `.jump(EX2_jump)` l.913, `.jump_target(EX2_alu_result)` l.918 | EX2 |

This is the "JALR resolution EX→EX2" deferral: it takes the ALU-result → PC path off the
critical path, and every JAL/JALR redirects one cycle later (7SP_BRAM 4 → 7SP_BRAM_Opt 5;
8SP_withoutOpt 5/6 → 8SP 6/7). Conditional branches resolve in EX2 in both builds
(`BranchLogic` is fed from `EX2_*`: `RV32IM72F_7SP.v:362-374`), which is why the branch
penalty does not change between the pair.

## 2. Why 5SP has load-use penalty 0 and 6SP has 1
- **5SP**: data memory is **asynchronous LUTRAM** (`Data_Memory.v:31-39`,
  `always @(*) read_data = memory[ram_address]`). A load in MEM forwards the byte-aligned read
  data (`Forward_Unit.v:108`, `OPCODE_LOAD : MEM_forward_data_value = byte_enable_logic_register_file_write_data`)
  into the EX operand mux **in the same cycle**, so a dependent instruction immediately behind
  the load never stalls. The cost is a long combinational path (MEM address → LUTRAM → byte
  align → forward mux → ALU). The 5SP top has no `load_use_hazard` signal at all.
- **6SP**: EX2 sits between EX and MEM. When the load is in EX2 its address has not reached
  memory, so the consumer in EX must wait: `Hazard_Unit.v:109-112` raises
  `load_use_hazard = ex2_is_load && (EX2_rd == EX_rs1/rs2)` for **one cycle**, after which the
  same combinational MEM forward applies.

## 3. Branch predictor and the `mispred` counter
- **Predictor** (`Branch_Predictor.v`): **one global 2-bit saturating counter**. There is no
  table and no PC index. `branch_estimation = prediction_counter[1]` for any branch in IF.
  The update happens in EX(2) on every conditional branch (`EX_branch`), with the standard
  00/01/10/11 transitions. Every branch in the program shares one counter, which explains the
  ≈41% CoreMark miss rate: interleaved loop branches (mostly taken) and data-dependent
  branches (mostly not taken) keep flipping it.
- **`mispred`** = profile bit 0 = `branch_prediction_miss` (`Branch_Logic.v:40`:
  `branch_estimation != branch_taken`), asserted **only for conditional branches**
  (`if (branch)`). JAL/JALR and correctly predicted taken-branch redirects are **not** counted.
  The profiler counts **rising edges**, so a mispredicting branch held over several stall
  cycles counts once. Two mispredicting branches resolving on consecutive cycles would merge
  into one event (a possible small undercount).

## 4. Why a correctly predicted taken branch costs 2 cycles from 7SP onward
From 7SP on, the IF/IO register sits between fetch and decode and instruction memory
becomes synchronous (BRAM) or registered. The prediction is made from the instruction in
IF, but by then the next sequential fetch has already been issued. `IF_IO_Register.v:35-46`
(7SP_BRAM_Opt line numbers) pays for this explicitly: on `branch_estimation` it squashes the
slot entering IO (bubble 1) and sets `flush_reg`, which squashes the following slot as well
(bubble 2). 5SP/6SP have no IF/IO stage. The predicted target reaches the PC mux in the
branch's own fetch cycle, so the taken-branch excess is 0.

**Consequence found under T6.** The same line gates the squash with `!is_m_extend`
(`is_m_extend = ID_opcode==RTYPE && ID_funct7==1`, l.30). When an M-extension instruction
is in ID at the moment a taken branch is predicted, **both bubbles are skipped**. If the
prediction is correct, nothing downstream flushes the admitted sequential instruction, and
it commits. This is the AAPG divergence (see T6). The exception is present in all ten
7/8-stage tops and absent from 5SP/6SP.
