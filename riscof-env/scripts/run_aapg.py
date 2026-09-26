#!/usr/bin/env python3
"""AAPG randomized testing with Sail co-simulation.

For each variant, every program in its ISA pool is assembled twice -- once
against dut.ld for the core's memory map, once against sail.ld for Sail's --
run on both, and the signature regions compared.  Same methodology as the
RISCOF sweep; the only difference is that the programs are randomly generated
rather than hand-written, so they reach instruction sequences and hazard
patterns the directed suites do not.

The Sail reference is computed once per (pool, program) and cached: it depends
on the program and the ISA, never on which pipeline is executing it, so the
eight RV64IM variants share one reference run each.

Usage:
    scripts/run_aapg.py                    # every variant
    scripts/run_aapg.py socs_RV64IM_8SP
    scripts/run_aapg.py --jobs 8
"""
import argparse
import concurrent.futures as cf
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import all_variants  # noqa: E402

ENV        = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AAPG_ENV   = os.path.join(ENV, "aapg-env")
POOLS      = os.path.join(ENV, "build", "aapg")
SAIL_DIR   = "/home/khwl/Downloads/sail-riscv-riscof-0.6/c_emulator"
TOOLS      = "/opt/riscv/bin"
PREFIX     = "riscv64-unknown-elf-"
MAX_CYCLES = 20_000_000
INST_LIMIT = 2_000_000


def pool_for(v):
    return "rv%d%s" % (v["xlen"], v["ext"].lower())


def programs_in(pool):
    d = os.path.join(POOLS, pool, "work", "asm")
    if not os.path.isdir(d):
        return []
    out = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".S") and not f.endswith("_template.S"):
            p = os.path.join(d, f)
            if any(l.startswith("i0") for l in open(p)):
                out.append((f[:-2], p))
    return out


def _common_dir(pool):
    return os.path.join(POOLS, pool, "work", "common")


def compile_one(pool, src, out_elf, ldscript, march, mabi, dut, log):
    env = dict(os.environ, PATH=TOOLS + ":" + os.environ["PATH"])
    cmd = (f"{PREFIX}gcc -march={march} -mabi={mabi} -static -mcmodel=medany "
           f"-nostdlib -nostartfiles "
           f"{'-DRVIM_DUT ' if dut else ''}"
           f"-T {AAPG_ENV}/{ldscript} "
           f"-I {AAPG_ENV} -I {_common_dir(pool)} -I {os.path.dirname(src)} "
           f"{src} {AAPG_ENV}/crt_dut.S -o {out_elf}")
    log.write("$ %s\n" % cmd)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
    log.write(r.stdout + r.stderr)
    return r.returncode == 0


def sig_bounds(elf):
    env = dict(os.environ, PATH=TOOLS + ":" + os.environ["PATH"])
    out = subprocess.check_output([PREFIX + "nm", elf], text=True, env=env)
    b = e = None
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 3:
            if p[2] == "begin_signature":
                b = p[0]
            elif p[2] == "end_signature":
                e = p[0]
    return b, e


# Text-base offsets used to expose link-address dependence.  One probe is not
# enough: a word holding a masked or shifted fragment of an address can be
# insensitive to a small shift yet still differ between the DUT at base
# 0x00000000 and Sail at 0x80000000.  Measured on rv32i_s001, a 0x40000 probe
# found 14 dependent words and a 0x40000000 probe found 16 -- the two extra
# being words this harness previously reported as DUT mismatches.  Probing at
# several magnitudes and taking the union covers dependence on low and high
# address bits alike.
SHIFTS = (0x40000, 0x400000, 0x4000000, 0x40000000)


