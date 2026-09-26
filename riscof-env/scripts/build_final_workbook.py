#!/usr/bin/env python3
"""~/Documents/Research_data_Final_0921.xlsx

Everything measured for the revision that is NOT already in
Research_data_FPGA_0917-A.xlsx (SoC/core synthesis, CoreMark and Dhrystone FPGA)
or Research_data_Embench_0918-A.xlsx (Embench FPGA).

  CPI and stalls      profile.csv          reviewer ask for a measured CPI table
  Embench simulation  embench.csv          full 19 x 16 matrix, supplementary
  Core comparison     extcore_summary.csv  PicoRV32 / RVCoreP / VexRiscv
  SAIF detail         saif_breakdown.csv   per-category activity-based power
  Verification        RISCOF, riscv-tests, Embench verify
"""
import csv, pathlib, datetime, collections
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

ENV  = pathlib.Path(__file__).resolve().parent.parent
ROOT = ENV.parent
DST  = pathlib.Path.home() / "Documents" / "Research_data_Final_0921.xlsx"
F    = "NanumGothic"
HDR  = PatternFill("solid", fgColor="FFBFBFBF")
BAND = PatternFill("solid", fgColor="FFEEEEEE")
GOOD = PatternFill("solid", fgColor="FFCDF2E4")
WARN = PatternFill("solid", fgColor="FFFFEB9C")
BAD  = PatternFill("solid", fgColor="FFFFC7CE")
thin = Side(style="thin", color="FFD0D0D0")
BOX  = Border(left=thin, right=thin, top=thin, bottom=thin)
ORDER = ["I_5SP","IM_5SP","IM_6SP","IM_7SP","IM_7SP_BRAM","IM_7SP_BRAM_Opt",
         "IM_8SP_withoutOpt","IM_8SP"]
VARIANTS = [p+s for p in ("RV32","RV64") for s in ORDER]
STALL = ["branch mispred","pc stall","front-end stall","ID/EX stall","EXR/EX stall",
         "EX/EX2 stall","EX/MEM stall","MEM/WB stall","load-use hazard",
         "divider busy","multiplier busy"]

AVAIL = {}
_ap = ENV/"logs/profile_available.json"
if _ap.exists():
    import json
    AVAIL = json.load(_ap.open())

def load(n):
    p = ENV/"logs"/n
    return list(csv.DictReader(p.open())) if p.exists() else []

def put(ws, cell, v, *, bold=False, fill=None, fmt=None, align="right", wrap=False):
    c = ws[cell]; c.value = v
    c.font = Font(name=F, size=11, bold=bold)
    if fill: c.fill = fill
    if fmt: c.number_format = fmt
    c.alignment = Alignment(horizontal=align, vertical="center", wrap_text=wrap)
    c.border = BOX
    return c

def widths(ws, spec):
    for col, w in spec: ws.column_dimensions[col].width = w

wb = openpyxl.Workbook(); wb.remove(wb.active)
COLS = "BCDEFGHIJKLMNOPQRSTUVWXYZ"

# ---------------------------------------------------------------- CPI & stalls
prof = load("profile.csv")
ws = wb.create_sheet("CPI and stalls")
widths(ws, [("A",3),("B",24),("C",11),("D",14),("E",14),("F",9),("G",9),("H",11),("I",11)] +
           [(chr(74+i),13) for i in range(11)])
put(ws,"B2","Cycle-accurate profiling, both benchmarks x 16 variants",bold=True,fill=HDR,align="left")
put(ws,"B3","Counters live in the simulation wrapper, not the core, so profiling cannot "
            "perturb the RTL that produced the timing and area numbers.  FPGA runs confirm "
            "the simulation is cycle-accurate: all 40 RV64 Embench rows match exactly.",
    align="left", wrap=True)
