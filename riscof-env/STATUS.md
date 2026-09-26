# Verification status

## Verified, all 16 SoC variants

| Suite | Result |
|---|---|
| riscv-arch-test 2.7.4 via RISCOF, Sail reference | 851/851 |
| riscv-tests (Berkeley) | 883/899 -- the 16 failures are all `ma_data` |
| AAPG randomized, Sail co-simulation | see below, NOT clean |

`ma_data` is misaligned data access: optional in RISC-V, these cores trap and
do not implement `mtval`.  `fence_i` is excluded family-wide (needs Zifencei).

## Open defect: RV64IM_8SP differs from Sail

`aapg-env/repro/pristine_2925.S` is a 2925-instruction prefix of an
unmodified AAPG program.  On the identical ROM image:

    RV64IM_5SP / 6SP / 7SP    0 real differences vs Sail
    RV64IM_8SP                1 real difference  (signature word 3064)

(5 further words differ purely because the DUT links at 0x00000000 and Sail's
RAM base is fixed at 0x80000000; those are identified by running Sail against
itself at two link addresses and excluded.  See below.)

Three cores agreeing with the golden model on the same binary rules out the
harness.  8SP is wrong.  Not yet root-caused.

## Open defect: 7SP and deeper hang

9-16 of 20 randomized programs never terminate on 7SP, 7SP_BRAM,
7SP_BRAM_Opt, 8SP, 8SP_withoutOpt, in both RV32 and RV64.  5SP and 6SP
complete all 20, as does Sail.  Stuck rather than slow: memory state is
byte-identical at 20M and 200M cycles.  Reproduced with *unmodified* AAPG
output, so it is not an artifact of the rewrites in `gen_aapg.py`.

The trigger is a backward-jump block whose guard (`beq x18, x19`) reads
registers no instruction in the loop writes, so termination depends entirely
on values computed earlier -- i.e. the hang is a *symptom* of a data
divergence, not a control-flow bug in itself.

7SP matches Sail through instruction 2925 yet still hangs on the full
program, so its divergence is later than 8SP's.  Treat them as separate
defects until shown otherwise.

## Traps this harness has already sprung -- read before trusting a result

1. **The write tap.**  `SIM_dmem_write_enable` originally mirrored
   DataMemory's `write_enable` *port*.  On the BRAM-backed and 8-stage
   designs that is not the write: the module gates it with `!write_phase`,
   and the top re-points `address` at a load in EX2 for the store's second
   cycle.  The shadow RAM recorded a store that never happened, at the load's
   address.  This produced a *completely convincing* fake RTL defect --
   affecting exactly the four variants with the EX2 address mux, hidden by a
   single nop, byte-identical within `_Opt`/`withoutOpt` pairs.  Fixed by
   qualifying with `write_done`.
   **Lesson: a clean variant split is equally consistent with "these variants
   are broken" and "my instrumentation misreads these variants."**

2. **Always run the control.**  The check that would have caught (1) in
   minutes: run an *unmodified* AAPG program.  Any finding that depends on
   generated or rewritten programs must be reproduced without the rewrites.

3. **Link-address dependence.**  The DUT runs from ROM at 0x00000000; Sail's
   RAM base is fixed at 0x80000000 with no `--ram-base`.  `auipc`, and AAPG's
   `jal`/`jalr` links and `la`-to-label targets, put PCs into registers the
   program computes on, and the divergence cascades.  `gen_aapg.py` removes
   most of it; the residue is *measured* by running Sail against itself at two
   link addresses and excluded.  That exclusion under-detects: the shift is
   0x40000, so words depending only on high address bits do not move.
   **Prefer DUT-vs-DUT on the same ROM image -- it has no artifact at all.**

4. **Never compare a timed-out signature.**  The testbench dumps a signature
   however the run ended.  A hung run's signature differs wildly and looks
   like divergence.  Check status first.

5. **Bisect hazards.**  Truncating a program can orphan a forward branch
   label, so the prefix will not assemble; and a prefix can hang.  Neither is
   evidence of divergence.  Skipping forward past `hi` makes the search
   non-monotonic and it will spin forever -- this happened.

6. **`pgrep -f "foo.py"` matches its own command line.**  `until ! pgrep -f
   ...` never exits.  Four such waiters ran until killed by hand.

## Tools

sim: `scripts/prepare_rtl.py` then `scripts/build_sim.sh all` (RVIM_SOURCE=socs)
run: `scripts/run.py`, `scripts/run_rvtests.py`, `scripts/run_aapg.py`
bisect: `scripts/bisect_aapg.py --good <v> --bad <v>` (DUT-vs-DUT, no artifact)

## 8SP defect, characterised (2026-09-03)

Reproducer: `aapg-env/repro/dropped_store_1047.S` -- a 1047-instruction
prefix of an unmodified AAPG program.  Build with `dut.ld -DRVIM_DUT`, run,
and compare signature word 3064:

    correct (5SP, 6SP, 7SP, 7SP_BRAM, 7SP_BRAM_Opt, Sail)   131ddf00
    RV64IM_8SP and RV64IM_8SP_withoutOpt                    131ddfa9

**The store is dropped, not miscomputed.**  0xa9 is the *untouched seed byte*
from `.data`; 0x00 is what `sb t6, -0x40(sp)` should write.  The 8SP cores
never perform the write.  Sail's trace confirms the architectural value:

    [17656] sd    s5, -0x3a8(sp)      store 1, lands correctly
    [17657] and   t6, s3, a0          t6 <- 0x0
    [17658] sb    t6, -0x40(sp)       mem[0x801037E0] <- 0x00   -- dropped on 8SP

Ruled out so far:

* **Not the store-data forwarding mechanism.**  8SP uses a hold register with
  a 4-source chain and no retire term; 8SP_withoutOpt uses a retire term with
  a 5-source chain and no hold register.  They fail *byte-identically*.  And
  6SP has exactly withoutOpt's structure and is correct.  Structure is not
  the discriminator.
* **Not plain ALU-to-store forwarding.**  `and` then `s{b,h,w,d}` at 0-2
  instructions of separation: all variants agree.
* **Not store-to-store spacing.**  Two stores 0-3 instructions apart: all
  variants agree.
* **Not divider interaction.**  `divuw` 0-4 instructions before two stores
  0-3 apart, 20 combinations: all variants agree.

Next step: delta-reduce `dropped_store_1047.S` against the oracle
"8SP's byte at the sb target differs from 5SP's".  Synthetic guessing has
now failed three times; shrink the real failing case instead.

## Reduction outcome (2026-09-03)

`aapg-env/repro/min2.S` -- 56 instructions plus scaffolding, converged (not
budget-capped).  Only RV64IM_8SP and RV64IM_8SP_withoutOpt diverge; 5SP, 6SP,
7SP, 7SP_BRAM and 7SP_BRAM_Opt agree.  Signature word 148 differs.