def address_dependent_words(pool, name, src, march, mabi, workdir):
    """Indices whose value provably depends on where the program was linked.

    The DUT runs from ROM at 0x00000000; Sail's RAM base is fixed at
    0x80000000 and its emulator has no --ram-base, so the two can never share
    a link address.  Most of that dependence has been engineered out of the
    generated programs, but a residue survives, and a raw DUT-vs-Sail count
    conflates it with real divergence.

    Rather than guess at it, measure it: run the *reference model against
    itself* at two text addresses.  Any word that moves is link-address
    dependent by construction, and cannot be evidence about the DUT.  Nothing
    else is excluded -- this is an independent measurement on Sail alone, not
    a mask fitted to the DUT's mismatches.
    """
    d = os.path.join(POOLS, pool, "_sailref", name)
    marker = os.path.join(d, "addrdep.txt")
    if os.path.isfile(marker):
        return set(int(x) for x in open(marker).read().split())
    base, _ = sail_reference(pool, name, src, march, mabi, workdir)
    if base is None:
        return set()
    os.makedirs(d, exist_ok=True)
    idx = set()
    for shift in SHIFTS:
        ld = os.path.join(d, "shift_%x.ld" % shift)
        txt = open(os.path.join(AAPG_ENV, "sail.ld")).read()
        open(ld, "w").write(txt.replace(". = 0x80000000;", ". = 0x%08x;" % (0x80000000 + shift)))
        elf = os.path.join(d, "shift_%x.elf" % shift)
        sig = os.path.join(d, "shift_%x.sig" % shift)
        with open(os.path.join(d, "shift_%x.log" % shift), "w") as lf:
            if not compile_one(pool, src, elf, os.path.relpath(ld, AAPG_ENV),
                               march, mabi, False, lf):
                continue
            exe = os.path.join(SAIL_DIR, "riscv_sim_RV%d" % (64 if "64" in march else 32))
            subprocess.run(f"{exe} --no-trace --inst-limit={INST_LIMIT} "
                           f"--test-signature={sig} {elf}",
                           shell=True, capture_output=True, timeout=600)
        if not os.path.isfile(sig):
            continue
        a = [x.strip() for x in open(base)]; b = [x.strip() for x in open(sig)]
        idx |= set(i for i, (x, y) in enumerate(zip(a, b)) if x != y)
    open(marker, "w").write(" ".join(str(i) for i in sorted(idx)))
    return idx


def sail_reference(pool, name, src, march, mabi, workdir):
    """Run Sail once for this program; cached on disk.

    The cache lives with the pool, not with the variant: the reference
    depends only on the program and the ISA, so all eight RV64IM variants
    share one run each instead of repeating it eight times.
    """
    d = os.path.join(POOLS, pool, "_sailref", name)
    os.makedirs(d, exist_ok=True)
    sig = os.path.join(d, "sail.sig")
    if os.path.isfile(sig) and os.path.getsize(sig) > 0:
        return sig, None
    elf = os.path.join(d, "sail.elf")
    with open(os.path.join(d, "sail.log"), "w") as lf:
        if not compile_one(pool, src, elf, "sail.ld", march, mabi, False, lf):
            return None, "sail compile failed"
        exe = os.path.join(SAIL_DIR, "riscv_sim_RV%d" % (64 if "64" in march else 32))
        cmd = (f"{exe} --no-trace --inst-limit={INST_LIMIT} "
               f"--test-signature={sig} {elf}")
        lf.write("\n$ %s\n" % cmd)
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True,
                               text=True, timeout=600)
            lf.write(r.stdout[-4000:] + r.stderr[-4000:])
        except subprocess.TimeoutExpired:
            return None, "sail wall-clock timeout"
    if not os.path.isfile(sig) or os.path.getsize(sig) == 0:
        return None, "sail produced no signature"
    return sig, None


