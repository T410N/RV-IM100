#!/usr/bin/env python3
"""Value-level lock-step comparison of two variants on the same image (T6, P2).

Runs <ref> and <dut> (same ROM image, same XLEN) side by side, each streaming
its retire trace through a FIFO, and walks the two committed streams together:

  * (pc, insn) equal, rd value equal            -> in step
  * (pc, insn) equal, rd value different         -> VALUE DIVERGENCE, unless the
                                                    value is tainted (below)
  * (pc, insn) different                         -> CONTROL event; resynchronise
                                                    by skipping up to WIN entries
                                                    on either side, and log how
                                                    many were inserted/dropped

Taint: a csrr of a counter legitimately returns different values on different
pipelines.  Its destination is tainted, taint propagates through any retired
instruction that reads a tainted register, and through memory (a store of a
tainted register taints its address; a load from a tainted address taints the
destination).  Divergent values on tainted registers are expected and are not
counted.  Load/store addresses are computed as x[rs1]+imm from a register file
rebuilt from the reference trace's rd values.

NOP words (0x00000013) are dropped, as in the cores' minstret.

usage: lockstep.py <ref_variant> <dut_variant> <hex> [max_cycles] [--halt-addr=X] [--nohalt]
                   [--stop-pc=HEX --stop-count=N]
prints one JSON line.
"""
import sys, os, subprocess, json, threading, queue

ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WIN = int(os.environ.get('LS_WIN', 16))


def stream(variant, hexf, maxc, halt, nohalt, tmpd, tag):
    fifo = f'{tmpd}/ls_{tag}_{variant}.fifo'
    if os.path.exists(fifo):
        os.remove(fifo)
    os.mkfifo(fifo)
    cmd = [f'{ENV}/build/socs_{variant}/Vsim_top', f'+HEX={hexf}', f'+TRACE={fifo}', f'+MAX_CYCLES={maxc}']
    if halt:
        cmd.append(f'+HALT_ADDR={halt}')
    if nohalt:
        cmd.append('+NOHALT')
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    q = queue.Queue(maxsize=200000)

    def reader():
        pending_stores = []
        with open(fifo) as f:
            for line in f:
                if line[0] == 'S':
                    a = line.split()
                    pending_stores.append(int(a[1], 16) & ~7)
                    continue
                a = line.split()
                if len(a) < 3:                     # partial last line of a killed simulator
                    continue
                w = int(a[2], 16)
                if w == 0x13:
                    continue
                rd = None
                if len(a) > 3 and a[3] != '-':
                    r, v = a[3].split('=')
                    rd = (int(r[1:]), int(v, 16))
                q.put((int(a[0]), int(a[1], 16), w, rd, pending_stores))
                pending_stores = []
        q.put(None)
        os.remove(fifo)
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    return p, q