ws.merge_cells("B3:P3"); ws.row_dimensions[3].height = 30
row = 5
for bench in ("dhrystone","coremark"):
    put(ws,f"B{row}",f"{bench}",bold=True,fill=HDR,align="left")
    for i,lbl in enumerate(["cycles","retired","CPI","IPC","branch","mispred","br-miss %"]):
        put(ws,f"{COLS[i+1]}{row}",lbl,bold=True,fill=HDR)
    for i,lbl in enumerate(STALL):
        put(ws,f"{COLS[i+8]}{row}",lbl+" %",bold=True,fill=HDR)
    row += 1
    for v in VARIANTS:
        r = next((x for x in prof if x["_v"]==f"socs_{v}" and x["_b"]==bench), None)
        put(ws,f"B{row}",v,fill=BAND,align="left")
        if r:
            cyc=int(r["cycles"] or 0); ret=int(r["retired"] or 0)
            br=int(r["branch"] or 0); mis=int(r.get("bit0_events") or 0)
            put(ws,f"C{row}",cyc,fmt="#,##0"); put(ws,f"D{row}",ret,fmt="#,##0")
            put(ws,f"E{row}",round(cyc/ret,4) if ret else None,fmt="0.0000")
            put(ws,f"F{row}",round(ret/cyc,4) if cyc else None,fmt="0.0000")
            put(ws,f"G{row}",br,fmt="#,##0"); put(ws,f"H{row}",mis,fmt="#,##0")
            put(ws,f"I{row}",(mis/br) if br else None,fmt="0.00%")
            # A counter reading 0 can mean the stage does not exist OR that it never
            # fired.  profile.csv cannot tell them apart, so availability is taken from
            # the instrumented RTL: SIM_prof[bit] tied to 1'b0 means the stage is absent.
            av = AVAIL.get(v, {})
            for i in range(11):
                raw = r.get(f"bit{i}_cycles")
                if not av.get(str(i), True):
                    put(ws,f"{COLS[i+8]}{row}","n/a",fill=BAND)
                elif raw in (None,"","n/a"):
                    put(ws,f"{COLS[i+8]}{row}","-",fill=BAND)
                else:
                    put(ws,f"{COLS[i+8]}{row}",(int(raw)/cyc) if cyc else None,fmt="0.00%")
        row += 1
    row += 1
put(ws,f"B{row}","n/a = the variant has no such pipeline stage, determined from the "
                 "instrumented RTL (SIM_prof[bit] tied to 1'b0), not inferred from a zero "
                 "count.  Rendering these as 0 would read as 'never stalled'.",align="left")

# ------------------------------------------------- Embench full simulation set
emb = load("embench.csv")
benches = sorted({r["bench"] for r in emb})
ws = wb.create_sheet("Embench simulation")
widths(ws,[("A",3),("B",24)]+[(COLS[i+1],14) for i in range(len(benches))])
put(ws,"B2",f"Embench-IoT, all {len(benches)} benchmarks x 16 variants (RTL simulation)",
    bold=True,fill=HDR,align="left")
put(ws,"B3","Cycles.  Five of these were also measured on FPGA; see "
            "Research_data_Embench_0918-A.xlsx.  xgboost is absent from the FPGA set: at "
            "41-45 KB it exceeds the 32 KB instruction memory.",align="left",wrap=True)
ws.merge_cells(f"B3:{COLS[len(benches)]}3"); ws.row_dimensions[3].height = 28
row=5
put(ws,f"B{row}","variant",bold=True,fill=HDR,align="left")
for i,b in enumerate(benches): put(ws,f"{COLS[i+1]}{row}",b,bold=True,fill=HDR)
row+=1
FPGA5={"matmult-int","crc32","nettle-aes","statemate","md5sum"}
for v in VARIANTS:
    put(ws,f"B{row}",v,fill=BAND,align="left")
    for i,b in enumerate(benches):
        r=next((x for x in emb if x["variant"]==f"socs_{v}" and x["bench"]==b),None)
        if r and r["status"]=="ok":
            put(ws,f"{COLS[i+1]}{row}",int(r["cycles"]),fmt="#,##0",
                fill=GOOD if b in FPGA5 else None)
        else:
            put(ws,f"{COLS[i+1]}{row}","no result",fill=WARN)
    row+=1
put(ws,f"B{row+1}","green = also measured on FPGA.  'no result' = exceeded the 400M-cycle "
                   "simulation limit; a simulation-speed limit, not a functional failure.",align="left")

