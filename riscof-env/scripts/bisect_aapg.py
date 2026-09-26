#!/usr/bin/env python3
"""Find the first instruction at which two RV-IM100 variants diverge.

Both variants run the *same* ROM image, so unlike the Sail comparison there
is no link-address artifact to see through: any difference is the RTL.  The
5-stage designs match Sail exactly on these programs, which makes them a
clean reference for the deeper pipelines.

The program is truncated after N body instructions -- everything after the
cut is replaced by the program's own exit -- and N is bisected for the
smallest prefix that still diverges.  That instruction is where to look.

Usage:
    scripts/bisect_aapg.py <program.S> --good socs_RV64IM_5SP --bad socs_RV64IM_8SP
"""
import argparse
import os
import re
import subprocess
import sys

ENV    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AE     = os.path.join(ENV, "aapg-env")
TOOLS  = "/opt/riscv/bin"
PREFIX = "riscv64-unknown-elf-"
BODY   = re.compile(r"^i[0-9a-f]+:")


def build_and_run(src_lines, work, march, mabi, common, asmdir, variants):
    """Assemble the given program text and return {variant: signature list}."""
    os.makedirs(work, exist_ok=True)
    s = os.path.join(work, "cut.S")
    open(s, "w").write("\n".join(src_lines) + "\n")
    env = dict(os.environ, PATH=TOOLS + ":" + os.environ["PATH"])
    elf = os.path.join(work, "cut.elf")
    cc = (f"{PREFIX}gcc -march={march} -mabi={mabi} -static -mcmodel=medany "
          f"-nostdlib -nostartfiles -DRVIM_DUT -T {AE}/dut.ld "
          f"-I {AE} -I {common} -I {asmdir} {s} {AE}/crt_dut.S -o {elf}")
    if subprocess.run(cc, shell=True, capture_output=True, env=env).returncode:
        return None
    nm = subprocess.check_output([PREFIX + "nm", elf], text=True, env=env)
    b = e = None
    for line in nm.splitlines():
        p = line.split()
        if len(p) >= 3 and p[2] == "begin_signature": b = p[0]
        if len(p) >= 3 and p[2] == "end_signature":   e = p[0]
    binp = os.path.join(work, "cut.bin")
    subprocess.run(f"{PREFIX}objcopy -O binary -j .text.init -j .text "
                   f"-j .rodata -j .data {elf} {binp}",
                   shell=True, capture_output=True, env=env)
    blob = open(binp, "rb").read()
    blob += b"\x00" * ((-len(blob)) % 4)
    hexp = os.path.join(work, "cut.hex")
    with open(hexp, "w") as fh:
        for i in range(0, len(blob), 4):
            fh.write("%08x\n" % int.from_bytes(blob[i:i+4], "little"))
    out = {}
    for v in variants:
        sig = os.path.join(work, "%s.sig" % v)
        exe = os.path.join(ENV, "build", v, "Vsim_top")
        r = subprocess.run(f"{exe} +HEX={hexp} +SIG_BEGIN={b} +SIG_END={e} "
                           f"+SIG_FILE={sig} +MAX_CYCLES=20000000",
                           shell=True, capture_output=True, text=True)
        if "TIMEOUT" in r.stdout or not os.path.isfile(sig):
            return None
        out[v] = [x.strip() for x in open(sig)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("program")
    ap.add_argument("--good", required=True)
    ap.add_argument("--bad", required=True)
    ap.add_argument("--march", default="rv64im_zicsr")
    ap.add_argument("--mabi", default="lp64")
    args = ap.parse_args()

    lines = open(args.program).read().splitlines()
    asmdir = os.path.dirname(os.path.abspath(args.program))
    common = os.path.join(os.path.dirname(asmdir), "common")
    work = os.path.join(ENV, "build", "aapg", "bisect")

    body = [i for i, l in enumerate(lines) if BODY.match(l.strip())]
    # everything from the program's own exit onward (exit code + .data)
    tail_start = next(i for i, l in enumerate(lines) if "j" in l and "write_tohost" in l)
    tail = lines[tail_start:]
    print("body instructions: %d" % len(body))

    def diverges(n):
        """True if the first n body instructions already make good != bad."""
        cut = lines[:body[n - 1] + 1] if n else lines[:body[0]]
        r = build_and_run(cut + tail, work, args.march, args.mabi,
                          common, asmdir, [args.good, args.bad])
        if r is None:
            return None
        return r[args.good] != r[args.bad]

    full = diverges(len(body))
    print("full program diverges: %s" % full)
    if not full:
        raise SystemExit("no divergence with the whole body -- nothing to bisect")

    def probe(n):
        """Nearest prefix at or after n that both builds and halts on both."""
        for k in range(n, min(n + 60, len(body) + 1)):
            r = diverges(k)
            if r is not None:
                return k, r
        return n, None

    lo, hi = 0, len(body)          # lo known-clean, hi known-diverging
    while hi - lo > 1:
        mid = (lo + hi) // 2
        # A prefix that will not assemble (a truncation can orphan a forward
        # branch label) or that hangs carries no information about
        # divergence.  Step forward to the next usable one instead of
        # scoring it, which is what made an earlier run of this bisect
        # untrustworthy.
        k, d = probe(mid)
        if d is None:
            hi = mid
            continue
        print("  n=%-5d %s" % (k, "DIVERGES" if d else "clean"))
        if d: hi = k
        else: lo = k

    print("\nfirst divergence appears at body instruction #%d" % hi)
    idx = body[hi - 1]
    print("context:")
    for k in range(max(0, idx - 12), min(len(lines), idx + 3)):
        mark = ">>" if k == idx else "  "
        print("  %s %s" % (mark, lines[k].rstrip()))


if __name__ == "__main__":
    main()
