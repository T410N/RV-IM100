# T9 — Branch misprediction penalty, measured by matched pairs

## (a) Result summary

**Measured, not asserted, and the two directions differ.** The paper's single figure per
depth (2/3/4/5 cycles for 5/6/7/8 stages) is the average of two different penalties:

| variant | NT→T (predicted not-taken, resolves taken) | T→NT (predicted taken, resolves not-taken) | correctly predicted taken branch | matched-pair blend |
|---|---|---|---|---|
| RV32I_5SP, RV32IM_5SP, RV64I_5SP, RV64IM_5SP | **2** | **2** | 0 | 2.00 |
| RV32IM_6SP, RV64IM_6SP | **3** | **3** | 0 | 3.00 |
| IM_7SP, IM_7SP_BRAM, IM_7SP_BRAM_Opt (both widths) | **3** | **5** | **2** | 5.14 |
| IM_8SP_withoutOpt, IM_8SP (both widths) | **4** | **6** | **2** | 6.14 |

Identical for RV32 and RV64 (the front end is the same), and identical for forward and
backward branches and for both instruction gaps (0 and 4) — 48 fitted families, all
consistent.

So the paper's "4 at 7 stages, 5 at 8 stages" sits between the two directions. The correct
statement is: **from 7 stages on, a taken branch costs 2 cycles even when correctly
predicted, a not-taken misprediction costs 3 (7SP) or 4 (8SP), and a taken misprediction
costs 5 (7SP) or 6 (8SP)** — the misprediction plus the taken-path refill. The 5- and
6-stage cores have no taken-branch cost and one penalty in both directions.

## Method
Each branch targets **the next instruction**, so taken and not-taken retire the identical
instruction stream. Kernels of one family therefore differ only in the branch *pattern*:
`allt`, `allnt`, `alt` (alternating), `blocked` (same taken count, grouped), `t7nt1` and
`nt7t1` (one isolated branch of the other direction). 64 branches × 1024 repetitions, run
after a warm-up with the same pattern.

Two independent estimates per variant and family:
- **matched pair** `alt` vs `blocked`: same instruction count, same branch count and
  **identical taken counts** (measured delta = 0 in all 48 families), so
  `penalty = Δcycles / Δmispredictions`.
- **least squares** over all six patterns:
  `cycles = a + b·taken + c·miss(NT→T) + d·miss(T→NT)`.
  **Maximum residual 0.0%** across all 48 families: the model is exact, which is itself
  evidence that these are the only per-branch costs.

The two misprediction directions are separated by a counter added to the micro-kernel
monitor (testbench only): a miss whose branch resolved taken was predicted not-taken, and
vice versa.

**Acceptance:** all 288 runs PASS the independent oracle; retired counts are identical
across every pattern within a family (checked, column `retired_identical`).

## (b) Fragments
`t9_mispredict_penalties.csv`: 48 rows (16 variants × 3 families) with both estimates, the
taken-branch cost, the residual, and the raw cycles/mispredictions per pattern. Column group
for `Microkernel penalties`: **mispredict penalty (NT→T), mispredict penalty (T→NT),
correctly-predicted-taken cost**, per variant.

Kernels and the direction-split counter are in `riscof-env/microkernels/run.py` and
`monitor.v.in`; penalties computed by `riscof-env/microkernels/t9_penalties.py`.
The 18 new kernels raise the campaign from 338 to 410 images; the existing kernels and their
results are unchanged.

## (c) Contradicts the master file
1. `Microkernel penalties` reports one flush penalty per depth. There are two, differing by
   2 cycles from 7 stages on.
2. The paper's 4/5 cycles for 7/8 stages should become 3/5 and 4/6 by direction, plus the
   2-cycle correctly-predicted-taken cost, which the earlier tables carried as a separate
   "taken-branch excess" observation (T11.4) without connecting it to the penalty.
