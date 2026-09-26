# T8 — Cause-based stall accounting

## (a) Result summary

**Every cycle is now attributed to exactly one cause.** 112 runs (16 variants × Dhrystone,
CoreMark and the five FPGA Embench benchmarks). Both acceptance checks pass on all of them:

| check | result |
|---|---|
| exact partition: `sum(buckets) + retired-cycles == cycles` | **112 / 112** |
| monitor does not perturb: cycles and retired equal the production simulator's | **112 / 112** |
| cycles + retired equal the master `CPI and stalls` sheet | 30 / 32 (see note) |

Note: the two exceptions are RV64 IM_8SP and IM_8SP_withoutOpt CoreMark, 7 cycles apart
(20,909,384 vs 20,909,391). The sheet's profiling used a different image from the board
image (its own image column shows e.g. `coremark_RV64IM_100MHz` where the board runs
102 MHz). T8 uses each variant's **board image**, so it is consistent with the FPGA rows.

Counters live in the testbench of a separate build (`build_t8/`), never in the core; the
production simulators are untouched. Buckets, in priority order: `div_busy`, `mul_busy`,
`load_use`, `exec_use`, `csr_not_ready`, `mispredict_flush`, `taken_refill`,
`jump_redirect`, `stall_other`, `frontend_empty`.

### The headline: "load-use" on the 8-stage was two causes combined
`Hazard_Unit.v:124-125` (8-stage, both widths):

```verilog
assign exr_data_stall  = ex_data_stall || load_br_use_hazard;   // ALU producer in EX, or load in BR
assign load_use_hazard = exr_data_stall;                        // the profiled signal
```

So the master sheet's "load-use hazard ≈18%" on the 8-stage is `load-use OR execution-use`,
which is why it exceeded the extra cycles over 7SP_BRAM_Opt. Split at the source and
partitioned (RV64, Dhrystone, % of cycles):

| variant | CPI | load-use | exec-use | div | mul | mispredict | taken refill | jump | other stall | front-end empty |
|---|---|---|---|---|---|---|---|---|---|---|
| RV64I_5SP | 1.192 | – | – | – | – | 1.41 | 0.40 | 1.01 | 0.00 | 13.28 |
| RV64IM_5SP | 1.279 | 0.00 | – | 7.07 | 0.61 | 1.01 | 0.61 | 1.01 | 0.20 | 11.31 |
| RV64IM_6SP | 1.328 | 1.17 | – | 6.81 | 0.58 | 0.39 | 0.20 | 1.75 | 0.20 | 13.62 |
| RV64IM_7SP | 1.659 | 0.93 | – | 5.45 | 0.47 | 0.31 | 5.14 | 1.71 | 0.16 | 25.55 |
| RV64IM_7SP_BRAM | 1.819 | 1.14 | – | 4.97 | 0.43 | 0.43 | 4.54 | 1.85 | 8.95 | 22.74 |
| RV64IM_7SP_BRAM_Opt | 1.876 | 1.10 | – | 4.82 | 0.41 | 0.41 | 4.41 | 1.93 | 8.54 | 25.08 |
| RV64IM_8SP_withoutOpt | 2.142 | 1.93 | **8.57** | 4.22 | 0.36 | 0.60 | 3.87 | 1.33 | 7.12 | 25.33 |
| RV64IM_8SP | 2.199 | 1.88 | **8.58** | 4.11 | 0.35 | 0.59 | 3.77 | 1.29 | 6.82 | 27.14 |

**The 8-stage CPI regression is execution-use, not load-use.** True load-use stays near 1–2%
of cycles at every depth; execution-use (an ALU producer still in EX when the consumer needs
it, a consequence of the EXR stage) appears only at 8 stages and costs 8.6% of all cycles.
On CoreMark the same split is load-use 4.1% and execution-use 4.5% (RV64 IM_8SP).

Two more effects the single-signal view hid:
- **`taken_refill` jumps from 0.2% (6SP) to 4.4–5.1% (7SP+)**: the front-end refill after a
  correctly predicted taken branch, i.e. the 2-cycle cost T11.4 explains and T9 measures.
- **`stall_other` appears at 7SP_BRAM (8.5–9.0%)** and is absent on the LUTRAM builds: the
  synchronous-BRAM data memory's second store cycle and its fetch stalls.

## (b) Fragments
`t8_stall_breakdown.csv`: 112 rows, absolute cycles and % of cycles per bucket, plus the two
invariant flags. Suggested new master sheet: `Stall breakdown by cause`.

Scripts: `riscof-env/scripts/build_t8_sims.sh` (builds the instrumented simulators; also
marks the two hazard-unit wires `/*verilator public*/` **in its own copy**),
`riscof-env/scripts/t8_run.py` (runs and checks the invariants).

## (c) Contradicts the master file
1. `CPI and stalls`: "load-use hazard %" on the four 8-stage variants conflates load-use with
   execution-use. Replace with the two separate columns.
2. The stall columns in that sheet are **overlapping occupancies**, not a partition: pc/front-end/ID-EX
   are identical by construction and cannot be added. The new sheet is additive by construction.
3. Its per-variant cycles come from profiling images that differ from the board images on
   some variants (7-cycle differences on two rows); state which image each row used.