# ------------------------------------------------------------ core comparison
ext = load("extcore_summary.csv"); core = load("core_synth.csv")
ws = wb.create_sheet("Core comparison")
widths(ws,[("A",3),("B",30),("C",10),("D",10),("E",10),("F",10),("G",8),("H",8),("I",11),("J",11),("K",46)])
put(ws,"B2","Core-only synthesis against published soft cores",bold=True,fill=HDR,align="left")
put(ws,"B3","Identical methodology throughout: xc7a200tsbg484-1, a 5 ns constraint read "
            "BEFORE synthesis so the run is timing-driven, out-of-context so no I/O buffers "
            "count, core alone with memory at the boundary.  Fmax = 1000/(5 - WNS).",
    align="left",wrap=True)
ws.merge_cells("B3:K3"); ws.row_dimensions[3].height = 30
row=5
for i,l in enumerate(["core","ISA","LUT","logic","LUTRAM","FF","BRAM","DSP","WNS","Fmax","note"]):
    put(ws,f"{COLS[i]}{row}",l,bold=True,fill=HDR,align="left" if i in (0,10) else "right")
row+=1
NOTE={"picorv32":"ENABLE_MUL/DIV; multi-cycle multiplier in the ALU, hence 0 DSP",
      "rvcorep":"v0.5.3 default config; RV32I only -- compare against RV32I_5SP",
      "vexriscv":"GenFullNoMmuNoCache as shipped, includes DebugPlugin",
      "vexriscv_nodebug":"DebugPlugin removed: -80 LUT, -46 FF, Fmax unchanged"}
ISA={"picorv32":"RV32IM","rvcorep":"RV32I","vexriscv":"RV32IM","vexriscv_nodebug":"RV32IM"}
for e in ext:
    put(ws,f"B{row}",e["core"],fill=BAND,align="left")
    put(ws,f"C{row}",ISA.get(e["core"],""),align="left")
    for c,k in (("D","lut"),("E","lut_logic"),("F","lutram"),("G","ff"),("H","bram"),("I","dsp")):
        put(ws,f"{c}{row}",int(e[k]),fmt="#,##0")
    put(ws,f"J{row}",float(e["wns_ns"]),fmt="0.000")
    put(ws,f"K{row}",float(e["fmax_mhz"]),fmt="0.000")
    put(ws,f"L{row}",NOTE.get(e["core"],""),align="left")
    row+=1
row+=1
put(ws,f"B{row}","RV-IM100 cores, same constraint",bold=True,fill=HDR,align="left"); row+=1
for c in core:
    put(ws,f"B{row}",c["variant"],fill=BAND,align="left")
    put(ws,f"C{row}","RV32I" if c["variant"].endswith("I_5SP") and c["variant"].startswith("RV32")
        else ("RV64I" if c["variant"].endswith("I_5SP") else
              ("RV64IM" if c["variant"].startswith("RV64") else "RV32IM")),align="left")
    for col,k in (("D","lut"),("E","lut_logic"),("F","lutram"),("G","ff"),("H","bram"),("I","dsp")):
        put(ws,f"{col}{row}",int(float(c[k])),fmt="#,##0")
    put(ws,f"J{row}",float(c["wns_ns"]),fmt="0.000")
    put(ws,f"K{row}",float(c["fmax_mhz"]),fmt="0.000")
    row+=1
put(ws,f"B{row+1}","Frequency alone favours all three external cores and is misleading in "
                   "isolation: PicoRV32 is multi-cycle at a CPI near 4, so 182 MHz is not "
                   "182 MHz of work.  Pair with the CPI sheet.",align="left")

# ------------------------------------------------------------- SAIF breakdown
brk = load("saif_breakdown.csv"); sp = {(r["variant"],r["bench"]):r for r in load("saif_power.csv")}
ws = wb.create_sheet("SAIF detail")
widths(ws,[("A",3),("B",24),("C",11)]+[(COLS[i+2],10) for i in range(10)])
put(ws,"B2","Activity-based (SAIF) power, per component, all 32 SoC builds",bold=True,fill=HDR,align="left")
put(ws,"B3","Measured switching activity from post-implementation netlist simulation, not "
            "Vivado's assumed toggle rates.  Vivado prints '<0.001' for sub-milliwatt "
            "components; shown here as 0.000 and flagged in the last column.",align="left",wrap=True)
