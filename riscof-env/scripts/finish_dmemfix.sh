#!/usr/bin/env bash
# Finish the RV32IM_7SP_BRAM_Opt data-memory correction end to end.
#   dhrystone: clock unchanged -> re-cost the existing SAIF on the new netlist
#   coremark : clock moved 90 -> 92 MHz -> the capture's implied activity rate
#              belongs to the old clock, so it must be re-simulated
set -uo pipefail
E="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$E"
echo "=== [1/4] re-cost dhrystone SAIF on the corrected netlist $(date +%H:%M:%S) ==="
bash scripts/repower_changed.sh RV32IM_7SP_BRAM_Opt_dhrystone
echo "=== [2/4] re-simulate coremark SAIF at 92 MHz $(date +%H:%M:%S) ==="
bash scripts/saif_resim.sh RV32IM_7SP_BRAM_Opt_coremark
echo "=== [3/4] rebuild soc_final.csv and fold SAIF $(date +%H:%M:%S) ==="
python3 scripts/build_soc_final.py > /dev/null
python3 - <<'PY'
import csv,re,pathlib
exact={}
for l in open("logs/exact_pll.txt"):
    m=re.match(r"EXACT (\S+) .*exact=([0-9.]+)",l)
    if m: exact[m.group(1)]=float(m.group(2))
exact.update({"RV64IM_7SP_BRAM_Opt_coremark":80.952380952,"RV32IM_8SP_coremark":122.0,
              "RV32IM_8SP_dhrystone":122.0,"RV64IM_7SP_BRAM_coremark":58.0,
              "RV32IM_7SP_BRAM_Opt_coremark":92.0,"RV32IM_7SP_BRAM_Opt_dhrystone":90.909090909})
rows=list(csv.DictReader(open("logs/soc_final.csv"))); hdr=list(rows[0].keys())
for r in rows:
    e=exact[f"{r['variant']}_{r['bench']}"]; w=float(r['wns_ns'])
    fm=1000.0/(1000.0/e-w)
    r['constraint_mhz']=f"{e:.6f}"; r['fmax_mhz']=f"{fm:.3f}"; r['bit_fmax']=f"{fm:.3f}"
with open("logs/soc_final.csv","w",newline="") as f:
    csv.DictWriter(f,fieldnames=hdr).writeheader() or None
with open("logs/soc_final.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=hdr); w.writeheader(); w.writerows(rows)
# fold the two refreshed SAIF results
def grab_log(p):
    t=pathlib.Path(p).read_text(errors="replace")
    g=lambda a,k:(lambda m: float(m.group(1)) if m else None)(re.search(rf"^{a} {re.escape(k)} = ([0-9.]+)",t,re.M))
    return dict(vt=g("VECTORLESS","Total On-Chip Power (W)"),vd=g("VECTORLESS","Dynamic (W)"),
                st=g("SAIF_BASED","Total On-Chip Power (W)"),sd=g("SAIF_BASED","Dynamic (W)"),
                ss=g("SAIF_BASED","Device Static (W)"))
def grab_res(p):
    t=pathlib.Path(p).read_text(errors="replace")
    g=lambda k:(lambda m: float(m.group(1)) if m else None)(re.search(rf"^{re.escape(k)} = ([0-9.]+)",t,re.M))
    tog=re.search(r"^toggling_pct (\S+)",t,re.M)
    return dict(vt=g("VECTORLESS Total On-Chip Power (W)"),vd=g("VECTORLESS Dynamic (W)"),
                st=g("SAIF_BASED Total On-Chip Power (W)"),sd=g("SAIF_BASED Dynamic (W)"),
                ss=g("SAIF_BASED Device Static (W)"),tog=float(tog.group(1)) if tog else None)
srows=list(csv.DictReader(open("logs/saif_power.csv"))); shdr=list(srows[0].keys())
upd={}
p=pathlib.Path("logs/repower/RV32IM_7SP_BRAM_Opt_dhrystone.log")
if p.exists(): upd[("RV32IM_7SP_BRAM_Opt","dhrystone")]=grab_log(p)
p=pathlib.Path("saif/results/RV32IM_7SP_BRAM_Opt_coremark.txt")
if p.exists(): upd[("RV32IM_7SP_BRAM_Opt","coremark")]=grab_res(p)
for r in srows:
    k=(r['variant'],r['bench'])
    if k not in upd: continue
    d=upd[k]
    if d['sd'] is None: continue
    r['vect_total'],r['vect_dyn']=d['vt'],d['vd']
    r['saif_total'],r['saif_dyn'],r['saif_static']=d['st'],d['sd'],d['ss']
    if d.get('tog') is not None: r['toggling_pct']=d['tog']
    r['dyn_delta_pct']=round((d['sd']-d['vd'])/d['vd']*100,1)
    print(f"  SAIF updated {k[0]}/{k[1]}: dyn {d['sd']} W, total {d['st']} W")
with open("logs/saif_power.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=shdr); w.writeheader(); w.writerows(srows)
PY
echo "=== [4/4] rebuild the workbook $(date +%H:%M:%S) ==="
/tmp/xlsxenv/bin/python3 scripts/build_workbook_0916A.py
echo "=== DMEM FIX COMPLETE $(date) ==="
