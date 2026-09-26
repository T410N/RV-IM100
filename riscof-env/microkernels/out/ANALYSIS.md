# Measured dependency penalties

Matched binaries have equal retired instruction counts and branch-miss counts. Each cell is extra cycles per dependency, relative to the matched independent consumer.

| Variant | ALU gap 0 | ALU gap 1 | Load gap 0 | Load gap 1 | Load gap 2 |
|---|---:|---:|---:|---:|---:|
| socs_RV32IM_5SP | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| socs_RV32IM_6SP | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| socs_RV32IM_7SP | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| socs_RV32IM_7SP_BRAM | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| socs_RV32IM_7SP_BRAM_Opt | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| socs_RV32IM_8SP | 1.0000 | 0.0000 | 2.0000 | 1.0000 | 0.0000 |
| socs_RV32IM_8SP_withoutOpt | 1.0000 | 0.0000 | 2.0000 | 1.0000 | 0.0000 |
| socs_RV32I_5SP | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| socs_RV64IM_5SP | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| socs_RV64IM_6SP | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| socs_RV64IM_7SP | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| socs_RV64IM_7SP_BRAM | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| socs_RV64IM_7SP_BRAM_Opt | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| socs_RV64IM_8SP | 1.0000 | 0.0000 | 2.0000 | 1.0000 | 0.0000 |
| socs_RV64IM_8SP_withoutOpt | 1.0000 | 0.0000 | 2.0000 | 1.0000 | 0.0000 |
| socs_RV64I_5SP | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

These differences measure the tested instruction pairs. They do not establish penalties for all opcodes or dependency types. Unoptimized/optimized naming follows the existing repository; this campaign does not certify a twelve-change RTL ablation.

## Branch and jump observations

| Variant | Taken branch: excess cycles/retired branch | Taken branch misses | JAL: excess cycles/jump | JALR: excess cycles/jump |
|---|---:|---:|---:|---:|
| socs_RV32IM_5SP | 0.0000 | 1 | 2.0002 | 2.0002 |
| socs_RV32IM_6SP | 0.0000 | 1 | 2.0003 | 2.0003 |
| socs_RV32IM_7SP | 2.0000 | 1 | 4.0628 | 4.0628 |
| socs_RV32IM_7SP_BRAM | 2.0000 | 1 | 4.0628 | 4.0628 |
| socs_RV32IM_7SP_BRAM_Opt | 2.0000 | 1 | 5.0628 | 5.0628 |
| socs_RV32IM_8SP | 2.0154 | 1 | 6.0941 | 7.0941 |
| socs_RV32IM_8SP_withoutOpt | 2.0154 | 1 | 5.0941 | 6.0941 |
| socs_RV32I_5SP | 0.0000 | 1 | 2.0002 | 2.0002 |
| socs_RV64IM_5SP | 0.0000 | 1 | 2.0002 | 2.0002 |
| socs_RV64IM_6SP | 0.0000 | 1 | 2.0003 | 2.0003 |
| socs_RV64IM_7SP | 2.0000 | 1 | 4.0628 | 4.0628 |
| socs_RV64IM_7SP_BRAM | 2.0000 | 1 | 4.0628 | 4.0628 |
| socs_RV64IM_7SP_BRAM_Opt | 2.0000 | 1 | 5.0628 | 5.0628 |
| socs_RV64IM_8SP | 2.0154 | 1 | 6.0941 | 7.0941 |
| socs_RV64IM_8SP_withoutOpt | 2.0154 | 1 | 5.0941 | 6.0941 |
| socs_RV64I_5SP | 0.0000 | 1 | 2.0002 | 2.0002 |

Excess cycles include loop overhead, operand hazards, and pipeline recovery. These ratios are descriptive, not isolated misprediction or refill penalties. Branch patterns are generated at multiple static sites sharing the global counter; the outer loop also trains the predictor.

## Matched direct-jump cost

JAL and the sequential control retire equal instruction counts and execute the same loop branches. Where both checks pass and branch-miss counts agree, their difference measures the incremental cost of replacing one independent instruction with JAL to a nearby target. It includes all redirect/recovery work, without claiming to separate front-end refill from branch resolution.

| Variant | Extra cycles/JAL |
|---|---:|
| socs_RV32IM_5SP | 2.0000 |
| socs_RV32IM_6SP | 2.0000 |
| socs_RV32IM_7SP | 4.0000 |
| socs_RV32IM_7SP_BRAM | 4.0000 |
| socs_RV32IM_7SP_BRAM_Opt | 5.0000 |
| socs_RV32IM_8SP | 6.0000 |
| socs_RV32IM_8SP_withoutOpt | 5.0000 |
| socs_RV32I_5SP | 2.0000 |
| socs_RV64IM_5SP | 2.0000 |
| socs_RV64IM_6SP | 2.0000 |
| socs_RV64IM_7SP | 4.0000 |
| socs_RV64IM_7SP_BRAM | 4.0000 |
| socs_RV64IM_7SP_BRAM_Opt | 5.0000 |
| socs_RV64IM_8SP | 6.0000 |
| socs_RV64IM_8SP_withoutOpt | 5.0000 |
| socs_RV64I_5SP | 2.0000 |

## Arithmetic and store service cost

Extra cycles per instruction relative to the independent-ALU body with equal retired counts and branch misses. Normal arithmetic uses the fixed nontrivial operands documented in the assembly; corner operands are separate tests. A dash means unsupported or unmatched.

| Variant | MUL | DIV | DIVW | SW |
|---|---:|---:|---:|---:|
| socs_RV32IM_5SP | 4.0000 | 36.0000 | — | 0.0000 |
| socs_RV32IM_6SP | 4.0000 | 36.0000 | — | 0.0000 |
| socs_RV32IM_7SP | 4.0000 | 36.0000 | — | 0.0000 |
| socs_RV32IM_7SP_BRAM | 4.0000 | 36.0000 | — | 1.0000 |
| socs_RV32IM_7SP_BRAM_Opt | 4.0000 | 36.0000 | — | 1.0000 |
| socs_RV32IM_8SP | 4.0000 | 36.0000 | — | 1.0000 |
| socs_RV32IM_8SP_withoutOpt | 4.0000 | 36.0000 | — | 1.0000 |
| socs_RV32I_5SP | — | — | — | 0.0000 |
| socs_RV64IM_5SP | 4.0000 | 68.0000 | 36.0000 | 0.0000 |
| socs_RV64IM_6SP | 4.0000 | 68.0000 | 36.0000 | 0.0000 |
| socs_RV64IM_7SP | 4.0000 | 68.0000 | 36.0000 | 0.0000 |
| socs_RV64IM_7SP_BRAM | 4.0000 | 68.0000 | 36.0000 | 1.0000 |
| socs_RV64IM_7SP_BRAM_Opt | 4.0000 | 68.0000 | 36.0000 | 1.0000 |
| socs_RV64IM_8SP | 4.0000 | 68.0000 | 36.0000 | 1.0000 |
| socs_RV64IM_8SP_withoutOpt | 4.0000 | 68.0000 | 36.0000 | 1.0000 |
| socs_RV64I_5SP | — | — | — | 0.0000 |

## Provenance

See `provenance/` for source hashes, per-variant counter mappings, build commands, simulator hashes, tool versions, and generator hashes. Generated assembly, disassembly, ELF and binary files are in `images/`; regenerate them with the documented command.