ws.merge_cells("B3:M3"); ws.row_dimensions[3].height = 30
row=5
for bench in ("dhrystone","coremark"):
    put(ws,f"B{row}",bench,bold=True,fill=HDR,align="left")
    for i,l in enumerate(["total W","dynamic","clocks","signals","logic","BRAM","DSP","PLL","I/O","static","toggling","<1mW"]):
        put(ws,f"{COLS[i+1]}{row}",l,bold=True,fill=HDR)
    row+=1
    for v in VARIANTS:
        r=next((x for x in brk if x["variant"]==v and x["bench"]==bench),None)
        put(ws,f"B{row}",v,fill=BAND,align="left")
        if r:
            g=lambda k: float(r[k] or 0)
            dyn=sum(g(x) for x in ("p_clocks","p_signals","p_logic","p_bram","p_dsp","p_pll","p_io"))
            for col,val in (("C",g("p_total")),("D",round(dyn,4)),("E",g("p_clocks")),
                            ("F",g("p_signals")),("G",g("p_logic")),("H",g("p_bram")),
                            ("I",g("p_dsp")),("J",g("p_pll")),("K",g("p_io")),("L",g("p_static"))):
                put(ws,f"{col}{row}",val,fmt="0.000")
            s=sp.get((v,bench))
            if s: put(ws,f"M{row}",float(s["toggling_pct"])/100,fmt="0.0%")
            put(ws,f"N{row}",r["below_1mW"] or "",align="left")
        row+=1
    row+=1

# --------------------------------------------------------------- verification
ws = wb.create_sheet("Verification")
widths(ws,[("A",3),("B",24),("C",10),("D",12),("E",12),("F",12),("G",12),("H",12),("I",40)])
put(ws,"B2","Functional verification evidence",bold=True,fill=HDR,align="left")
row=4
riscof = []
for f in ("results_socs.csv","results.csv"):
    p=ENV/f
    if p.exists(): riscof=list(csv.DictReader(p.open())); break
rv=collections.defaultdict(collections.Counter)
for r in load("rvtests_results.csv"): rv[r["variant"]][r["status"]]+=1
embv=collections.defaultdict(collections.Counter)
for r in emb: embv[r["variant"]][r["status"]]+=1
aapg=collections.defaultdict(collections.Counter)
for r in load("aapg_results.csv"): aapg[r["variant"]][r["status"]]+=1
for i,l in enumerate(["variant","RISCOF","riscv-tests","Embench sim","randomized (AAPG)","note"]):
    put(ws,f"{COLS[i]}{row}",l,bold=True,fill=HDR,align="left" if i in (0,5) else "right")
row+=1
for v in VARIANTS:
    put(ws,f"B{row}",v,fill=BAND,align="left")
    rf=[r for r in riscof if r.get("variant","").endswith(v)]
    if rf:
        p=sum(int(r["passed"]) for r in rf); t=sum(int(r["total"]) for r in rf)
        put(ws,f"C{row}",f"{p}/{t}",fill=GOOD if p==t else BAD)
    k=f"socs_{v}"
    if k in rv:
        p=rv[k]["PASS"]; t=sum(rv[k].values())
        put(ws,f"D{row}",f"{p}/{t}",fill=GOOD if p==t else WARN)
    if k in embv:
        p=embv[k]["ok"]; t=sum(embv[k].values())
        put(ws,f"E{row}",f"{p}/{t}",fill=GOOD if p==t else WARN)
    if k in aapg:
        c=aapg[k]; t=sum(c.values())
        note=[]
        if c["TIMEOUT"]: note.append(f"{c['TIMEOUT']} timeout")
        if c["MISMATCH"]: note.append(f"{c['MISMATCH']} mismatch")
        put(ws,f"F{row}",f"{c['MATCH']}/{t}",fill=GOOD if c["MATCH"]==t else WARN)
        put(ws,f"G{row}","; ".join(note),align="left")
    row+=1
