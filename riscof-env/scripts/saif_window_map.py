#!/usr/bin/env python3
"""T4: where in the program did each SAIF capture window fall?

The netlist-simulation capture (cap.tcl) follows a fixed timeline: the core is
released at 70 us (forced benchmark_start), tx_busy is forced low from 100 us to 1100 us,
the simulation runs to 1200 us, and the first 100 us window is 1200-1300 us
(later windows follow at +100 us if the UART was busy).  RTL simulation is
cycle-exact with the hardware (FPGA == sim on every row checked), so the window
maps to core cycles [ (t0-70us)*f , (t1-70us)*f ) on the same image.

For each build: rebuild the board image's ELF (the image is reproducible
byte-for-byte; the rebuilt .mem is checked against the project's), run the RTL
simulation with a retire trace, and report the cycle and instret range of the
window plus the functions retiring inside it.

usage: saif_window_map.py [try_index=0]   -> logs/saif_window_map.csv
"""
import csv, json, os, re, subprocess, sys, hashlib, bisect, collections, shutil
ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ROOT = os.path.dirname(ENV)
BM = f'{ROOT}/benchmarks'
TOOLS = '/opt/riscv/bin:' + os.path.expanduser('~/riscv32i-elf/bin')
TRY = int(sys.argv[1]) if len(sys.argv) > 1 else 0
T0_US, T1_US, START_US = 1200 + 100 * TRY, 1300 + 100 * TRY, 70
TMP = os.environ.get('CFTMP', '/tmp/rv-im100')


def build_elf(variant, bench, mhz, want_md5):
    isa = {'RV64I_': 'rv64i', 'RV64IM': 'rv64im', 'RV32I_': 'rv32i', 'RV32IM': 'rv32im'}[
        next(k for k in ('RV64I_', 'RV64IM', 'RV32I_', 'RV32IM') if variant.startswith(k))]
    abi = 'lp64' if '64' in isa else 'ilp32'
    if '64' in isa:
        d = 'Coremark_baremetal' if bench == 'coremark' else 'Dhrystone2.1_baremetal_RV64'
    else:
        d = 'coremark_rv32i_port' if bench == 'coremark' else 'dhrystone_rv32i_port'
    wd = f'{TMP}/wm_{variant}_{bench}'
    shutil.rmtree(wd, ignore_errors=True)
    shutil.copytree(f'{BM}/{d}', wd)
    env = dict(os.environ, PATH=TOOLS + ':' + os.environ['PATH'])
    subprocess.run('make clean', shell=True, cwd=wd, capture_output=True, env=env)
    hz = int(round(mhz * 1e6))
    subprocess.run(f'make CPU_FREQ_HZ={hz} ARCH_FLAGS="-march={isa}_zicsr -mabi={abi}" '
                   f'ASFLAGS="-march={isa}_zicsr -mabi={abi} -Wa,-march={isa}_zicsr" '
                   f'FLAGS_STR="\\"-O2 -march={isa}_zicsr -mabi={abi} -fno-common -funroll-loops\\"" verilog',
                   shell=True, cwd=wd, capture_output=True, env=env)
    tgt = 'coremark' if bench == 'coremark' else 'dhrystone'
    got = hashlib.md5(open(f'{wd}/{tgt}.mem', 'rb').read()).hexdigest()
    return wd, f'{wd}/{tgt}.elf', got == want_md5


def symtab(elf):
    out = subprocess.run(['/opt/riscv/bin/riscv64-unknown-elf-nm', '-n', elf], capture_output=True, text=True).stdout
    s = [(int(p[0], 16), p[2]) for p in (l.split() for l in out.splitlines()) if len(p) == 3 and p[1] in 'tT']
    return [a for a, _ in s], [n for _, n in s]


def main():
    audit = json.load(open(sys.argv[2] if len(sys.argv) > 2 else f'{ENV}/logs/img_audit.json'))
    rows = []
    for o in audit:
        proj = o['project'].split('/')[-1]
        m = re.match(r'(RV\d+I(?:M)?_\w+?)_(Dhry|Coremark)$', proj)
        variant, bench = m.group(1), ('dhrystone' if m.group(2) == 'Dhry' else 'coremark')
        f = float(o['pll'])
        mhz_img = float(re.search(r'_([0-9.]+)MHz', o['mem']).group(1))
        wd, elf, ok = build_elf(variant, bench, mhz_img, o['md5'][0])
        addrs, names = symtab(elf)
        memf = f"{ROOT}/RV-IM100_RTL/project_files/{o['project']}/{o['paths'][0]}"
        c0, c1 = int((T0_US - START_US) * f), int((T1_US - START_US) * f)
        fifo = f'{TMP}/wm_{variant}_{bench}.fifo'
        if os.path.exists(fifo):
            os.remove(fifo)
        os.mkfifo(fifo)
        p = subprocess.Popen([f'{ENV}/build/socs_{variant}/Vsim_top', f'+HEX={memf}', '+NOHALT',
                              f'+TRACE={fifo}', f'+MAX_CYCLES={c1 + 10}'], stdout=subprocess.DEVNULL)
        n = 0; i0 = i1 = None; fn = collections.Counter()
        for line in open(fifo):
            if line[0] == 'S':
                continue
            a = line.split()
            cyc, pc, w = int(a[0]), int(a[1], 16), a[2]
            if w != '00000013':
                n += 1
            if cyc >= c0 and i0 is None:
                i0 = n
            if c0 <= cyc < c1 and w != '00000013':      # bubbles retire as pc=0 nop
                k = bisect.bisect_right(addrs, pc) - 1
                fn[names[k] if k >= 0 else '?'] += 1
            if cyc >= c1:
                i1 = n
                break
        p.kill(); p.wait(); os.remove(fifo)
        tot = sum(fn.values()) or 1
        top = '; '.join(f'{k} {100 * v / tot:.0f}%' for k, v in fn.most_common(4))
        rows.append(dict(variant=variant, bench=bench, pll_MHz=f, image=o['mem'], elf_rebuilt_matches=ok,
                         window_us=f'{T0_US}-{T1_US}', start_cycle=c0, end_cycle=c1,
                         instret_start=i0, instret_end=i1, top_functions=top))
        shutil.rmtree(wd, ignore_errors=True)
        print(rows[-1]['variant'], bench, c0, c1, i0, i1, ok, top, flush=True)
    out = f'{ENV}/logs/saif_window_map_try{TRY}.csv'
    with open(out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print('wrote', out)


if __name__ == '__main__':
    main()
