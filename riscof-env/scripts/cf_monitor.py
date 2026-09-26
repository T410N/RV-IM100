#!/usr/bin/env python3
"""Committed-stream control-flow continuity monitor (testbench-only, T6).

Reads the retire trace produced by sim_top's +TRACE (one line per retired
instruction: "<cycle> <pc> <insn> <xN=val|->", plus "S ..." store lines) and
checks, for every pair of consecutive committed instructions, that the second
one's PC is architecturally reachable from the first:

    branch      -> pc+4 or pc+imm_b
    jal         -> pc+imm_j
    jalr        -> (x[rs1] + imm_i) & ~1    (x[] tracked from the trace itself)
    other       -> pc+4
    (a run of genuine NOP words in the ROM between the two is skipped: the
     tap does not record 0x00000013, whether bubble or program nop)

P3 (branch-outcome consistency): each committed branch's condition is evaluated
on the architectural register values rebuilt from the trace; the next committed
PC must be exactly the outcome that condition implies.  This catches a branch
resolved on stale operands, which P1 alone cannot (both successors are legal).

A violation means the core committed an instruction that is not on the
architectural path (wrong-path commit), or skipped one that is (dropped
instruction).  Nothing in the core is touched: this consumes the existing
retire tap, so it can be applied to any run of any variant.

The register file is reconstructed from the trace's rd writes.  Registers
written by instructions the tap does not show would make a JALR target
unknowable; those are counted separately (jalr_unknown) rather than guessed.

usage: cf_monitor.py <variant> <hex> <elf> [max_cycles] [--halt-addr=10012000] [--nohalt]
prints one JSON line: counts and the first few violations with context.
"""
import sys, os, subprocess, json

ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OBJCOPY = '/opt/riscv/bin/riscv64-unknown-elf-objcopy'


def sext(v, bits):
    return v - (1 << bits) if v >> (bits - 1) & 1 else v