**The failing store is in crt_dut.S's own .data copy loop**, not in the AAPG
body:

    [1992] ld t3, 0x0(t0)
    [1993] sd t3, 0x0(t1)      <- wrong data on 8SP

That also explains why every reduction pass "drifted" to a different failing
word: removing body instructions changes .text size, which moves _data_lma,
which changes the ROM addresses the copy loop reads.  The defect is
address/timing dependent, so it surfaces at a different dword each time.

An earlier boot-only test (same copy loop, no program body) passed 4096/4096,
so the loop is not unconditionally broken -- it fails for particular
address/timing combinations.

### Hypotheses tested and refuted -- do not retry

1. ALU-to-store forwarding (`and` then `s{b,h,w,d}`, 0-2 separation)
2. Store-to-store spacing (0-3 instructions apart)
3. Divider then two stores (20 combinations of separation)
4. Store-forward chain *structure* -- 8SP uses a hold register and no retire
   term, 8SP_withoutOpt uses a retire term and no hold register, they fail
   byte-identically, and 6SP shares withoutOpt's structure and is correct
5. Divide-by-zero special cases (`div`/`divu`/`rem`/`divw` by zero all
   architecturally correct on every variant)
6. Tight ld->sd copy loop in isolation (64/512/2048 dwords, all variants agree)

### Why the next step needs better observability

Six synthetic reproductions have failed.  The symptom is visible only as a
wrong *memory word*, which is many cycles downstream of the cause, and the
DUT has no retire-level trace to diff against Sail's.

Recommended: add a retire tap to `prepare_rtl.py` (retired PC + instruction +
register write, one per cycle) and diff it against Sail's `-v` trace to find
the first *architecturally* divergent instruction, rather than the first
divergent memory word.  That is far cheaper than a full RVFI port and is the
information the search has been missing.

## 8SP divider defect -- located (2026-09-03)

Reproducer: `aapg-env/repro/min2.S` (+ `min2.hex`).  Waveform:
`aapg-env/repro/8SP_divw_bug.vcd`, cycles 38480-38700.

Regenerate:

    VCD=1 RVIM_SOURCE=socs scripts/build_sim.sh socs_RV64IM_8SP
    build/socs_RV64IM_8SP/Vsim_top +HEX=aapg-env/repro/min2.hex \
      +MAX_CYCLES=39000 +VCD=out.vcd +VCD_START=38480 +VCD_END=38700

### The divergence

First architecturally wrong instruction, after 15441 identical retires:

    pc 0x5a4   0x02dfc83b   divw a6, t6, a3     (t6 = 0x37730000, a3 = 4)
      5SP / 6SP / 7SP / Sail : a6 = 0x0ddcc000
      8SP / 8SP_withoutOpt   : a6 = 0x0beb5d3d      RTL cycle 38606

### The mechanism -- the division itself is NOT wrong

From the waveform (`divider_word`, approximate RTL cycles):

    38527  division_start
    38528  dividend_reg = 0xe5997aff    (s6)  correct  } divuw a3, s6, t6
    38529  divisor_reg  = 0x37730000    (t6)  correct  }
    38563  quotient_reg = 0x4                 correct  }

    38566  division_start
    38567  dividend_reg = 0x2fad74f4    WRONG, should be 0x37730000 (t6)
    38568  divisor_reg  = 0x4           correct (a3)
    38602  quotient_reg = 0x0beb5d3d

0x2fad74f4 / 4 = 0x0beb5d3d exactly.  The divider divided correctly; it was
handed the wrong dividend.  `Divider_WORD.v` is **byte-identical** between
6SP and 8SP, so the module is not at fault.

### Where to look

`ALU.v` feeds the divider from `src_A`/`src_B`, and in the 8SP core those are
`EX_src_A`/`EX_src_B` -- commented in the source as "CHANGED: registered from
EXR_EX".  The 8SP is the only variant that *registers* the ALU operands in an
extra EXR_EX stage.  A stale value latched there cannot correct itself, which
matches the observation that the dividend is wrong while the older divisor is
right.

Note also that Divider_WORD samples its inputs across **two** cycles:
`dividend_reg` on `division_start`, then `remainder_quotient`/`divisor_reg`
from the *live* ports during INITIALIZE.  So the operands must be stable for
two consecutive cycles -- an assumption the 8SP's registered operand path may
not satisfy.

### What is NOT the fix

Adding `!load_use_hazard` to `div_start` (making 8SP match 6SP/7SP) was tried
and **reverted**: it took 8SP from 1 to 39 real differences against Sail, and
the matching `mul_start` change broke every riscv-tests `mul*` test.  In the
8SP, `load_use_hazard` is assigned from `exr_data_stall` -- an EXR-stage
signal -- while the divider starts in EX, so the term does not mean there what
it means in the shallower cores.

## CPI / stall profiling (2026-09-06)

`scripts/profile_all.py` -> `logs/profile.csv`, `logs/profile_report.txt`.

Counters live in the simulation wrapper, never in the core, so nothing added
for measurement can affect synthesis, timing or area: the RTL profiled is the
RTL that produced the Fmax and power numbers.

Method: each variant runs the ROM image from its *own* Vivado project, stopped
after a fixed number of retired instructions (default 10M).  A fixed
instruction budget rather than a fixed cycle budget is what makes CPI
comparable across depths -- identical work, only cycles differ.

Caveats to state in the paper:

* `minstret` (and this counter) exclude NOPs, matching the cores' own
  definition.  This shifts IPC slightly against a Sail-counted total.
* The I-only variants necessarily run *different binaries* from the IM
  variants (software multiply), so CPI is comparable within the IM family and
  across pipeline depth, but not directly between I and IM.
* These are fixed-instruction windows, not complete benchmark runs.  The
  published scores still come from the FPGA runs.
* 0x10010000 is both the UART transmit register and the harness halt address,
  so benchmark runs need +NOHALT or the first printf ends the run.
* Stall signals propagate backwards through the pipeline, so pc/front-end/ID-EX
  percentages move together; they are one stall seen at several stages, not
  additive.

### Headline numbers (Dhrystone, 10M instructions)

    variant                CPI      load-use    div busy
    RV64IM_5SP            1.279       n/a         7.1%
    RV64IM_6SP            1.328       1.4%        6.8%
    RV64IM_7SP            1.660       1.1%        5.5%
    RV64IM_7SP_BRAM       1.820       1.3%        5.0%
    RV64IM_7SP_BRAM_Opt   1.877       1.2%        4.8%
    RV64IM_8SP            2.200      18.0%        4.1%
    RV64IM_8SP_withoutOpt 2.144      17.7%        4.2%

Three results that answer specific reviewer points:

* **R3.4** (IO stage vs BRAM confounded): 7SP 1.660 -> 7SP_BRAM 1.820 isolates
  the synchronous-BRAM change from the structural one.
* **R1.2 / R2.4 / R3.1** (optimizations confounded with depth): the timing
  optimizations *cost* CPI while raising Fmax -- 8SP 2.200 vs withoutOpt
  2.144, 7SP_BRAM_Opt 1.877 vs 7SP_BRAM 1.820.
