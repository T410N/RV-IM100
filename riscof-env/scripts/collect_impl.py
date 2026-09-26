#!/usr/bin/env python3
"""Collect post-implementation results for the SoCs projects.

Reads the uniform reports written by scripts/gen_reports_all.sh into
logs/impl_reports/<project>/ -- regenerated from each routed design so every
variant is measured the same way, rather than relying on whatever report set
each run's strategy happened to emit.

The SoC clock is the clock the core actually runs on: the clock-wizard output
where the SoC instantiates one, otherwise the board clock.  Fmax is
1 / (period - setup WNS) for that clock.  Each project keeps its own ROM image,
so the benchmark in the bitstream is read back from Instruction_Memory.v.
"""
import os
import re
import sys

ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = os.path.abspath(os.path.join(ENV, "..", "RV-IM100_RTL", "project_files"))
RPTS = os.path.join(ENV, "logs", "impl_reports")

ORDER = [
    ("RV32s", "RV32I_5SP"), ("RV32s", "RV32IM_5SP"), ("RV32s", "RV32IM_6SP"),
    ("RV32s", "RV32IM_7SP"), ("RV32s", "RV32IM_7SP_BRAM"),
    ("RV32s", "RV32IM_7SP_BRAM_Opt"), ("RV32s", "RV32IM_8SP"),
    ("RV32s", "RV32IM_8SP_withoutOpt"),
    ("RV64s", "RV64I5SP_SoC"), ("RV64s", "RV64IM_5SP"), ("RV64s", "RV64IM_6SP"),
    ("RV64s", "RV64IM_7SP"), ("RV64s", "RV64IM_7SP_BRAM"),
    ("RV64s", "RV64IM_7SP_BRAM_Opt"), ("RV64s", "RV64IM_8SP"),
    ("RV64s", "RV64IM_8SP_withoutOpt"),
]


def cell(line, idx=2):
    parts = [c.strip() for c in line.split("|")]
    try:
        return float(parts[idx])
    except (IndexError, ValueError):
        return None


def util(path):
    rows = {"lut": r"^\|\s*Slice LUTs", "lutram": r"^\|\s*LUT as Memory",
            "ff": r"^\|\s*Slice Registers", "bram": r"^\|\s*Block RAM Tile",
            "dsp": r"^\|\s*DSPs", "io": r"^\|\s*Bonded IOB"}
    out = dict.fromkeys(rows, 0.0)
    out["pll"] = 0.0
    # Clocking primitives are listed twice: once in section 6 "Clocking" with
    # their real counts, and again in section 8 "Primitives" as a census.
    # Only the Clocking section counts, or every design reports twice its PLLs.
    in_clocking = False
    seen = set()
    for line in open(path, errors="ignore"):
        if re.match(r"^\d+\. ", line):
            in_clocking = line.startswith("6. Clocking")
        for k, pat in rows.items():
            if not out[k] and re.match(pat, line):
                v = cell(line)
                if v is not None:
                    out[k] = v
        m = re.match(r"^\|\s*(MMCME2_ADV|PLLE2_ADV)\s*\|", line)
        if in_clocking and m and m.group(1) not in seen:
            seen.add(m.group(1))
            v = cell(line)
            if v:
                out["pll"] += v
    return out


def power(path):
    labels = {"clocks": "Clocks", "logic": "Slice Logic", "signals": "Signals",
              "bram": "Block RAM", "dsp": "DSPs", "pll": "PLL", "io": "I/O",
              "static": "Static Power", "total": "Total"}
    out = dict.fromkeys(labels, 0.0)
    lines = open(path, errors="ignore").read().splitlines()
    # the heading appears twice -- once in the table of contents, once as the
    # real section, which is the one followed by a dashed underline
    start = next((i for i, l in enumerate(lines)
                  if l.startswith("1.1 On-Chip Components")
                  and i + 1 < len(lines) and lines[i + 1].startswith("---")), None)
    if start is None:
        return out
    sec = True
    for line in lines[start + 1:]:
        if line.startswith("1.2 "):
            break
        m = re.match(r"^\|\s{0,2}([A-Za-z][^|]*?)\s*\|\s*(<?[\d.]+)\s*\|", line)
        if sec and m:
            name, raw = m.group(1).strip(), m.group(2)
            v = 0.0 if raw.startswith("<") else float(raw)
            for k, lab in labels.items():
                if name == lab:
                    out[k] = v
    return out


def intra_clock(path):
    """clock -> (setup WNS, setup endpoints); the table indents nested clocks."""
    res, sec = {}, False
    for line in open(path, errors="ignore"):
        if "Intra Clock Table" in line:
            sec = True
            continue
        if sec and "Inter Clock Table" in line:
            break
        m = re.match(r"^\s*(\S+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(\d+)\s+(\d+)\s", line)
        if sec and m and not m.group(1).startswith("-"):
            res[m.group(1)] = (float(m.group(2)), int(m.group(5)))
    return res


