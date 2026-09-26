# T10 — Dynamic instruction counts per iteration

Method: fixed-iteration images of each benchmark (CoreMark `ITERATIONS=10/20`, Dhrystone
`DHRY_ITERS=1000/2000`), built with the same recipe as the board images, run in RTL
simulation. The timed region is cut at the benchmark's own timing calls (CoreMark
`start_time`→`stop_time`, Dhrystone first→second `times()`). **Per-iteration value =
(region(N2) − region(N1)) / (N2 − N1)**, which cancels every fixed overhead. Counts exclude
NOP, as minstret does. The mix is decoded from the retired instruction words
(`tools/iter_runner.py`, `tools/analyze_iter.py`).

| ISA | benchmark | instr/iter | branch | jal | jalr | load | store | mul | div | W-suffix | RV64-only mem (ld/sd/lwu) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rv32i | Dhrystone | **436.0** | 68 | 13 | 11 | 84 | 72 | 0 | 0 | – | – |
| rv32im | Dhrystone | **406.0** | 58 | 12 | 10 | 84 | 72 | 1 | 1 | – | – |
| rv64i | Dhrystone | **416.0** | 65 | 13 | 11 | 76 | 67 | 0 | 0 | 16 (3.8%) | 43 (10.3%) |
| rv64im | Dhrystone | **386.0** | 55 | 12 | 10 | 76 | 67 | 1 | 1 | 16 (4.1%) | 43 (11.1%) |
| rv32i | CoreMark | **712,348.9** | 194,185 | 14,960 | 11,536 | 55,112 | 14,442 | 0 | 0 | – | – |
| rv32im | CoreMark | **279,972.9** | 49,289 | 5,564 | 2,140 | 55,196 | 14,662 | 9,396 | 0 | – | – |
| rv64i | CoreMark | **864,713.6** | 228,478 | 15,864 | 11,536 | 54,851 | 14,285 | 0 | 0 | 51,227 (5.9%) | 31,195 (3.6%) |
| rv64im | CoreMark | **331,857.6** | 50,138 | 5,748 | 2,140 | 54,887 | 14,321 | 9,396 | 0 | 60,623 (18.3%) | 31,267 (9.4%) |

(Branch/jal/jalr/load/store figures are per iteration. The full percentages are in `t10_dynamic_mix.csv`.)

**Sanity check (plan).** Expected ≈406.9 (RV32IM) and ≈387.0 (RV64IM) Dhrystone
instructions/iteration, as implied by FPGA throughput ÷ sim CPI. Measured: **406.0 and
386.0 exactly**, within 0.25%. The small gap is the implied figure absorbing loop overhead
and rounding.

**Consistency across microarchitectures.** The count is identical on every variant of the
same ISA (7 IM variants per width). The one exception is RV64IM_7SP on CoreMark, which
commits **one extra instruction per iteration**: a wrong-path `mv a1,s1` after the taken
back-edge at `core_bench_list+0x1ec` (see T6). It is architecturally harmless there, but it
is a genuine wrong-path commit.

**Cross-check with Spike.** Not possible: Spike is not installed on this machine. The
cross-check is instead against the RTL variants themselves (5SP is RISCOF-clean), plus the
Dhrystone expectation above. The CoreMark count is also validated indirectly, because the
per-iteration cycles reproduce all 16 printed board scores exactly (T3).

**Corrects an assumption in the plan.** The ≈310k instructions/iteration inferred for RV32
IM_8SP_withoutOpt CoreMark came from the mislabelled 100 MHz image (T3). The true count is
279,972.9, identical on all RV32IM variants.

**Dynamic W-suffix and RV64-only memory ops** replace the static argument in the paper:
RV64IM CoreMark executes W-suffix instructions for 18.3% of its dynamic stream, and
`ld`/`sd`/`lwu` for 9.4%. On Dhrystone the figures are 4.1% and 11.1%.
