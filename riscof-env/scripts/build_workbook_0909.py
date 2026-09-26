#!/usr/bin/env python3
"""Build ~/Documents/Research_data_complete_0909.xlsx from the measurement CSVs.

A clean rebuild, not a patch of the inherited layout.  One status column per SoC
row carries the timing verdict in both text and colour, so the sheet can be
scanned without reading notes:

    (no fill)  timing met, less than 1 MHz of headroom -- nothing to do
    blue       timing met but closes >1 MHz above its clock -> build a faster .mem
    red        timing VIOLATION: negative setup slack at the configured clock
    yellow     not measured, or needs checking

The core block is deliberately uncoloured: every variant has negative slack at
the shared 5 ns constraint by construction (none targets 200 MHz), so a red
there would mean nothing.
"""
import csv, json, pathlib
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

ENV = pathlib.Path(__file__).resolve().parent.parent
DST = pathlib.Path.home() / "Documents" / "Research_data_complete_0909.xlsx"
L   = ENV / "logs"

load = lambda n: {r["variant"]: r for r in csv.DictReader((L / n).open())}
core, pre, post = load("core_synth.csv"), load("soc_preswap.csv"), load("soc_postswap.csv")
bench = load("fpga_benchmarks.csv")
plan  = {p["variant"]: p for p in json.load((L / "swap_plan.json").open())}

ORDER = {
    "RV32": ["RV32I_5SP", "RV32IM_5SP", "RV32IM_6SP", "RV32IM_7SP", "RV32IM_7SP_BRAM",
             "RV32IM_7SP_BRAM_Opt", "RV32IM_8SP_withoutOpt", "RV32IM_8SP"],
    "RV64": ["RV64I_5SP", "RV64IM_5SP", "RV64IM_6SP", "RV64IM_7SP", "RV64IM_7SP_BRAM",
             "RV64IM_7SP_BRAM_Opt", "RV64IM_8SP_withoutOpt", "RV64IM_8SP"],
}
NONE   = PatternFill(fill_type=None)
BLUE   = PatternFill("solid", fgColor="BDD7EE")
RED    = PatternFill("solid", fgColor="FFC7CE")
YELLOW = PatternFill("solid", fgColor="FFEB9C")

HEAD_FILL = PatternFill("solid", fgColor="404040")
SEC_FILL  = PatternFill("solid", fgColor="D9E1F2")
HEAD_FONT = Font(bold=True, color="FFFFFF", size=10)
SEC_FONT  = Font(bold=True, size=11)
thin  = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

f = lambda v: None if v in (None, "", "None") else float(v)
i = lambda v: None if v in (None, "", "None") else int(float(v))


def classify(clk, wns, fmax):
    """-> (status text, fill).  Timing decides the colour; headroom refines it."""
    if wns is None or fmax is None:
        return "not measured", YELLOW
    if wns < 0:
        return f"VIOLATION {wns:+.3f} ns", RED
    head = fmax - clk
    if head > 1.0:
        return f"+{head:.2f} MHz headroom", BLUE
    return "OK", NONE


BAUD = {"RV64IM_7SP_BRAM_Opt": (84.0, 83.0, 729, 720),
        "RV32IM_7SP": (58.0, 50.0, 503, 434),
        "RV32IM_7SP_BRAM_Opt": (90.90909, 90.0, 789, 781)}


def soc_memo(v, src, clk, wns, fmax, head, fill):
    """Compact per-row memo, in the phrasing used by the 0908 workbook."""
    what = ("measured 2026-09-08 on the fully-verified RTL"
            if src["measured"] == "2026-09-08"
            else "re-impl + re-measured 2026-09-09 after the benchmark swap")
    m = (f"{what}; image {src['image']}; core clock {src['core_clk']} constrained "
         f"{clk:g} MHz, WNS {wns:+.3f} ns")
    if v in BAUD and src["measured"] == "2026-09-09":
        of, nf, ob, nb = BAUD[v]
        m += f"; clock moved {of:g}->{nf:g} MHz, BAUD_DIV {ob}->{nb}"
    if fill is RED:
        m += (f"  ||  TIMING NOT MET at {clk:g} MHz (WNS {wns:+.3f} ns) - the design only "
              f"closes at {fmax:.2f} MHz; needs a slower image or re-timing")
    elif fill is BLUE:
        m += (f"  ||  HEADROOM +{head:.2f} MHz - runs at {clk:g} MHz but closes at "
              f"{fmax:.2f} MHz; a faster .mem image is worth building")
    return m


SOC_COLS = [("variant", 22), ("status", 20), ("clock MHz", 10), ("WNS ns", 9),
            ("Fmax MHz", 10), ("headroom MHz", 13), ("image", 32), ("LUT", 8),
            ("LUTRAM", 8), ("FF", 7), ("BRAM", 6), ("DSP", 5), ("IO", 5), ("PLL", 5),
            ("power W", 9), ("dynamic W", 10), ("static W", 9), ("result", 11),
            ("per MHz", 18), ("measured", 11), ("implementation memo", 96)]
