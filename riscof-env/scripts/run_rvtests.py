#!/usr/bin/env python3
"""Run the Berkeley riscv-tests ISA suite on the RV-IM100 variants.

Unlike the architectural tests, riscv-tests are self-checking: each test
computes its own pass/fail and stores the verdict, so there is no reference
model and no signature comparison.  The verdict reaches us as the value the
program writes to the tohost MMIO address, which sim_top exposes as halt_code
and tb_sim_top turns into an exit status: 0 pass, 1 a numbered test failed,
2 the run hit the cycle limit.

fence_i is excluded family-wide: it requires Zifencei, which none of these
designs implement.

Usage:
    scripts/run_rvtests.py                  # every variant
    scripts/run_rvtests.py RV64IM_8SP ...   # named variants
    scripts/run_rvtests.py --jobs 8
"""
import argparse
import concurrent.futures as cf
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import all_variants  # noqa: E402

ENV        = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RVTESTS    = "/home/khwl/riscv-tests"
ISA_DIR    = os.path.join(RVTESTS, "isa")
MACRO_DIR  = os.path.join(ISA_DIR, "macros", "scalar")
TESTENV    = os.path.join(ENV, "rvtests-env")
TOOLS      = "/opt/riscv/bin"
PREFIX     = "riscv64-unknown-elf-"
MAX_CYCLES = 20_000_000

# Needs Zifencei, which no RV-IM100 variant implements.
EXCLUDE = {"fence_i"}


def suites_for(v):
    base = "rv%d" % v["xlen"]
    out = [base + "ui"]
    if "M" in v["ext"]:
        out.append(base + "um")
    return out


def march_for(v):
    return "rv%d%s_zicsr" % (v["xlen"], v["ext"].lower())


def tests_for(v):
    found = []
    for suite in suites_for(v):
        d = os.path.join(ISA_DIR, suite)
        for f in sorted(os.listdir(d)):
            if f.endswith(".S") and f[:-2] not in EXCLUDE:
                found.append((suite, f[:-2], os.path.join(d, f)))
    return found


def run_one(v, suite, name, src, workdir, dut_exe):
    tdir = os.path.join(workdir, suite, name)
    os.makedirs(tdir, exist_ok=True)
    elf  = os.path.join(tdir, "test.elf")
    hexf = os.path.join(tdir, "test.hex")
    log  = os.path.join(tdir, "test.log")

    march = march_for(v)
    mabi  = "lp64" if v["xlen"] == 64 else "ilp32"
    env   = dict(os.environ, PATH=TOOLS + ":" + os.environ["PATH"])

    with open(log, "w") as lf:
        cc = (f"{PREFIX}gcc -march={march} -mabi={mabi} "
              f"-static -mcmodel=medany -fvisibility=hidden "
              f"-nostdlib -nostartfiles "
              f"-T {TESTENV}/link.ld -I {TESTENV} -I {MACRO_DIR} "
              f"{src} -o {elf}")
        lf.write("$ %s\n" % cc)
        r = subprocess.run(cc, shell=True, capture_output=True, text=True, env=env)
        lf.write(r.stdout + r.stderr)
        if r.returncode != 0:
            return (suite, name, "BUILD", "compile failed")

        oc = (f"{PREFIX}objcopy -O binary -j .text.init -j .text -j .rodata "
              f"-j .data {elf} {tdir}/test.bin")
        lf.write("\n$ %s\n" % oc)
        r = subprocess.run(oc, shell=True, capture_output=True, text=True, env=env)
        lf.write(r.stdout + r.stderr)
        if r.returncode != 0:
            return (suite, name, "BUILD", "objcopy failed")

        with open(f"{tdir}/test.bin", "rb") as bf, open(hexf, "w") as hf:
            blob = bf.read()
            if len(blob) % 4:
                blob += b"\x00" * (4 - len(blob) % 4)
            for i in range(0, len(blob), 4):
                hf.write("%08x\n" % int.from_bytes(blob[i:i+4], "little"))
        os.remove(f"{tdir}/test.bin")

        run = f"{dut_exe} +HEX={hexf} +MAX_CYCLES={MAX_CYCLES}"
        lf.write("\n$ %s\n" % run)
        try:
            r = subprocess.run(run, shell=True, capture_output=True,
                               text=True, timeout=900)
        except subprocess.TimeoutExpired:
            lf.write("\n[run_rvtests] wall-clock timeout\n")
            return (suite, name, "TIMEOUT", "wall clock")
        lf.write(r.stdout + r.stderr)

        m = re.search(r"code=0x([0-9a-fA-F]+)", r.stdout)
        code = int(m.group(1), 16) if m else -1
        if r.returncode == 0:
            return (suite, name, "PASS", "")
        if r.returncode == 2:
            return (suite, name, "TIMEOUT", "cycle limit")
        # riscv-tests encodes the failing test number as (n << 1) | 1
        num = (code >> 1) if code > 1 else None
        detail = ("failed subtest %d" % num) if num else ("code=0x%08x" % code)
        return (suite, name, "FAIL", detail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variants", nargs="*")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    args = ap.parse_args()

    allv = all_variants()
    if args.variants:
        want = set(args.variants)
        allv = [v for v in allv
                if v["name"] in want or v["name"].replace("socs_", "") in want]
        if not allv:
            raise SystemExit("no matching variants")

    os.makedirs(os.path.join(ENV, "logs"), exist_ok=True)
    summary = []
    grand_pass = grand_total = 0

    for v in allv:
        dut = os.path.join(ENV, "build", v["name"], "Vsim_top")
        if not os.path.isfile(dut):
            print("!! %s: no simulator, run build_sim.sh first" % v["name"])
            continue
        workdir = os.path.join(ENV, "build", v["name"], "rvtests")
        tests = tests_for(v)
        results = []
        with cf.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futs = [ex.submit(run_one, v, s, n, p, workdir, dut)
                    for s, n, p in tests]
            for f in cf.as_completed(futs):
                results.append(f.result())
        results.sort()
        npass = sum(1 for r in results if r[2] == "PASS")
        grand_pass += npass
        grand_total += len(results)
        bad = [r for r in results if r[2] != "PASS"]
        print("%-30s %3d/%3d%s" % (v["name"], npass, len(results),
              ("   failing: " + ", ".join("%s(%s)" % (r[1], r[2]) for r in bad)) if bad else ""))
        summary.append((v["name"], npass, len(results), results))

    out = os.path.join(ENV, "logs", "rvtests_results.csv")
    with open(out, "w") as fh:
        fh.write("variant,suite,test,status,detail\n")
        for name, _, _, results in summary:
            for s, n, st, d in results:
                fh.write("%s,%s,%s,%s,%s\n" % (name, s, n, st, d))
    print("\nTOTAL %d/%d   -> %s" % (grand_pass, grand_total, out))


if __name__ == "__main__":
    main()