* **R1.3** (stall breakdown): load-use hazard cycles jump from ~1.2% at 7SP to
  ~18% at 8SP.  That single term accounts for most of the 8-stage CPI
  regression and substantiates the paper's execution-use-hazard argument.

Branch mispredictions are identical across 5SP/6SP/7SP (same binary, same
predictor) and rise slightly at 7SP_BRAM and 8SP, where predictor state
updates later relative to fetch.  Misprediction rate is ~19-22% of branches on
Dhrystone and ~41-42% on CoreMark.

## 8SP defect #1 -- FIXED (2026-09-06)

Root cause: the 8-stage core resolves ALU operands through a forwarding mux
whose lowest-priority source is the one-deep *retire* shadow.  While EXR is
stalled a producer can drain out of that shadow before the stalled consumer
advances; `hazard_retire` deasserts, `alu_forward_source_select_*` falls to
3'b000, and the mux takes `EXR_read_data1` -- the register-file value sampled
back in ID, which predates the producer entirely.

Waveform (`aapg-env/repro/8SP_divw_bug.vcd`):

    t=188  EXR_EX_stall=1  select_a=5 (retire)     correct forward
    t=190  EXR_EX_stall=0  select_a=0              producer drained
                           EXR_src_A=0x..2fad74f4  stale regfile value
    t=192  div_start=1     EX_src_A =0x..2fad74f4  divider gets 0x2fad74f4

0x2fad74f4/4 = 0x0beb5d3d, the wrong divw result exactly.

Fix: `EXR_src_A_hold` / `EXR_src_B_hold` in the 8SP tops -- latch the resolved
operand while a forward is valid, reuse it until the instruction advances.
This is the same pattern the store-data path already used
(`EXR_store_data_hold`); the ALU operand path had simply never been given it.
Applied to all 10 top files.

Verified: all four AAPG reproducers 0 differing words; RISCOF 46/46 + 63/63
clean on the four 8SP variants; riscv-tests unchanged at 226/230; Embench
`edn` now passes everywhere and `ud` passes on RV64IM_8SP.

**A rejected fix, for the record:** adding `!load_use_hazard` to `div_start`
(making 8SP match 6SP/7SP) took 8SP from 1 to 39 differences against Sail and
the matching `mul_start` change broke every riscv-tests `mul*` test.  In the
8SP, `load_use_hazard` comes from `exr_data_stall`, an EXR-stage signal, while
the divider starts in EX.

## 8SP defect #2 -- SAME defect as #1; both FIXED

Defects #1 and #2 turned out to be one mechanism, not two.  The first patch
cleared the operand hold on `EXR_EX_stall`, which gates the EXR->EX register.
The signal that actually marks how long one instruction occupies EXR is
`ID_EXR_stall`, which gates the EXR stage register itself, and it can stay
asserted a cycle longer.  Clearing early let the stale latched operand through
on the longer stalls -- which is why the first patch fixed the short-stall
cases (divw, edn) and missed the store case.

    cyc    ID_EXR_stall  EXR_EX_stall  rs1  sel_a  hold_valid  EXR_src_A
    12401       1             0        0xb    4        0       0x1000007c  ok
    12402       1             1        0xb    5        0       0x1000007c  ok
    12403       1             0        0xb    0        1       0x1000007c  hold engaged
    12404       0             0        0xb    0        0       0x10000078  cleared too early

Corrected in all 10 top files.  Results below.

## Old heading kept for history: defect #2 as first written

`nettle-sha256`, `picojpeg` and `qrduino` still fail on all four 8SP variants.
5SP, 6SP, 7SP, 7SP_BRAM and 7SP_BRAM_Opt produce bit-identical traces.

The trace tooling now logs stores as well as retires, which is what found it:
the first divergent *retire* is #4569515, but the first divergent **store** is
#206, four and a half million instructions earlier.  A store-only defect stays
invisible until something loads the corrupted value back.

    instruction:  sb a6, -4(a1)     in a loop doing addi a1, a1, 4
    5SP  addr=0x10000079 mask=0x02
    8SP  addr=0x10000075 mask=0x20      <- 4 bytes low, one iteration stale

Address and mask are internally consistent, so it is one wrong address rather
than a mask bug: the store used a stale base register.  Same class as defect
#1 but on the store-address path, and not cured by the operand hold.

Reproduce deterministically with `embench-env/boardsupport_notiming.c` -- the
normal build reads mcycle, whose value legitimately differs between
microarchitectures, so a trace diff otherwise reports the cycle counter as the
first divergence and buries everything after it.


## Verification after the operand-hold fix (2026-09-07)

    RISCOF          851/851, all 16 variants, zero failures
    riscv-tests     226/230 on the 8SP variants (ma_data only), unchanged
    AAPG repros     all four at 0 differing words
    Embench         8SP verify-failures 5 -> 1 per variant

Embench remaining failures are three unrelated defects in three different
variant groups -- none of them the 8SP operand path:

  picojpeg        all four 8SP variants.  Unexplained.  A branch-flush
                  hypothesis was tested and REFUTED: branch_prediction_miss
                  never asserts near the divergence, and the only
                  EX_EX2_flush pulses are ~20 cycles earlier.  What is
                  established is that an extra instruction from the
                  fall-through path (pc 0xb28) commits between the branch
                  (0xb20) and its target (0xba4), with no misprediction
                  signalled and the condition register holding 0xfb on both
                  cores.
  ud              RV32IM 6SP / 7SP / 7SP_BRAM / 7SP_BRAM_Opt only.  Not RV64,
                  and no longer RV32IM_8SP.  RV32-specific, middle depths.
  qrduino,        RV64IM_7SP_BRAM only.  7SP_BRAM_Opt is clean, so it is
  sglib-combined  specific to the un-optimised BRAM build.

Timeouts: wikisort (16/16) and slre/huffbench (all RV64, including the
known-good 5SP) are the 400M-cycle simulation cap, not defects.  statemate
(four 8SP only) remains depth-correlated and unexplained.

**The four 8SP variants need re-synthesis and re-implementation before their
Fmax/area/power rows can be trusted** -- the operand hold adds two XLEN-wide
registers and a mux level to the EXR path.

## Divider operand-latch defect -- FIXED (2026-09-07)

`ud` failed on RV32IM 6SP / 7SP / 7SP_BRAM / 7SP_BRAM_Opt.

Root cause: `Divider_WORD` and `Divider_DWORD` latch `dividend_reg` at
`division_start` and then **ignore it**, re-reading the live `dividend` and
`divisor` ports one cycle later in INITIALIZE to build `remainder_quotient`
and `divisor_reg`.  The divider therefore required its operands to stay valid
for two consecutive cycles -- an undocumented contract the pipeline does not
honour when the operand arrives by a load-use forward.

    cyc 5505  division_start=1  src_A=0x28 ok   src_B=0x11 ok   dividend_reg <- 0x28 ok
    cyc 5506  INITIALIZE        src_A=0x10001554 -- operands already moved on
                                remainder_quotient <- 0x10001554  (the live port)