def run_program(v, pool, name, src, workdir):
    march = "rv%d%s_zicsr" % (v["xlen"], v["ext"].lower())
    mabi  = "lp64" if v["xlen"] == 64 else "ilp32"
    d = os.path.join(workdir, name)
    os.makedirs(d, exist_ok=True)
    elf, hexf = os.path.join(d, "dut.elf"), os.path.join(d, "dut.hex")
    sig = os.path.join(d, "dut.sig")

    with open(os.path.join(d, "dut.log"), "w") as lf:
        if not compile_one(pool, src, elf, "dut.ld", march, mabi, True, lf):
            return (name, "BUILD", "dut compile failed")
        env = dict(os.environ, PATH=TOOLS + ":" + os.environ["PATH"])
        oc = (f"{PREFIX}objcopy -O binary -j .text.init -j .text -j .rodata "
              f"-j .data {elf} {d}/dut.bin")
        lf.write("\n$ %s\n" % oc)
        if subprocess.run(oc, shell=True, capture_output=True, env=env).returncode:
            return (name, "BUILD", "objcopy failed")
        with open(f"{d}/dut.bin", "rb") as bf, open(hexf, "w") as hf:
            blob = bf.read()
            blob += b"\x00" * ((-len(blob)) % 4)
            for i in range(0, len(blob), 4):
                hf.write("%08x\n" % int.from_bytes(blob[i:i+4], "little"))
        os.remove(f"{d}/dut.bin")

        b, e = sig_bounds(elf)
        if not b or not e:
            return (name, "BUILD", "no signature symbols")
        exe = os.path.join(ENV, "build", v["name"], "Vsim_top")
        cmd = (f"{exe} +HEX={hexf} +SIG_BEGIN={b} +SIG_END={e} "
               f"+SIG_FILE={sig} +MAX_CYCLES={MAX_CYCLES}")
        lf.write("\n$ %s\n" % cmd)
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True,
                               text=True, timeout=900)
            lf.write(r.stdout + r.stderr)
        except subprocess.TimeoutExpired:
            return (name, "TIMEOUT", "wall clock")
        if "TIMEOUT" in r.stdout:
            return (name, "TIMEOUT", "cycle limit")

    ref, err = sail_reference(pool, name, src, march, mabi, workdir)
    if ref is None:
        return (name, "REFERR", err)
    if not os.path.isfile(sig):
        return (name, "NOSIG", "dut produced no signature")
    a = [l.strip().lower() for l in open(sig)]
    c = [l.strip().lower() for l in open(ref)]
    skip = address_dependent_words(pool, name, src, march, mabi, workdir)
    diff = [i for i, (x, y) in enumerate(zip(a, c)) if x != y]
    real = [i for i in diff if i not in skip]
    if not real and len(a) == len(c):
        note = "" if not diff else "%d link-address words excluded" % len(diff)
        return (name, "MATCH", note)
    n = len(real) + abs(len(a) - len(c))
    return (name, "MISMATCH", "%d/%d words differ (%d link-address excluded)"
            % (n, max(len(a), len(c)), len(diff) - len(real)))


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

    rows, gp, gt = [], 0, 0
    for v in allv:
        if not os.path.isfile(os.path.join(ENV, "build", v["name"], "Vsim_top")):
            print("!! %s: no simulator" % v["name"]); continue
        pool = pool_for(v)
        progs = programs_in(pool)
        if not progs:
            print("!! %s: pool %s is empty, run gen_aapg.py" % (v["name"], pool))
            continue
        workdir = os.path.join(ENV, "build", v["name"], "aapg")

        # Warm the Sail cache serially so parallel workers do not all try to
        # produce the same reference file at once.
        march = "rv%d%s_zicsr" % (v["xlen"], v["ext"].lower())
        mabi = "lp64" if v["xlen"] == 64 else "ilp32"
        for name, src in progs:
            sail_reference(pool, name, src, march, mabi, workdir)

        res = []
        with cf.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futs = [ex.submit(run_program, v, pool, n, s, workdir)
                    for n, s in progs]
            for f in cf.as_completed(futs):
                res.append(f.result())
        res.sort()
        ok = sum(1 for r in res if r[1] == "MATCH")
        gp += ok; gt += len(res)
        bad = [r for r in res if r[1] != "MATCH"]
        print("%-30s %2d/%2d%s" % (v["name"], ok, len(res),
              ("   " + ", ".join("%s:%s(%s)" % r for r in bad[:4])) if bad else ""))
        rows.append((v["name"], res))

    out = os.path.join(ENV, "logs", "aapg_results.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        fh.write("variant,program,status,detail\n")
        for name, res in rows:
            for p, st, d in res:
                fh.write("%s,%s,%s,%s\n" % (name, p, st, d))
    print("\nTOTAL %d/%d matching Sail   -> %s" % (gp, gt, out))


if __name__ == "__main__":
    main()
