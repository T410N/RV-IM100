# T2 — Scope of the RV32 counter-read fix

**Finding: software only. RV32 SoC utilisation/timing/power and RV32 Dhrystone/CoreMark data remain valid with respect to this fix.**

The counter-read fix is commit `3a3bc896` (2026-09-19 02:25). Its v4 revision, the
single-low-word read, is the uncommitted edit to `riscof-env/embench-env/boardsupport.c`
in the working tree. Neither touches anything that is synthesised.

| commit / change | files | class |
|---|---|---|
| `3a3bc896` | `riscof-env/embench-env/boardsupport.c` (+ `.bak`) | software (Embench board support) |
| | `riscof-env/scripts/build_embench_workbook.py`, `embench_rv32_rebuild.sh` | scripts |
| | `bitstream/embench/**` (MANIFEST, pngs, csv) | build outputs |
| working tree (v2→v4) | `riscof-env/embench-env/boardsupport.c` | software |
| | `riscof-env/logs/embench_fpga/*.log`, `verilate_socs_*.log` | logs |

Checks performed:
1. `git diff --stat bb433c10 HEAD -- '*.v' '*.vh' '*.xdc' '*.xci'` finds only
   `comparison_cores/**` and `riscof-env/logs/extcore/*/gen_clock.xdc` (external-core
   synthesis). **No RV-IM100 RTL file changed after `bb433c10`** (2026-09-16 15:02).
   `git status` shows no uncommitted RTL.
2. `bb433c10` itself is the **last RTL change**. It fixed RV32IM_7SP_BRAM_Opt data memory
   (16384→8192 words) in all four copies, and **re-implemented** RV32IM_7SP_BRAM_Opt
   Dhrystone (09-16 14:13) and CoreMark (09-16 14:26) in the same commit
   (`logs/final_impl/RV32IM_7SP_BRAM_Opt_*` are dated after the fix). So the SoC rows
   post-date the last RTL change.
3. Byte-level consistency: for each of the 16 variants, every source file in the
   `sources_1` fileset (excluding `Instruction_Memory.v`/`UART_TX.v`, which carry the
   image name and baud divisor, and IP) is **identical across all 8 projects** of that
   variant: legacy (used by Verilator), `_Dhry`, `_Coremark` and the five `_Embench_*`.
   That is 37–47 files per variant and 0 differences (`tools/rtl_consistency.py`).
   So the Dhrystone/CoreMark bitstreams, the rebuilt Embench bitstreams and the
   simulator all come from the same RTL.

**RTL data tag to use (T15): `bb433c10`.** HEAD `3b66323f` carries identical RTL.

Affected rows: none.