0x10001554 / 0x11 = 0xF0F232, exactly the wrong quotient observed, in place of
0x28 / 0x11 = 2.

Fix: latch the divisor at `division_start` as well, and have INITIALIZE use
the latched copies.  The divider now needs its operands valid only on the
start cycle.  Applied to 62 divider files; the six 5SP copies use an older
divider with no `dividend_reg` at all and pass every suite, so they are left
alone.

Note this is a *different* defect from the 8SP `divw` failure in the same
module: there the operand was already wrong at the start cycle (fixed by the
EXR operand hold), here it is correct at start and wrong one cycle later.

## Store logging in the trace was level-triggered

Fixed to edge-triggered.  A store held across stall cycles was recorded once
per cycle, so the 6-stage core logged one store four times and store indices
could not be aligned between variants.  The write itself is idempotent -- only
the logging was wrong -- but any earlier conclusion drawn from store *counts*
or *indices* should be re-derived.

## qrduino / sglib-combined on RV64IM_7SP_BRAM -- located, not fixed

Comparing against 7SP_BRAM_Opt, which passes and has an identical store count:

    both:  pc=001ed4  08f4e863  bltu x9, x15, ...
    Opt:   pc=001f64  <- branch target, executed
    BRAM:  pc=001f68  <- lands one instruction past the target

The branch redirect is off by four on 7SP_BRAM: it begins executing at
target+4 and silently drops the instruction at the target.  Not the operand
or divider path.

Also noted while investigating: **RV64IM_7SP reads ROM byte 0x2c72 as 0x00
where the image holds 0x13**, and still passes qrduino.  That is a separate
latent defect in a variant currently reported as clean, and needs its own
investigation.

## qrduino / sglib-combined on RV64IM_7SP_BRAM -- waveform (2026-09-07)

`aapg-env/repro/7SP_BRAM_branch_bug.vcd`, cycles 18350-18400; the event is at
18368-18369.  Reproduce with `qrduino.hex` built from the timing-free board
support, `+HALT_ADDR=10012000`.

    cyc    IO_insn   ID_insn   EX_insn     IF_IO/IO_ID/ID_EX/EX_EX2 flush
    18368   14f793      13     8f4e863     0 0 0 0     0x1f64 in IO, bltu in EX
    18369   84851b      13        13       0 0 0 0     0x1f64 GONE, ID got a bubble
    18370  2078463   84851b       13       0 0 0 0     0x1f68 proceeds normally

The branch `bltu` at 0x1ed4 targets 0x1f64 (offset 0x90, verified by decode).
The target instruction *was* fetched -- `pc` reached 0x1f64 at cycles
18366-18367 -- and reached the IO stage.  On the cycle the branch resolved in
EX it disappeared in the IO->ID transfer while **no flush signal was
asserted**, and the following instruction (0x1f68) advanced normally.

So this is neither a wrong branch target nor the visible flush logic: a
correctly-predicted taken branch silently drops the instruction sitting in IO
as it resolves.

Refuted along the way, do not retry:
  * PC_Controller, Branch_Predictor and Branch_Logic are byte-identical
    between 7SP_BRAM and 7SP_BRAM_Opt.
  * The branch redirect wiring into PC_Controller is identical; only the jump
    path differs (EX_jump/alu_result vs EX2_jump/EX2_alu_result), and the
    failing instruction is a branch, not a jump.
  * The branch_prediction_miss flush block in Hazard_Unit is identical between
    the two builds; only the jump branch of that block differs.

## RV64IM_7SP_BRAM branch defect -- ROOT-CAUSED AND FIXED (2026-09-07)

`qrduino` and `sglib-combined` failed on socs_RV64IM_7SP_BRAM only.

### Mechanism

`IF_IO_Register` injects fetch bubbles after a redirect, because the BRAM
instruction memory is synchronous and costs an extra fetch cycle:

    line 37  flush | branch_estimation | jump  -> flush_reg <= 1, IO <= NOP   (bubble 1)
    line 44  flush_reg && !IF_IO_stall         -> flush_reg <= 0, IO <= NOP   (bubble 2)
    line 69  load_use_hazard && flush_reg      -> is_load_use_hazard <= 1
    line 50  is_load_use_hazard                -> IO <= NOP                   (bubble 3)

`IF_IO_stall` *defers* bubble 2 by a cycle.  Line 69 does not account for that
and schedules a third bubble anyway, so the extra NOP lands one cycle after the
redirect is already covered -- and by then IF holds the branch **target**,
which the NOP overwrites.  The branch therefore resumes one instruction past
its target.

Waveform (`aapg-env/repro/7SP_BRAM_branch_bug.vcd`), signal names exact:

    cyc    IF_insn    ID_insn  br_est stall lu_haz flush_reg is_lu_haz
    18365  10000a97  ff27879b    1     0      0        0         0    predictor redirect
    18366  18aaca83   8f4e863    0     1      1        1         0    stall defers bubble 2
    18367  18aaca83   8f4e863    0     0      0        1         1    bubble 2 emitted late
    18368    14f793        13    0     0      0        0         1    bubble 3 EATS the target
    18369    84851b        13    0     0      0        0         0

### Fix

    -  if (load_use_hazard && flush_reg) begin
    +  if (load_use_hazard && flush_reg && !IF_IO_stall) begin

Only schedule the extra bubble when bubble 2 was actually emitted this cycle.
Applied to the three RV64IM_7SP_BRAM copies of IF_IO_Register.v; saved as
`rtl-patches/7SP_BRAM_if_io_bubble_fix.patch`.

### Why only this one variant

* **_Opt has no injector at all** -- lines 30/31/39/50-62/69-71 are absent
  from every `*_7SP_BRAM_Opt` copy.  So the fix does NOT duplicate an _Opt
  change; _Opt avoids the bug by not having the mechanism.  The ablation pair
  remains distinct.
* **RV32 has it but it is dead code**: the RV32 copies read
  `if (load_use_hazard && flush_reg && is_load_use_hazard)` -- self-referential,
  so `is_load_use_hazard` can never become 1.  That is why RV32IM_7SP_BRAM
  never failed.
* The same live injector is also present in **7SP and 8SP** variants
  (RV32s/RV64s SoCs+cores+codes).  Left untouched here: 8SP belongs to a
  concurrent investigation, and 7SP shows no failure.  Both are latent
  candidates for the same defect.

### Refuted

PC_Controller / Branch_Predictor / Branch_Logic byte-identical between the two
builds; branch redirect wiring identical; the branch_prediction_miss flush
block identical.  The parent's reading that "no flush was asserted" was
correct but incomplete -- the squash is inside IF_IO_Register, not in the
hazard unit's flush signals.  Also note an earlier trace table mislabelled
IF_instruction as IO_insn (both live in scope if_io_register); the corrected
labels are above.


