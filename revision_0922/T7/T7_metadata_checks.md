# T7 — Metadata consistency checks (read-only)

| # | item | verdict |
|---|---|---|
| 1 | RV64 IM_5SP nettle-aes build MHz = 30 | **confirmed (with footnote)** |
| 2 | Core-only top `RV64IM72F6SP_CORE` for IM_7SP / _BRAM / _BRAM_Opt; identical Fmax 64.637 MHz / WNS −10.471 ns for 6SP/7SP/7SP_BRAM | **confirmed genuine**, naming inherited |
| 3 | RV32 IM_8SP device static 0.136 W vs 0.152–0.153 W | **not temperature**; estimator artefact on the Vcco33 rail |
| 4 | PLLE2_ADV vs MMCME2_ADV; RV64 IM_8SP PLL = 0 in the utilisation row | **corrected**: PLL = 1 in all 32 builds |
| 5 | Vivado version and strategies of the 09-15/16 rebuilds | **confirmed** |
| 6 | RISCOF reference plugin and suite version | **confirmed**: live Sail, arch-test 2.7.4 (with one local edit) |
| 7 | riscv-tests: only `ma_data` fails; misaligned behaviour | **confirmed**, and the behaviour is more nuanced than "traps" |

## 1. RV64 IM_5SP nettle-aes at 30 MHz
The build at the variant clock failed timing: 38 MHz WNS −0.131 ns (`embench_fpga_all.log`
[43/80]), and a retry at 37 MHz gave WNS −0.106 (`embench_retry.log`). It was rebuilt at
**30 MHz, WNS +0.735** (`embench_retry2.log`; `bitstream/embench/MANIFEST.csv`: "reduced clock:
did not close at the variant clock"). The cycle count is clock-independent (mcycle), so the
row's cycles/instret are unaffected. **Runtime 175.532 ms = 5,265,973 / 30 MHz is correct for
that bitstream.** Footnote it in the paper: at the variant clock the projection would be
138.58 ms, but that build does not close timing, so it must not be reported as a measurement.

## 2. Core-only synthesis tops and the shared 64.637 MHz
From `logs/coresynth/<v>.log`:
- IM_6SP, IM_7SP, IM_7SP_BRAM and IM_7SP_BRAM_Opt all run
  `synth_design -top RV64IM72F6SP_CORE`. **The module name is inherited**: each run reads its
  own `RV64s/cores/<variant>/…/RV64IM72F_6SP.v`, and the elaborated hierarchy differs
  (6SP: no `IF_IO_Register`; the three 7SP runs: `IF_IO_Register` present, 30 modules).
- All runs requested `-auto_incremental` against a stale *SoC* checkpoint, but every log
  reports **"Incremental synthesis run: no"** ("incremental criteria not met"). The results
  come from full synthesis.
- The identical Fmax is genuine. The worst path is **the same EX-stage path** in all three,
  `ex_mem_register/MEM_alu_result_reg[1]` (forward) → 64-bit ALU (38 logic levels, 23 CARRY4)
  → `ex_ex2_register/EX2_alu_zero_reg`, with data-path delay 15.405–15.406 ns. Neither the IO
  stage nor the BRAM change touches EX. RV32 6SP/7SP/7SP_BRAM behave the same way (the same
  endpoint, −9.53 to −9.56 ns).
- Small discrepancy: `core_reports/*/timing.rpt` shows −10.460/−10.461 ns, while the workbook
  and `core_synth.csv` say −10.471. The reports were regenerated in a separate run; the
  0.01 ns difference is run-to-run.

## 3. RV32 IM_8SP static 0.136 W
Ambient 25 °C, Tj 26.1 °C, process "typical", board and airflow settings, and
`report_operating_conditions -all` are **identical** to RV32 IM_8SP_withoutOpt (0.153 W).
I/O is identical too: the same 12 ports, pins, IOSTANDARDs and banks (13, 14, 16, 34, 35),
checked on the routed checkpoints. The 17 mW difference is entirely **Vcco33 static
(0.000 A vs 0.005 A × 3.3 V)**. It reproduces when `report_power` is re-run on both RV32 8SP
checkpoints (Dhrystone and CoreMark), so it is a property Vivado's estimator assigns to that
netlist, not a measurement condition. Recommendation: compare dynamic power, or quote
static as the device constant (0.152–0.153 W).

## 4. Clocking
From all 32 `logs/final_impl/*/utilization.rpt`: **PLLE2_ADV = 1, MMCME2_ADV = 0 for every
build**; BUFGCTRL is 2 in 28 builds, 3 in RV32IM_8SP (both images) and 4 in RV32IM_7SP_BRAM_Opt Dhrystone and RV64IM_7SP_BRAM_Opt CoreMark, matching the Clocking sheet. The `RV64 SoC and FPGA` PLL cell for **IM_8SP (Dhrystone and CoreMark)
is 0 and must be 1**. The notes column in the SoC sheets says "the MMCM's exact output";
it should say PLL.

## 5. Tool and strategies
Vivado **v2025.2 (SW build 6299465)** for all 32. From each `.xpr`: synthesis
**Flow_PerfOptimized_high**, implementation **Performance_ExplorePostRoutePhysOpt**. The
project enables auto-incremental synthesis, but every one of the 32 build logs prints
`INCREMENTAL_DISABLED` (set by the build script), so all reported builds are from scratch.
Build dates: 2026-09-15 18:06 to 2026-09-16 14:26.

## 6. RISCOF
`scripts/run.py` writes `ReferencePlugin=sail_cSim` (`plugins/sail_cSim`): **the Sail RISC-V
0.6 C emulator run live**, not pre-generated `archtest_ref` signatures. Suite: `riscv-arch-test`
branch **`old-framework-2.x` @ `6f7f47bd` (2.7.4)**, with **one uncommitted local edit** to
`riscv-test-suite/env/arch_test.h` (the `TEST_JALR_OP` guard `.ifnc rd,x0`; the backup is
`arch_test.h.riscof-backup`). Both DUT and reference compile with it; disclose it.
Pass counts: I 38 (RV32), I+M 38+8 = 46 (RV32IM), I 50 (RV64), I+M 50+13 = 63 (RV64IM);
851/851 in total.

## 7. riscv-tests and misaligned access
The only failure on every variant is `ma_data` (883/899 in total). A direct probe
(`T7/misaligned_probe.S`) on all 16:

| access | behaviour |
|---|---|
| misaligned `lh`/`lhu`/`lw` | trap, mcause 4, on all 16 |
| misaligned `sh`/`sw` | trap, mcause 6, on all 16. **But on RV32IM_5SP, RV32IM_8SP and RV32IM_8SP_withoutOpt the misaligned `sh` still writes memory** (at the aligned halfword); `sw` is suppressed |
| misaligned `ld` (+1, +4), `lwu` (+6) | **no trap on any of the 8 RV64 variants**: the low address bits are dropped and the aligned value is returned |

`mtval` is not implemented. This explains the two `ma_data` failure points (subtest 1 on
most variants, subtest 668 on 5SP and 7SP_BRAM_Opt). Wording for the paper: "misaligned
loads/stores trap as required, except RV64 doubleword/`lwu` loads, which silently align, and
a sub-word misaligned store on three RV32 variants, which traps but is not suppressed.
Misaligned access support is optional in RISC-V and no reported workload performs one."

## (c) Contradicts the master file
- RV64 IM_8SP PLL = 0 → 1 (both images).
- "MMCM" → "PLL" in the SoC notes.
- The Verification sheet's "these cores trap" (misaligned) is incomplete; see item 7.
