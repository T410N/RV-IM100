# Comparison cores

Synthesized under the same methodology as the RV-IM100 cores so the numbers are
comparable: part `xc7a200tsbg484-1`, a 5 ns (200 MHz) constraint read *before*
synthesis so the run is timing-driven, `-mode out_of_context` so no I/O buffers
are counted, and the core alone with its memory interface left at the top-level
boundary.  `Fmax = 1000 / (5 - WNS)`.

The constraint is deliberately unreachable: every design then reports a negative
WNS from a fully-optimised result, rather than one the tool stopped working on
after meeting an easy target.

| core | source | version | configuration |
|---|---|---|---|
| PicoRV32 | https://github.com/YosysHQ/picorv32 | `ef203c2` | `ENABLE_MUL=1`, `ENABLE_DIV=1`; all else default. `ENABLE_FAST_MUL` left off -- it is a separate opt-in, not part of "default with mul/div". |
| RVCoreP | https://www.arch.cs.titech.ac.jp/wk/rvcore/ | ver 0.5.3 (MIT, Kise Lab, Tokyo Tech) | `config.vh` as shipped. `D_SIMPLE_ALU` and `D_SIMPLE_DMOUT` are commented out upstream, so the default selects the *optimised* ALU and data-memory alignment unit, which is RVCoreP's contribution. |
| VexRiscv | https://github.com/SpinalHDL/VexRiscv | `c4b2a55` | `GenFullNoMmuNoCache`, elaborated with SpinalHDL 1.13.0 / Scala 2.12.18. |

## Notes that affect interpretation

- **RVCoreP is RV32I**, not RV32IM.  Its area and frequency buy less function
  than the RV32IM entries; the fair pairing is against `RV32I_5SP`.
- **VexRiscv `GenFullNoMmuNoCache` includes `DebugPlugin`**, a JTAG debug module
  none of the other cores have, so it was also generated without it
  (`GenFullNoMmuNoCacheNoDebug`, kept under `generated/`).  The debug module
  costs **80 LUT (5.6%) and 46 FF, and is not on the critical path**: Fmax moves
  only 136.593 -> 136.537 MHz.  Use the no-debug figure for comparison and cite
  the with-debug one in a footnote.

  Removing it was verified not to disturb anything else, since `DebugPlugin` and
  `CsrPlugin` interact.  The port diff is exactly the 8 debug ports; MulPlugin
  and DivPlugin logic is identical (45 and 90 occurrences either way); no
  CsrPlugin signal name disappears; and every architectural CSR is unchanged,
  including `mcycle` and `minstret`, which matters because RV-IM100 implements
  Zicsr and the comparison must stay like-for-like.  The only CSR difference is
  `CsrPlugin_trapCauseEbreakDebug` and `CsrPlugin_trapEnterDebug`, both already
  hardwired to 1'b0 in the with-debug build -- dead logic whose tie-offs simply
  went away.
- **RVCoreP and VexRiscv each infer 1 BRAM** for branch prediction structures;
  the RV-IM100 cores use none at core level.
- **PicoRV32 uses 0 DSPs** because its multiplier is multi-cycle inside the ALU;
  VexRiscv and the RV-IM100 IM cores each use 4.
- **Frequency alone favours all three over the RV-IM100 cores and is misleading
  on its own.**  PicoRV32 is multi-cycle with a CPI around 4, so its 182 MHz is
  not 182 MHz of work.  Any table must carry CPI or throughput beside Fmax.

## Reproducing

    git clone --depth 1 https://github.com/YosysHQ/picorv32.git comparison_cores/picorv32
    curl -o comparison_cores/rvcorep_orig.zip \
      "https://www.arch.cs.titech.ac.jp/wk/rvcore/lib/exe/fetch.php?media=rvcorep_ver053.zip"
    git clone --depth 1 https://github.com/SpinalHDL/VexRiscv.git comparison_cores/VexRiscv
    bash comparison_cores/gen_vexriscv.sh       # needs a JDK; Vivado's bundled one works
    bash riscof-env/scripts/synth_extcores.sh

No JDK was installed system-wide: the JDK bundled with Vivado
(`tps/lnx64/jre11.0.16_1`, which does include `javac`) and a locally-extracted
sbt under `~/tools/sbt` were used.

## Published throughput (investigated 2026-09-22)

None of the three publishes a figure measured under the RV-IM100 conditions
(gcc 15.2, Dhrystone `-O2`, CoreMark `-O2 -fno-common -funroll-loops`), and two
of the three do not publish one for the configuration synthesized here.

| core | published figure | source | matches our config? |
|---|---|---|---|
| PicoRV32 | 0.516 DMIPS/MHz, Dhrystone CPI 4.100; 0.305 DMIPS/MHz / CPI 5.232 without the look-ahead interface. No CoreMark figure. | `picorv32/README.md` @ `ef203c2`, "Cycles per Instruction Performance" | **No.** The figure is for `ENABLE_FAST_MUL` + `ENABLE_DIV` + `BARREL_SHIFTER`. Ours has the 40-cycle `ENABLE_MUL` and no barrel shifter (shifts 4-14 cycles), so 0.516 is an upper bound for it. |
| VexRiscv | 1.21 DMIPS/MHz, 2.30 CoreMark/MHz ("VexRiscv full no cache") | `VexRiscv/README.md` @ `c4b2a55` | **Yes** -- same `GenFullNoMmuNoCache` demo config; README area 1418 LUT / 949 FF vs ours 1441 / 940. Dhrystone built `-O3 -fno-inline`, not `-O2`. Its 216 MHz is on the fastest speed grade (-3) and must not be set beside our -1 Fmax. |
| RVCoreP | **No DMIPS/MHz or CoreMark/MHz is published.** The paper reports IPC only: Dhrystone 0.935, CoreMark 0.823, average 0.879 (RVP-optALL), and "performance" = average IPC x MHz = 167.0 at 190 MHz. | Miyazaki et al., arXiv:2002.03568, Tables 1-2; IEICE Trans. Inf. & Syst., doi:10.1587/transinf.2020PAP0015 | **Nearly.** RVP-optALL = optimised ALU + IF + data-memory output, which is the 0.5.3 default. RV32I, gcc 8.3.0 `-O2`, riscv-tests Dhrystone, CoreMark ITERATIONS=2. Their 190 MHz is xc7a100t-1 (same speed grade) but found by a 5 MHz constraint sweep on the full system in Vivado 2017.2, not core-only. |

The `rvcorep_orig/rvcorep_ver053/result.txt` shipped with the source reports
Dhrystone IPC 0.929 and CoreMark IPC 0.825, but its log paths name `v091_release`,
so it was produced by a later release than the 0.5.3 source synthesized here.

Converting RVCoreP's IPC into DMIPS/MHz would need its per-iteration instruction
count, which the paper does not give; any such figure would be derived here, not
cited, and must be labelled that way.

## Measured throughput (2026-09-23)

Superseded the citation route above: all three cores were run on RV-IM100's own
Dhrystone and CoreMark images in cycle-accurate simulation. See `throughput/README.md`
for the method and checks, and `throughput/out/throughput.csv` for the results. The
master workbook's `Core throughput` sheet holds them beside the RV-IM100 RV32 cores.
Published figures remain useful only as sanity checks: PicoRV32 reproduces its published
CPI 4.10 in the harness, and RVCoreP its published IPC to within 2%.
