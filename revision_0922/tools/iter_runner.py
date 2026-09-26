#!/usr/bin/env python3
"""Per-iteration cycles / instructions for CoreMark and Dhrystone in RTL simulation.

Builds a fixed-iteration image (same make invocation as build_image_exact.sh,
plus ITERATIONS / DHRY_ITERS), runs it on build/socs_<variant>/Vsim_top with a
retire trace, and cuts the trace at the benchmark's own timing calls:

  CoreMark : first retire at start_time() .. first retire at stop_time()
  Dhrystone: first retire at times()      .. second retire at times()

Instret excludes NOP (0x00000013), matching the cores' minstret.  The dynamic
mix is decoded from the retired instruction words inside the region.

usage: iter_runner.py <variant> <coremark|dhrystone> <iters> [hz] [--keep]
prints one JSON line.
"""
import sys, os, subprocess, json, hashlib, re, shutil

S = os.path.dirname(os.path.abspath(__file__))
ENV = '/home/khwl/Desktop/RV-IM100/riscof-env'
TOOLS = '/opt/riscv/bin:' + os.path.expanduser('~/riscv32i-elf/bin')

def isa_of(v):
    for p, isa in (('RV64I_', 'rv64i'), ('RV64IM', 'rv64im'), ('RV32I_', 'rv32i'), ('RV32IM', 'rv32im')):
        if v.startswith(p):
            return isa
    raise SystemExit('bad variant ' + v)

def build(isa, bench, iters, hz):
    abi = 'lp64' if '64' in isa else 'ilp32'
    if '64' in isa:
        d = 'Coremark_baremetal' if bench == 'coremark' else 'Dhrystone2.1_baremetal_RV64'
    else:
        d = 'coremark_rv32i_port' if bench == 'coremark' else 'dhrystone_rv32i_port'
    tag = f'{bench}_{isa}_{iters}it_{hz}'
    out = f'{S}/images/{tag}'
    if os.path.exists(out + '.mem') and os.path.exists(out + '.elf'):
        return out
    os.makedirs(f'{S}/images', exist_ok=True)
    # private copy of the port so parallel builds do not collide
    wd = f'{S}/buildtmp/{tag}'
    if os.path.exists(wd):
        shutil.rmtree(wd)
    shutil.copytree(f'{S}/bm/{d}', wd)
    it = f'ITERATIONS={iters}' if bench == 'coremark' else f'DHRY_ITERS={iters}'
    tgt = 'coremark' if bench == 'coremark' else 'dhrystone'
    env = dict(os.environ, PATH=TOOLS + ':' + os.environ['PATH'])
    subprocess.run('make clean', shell=True, cwd=wd, capture_output=True, env=env)
    cmd = (f'make CPU_FREQ_HZ={hz} {it} ARCH_FLAGS="-march={isa}_zicsr -mabi={abi}" '
           f'ASFLAGS="-march={isa}_zicsr -mabi={abi} -Wa,-march={isa}_zicsr" '
           f'FLAGS_STR="\\"-O2 -march={isa}_zicsr -mabi={abi} -fno-common -funroll-loops\\"" verilog')
    r = subprocess.run(cmd, shell=True, cwd=wd, capture_output=True, text=True, env=env)
    if not os.path.exists(f'{wd}/{tgt}.mem'):
        raise SystemExit('build failed ' + tag + r.stderr[-2000:])
    shutil.copy(f'{wd}/{tgt}.mem', out + '.mem')
    shutil.copy(f'{wd}/{tgt}.elf', out + '.elf')
    shutil.rmtree(wd)
    return out

def symbols(elf):
    nm = subprocess.run(['riscv64-unknown-elf-nm', elf], capture_output=True, text=True,
                        env=dict(os.environ, PATH=TOOLS + ':' + os.environ['PATH'])).stdout
    return {p[2]: int(p[0], 16) for p in (l.split() for l in nm.splitlines()) if len(p) == 3}

