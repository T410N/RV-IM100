# Comparison-core throughput harness

Measures Dhrystone and CoreMark on PicoRV32, VexRiscv and RVCoreP with **RV-IM100's
own benchmark images**, so every core runs the same program built the same way.

    ./build_sw.sh      # images: gcc 15.2.0, RV-IM100 ports and flags, rv32im + rv32i
    ./build_sim.sh     # one Verilator simulator per core configuration
    ./run_all.sh       # 4 configurations x 2 benchmarks
    python3 analyze.py # checks every run, writes out/throughput.csv

## Method

- **Programs.** `sw/` is a copy of `benchmarks/{dhrystone,coremark}_rv32i_port`
  at `bb433c10`. The benchmark sources are unchanged. Two BSP edits only:
  - the timer reads a testbench cycle counter at `0x1002_0000` instead of `csrr mcycle`,
    because RVCoreP has no CSRs;
  - `crt0.S` stores to `0x1001_2000` after `main` returns, ending the simulation.

  Dhrystone runs 300,000 times at `-O2`. CoreMark runs 300 iterations at
  `-O2 -fno-common -funroll-loops`. PicoRV32 and VexRiscv get the rv32im build, RVCoreP
  the rv32i build.
- **Cores**, at the boundary synthesized for the Core comparison sheet:
  - PicoRV32 `ef203c2`, `ENABLE_MUL=1 ENABLE_DIV=1`;
  - VexRiscv `c4b2a55` `GenFullNoMmuNoCache` without `DebugPlugin`;
  - RVCoreP 0.5.3 `RVCore`, with `config.vh` as shipped.
- **Memory** (`tb/tbmem.v`) uses the RV-IM100 SoC map, zero-wait, and each core's own
  reference timing:
  - PicoRV32 runs twice, with look-ahead (`dhrystone/testbench.v`) and with
    registered ready (`dhrystone/testbench_nola.v`).
  - VexRiscv accepts every command and responds on the next cycle. It resets to
    `0x8000_0000`, where a one-word boot ROM (`jalr x0,0(x0)`) jumps to the image.
  - RVCoreP gets a one-cycle synchronous read on both ports, as in its
    `D_SYNC_IMEM`/`D_SYNC_DMEM`.
- **Metric.** Cycles are counted between the program's two timer reads, the same window
  the software times.
  - DMIPS/MHz = runs × 10⁶ / (cycles × 1757)
  - CoreMark/MHz = iterations × 10⁶ / cycles
- **Validity.** A run counts only if all of these hold:
  - it ends on the halt store;
  - it reads the timer exactly twice;
  - it passes all 22 Dhrystone "should be" checks, or CoreMark's CRC validation (all
    four cores give `crcfinal 0x5275` at 300 iterations).

## Results (`out/throughput.csv`, all 8 VALID)

| core | ISA | memory | DMIPS/MHz | CoreMark/MHz | CPI Dhry / CM |
|---|---|---|---:|---:|---:|
| PicoRV32 | RV32IM | registered ready | 0.244 | 0.555 | 5.72 / 6.43 |
| PicoRV32 | RV32IM | look-ahead | 0.327 | 0.684 | 4.27 / 5.23 |
| VexRiscv | RV32IM | next-cycle | 1.011 | 2.496 | 1.38 / 1.43 |
| RVCoreP | RV32I | sync read | 1.229 | 1.133 | 1.06 / 1.24 |

## Checks on the harness

- **Instruction counts agree across independent sources.** PicoRV32's own retired
  counter gives 407.0 instructions per Dhrystone run and 279,946.9 per CoreMark
  iteration. The RV-IM100 RTL monitor gives 407.0 and 279,945.1 on the FPGA images, and
  revision_0922/T3 gives 279,972.9.
- **PicoRV32** in its published configuration (`BARREL_SHIFTER ENABLE_FAST_MUL
  ENABLE_DIV`, look-ahead) runs at CPI 4.10, the README's "average CPI is 4.100".
- **RVCoreP** IPC is 0.944 on Dhrystone and 0.807 on CoreMark. Its paper reports 0.935
  and 0.823, with a different compiler and benchmark build.
- Every core's own printed score agrees with the harness cycle count.

## Why absolute DMIPS/MHz differs from published figures

Measured by rebuilding Dhrystone with one factor changed at a time. Retired instructions
per run come from PicoRV32's counter, as the difference between 1,000- and 2,000-run
builds (all builds pass the 22 self-checks):

| build | instr/run | VexRiscv DMIPS/MHz | PicoRV32 (published config) DMIPS/MHz |
|---|---:|---:|---:|
| -O2, byte strcpy (this port, as used) | 406 | 1.013 | 0.340 |
| -O3, byte strcpy | 405 | 1.018 | 0.341 |
| -O2, word strcpy (PicoRV32's library) | 339 | 1.191 | 0.426 |
| -O3 -fno-inline, word strcpy | 392 | 1.025 | 0.366 |
| -O2, compiler builtins + newlib | 267 | 1.467 | **0.515** (published 0.516) |
| -O3 -fno-inline, builtins + newlib | 318 | **1.235** (published 1.21) | -- |

Optimisation level barely matters. The difference is the string copy Dhrystone makes
on every run:
- The port is built `-ffreestanding` with a byte-by-byte `strcpy`, giving 406
  instructions per run.
- Let gcc expand the copy itself (builtins on, newlib `memcpy`) and it falls to 267.
- In that form, both cores reproduce their published figures.

So the published figures and ours measure the same pipelines on different programs.
DMIPS/MHz from this port, including RV-IM100's own, compares only within this port.

## Not met

CoreMark's reporting rules ask for a board run of at least 10 s. Here the cycle counter
is exact, and the nominal 10 MHz clock only keeps the program's own report above 10
notional seconds. These are simulation figures, and should be labelled that way.
