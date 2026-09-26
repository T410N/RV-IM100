#!/usr/bin/env python3
"""Rebuild logs/soc_final.csv from logs/final_impl/ -- one implementation per row.

Every field comes from the SAME clean implementation run: utilisation and
vectorless power from that run's reports, timing from its per-clock CLOCK lines
(the core clock, never the board clock, which has no timed paths)."""
import csv,re,pathlib,sys
env=pathlib.Path(__file__).resolve().parent.parent
cfg={(r['variant'],r['benchmark']):r
     for r in csv.DictReader(open(env.parent/"evidence/CONFIGURATIONS_perbench.csv"))}
FIELDS=["variant","bench","project","constraint_mhz","wns_ns","fmax_mhz","lut","lutram",
        "ff","bram","dsp","io","bit_wns","bit_fmax","p_clocks","p_signals","p_logic",
        "p_bram","p_dsp","p_pll","p_io","p_static","p_total"]
def num(m):
    if not m: return 0.0
    t=m.group(1).strip()
    return 0.0 if t.startswith("<") else float(t)
rows=[]; bad=[]
for u in sorted((env/"logs/final_impl").glob("*/utilization.rpt")):
    tag=u.parent.name; v,b=tag.rsplit("_",1)
    log=(env/"logs/final_impl"/f"{tag}.log").read_text(errors="replace")
    ut=u.read_text(errors="replace")
    pw=(u.parent/"power.rpt")
    pw=pw.read_text(errors="replace") if pw.exists() else ""
    cl=[l for l in log.splitlines() if l.startswith("CLOCK ") and "wns=none" not in l]
    if not cl: bad.append(f"{tag}: no timed clock"); continue
    if len(cl)>1: bad.append(f"{tag}: {len(cl)} timed clocks, using {cl[0].split()[1]}")
    wns=float(re.search(r"wns=(\S+)",cl[0]).group(1))
    fmax=float(re.search(r"fmax=(\S+)",cl[0]).group(1))
    gi=lambda p:(lambda m:int(m.group(1)) if m else 0)(re.search(p,ut))
    gp=lambda p:num(re.search(p,pw))
    c=cfg.get((v,b),{})
    rows.append(dict(
        variant=v,bench=b,project=pathlib.Path(c.get("xpr","")).parent.name,
        constraint_mhz=c.get("clock_mhz",""),wns_ns=wns,fmax_mhz=fmax,
        lut=gi(r"\|\s+Slice LUTs\*?\s+\|\s+(\d+)"),
        lutram=gi(r"\|\s+LUT as Memory\s+\|\s+(\d+)"),
        ff=gi(r"\|\s+Slice Registers\s+\|\s+(\d+)"),
        bram=gi(r"\|\s+Block RAM Tile\s+\|\s+(\d+)"),
        dsp=gi(r"\|\s+DSPs\s+\|\s+(\d+)"),
        io=gi(r"\|\s+Bonded IOB\s+\|\s+(\d+)"),
        bit_wns=wns,bit_fmax=fmax,
        p_clocks=gp(r"\|\s+Clocks\s+\|\s+([<0-9.]+)"),
        p_signals=gp(r"\|\s+Signals\s+\|\s+([<0-9.]+)"),
        p_logic=gp(r"\|\s+Slice Logic\s+\|\s+([<0-9.]+)"),
        p_bram=gp(r"\|\s+Block RAM\s+\|\s+([<0-9.]+)"),
        p_dsp=gp(r"\|\s+DSPs\s+\|\s+([<0-9.]+)"),
        p_pll=gp(r"\|\s+PLL\s+\|\s+([<0-9.]+)"),
        p_io=gp(r"\|\s+I/O\s+\|\s+([<0-9.]+)"),
        p_static=gp(r"\|\s+Device Static \(W\)\s+\|\s+([<0-9.]+)"),
        p_total=gp(r"\|\s+Total On-Chip Power \(W\)\s+\|\s+([<0-9.]+)")))
out=env/"logs/soc_final.csv"
with open(out,"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
print(f"wrote {len(rows)} rows -> {out.relative_to(env)}")
for m in bad: print("  note:",m)
