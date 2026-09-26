# T12 — AAPG with an address-matched reference

## (a) Result summary

**An address-matched ISS reference is not available on this machine. The comparison was
instead made DUT-vs-DUT on the identical ROM image, which has no link-address artefact at
all. Every completing run is byte-identical to its reference core: 113 of 113, zero
differing words.**

### Why the address-matched ISS was not achievable (checked, not assumed)
| route | outcome |
|---|---|
| Sail `--ram-base` | does not exist. Sail 0.6 offers only `--ram-size` (`-z`) |
| Patch the shipped Sail binary | `rv_ram_base` has been constant-folded: no symbol in `.data`, and no matching data word to patch |
| Rebuild Sail from `~/Downloads/sail-riscv-riscof-0.6` with the base changed | the source patch is one line (`riscv_platform_impl.c:30`), but CMake aborts with "Sail not found": the build regenerates the model from the Sail sources, and the Sail compiler is not installed |
| Run stock Sail on the DUT-linked ELF | it loads the ELF at 0x0 and finds `tohost` at 0x1001_0000, but then hangs: the program lies outside Sail's RAM window (0x8000_0000). 20,000-instruction limit never reached, killed at 90 s |
| Spike `-m<base>:<size>` | Spike is not installed |

### The comparison that was made
For every program, each variant's signature is compared word-by-word with the **5-stage
variant of the same ISA pool** on the **same ROM image**. Both sides are the same binary at
the same addresses, so no word is address-dependent and nothing has to be excluded. The
5-stage reference is independently validated: RISCOF 851/851 against Sail, riscv-tests
(only `ma_data`), and it carries none of the control-flow defects T6 found in the 7/8-stage
front end.

Timed-out runs are never compared: the testbench dumps a signature however the run ended
(STATUS.md trap #4).

| variant | identical to 5SP | differing | timeout (not compared) | old table vs Sail (MATCH/MISMATCH/TIMEOUT) |
|---|---|---|---|---|
| RV32IM_5SP, RV32I_5SP, RV64IM_5SP, RV64I_5SP | reference | – | 0 | 7/13/0, 7/13/0, 19/1/0, 14/6/0 |
| RV32IM_6SP | **20 / 20** | 0 | 0 | 7/13/0 |
| RV32IM_7SP | 5 | 0 | 15 | 3/2/15 |
| RV32IM_7SP_BRAM | 4 | 0 | 16 | 2/2/16 |
| RV32IM_7SP_BRAM_Opt | 4 | 0 | 16 | 2/2/16 |
| RV32IM_8SP_withoutOpt | 4 | 0 | 16 | 2/2/16 |
| RV32IM_8SP | 4 | 0 | 16 | 2/2/16 |
| RV64IM_6SP | **20 / 20** | 0 | 0 | 19/1/0 |
| RV64IM_7SP, _BRAM, _BRAM_Opt | 10 each | 0 | 10 each | 10/0/10 |
| RV64IM_8SP, 8SP_withoutOpt | 11 each | 0 | 9 each | 11/0/9 |

**24 runs that the old table calls MISMATCH are byte-identical to the 5-stage core.** They
are the artefact. A further 33 MISMATCH rows are on the reference cores themselves, where
no cross-check is possible (the I-only pools have a single variant each), so for those the
Sail comparison with address-dependent words excluded remains the only evidence; they are
backed by RISCOF 851/851 on the same cores.

**Nothing in the randomized campaign shows a wrong architectural result on a completing
run.** The only failures are the 127 timeouts, and T6 root-causes those to one defect
(`IF_IO_Register` skipping the predicted-taken squash when an M-extension instruction is in
decode) which no reported workload triggers.

### Reference-free corroboration (no ISS, no reference core)
From T6, on the same 320 runs: the committed-stream continuity check (P1), the
branch-outcome check (P3) and the value-level lock-step against the 5-stage core (P2) agree
with the table above. They fire on all 127 timeouts and on none of the 5SP/6SP runs.

## Proposed replacement for the Verification sheet's "randomized (AAPG)" column
Report completion and agreement instead of "7/20":

> AAPG randomized programs, 20 per ISA pool, signatures compared with the 5-stage core on
> the identical ROM image (no link-address artefact): **every completing run agrees
> exactly** — 20/20 on 5SP and 6SP (both widths), and all completing runs on the 7/8-stage
> variants (RV32: 4–5 of 20; RV64: 10–11 of 20). The remaining runs do not terminate, from
> the single front-end defect characterised in T6, which no reported workload triggers. The
> earlier "7/20 pass" reflected Sail's fixed 0x8000_0000 RAM base against the DUT's 0x0, not
> a functional difference.

## (b) Fragment
`t12_aapg_dutvsdut.csv`: 320 rows (variant, program, pool, reference, old status vs Sail,
words differing vs 5SP, verdict). Script: `riscof-env/scripts/t12_aapg_dutvsdut.py`.

## (c) Contradicts the master file
1. `Verification` AAPG column ("7/20", "3/20", "13 mismatch", …) understates agreement: no
   completing run differs from the reference core. Replace with the wording above.
2. The "two randomized failure modes" note should become one: non-termination from the T6
   defect. The "mismatch" mode is an artefact of the reference's memory map.
