#!/usr/bin/env python3
"""Per-category SAIF power for all 32 configurations.

logs/saif_power.csv carries only totals.  The workbook reports vectorless power
broken down by Clocks / Signals / Logic / BRAM / DSP / PLL / I/O / Static, so the
SAIF figures need the same decomposition to sit beside them.

Vivado prints "<0.001" for anything under a milliwatt; that is recorded as 0.0
and flagged, because treating it as exactly zero would otherwise look like a
component that draws nothing at all.
"""
import re,csv,pathlib
E=pathlib.Path(__file__).resolve().parent.parent
def val(t,label):
    m=re.search(rf"^\|\s*{re.escape(label)}\s*\|\s*([<0-9.]+)\s*\|",t,re.M)
    if not m: return None,False
    s=m.group(1).strip()
    return (0.0,True) if s.startswith("<") else (float(s),False)
rows=[];sub=[]
for d in sorted((E/"saif").iterdir()):
    rpt=d/"power_saif.rpt"
    if not d.is_dir() or not rpt.exists(): continue
    tag=d.name
    if tag.endswith("_coremark"): v,b=tag[:-9],"coremark"
    elif tag.endswith("_dhrystone"): v,b=tag[:-10],"dhrystone"
    else: continue
    t=rpt.read_text(errors="replace")
    r={"variant":v,"bench":b}
    marks=[]
    for key,label in (("p_clocks","Clocks"),("p_logic","Slice Logic"),("p_signals","Signals"),
                      ("p_bram","Block RAM"),("p_pll","PLL"),("p_dsp","DSPs"),
                      ("p_io","I/O"),("p_static","Static Power"),("p_total","Total")):
        x,sm=val(t,label); r[key]=x
        if sm: marks.append(label)
    r["below_1mW"]=";".join(marks)
    dyn=sum(r[k] or 0 for k in ("p_clocks","p_logic","p_signals","p_bram","p_pll","p_dsp","p_io"))
    r["p_dynamic_sum"]=round(dyn,4)
    r["residual"]=round((r["p_total"] or 0)-dyn-(r["p_static"] or 0),4)
    rows.append(r)
out=E/"logs/saif_breakdown.csv"
with open(out,"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(f"  wrote {out.relative_to(E)} ({len(rows)} rows)")
worst=max(abs(r['residual']) for r in rows)
print(f"  max |total - (components + static)| = {worst:.4f} W  (rounding in Vivado's own table)")
n=sum(1 for r in rows if r['below_1mW'])
print(f"  rows with at least one component under 1 mW (reported as <0.001): {n}")
