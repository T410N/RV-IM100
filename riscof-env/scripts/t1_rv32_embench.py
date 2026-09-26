#!/usr/bin/env python3
"""T1: RV32 Embench on FPGA -- simulation reference and board cross-check.

  t1_rv32_embench.py simref     simulate every RV32 Embench FPGA image, write
                                logs/embench_rv32_simref_v4.csv
  t1_rv32_embench.py compare    read the board's embench_results.csv files and
                                compare against the reference, write
                                logs/embench_rv32_fpga_vs_sim.csv

The simulated image is the .mem inside each <variant>_Embench_<bench> Vivado
project -- the file the bitstream was built from -- not a rebuild of it.  Its
hash is checked against build/embench_fpga/<isa>/<bench>.mem and the ELF's
sha256 is recorded for provenance.

Board results are looked for, per variant, in
  bitstream/embench/RV32/Done/<variant>/embench_results.csv
  (header: architecture,benchmark,cycles,instret,verify)
Any mismatch is reported with its delta.  Numbers are never adjusted.
"""
import csv, glob, hashlib, os, re, subprocess, sys, datetime
from concurrent.futures import ThreadPoolExecutor

ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ROOT = os.path.dirname(ENV)
SOCS = f'{ROOT}/RV-IM100_RTL/project_files/RV32s/SoCs'
VARIANTS = ['RV32I_5SP', 'RV32IM_5SP', 'RV32IM_6SP', 'RV32IM_7SP', 'RV32IM_7SP_BRAM',
            'RV32IM_7SP_BRAM_Opt', 'RV32IM_8SP_withoutOpt', 'RV32IM_8SP']
BENCHES = ['matmult-int', 'crc32', 'nettle-aes', 'statemate', 'md5sum']
REF = f'{ENV}/logs/embench_rv32_simref_v4.csv'
OUT = f'{ENV}/logs/embench_rv32_fpga_vs_sim.csv'
RE_LINE = re.compile(r'EMBENCH (\S+) cycles=(\d+) instret=(\d+) verify=(OK|FAIL)')


def sha(path, algo='sha256'):
    h = hashlib.new(algo)
    h.update(open(path, 'rb').read())
    return h.hexdigest()


def project_image(proj):
    """The .mem the project's Instruction_Memory.v loads, resolved via the .xpr."""
    xpr = glob.glob(f'{proj}/*.xpr')[0]
    base = os.path.splitext(xpr)[0]
    files = [f.replace('$PPRDIR', proj).replace('$PSRCDIR', base + '.srcs')
             for f in re.findall(r'<File Path="([^"]+)"', open(xpr).read())]
    im = [f for f in files if f.endswith('Instruction_Memory.v')][0]
    src = re.sub(r'//.*', '', open(im).read())
    name = os.path.basename(re.findall(r'readmemh\(\s*"([^"]+)"', src)[0])
    cands = [f for f in files if os.path.basename(f) == name and os.path.exists(f)]
    return cands[0] if cands else None


