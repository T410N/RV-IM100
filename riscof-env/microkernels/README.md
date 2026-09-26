# Targeted microkernels

Hand-written assembly kernels that isolate one microarchitectural behaviour
each, so a cost can be attributed to that behaviour rather than inferred from
whole-program timing.  Dhrystone and CoreMark mix every effect at once; these
separate them.

## Method

Each kernel is generated as assembly, checked against an independent
interpreter, built, and simulated on all 16 SoC variants.

**Retirement-bounded region of interest.**  `monitor.v.in` watches for three
architectural marker instructions — `ADDI x0, x0, 0x701 / 0x702 / 0x703`, which
are hint-encoded NOPs distinct from the bubble NOPs the RTL injects — and counts
cycles, retired instructions, branches, taken branches, mispredicts, jumps,
loads, stores, mul and div only between START and STOP.  Startup and
verification are therefore outside every number reported.

**Matched pairs.**  Kernels come in `_dep` / `_control` pairs that retire the
same instruction count and execute the same branches; only the register
dependence differs.  The cycle difference between a pair is the penalty, with
loop overhead and instruction mix cancelling out.  `gap0`..`gap4` insert 0 to 4
independent instructions between producer and consumer, so the penalty is
measured as a function of dependence *distance*, not merely its presence.

**Independent oracle.**  `reference.py` is a small RV I/M interpreter used as a
functional check, not a timing model or a Sail replacement.  It maintains a
rolling hash over retired `(pc, insn, rd, value)`; the RTL monitor computes the
same hash, and a run passes only if they agree.  Unsupported instructions and
uninitialised loads fail closed.

## Kernel families

| family | kernels | isolates |
|---|---|---|
| `alu_raw` | `add/addw/xor_gap0..4_{dep,control}` | back-to-back ALU dependence vs distance |
| `load_use` | `load_gap0..4_{dep,control}` | load-use interlock vs distance |
| `store_forward` | `copy_gap0..4`, `store_load_{same,different}` | store-to-load forwarding |
| `branch` | `branch_{taken,nt,alternate,ttnt}_gap{0,8}` | direction, pattern and spacing |
| `jump` | `jump_{jal,jalr,sequential}` | front-end refill on direct vs indirect transfer |
| `muldiv` | `{mul,mulw,div,divu,divw,divuw,rem,remw}_every{1,4,16}` | unit occupancy vs density |
| `corner` | `corner_{div,divu,divw,divuw,rem,remu,remuw,remw,mulh,mulhsu,mulhu}` | M-extension corner cases |
| `memory` | `memory_{load,store,mixed}_{0,25,50,75,100}` | memory access intensity |
| `mixed` | `mixed_embedded`, `alu_{independent,dependency_chain}` | combined reference points |

112 kernels on RV64IM.  RV32 variants omit the 26 RV64 W-instruction kernels;
I-only variants additionally omit the 21 M-extension kernels.  Every exclusion
is an ISA property, not a gap: on an I-only core the M kernels would measure
libgcc's software routines rather than a hardware unit.

## Running

    ./run.py                  # generate, check, build and simulate all variants
    ./analyze.py              # derive matched-pair penalties and figures
    ./analyze.py --no-plots   # skip Matplotlib

## Outputs

* `out/results.csv` — one row per (variant, kernel): counters, hashes, status
* `out/REPORT.md` — pass counts and CPI per variant
* `out/ANALYSIS.md` — matched-pair penalties, the publication tables
* `out/dependency_penalties.csv` — the penalty matrix
* `out/provenance/` — source, binary and simulator hashes, tool versions
* `out/images/`, `out/build/`, `out/runs/` — generated artefacts, regenerable,
  and excluded from git by `.gitignore`

## Reading the results

`ANALYSIS.md` distinguishes matched-pair penalties, which isolate a cost, from
descriptive ratios, which do not.  The branch and jump ratios include loop
overhead and recovery and are labelled as such.  Occupancy buckets are not
additive CPI penalties.  The document states these limits inline; keep them
attached to any figure taken from it.
