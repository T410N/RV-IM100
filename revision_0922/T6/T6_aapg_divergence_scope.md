# T6 — AAPG divergence: minimal reproduction, trigger predicate, scope evidence

No RTL was changed. The monitors are testbench-only or post-process the existing retire tap.
The trigger-counting simulators are **separate copies** (`riscof-env/build_t6/`); the
production simulators in `build/` are untouched.

## (a) Result

**Acceptance met: trigger count = 0 on every reported workload, on all ten 7/8-stage variants.**

### Root cause (read-only)
`IF_IO_Register.v` in every 7/8-stage top (7SP l.36, 7SP_BRAM l.37, 7SP_BRAM_Opt l.35,
8SP/8SP_withoutOpt `est_squash` l.65, both widths):

```verilog
wire is_m_extend = (ID_opcode == `OPCODE_RTYPE) && (ID_funct7 == 7'b000_0001);   // RV64 8SP_withoutOpt also RTYPE_WORD
if (flush || (branch_estimation && !IF_IO_stall && !is_m_extend) || (jump && !IF_IO_stall)) ...
```

The IF/IO register normally squashes the sequential fetch behind a **predicted-taken**
branch (two bubbles: this slot plus `flush_reg`). When an **M-extension instruction is in ID**
at that moment, the squash is skipped. If the prediction is **correct**, EX raises no
mispredict, so nothing removes the admitted sequential instruction, and **it commits**.
5SP and 6SP have no IF/IO stage, so they are immune. This matches the AAPG failure set
exactly (all 7/8-stage variants, both widths).

### Minimal reproduction — `aapg-env/repro/t6_min2.hex`, `t6_min2_listing.txt`
Delta-debugged from `rv32im_s004` in two stages (`t6_ddmin.py`, then `t6_ddmin2.py`). Stage 2
uses an **architectural** oracle: the DUT must show a control-flow/branch-outcome violation
and the reference none. That rejects reductions which merely change the correct outcome.
The prologue seeds the architectural register state of s004 at pc 0x5d30. After that, only
these instructions execute (everything else in the window is NOP):

```
5db4  addi s3,s3,1
5dec  bge  s11,s3,0x5d84      # 564-iteration loop: the global 2-bit predictor saturates "taken"
5f5c  li   s3,10
5fe0  li   a7,10
6010  rem  gp,s9,a4           # M-extension op: in ID while the next branch is predicted in IF
6014  beq  s3,a7,0x601c       # architecturally taken (s3 == a7 == 10), correctly predicted taken
6018  (fall-through)  -> FAIL marker        601c (target) -> PASS marker
```

| variant | result | P3 branch-outcome errors |
|---|---|---|
| RV32IM_5SP, RV32IM_6SP | PASS | 0 / 565 |
| RV32IM_7SP, _BRAM, _BRAM_Opt, 8SP_withoutOpt, 8SP | **FAIL**: commits 0x6018 | 1 / 565 at 0x6014 |

A hand-written synthetic kernel with the same ingredients (48 variations of predictor
state, M-op type, divide-by-zero and gap) did **not** trigger. The exact fetch/decode
alignment matters, which is why the reduced real case is the reproducer.

### Predicates and monitors
| id | predicate | where evaluated | what it catches |
|---|---|---|---|
| **TRIG** | `clk_enable ∧ branch_estimation ∧ ¬IF_IO_stall ∧ is_m_extend` (the squash is suppressed) | per cycle, `build_t6` testbench monitor (`scripts/build_t6_sims.sh`) | the trigger itself |
| P1 | each committed PC is a legal successor of the previous committed instruction | retire trace (`scripts/cf_monitor.py`) | wrong-path commits, dropped instructions |
| P3 | each committed branch's direction agrees with the architectural operand values | retire trace (`cf_monitor.py`) | a branch whose committed outcome contradicts its operands |
| P2 | value-level lock-step against the same image on the 5SP (counter values taint-tracked) | two simulators (`scripts/lockstep.py`) | wrong register values |

TRIG does not change behaviour: cycle counts are identical to the production simulator
(checked on the reproduction and on s004).

### Sanity check (step 5): every timing-out AAPG test is caught
| AAPG status | TRIG fired (10 deep variants, 200 runs) | P1 ∨ P3 fired (all 16 variants, 320 runs) | P2 event (12 variants vs 5SP, 240 runs) |
|---|---|---|---|
| **TIMEOUT** | **127 / 127** | **127 / 127** | **127 / 127** |
| MATCH | 48 / 63 | 48 / 136 | 60 / 89 |
| MISMATCH | 10 / 10 | 9 / 57 | 9 / 24 |

Every timeout occurs on a 7/8-stage variant. TRIG also fires on 58 completing programs; the
admitted instruction is harmless in those (already dead, or overwritten). The MISMATCH
entries are mostly the link-address artefact against Sail (T12), not a DUT error. P1/P3 fire
on none of the 5SP/6SP runs.

### Scope (step 4): trigger count on every reported workload
TRIG, all ten 7/8-stage variants (`trigger_counts_*.csv`):

| workload | runs per variant | TRIG |
|---|---|---|
| **CoreMark, full board binary** (each project's `.mem`, run to completion: 1.3–2.7 G cycles) | 1 | **0** |
| **Dhrystone, full board binary** (300,000 iterations) | 1 | **0** |
| CoreMark 10-iteration / Dhrystone 1000-iteration images | 1 + 1 | 0 |
| Embench, all 19 (huffbench/slre/wikisort in their 12 KB-stack builds) | 19 | 0 |
| micro-kernels (all images of the matching XLEN) | 151 (RV32) / 187 (RV64) | 0 |
| AAPG | 20 | fires (see above) |

Cross-checks on the same workloads:
- **P3: no branch-outcome error on any reported workload**, except the separate RV64IM_7SP defect below. **No misaligned access** in any reported workload.
- **P2: 0 value divergences** on CoreMark, Dhrystone and all completing Embench on every
  6/7/8-stage variant of both widths, versus the 5SP (≈74–77 M instructions compared per
  variant). The one exception is RV64IM_7SP qrduino, below.

**Conclusion for the paper:** the AAPG divergence is a real RTL defect in all 7/8-stage
variants: a correctly predicted taken branch commits one wrong-path instruction when an
M-extension instruction occupies ID. Its trigger condition **never occurs** in any workload
whose cycle count, CPI or throughput is reported, so none of those numbers is affected. It
is found only by randomized testing.

## Other defects found by the same monitors (not the AAPG mechanism)
1. **CSR-read / `ret` fall-through** (5SP, 6SP, 7SP both widths; RV64 7SP_BRAM). A `ret`
   shortly after `csrr mcycle` loses its redirect and execution falls into the next function.
   It happens once per Embench run inside the board-support harness (`start_trigger` falls
   into `stop_trigger`) and 2–3 times in CoreMark's `start_time`. The effect is benign (same
   return address; the values are overwritten by the real call). Measurable consequence: the
   affected variants execute 13–14 extra harness instructions in the timed region, which is
   exactly the unexplained per-variant minstret offset in the RV64 Embench FPGA sheet
   (3,016,347 / 3,016,346 vs 3,016,333). About 20–30 cycles per run (< 0.001%).
   7SP_BRAM_Opt, 8SP_withoutOpt and 8SP do not have it.
2. **RV64IM_7SP wrong-path commit after a taken back-edge.** Once per CoreMark iteration
   (`mv a1,s1` at `core_bench_list+0x1ec`) and once at boot (`lh` after `jal main`, which
   writes `a0`). Harmless in CoreMark. It is the un-fixed IF/IO bubble logic that STATUS.md
   flagged as a latent candidate for the 7SP_BRAM defect. TRIG does not count it; P1/P3 do.
3. **RV64IM_7SP wrong byte loads.** `lbu` at qrduino 0x240c returns 0 instead of 0x13/0x22,
   12 times per run (the "ROM byte read as 0x00" noted in STATUS.md). qrduino still passes
   verify. Only the simulation-matrix row for RV64IM_7SP qrduino is affected.

(1)–(3) do not affect any FPGA-reported number. (2) and (3) are confined to the
ablation-only RV64IM_7SP. The RV64IM_7SP rows (CoreMark/Embench simulation) should carry a
footnote.

## (b) Fragments
`trigger_counts_all_workloads.csv` (2,100 runs), `trigger_counts_board_binaries.csv` (20),
`p1_controlflow_*.csv`, `p2_lockstep*.csv`, `t6_min2.hex`, `t6_min2_listing.txt`,
`t6_ddmin*.json`.

## (c) Contradicts the master file / STATUS.md
- STATUS.md: "the hang is a symptom of a data divergence, not a control-flow bug". In fact
  it is a control-flow bug (a wrong-path commit). The loop guard's operands are correct; the
  committed path is not.
- The Verification sheet's "affects no reported measurement" is now **proven** for the AAPG
  defect (TRIG = 0 everywhere). Add the three secondary defects above, with their stated
  (negligible or ablation-only) scope.
- "RV64IM_7SP … passes every suite" (STATUS.md): it passes, but it computes wrong values on
  qrduino and commits wrong-path instructions on CoreMark.
