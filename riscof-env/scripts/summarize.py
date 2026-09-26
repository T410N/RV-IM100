#!/usr/bin/env python3
"""Collect every RISCOF run into one table.

Reads the per-run riscof logs rather than the HTML reports: the log records one
authoritative Passed/Failed line per test, while the report's markup is awkward
to parse reliably.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import all_variants  # noqa: E402

ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGS = os.path.join(ENV, "logs")

LINE = re.compile(r"/src/([^ ]+)\.S\s*:.*?:\s*(Passed|Failed)")


def read(variant, group):
    p = os.path.join(LOGS, "riscof_%s_%s.log" % (variant, group))
    if not os.path.isfile(p):
        return None
    res = {}
    with open(p, errors="ignore") as fh:
        for line in fh:
            m = LINE.search(re.sub(r"\x1b\[[0-9;]*m", "", line))
            if m:
                res[m.group(1)] = m.group(2)
    return res


def main():
    rows = []
    for v in all_variants():
        groups = ["I", "M"] if v["ext"] == "IM" else ["I"]
        per = {}
        fails = []
        for g in groups:
            r = read(v["name"], g)
            if r is None:
                per[g] = None
                continue
            p = sum(1 for s in r.values() if s == "Passed")
            per[g] = (p, len(r))
            fails += sorted(k for k, s in r.items() if s == "Failed")
        rows.append((v, per, fails))

    w = "%-22s %-14s %-10s %-10s  %s"
    print(w % ("VARIANT", "ISA", "I", "M", "FAILING TESTS"))
    print("-" * 104)
    tp = tt = 0
    for v, per, fails in rows:
        def cell(g):
            if g not in per:
                return "-"
            if per[g] is None:
                return "not run"
            return "%d/%d" % per[g]
        for g in per:
            if per[g]:
                tp += per[g][0]
                tt += per[g][1]
        print(w % (v["name"], v["isa"], cell("I"), cell("M"),
                   ", ".join(fails) if fails else "none"))
    print("-" * 104)
    print("%-22s %-14s %d/%d tests passed" % ("TOTAL", "", tp, tt))

    csv = os.path.join(ENV, "results.csv")
    with open(csv, "w") as fh:
        fh.write("variant,isa,xlen,stages,suite,passed,total,failing\n")
        for v, per, fails in rows:
            stages = re.search(r"(\d)SP", v["name"]).group(1)
            for g, r in per.items():
                if not r:
                    continue
                bad = [f for f in fails] if g == "I" else fails
                fh.write("%s,%s,%d,%s,%s,%d,%d,%s\n" % (
                    v["name"], v["isa"], v["xlen"], stages, g, r[0], r[1],
                    " ".join(sorted(set(bad)))))
    print("\nwrote", csv)


if __name__ == "__main__":
    main()
