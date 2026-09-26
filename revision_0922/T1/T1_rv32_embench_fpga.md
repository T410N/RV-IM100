# T1 — RV32 Embench on FPGA, and the cross-check against RTL simulation

## (a) Result summary

**Complete. 40 board runs, 40/40 EXACT in both counters against the RTL simulation, and
40/40 `verify = OK` on the board.** The RV32 Embench block of the paper is now measured
hardware, not a simulation stand-in, and it is cross-checked at the cycle level.

| check | result |
|---|---|
| board `verify` (Embench's own output check) | **40 / 40 OK** |
| board cycles == RTL-simulated cycles | **40 / 40 EXACT** (every delta 0) |
| board instret == RTL-simulated instret | **40 / 40 EXACT** (every delta 0) |

This is the same outcome as the RV64 runs, and it re-establishes for RV32 the simulation
fidelity claim the paper rests on (FPGA == RTL simulation, so any sim-only measurement in
this revision — T8, T9, T10, T12 — is admissible at the same RTL commit).

Measured per variant (5 benchmarks: matmult-int, crc32, nettle-aes, statemate, md5sum):

| variant | build MHz | CPI (aggregate) | geomean runtime (ms) | vs IM-5 |
|---|---|---|---|---|
| RV32I_5SP | 45 | 1.219 | 209.65 | 2.137 |
| RV32IM_5SP | 43 | 1.230 | 98.09 | 1.000 |
| RV32IM_6SP | 50 | 1.255 | 86.24 | 0.879 |
| RV32IM_7SP | 57.501 | 1.447 | 86.83 | 0.885 |
| RV32IM_7SP_BRAM | 71.999 | 1.542 | 74.10 | 0.755 |
| RV32IM_7SP_BRAM_Opt | 92 | 1.579 | 59.31 | 0.605 |
| RV32IM_8SP_withoutOpt | 113.999 | 1.876 | 56.53 | 0.576 |
| RV32IM_8SP | 122 | 1.913 | 53.78 | 0.548 |

The RV32 depth trend now matches RV64 measured-to-measured: 0.548 vs 0.551 geomean runtime
for the 8-stage relative to IM-5. CPI rises monotonically with depth (1.23 → 1.91) and is
out-run by frequency (43 → 122 MHz), which is the paper's central claim, measured on both
widths.

## Provenance
- Bitstreams: `bitstream/embench/RV32/<variant>/<variant>_embench_<bench>.bit`, 40 files from
  the fourth rebuild (`logs/embench_rv32_rebuild3.log`, 2026-09-22 10:59–15:57); all closed
  timing, minimum WNS +0.007 ns. The earlier `embench_rv32_v2/` (minstret reads mcycle) and
  `embench_rv32_v3/` (hangs in the counter-read loop) are **not** used; both READMEs say so.
- Counter read: the v4 `boardsupport.c` reads the low 32 bits of mcycle/minstret and forms
  the difference in unsigned 64-bit. Valid while a run stays below 2³² cycles; the largest
  run here is 43 M cycles (T2 bounds the scope of this fix).
- Board results: `bitstream/embench/RV32/Done/<variant>/embench_results.csv` (runs of
  2026-09-23), one folder per variant.
- Reference: `embench_rv32_simref_v4.csv` — each rebuilt project's **own** `.mem` image run on
  the RTL simulator built from the same RTL commit as the bitstreams; each image is
  byte-identical to `build/embench_fpga/<isa>/<bench>.mem`. ELF sha256, image md5 and
  bitstream timestamps are in that CSV.
- Comparison: `riscof-env/scripts/t1_rv32_embench.py compare` →
  `riscof-env/logs/embench_rv32_fpga_vs_sim.csv` (per-row deltas; mismatches are printed,
  never adjusted).
- Runtime (ms) = cycles / build MHz, the build clocks above (45 for RV32I, then 43, 50,
  57.501, 71.999, 92, 113.999, 122).

## (b) Fragments
- `T1_fragment_embench_fpga_rv32.csv` — the 40 measured rows in the master's per-benchmark
  block layout, for sheet `Embench FPGA RV32` (cycles, instret, verify, build MHz, runtime ms).
- `T1_fragment_fpga_vs_sim_rows.csv` — the 40 cross-check rows (FPGA vs sim, both counters,
  EXACT/MISMATCH), to append to the `Embench FPGA vs simulation` sheet.
- Workbook sheet `T1 Sim ref` in `Revision_review_0923.xlsx` carries both side by side with the
  EXACT checks as live formulas.

## (c) Contradicts the master file
Nothing here contradicts a *measured* master value: the master's `Embench FPGA RV32` sheet
carries no numbers at all. All 40 data rows read `awaiting re-measurement (RV32 counter fix)`
in the FPGA-cycles column, with every other column empty. Three things to update:

1. `Embench FPGA RV32`: replace the 40 placeholder rows with the measured values
   (`T1_fragment_embench_fpga_rv32.csv`), which fills cycles, instret, CPI, sim cycles,
   `sim = FPGA?`, verify, build MHz and runtime ms.
2. `Embench FPGA vs simulation`: the sheet holds the 40 RV64 rows and the note *"All 40 RV64
   rows are shown. RV32 is excluded: those runs predate the RV32 counter-read fix and their
   cycle counts are invalid."* Append the 40 RV32 cross-check rows
   (`T1_fragment_fpga_vs_sim_rows.csv`, same column order), change the summary line to
   **80 of 80 rows match simulation exactly in BOTH counters**, and replace the exclusion note
   with a line saying the RV32 rows come from the rebuilt (v4 counter-read) bitstreams.
3. Any RV32 Embench figure or sentence marked "simulation" should now read "measured on
   hardware"; `figures/fig_embench_geomean.pdf` has been regenerated from the board data and
   no longer carries the simulation caveat.
