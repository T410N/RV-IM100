# Resume the SAIF power measurement

Stopped cleanly 2026-09-14 ~09:55 (laptop battery). Nothing is lost.

## State

* **29 / 32** configs measured with the final, consistent method
* **3** still to re-measure (their earlier values are archived as `.pregate`):
  `RV64IM_6SP/coremark`, `RV64IM_8SP_withoutOpt/coremark`, `RV64I_5SP/coremark`
* All 32 netlists built, so no Vivado re-implementation is needed — simulation
  and power only, roughly 30–60 min for the three.

## To resume

```bash
cd ~/Desktop/RV-IM100/riscof-env
PAR=3 ./scripts/saif_regate.sh          # logs/saif_regate.json still lists the 3
```
It is resumable: any config with `saif/results/<v>_<b>.txt` is skipped.

Then rebuild the workbook:
```bash
<venv>/bin/python scripts/build_workbook_0913.py
```

## Why these are being re-measured

Window placement changes activity-based power by up to ~90%. Early captures
landed in program start-up or in a UART-printing phase, where the CPU is
largely idle-waiting, and understated dynamic power. The final method, applied
to all 32:

1. boot, then force `benchmark_start` to skip the 5.5 ms button debounce
2. hold `tx_busy` low for 1 ms so the CPU runs through any pre-kernel printing
   without waiting on the 115200-baud wire, then **release** the force
3. search forward for a 100 us window with `uart_delta <= 1`
4. capture SAIF there; record `toggling_pct` and `uart_delta` with every result

The force is always released before the capture opens, so no measured window
contains artificial forcing.

`.pregate` files are the earlier (window-sensitive) values, kept deliberately:
they quantify how much window placement matters, which is worth reporting.

## Caveat for the paper

Switching activity comes from post-implementation netlist simulation **without**
SDF back-annotation — SDF drives flip-flops to X at start-up and the design
never recovers. Glitch power is therefore excluded.
