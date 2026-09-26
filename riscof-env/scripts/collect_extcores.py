#!/usr/bin/env python3
"""Collect the comparison-core synthesis results into logs/extcore_summary.csv."""
import re,csv,pathlib
E=pathlib.Path(__file__).resolve().parent.parent
rows=[]
for d in sorted((E/"logs/extcore").iterdir()):
    if not d.is_dir() or not (d/"utilization.rpt").exists(): continue
    u=(d/"utilization.rpt").read_text(errors="replace")
    t=(d/"timing.rpt").read_text(errors="replace")
    g=lambda p,s=u:(lambda m:int(m.group(1)) if m else 0)(re.search(p,s))
    m=re.search(r"WNS\(ns\).*?\n\s*-+[-\s]*\n\s*(-?[0-9.]+)",t,re.S)
    wns=float(m.group(1)) if m else None
    rows.append(dict(core=d.name,
        lut=g(r"\|\s*Slice LUTs\*?\s*\|\s*(\d+)"),
        lut_logic=g(r"\|\s+LUT as Logic\s*\|\s*(\d+)"),
        lutram=g(r"\|\s+LUT as Memory\s*\|\s*(\d+)"),
        ff=g(r"\|\s*Slice Registers\s*\|\s*(\d+)"),
        bram=g(r"\|\s*Block RAM Tile\s*\|\s*(\d+)"),
        dsp=g(r"\|\s*DSPs\s*\|\s*(\d+)"),
        wns_ns=wns, fmax_mhz=round(1000.0/(5.0-wns),3) if wns is not None else None))
with open(E/"logs/extcore_summary.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(f"  wrote logs/extcore_summary.csv ({len(rows)} cores)")
for r in rows: print(f"    {r['core']:<12}LUT {r['lut']:>6}  FF {r['ff']:>6}  BRAM {r['bram']}  DSP {r['dsp']}  Fmax {r['fmax_mhz']}")