## picojpeg on the four 8SP variants -- ROOT-CAUSED AND FIXED (2026-09-07)

`picojpeg` verify-failed on exactly `RV32IM_8SP`, `RV32IM_8SP_withoutOpt`,
`RV64IM_8SP` and `RV64IM_8SP_withoutOpt`, and passed on the other twelve.

### The mechanism

Not a missed flush.  The earlier branch-flush hypothesis stays REFUTED:
`branch_prediction_miss` never asserts at the divergence.  This is the
*predicted-taken* path, which is a different mechanism entirely --
`branch_estimation` redirects the PC and is never even wired to
`Hazard_Unit.v`, so the whole squash happens inside `IF_IO_Register.v`.

When the predictor calls a branch taken, the PC keeps issuing sequential
fetches until the redirect lands.  **How many wrong-path fetches escape is not
fixed** -- it depends on whether `IF_IO_stall` / `exr_data_stall` stretch the
shadow.  The existing squash machinery in `IF_IO_Register.v` covers only some
of the cases:

  * the `branch_estimation` arm squashes the slot entering IO;
  * `flush_reg` squashes one more -- but the `exr_data_stall` arm clears
    `flush_reg`, cancelling exactly that second squash;
  * `is_load_use_hazard` squashes one more -- but only when a load-use hazard
    happens to be live at that moment.

picojpeg falls in the gap.  At the taken `bnez a5,0xba4` at pc 0xb20 the
shadow is two fetches deep and no load-use hazard is pending, so the second
wrong-path fetch survives.  Waveform, 8SP, `if_io_register` internals:

    cyc   IF_pc  IF_insn   IO_pc  IO_insn  branch_est  IF_IO_stall
    6257   b24   400793     b20   8079263      1            0    predict taken -> ba4
    6258   b28  10000717      0      13        0            1    b24 squashed  OK
    6259   b28  10000717      0      13        0            1
    6260   b28  10000717      0      13        0            0
    6261   ba4  10000717     b28  10000717     0            0    b28 enters IO  WRONG
    6262   ba8  e1974703     ba4  10000717     0            0

pc 0xb28 then commits.  Over the run it retired **2010** times against 18
legitimate executions.

Control (Trap 2 -- always run the control): on the identical ROM image, 6SP
and 7SP show **0** extra retires against 5SP.  8SP-only, so the fix is scoped
to the 8SP files.

Note when tracing this: 0xb28 and 0xba4 hold the *same encoding*
(`10000717`), so per-stage instruction registers cannot tell wrong-path from
correct-path.  Extract per-stage **PC** registers instead.

### The fix

Rather than trying to predict the shadow depth, track the outstanding redirect
and refuse to admit any instruction whose PC is not the predicted target.  In
`IF_IO_Register.v` (8SP only): new inputs `branch_target` and
`branch_prediction_miss`, an `est_pending` / `est_target` pair, and a squash
arm for `est_wrong_path`.  Wired in all 10 8SP top files.

This is correct for a shadow of any depth and, unlike a blanket "squash one
more", cannot drop the target itself.

### Two rejected fixes, for the record

**(a) Hold `flush_reg` through the `exr_data_stall` arm.**  Cures 0xb28
exactly (2010 -> 18) but *drops* pc 0x126c, the loop head of the short
backward branch `bne a5,a2,0x126c` at 0x128c: there the shadow is only one
deep, `is_load_use_hazard` already squashes it, and the held `flush_reg` adds
a second squash that eats the branch target.  This is why the new arm also
clears `is_load_use_hazard`.

**(b) Latching the predicted target before checking for a real redirect.**
Livelocked the core at cycle 51397.  `branch_prediction_miss` and
`branch_estimation` can assert on the SAME cycle (at pc 0x1100): the miss wins
in `PCController` and the PC goes to 0x10f4, so a shadow waiting on the
predicted 0xef8 never closes and the pipeline squashes forever.  **Clear on a
real redirect first, latch the prediction second.**

### Verification

Retire streams, deterministic picojpeg image built with
`boardsupport_notiming.c`, 8SP vs 5SP: **4,337,116 instructions identical** --
zero value divergences, zero insertions, zero deletions.  (Diff retire and
store streams separately, and use an alignment-tolerant diff: an index-based
compare reports every entry after the first insertion as different.)

The 8SP store stream has ~1.6x the line count of 5SP for the same program --
that is the byte-bank write tap granularity, not a divergence.  Cross-variant
store-line *counts* are not comparable; the retire stream is.

# CORRECTNESS COMPLETE (2026-09-07)

    RISCOF vs Sail   851/851   all 16 variants, zero failures
    riscv-tests      883/899   ma_data only -- misaligned access is optional in
                               RISC-V; these cores trap and do not implement mtval
    Embench-IoT      verify-fail 0 on all 16 variants

Remaining Embench no-results are `wikisort` (16/16), `slre` and `huffbench`
(all RV64).  Each also times out on the known-good 5SP, so they are the 400M
cycle simulation cap, not processor defects.  `statemate`, which previously hung
on the four 8SP variants and was the one depth-correlated timeout, now
completes -- the 8SP IF/IO fix resolved it.

## Defects found and fixed this session

1. **8SP stale ALU operand.**  A producer drains out of the one-deep retire
   shadow while EXR is stalled; the forward select falls to 0 and the mux takes
   the register value sampled back in ID.  Fixed with `EXR_src_A/B_hold`,
   cleared on `ID_EXR_stall` (clearing on `EXR_EX_stall` was a first attempt
   that fixed only the short-stall cases).
2. **Divider operand latch.**  `Divider_WORD`/`Divider_DWORD` latched
   `dividend_reg` at `division_start` then re-read the *live* ports in
   INITIALIZE, requiring operands stable for two cycles.  Latch both at start.
3. **7SP_BRAM IF/IO bubble.**  The load-use bubble injector ignored
   `IF_IO_stall` deferring a redirect's second bubble, so a third bubble
   overwrote the branch target sitting in IF.
4. **8SP IF/IO redirect shadow.**  A fetch still inside the redirect shadow
   entered IO, and the hazard arm then squashed the branch *target*.  Fixed by
   suppressing that fetch and clearing `is_load_use_hazard` with it.

Also fixed, in the harness rather than the RTL: the simulation write tap
recorded phantom stores (it mirrored DataMemory's `write_enable` port rather
than the gated write), UART capture was level-triggered and duplicated every
byte on two-phase memories, and store logging was level-triggered.  Each of
these produced convincing but false "RTL defects".

## Not investigated

`RV64IM_7SP` reads ROM byte 0x2c72 as 0x00 where the image holds 0x13, yet
passes every suite.  A wrong result in a variant reported as clean.

## Re-synthesis required

Four 8SP variants and RV64IM_7SP_BRAM have modified RTL.  Their Fmax, area and
power rows must be regenerated before use.

## Harness trap #7 — Fmax measured against the wrong clock (Sep 8)