row+=1
for t in ["riscv-tests shortfalls are ma_data only, which is optional in RISC-V.",
          "Embench 'no result' rows hit the simulation cycle limit, not a functional failure.",
          "Randomized testing has two distinct failure modes, and they do not mean the same thing:",
          "  MISMATCH is dominated by a co-simulation artifact.  The DUT runs from ROM at 0x00000000 and the",
          "  Sail reference from 0x80000000, so signature words holding address fragments differ by construction.",
          "  The harness excludes words it can prove are link-address dependent by re-running Sail at shifted",
          "  bases; after widening that probe, matches rose from 49 to 136 of 320 and 37 of the 57 remaining",
          "  mismatches differ by a single word in 4096.  On RV32 the effect is far stronger because 0x80000000",
          "  is negative as a signed 32-bit value, which is why RV64IM reaches 19/20 and RV32 reaches 7/20.",
          "  TIMEOUT is a real divergence and is NOT an artifact.  It appears only on the 7- and 8-stage",
          "  variants, at both widths.  rv32im_s004 completes on RV32IM_5SP in 83,767 cycles and does not",
          "  terminate on RV32IM_7SP within 20,000,000: the branch guarding the loop exit is not taken, and",
          "  nothing in the loop body writes the register it tests.  Not reached by RISCOF, riscv-tests,",
          "  any Embench benchmark, or either FPGA benchmark.  Under investigation; affects no reported result.",
          "Randomized testing found two defects during development that are now fixed: a 7SP_BRAM branch bug",
          "and an 8SP divw bug, both reproducible from aapg-env/repro/."]:
    put(ws,f"B{row}",t,align="left"); row+=1

# ------------------------------------------------------- normalized metrics
nm = load("normalized_metrics.csv")
if nm:
    ws = wb.create_sheet("Normalized metrics")
    widths(ws,[("A",3),("B",24)]+[(COLS[i+1],14) for i in range(11)])
    put(ws,"B2","Throughput, area and energy efficiency",bold=True,fill=HDR,align="left")
    put(ws,"B3","CoreMark score is CoreMarks/MHz x the run frequency, NOT Fmax.  Area ratios use the "
                "core-only LUT count, which excludes memory and is comparable across variants; the SoC "
                "column is given for reference and is not.  Energy per iteration is total on-chip power "
                "(SAIF dynamic + static) divided by measured iterations per second.",align="left",wrap=True)
    ws.merge_cells("B3:L3"); ws.row_dimensions[3].height = 42
    r=5
    for i,l in enumerate(["variant","run MHz","CoreMark","CM/MHz","DMIPS/MHz","CM/LUT core",
                          "CM/LUT SoC","DMIPS/LUT","total W","CM/W","mJ/iter","iters/s"]):
        put(ws,f"{COLS[i]}{r}",l,bold=True,fill=HDR,align="left" if i==0 else "right")
    r+=1
    for d in nm:
        put(ws,f"B{r}",d["variant"],fill=BAND,align="left")
        for col,key,fmt in (("C","clock_mhz","0.000###"),("D","coremark_score","0.0"),
                            ("E","coremarks_per_mhz","0.000"),("F","dmips_per_mhz","0.000"),
                            ("G","coremark_per_lut_core","0.00000"),("H","coremark_per_lut_soc","0.00000"),
                            ("I","dmips_per_lut_core","0.000000"),("J","saif_total_w","0.000"),
                            ("K","coremark_per_watt","0.0"),("L","energy_per_iteration_mJ","0.0000"),
                            ("M","iterations_per_sec","#,##0")):
            v=d.get(key)
            if v not in (None,""): put(ws,f"{col}{r}",float(v),fmt=fmt)
        r+=1

