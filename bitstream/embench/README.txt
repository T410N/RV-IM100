Embench-IoT FPGA bitstreams: 5 benchmarks x 16 variants.

Layout
  RV32/<variant>/<variant>_embench_<benchmark>.bit
  RV64/<variant>/<variant>_embench_<benchmark>.bit
  MANIFEST.csv carries a `path` column with the location of every bitstream,
  alongside the clock it was built at and its WNS.

Subset rationale
  All 18 Embench benchmarks that fit the 32 KB instruction memory were verified
  in simulation across all 16 variants (xgboost alone exceeds it at 41-45 KB).
  These five were selected for FPGA measurement because each substantiates a
  specific contested claim rather than for apparent variety:

    matmult-int   load-use hazard + integer multiply -> execution-use hazard
    crc32         tight loop, back-to-back ALU dependency -> forwarding paths
    nettle-aes    table-lookup heavy -> memory access intensity, BRAM latency
    statemate     branch-dense state machine -> branch penalty, front-end refill
    md5sum        mixed sequential integer work -> general-purpose baseline

  All five are integer-only, avoiding the soft-float interpretation problem that
  affects wikisort, and all are small enough to avoid memory pressure.

Output
  Each run prints one line over UART at the design's own baud rate:
    EMBENCH <name> cycles=<n> instret=<n> verify=<OK|FAIL>
  The line is self-identifying, so a capture cannot be misattributed to the
  wrong benchmark.

Clocks
  Each build runs at its variant's measured operating frequency, with two
  exceptions recorded in MANIFEST.csv:
    RV32I_5SP/matmult-int    45.000 -> 44.001 MHz
    RV64IM_5SP/nettle-aes    38.000 -> 30.000 MHz
  Both failed to close timing with the Embench image at the variant clock.  This
  does not affect the measurement: Embench times with the mcycle CSR, so the
  cycle count is identical at any frequency the design closes at.  It does mean
  that any wall-clock figure derived from these two must use the build clock in
  MANIFEST.csv, not the variant's CoreMark frequency.

  RV64IM_5SP/nettle-aes needed a large drop rather than a small one: at 38 MHz it
  closed at -0.131 ns and at 37 MHz at -0.106, because Vivado optimises to the
  constraint and a small relaxation simply yields a similarly marginal result.
  At 30 MHz it closes at +0.735.

failed_timing/
  Holds the superseded bitstreams from the two builds that violated timing
  before they were rebuilt.  Kept as a record; do not load them.
