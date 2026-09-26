#!/usr/bin/env python3
"""Run Embench-IoT on every RV-IM100 variant.

Each variant runs the build for the ISA it implements.  The benchmark times
itself with the cores' own mcycle/minstret CSRs over the region between
start_trigger() and stop_trigger(), so the reported figures exclude startup,
verification and printing -- and the same binary would report the same way on
the FPGA.

Results arrive over the UART as "EMBENCH <cycles> <instret> <ok|BAD>", in hex
because decimal conversion needs a divide and these binaries also run on the
I-only cores.  A run that does not print "ok" failed verification and is
reported as such rather than being silently averaged in.

Usage:
    scripts/run_embench.py [--variants v1 ...] [--csv out.csv]
"""
import argparse, os, re, subprocess, sys

ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ENV, "scripts"))
os.environ.setdefault("RVIM_SOURCE", "socs")
from variants import all_variants  # noqa: E402

RESULT = re.compile(r"EMBENCH\s+([0-9a-f]+)\s+([0-9a-f]+)\s+(ok|BAD)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="*")
    ap.add_argument("--max-cycles", type=int, default=400_000_000)
    ap.add_argument("--csv", default=os.path.join(ENV, "logs", "embench.csv"))
    args = ap.parse_args()

    vs = all_variants()
    if args.variants:
        want = set(args.variants)
        vs = [v for v in vs if v["name"] in want
              or v["name"].replace("socs_", "") in want]

    rows = []
    for v in vs:
        isa = "rv%d%s" % (v["xlen"], v["ext"].lower())
        bdir = os.path.join(ENV, "build", "embench", isa)
        exe = os.path.join(ENV, "build", v["name"], "Vsim_top")
        if not os.path.isdir(bdir) or not os.path.isfile(exe):
            print("!! %s: missing build or simulator" % v["name"]); continue
        work = os.path.join(ENV, "build", v["name"], "embench")
        os.makedirs(work, exist_ok=True)
        ok = bad = err = 0
        for hexf in sorted(os.listdir(bdir)):
            if not hexf.endswith(".hex"):
                continue
            b = hexf[:-4]
            uart = os.path.join(work, b + ".uart")
            prof = os.path.join(work, b + ".prof")
            r = subprocess.run(
                f"{exe} +HEX={os.path.join(bdir, hexf)} +HALT_ADDR=10012000 "
                f"+UART={uart} +PROF={prof} +MAX_CYCLES={args.max_cycles}",
                shell=True, capture_output=True, text=True)
            text = open(uart).read() if os.path.isfile(uart) else ""
            m = RESULT.search(text)
            if not m:
                err += 1
                rows.append(dict(variant=v["name"], bench=b, status="NO-RESULT",
                                 cycles="", instret="",
                                 note="TIMEOUT" if "TIMEOUT" in r.stdout else "no output"))
                continue
            cyc, ins, verdict = int(m.group(1), 16), int(m.group(2), 16), m.group(3)
            if verdict == "ok":
                ok += 1
            else:
                bad += 1
            rows.append(dict(variant=v["name"], bench=b,
                             status="ok" if verdict == "ok" else "VERIFY-FAIL",
                             cycles=cyc, instret=ins,
                             note="%.3f" % (cyc / ins) if ins else ""))
        print("  %-30s %-8s  ok %2d   verify-fail %2d   no-result %2d"
              % (v["name"], isa, ok, bad, err))
        rows[-1] if rows else None

    if rows:
        import csv
        os.makedirs(os.path.dirname(args.csv), exist_ok=True)
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["variant", "bench", "status",
                                               "cycles", "instret", "note"])
            w.writeheader(); w.writerows(rows)
        print("\nwrote %s" % args.csv)
        bad = [r for r in rows if r["status"] != "ok"]
        if bad:
            print("\n%d run(s) did not verify:" % len(bad))
            for r in bad[:20]:
                print("   %-30s %-16s %s %s" % (r["variant"], r["bench"],
                                                r["status"], r["note"]))


if __name__ == "__main__":
    main()
