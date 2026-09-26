#!/usr/bin/env python3
"""~/Documents/Research_data_Embench_0918-A.xlsx

Embench-IoT FPGA results, laid out like Research_data_FPGA_0917-A.xlsx: one
sheet per architecture, a block per benchmark, variants down the rows.

Two departures from that workbook, both deliberate:

  - power is the SAIF activity-based figure, not vectorless.  The columns are
    the same decomposition (Clocks / Signals / Logic / BRAM / DSP / PLL / I/O /
    Static) so the two workbooks read alike, but every value is measured
    switching activity rather than Vivado's assumed-toggle estimate.
    Vivado prints "<0.001" for sub-milliwatt components; those are written as
    0.0 and listed in the notes, since a bare 0.000 would read as "draws
    nothing".

  - a Validation sheet compares every FPGA cycle/instret against the RTL
    simulation.  That comparison is the point of the exercise, not a footnote:
    it is what lets the simulation-derived CPI and stall tables stand as
    hardware-backed.

SAIF power is per (variant, benchmark-of-the-SoC-build) and the SoC builds are
CoreMark and Dhrystone, not Embench.  The power columns therefore describe the
variant's CoreMark SoC build and are labelled as such -- they are NOT power
measured while running Embench, and must not be presented as if they were.
"""
import csv, pathlib, datetime
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

ENV = pathlib.Path(__file__).resolve().parent.parent
ROOT = ENV.parent
DST = pathlib.Path.home() / "Documents" / "Research_data_Embench_0918-A.xlsx"
BENCHES = ["matmult-int", "crc32", "nettle-aes", "statemate", "md5sum"]
ORDER = ["I_5SP","IM_5SP","IM_6SP","IM_7SP","IM_7SP_BRAM","IM_7SP_BRAM_Opt",
         "IM_8SP_withoutOpt","IM_8SP"]

HDR   = PatternFill("solid", fgColor="FFBFBFBF")
BAND  = PatternFill("solid", fgColor="FFEEEEEE")
GOOD  = PatternFill("solid", fgColor="FFCDF2E4")
WARN  = PatternFill("solid", fgColor="FFFFEB9C")
F     = "NanumGothic"
thin  = Side(style="thin", color="FFD0D0D0")
BOX   = Border(left=thin, right=thin, top=thin, bottom=thin)

# Every RV32 result on disk was produced before the RV32 counter-read fix and is
# not usable.  boardsupport.c read a 64-bit counter with a single csrr, which on
# RV32 fills only the low half of a register pair; mcycle crosses a 2^32 boundary
# during a run, so the garbage high word stopped cancelling in the subtraction.
# A handful of RV32 rows happen to look right because the high word was zero by
# luck -- they are excluded too, since "correct by accident" is not a measurement.
# The RV64 path was always correct: there, one csrr is the whole counter.
RV32_SUPERSEDED = True

def load_fpga():
    out = {}
    for f in ROOT.glob("bitstream/embench/RV*/Done/*/*.csv"):
        for r in csv.DictReader(f.open()):
            if RV32_SUPERSEDED and r["architecture"].startswith("RV32"):
                continue
            out[(r["architecture"], r["benchmark"])] = r
    return out

fpga = load_fpga()
sim  = {(r["variant"], r["benchmark"]): r
        for r in csv.DictReader((ENV/"logs/embench_sim_reference.csv").open())}
soc  = {(r["variant"], r["bench"]): r
        for r in csv.DictReader((ENV/"logs/soc_final.csv").open())}
brk  = {(r["variant"], r["bench"]): r
        for r in csv.DictReader((ENV/"logs/saif_breakdown.csv").open())}
manifest = {}
for r in csv.DictReader((ROOT/"bitstream/embench/MANIFEST.csv").open()):
    manifest[(r["variant"], r["benchmark"])] = r

def put(ws, cell, value, *, bold=False, fill=None, fmt=None, align="right"):
    c = ws[cell]; c.value = value
    c.font = Font(name=F, size=11, bold=bold)
    if fill: c.fill = fill
    if fmt:  c.number_format = fmt
    c.alignment = Alignment(horizontal=align, vertical="center")
    c.border = BOX
    return c

def sheet_for(wb, arch):
    ws = wb.create_sheet(arch)
    for col, w in (("A",4),("B",22),("C",15),("D",14),("E",10),("F",12),("G",14),
                   ("H",10),("I",12),("J",11),("K",11),("L",10),("M",10),("N",10),
                   ("O",10),("P",10),("Q",10),("R",10),("S",10),("T",11)):
        ws.column_dimensions[col].width = w
    return ws

