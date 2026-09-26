#!/usr/bin/env python3
"""Emit one line only when a clean row DIFFERS from the incremental baseline,
plus a progress note every 8 configs and a final summary.  Silence means the
clean rebuild is reproducing the workbook."""
import csv,re,sys,time,pathlib
env=pathlib.Path(__file__).resolve().parent.parent
base={}
for r in csv.DictReader(open(env/"logs/soc_final_incremental.csv")):
    base[(r['variant'],r['bench'])]=r
seen=set(); total=32; changed=0
out=env/"logs/final_impl"
drv=env/"logs/reimpl_clean32.log"
while True:
    for u in sorted(out.glob("*/utilization.rpt")):
        tag=u.parent.name
        if tag in seen: continue
        log=out/f"{tag}.log"
        if not log.exists(): continue
        seen.add(tag)
        txt=log.read_text(errors="replace")
        cl=[l for l in txt.splitlines() if l.startswith("CLOCK") and "wns=none" not in l]
        wns=re.search(r"wns=(\S+)",cl[0]).group(1) if cl else None
        m=re.search(r"\|\s+Slice LUTs\*?\s+\|\s+(\d+)",u.read_text(errors="replace"))
        lut=m.group(1) if m else None
        v,b=tag.rsplit("_",1); o=base.get((v,b))
        if o is None:
            print(f"[{len(seen)}/{total}] {tag}: no baseline row",flush=True); changed+=1
        elif lut!=o['lut'] or wns is None or abs(float(wns)-float(o['wns_ns']))>1e-9:
            changed+=1
            print(f"[{len(seen)}/{total}] CHANGED {tag}: "
                  f"LUT {o['lut']}->{lut}  WNS {o['wns_ns']}->{wns}",flush=True)
        if len(seen)%8==0:
            print(f"[{len(seen)}/{total}] progress - {changed} changed so far",flush=True)
    if len(seen)>=total or (drv.exists() and "=== finished" in drv.read_text(errors="replace")):
        print(f"SWEEP DONE: {len(seen)}/{total} configs, {changed} differ from baseline",flush=True)
        return_code=0; sys.exit(0)
    time.sleep(30)
