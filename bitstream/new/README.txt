Bitstreams needing an FPGA run.

These 9 configurations changed since the bitstreams in Done_legacy/ were built,
either because the clock moved or because the benchmark image was recompiled.
The other 23 configurations are unchanged in both clock and image, so their
Done_legacy/ bitstreams still measure exactly what the workbook reports.

  RV32IM_6SP_dhrystone_51.515152MHz       image rebuilt: was compiled for
                                          51,500,000 Hz, silicon runs at
                                          51,515,152 (294 ppm)
  RV32IM_7SP_BRAM_Opt_coremark_92MHz      clock 90 -> 92 MHz, and data memory
                                          corrected from 16384 to 8192 words
  RV32IM_7SP_BRAM_Opt_dhrystone_90.909091MHz
                                          data memory corrected (BRAM 18 -> 10)
  RV32IM_8SP_coremark_122MHz              clock 119.047619 -> 122 MHz
  RV32IM_8SP_dhrystone_122MHz             clock 119.047619 -> 122 MHz
  RV64IM_7SP_dhrystone_48.611111MHz       image rebuilt (1 Hz correction)
  RV64IM_7SP_BRAM_coremark_58MHz          clock 55.555556 -> 58 MHz
  RV64IM_7SP_BRAM_Opt_coremark_80.952381MHz   image rebuilt
  RV64IM_7SP_BRAM_Opt_dhrystone_80.952381MHz  image rebuilt: was compiled for
                                          81,000,000 Hz against 80,952,381 (588 ppm)

Expect four of these to read differently from before, not merely re-confirm:
the three clock changes raise throughput proportionally, and the two dhrystone
images with genuine ppm errors (RV32IM_6SP, RV64IM_7SP_BRAM_Opt) should shift
Dhrystones/Sec slightly.  The two 1 Hz corrections should be indistinguishable.

The filename frequency is the exact MMCM output, 100*M/(D*O), and matches the
workbook's clock for that row.