wb = openpyxl.Workbook(); wb.remove(wb.active)
notes = []

for arch, pfx in (("RV64", "RV64"), ("RV32", "RV32")):
    ws = sheet_for(wb, arch)
    row = 2
    for b in BENCHES:
        put(ws, f"B{row}", f"{arch}  {b}", bold=True, fill=HDR, align="left")
        for col, lbl in (("C","FPGA cycles"),("D","FPGA instret"),("E","CPI"),
                         ("F","sim cycles"),("G","sim = FPGA?"),("H","verify"),
                         ("I","build MHz"),("J","runtime ms")):
            put(ws, f"{col}{row}", lbl, bold=True, fill=HDR)
        row += 1
        for short in ORDER:
            v = pfx + short
            put(ws, f"B{row}", short, fill=BAND, align="left")
            fr = fpga.get((v, b)); sr = sim.get((v, b)); mf = manifest.get((v, b))
            if fr:
                cyc = int(fr["cycles"]); ins = int(fr["instret"])
                put(ws, f"C{row}", cyc, fmt="#,##0")
                put(ws, f"D{row}", ins, fmt="#,##0")
                put(ws, f"E{row}", round(cyc/ins, 4) if ins else None, fmt="0.0000")
                put(ws, f"H{row}", fr.get("verify",""))
                if sr:
                    sc = int(sr["sim_cycles"])
                    put(ws, f"F{row}", sc, fmt="#,##0")
                    exact = (cyc == sc and ins == int(sr["sim_instret"]))
                    put(ws, f"G{row}", "EXACT" if exact else "differs",
                        fill=GOOD if exact else WARN)
                if mf and mf.get("build_clock_mhz"):
                    mhz = float(mf["build_clock_mhz"])
                    put(ws, f"I{row}", mhz, fmt="0.000###")
                    put(ws, f"J{row}", round(cyc/(mhz*1e6)*1e3, 3), fmt="0.000")
            else:
                put(ws, f"C{row}", "awaiting re-measurement (RV32 counter fix)"
                    if v.startswith("RV32") else "not yet measured", fill=WARN, align="left")
            row += 1
        row += 1

    # SAIF power block -- of the variant's CoreMark SoC build, not of Embench
    put(ws, f"B{row}", f"{arch}  SAIF power of the SoC build (CoreMark image)",
        bold=True, fill=HDR, align="left")
    for col, lbl in (("C","SoC Fmax"),("D","Total W"),("E","Dynamic"),("F","Clocks"),
                     ("G","Signals"),("H","Logic"),("I","BRAM"),("J","DSP"),
                     ("K","PLL"),("L","I/O"),("M","Static"),("N","toggling %")):
        put(ws, f"{col}{row}", lbl, bold=True, fill=HDR)
    row += 1
    for short in ORDER:
        v = pfx + short
        put(ws, f"B{row}", short, fill=BAND, align="left")
        s = soc.get((v, "coremark")); k = brk.get((v, "coremark"))
        if s: put(ws, f"C{row}", float(s["fmax_mhz"]), fmt="0.000")
        if k:
            g = lambda key: float(k[key] or 0)
            dyn = sum(g(x) for x in ("p_clocks","p_signals","p_logic","p_bram","p_dsp","p_pll","p_io"))
            put(ws, f"D{row}", g("p_total"), fmt="0.000")
            put(ws, f"E{row}", round(dyn,4), fmt="0.000")
            for col, key in (("F","p_clocks"),("G","p_signals"),("H","p_logic"),
                             ("I","p_bram"),("J","p_dsp"),("K","p_pll"),("L","p_io"),
                             ("M","p_static")):
                put(ws, f"{col}{row}", g(key), fmt="0.000")
            if k["below_1mW"]:
                notes.append(f"{v}/coremark: reported <0.001 W for {k['below_1mW']}")
        sp = {(r['variant'],r['bench']):r for r in csv.DictReader((ENV/'logs/saif_power.csv').open())}
        if (v,"coremark") in sp:
            put(ws, f"N{row}", float(sp[(v,"coremark")]["toggling_pct"])/100, fmt="0.0%")
        row += 1

# ---- Validation sheet: the sim-vs-hardware comparison ----
vs = wb.create_sheet("Validation")
for col, w in (("A",4),("B",24),("C",14),("D",16),("E",16),("F",16),("G",16),("H",12),("I",12)):
    vs.column_dimensions[col].width = w
