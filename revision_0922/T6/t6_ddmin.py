#!/usr/bin/env python3
"""T6: delta-debug an AAPG branch-outcome divergence to a minimal standalone test.

Starting point: rv32im_s004, where RV32IM_7SP commits the fall-through of
`beq s3,a7` at 0x6014 although s3 == a7 == 10 architecturally (5SP takes it).

Construction (all addresses are the original ones, so auipc results and branch
targets are unchanged):
  0x0000   prologue: pre-store the words the replayed window loads, then set
           x1..x31 to the architectural values at the window entry (rebuilt from
           the reference trace), then jump to the window entry
  window   the original instruction words, K committed instructions before the
           failing branch (taken branches inside the window are kept as-is)
  0x6018   (fall-through of the branch)  -> FAIL: tohost <- 2
  0x601c   (branch target)               -> PASS: tohost <- 1

ddmin replaces window instructions with NOP and keeps a candidate only if the
DUT still FAILS and the reference still PASSES.

usage: t6_ddmin.py   (writes t6_min.hex / t6_min.S / t6_ddmin.json next to itself)
"""
import os, subprocess, json, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.abspath(os.path.join(HERE, '..', '..'))
REF, DUT = 'RV32IM_5SP', 'RV32IM_7SP'
PROG = f'{ENV}/build/socs_RV32IM_5SP/aapg/rv32im_s004'
BR_PC, FAIL_PC, PASS_PC = 0x6014, 0x6018, 0x601c
K = int(os.environ.get('K', 40))
TMP = os.environ.get('CFTMP', '/tmp/rv-im100')
NOP = 0x00000013


def rom_image():
    b = open(f'{PROG}/dut.hex').read().split()
    return {4 * i: int(w, 16) for i, w in enumerate(b)}


def ref_trace():
    t = f'{TMP}/t6_ref_trace.txt'
    subprocess.run([f'{ENV}/build/socs_{REF}/Vsim_top', f'+HEX={PROG}/dut.hex', f'+TRACE={t}',
                    '+MAX_CYCLES=200000'], capture_output=True)
    out = []
    for l in open(t):
        if l[0] == 'S':
            continue
        a = l.split()
        if len(a) < 3 or a[2] == '00000013':
            continue
        out.append((int(a[1], 16), int(a[2], 16), a[3] if len(a) > 3 else '-'))
    return out


def sx(v, n):
    return v - (1 << n) if v >> (n - 1) & 1 else v


# ---- tiny RV32 encoder -------------------------------------------------------
def lui(rd, imm20): return ((imm20 & 0xfffff) << 12) | (rd << 7) | 0x37
def addi(rd, rs, imm): return ((imm & 0xfff) << 20) | (rs << 15) | (rd << 7) | 0x13
def sw(rs2, rs1, imm): return (((imm >> 5) & 0x7f) << 25) | (rs2 << 20) | (rs1 << 15) | (2 << 12) | ((imm & 31) << 7) | 0x23
def jal(rd, off):
    o = off & 0x1fffff
    return (((o >> 20) & 1) << 31) | (((o >> 1) & 0x3ff) << 21) | (((o >> 11) & 1) << 20) | (((o >> 12) & 0xff) << 12) | (rd << 7) | 0x6f


def li(rd, v):
    v &= 0xffffffff
    lo = sx(v & 0xfff, 12)
    hi = ((v - lo) >> 12) & 0xfffff
    return [lui(rd, hi), addi(rd, rd, lo)]


