#!/usr/bin/env python3
"""logs/coresynth/*.log -> logs/core_synth.csv

Core-only out-of-context synthesis of the memory-externalised *_CORE top, all
variants at the same 5 ns (200 MHz) constraint, so Fmax = 1000/(5 - WNS) and the
area figures exclude ROM/RAM entirely.  That is what makes these comparable
across variants -- the SoC LUT totals are not, because the 5SP/6SP designs hold
memory in LUTRAM while the BRAM/8SP designs hold it in block RAM.

POST-SYNTHESIS: routing is estimated, so these are comparable to each other but
not to the SoC post-route numbers.
"""
import re, csv, pathlib

LOGS = pathlib.Path(__file__).resolve().parent.parent / "logs" / "coresynth"
PWR = ["Clocks", "Slice Logic", "Signals", "Block RAM", "DSPs", "I/O",
       "Static Power", "Total"]
ORDER = ["RV32I_5SP", "RV32IM_5SP", "RV32IM_6SP", "RV32IM_7SP", "RV32IM_7SP_BRAM",
         "RV32IM_7SP_BRAM_Opt", "RV32IM_8SP_withoutOpt", "RV32IM_8SP",
         "RV64I_5SP", "RV64IM_5SP", "RV64IM_6SP", "RV64IM_7SP", "RV64IM_7SP_BRAM",
         "RV64IM_7SP_BRAM_Opt", "RV64IM_8SP_withoutOpt", "RV64IM_8SP"]

rows = []
for name in ORDER:
    f = LOGS / f"{name}.log"
    if not f.is_file():
        rows.append(dict(variant=name, status="NO LOG")); continue
    txt = f.read_text(errors="replace")
    if "READONLY_SKIP" in txt:
        rows.append(dict(variant=name, status="LOCKED")); continue
    if "DONE" not in txt:
        prog = re.search(r"^SYNTH_PROGRESS (\S+)", txt, re.M)
        rows.append(dict(variant=name,
                         status=f"INCOMPLETE {prog.group(1) if prog else '?'}")); continue

    clocks = [dict(name=m[0], period=float(m[1]), wns=m[3], fmax=m[4])
              for m in re.findall(
                  r"^CLOCK name=(\S+) period=(\S+) mhz=(\S+) wns=(\S+) fmax=(\S+)", txt, re.M)]
    core = next((c for c in clocks if c["wns"] not in ("none", "")), None)

    util = {}
    for m in re.finditer(r"^UTIL_(\w+) (\d+)$", txt, re.M):
        util.setdefault(m.group(1), int(m.group(2)))
    # post-synthesis reports may omit the combined "Slice LUTs*" row
    lut = util.get("LUT") or (util.get("LUTLOGIC", 0) + util.get("LUTRAM", 0))

    pwr, done = {}, False
    for m in re.finditer(r"^PWR (.+?) = ([\d.]+)$", txt, re.M):
        if done: break
        c = m.group(1)
        if c in PWR and c not in pwr:
            pwr[c] = float(m.group(2))
            done = (c == "Total")

    rows.append(dict(
        variant=name, status="ok",
        top=(re.search(r"^TOP\s+(\S+)", txt, re.M) or [None, ""])[1],
        constraint_mhz=round(1000.0 / core["period"], 3) if core else "",
        wns_ns=core["wns"] if core else "", fmax_mhz=core["fmax"] if core else "",
        lut=lut, lut_logic=util.get("LUTLOGIC"), lutram=util.get("LUTRAM", 0),
        ff=util.get("FF"), bram=util.get("BRAM", 0), dsp=util.get("DSP", 0),
        # a category absent from report_power rounds to zero -- never leave it None
        p_clocks=pwr.get("Clocks", 0.0), p_signals=pwr.get("Signals", 0.0),
        p_logic=pwr.get("Slice Logic", 0.0), p_bram=pwr.get("Block RAM", 0.0),
        p_dsp=pwr.get("DSPs", 0.0), p_io=pwr.get("I/O", 0.0),
        p_static=pwr.get("Static Power"), p_total=pwr.get("Total"),
    ))

out = LOGS.parent / "core_synth.csv"
cols = ["variant", "status", "top", "constraint_mhz", "wns_ns", "fmax_mhz", "lut",
        "lut_logic", "lutram", "ff", "bram", "dsp", "p_clocks", "p_signals",
        "p_logic", "p_bram", "p_dsp", "p_io", "p_static", "p_total"]
with out.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)

h = f"{'variant':<23}{'WNS':>9}{'Fmax':>9}{'LUT':>7}{'LUTRAM':>7}{'FF':>6}{'DSP':>5}{'P(W)':>7}"
print("CORE-ONLY, POST-SYNTHESIS  (xc7a200tsbg484-1, 5 ns / 200 MHz constraint)")
print(h); print("-" * len(h))
for r in rows:
    if r.get("status") != "ok":
        print(f"{r['variant']:<23}  -- {r.get('status')} --"); continue
    g = lambda k: r[k] if r[k] is not None else "-"
    print(f"{r['variant']:<23}{g('wns_ns'):>9}{g('fmax_mhz'):>9}{g('lut'):>7}"
          f"{g('lutram'):>7}{g('ff'):>6}{g('dsp'):>5}{g('p_total'):>7}")
print(f"\nwrote {out}")