# The core block and the SoC blocks share physical columns, so a width set for one
# applies to the other.  Pad the core layout so its memo lands in the SAME column as
# the SoC memo; otherwise the core memo inherits the width of the SoC "PLL" column
# (5 chars) and its row expands to fill the screen.
CORE_COLS = ([("variant", 22), ("Fmax MHz", 10), ("WNS ns @5ns", 12), ("LUT", 8),
              ("LUT as logic", 12), ("LUTRAM", 8), ("FF", 7), ("BRAM", 6), ("DSP", 5),
              ("power W", 9), ("dynamic W", 10), ("static W", 9), ("core top", 24)]
             + [("", 9)] * (len(SOC_COLS) - 14)
             + [("implementation memo", 96)])
assert len(CORE_COLS) == len(SOC_COLS), (len(CORE_COLS), len(SOC_COLS))


def header(ws, row, cols):
    for c, (name, _) in enumerate(cols, 1):
        if not name:                      # padding column in the core layout
            continue
        cell = ws.cell(row=row, column=c, value=name)
        cell.fill, cell.font = HEAD_FILL, HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = 26


def section(ws, row, text, width):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=width)
    cell = ws.cell(row=row, column=1, value=text)
    cell.fill, cell.font = SEC_FILL, SEC_FONT
    cell.alignment = Alignment(vertical="center")
    ws.row_dimensions[row].height = 22


wb = openpyxl.Workbook()
wb.remove(wb.active)
summary = {"blue": [], "red": [], "yellow": []}