def build(rom, window_pcs, keep, regs, mem):
    img = dict(rom)
    for pc in window_pcs:
        if pc not in keep and pc != BR_PC:
            img[pc] = NOP
    p = []
    for addr, val in sorted(mem.items()):
        p += li(5, addr) + li(6, val) + [sw(6, 5, 0)]
    for r in range(1, 32):
        p += li(r, regs[r])
    entry = window_pcs[0]
    p += [NOP] * 8
    p.append(jal(0, entry - 4 * len(p)))
    for i, w in enumerate(p):
        img[4 * i] = w
    assert 4 * len(p) < min(window_pcs), 'prologue overlaps the window'
    fail = li(5, 0x10010000) + [addi(6, 0, 2), sw(6, 5, 0)]
    pas = li(5, 0x10010000) + [addi(6, 0, 1), sw(6, 5, 0)]
    img[FAIL_PC] = jal(0, 0x7000 - FAIL_PC)
    for i, w in enumerate(fail):
        img[0x7000 + 4 * i] = w
    for i, w in enumerate(pas):
        img[PASS_PC + 4 * i] = w
    top = max(img)
    return [img.get(4 * i, 0) for i in range(top // 4 + 1)]


def run(variant, words, tag):
    hexf = f'{TMP}/t6_{tag}.hex'
    open(hexf, 'w').write(''.join(f'{w:08x}\n' for w in words))
    r = subprocess.run([f'{ENV}/build/socs_{variant}/Vsim_top', f'+HEX={hexf}', '+MAX_CYCLES=20000'],
                       capture_output=True, text=True)
    if 'code=0x00000001' in r.stdout:
        return 'PASS'
    if 'code=0x00000002' in r.stdout:
        return 'FAIL'
    return 'OTHER:' + r.stdout.strip()[-80:]


def main():
    rom = rom_image()
    tr = ref_trace()
    ib = next(i for i, (pc, _, _) in enumerate(tr) if pc == BR_PC)
    i0 = ib - K
    # architectural state before tr[i0]
    regs = [0] * 32
    for pc, w, rd in tr[:i0]:
        if rd != '-':
            r, v = rd.split('=')
            regs[int(r[1:])] = int(v, 16)
    # memory the window loads: pre-store the loaded value (word-aligned read-modify)
    x = list(regs)
    mem = {}
    for pc, w, rd in tr[i0:ib]:
        op, f3 = w & 0x7f, (w >> 12) & 7
        if op == 0x03 and rd != '-':
            a = (x[(w >> 15) & 31] + sx(w >> 20, 12)) & 0xffffffff
            v = int(rd.split('=')[1], 16)
            wa, sh = a & ~3, (a & 3) * 8
            width = {0: 8, 4: 8, 1: 16, 5: 16, 2: 32}[f3]
            m = ((1 << width) - 1) << sh
            mem[wa] = (mem.get(wa, 0) & ~m) | ((v << sh) & m)
        if rd != '-':
            r, v = rd.split('=')
            x[int(r[1:])] = int(v, 16)
    window = sorted({pc for pc, _, _ in tr[i0:ib]})
    assert window[0] == tr[i0][0] or True
    # entry must be the first committed pc of the window
    window_pcs = [tr[i0][0]] + [p for p in window if p != tr[i0][0]]
    full = set(window_pcs)
    base = build(rom, window_pcs, full, regs, mem)
    rr, rd_ = run(REF, base, 'ref'), run(DUT, base, 'dut')
    print('full window:', len(full), 'instructions; ref', rr, 'dut', rd_, flush=True)
    if not (rr == 'PASS' and rd_ == 'FAIL'):
        print('window does not reproduce; increase K'); sys.exit(1)

    def test(keep):
        w = build(rom, window_pcs, keep, regs, mem)
        return run(DUT, w, 'dut') == 'FAIL' and run(REF, w, 'ref') == 'PASS'

    cand = [p for p in window_pcs if p != BR_PC]
    n = 2
    while len(cand) >= 2:
        chunk = max(1, len(cand) // n)
        reduced = False
        for i in range(0, len(cand), chunk):
            trial = cand[:i] + cand[i + chunk:]
            if test(set(trial)):
                cand, n, reduced = trial, max(n - 1, 2), True
                print('  kept', len(cand), flush=True)
                break
        if not reduced:
            if n >= len(cand):
                break
            n = min(len(cand), 2 * n)
    keep = set(cand)
    final = build(rom, window_pcs, keep, regs, mem)
    open(f'{HERE}/t6_min.hex', 'w').write(''.join(f'{w:08x}\n' for w in final))
    res = {v: run(v, final, 'x' + v) for v in
           ['RV32IM_5SP', 'RV32IM_6SP', 'RV32IM_7SP', 'RV32IM_7SP_BRAM', 'RV32IM_7SP_BRAM_Opt',
            'RV32IM_8SP_withoutOpt', 'RV32IM_8SP', 'RV32I_5SP']}
    kept = [(hex(p), f'{rom[p]:08x}') for p in sorted(keep)] + [(hex(BR_PC), f'{rom[BR_PC]:08x}')]
    json.dump(dict(K=K, window=len(full), kept=kept, regs={f'x{i}': hex(v) for i, v in enumerate(regs)},
                   mem={hex(a): hex(v) for a, v in mem.items()}, results=res),
              open(f'{HERE}/t6_ddmin.json', 'w'), indent=1)
    print('minimal:', kept)
    print('results:', res)


if __name__ == '__main__':
    main()