put(vs, "B2", "FPGA vs RTL simulation: mcycle / minstret", bold=True, fill=HDR, align="left")
for col, lbl in (("C","benchmark"),("D","FPGA cycles"),("E","sim cycles"),
                 ("F","FPGA instret"),("G","sim instret"),("H","cycles"),("I","instret")):
    put(vs, f"{col}2", lbl, bold=True, fill=HDR)
r = 3; nexact = ntot = 0
for (v, b), fr in sorted(fpga.items()):
    sr = sim.get((v, b))
    if not sr: continue
    ntot += 1
    cyc, ins = int(fr["cycles"]), int(fr["instret"])
    sc, si = int(sr["sim_cycles"]), int(sr["sim_instret"])
    ce, ie = cyc == sc, ins == si
    nexact += (ce and ie)
    put(vs, f"B{r}", v, fill=BAND, align="left")
    put(vs, f"C{r}", b, align="left")
    put(vs, f"D{r}", cyc, fmt="#,##0"); put(vs, f"E{r}", sc, fmt="#,##0")
    put(vs, f"F{r}", ins, fmt="#,##0"); put(vs, f"G{r}", si, fmt="#,##0")
    put(vs, f"H{r}", "EXACT" if ce else "differs", fill=GOOD if ce else WARN)
    put(vs, f"I{r}", "EXACT" if ie else "differs", fill=GOOD if ie else WARN)
    r += 1
put(vs, f"B{r+1}", f"{nexact} of {ntot} rows match simulation exactly in BOTH counters",
    bold=True, align="left")
put(vs, f"B{r+2}", "All 40 RV64 rows are shown.  RV32 is excluded: those runs predate the "
                   "RV32 counter-read fix and their cycle counts are invalid.", align="left")

# ---- Notes sheet ----
ns = wb.create_sheet("Notes")
ns.column_dimensions["B"].width = 120
lines = [
 f"Built {datetime.date.today().isoformat()} from bitstream/embench/*/Done/*/*.csv",
 "",
 "POWER COLUMNS",
 "  SAIF activity-based power, replacing the vectorless figures used in",
 "  Research_data_FPGA_0917-A.xlsx.  Same decomposition, but measured switching",
 "  activity rather than Vivado's assumed toggle rates.",
 "  These describe the variant's CoreMark SoC build.  They are NOT power measured",
 "  while running Embench -- no SAIF capture was made for the Embench images --",
 "  and must not be presented as such.",
 "  Vivado prints '<0.001' for sub-milliwatt components; written here as 0.000.",
 "",
 "VALIDATION",
 "  The Validation sheet compares every FPGA cycle and instret against RTL",
 "  simulation.  Exact agreement means the simulation is cycle-accurate against",
 "  silicon, which is what lets the simulation-derived CPI, stall-cycle and",
 "  branch-misprediction tables stand as hardware-backed rather than inferred.",
 "",
 "CLOCKS",
 "  'build MHz' is the clock each Embench bitstream was built at, from",
 "  bitstream/embench/MANIFEST.csv.  Two differ from their variant's normal clock",
 "  because they would not close timing with the Embench image:",
 "     RV32I_5SP/matmult-int    45.000 -> 44.001 MHz",
 "     RV64IM_5SP/nettle-aes    38.000 -> 30.000 MHz",
 "  Cycle counts are unaffected -- Embench times with mcycle -- but any runtime",
 "  derived from them must use the build clock, which is what column J does.",
 "",
 "EXCLUSIONS",
 "  18 of 19 Embench benchmarks fit the 32 KB instruction memory and were verified",
 "  in simulation on all 16 variants; xgboost alone exceeds it at 41-45 KB.",
 "  Five were selected for FPGA measurement, each mapped to a contested claim:",
 "     matmult-int  load-use hazard + integer multiply",
 "     crc32        tight loop, back-to-back ALU dependency",
 "     nettle-aes   table-lookup heavy, memory access intensity",
 "     statemate    branch-dense state machine",
 "     md5sum       mixed sequential integer baseline",
 "",
]
if notes:
    lines += ["SUB-MILLIWATT COMPONENTS"] + [f"  {n}" for n in sorted(set(notes))]
for i, t in enumerate(lines, start=2):
    c = ns[f"B{i}"]; c.value = t
    c.font = Font(name=F, size=11, bold=t.isupper() and bool(t))
    c.alignment = Alignment(horizontal="left", vertical="center")

wb.save(DST)
print(f"  wrote {DST}")
print(f"  validation: {nexact}/{ntot} rows exact")