`scripts/reimpl.tcl` computed Fmax as

```tcl
set wns [get_property SLACK [get_timing_paths -delay_type max -max_paths 1 -nworst 1]]
set per [get_property PERIOD [lindex [get_clocks] 0]]
set fmax [expr {1000.0 / ($per - $wns)}]
```

`[lindex [get_clocks] 0]` is `clk` — the **100 MHz board clock** — on every
project. The CPU does not run on it: each SoC instantiates `clk_wiz_0` and the
core is clocked by `clk_out1_clk_wiz_0`, whose constraint is per-variant and
ranges from **38 MHz (RV64IM_5SP) to 130 MHz (RV32IM_8SP)**. Dividing every
design's slack by the same 10 ns period compressed all 16 variants into a
meaningless 95–102 MHz band and inverted the 7SP_BRAM vs 7SP_BRAM_Opt ordering.

Caught by the user: *"7SP_BRAM_Opt should be faster than 7SP_BRAM."* Correct —
`RV64IM_7SP_BRAM` is constrained at 55 MHz and `RV64IM_7SP_BRAM_Opt` at 84 MHz.

Two further traps in the same expression, both live:

* the global worst path may end in **any** clock domain, so pairing it with one
  clock's period is only valid when that domain owns the worst path;
* `RV64IM_8SP` has **no MMCM** — it genuinely runs off the 100 MHz board clock,
  so it is the one variant whose old number was right, which made the bad table
  look internally consistent.

Replaced by `scripts/retime.tcl` + `retime_all.sh`, which report worst setup
slack **per capture clock** (`get_timing_paths -to $clk`) and derive Fmax only
on the clock that actually captures logic. Read-only: they re-open the routed
DCP, they do not re-implement.

**Fmax numbers reported before Sep 8 are void.** Use `logs/impl_retime.csv`.

### Constraint is not achievable Fmax

Even corrected, `1/(period − WNS)` measures the implementation Vivado produced
for *that* constraint, not the design's ceiling — the tool stops optimizing once
it meets timing. Cross-variant Fmax claims in the paper need either a constraint
sweep per variant or an explicit statement that the figure is the achieved
frequency at the shipped constraint.

### Corrected implementation results (Sep 8, `logs/impl_retime.csv`)

Fmax on the core clock only; power is Vivado **vectorless** estimation (no SAIF).

| variant | constraint | WNS | Fmax | LUT | FF | BRAM | DSP | P(W) |
|---|---|---|---|---|---|---|---|---|
| RV32I_5SP  | 45.00 | +0.137 | 45.28 | 13504 | 1666 | 0 | 0 | 0.349 |
| RV32IM_5SP | 43.00 | +0.074 | 43.14 | 12559 | 2160 | 0 | 4 | 0.306 |
| RV32IM_6SP | 50.00 | +0.028 | 50.07 | 14180 | 2464 | 0 | 4 | 0.335 |
| RV32IM_7SP | 58.00 | **−0.005** | 57.98 | 10466 | 2693 | 8 | 4 | 0.334 |
| RV32IM_7SP_BRAM | 72.00 | +0.091 | 72.47 | 3113 | 2222 | 10 | 4 | 0.302 |
| RV32IM_7SP_BRAM_Opt | 90.91 | +0.092 | 91.68 | 2707 | 1920 | 18 | 4 | 0.312 |
| RV32IM_8SP_withoutOpt | 114.00 | +0.023 | 114.30 | 3332 | 2595 | 16 | 4 | 0.345 |
| RV32IM_8SP | 125.00 | **−0.223** | 121.61 | 2882 | 2355 | 16 | 4 | 0.322 |
| RV64I_5SP  | 40.00 | +0.052 | 40.08 | 20907 | 2782 | 0 | 0 | 0.383 |
| RV64IM_5SP | 38.00 | +0.040 | 38.06 | 26460 | 3995 | 0 | 20 | 0.414 |
| RV64IM_6SP | 45.00 | +0.053 | 45.11 | 26554 | 4496 | 0 | 20 | 0.406 |
| RV64IM_7SP | 48.61 | **−0.242** | 48.05 | 21353 | 4901 | 8 | 20 | 0.374 |
| RV64IM_7SP_BRAM | 55.00 | +0.239 | 55.73 | 12475 | 4665 | 24 | 20 | 0.322 |
| RV64IM_7SP_BRAM_Opt | 84.00 | +0.003 | 84.02 | 8270 | 3919 | 18 | 20 | 0.322 |
| RV64IM_8SP_withoutOpt | 96.00 | **−0.444** | 92.07 | 12393 | 5353 | 24 | 20 | 0.386 |
| RV64IM_8SP | 100.00 | +0.160 | 101.63 | 10028 | 4834 | 24 | 20 | 0.246 |

`RV64IM_8SP` has no MMCM — it is clocked directly by the 100 MHz board pin
(`sys_clk_pin`), which is why its pre-correction number was the only right one.

**Four variants ship with negative slack** and their bitstreams therefore violate
timing at the clock the MMCM is configured for: RV32IM_7SP, RV32IM_8SP,
RV64IM_7SP, RV64IM_8SP_withoutOpt. Either re-implement each at a constraint at
or below its achieved Fmax, or disclose the negative slack in the paper.

## Trap #8 — LUT counts are not comparable across variants

The 5SP/6SP variants keep ROM/RAM in **LUTRAM**; the BRAM and 8SP variants keep
it in block RAM. So the apparent LUT collapse is largely memory relocating:

| | LUT as Logic | LUT as Memory | BRAM |
|---|---|---|---|
| RV64IM_5SP | 18180 | 8280 | 0 |
| RV64IM_8SP | 9937 | 88 | 24 |
| RV32IM_5SP | 8419 | 4140 | 0 |
| RV32IM_7SP_BRAM_Opt | 2654 | 44 | 18 |

LUTRAM accounts for the memory itself, but *LUT as Logic* also falls 68% (RV32),
which pipeline depth cannot explain — a deeper pipeline adds registers and hazard
logic. The remainder is memory decode/mux absorbed into the BRAM primitives.

Any area claim in the paper must therefore come from **core-only synthesis with
memories excluded** (`scripts/synth_cores_all.sh`), not from these SoC totals.
The SoC totals are still the right source for the BRAM/DSP accounting R1.7 asked
for, since that is exactly the memory-implementation question.

## Trap #9 — report_power omits zero categories

`report_power` prints no row at all for a category that rounds to 0.000 W —
`RV64IM_8SP_withoutOpt` has no `I/O` line, `RV32IM_8SP` no `DSPs` line. A
collector that writes only the categories it finds leaves whatever was already
in that cell, which silently mixed a Sep-2 value into a Sep-8 row of the
workbook. Every power category now defaults to 0.0 in `collect_retime.py`.

Residual: category values print at 3 dp, so their sum can differ from the
reported total by ~2 mW (`RV32IM_8SP`: 0.320 vs 0.322). That is Vivado
rounding, not a collection error.

