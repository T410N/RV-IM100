# ISA Extension

## XLEN Expansion

From the base **basic_RV32s**' 46F5SP architecture(RV32IZicsr) we've expanded XLEN bit-width which is the width of the main integer registers.

To support RV64I, existing instructions' functions are changed and new W-suffix instructions replace some of the previous 32-bit XLEN instructions.

- R-Type
  - **SLL, SRL, SRA**
    - Changed to support 6-bit shift amount (shamt). 
  - **ADDW, SUBW, SLLW, SRLW, SRAW**
    - Works same as RV32I ISA.
  - Rest of the instructions
    - Changed to execute 64-bit operations.
- I-Type
  - **SLLI, SRLI, SRAI**
    - Changed to support 6-bit shift amount (shamt). 
  - **LW**
    - Loads 32-bit value but sign-extend the MSB to 64-bit.
  - **LWU**
    - Loads 32-bit value but zero-extend to 64-bit
  - **LD**
    - Loads 64-bit value
  - **ADDIW, SLLIW, SRLIW, SRAIW**
    - Works same as RV32I ISA.
  - Rest of the instructions(*Except LB, LBU, LH, LHU*)
    - Changed to execute 64-bit operations.
- S-Type
  - **SD**	
    - Stores 64-bit value

## M Extension

M-extension is for Integer Multiplication and Division. For Multiplication only, Zmmul extension is part of the M Extension.
This extension adds only R-Type instructions.

- RV32
  - **MUL, MULH, MULHSU, MULHU**
  - **DIV, DIVU**
  - **REM, REMU**
- RV64
  - **MULW, DIVW, DIVUW, REMW, REMUW**
    - Works same as RV32.
  - Rest of the instructions such as MUL, MULH
    - Changed to execute 64-bit operations.

-----

# Pipeline Extension

## Base 5-Stage Pipeline Architecture

![Image of 72F7SP](/docs/diagrams/RV32I46F_5SP.R10.png)

Pipeline stage definitions:

- **IF; Instruction Fetch**(PC-Instruction Memory) 
- **ID; Instruction Decode**(Instruction Decoder-Control Unit-Register File)  
- **EX; Execute**(ALU-Branch Logic)
- **MEM; Memory Access** (Byte Enable Logic - Data Memory) 
- **WB; register Write Back**(Register File)

## 6-Stage Pipeline Architecture

![Image of 72F6SP](/docs/diagrams/RV32I46F_6SP_without_MMIO.drawio.png)

Pipeline stage definitions:

- **IF; Instruction Fetch** (PC-Instruction Memory)
- **ID; Instruction Decode** (Instruction Decoder - Control Unit - Register File)
- **EX; Execute** (ALU)
- **BR; Branch** (Branch Logic)
- **MEM; Memory Access** (Byte Enable Logic - Data Memory)
- **WB; register Write Back** (Register File)

The Critical Path in previous 5-Stage was the **EX stage** where ALU and Branch Logic module operates. 
The datapath to Branch logic to decide whether the instruction should be branched was the most significant length. So we've decided to pipeline the path.

**BR stage(EX2)** is added, so from 6-stage pipeline, EX stage only executes ALU operation and BR stage executes branch decision with Branch Logic.

This pipelining increased Core Fmax from 50MHz to 67MHz in RV64.

## 7-Stage Pipeline Architecture

![Image of 72F7SP](/docs/diagrams/RV32I46F_7SP_handmade_noMMIO.drawio.png)

Pipeline stage definitions:

- **IF; Instruction Fetch** (PC-Instruction Memory)
- **IO; Instruction Order** (Instruction Memory)
- **ID; Instruction Decode** (Instruction Decoder - Control Unit - Register File)
- **EX; Execute** (ALU)
- **BR; Branch** (Branch Logic)
- **MEM; Memory Access** (Byte Enable Logic - Data Memory)
- **WB; register Write Back** (Register File)

The previous architectures were using asynchronous distributed RAM of FPGA (LUTRAM).

The STA(Static Timing Analysis) didn't directly show us the critical path of LUTRAM but most of the critical paths were consist of Memory Access paths.

As combinational paths increases the delay of clock timing, we've decided to replace LUTRAM to synchronous BRAM. 
Since the instruction memory is now synchronous, the instruction that is followed by the input PC address comes out at next clock cycle.

Because of this characteristic, we need to synchronize the PC address and according Instruction at same pipeline stage. 
It's not necessary but without ordering the PC and Instruction, PC related instructions would need additional complex logics for every operation.
1-cycle stall on every new PC address could be an answer, but it would make effective operating speed to half. 
So we've made additional pipeline stage to order the PC-Instruction at front-end of the pipeline. 

This stage orders instructions with single 1-cycle stall when it's only needed such as jump and branch instruction.

This pipelining **decreased** Core Fmax from 67MHz to 65MHz in RV64.
But SoC Fmax increased from 45MHz to 55MHz. This architectural optimization sure improved the critical path but it also added new critical path we think.

## 8-Stage Pipeline Architecture

![Image of 72F8SP](/docs/diagrams/RV32I46F_8SP_handmade_noMMIO_withWatermark.drawio.png)

Pipeline stage definitions:

- **IF; Instruction Fetch** (PC-Instruction Memory)
- **IO; Instruction Order** (Instruction Memory)
- **ID; Instruction Decode** (Instruction Decoder - Control Unit - Register File)
- **EXR; Execute Ready** (Multiple forward unit Multiplexer; MUXs)
- **EX; Execute** (ALU)
- **BR; Branch** (Branch Logic)
- **MEM; Memory Access** (Byte Enable Logic - Data Memory)
- **WB; register Write Back** (Register File)

After the 7-Stage pipeline and timing closure, the longest critical path was data forwarding path. 

When it comes to data hazard, our architecture detects hazard and forwards data with combinational logics.
So when consecutive instructions are executing, the datapath also include forwarding in single clock cycle.

To separate the forwarding path from the critical path, we've added **EXR Stage**. This stage registers the forwarded value to pipeline register before the EX stage, separating operand selection from ALU execution.

This pipeline increased SoC Fmax from 88MHz to 100.8MHz in RV64.