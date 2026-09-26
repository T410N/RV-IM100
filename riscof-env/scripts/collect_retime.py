#!/usr/bin/env python3
"""logs/vivado/retime/*.log -> logs/impl_retime.csv

Fmax is taken on the CORE clock -- the clock-wizard output that actually
captures logic.  The 100 MHz board clock and the MMCM feedback clock capture
nothing and report no slack.  RV64IM_8SP has no MMCM and is clocked straight
off the board pin, so there its core clock IS sys_clk_pin.
"""
import re, csv, pathlib

LOGS = pathlib.Path(__file__).resolve().parent.parent / "logs" / "vivado" / "retime"
# power categories, in the order report_power prints them; parsing stops at Total
# so the per-instance hierarchy section below it is never mistaken for a category
PWR = ["Clocks", "Slice Logic", "Signals", "Block RAM", "DSPs", "PLL", "MMCM",
       "I/O", "Static Power", "Total"]

rows = []
for f in sorted(LOGS.glob("*.log")):
    if f.name.startswith("_"):
        continue
    txt = f.read_text(errors="replace")
    clocks = [dict(name=m[0], period=float(m[1]), mhz=float(m[2]), wns=m[3], fmax=m[5])
              for m in re.findall(
                  r"^CLOCK name=(\S+) period=(\S+) mhz=(\S+) wns=(\S+) whs=(\S+) fmax=(\S+)",
                  txt, re.M)]
    core = next((c for c in clocks if c["wns"] not in ("none", "")), None)

    util = {}
    for m in re.finditer(r"^UTIL_(\w+) (\d+)$", txt, re.M):
        util.setdefault(m.group(1), int(m.group(2)))   # first hit wins

    pwr, seen_total = {}, False
    for m in re.finditer(r"^PWR (.+?) = ([\d.]+)$", txt, re.M):
        if seen_total:
            break
        cat = m.group(1)
        if cat in PWR and cat not in pwr:
            pwr[cat] = float(m.group(2))
            if cat == "Total":
                seen_total = True

    rows.append(dict(
        variant=f.stem,
        core_clk=core["name"] if core else "",
        constraint_mhz=round(core["mhz"], 3) if core else "",
        wns_ns=core["wns"] if core else "",
        fmax_mhz=core["fmax"] if core else "",
        lut=util.get("LUT"), lut_logic=util.get("LUTLOGIC"), lutram=util.get("LUTRAM"),
        ff=util.get("FF"), bram=util.get("BRAM"), dsp=util.get("DSP"),
        io=util.get("IO"), pll=(util.get("PLL", 0) or 0) + (util.get("MMCM", 0) or 0),
        # report_power OMITS a category entirely when it rounds to zero, so every
        # category must default to 0.0 -- otherwise the consumer keeps whatever
        # stale value was already in that cell.
        p_clocks=pwr.get("Clocks", 0.0), p_signals=pwr.get("Signals", 0.0),
        p_logic=pwr.get("Slice Logic", 0.0), p_bram=pwr.get("Block RAM", 0.0),
        p_dsp=pwr.get("DSPs", 0.0), p_pll=pwr.get("PLL", pwr.get("MMCM", 0.0)),
        p_io=pwr.get("I/O", 0.0), p_static=pwr.get("Static Power"), p_total=pwr.get("Total"),
        ok="DONE" in txt,
    ))

out = LOGS.parent.parent / "impl_retime.csv"
with out.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

h = (f"{'variant':<23}{'constr':>8}{'WNS':>8}{'Fmax':>9}{'LUT':>7}{'LUTRAM':>7}"
     f"{'FF':>6}{'BRAM':>5}{'DSP':>4}{'P(W)':>7}")
print(h); print("-" * len(h))
for r in rows:
    f = lambda k, d="-": r[k] if r[k] is not None else d
    flag = "" if r["ok"] else "  INCOMPLETE"
    neg = " *" if r["wns_ns"] and str(r["wns_ns"]).startswith("-") else ""
    print(f"{r['variant']:<23}{f('constraint_mhz'):>8}{f('wns_ns'):>8}{f('fmax_mhz'):>9}"
          f"{f('lut'):>7}{f('lutram'):>7}{f('ff'):>6}{f('bram'):>5}{f('dsp'):>4}"
          f"{f('p_total'):>7}{neg}{flag}")
print("\n* = negative setup slack: timing NOT met at the configured clock")
print(f"wrote {out}")