def reads(w):
    op = w & 0x7f
    rs1 = (w >> 15) & 31
    rs2 = (w >> 20) & 31
    if op in (0x33, 0x3b, 0x63, 0x23):
        return {rs1, rs2}
    if op in (0x13, 0x1b, 0x03, 0x67):
        return {rs1}
    if op == 0x73 and ((w >> 12) & 3) in (1, 2, 3):
        return {rs1}
    return set()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    ref, dut, hexf = args[:3]
    maxc = int(args[3]) if len(args) > 3 else 400_000_000
    halt = next((a.split('=')[1] for a in sys.argv if a.startswith('--halt-addr=')), None)
    nohalt = '--nohalt' in sys.argv
    # compare only up to the benchmark's own stop marker: after it the elapsed
    # counter values are reloaded from memory and printed, which legitimately differs
    stop_pc = next((int(a.split('=')[1], 16) for a in sys.argv if a.startswith('--stop-pc=')), None)
    stop_count = next((int(a.split('=')[1]) for a in sys.argv if a.startswith('--stop-count=')), 1)
    seen_stop = 0
    tmpd = os.environ.get('CFTMP', '/tmp/rv-im100')
    os.makedirs(tmpd, exist_ok=True)
    tag = str(os.getpid())
    pr, qr = stream(ref, hexf, maxc, halt, nohalt, tmpd, tag)
    pd, qd = stream(dut, hexf, maxc, halt, nohalt, tmpd, tag)

    taint = set()          # tainted registers (shared view: the architectural stream)
    tmem = set()           # tainted 8-byte-aligned addresses
    xr = [0] * 32          # reference register file, rebuilt from the trace's rd values
    xmask = (1 << (64 if ref.startswith('RV64') else 32)) - 1

    def sx(v, bits):
        return v - (1 << bits) if v >> (bits - 1) & 1 else v
    n = 0
    vdiv = []
    nv = 0
    ctrl = []
    nctrl = 0
    ins = dele = 0
    bufr, bufd = [], []

    def nxt(q, buf):
        if buf:
            return buf.pop(0)
        return q.get()

    a = nxt(qr, bufr)
    b = nxt(qd, bufd)
    while a is not None and b is not None:
        if (a[1], a[2]) == (b[1], b[2]):
            if stop_pc is not None and a[1] == stop_pc:
                seen_stop += 1
                if seen_stop >= stop_count:
                    break
            n += 1
            w = a[2]
            src = reads(w)
            tainted_src = bool(src & taint)
            op = w & 0x7f
            if op == 0x03:                                   # load from a tainted address
                addr = (xr[(w >> 15) & 31] + sx(w >> 20, 12)) & xmask
                if (addr & ~7) in tmem:
                    tainted_src = True
            elif op == 0x23:                                 # store: data taint -> address taint
                addr = (xr[(w >> 15) & 31] + sx(((w >> 25) << 5) | ((w >> 7) & 31), 12)) & xmask
                if ((w >> 20) & 31) in taint:
                    tmem.add(addr & ~7)
            if a[3] is not None or b[3] is not None:
                rdn = (a[3] or b[3])[0]
                is_csr = op == 0x73 and ((w >> 12) & 3) != 0
                if is_csr or tainted_src:
                    taint.add(rdn)
                else:
                    taint.discard(rdn)
                    if a[3] != b[3]:
                        nv += 1
                        if len(vdiv) < 10:
                            vdiv.append(dict(n=n, pc=hex(a[1]), insn=f'{w:08x}', ref=str(a[3]), dut=str(b[3]),
                                             ref_cycle=a[0], dut_cycle=b[0]))
            if a[3] is not None and a[3][0]:
                xr[a[3][0]] = a[3][1]
            a = nxt(qr, bufr)
            b = nxt(qd, bufd)
            continue
        # control event: resynchronise
        nctrl += 1
        la, lb = [a], [b]
        for _ in range(WIN):
            x = nxt(qr, bufr)
            if x is None:
                break
            la.append(x)
        for _ in range(WIN):
            x = nxt(qd, bufd)
            if x is None:
                break
            lb.append(x)
        best = None
        for i in range(len(la)):
            for j in range(len(lb)):
                if (la[i][1], la[i][2]) == (lb[j][1], lb[j][2]) and \
                        all((la[i + k][1], la[i + k][2]) == (lb[j + k][1], lb[j + k][2])
                            for k in range(1, min(4, len(la) - i, len(lb) - j))):
                    if best is None or i + j < best[0] + best[1]:
                        best = (i, j)
        if len(ctrl) < 10:
            ctrl.append(dict(n=n, ref=[f'{x[1]:x}:{x[2]:08x}' for x in la[:6]],
                             dut=[f'{x[1]:x}:{x[2]:08x}' for x in lb[:6]],
                             dropped=best[0] if best else None, inserted=best[1] if best else None,
                             dut_cycle=b[0]))
        if best is None:
            break
        dele += best[0]
        ins += best[1]
        # skipped DUT-side instructions may have written registers the reference never did
        for x in lb[:best[1]]:
            if x[3] is not None:
                taint.add(x[3][0])
        for x in la[:best[0]]:                                # keep the reference regfile current
            if x[3] is not None and x[3][0]:
                xr[x[3][0]] = x[3][1]
        bufr = la[best[0]:] + bufr
        bufd = lb[best[1]:] + bufd
        a = nxt(qr, bufr)
        b = nxt(qd, bufd)
    pr.kill(); pd.kill()
    pr.wait(); pd.wait()
    sys.stdout.write(json.dumps(dict(ref=ref, dut=dut, image=hexf, compared=n, value_divergences=nv,
                          control_events=nctrl, dut_inserted=ins, dut_dropped=dele,
                          ended='stop-marker' if stop_pc is not None and seen_stop >= stop_count else
                          ('both' if a is None and b is None else ('ref' if a is None else 'dut')),
                          first_value=vdiv, first_control=ctrl)))


if __name__ == '__main__':
    main()
    sys.stdout.write('\n')
    sys.stdout.flush()
    os._exit(0)          # reader threads may still be blocked on a killed simulator's FIFO
