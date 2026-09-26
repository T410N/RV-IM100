# T5 — Embench "no result" rows

## (a) Result summary

**Every Embench non-completion is stack exhaustion in the software port. None is an RTL
defect or the simulation cycle cap.**

The port's linker script (`riscof-env/embench-env/link.ld`) gives **DATA = 32 KB** (not
64 KB) and a **4 KB stack** (`_stack_end = _bss_end + 0x1000`) that grows down into `.bss`.
Lowest `sp` reached, tracked from the retire trace on the 5SP variants of all four ISAs
(`stack_audit_19x4.tsv`, 19 benchmarks × 4 ISAs):

| benchmark | ISA | stack depth | outcome |
|---|---|---|---|
| huffbench | rv64i/rv64im | 13,008 B | **sp leaves RAM** (0x0FFF_FF90). Return addresses are lost, the PC jumps to 0x0 and the program restarts forever |
| slre | rv64i/rv64im | 4,320 / 4,560 B | **sp leaves RAM** (0x0FFF_FEC0 at cycle 748), same failure |
| wikisort | all four | 4,672 (rv32) / 5,024 B (rv64) | stack enters `.bss` by 568 / 920 B and corrupts its heap: non-termination on all 16 |
| **huffbench** | **rv32i/rv32im** | **7,840 B** | **stack enters `.bss` by 3,744 B (the heap), yet verify passes**: the master's RV32 huffbench rows were measured on a corrupted execution |
| the other 15 | all | < 4 KB | inside the allocation |

**The five FPGA benchmarks (crc32, matmult-int, md5sum, nettle-aes, statemate) stay inside
their stack on all four ISAs**, so the RV64 FPGA rows and the pending RV32 FPGA rows are
unaffected.

**Causal confirmation.** Rebuilding only these three with a 12 KB stack (`. = . + 0x3000`,
everything else identical, still inside 32 KB DATA) makes **all 48 runs (3 × 16 variants)
complete with verify = OK** (`T5_fragment_embench_12KBstack.csv`). RV32 huffbench's
instret drops from 2,618,879 to 2,392,544 (−8.6%) once the stack no longer overwrites the
heap. slre (RV32) is unchanged to within 2 instructions, since its RV32 stack fits.

**ISS step.** Spike is not installed. The Sail 0.6 emulator's RAM base is fixed at
0x8000_0000, so it cannot run these ELFs at the SoC map (0x0 ROM / 0x1000_0000 RAM).
The RTL-side evidence (sp trajectory plus the causal relink) is decisive. An ISS run with
the same map would also go below RAM, because the overflow is a property of the program
and the memory map, not of the core.

**xgboost.**
- The I and IM images are **byte-identical** within each width (hex md5 `e48040b1` RV32,
  `1c298d21` RV64). Static counts: 0 `mul*`, 0 `div*`/`rem*`, 0 calls to `__mul*`/`__div*`,
  and 0 soft-float libcalls. The benchmark is integer tree traversal, so identical I/IM
  counts are correct.
- `verify_benchmark` returns `r >= SAMPLES_IN_FILE * (LOCAL_SCALE_FACTOR, GLOBAL_SCALE_FACTOR / 12)`.
  The comma operator makes that `GLOBAL_SCALE_FACTOR/12 = 0` at scale 1, so **verify is
  vacuous** (an upstream Embench bug).
- The text size is 40.7 KB, larger than the 32 KB IMEM. It runs only because the simulator's
  IMEM is widened to 2 MB. Its simulation row describes a memory configuration the silicon
  does not have.

## Corrected wording for the Verification sheet
> huffbench, slre, wikisort: the Embench port allotted a 4 KB stack. huffbench and slre on
> RV64 (64-bit frames) overflow below the RAM base and never terminate. wikisort overflows
> into its heap on every ISA. huffbench on RV32 overflows into its heap but still passes
> verify. The three were rebuilt with a 12 KB stack (all other benchmarks unchanged) and
> then complete with verify = OK on all 16 variants. None of the five FPGA benchmarks is
> affected.
> xgboost: excluded from hardware (code 41–45 KB exceeds the 32 KB instruction memory). In
> simulation its verify function is vacuous at GLOBAL_SCALE_FACTOR=1, and it contains no
> multiply/divide, so I and IM results are identical by construction.

## (b) Fragments
- `T5_fragment_embench_12KBstack.csv`: 48 rows (variant, benchmark, cycles, instret, CPI,
  verify, the old status and counts, ELF sha256) for the `Embench simulation` sheet.
- `stack_audit_19x4.tsv`: bss_end, stack_end, lowest sp, depth, overflow bytes and verdict per benchmark × ISA.

## (c) Contradicts the master file
1. Verification note "simulation-speed limit, not a functional failure" (huffbench/slre
   RV64, wikisort) is **wrong**: they are stack overflows.
2. `Embench simulation` RV32 huffbench rows (8 variants, "ok") came from an execution that
   overwrote its own heap. Replace them with the 12 KB-stack rows.
3. "wikisort fails everywhere" now resolves to 16/16 OK with the larger stack.
4. xgboost "ok" rows should be annotated (vacuous verify; not runnable on the 32 KB IMEM).
