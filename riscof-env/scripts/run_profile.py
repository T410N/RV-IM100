#!/usr/bin/env python3
"""Cycle-accurate profiling across the RV-IM100 variants.

Answers the reviewers' request for dynamic instruction counts, CPI/IPC,
branch frequency, misprediction counts and a stall-cycle breakdown
(load-use, execution-use, mul/div).

The counters live in the simulation wrapper, not in the core, so nothing
measured here can affect synthesis, timing or area -- the RTL that produced
the Fmax and power numbers is the RTL being profiled.

Instruction-mix counts are decoded from the retired instruction word, so they
mean the same thing on every pipeline depth.  Stall counts necessarily come
from each variant's own signals; stages a variant does not have are reported
as n/a rather than zero, because zero would read as "never stalled".

A NOP is excluded from the retired count, matching the cores' own minstret
definition.  State that in the paper: it shifts IPC slightly against a
Sail-counted instruction total.

Usage:
    scripts/run_profile.py <program.hex> [--variants v1 v2 ...] [--csv out.csv]
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import all_variants  # noqa: E402

ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

LABELS = ["branch mispred", "pc stall", "front-end stall", "ID/EX stall",
          "EXR/EX stall", "EX/EX2 stall", "EX/MEM stall", "MEM/WB stall",
          "load-use hazard", "divider busy", "multiplier busy"]


def read_prof(path):
    d = {}
    for line in open(path):
        p = line.split()
        if len(p) == 2:
            d[p[0]] = int(p[1])
        elif len(p) == 4:
            d[p[0]] = int(p[1]); d[p[2]] = int(p[3])
    return d


def available(variant, bit):
    """Whether this variant actually has the signal behind a profile bit."""
    import glob, re
    for f in glob.glob(os.path.join(ENV, "build", variant, "rtl", "RV*.v")):
        for line in open(f):
            m = re.match(r"\s*assign SIM_prof\[\s*%d\]\s*=\s*(\S+?);" % bit, line)
            if m:
                return m.group(1) != "1'b0"
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hexfile")
    ap.add_argument("--variants", nargs="*")
    ap.add_argument("--max-cycles", type=int, default=200_000_000)
    ap.add_argument("--csv")
    args = ap.parse_args()

    vs = [v["name"] for v in all_variants()]
    if args.variants:
        want = set(args.variants)
        vs = [v for v in vs if v in want or v.replace("socs_", "") in want]

    rows = []
    for v in vs:
        exe = os.path.join(ENV, "build", v, "Vsim_top")
        if not os.path.isfile(exe):
            print("!! %s: no simulator" % v); continue
        prof = os.path.join(ENV, "build", v, "profile.txt")
        r = subprocess.run(f"{exe} +HEX={args.hexfile} +PROF={prof} "
                           f"+MAX_CYCLES={args.max_cycles}",
                           shell=True, capture_output=True, text=True)
        if not os.path.isfile(prof):
            print("!! %s: no profile produced (%s)" % (v, r.stdout.strip())); continue
        d = read_prof(prof)
        d["_variant"] = v
        d["_halted"] = "HALT" in r.stdout
        rows.append(d)

    hdr = f"{'variant':<28} {'cycles':>10} {'retired':>9} {'CPI':>6} {'IPC':>6} " \
          f"{'br':>7} {'mispred':>8} {'br-miss%':>8} {'ld':>7} {'st':>7} {'mul':>6} {'div':>6}"
    print(hdr); print("-" * len(hdr))
    for d in rows:
        cyc, ret = d["cycles"], max(d["retired"], 1)
        br = d["branch"]; mis = d.get("bit0_events", 0)
        print(f"{d['_variant']:<28} {cyc:>10} {d['retired']:>9} {cyc/ret:>6.3f} {ret/cyc:>6.3f} "
              f"{br:>7} {mis:>8} {(100.0*mis/br if br else 0):>7.1f}% "
              f"{d['load']:>7} {d['store']:>7} {d['mul']:>6} {d['div']:>6}"
              + ("" if d["_halted"] else "   [did not halt]"))

    print("\nstall-cycle breakdown (% of total cycles; n/a = stage absent)")
    hdr2 = f"{'variant':<28}" + "".join(f"{l[:13]:>15}" for l in LABELS[1:])
    print(hdr2); print("-" * len(hdr2))
    for d in rows:
        cyc = max(d["cycles"], 1)
        cells = ""
        for i in range(1, len(LABELS)):
            if not available(d["_variant"], i):
                cells += f"{'n/a':>15}"
            else:
                cells += f"{100.0*d.get('bit%d_cycles' % i, 0)/cyc:>14.1f}%"
        print(f"{d['_variant']:<28}{cells}")

    if args.csv:
        import csv as _csv
        keys = ["_variant", "cycles", "retired", "branch", "jump", "load", "store", "mul", "div"] \
               + [f"bit{i}_cycles" for i in range(11)] + [f"bit{i}_events" for i in range(11)]
        with open(args.csv, "w", newline="") as fh:
            w = _csv.writer(fh); w.writerow(keys)
            for d in rows:
                w.writerow([d.get(k, "") for k in keys])
        print("\nwrote %s" % args.csv)


if __name__ == "__main__":
    main()
