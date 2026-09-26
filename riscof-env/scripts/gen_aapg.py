#!/usr/bin/env python3
"""Generate AAPG random programs, one pool per ISA.

Four pools -- rv32i, rv32im, rv64i, rv64im -- because a program has to be
assembled for the exact ISA the variant implements: feeding rv64 instructions
to an RV32 core, or M instructions to an I-only core, would test the assembler
rather than the pipeline.

The instruction mix is weighted compute:data:ctrl = 10:4:1 (plus M at 3 where
the variant has it).  AAPG aborts generation outright if branches are too
frequent for its block size, and a mix that heavy on branches would in any
case spend the program on control flow rather than on the data hazards these
pipelines differ in.

Usage:
    scripts/gen_aapg.py                    # 20 programs per ISA
    scripts/gen_aapg.py --programs 50
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

ENV      = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AAPG     = "/tmp/aapgenv/bin/aapg"
BASE_CFG = os.path.join(ENV, "aapg-env", "config_base.yaml")
OUT      = os.path.join(ENV, "build", "aapg")

# Relative frequencies per pool.  Anything not named here stays at 0.
# AAPG hardcodes auipc into its rv32i.compute group with no way to disable it,
# and auipc is the one instruction that makes a program's results depend on
# where it was linked.  That matters here because the DUT runs from ROM at
# 0x00000000 while Sail's RAM base is fixed at 0x80000000 and its emulator has
# no --ram-base, so the two builds cannot share a link address.  A PC landing
# in a register does not stay put: it feeds the random arithmetic that follows
# and the divergence cascades -- measured at ~150 differing signature words
# from only 6-11 direct address stores.
#
# Rewriting body auipc to lui keeps the instruction count, the block
# structure, the destination register and the immediate, and drops only the
# PC dependence.  Both sides then execute a byte-identical program, which is
# what makes the signature comparison mean anything.  auipc itself is covered
# by the architectural tests and by riscv-tests, so nothing goes unverified.
BODY_AUIPC = re.compile(r"^(i[0-9a-f]+:\s+)auipc(\s+)", re.M)

# AAPG's prologue installs the trap vector with
#     la t0, custom_trap_handler
#     csrw mtvec, t0
# and then runs the body, which uses t0 (x5) as an ordinary random operand.
# That leaves a text address in a register the program computes on, which is
# the second way a link address reaches the signature.  It is also an
# unpadded CSR write, and the CSR read path on these cores is two cycles and
# not interlocked, so mtvec would be written from a stale t0 on the deeper
# pipelines.  Pad it, then put t0 back to a value both sides agree on.
PROLOGUE = re.compile(
    r"^(\s*)la(\s+)t0,(\s*)custom_trap_handler\s*\n"
    r"\s*csrw\s+mtvec,\s*t0\s*$", re.M)

PROLOGUE_FIX = (r"\1la\2t0,\3custom_trap_handler" "\n"
                r"\1nop; nop; nop; nop" "\n"
                r"\1csrw                mtvec, t0" "\n"
                r"\1nop; nop; nop; nop" "\n"
                r"\1li                  t0, 0")


# AAPG's control flow links every jump into x10 (a0) and reaches indirect
# targets via `la <reg>, <label>` into an ordinary body register.  Both put a
# text address where the random arithmetic can read it, and once a PC enters
# the datapath the divergence between a DUT linked at 0x00000000 and a Sail
# run based at 0x80000000 cascades into arbitrary values -- measured at ~150
# differing signature words from a handful of direct address stores.
#
# x10 is never used as a jump target, so no return ever consumes the link
# value: it is dead, and can be discarded into x0 rather than merely moved
# somewhere quieter.  Writing it to x1 was not enough -- AAPG's trap handler
# pushes x1..x31 onto a stack that sits inside the signature region, so a
# PC parked in x1 still reached the comparison.  Only the indirect target
# needs a real register, and x1 is safe for that because regs_not_use
# withholds it from the body.
CALL_PAIR = re.compile(
    r"^(\s*)la(\s+)(x\d+),(\s*)(i[0-9a-f]+)\s*\n"
    r"(\s*)jalr(\s+)x10,(\s*)\3,(\s*)0\s*$", re.M)
JAL_LINK = re.compile(r"^(\s*)jal(\s+)x10,(\s*)(\S+)\s*$", re.M)


def depc(asm_path):
    """Make a generated program independent of where it was linked.

    Returns (auipc_rewritten, prologue_fixed, calls_relinked).
    """
    s = open(asm_path).read()
    s, n = BODY_AUIPC.subn(r"\1lui\2", s)
    s, m = PROLOGUE.subn(PROLOGUE_FIX, s)
    s, c = CALL_PAIR.subn(r"\1la\2x1,\4\5\n\6jalr\7x0,\8x1,\9 0", s)
    s, j = JAL_LINK.subn(r"\1jal\2x0,\3\4", s)
    open(asm_path, "w").write(s)
    return n, m, c + j


POOLS = {
    "rv32i":  ("rv32", {"rel_rv32i.compute": 10, "rel_rv32i.data": 4,
                        "rel_rv32i.ctrl": 1,
                        "rel_rv64i.compute": 0, "rel_rv64i.data": 0,
                        "rel_rv32m": 0, "rel_rv64m": 0}),
    "rv32im": ("rv32", {"rel_rv32i.compute": 10, "rel_rv32i.data": 4,
                        "rel_rv32i.ctrl": 1,
                        "rel_rv64i.compute": 0, "rel_rv64i.data": 0,
                        "rel_rv32m": 3, "rel_rv64m": 0}),
    "rv64i":  ("rv64", {"rel_rv32i.compute": 10, "rel_rv32i.data": 4,
                        "rel_rv32i.ctrl": 1,
                        "rel_rv64i.compute": 10, "rel_rv64i.data": 4,
                        "rel_rv32m": 0, "rel_rv64m": 0}),
    "rv64im": ("rv64", {"rel_rv32i.compute": 10, "rel_rv32i.data": 4,
                        "rel_rv32i.ctrl": 1,
                        "rel_rv64i.compute": 10, "rel_rv64i.data": 4,
                        "rel_rv32m": 3, "rel_rv64m": 3}),
}


def write_config(path, overrides):
    s = open(BASE_CFG).read()
    for k, v in overrides.items():
        s, n = re.subn(r"^(\s*%s:)\s*\S+$" % re.escape(k), r"\1 %d" % v,
                       s, flags=re.M)
        if n != 1:
            raise SystemExit("config key %s matched %d times" % (k, n))
    open(path, "w").write(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--programs", type=int, default=20)
    ap.add_argument("--pools", nargs="*", default=sorted(POOLS))
    args = ap.parse_args()

    if not os.path.isfile(AAPG):
        raise SystemExit("aapg not found at %s -- see aapg-env/README" % AAPG)

    for pool in args.pools:
        arch, overrides = POOLS[pool]
        d = os.path.join(OUT, pool)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)

        subprocess.run([AAPG, "setup"], cwd=d, check=True,
                       capture_output=True, text=True)
        write_config(os.path.join(d, "work", "config.yaml"), overrides)

        made = 0
        for seed in range(1, args.programs + 1):
            name = "%s_s%03d" % (pool, seed)
            r = subprocess.run(
                [AAPG, "gen", "--num_programs", "1", "--arch", arch,
                 "--seed", str(seed), "--asm_name", name],
                cwd=d, capture_output=True, text=True)
            asm = os.path.join(d, "work", "asm", name + ".S")
            # AAPG reports a non-zero exit for some seeds and still writes a
            # body; and for others writes a file with no instructions at all.
            # Count only what actually carries a program.
            if os.path.isfile(asm) and sum(
                    1 for l in open(asm) if l.startswith("i0")) > 0:
                depc(asm)
                made += 1
            else:
                print("  %s: seed %d produced no body%s" % (
                    pool, seed,
                    " (" + r.stderr.strip().splitlines()[-1] + ")" if r.stderr.strip() else ""))
        print("%-8s %2d/%d programs -> %s/work/asm" % (pool, made, args.programs, d))


if __name__ == "__main__":
    main()