## Deliverable — `~/Documents/Research_data_complete_0908.xlsx`

Built from `Research_data_RISCOF_with_cores_0902.xlsx` by
`scripts/build_workbook_0908.py`. **Two sheets only** — `Sheet1` (RV64) and
`Sheet2` (RV32), revised in place. No summary sheets: an earlier version added
`Impl_0908`/`Core_0908`, which the user removed as unwanted duplication. The
core block already holds all 16 variants, so a core summary sheet was pure
duplication; the SoC data does split across two benchmark blocks, but the notes
and legend carry that instead of a new sheet.

**Core block (rows 3-10)** — all 16 variants updated from `logs/core_synth.csv`.
One row per variant, no benchmark split, because memory is externalised.

**SoC blocks (rows 13-20 Dhrystone, 23-30 Coremark)** — updated **one row per
variant**, chosen by the `.mem` image the project actually holds. Rows in the
other block were not re-measured and are shaded grey with a note; their Fmax
still comes from the old board-clock calculation and must not be compared with
the updated rows.

**Legend (rows 33-44)** — carries the Fmax methodology, the LUT-comparability
warning, the benchmark-image split, and the power caveats.

Mapping validated on the three variants whose image and RTL are unchanged since
Sep 2 — RV32IM_5SP (LUT 12559 = 12559), RV32I_5SP (13504 = 13504) and
RV64I_5SP (20907 = 20907) reproduce their stored values exactly. All 32 updated
rows verified against the two CSVs; 96 formulas intact; benchmark columns
untouched.

**Reproducibility note.** The Sep 8 retime sweep ran twice end-to-end (09:36 and
09:47, all 16 projects each time, independent Vivado invocations). Rebuilding
the workbook from the second run's CSV produced a **byte-identical** result —
zero differing cells. The measurements are reproducible.

## Core-only synthesis (Sep 8) — `logs/core_synth.csv`

`scripts/core_synth.tcl` + `core_synth_all.sh`: out-of-context synthesis of the
memory-externalised `*_CORE` top, all 16 variants at the **same 5 ns (200 MHz)**
constraint, so `Fmax = 1000/(5 - WNS)` and cross-variant comparison is valid —
there is no per-variant constraint to confound it, and no Dhrystone/Coremark
split because memory is out of the design.

Before running, every core project's RTL was diffed against the verified SoC
RTL. The only differences are the externalised `*_CORE` top, `Instruction_Memory.v`
and `UART_TX.v` — plus two that looked alarming and were not: `Hazard_Unit.v` in
both `*_8SP_withoutOpt` differs by **two comment lines**, and `RV32IM_5SP`'s
`Divider_WORD.v` lacks `divisor_latch` in *both* trees because that variant's
divider never needed the fix.

| variant | WNS @5ns | Fmax | LUT | FF | DSP | P(W) |
|---|---|---|---|---|---|---|
| RV32I_5SP | −11.888 | 59.21 | 2676 | 1194 | 0 | 0.156 |
| RV32IM_5SP | −12.242 | 58.00 | 3759 | 1719 | 4 | 0.164 |
| RV32IM_6SP | −9.558 | 68.69 | 3806 | 1986 | 4 | 0.170 |
| RV32IM_7SP | −9.521 | 68.87 | 3151 | 2116 | 4 | 0.168 |
| RV32IM_7SP_BRAM | −9.525 | 68.85 | 3188 | 2116 | 4 | 0.156 |
| RV32IM_7SP_BRAM_Opt | −5.607 | 94.28 | 2633 | 1847 | 4 | 0.154 |
| RV32IM_8SP_withoutOpt | −5.126 | 98.76 | 3240 | 2549 | 4 | 0.161 |
| RV32IM_8SP | −4.507 | 105.19 | 2878 | 2278 | 4 | 0.158 |
| RV64I_5SP | −14.502 | 51.28 | 5645 | 2332 | 0 | 0.187 |
| RV64IM_5SP | −14.547 | 51.16 | 8292 | 3552 | 20 | 0.200 |
| RV64IM_6SP | −10.471 | 64.64 | 8600 | 3947 | 20 | 0.210 |
| RV64IM_7SP | −10.471 | 64.64 | 7448 | 4173 | 20 | 0.208 |
| RV64IM_7SP_BRAM | −10.471 | 64.64 | 7520 | 4173 | 20 | 0.187 |
| RV64IM_7SP_BRAM_Opt | −5.911 | 91.65 | 6509 | 3684 | 20 | 0.178 |
| RV64IM_8SP_withoutOpt | −6.112 | 89.99 | 7868 | 4974 | 20 | 0.193 |
| RV64IM_8SP | −4.934 | 100.66 | 6981 | 4489 | 20 | 0.183 |

**This resolves trap #8.** With memory excluded, core LUT stays in a narrow band
(2.6k–3.8k RV32, 5.6k–8.6k RV64) instead of the 4x collapse the SoC totals
showed. FF rises monotonically with depth, as a deeper pipeline should; LUT
*falls* for the optimized deep variants. The SoC "area reduction" was memory
relocating from LUTRAM to block RAM, not the pipeline shrinking.

Cross-check against the Sep 1 core values: **every variant lands within
0.07 MHz of its stored Fmax**, so the RTL fixes cost essentially nothing in
timing. The distribution is worth noting, because it is the opposite of the
naive expectation:

| | dFmax | dLUT |
|---|---|---|
| the four 8SP variants | **0.000** | **+41 … +182** |
| everything else | −0.046 … +0.062 | 0 … +6 |

The 8SP variants absorbed by far the largest area increase — the operand-hold
fix — yet their Fmax is unchanged to three decimals, which says the added logic
sits **off** the critical path. RV32I_5SP, RV64I_5SP and RV32IM_7SP_BRAM_Opt
show dLUT = 0, confirming their RTL is genuinely untouched.

Post-synthesis: routing is estimated, so these are comparable to each other but
**not** to the SoC post-route numbers.

## Benchmark swap (Sep 8-9) — both blocks now measured

