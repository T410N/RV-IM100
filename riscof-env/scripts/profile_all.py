#!/usr/bin/env python3
"""Profile every variant on its own Dhrystone and CoreMark images.

Each variant is run on the ROM image from *its own* Vivado project, so the
profile describes the same binary that produced the published FPGA score.

Runs stop after a fixed number of retired instructions rather than a fixed
cycle count: every variant then executes identical work and only the cycle
count differs, which is what makes CPI comparable across pipeline depths.

0x10010000 is the SoC's UART transmit register as well as the harness's halt
address, so +NOHALT is required or the benchmark's first printf ends the run.
The UART byte stream is captured, which is also how the benchmark's own
output is recovered.

Usage:
    scripts/profile_all.py [--instr 10000000] [--csv out.csv]
"""
import argparse, os, re, subprocess, sys

ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.abspath(os.path.join(ENV, "..", "RV-IM100_RTL", "project_files"))
sys.path.insert(0, os.path.join(ENV, "scripts"))
os.environ.setdefault("RVIM_SOURCE", "socs")
from variants import all_variants  # noqa: E402

# Project directories do not all match the variant name.
ALIAS = {"RV64I_5SP": "RV64I5SP_SoC"}

LABELS = ["branch mispred", "pc stall", "front-end stall", "ID/EX stall",
          "EXR/EX stall", "EX/EX2 stall", "EX/MEM stall", "MEM/WB stall",
          "load-use hazard", "divider busy", "multiplier busy"]


def project_dir(v):
    name = v["name"].replace("socs_", "")
    d = os.path.join(ROOT, "RV%ds" % v["xlen"], "SoCs", ALIAS.get(name, name))
    return d if os.path.isdir(d) else None


def find_image(v, bench):
    """Pick this variant's image for `bench`, preferring an ISA-tagged name.

    Some project directories hold images for a neighbouring ISA too (the
    RV64I core's folder also carries an RV64IM CoreMark), so an untagged
    substring match would silently profile the wrong binary.
    """
    d = project_dir(v)
    if not d:
        return None
    isa = "RV%d%s" % (v["xlen"], v["ext"])
    cands = []
    for dirpath, _, files in os.walk(d):
        for f in files:
            if f.endswith(".mem") and bench in f.lower():
                cands.append(os.path.join(dirpath, f))
    if not cands:
        return None

    # The ISA tag must be delimited.  A plain substring test puts an RV64IM
    # image on an RV64I core, because "RV64I" occurs inside "RV64IM" -- which
    # it did, and the resulting profile looked plausible but was the wrong
    # binary entirely.
    tagged = re.compile(r"(?:^|[_-])RV\d+I M?|(?:^|[_-])RV\d+IM?(?=[_.-])")

    def tag_of(name):
        m = re.search(r"(?:^|[_-])(RV\d+IM?)(?=[_.-])", name)
        return m.group(1) if m else None

    exact = [c for c in cands if tag_of(os.path.basename(c)) == isa]
    if exact:
        return sorted(exact)[0]
    # otherwise only accept images carrying no ISA tag at all
    untagged = [c for c in cands if tag_of(os.path.basename(c)) is None]
    if untagged:
        return sorted(untagged)[0]
    return None


def read_prof(p):
    d = {}
    for line in open(p):
        f = line.split()
        if len(f) == 2:
            d[f[0]] = int(f[1])
        elif len(f) == 4:
            d[f[0]] = int(f[1]); d[f[2]] = int(f[3])
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instr", type=int, default=10_000_000)
    ap.add_argument("--csv", default=os.path.join(ENV, "logs", "profile.csv"))
    ap.add_argument("--benchmarks", nargs="*", default=["dhrystone", "coremark"])
    args = ap.parse_args()

    rows = []
    for v in all_variants():
        for bench in args.benchmarks:
            img = find_image(v, bench)
            if not img:
                print("!! %-28s %-10s no image" % (v["name"], bench)); continue
            exe = os.path.join(ENV, "build", v["name"], "Vsim_top")
            if not os.path.isfile(exe):
                print("!! %-28s no simulator" % v["name"]); continue
            out = os.path.join(ENV, "build", v["name"], "prof_%s" % bench)
            r = subprocess.run(
                f"{exe} +HEX={img} +NOHALT +MAX_INSTR={args.instr} "
                f"+PROF={out}.txt +UART={out}.uart +MAX_CYCLES=400000000",
                shell=True, capture_output=True, text=True)
            if not os.path.isfile(out + ".txt"):
                print("!! %-28s %-10s no profile" % (v["name"], bench)); continue
            d = read_prof(out + ".txt")
            d["_v"] = v["name"]; d["_b"] = bench
            d["_img"] = os.path.basename(img)
            d["_done"] = d["retired"] >= args.instr
            rows.append(d)
            cyc, ret = d["cycles"], max(d["retired"], 1)
            print("   %-28s %-10s cycles=%-11d retired=%-9d CPI=%.3f%s"
                  % (v["name"], bench, cyc, ret, cyc / ret,
                     "" if d["_done"] else "   [short run]"))

    for bench in args.benchmarks:
        sel = [d for d in rows if d["_b"] == bench]
        if not sel:
            continue
        print("\n=== %s : CPI and instruction mix ===" % bench)
        h = f"{'variant':<28}{'CPI':>7}{'IPC':>7}{'br%':>7}{'mispred':>9}{'miss%':>7}{'ld%':>6}{'st%':>6}{'mul':>7}{'div':>7}"
        print(h); print("-" * len(h))
        for d in sel:
            cyc, ret = d["cycles"], max(d["retired"], 1)
            br, mis = d["branch"], d.get("bit0_events", 0)
            print(f"{d['_v']:<28}{cyc/ret:>7.3f}{ret/cyc:>7.3f}{100*br/ret:>6.1f}%"
                  f"{mis:>9}{(100*mis/br if br else 0):>6.1f}%"
                  f"{100*d['load']/ret:>5.1f}%{100*d['store']/ret:>5.1f}%"
                  f"{d['mul']:>7}{d['div']:>7}")

        print("\n=== %s : stall cycles (%% of total) ===" % bench)
        h2 = f"{'variant':<28}" + "".join(f"{l[:12]:>14}" for l in LABELS[1:])
        print(h2); print("-" * len(h2))
        for d in sel:
            cyc = max(d["cycles"], 1)
            cells = ""
            for i in range(1, len(LABELS)):
                key = "bit%d_cycles" % i
                cells += ("%13.1f%%" % (100.0 * d.get(key, 0) / cyc)) if key in d else f"{'n/a':>14}"
            print(f"{d['_v']:<28}{cells}")

    if rows:
        import csv
        keys = ["_v", "_b", "_img", "_done", "cycles", "retired", "branch", "jump",
                "load", "store", "mul", "div"] + \
               [f"bit{i}_cycles" for i in range(11)] + [f"bit{i}_events" for i in range(11)]
        os.makedirs(os.path.dirname(args.csv), exist_ok=True)
        with open(args.csv, "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(keys)
            for d in rows:
                w.writerow([d.get(k, "") for k in keys])
        print("\nwrote %s" % args.csv)


if __name__ == "__main__":
    main()
