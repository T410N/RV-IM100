#!/usr/bin/env python3
"""~/Documents/Research_data_complete_0916-A.xlsx

Built in ONE pass from one source per column, from clean from-scratch
implementations (AUTO_INCREMENTAL_CHECKPOINT 0). No layering: the previous
workbooks stacked results written across a week, and cells ended up describing
different implementations from the ones beside them.

  SoC rows   <- logs/soc_final.csv   (each config's OWN project and implementation)
  SAIF power <- logs/saif_power.csv
  Core block <- logs/core_synth.csv
"""
import csv, pathlib, datetime
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill

ENV = pathlib.Path(__file__).resolve().parent.parent
SRC = pathlib.Path.home() / "Documents" / "Research_data_RISCOF_with_cores_0902.xlsx"
DST = pathlib.Path.home() / "Documents" / "Research_data_complete_0916-A.xlsx"
load = lambda n: list(csv.DictReader((ENV / "logs" / n).open()))

soc  = {(r["variant"], r["bench"]): r for r in load("soc_final.csv")}
saif = {(r["variant"], r["bench"]): r for r in load("saif_power.csv")}
core = {r["variant"]: r for r in load("core_synth.csv")}

ORDER8 = ["I_5SP", "IM_5SP", "IM_6SP", "IM_7SP", "IM_7SP_BRAM",
          "IM_7SP_BRAM_Opt", "IM_8SP_withoutOpt", "IM_8SP"]
RED    = PatternFill("solid", fgColor="FFC7CE")   # fails timing
BLUE   = PatternFill("solid", fgColor="BDD7EE")   # >1% of the clock unused
YELLOW = PatternFill("solid", fgColor="FFEB9C")   # met, but too little margin to trust
NONE   = PatternFill(fill_type=None)

SOC = dict(lut="C", lutram="D", ff="E", bram="F", dsp="G", io="H",
           fmax="J", p_clocks="M", p_signals="N", p_logic="O", p_bram="P",
           p_dsp="Q", p_pll="R", p_io="S", p_static="T")
SAIFC = dict(saif_dyn="X", saif_total="Y", dyn_delta_pct="Z", toggling_pct="AA")
CORE = dict(fmax_mhz="J", p_clocks="M", p_signals="N", p_logic="O", p_bram="P",
            p_dsp="Q", p_io="R", p_static="S", lut="T", ff="U", dsp="V")

import shutil; shutil.copy(SRC, DST)
wb = openpyxl.load_workbook(DST)
f = lambda v: None if v in (None, "", "None") else float(v)
i = lambda v: None if v in (None, "", "None") else int(float(v))
today = datetime.date.today().isoformat()
n_soc = n_saif = n_core = 0
flags = {"fails": [], "marginal": [], "headroom": []}

for sheet, pfx in (("Sheet1", "RV64"), ("Sheet2", "RV32")):
    ws = wb[sheet]
    # ---- core-only synthesis, rows 3-10 -------------------------------------
    for idx, short in enumerate(ORDER8):
        d = core.get(pfx + short)
        if not d:
            continue
        row = 3 + idx
        for key, col in CORE.items():
            v = d.get(key)
            if v in (None, "", "None"):
                continue
            ws[f"{col}{row}"] = float(v) if key.startswith(("p_", "fmax")) else int(float(v))
        ws[f"W{row}"] = (f"core-only synthesis; top {d['top']}; every variant at the same "
                         f"{f(d['constraint_mhz']):g} MHz (5 ns) constraint, WNS "
                         f"{f(d['wns_ns']):+.3f} ns; memory externalised so area EXCLUDES "
                         f"ROM/RAM and IS comparable across variants; post-synthesis power")
        n_core += 1
    # ---- SoC, one project per benchmark ------------------------------------
    for bench, base in (("dhrystone", 13), ("coremark", 23)):
        for idx, short in enumerate(ORDER8):
            d = soc.get((pfx + short, bench))
            if not d:
                continue
            row = base + idx
            for key, col in SOC.items():
                v = d.get("fmax_mhz" if key == "fmax" else key)
                if v in (None, "", "None"):
                    continue
                ws[f"{col}{row}"] = (float(v) if key.startswith("p_") or key == "fmax"
                                     else int(float(v)))
            clk, wns, fmax = f(d["constraint_mhz"]), f(d["wns_ns"]), f(d["fmax_mhz"])
            head_pct = (fmax - clk) / clk * 100
            name = f"{pfx+short}/{bench}"
            if wns < 0:
                fill, tag = RED, (f"  ||  FAILS TIMING at {clk:g} MHz (WNS {wns:+.3f} ns); "
                                  f"closes only at {fmax:.2f} MHz")
                flags["fails"].append(name)
            elif fmax - clk > 1.0:      # headroom in MHz, the sweep criterion
                fill, tag = BLUE, (f"  ||  {fmax-clk:+.3f} MHz unused ({head_pct:+.2f}%); a faster "
                                   f"image would use it")
                flags["headroom"].append(name)
            else:
                fill, tag = NONE, ""
            ws[f"J{row}"].fill = fill
            ws[f"U{row}"] = (f"{today}: from project {d['project']}, which holds ONLY this "
                             f"benchmark. Utilisation, timing and power all come from that one "
                             f"implementation, built from scratch with incremental "
                             f"implementation disabled. Core clock is the MMCM's exact output "
                             f"100*M/(D*O) = {clk:.6f} MHz, and the benchmark image is compiled "
                             f"for that same frequency. WNS {wns:+.3f} ns, "
                             f"closes at {fmax:.2f} MHz." + tag)
            ws[f"U{row}"].fill = fill
            n_soc += 1
            # ---- SAIF activity-based power ----
            s = saif.get((pfx + short, bench))
            if not s:
                continue
            for key, col in SAIFC.items():
                val = f(s[key])
                ws[f"{col}{row}"] = val / 100.0 if key.endswith("_pct") else val
                if key.endswith("_pct"):
                    ws[f"{col}{row}"].number_format = ("+0.0%;-0.0%" if key.startswith("dyn")
                                                       else "0.0%")
            ws[f"{SAIFC['saif_dyn']}{base-1}"] = "SAIF dynamic W"
            ws[f"{SAIFC['saif_total']}{base-1}"] = "SAIF total W"
            ws[f"{SAIFC['dyn_delta_pct']}{base-1}"] = "vs vectorless"
            ws[f"{SAIFC['toggling_pct']}{base-1}"] = "nets toggling"
            for c in SAIFC.values():
                ws[f"{c}{base-1}"].font = Font(bold=True)
            ws[f"U{row}"] = (ws[f"U{row}"].value +
                f"  ||  SAIF: activity-based dynamic {f(s['saif_dyn']):.3f} W vs vectorless "
                f"{f(s['vect_dyn']):.3f} W ({f(s['dyn_delta_pct']):+.1f}%); post-implementation "
                f"netlist simulation without SDF, so glitch power is excluded; "
                f"{f(s['toggling_pct']):.1f}% of nets toggling in the captured window")
            n_saif += 1

wb.save(DST)
print(f"wrote {DST}")
print(f"  core rows {n_core}/16   SoC rows {n_soc}/32   SAIF {n_saif}/32")
for k, v in flags.items():
    if v:
        print(f"  {k}: {len(v)}")
        for x in v:
            print(f"     {x}")