def clocks(path):
    per, gen = {}, {}
    for line in open(path, errors="ignore"):
        m = re.match(r"CLOCK (\S+) period=([\d.]+) generated=(\d)", line)
        if m:
            per[m.group(1)] = float(m.group(2))
            gen[m.group(1)] = m.group(3) == "1"
    return per, gen


def benchmark(fam, proj):
    base = os.path.join(REPO, fam, "SoCs", proj)
    for root, _d, files in os.walk(base):
        if ".srcs" not in root or "archive" in root.lower():
            continue
        if "Instruction_Memory.v" in files:
            txt = open(os.path.join(root, "Instruction_Memory.v"), errors="ignore").read()
            m = re.search(r'\$readmemh\s*\(\s*"\./([^"]+)"', txt)
            if m:
                f = m.group(1)
                low = f.lower()
                return ("CoreMark" if "coremark" in low else
                        "Dhrystone" if "dhrystone" in low else "?"), f
    return "?", "?"


def main():
    rows = []
    for fam, proj in ORDER:
        d = os.path.join(RPTS, proj)
        need = [os.path.join(d, f) for f in ("utilization.rpt", "power.rpt",
                                             "timing.rpt", "clocks.txt")]
        if not all(os.path.isfile(x) for x in need):
            rows.append((fam, proj, None))
            continue
        U, P = util(need[0]), power(need[1])
        ic = intra_clock(need[2])
        per, gen = clocks(need[3])
        # prefer a generated (clock-wizard) clock that actually carries paths
        cands = {c: v for c, v in ic.items() if v[1] > 0}
        soc = None
        for c in cands:
            if gen.get(c) and "clkfbout" not in c:
                soc = c
                break
        if soc is None and cands:
            soc = max(cands, key=lambda c: cands[c][1])
        wns = cands[soc][0] if soc else None
        period = per.get(soc)
        fmax = 1000.0 / (period - wns) if (period and wns is not None) else None
        b, img = benchmark(fam, proj)
        rows.append((fam, proj, dict(u=U, p=P, clk=soc, wns=wns, period=period,
                                     fmax=fmax, bench=b, img=img)))

    W = 128
    print("=" * W)
    print("UTILIZATION  (post-implementation, xc7a200tsbg484-1)")
    print("=" * W)
    print("%-6s %-22s %-10s %8s %8s %8s %6s %5s %5s %5s" %
          ("FAM", "PROJECT", "BENCHMARK", "LUT", "LUTRAM", "FF", "BRAM", "DSP", "IO", "PLL"))
    print("-" * W)
    for fam, proj, r in rows:
        if not r:
            print("%-6s %-22s %s" % (fam, proj, "-- skipped / no results --"))
            continue
        u = r["u"]
        print("%-6s %-22s %-10s %8d %8d %8d %6g %5g %5g %5g" %
              (fam, proj, r["bench"], u["lut"], u["lutram"], u["ff"],
               u["bram"], u["dsp"], u["io"], u["pll"]))

    print("\n" + "=" * W)
    print("TIMING   SoC Fmax = 1 / (PLL-set period - setup WNS)")
    print("=" * W)
    print("%-6s %-22s %-20s %10s %10s %10s  %s" %
          ("FAM", "PROJECT", "SoC CLOCK", "SET MHz", "WNS ns", "Fmax MHz", ""))
    print("-" * W)
    for fam, proj, r in rows:
        if not r:
            continue
        if r["wns"] is None or r["period"] is None:
            print("%-6s %-22s %-20s %s" % (fam, proj, r["clk"] or "?", "no timing data"))
            continue
        print("%-6s %-22s %-20s %10.2f %10.3f %10.2f  %s" %
              (fam, proj, r["clk"], 1000.0 / r["period"], r["wns"], r["fmax"],
               "" if r["wns"] >= 0 else "TIMING NOT MET"))

    print("\n" + "=" * W)
    print("POWER (W)  post-route, vectorless")
    print("=" * W)
    print("%-6s %-22s %7s %8s %7s %7s %7s %7s %7s %8s %8s" %
          ("FAM", "PROJECT", "Clocks", "Signals", "Logic", "BRAM", "DSP",
           "PLL", "I/O", "Static", "TOTAL"))
    print("-" * W)
    for fam, proj, r in rows:
        if not r:
            continue
        p = r["p"]
        print("%-6s %-22s %7.3f %8.3f %7.3f %7.3f %7.3f %7.3f %7.3f %8.3f %8.3f" %
              (fam, proj, p["clocks"], p["signals"], p["logic"], p["bram"],
               p["dsp"], p["pll"], p["io"], p["static"], p["total"]))

    print("\nROM image per project (which benchmark is in the bitstream):")
    for fam, proj, r in rows:
        if r:
            print("  %-22s %s" % (proj, r["img"]))


if __name__ == "__main__":
    main()
