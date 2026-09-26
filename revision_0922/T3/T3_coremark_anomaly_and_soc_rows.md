# T3 — RV32 CoreMark anomaly (IM_8SP_withoutOpt) and the "duplicated" SoC rows

## (a) Result summary

**1. Root cause of the withoutOpt anomaly: wrong image.** Project `RV32IM_8SP_withoutOpt_Coremark`
loads `coremark_RV32IM_114MHz.mem`, but that file is **byte-identical to the 100 MHz build**
(md5 `bb5eaf…`). A fresh build at 114 MHz is `1e6ec5…` and appears nowhere. The canonical
`benchmarks/coremarks/coremark_RV32IM_114MHz.mem` is the same mislabelled copy
(dated 08-28). So the board ran a program that believes the clock is 100 MHz on a
114 MHz PLL.
- Audit of all 32 SoC projects: each image was rebuilt with the `build_image_exact.sh`
  recipe at the frequency in its file name. **31/32 are byte-identical; only this one differs.**
  The PLL settings match the image names on all 32 (`image_audit_32builds.tsv`).

**2. Every CoreMark score in the master file is quantised; the error is not specific to withoutOpt.**
Both CoreMark ports use `HAS_FLOAT 0`, so `time_in_secs()` truncates to whole seconds and
`Iterations/Sec = iterations / int_seconds` (integer). The auto-calibration picks
600–3000 iterations, giving 11–19 truncated seconds. Replaying `core_main.c`'s calibration
with the simulated cycles/iteration **reproduces the printed board value exactly on 16 of 16
variants** (withoutOpt's 166 included: 2000 iterations, 12 notional seconds). This also
confirms FPGA == RTL simulation for CoreMark on both widths. The true score,
`f / cycles-per-iteration`, differs from the master value by **−9.75% (withoutOpt) and
+0.13% … +7.28% (all others)**:

| variant | master it/s | true it/s | true CM/MHz | error |
|---|---|---|---|---|
| RV32I_5SP | 50 | 48.53 | 1.0784 | +3.03% |
| RV32IM_5SP | 117 | 115.22 | 2.6796 | +1.54% |
| RV32IM_6SP | 125 | 120.66 | 2.4131 | +3.60% |
| RV32IM_7SP | 117 | 115.62 | 2.0107 | +1.20% |
| RV32IM_7SP_BRAM | 142 | 139.62 | 1.9391 | +1.71% |
| RV32IM_7SP_BRAM_Opt | 176 | 175.78 | 1.9106 | +0.13% |
| **RV32IM_8SP_withoutOpt** | **166** | **183.93** | **1.6134** | **−9.75%** |
| RV32IM_8SP | 200 | 194.42 | 1.5936 | +2.87% |
| RV64I_5SP | 35 | 33.54 | 0.8944 | +4.36% |
| RV64IM_5SP | 91 | 89.12 | 2.3453 | +2.11% |
| RV64IM_6SP | 100 | 96.10 | 2.1355 | +4.06% |
| RV64IM_7SP | 91 | 84.83 | 1.8048 | +7.28% |
| RV64IM_7SP_BRAM | 105 | 101.31 | 1.7467 | +3.64% |
| RV64IM_7SP_BRAM_Opt | 142 | 139.48 | 1.7230 | +1.81% |
| RV64IM_8SP_withoutOpt | 142 | 134.27 | 1.4595 | +5.76% |
| RV64IM_8SP | 153 | 147.17 | 1.4429 | +3.96% |

withoutOpt's true CM/MHz (1.613) is now above IM_8SP's (1.594), consistent with its lower
CPI (2.2137 vs 2.2413).

**3. Simulated cycles/iteration (step 3).** Fixed-iteration images (10 and 20 iterations;
same recipe, `ITERATIONS=N`) were simulated on the RTL. Per-iteration values come from the
difference, which cancels fixed overhead. CRCs were validated (`crclist 0xe714`,
`crcmatrix 0x1fd7`, `crcstate 0x8e3a`, the 2K performance-run references) on all 16.
- RV32IM_8SP_withoutOpt: **619,804.0 cycles/iter, 279,972.9 instr/iter** → **183.93 it/s at 114 MHz**.
- RV32IM_8SP: 627,508.2 cycles/iter → 194.42 it/s at 122 MHz.
- The anomaly's "≈310k instructions/iteration" was an artefact of the wrong image. The
  true count is 279,972.9, identical on all seven RV32IM variants.

**4. Dhrystone is unaffected.** It prints a float computed from `HZ × runs / User_Time`
with cycle-resolution time. Simulated cycles/iteration predict every master Dhrystone/s to
within −0.20% … +0.14% on all 16 (`Dhrystone diff %`). The small residual is the fixed
loop overhead that the per-iteration difference removes.

**5. The "duplicated" SoC rows are genuine.** `RV32IM_8SP_Dhry` and `RV32IM_8SP_Coremark`
(and the two withoutOpt projects) have separate report files (different md5s, runs 4 min
apart, each loading its own image), and those reports contain identical numbers. That is
expected: these are BRAM designs, where the image only changes BRAM INIT, never the
netlist. `soc_rows_from_vivado_reports.csv` re-reads all 32 builds (utilisation, per-clock
WNS, every power component). **All 32 × 16 cells match the workbook**, except:
- RV64IM_8SP (both images): workbook PLL = 0, report PLLE2_ADV = 1 (see T7.4).
- SoC Fmax differs by ≤ 0.004 MHz, from the report's 3-dp clock period. Not a real difference.

## Board re-run of RV32 IM_8SP_withoutOpt (2026-09-23) — done, and it confirms the model

Rebuilt with `build_image_exact.sh RV32IM_8SP_withoutOpt coremark 113.999088` and re-run:

| | predicted (before the run) | measured |
|---|---|---|
| printed Iterations/Sec | 187 | **187** (exact) |
| iterations chosen by the calibration | 3000 | 3000 |
| printed seconds (integer) | 16 | 16 |
| Total ticks | 1,859,412,000 | **1,859,182,144** (−0.012%) |

So the replay model predicted the printed integer exactly and the tick count to one part in 8,000.
The row is therefore no longer simulation-derived: its score now comes from the board's own
counter, `3000 × 113.999088e6 / 1,859,182,144`:

- **true 183.95 it/s, 1.6136 CoreMark/MHz** (was 183.93 / 1.6134 from simulated cycles/iteration).
- The printed 187 is still **+1.66% high**: the correct image makes the calibration pick 3000
  iterations and 16 truncated seconds, so the quantisation does not disappear, it changes sign and
  size. That is the argument for never publishing the printed integer.
- The 0.012% tick difference is a model residual, not a fidelity failure: cycles-per-iteration was
  obtained by differencing a 10- and a 20-iteration image, while this run executes 3000 iterations
  in one image. Identical images match RTL simulation exactly (Embench, 80/80).

For the paper, report CoreMark as `iterations × f / Total_ticks` and say so; `Total ticks` is printed
by the unmodified benchmark (`core_main.c:359`). The 15 other variants still derive it from the
simulated cycles/iteration, because their UART logs kept only the `Iterations/Sec` line — a re-run
that saves the full output would turn each of those into a direct measurement too.

## (b) Fragments
- `T3_fragment_corrected_coremark.csv`: 16 rows, drop-in columns for `RV32/RV64 SoC and FPGA`
  (CoreMarks/MHz) and `Normalized metrics` (CoreMark, CM/MHz, CM/LUT, CM/W, mJ/iter must be
  recomputed from `TRUE it/s`).
- `soc_rows_from_vivado_reports.csv`: authoritative SoC rows with report dates and md5s.
- `image_audit_32builds.tsv`: image provenance per SoC project.

## (c) Contradicts the master file
1. RV32 IM_8SP_withoutOpt CoreMark 166 it/s / 1.456 CM/MHz → 183.93 / 1.613.
2. **All 16 CoreMark values** (and the `Normalized metrics` sheet derived from them) are
   biased by integer-second truncation, by +0.13% to +7.28%.
3. `Normalized metrics` "iters/s" and "CoreMark" columns inherit (1) and (2).
4. RV64 IM_8SP utilisation PLL = 0 → 1.
5. `benchmarks/coremarks/coremark_RV32IM_114MHz.mem` (and the `_120MHz` copy inside the
   withoutOpt project) is the 100 MHz image and should be replaced or deleted.