# ------------------------------------------------------- clocking resources
ck = load("clocking_resources.csv")
if ck:
    ws = wb.create_sheet("Clocking resources")
    widths(ws,[("A",3),("B",24),("C",12),("D",14),("E",14),("F",14),("G",40)])
    put(ws,"B2","Clocking primitives per SoC build",bold=True,fill=HDR,align="left")
    put(ws,"B3","Every build uses a PLLE2_ADV, not an MMCM: MMCME2_ADV is zero throughout.  Worth "
                "stating precisely, since the two are often used interchangeably in text.",align="left",wrap=True)
    ws.merge_cells("B3:G3"); ws.row_dimensions[3].height = 28
    r=5
    for i,l in enumerate(["variant","benchmark","BUFGCTRL","MMCME2_ADV","PLLE2_ADV"]):
        put(ws,f"{COLS[i]}{r}",l,bold=True,fill=HDR,align="left" if i<2 else "right")
    r+=1
    for d in ck:
        put(ws,f"B{r}",d["variant"],fill=BAND,align="left")
        put(ws,f"C{r}",d["bench"],align="left")
        for col,key in (("D","bufgctrl"),("E","mmcme2"),("F","plle2")):
            put(ws,f"{col}{r}",int(d[key]))
        r+=1

# --------------------------------------------------------------------- notes
ws = wb.create_sheet("Notes")
ws.column_dimensions["B"].width = 118
lines = [
 f"Research_data_Final_0921.xlsx   built {datetime.date.today().isoformat()}",
 "",
 "SCOPE",
 "  Everything measured for the revision that is not already in:",
 "    Research_data_FPGA_0917-A.xlsx     SoC and core synthesis, CoreMark/Dhrystone FPGA",
 "    Research_data_Embench_0918-A.xlsx  Embench FPGA (RV64 complete, RV32 pending)",
 "",
 "SHEETS",
 "  CPI and stalls       Per-variant CPI, IPC, branch frequency, misprediction rate and an",
 "                       11-counter stall breakdown, for both benchmarks.  Simulation-derived;",
 "                       the FPGA runs validate it exactly (40/40 RV64 rows).",
 "  Embench simulation   Full 19 x 16 matrix.  Five benchmarks, shown green, were also run on",
 "                       FPGA.  xgboost exceeds the 32 KB instruction memory on every variant.",
 "  Core comparison      PicoRV32, RVCoreP and VexRiscv against the RV-IM100 cores, identical",
 "                       synthesis methodology.  See comparison_cores/PROVENANCE.md.",
 "  SAIF detail          Per-component activity-based power for all 32 SoC builds.",
 "  Verification         RISCOF, riscv-tests and Embench pass counts per variant.",
 "",
 "NOT IN THIS WORKBOOK",
 "  Embench RV32 FPGA results.  The original runs used a harness that read a 64-bit counter",
 "  with a single csrr; on RV32 that fills only the low half of a register pair, so cycle",
 "  counts came back inflated by 2^32 or worse.  The harness is fixed and all 40 RV32",
 "  bitstreams rebuilt, but the board runs have not been repeated.  Left blank deliberately",
 "  rather than filled with the superseded numbers.",
 "",
 "CAVEATS THAT MUST REACH THE PAPER",
 "  - RVCoreP is RV32I, not RV32IM.  Compare it against RV32I_5SP, not the IM variants.",
 "  - VexRiscv GenFullNoMmuNoCache ships with DebugPlugin, which no other core here has.",
 "    Both figures are given; the no-debug one is the like-for-like comparison.",
 "  - Stall percentages show n/a where a variant lacks that pipeline stage.  Rendering those",
 "    as 0 would read as 'never stalled'.",
 "  - SAIF power describes the SoC builds running CoreMark and Dhrystone.  No SAIF capture",
 "    exists for the Embench images.",
 "  - Toggling coverage ranges 23.7% to 74.7%.  The lowest, RV64IM_8SP/coremark, was",
 "    re-captured with a 5x longer window: coverage held at 23.8% and power moved 0.180 to",
 "    0.182 W, so it reflects genuinely low activity rather than an unrepresentative window.",
]
for i,t in enumerate(lines, start=2):
    c=ws[f"B{i}"]; c.value=t
    c.font=Font(name=F,size=11,bold=t.isupper() and bool(t.strip()))
    c.alignment=Alignment(horizontal="left",vertical="center")

wb.save(DST)
print(f"  wrote {DST}")
print(f"  sheets: {wb.sheetnames}")
