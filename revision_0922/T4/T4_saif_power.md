# T4 — SAIF power: validity, one authoritative table, recomputed normalised metrics

## (a) Result summary

### Why the two master-file SAIF tables disagree
- `SAIF detail` was built from `saif/<build>/power_saif.rpt`: the power **computed on the
  capture-time netlist** (implementations from 09-12…09-14).
- The `SAIF` columns of `RV32/RV64 SoC and FPGA` come from `logs/saif_power.csv`, where the
  rows listed in `logs/repower/` were **re-costed** (the same activity applied to the final
  09-15/16 implementation).

Examples: RV64 IM_7SP Dhrystone 0.428 (capture netlist) vs 0.377 W (re-costed); RV32
IM_7SP_BRAM_Opt Dhrystone 0.345 (**pre-data-memory-fix** capture) vs 0.321 W.

**Resolution:** all 32 captured activities were re-applied to the **final** implementation
of their build (`scripts/saif_recost_all.sh`, 2026-09-22, Vivado 2025.2), and coverage was
recorded. That is the single authoritative table: `T4_saif_authoritative.csv`.

### Coverage (read_saif "Design nets matched")
50–81% of nets are annotated in the final table; the remainder is estimated vectorlessly. It
is lowest on RV64 IM_8SP Dhrystone (50.2%) and RV32I_5SP Dhrystone (53.8%). The original capture-time runs report the same coverage, so this reflects
how SAIF maps onto these netlists, not a mismatch between old and new implementations. It
belongs in the paper's power-method statement next to "no SDF, glitch power excluded".

### Capture windows (step 3): `capture_window_map.csv`
Every capture follows the same timeline: core released at 70 µs, UART forced idle from 100
to 1100 µs, window at 1200–1300 µs. RTL simulation is cycle-exact with the board, so each
window maps to core cycles and instret. For all 32, the window lies **inside benchmark
code**:
- Dhrystone: `strcpy`/`main`/`Proc_1`/`strcmp` in the same proportions on every variant.
- CoreMark: `core_bench_list` on most variants, but **`matrix_mul`** on RV32
  7SP_BRAM_Opt/8SP and **`crcu16`/`matrix_test`/`calc_func`** on RV64 7SP_BRAM_Opt/8SP.

A 100 µs window samples a *different CoreMark phase* on faster variants, because they have
progressed further by 1.2 ms. This, not an error, explains the RV64 IM_7SP_BRAM_Opt
CoreMark "+67.8% vs vectorless" outlier. Its core is genuinely 3× more active than in its
Dhrystone window, and its data memory is active (5.4k toggles/µs, a normal level).
(The capture-retry index was not logged for the original captures; the first window is
assumed, which is where the two surviving logs accepted.)

### Validity of each capture: `capture_validity_dmem_activity.csv`
A core running CoreMark or Dhrystone accesses data memory every few cycles. A core parked in
an idle loop does not. Data-memory toggle rate per µs of window:

| memory type | range over valid captures | outlier |
|---|---|---|
| LUTRAM builds (5SP/6SP/7SP) | 280k – 608k /µs | none |
| BRAM builds (7SP_BRAM*, 8SP*) | 1.9k – 6.4k /µs | **RV64 IM_8SP CoreMark: 211 /µs** |

Its core toggle count is also 5% of its Dhrystone sibling's. **That capture is invalid (idle
core) and has been replaced by a valid re-capture (below). All 32 rows of the final table
are valid.**

**Why it was idle (diagnosed):** gate-level (zero-delay, no-SDF) simulation does not always
reproduce the RTL/FPGA behaviour. A PC trace of the **final** RV64 IM_8SP *Dhrystone* netlist
shows the core clearing `.bss`, executing `jal main`, and then **spinning in `_exit`
(`j 0x74`) from ~160 µs on; `main` never runs**. The same image runs correctly in RTL
simulation (identical to FPGA). The old 8SP CoreMark capture has the same idle signature. The
final CoreMark netlists of RV64 IM_8SP and IM_7SP_BRAM_Opt **do** boot and execute CoreMark
code (PC traced over 70–300 µs), so they were re-captured:

| build | re-capture on final netlist | result |
|---|---|---|
| RV64 IM_8SP CoreMark | v2 (PC-sampled window) | **valid: 0.497 W total, 0.343 W dynamic, coverage 69.3%.** PC samples at 1200–1300 µs: `core_bench_list` → `crcu16` → `cmp_complex` → `matrix_test`, the phase the RTL window map predicted. Data memory 5.5k/µs, core 1.06 M/µs (the replaced capture had 0.2k / 25.6k). **Replaces the invalid capture.** |
| RV64 IM_7SP_BRAM_Opt CoreMark | v2, cross-check of the outlier | **valid: 0.483 W** (original capture 0.498 W, within 3%). PC samples: `core_bench_list` → `calc_func` → `crcu16` → `core_list_mergesort`, again exactly the predicted phase. Data memory 5.0k/µs. **Confirms the outlier is a genuine CoreMark-phase effect.** |

Both v2 captures sample the PC through the window, and both land in the functions the
RTL-based window map predicts. That independently validates the window mapping used for
all 32 captures. The v2 captures (final-implementation netlist, PC-verified window) are used
for these two rows; the other 30 use their original capture re-costed on the final
implementation.

### Core-attributable power (step 5)
`core_attributable_dyn` = total dynamic − PLL − I/O (the PLL alone is 0.10–0.12 W, i.e.
**29–69% of all dynamic power** across all 32 builds). `core_instance_dyn` is the CPU instance row of
`report_power -hier`, which includes its instruction and data memories; `…_excl_mem`
removes those.

### Recomputed normalised metrics: `T4_normalized_metrics.csv`
These use **true CoreMark it/s (T3)**, measured Dhrystone/s, and the authoritative SAIF
power:
- CM/W and mJ per CoreMark iteration: total and core-attributable.
- **µJ per Dhrystone iteration**: total and core-attributable (new column, as requested).
- CM per kLUT (core-only LUT).

Because CoreMark windows sample different phases per variant (above), **cross-variant
energy comparisons should use Dhrystone**, whose windows are phase-matched. CoreMark
power should be stated per variant, with the phase caveat.

## (b) Fragments
`T4_saif_authoritative.csv` (32 rows: every power category, vectorless delta,
core-attributable dynamic, CPU-instance power, coverage, core toggles vs sibling, window
cycles/instret/functions, validity), `T4_normalized_metrics.csv`,
`capture_window_map.csv`, `capture_validity_dmem_activity.csv`.

## (c) Contradicts the master file
1. `SAIF detail` and the SoC-sheet SAIF columns: replace both with `T4_saif_authoritative.csv`.
2. RV64 IM_8SP CoreMark SAIF (0.333 W, 23.7% toggling) is **invalid** (idle core). The
   `Normalized metrics` values derived from it (CM/W 459, 2.18 mJ/iter) are void. The valid
   re-capture gives **0.497 W → 296 CM/W, 3.38 mJ/iter** (with true CoreMark 147.17 it/s).
3. `Normalized metrics` must use true CoreMark it/s (T3).
4. The "window placement" note in RESUME_SAIF.md checks UART silence only. It does not
   detect an idle or mis-booted core; the data-memory activity and PC-sample checks above do.