def one(v, b):
    isa = 'rv32i' if v.startswith('RV32I_') else 'rv32im'
    proj = f'{SOCS}/{v}_Embench_{b}'
    mem = project_image(proj)
    ref_mem = f'{ENV}/build/embench_fpga/{isa}/{b}.mem'
    elf = f'{ENV}/build/embench_fpga/{isa}/{b}.elf'
    bit = f'{ROOT}/bitstream/embench/RV32/{v}/{v}_embench_{b}.bit'
    exe = f'{ENV}/build/socs_{v}/Vsim_top'
    uart = f'/tmp/rv-im100/t1_{v}_{b}.uart'
    os.makedirs(os.path.dirname(uart), exist_ok=True)
    r = subprocess.run([exe, f'+HEX={mem}', '+HALT_ADDR=10012000', f'+UART={uart}',
                        '+MAX_CYCLES=400000000'], capture_output=True, text=True)
    m = RE_LINE.search(open(uart).read()) if os.path.exists(uart) else None
    row = dict(variant=v, benchmark=b, isa=isa,
               sim_cycles=m.group(2) if m else '', sim_instret=m.group(3) if m else '',
               sim_verify=m.group(4) if m else 'NO-RESULT',
               image=os.path.relpath(mem, ROOT), image_md5=sha(mem, 'md5'),
               image_matches_build=sha(mem, 'md5') == sha(ref_mem, 'md5'),
               elf_sha256=sha(elf), bitstream=os.path.relpath(bit, ROOT) if os.path.exists(bit) else 'MISSING',
               bitstream_mtime=datetime.datetime.fromtimestamp(os.path.getmtime(bit)).isoformat(timespec='minutes')
               if os.path.exists(bit) else '',
               simulator=os.path.relpath(exe, ROOT),
               simulator_mtime=datetime.datetime.fromtimestamp(os.path.getmtime(exe)).isoformat(timespec='minutes'))
    if os.path.exists(uart):
        os.remove(uart)
    return row


def simref():
    jobs = [(v, b) for v in VARIANTS for b in BENCHES]
    with ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(lambda a: one(*a), jobs))
    with open(REF, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    bad = [r for r in rows if r['sim_verify'] != 'OK' or not r['image_matches_build']]
    print(f'wrote {REF}: {len(rows)} rows, {len(bad)} problems')
    for r in bad:
        print('  !!', r['variant'], r['benchmark'], r['sim_verify'], 'image_matches_build=', r['image_matches_build'])


def board_rows():
    got = {}
    for v in VARIANTS:
        for f in (f'{ROOT}/bitstream/embench/RV32/Done/{v}/embench_results.csv',
                  f'{ROOT}/bitstream/embench/RV32/{v}/embench_results.csv'):
            if os.path.exists(f):
                for r in csv.DictReader(open(f)):
                    got[(r['architecture'], r['benchmark'])] = (r, f)
                break
    return got


def compare():
    ref = {(r['variant'], r['benchmark']): r for r in csv.DictReader(open(REF))}
    board = board_rows()
    out = []
    for v in VARIANTS:
        for b in BENCHES:
            s = ref[(v, b)]
            if (v, b) not in board:
                out.append(dict(variant=v, benchmark=b, status='NO BOARD RESULT'))
                continue
            r, src = board[(v, b)]
            fc, fi, sc, si = int(r['cycles']), int(r['instret']), int(s['sim_cycles']), int(s['sim_instret'])
            out.append(dict(variant=v, benchmark=b, fpga_cycles=fc, sim_cycles=sc, fpga_instret=fi,
                            sim_instret=si, d_cycles=fc - sc, d_instret=fi - si,
                            cycles='EXACT' if fc == sc else 'MISMATCH',
                            instret='EXACT' if fi == si else 'MISMATCH',
                            fpga_verify=r['verify'], cpi=round(fc / fi, 4) if fi else '',
                            board_file=os.path.relpath(src, ROOT), status=''))
    keys = ['variant', 'benchmark', 'fpga_cycles', 'sim_cycles', 'fpga_instret', 'sim_instret',
            'd_cycles', 'd_instret', 'cycles', 'instret', 'fpga_verify', 'cpi', 'board_file', 'status']
    with open(OUT, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(out)
    exact = sum(1 for r in out if r.get('cycles') == 'EXACT' and r.get('instret') == 'EXACT')
    print(f'{exact} of {len(out)} rows EXACT in both counters -> {OUT}')
    for r in out:
        if r.get('status') or r.get('cycles') != 'EXACT' or r.get('instret') != 'EXACT':
            print('  ', r['variant'], r['benchmark'], r.get('status') or
                  f"d_cycles={r['d_cycles']} d_instret={r['d_instret']} verify={r['fpga_verify']}")


if __name__ == '__main__':
    {'simref': simref, 'compare': compare}[sys.argv[1]]()
