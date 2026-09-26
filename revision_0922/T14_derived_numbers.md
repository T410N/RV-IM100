# T14 — Derived-number generation

One script produces every number the paper quotes, so no value in the text is computed by
hand: `tools/paper_numbers.py` → **`paper_numbers.csv`** (1,561 rows), and with `--figures`
also **`figures/*.pdf`** (13 figures, via `tools/paper_figures.py`).

```bash
/tmp/xlsxenv/bin/python tools/paper_numbers.py --figures     # any python with openpyxl + matplotlib
```

Every row is `key, value, unit, source, note`. `source` names the master-workbook cell
(`RV64 SoC and FPGA!C8`), the fragment file (`T3/T3_fragment_corrected_coremark.csv[RV64IM_8SP]`)
or, for a derived row, the inputs it was computed from. Inputs are the master workbook for
everything the revision leaves unchanged, and the fragments for everything it corrects
(true CoreMark from T3, SAIF power from T4, the 12 KB-stack Embench rows from T5, and the
RV32 Embench reference from T1). **Projected values say `PROJECTION` in the note.**

## What it emits

| group | contents |
|---|---|
| per variant (16) | core and SoC Fmax, run clocks, Dhrystones/s, DMIPS, DMIPS/MHz, true CoreMark and CoreMark/MHz (plus the superseded master value), per-iteration CPI and cycles for both benchmarks, core LUT/FF/DSP, SoC LUT/BRAM, SAIF power (total, dynamic, core-attributable, coverage), CM/W, mJ/iteration, µJ per Dhrystone iteration, CM/kLUT, DMIPS/kLUT, and the Dhrystone-vs-CoreMark image Fmax spread |
| 11 transitions × 2 widths | deltas in core Fmax, SoC Fmax, run clock, Dhrystones/s, CoreMark, CPI, core LUT/FF |
| break-even per transition | clock ratio, cycles-per-iteration ratio, predicted throughput change, measured change |
| 2×2 ablation (IM-7, IM-7 Opt, IM-8 noOpt, IM-8) | individual effects, combined, sum and product of the individual ones, and the sub-additivity gap, for throughput, clock and CPI |
| cross-width | RV64/RV32 ratios at every depth for core LUT, FF, DSP, Fmax, DMIPS/MHz, CoreMark/MHz |
| Embench | per-benchmark FPGA runtimes and ratios vs IM-5, geomean per variant, and **projected** runtimes for all 19 simulated benchmarks at each variant's Embench build clock |

## Self-consistency check
The break-even model (clock ratio ÷ cycles-per-iteration ratio) reproduces the measured
board change to within **0.33 pp on every Dhrystone transition** and 0.01 pp on CoreMark.
The residual is the RV64I Dhrystone offset noted in T3.

## Figures
Regenerated from the same data: `fig_soc_fmax`, `fig_core_fmax`, `fig_dhry_abs`,
`fig_dmips_mhz`, `fig_cm_abs`, `fig_cm_mhz`, `fig_lut`, `fig_ff`, `fig_power`, and four new
ones: `fig_cpi` (CPI, both benchmarks), `fig_ablation` (the 2×2 with the sum of the
individual effects beside the measured combined effect), `fig_embench_geomean`,
`fig_energy_dhry` (core-attributable energy per Dhrystone iteration).

Conventions: single-column (3.5 in) PDF, all text 8 pt at final size, one y-axis per chart,
RV32/RV64 as the only two series in a fixed order, colours validated (CVD ΔE 24.7,
normal-vision ΔE 33.6, contrast ≥ 3:1 on white), RV64 hatched so the series stay
distinguishable in grayscale, recessive grid, legend on every chart, consistent variant
labels (IM-7 is the paper's 7-stage; IM-7 (IO only) is the ablation).
`fig_embench_geomean` states in the figure that RV32 is simulation until the board runs land.

**Caveat carried from T4:** cross-variant power/energy uses the Dhrystone windows, whose
capture phase matches across variants. CoreMark power is per variant with the phase caveat.