def rom_words(elf, tmp):
    if elf.endswith('.hex'):                  # a ROM image given directly (one 32-bit word per line)
        return b''.join(int(w, 16).to_bytes(4, 'little') for w in open(elf).read().split())
    subprocess.run([OBJCOPY, '-O', 'binary', '-j', '.text.init', '-j', '.text', '-j', '.rodata',
                    elf, tmp], check=True)
    b = open(tmp, 'rb').read()
    os.remove(tmp)
    return b


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    v, hexf, elf = args[:3]
    maxc = int(args[3]) if len(args) > 3 else 400_000_000
    halt = next((a.split('=')[1] for a in sys.argv if a.startswith('--halt-addr=')), None)
    nohalt = '--nohalt' in sys.argv
    xlen = 64 if v.startswith('RV64') else 32
    mask = (1 << xlen) - 1
    tag = f'{os.getpid()}_{v}'
    tmpd = os.environ.get('CFTMP', '/tmp/rv-im100')
    os.makedirs(tmpd, exist_ok=True)
    rom = rom_words(elf, f'{tmpd}/rom_{tag}.bin')

    def word(pc):
        if pc + 4 <= len(rom):
            return int.from_bytes(rom[pc:pc + 4], 'little')
        return None

    fifo = f'{tmpd}/cf_{tag}.fifo'
    if os.path.exists(fifo):
        os.remove(fifo)
    os.mkfifo(fifo)
    cmd = [f'{ENV}/build/socs_{v}/Vsim_top', f'+HEX={hexf}', f'+TRACE={fifo}', f'+MAX_CYCLES={maxc}']
    if halt:
        cmd.append(f'+HALT_ADDR={halt}')
    if nohalt:
        cmd.append('+NOHALT')
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    x = [0] * 32
    known = [True] * 32
    prev = None            # (cycle, pc, insn)
    n = 0
    viol = []
    nviol = 0
    jalr_unknown = 0
    mis = [0, []]           # misaligned loads/stores seen in the committed stream
    nbr = [0, 0]            # branches checked, branches whose outcome contradicts the operands
    brv = []
    hist = []
    for line in open(fifo):
        if line[0] == 'S':
            continue
        parts = line.split()
        cyc, pc, w = int(parts[0]), int(parts[1], 16), int(parts[2], 16)
        if w == 0x13:
            continue
        n += 1
        if prev is not None:
            pcy, ppc, pw = prev
            op = pw & 0x7f
            allowed = {ppc + 4}
            if op == 0x63:
                imm = sext(((pw >> 31) & 1) << 12 | ((pw >> 7) & 1) << 11 |
                           ((pw >> 25) & 0x3f) << 5 | ((pw >> 8) & 0xf) << 1, 13)
                # P3: the outcome must agree with the architectural operand values
                a_, b_ = x[(pw >> 15) & 31], x[(pw >> 20) & 31]
                sa, sb = sext(a_, xlen), sext(b_, xlen)
                f3 = (pw >> 12) & 7
                taken = {0: a_ == b_, 1: a_ != b_, 4: sa < sb, 5: sa >= sb, 6: a_ < b_, 7: a_ >= b_}.get(f3)
                if taken is None:
                    allowed.add((ppc + imm) & mask)
                elif taken:
                    allowed = {(ppc + imm) & mask}
                if taken is not None:
                    nbr[0] += 1
                    want = (ppc + imm) & mask if taken else ppc + 4
                    q = want
                    while q != pc and word(q) == 0x13 and q - want < 16384:
                        q += 4
                    if q != pc:
                        nbr[1] += 1
                        if len(brv) < 8:
                            brv.append(dict(cycle=cyc, pc=hex(ppc), insn=f'{pw:08x}', rs1=hex(a_), rs2=hex(b_),
                                            arch_taken=taken, next_pc=hex(pc)))
            elif op == 0x6f:
                imm = sext(((pw >> 31) & 1) << 20 | ((pw >> 12) & 0xff) << 12 |
                           ((pw >> 20) & 1) << 11 | ((pw >> 21) & 0x3ff) << 1, 21)
                allowed = {(ppc + imm) & mask}
            elif op == 0x67:
                rs1 = (pw >> 15) & 31
                if known[rs1]:
                    allowed = {((x[rs1] + sext(pw >> 20, 12)) & mask) & ~1}
                else:
                    allowed = None
                    jalr_unknown += 1
            if allowed is not None:
                # skip genuine nops in the program image
                ok = False
                for a in allowed:
                    q = a
                    while q != pc and word(q) == 0x13 and q - a < 16384:
                        q += 4
                    if q == pc:
                        ok = True
                        break
                if not ok:
                    nviol += 1
                    if len(viol) < 12:
                        viol.append(dict(cycle=cyc, prev_pc=hex(ppc), prev_insn=f'{pw:08x}',
                                         pc=hex(pc), insn=f'{w:08x}',
                                         expected=[hex(a) for a in sorted(allowed)],
                                         context=hist[-4:]))
        # misaligned data accesses (address from the architectural rs1 before this write)
        op_c = w & 0x7f
        if op_c in (0x03, 0x23):
            f3c = (w >> 12) & 7
            imm_c = sext(w >> 20, 12) if op_c == 0x03 else sext(((w >> 25) << 5) | ((w >> 7) & 31), 12)
            ea = (x[(w >> 15) & 31] + imm_c) & mask
            size = 1 << (f3c & 3)
            if ea % size:
                mis[0] += 1
                if len(mis[1]) < 5:
                    mis[1].append(dict(cycle=cyc, pc=hex(pc), insn=f'{w:08x}', addr=hex(ea)))
        # register writes (value is post-write, so update after the check that used rs1)
        if len(parts) > 3 and parts[3] != '-':
            r, val = parts[3].split('=')
            ri = int(r[1:])
            if ri:
                x[ri] = int(val, 16)
                known[ri] = True
        prev = (cyc, pc, w)
        hist.append(f'{cyc} {pc:x} {w:08x}')
        if len(hist) > 8:
            hist.pop(0)
    out = p.stdout.read()
    p.wait()
    os.remove(fifo)
    print(json.dumps(dict(variant=v, image=hexf, retired=n, violations=nviol,
                          jalr_unknown=jalr_unknown, branches_checked=nbr[0], branch_outcome_errors=nbr[1],
                          misaligned=mis[0], first_misaligned=mis[1],
                          halted='HALT' in out, first=viol, first_branch_errors=brv)))


if __name__ == '__main__':
    main()