for fam in ("RV32", "RV64"):
    ws = wb.create_sheet(fam)
    ws["A1"] = f"RV-IM100 — {fam} implementation results"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = ("Fmax is measured on the CORE clock as 1000/(period − WNS); the 100 MHz board "
                "clock is not the CPU clock. Power is Vivado vectorless (no SAIF).")
    ws["A2"].font = Font(italic=True, size=9)
    ws.merge_cells("A2:T2")

    # ---------------- core-only synthesis ----------------
    r = 4
    section(ws, r, "CORE-ONLY SYNTHESIS — memory externalised, every variant at the same "
                   "5 ns (200 MHz) constraint. Use THIS block for area comparisons.",
            len(CORE_COLS))
    r += 1
    header(ws, r, CORE_COLS)
    core_hdr = r
    for v in ORDER[fam]:
        r += 1
        d = core[v]
        vals = [v, f(d["fmax_mhz"]), f(d["wns_ns"]), i(d["lut"]), i(d["lut_logic"]),
                i(d["lutram"]), i(d["ff"]), i(d["bram"]), i(d["dsp"]),
                f(d["p_total"]), round(f(d["p_total"]) - f(d["p_static"]), 3),
                f(d["p_static"]), d["top"]] + [None] * (len(SOC_COLS) - 14) + [
                (f"core-only re-synth 2026-09-08 on the fully-verified RTL; top "
                 f"{d['top']}; all variants at the same {f(d['constraint_mhz']):g} MHz (5 ns) "
                 f"constraint, WNS {f(d['wns_ns']):+.3f} ns; memory externalised so area "
                 f"excludes ROM/RAM; power is POST-SYNTHESIS (routing estimated) and is NOT "
                 f"comparable to the SoC post-route power below")]
        for c, val in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.border = BORDER
        ws.cell(row=r, column=len(CORE_COLS)).alignment = Alignment(
            wrap_text=True, vertical="top")

    # ---------------- the two SoC blocks ----------------
    for bench_name, key_result, key_permhz in (
            ("DHRYSTONE", "dhrystones_per_sec", "dmips_per_mhz"),
            ("COREMARK",  "iterations_per_sec", "coremarks_per_mhz")):
        r += 2
        section(ws, r, f"SoC — {bench_name}   (each project holds one image; measured with "
                       f"the image named in the row)", len(SOC_COLS))
        r += 1
        header(ws, r, SOC_COLS)
        for v in ORDER[fam]:
            r += 1
            # pick whichever pass ran this benchmark on this variant
            src = None
            for cand in (pre.get(v), post.get(v)):
                if cand and cand["image"].startswith(bench_name.lower()):
                    src = cand
            if src is None:
                status, fill = "not measured", YELLOW
                note = (f"no {bench_name.lower()} image exists at or below this variant's "
                        f"Fmax, so it has never run this benchmark")
                vals = ([v, status] + [None] * 4 + ["— " + note] + [None] * 13
                        + ["NOT measured - no image for this benchmark exists at or below this variant's Fmax, so it has never run this benchmark on the fixed RTL"])
                summary["yellow"].append((fam, v, bench_name, note))
            else:
                clk, wns, fmax = (f(src["constraint_mhz"]), f(src["wns_ns"]),
                                  f(src["fmax_mhz"]))
                status, fill = classify(clk, wns, fmax)
                head = None if fmax is None else round(fmax - clk, 2)
                b = bench.get(v, {})
                vals = [v, status, clk, wns, fmax, head, src["image"],
                        i(src["lut"]), i(src["lutram"]), i(src["ff"]), i(src["bram"]),
                        i(src["dsp"]), i(src["io"]), i(src["pll"]),
                        f(src["p_static"]) + sum(f(src[k]) for k in
                            ("p_clocks", "p_signals", "p_logic", "p_bram", "p_dsp",
                             "p_pll", "p_io")),
                        round(sum(f(src[k]) for k in ("p_clocks", "p_signals", "p_logic",
                              "p_bram", "p_dsp", "p_pll", "p_io")), 3),
                        f(src["p_static"]),
                        b.get(key_result), b.get(key_permhz), src["measured"],
                        soc_memo(v, src, clk, wns, fmax, head, fill)]
                if fill is RED:
                    summary["red"].append((fam, v, bench_name, clk, fmax))
                elif fill is BLUE:
                    summary["blue"].append((fam, v, bench_name, clk, fmax, head))
            for c, val in enumerate(vals, 1):
                cell = ws.cell(row=r, column=c, value=val)
                cell.border = BORDER
            ws.cell(row=r, column=len(SOC_COLS)).alignment = Alignment(
                wrap_text=True, vertical="top")
            ws.cell(row=r, column=2).fill = fill
            ws.cell(row=r, column=2).font = Font(bold=(fill is not NONE), size=10)
            ws.cell(row=r, column=5).fill = fill

    # ---------------- legend ----------------
    r += 3
    ws.cell(row=r, column=1, value="LEGEND — status column").font = Font(bold=True, size=11)
    for text, fill, meaning in (
            ("OK", NONE, "timing met, less than 1 MHz of headroom — nothing to do"),
            ("+n MHz headroom", BLUE, "timing met but the design closes more than 1 MHz above "
                                      "its clock — a faster .mem image is worth building"),
            ("VIOLATION", RED, "negative setup slack at the configured clock — needs a slower "
                               "image or re-timing; the Fmax column gives what it does close at"),
            ("not measured", YELLOW, "no result for this variant/benchmark pair — see the "
                                     "image column for why")):
        r += 1
        c = ws.cell(row=r, column=1, value=text)
        c.fill, c.border = fill, BORDER
        c.font = Font(bold=True, size=10)
        ws.cell(row=r, column=2, value=meaning)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=len(SOC_COLS))

    r += 2
    for note in (
        "Core block is uncoloured on purpose: every variant has negative slack at the shared "
        "5 ns constraint by construction (none targets 200 MHz), so a red there would be "
        "meaningless. That block exists to compare variants at an identical constraint.",
        "SoC LUT totals are NOT comparable across variants — the 5SP/6SP designs hold ROM/RAM "
        "in LUTRAM, the BRAM/8SP designs in block RAM. Compare area using the core block.",
        "The benchmark image changes timing only on LUTRAM designs, where the ROM is logic. On "
        "BRAM designs it is only block-RAM initialisation: RV32IM_8SP and RV32IM_8SP_withoutOpt "
        "returned bit-identical results for both benchmarks.",
        "RV64IM_8SP has no MMCM — it is clocked directly by the 100 MHz board pin.",
        "Power categories are printed by Vivado at 3 dp, so the dynamic + static columns can "
        "differ from its reported total by up to 2 mW.",
    ):
        r += 1
        ws.cell(row=r, column=1, value="• " + note).alignment = Alignment(
            wrap_text=True, vertical="top")
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(SOC_COLS))
        ws.row_dimensions[r].height = 30

    for idx, (a, b) in enumerate(zip(SOC_COLS, CORE_COLS), 1):
        ws.column_dimensions[get_column_letter(idx)].width = max(a[1], b[1])
    ws.freeze_panes = ws.cell(row=core_hdr + 1, column=2)
    # explicit per-column formats: a heuristic on magnitude makes one column show
    # both "-14.50" and "0.052", which is exactly the kind of mess being fixed here
    CORE_FMT = {2: "0.000", 3: "0.000", 10: "0.000", 11: "0.000", 12: "0.000"}
    SOC_FMT  = {3: "0.000", 4: "0.000", 5: "0.000", 6: "+0.00;-0.00;0.00",
                15: "0.000", 16: "0.000", 17: "0.000"}
    for row in ws.iter_rows():
        for cell in row:
            if not isinstance(cell.value, float):
                continue
            fmt = CORE_FMT.get(cell.column) if cell.row <= core_hdr + 8 \
                  else SOC_FMT.get(cell.column)
            cell.number_format = fmt or "0.000"

wb.save(DST)
print(f"wrote {DST}")
print(f"  sheets: {wb.sheetnames}")
print(f"  red (violation)     {len(summary['red'])}")
for x in sorted(summary["red"], key=lambda t: t[4] - t[3]):
    print(f"      {x[0]} {x[1]:<23} {x[2]:<10} runs {x[3]:>8} closes {x[4]:>7.2f}")
print(f"  blue (headroom)     {len(summary['blue'])}")
for x in sorted(summary["blue"], key=lambda t: -t[5]):
    print(f"      {x[0]} {x[1]:<23} {x[2]:<10} runs {x[3]:>8} closes {x[4]:>7.2f}  +{x[5]:.2f}")
print(f"  yellow (unmeasured) {len(summary['yellow'])}")
for x in summary["yellow"]:
    print(f"      {x[0]} {x[1]:<23} {x[2]}")
