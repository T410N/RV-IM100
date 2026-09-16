`ifndef TRAP_VH
`define TRAP_VH

`define TRAP_NONE		3'b000
`define TRAP_EBREAK		3'b001            // breakpoint 
`define TRAP_ECALL		3'b010              // environment call from M-mode
`define TRAP_MISALIGNED_INSTRUCTION	3'b011 // instruction address misaligned
`define TRAP_MRET       3'b100
`define TRAP_FENCEI     3'b101
`define TRAP_MISALIGNED_STORE 3'b110    // store access fault
`define TRAP_MISALIGNED_LOAD 3'b111    // load access fault
//`define TRAP_ILLEGAL_INSTRUCTION 4'b1000

`endif // TRAP_VH