def classify(w, rv64):
    op = w & 0x7f; f3 = (w >> 12) & 7; f7 = w >> 25
    c = {}
    if op == 0x63: c['branch'] = 1
    elif op == 0x6f: c['jal'] = 1
    elif op == 0x67: c['jalr'] = 1
    elif op == 0x03:
        c['load'] = 1
        if rv64 and f3 in (3, 6): c['rv64_mem'] = 1          # ld, lwu
    elif op == 0x23:
        c['store'] = 1
        if rv64 and f3 == 3: c['rv64_mem'] = 1               # sd
    elif op in (0x33, 0x3b) and f7 == 1:
        c['div' if f3 & 4 else 'mul'] = 1
    if op in (0x1b, 0x3b): c['wsuffix'] = 1
    return c

def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    keep = '--keep' in sys.argv
    v, bench, iters = a[0], a[1], int(a[2])
    hz = int(a[3]) if len(a) > 3 else 100000000
    isa = isa_of(v); rv64 = '64' in isa
    img = build(isa, bench, iters, hz)
    sym = symbols(img + '.elf')
    if bench == 'coremark':
        marks = [sym['start_time'], sym['stop_time']]
    else:
        marks = [sym['times'], sym['times']]
    exe = f'{ENV}/build/socs_{v}/Vsim_top'
    run = f'{S}/runs/{v}_{bench}_{iters}'
    os.makedirs(run, exist_ok=True)
    tr, ua = f'{run}/trace.txt', f'{run}/uart.txt'
    maxc = int(os.environ.get('MAXC', '400000000'))
    # stream the trace through a FIFO so we never store gigabytes
    if os.path.exists(tr): os.remove(tr)
    os.mkfifo(tr)
    p = subprocess.Popen([exe, f'+HEX={img}.mem', '+NOHALT', f'+UART={ua}', f'+TRACE={tr}',
                          f'+MAX_CYCLES={maxc}'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    state = 0; c0 = i0 = None; n = 0; mix = {}; c1 = i1 = None; last_cyc = 0
    exit_pc = sym.get('_exit')
    with open(tr) as f:
        for line in f:
            if line[0] == 'S':
                continue
            parts = line.split()
            cyc = int(parts[0]); pc = int(parts[1], 16); w = int(parts[2], 16)
            last_cyc = cyc
            if w != 0x13:
                n += 1
            if state == 0 and pc == marks[0]:
                c0, i0, state = cyc, n, 1
                continue
            if state == 1:
                if pc == marks[1]:
                    c1, i1, state = cyc, n, 2
                    continue
                if w != 0x13:
                    for k in classify(w, rv64):
                        mix[k] = mix.get(k, 0) + 1
            if state == 2 and exit_pc is not None and pc == exit_pc:
                p.kill(); break
    p.wait()
    os.remove(tr)
    # the trace pass is killed at _exit, which loses the buffered UART file;
    # re-run untraced to a cycle bound just past _exit so it exits cleanly
    subprocess.run([exe, f'+HEX={img}.mem', '+NOHALT', f'+UART={ua}',
                    f'+MAX_CYCLES={last_cyc + 20000}'], capture_output=True)
    uart = open(ua, errors='replace').read() if os.path.exists(ua) else ''
    res = dict(variant=v, bench=bench, iters=iters, hz=hz, isa=isa,
               elf_sha256=hashlib.sha256(open(img + '.elf', 'rb').read()).hexdigest(),
               region_cycles=(c1 - c0) if c1 else None,
               region_instret=(i1 - i0 - 1) if i1 else None,   # exclude the marker retire itself
               mix=mix, reached_stop=state == 2, last_cycle=last_cyc)
    m = re.search(r'Total ticks\s*:\s*(\d+)', uart)
    if m: res['uart_total_ticks'] = int(m.group(1))
    # 2K performance-run reference CRCs; the 10-second rule is the only
    # other error CoreMark raises, and short fixed-iteration runs trip it by design
    res['cm_valid'] = (all(x in uart for x in ('crclist       : 0xe714', 'crcmatrix     : 0x1fd7',
                                                'crcstate      : 0x8e3a'))
                       if bench == 'coremark' else None)
    if bench == 'dhrystone':
        res['dhry_ok'] = ('should be' in uart)
    res['uart_tail'] = uart[-600:]
    if not keep:
        shutil.rmtree(run, ignore_errors=True)
    print(json.dumps(res))

if __name__ == '__main__':
    main()
