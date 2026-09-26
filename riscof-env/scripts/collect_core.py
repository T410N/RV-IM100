#!/usr/bin/env python3
"""Post-synthesis core-only results from logs/core_reports/<project>/.

The cores/ projects export a memory-externalised *_CORE top and are constrained
at 5 ns, so Core Fmax = 1 / (5 - WNS).  These are synthesis results: power needs
implementation and is not available here.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect_impl as C

RPTS = os.path.join(C.ENV, "logs", "core_reports")
ORDER = ["RV32I_5SP","RV32IM_5SP","RV32IM_6SP","RV32IM_7SP","RV32IM_7SP_BRAM",
         "RV32IM_7SP_BRAM_Opt","RV32IM_8SP","RV32IM_8SP_withoutOpt",
         "RV64I_5SP","RV64IM_5SP","RV64IM_6SP","RV64IM_7SP","RV64IM_7SP_BRAM",
         "RV64IM_7SP_BRAM_Opt","RV64IM_8SP","RV64IM_8SP_withoutOpt"]

W = 108
print("=" * W)
print("CORE-ONLY, POST-SYNTHESIS   (xc7a200tsbg484-1, 5 ns constraint)")
print("=" * W)
print("%-24s %8s %8s %8s %6s %5s %10s %10s" %
      ("PROJECT","LUT","LUTRAM","FF","BRAM","DSP","WNS ns","Fmax MHz"))
print("-" * W)
for p in ORDER:
    d = os.path.join(RPTS, p)
    fu, ft, fc = (os.path.join(d,f) for f in ("utilization.rpt","timing.rpt","clocks.txt"))
    if not all(os.path.isfile(x) for x in (fu, ft, fc)):
        print("%-24s %s" % (p, "-- skipped (project locked) --")); continue
    u = C.util(fu); ic = C.intra_clock(ft); per, gen = C.clocks(fc)
    cands = {c: v for c, v in ic.items() if v[1] > 0}
    clk = max(cands, key=lambda c: cands[c][1]) if cands else None
    wns = cands[clk][0]; period = per.get(clk)
    fmax = 1000.0 / (period - wns)
    print("%-24s %8d %8d %8d %6g %5g %10.3f %10.2f" %
          (p, u["lut"], u["lutram"], u["ff"], u["bram"], u["dsp"], wns, fmax))
