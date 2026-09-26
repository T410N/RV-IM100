# Reproducibility evidence

Everything needed to rebuild any of the 32 measured configurations from source.

## Why this exists

The 32 bitstreams in `../bitstream/` were each built from a specific project
state: one benchmark image, one PLL frequency, one UART divisor. A Vivado project
holds only **one** of those at a time, so no single checkout of the repository
represents all 32. Git HEAD does not represent them either — it predates the
frequency sweep (it still references `dhrystone_RV32IM_50MHz.mem` where the
shipped bitstream used 53 MHz).

Rather than keep 32 project copies, this directory records the **configuration**
of each one. The projects, images and constraints are all in git; what was not
recorded was which combination produced which result. That is what
`CONFIGURATIONS.csv` fixes.

## Contents

* `CONFIGURATIONS.csv` — one row per bitstream: project, `.mem` image, clock,
  MMCM M/D/O and the exact frequency it synthesises, UART `BAUD_DIV`, measured
  WNS and Fmax, utilisation where verified, and both vectorless and SAIF power.
* `restore_config.sh` — puts a project back into any recorded configuration.

## Use

```bash
./restore_config.sh RV64IM_8SP coremark              # set sources, report, stop
./restore_config.sh RV64IM_8SP coremark --implement  # also set the PLL and re-implement
```

Re-implementation is deterministic for identical inputs, so a restored project
reproduces its recorded numbers. It is not *guaranteed* bit-identical across tool
sessions: `RV64IM_7SP_BRAM_Opt/coremark` was re-implemented during the SAIF work
and came back **worse** (WNS −0.193, failing timing, against the shipped
bitstream's +0.028 at 83.105 MHz). The shipped bitstream is the good one.

## Caveats recorded honestly

* **Utilisation is verified for 14 of 32 rows** — those whose live project still
  matches its bitstream. The rest are marked `not verified` in
  `util_source`: their Fmax and WNS come from the bitstream implementation and
  are sound, but their LUT/FF figures may come from an earlier implementation.
* **Clock figures read 0.001 MHz low** in places (101.999 where the MMCM
  synthesises exactly 102.000). The XDC stores the period to three decimals;
  `mmcm_exact_mhz` gives the true value.
* **SoC utilisation is benchmark-dependent.** Changing only the ROM image moved
  `RV64IM_8SP` from 9,065 to 12,666 LUTs, despite the ROM living in BRAM. Area
  claims should use the core-only block, which is image-independent and
  constrains every variant identically.
