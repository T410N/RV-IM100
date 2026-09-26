# T13 — Critical paths from the existing timing reports (no rebuild)

Source: `riscof-env/logs/final_impl/<build>/timing.rpt`, the worst setup path on the core
clock for all 32 SoC builds (`T13_worst_paths_soc.tsv`). Core-only paths come from
`logs/core_reports/<v>/timing.rpt`.

| question | answer |
|---|---|
| RV32 vs RV64 IM_8SP (R3.3) | **Different.** RV64 IM_8SP is **multiplier-limited**: `alu/multiplier_dword/mult_ALBL` (DSP) → `prod_high_reg[63]`, 9.53 ns, 35 levels (30 CARRY4). RV32 IM_8SP is limited by **store-forwarding hold control**: `ex_ex2_register/EX2_alu_result_reg[30]` → `EXR_store_data_hold_reg[10]/CE`, 8.00 ns, 10 levels. |
| 6SP (R3.1) | RV64 and RV32 IM_6SP are both limited by **forward → ALU → branch resolve / PC redirect**: `ex_mem_register/MEM_alu_result` → `program_counter/pc_reg` or `ex_ex2_register/EX2_alu_zero` (RV64: 22.2–22.6 ns, 20–27 levels; RV32: 19.5–19.9 ns, 21–23 levels). The 5SP builds are the same class (→ `pc_reg`, 23–27 ns). |
| RV64 7SP_BRAM_Opt (Table II) | CoreMark image: `data_memory/memory_bank2` (BRAM) → `ex_ex2_register/EX2_alu_result_reg[60]`, **12.483 ns** (logic 5.95 / route 6.53), 23 levels, WNS +0.003 ns at **80.952 MHz** → SoC Fmax **80.97 MHz**. Dhrystone image: 12.103 ns, 10 levels. Core-only (post-synthesis, 5 ns target): WB_rd → EX2_alu_result, 10.94 ns → 91.65 MHz. |
| Core vs SoC Fmax inversion | Core Fmax is **post-synthesis** at an **over-constrained 5 ns** target with estimated routing. SoC Fmax is **post-route** at the build's own PLL constraint, after `phys_opt`. E.g. RV32 IM_8SP core 105.19 MHz (WNS −4.507 @ 5 ns) vs SoC 122.18 MHz. The two are not comparable, and the paper should say so. |

## Consequences for the text
1. **"The 12 optimisations target paths that are not limiting at 5/6 stages" is not
   supported.** At 5SP/6SP (and non-optimised 7SP/7SP_BRAM) the limiting path *is* the
   EX forward → ALU → branch/PC-redirect path. The optimised 7SP removes it (its limiting
   path moves to the BRAM read → ALU operand path). Consistent with this, core-only 6SP,
   7SP and 7SP_BRAM share the same core critical path and an identical Fmax (T7.2).
   A defensible statement: *the optimisations remove the EX-stage forward/branch path that
   limits every non-optimised build; they were applied only at 7 stages, so the 7SP→7SP_BRAM_Opt
   step measures their effect, and applying them at 5/6 stages was not evaluated.*
2. **R3.3: the RV32 and RV64 8-stage builds are limited by different structures** (store
   forwarding control vs the 64-bit multiplier), so the RV32 Fmax is not simply "inherited".
3. **The post-review store-forwarding fix is on the RV32 8SP SoC critical path**
   (`EXR_store_data_hold` CE). STATUS.md's conclusion that the fixes sit off the critical
   path holds for core-only synthesis only.
4. Table II's "~88 MHz / ~10.5 ns" for RV64 7SP_BRAM_Opt should become 80.95 MHz
   (SoC, closed at +0.003 ns) with a 12.48 ns data path, or 91.65 MHz core-only (post-synthesis).