Every SoC project was retargeted to the **opposite** benchmark at its existing
clock, per the Sep 2 precedent in `logs/swap_list.tsv` (which records each
project's own PLL frequency, i.e. keep the clock, change the image). Per project:
`$readmemh` in `Instruction_Memory.v`, plus `BAUD_DIV` in `UART_TX.v`
(= `round(freq/115200)`, verified exact on all 16) and the clock-wizard
frequency where the clock had to move.

12 swapped at their existing clock. 3 had no opposite image at that frequency and
took the fastest available at or below Fmax, with PLL + baud changed to match:
RV64IM_7SP_BRAM_Opt 84→83, RV32IM_7SP 58→50, RV32IM_7SP_BRAM_Opt 90.909→90.
**RV64IM_8SP_withoutOpt could not be swapped** — its only Dhrystone images are
100 MHz, above its 92.07 MHz Fmax. It needs a ~92 MHz Dhrystone image.

Result: **31 of 32 SoC rows now carry real measurements** (only Sheet1 r19,
RV64IM_8SP_withoutOpt Dhrystone, is unmeasured).

### The image changes timing only on LUTRAM designs

| memory | effect of swapping the image |
|---|---|
| **LUTRAM** (5SP/6SP, 7SP non-BRAM) | ROM is *logic*: netlist, placement and timing all move |
| **BRAM** (BRAM/8SP variants) | only block-RAM initialisation: netlist unchanged |

RV32IM_8SP and RV32IM_8SP_withoutOpt came back **bit-identical** — same LUT count,
same WNS to three decimals — which is the expected result for a BRAM design and a
good determinism check on the flow. By contrast RV64I_5SP grew 20907 → 24987 LUTs
switching to CoreMark and lost 0.75 ns of slack.

**Three variants that met timing before now miss it** (all LUTRAM):
RV64I_5SP (+0.052 → −0.695), RV64IM_6SP (+0.053 → −0.207), RV64IM_5SP
(+0.040 → −0.094). One improved: RV64IM_7SP (−0.242 → +0.013) now meets timing.

### Flags in the workbook

`J` column fill: **red** = timing not met (8 rows), **blue** = closes >1 MHz above
its clock, so a faster `.mem` is worth building (4 rows), green = measured and met,
grey = never measured. Column U carries the image name, clock, WNS and the reason.

Blue: RV32IM_7SP +2.29 (50→52.29), RV64IM_8SP +1.63 (100→101.63),
RV32IM_6SP +1.24 (50→51.24), RV64IM_7SP_BRAM +1.24 (55→56.24).

### Infrastructure defects found

* **`launch_runs` blocks forever on a wedged IP run.** Killing a session mid
  clock-wizard OOC synthesis leaves that run marked in-progress at 0%; the next
  `launch_runs` waits on it with **zero CPU** — RV64IM_7SP_BRAM_Opt burned 6.5 h
  twice. `swap_impl.tcl` only reset the IP run when the PLL frequency *changed*,
  so the retry skipped it. Now reset unconditionally when not 100%.
* **`swap_all.sh` never cleared `.lock` files**, silently skipping projects as
  READONLY. Added.
* **Machine throttling.** Runs from Sep 8 14:58 to Sep 9 10:16 executed on
  battery in `low-power`, cores at 1.1-1.8 GHz of 5.1 GHz. Wall-clock times from
  that window are ~3x inflated; the *results* are unaffected, timing analysis
  being independent of tool speed.

## Clean workbook — `~/Documents/Research_data_complete_0909.xlsx`

Built by `scripts/build_workbook_0909.py` from the measurement CSVs
(`core_synth.csv`, `soc_preswap.csv`, `soc_postswap.csv`, `fpga_benchmarks.csv`,
`swap_plan.json`) — a fresh build, not a patch of the inherited 0902 layout,
because the accumulated colour coding had become unreadable.

Two sheets, **RV32** and **RV64**, each with three blocks: core-only synthesis,
SoC Dhrystone, SoC CoreMark. `Research_data_complete_0908.xlsx` is left untouched
for comparison.

**One status column carries the timing verdict in text and colour**, so the sheet
scans without reading notes:

| fill | status | meaning |
|---|---|---|
| none | `OK` | timing met, <1 MHz headroom — nothing to do |
| blue | `+n MHz headroom` | closes >1 MHz above its clock — build a faster `.mem` |
| red | `VIOLATION ±n ns` | negative setup slack at the configured clock |
| yellow | `not measured` | no result for that variant/benchmark pair |

Counts: **8 red, 4 blue, 1 yellow**, 47 values verified against the CSVs.

Two deliberate choices worth keeping:

* **The core block is uncoloured.** Every variant has negative slack at the shared
  5 ns constraint by construction — none targets 200 MHz — so a red there would
  be meaningless. That block exists only to compare variants at an identical
  constraint.
* **`clock`, `WNS`, `Fmax` and `headroom` are real columns**, not prose in a note.
  Headroom was previously only discoverable by reading column U.

Number formats are set per column. An earlier version chose the format from the
value's magnitude, which made one column show both `-14.50` and `0.052`.

## Frequency sweep to convergence (Sep 9 evening)

Every row that violated timing or left >1 MHz unused was re-imaged at a frequency
it can actually hold, iterating until convergence (`scripts/sweep_freq.py`): build
the image at the target, set PLL + `BAUD_DIV`, re-implement, read the achieved
clock back, and retarget at `floor(Fmax)`. Bounded at 6 iterations and stopped on
a repeated target, so a non-convergent row reports its best result instead of
spinning. Runs are strictly sequential — parallel Vivado is slower on this machine.

**All 32 SoC rows now meet timing.** No violations, no unmeasured rows.

Two results worth carrying into the paper:

* **`RV32IM_8SP`: reported Fmax overstates what can be closed.** Constrained to
  119 MHz it meets timing (+0.149 ns) and reports it could reach 121.2.
  Constrained to 121 it produces a *worse* implementation closing at 119.0. The
  margin is not reachable; 119 MHz is the real limit. Identical on both
  benchmarks, as expected for a BRAM design whose netlist the image does not
  touch. So `1/(period − WNS)` bounds *that implementation*, not the design.
* **`RV64IM_8SP` headroom is not exploitable.** No MMCM — `create_clock -period
  10.00 [get_ports clk]` wires the core to the 100 MHz board pin, so its
  +1.63 MHz needs a PLL, not a different image. (User is adding one.)

Also confirmed: `RV64IM_8SP_withoutOpt` meets timing at 96 MHz with the Dhrystone
image (+0.074) but violated at the same 96 MHz with CoreMark (−0.444). Same RTL,
same constraint — only the ROM differs, and on LUTRAM designs the ROM is logic.

### Two defects in my own tooling, both caught by cross-checks

* **Stale IP netlist.** `reimage_impl.tcl` reset any clock-wizard run that was
  not at 100%, which caught `clk_wiz_0_impl_1` but not `clk_wiz_0_synth_1`
  (already complete). Vivado then reused the previously synthesized IP and the
  design kept the OLD clock while the `.xci` read the new one — **10 of 13 runs
  in the first batch ran at the wrong frequency.** Fixed by always resetting the
  IP synth run after a retune, plus a `CLOCK_MISMATCH` guard that compares the
  achieved clock with the requested one.
* **Live file read as a frozen snapshot.** `build_workbook_0908.py` loaded
  `post_data` from `logs/impl_retime.csv`, which every later sweep regenerates,
  so new measurements were silently back-dated into the swap rows. Now reads
  `logs/soc_postswap.csv`.

Image builds are parameterised by `CPU_FREQ_HZ` (Dhrystone `-DHZ`, CoreMark
`-DEE_TICKS_PER_SEC`); the two RV64 ports hardcoded theirs and were changed to
match the RV32 ports. Validated by rebuilding an existing image byte-for-byte.
