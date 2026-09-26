#!/usr/bin/env python3
"""Generate, reference-check, build and simulate micro-kernels on all 16 SoCs."""
import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ENV = HERE.parent
sys.path.insert(0, str(ENV / 'scripts'))
import prepare_rtl as prep
from variants import soc_variants
from reference import execute

OUT = HERE / 'out'
PAD = 'addi x29,x0,31'
GUARD = [PAD] * 16


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, log=None, cwd=None):
    result = subprocess.run([str(x) for x in args], cwd=cwd, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if log: Path(log).write_text(result.stdout)
    if result.returncode:
        raise RuntimeError('command failed: %s\n%s' % (' '.join(map(str,args)), result.stdout[-4000:]))
    return result.stdout


def kernels(xlen, ext):
    """Every definition returns a static body; actual instruction counts are oracle-derived."""
    cases = []
    def add(name, family, body, **kw):
        cases.append(dict(name=name, family=family, body=body, **kw))
    independent = [f'add x{5+i%8},x17,x18' for i in range(128)]
    add('alu_independent','alu',independent)
    add('alu_dependency_chain','alu_raw',['add x5,x5,x18']*128,events=128)
    for op in ['add','xor'] + (['addw'] if xlen == 64 else []):
        for gap in range(5):
            for dep in (True,False):
                block = [f'{op} x5,x17,x18'] + [PAD]*gap + [f'{op} x8,x{5 if dep else 10},x19']
                block += [PAD]*(8-len(block))
                add(f'{op}_gap{gap}_{"dep" if dep else "control"}', 'alu_raw', block*16,
                    gap=gap, events=16)
    for gap in range(5):
        for dep in (True,False):
            block=['lw x5,0(x20)']+[PAD]*gap+[f'add x8,x{5 if dep else 10},x19']
            block += [PAD]*(8-len(block))
            add(f'load_gap{gap}_{"dep" if dep else "control"}','load_use',block*16,gap=gap,events=16)
    for kind in ('load','store','mixed'):
        for density in (0,25,50,75,100):
            body=[]
            for i in range(128):
                active = (i%4)*25 < density
                if not active: ins=independent[i]
                elif kind=='load' or (kind=='mixed' and i%2==0): ins=f'lw x{5+i%8},{(i%64)*4}(x20)'
                else: ins=f'sw x15,{(i%64)*4}(x20)'
                body.append(ins)
            add(f'memory_{kind}_{density}','memory',body,density=density)
    for gap in (0,1,2,4):
        block=['lw x5,0(x20)']+[PAD]*gap+['sw x5,128(x20)']
        block += [PAD]*(8-len(block))
        add(f'copy_gap{gap}','store_forward',block*16,gap=gap,events=16)
    for alias in ('same','different'):
        block=['sw x15,0(x20)',f'lw x5,{0 if alias=="same" else 4}(x20)']+[PAD]*6
        add(f'store_load_{alias}','store_wait',block*16,events=16)
    patterns={'nt':[False], 'taken':[True], 'alternate':[True,False], 'ttnt':[True,True,False,True]}
    for pattern,values in patterns.items():
        for gap in (0,8):
            body=[]
            for i in range(64):
                branch='beq' if values[i%len(values)] else 'bne'
                body += [f'{branch} x0,x0,1f',PAD,'1:']+[PAD]*gap
            add(f'branch_{pattern}_gap{gap}','branch',body,events=64,warm=True)
    # T9 matched-pair misprediction kernels.  Every branch targets the next
    # instruction, so taken and not-taken retire the identical stream: a pair with
    # the same number of taken branches differs only in predictability, and
    #     penalty = d(cycles) / d(mispredictions).
    def brseq(dirs, gap, back=False):
        body = []
        for i, t in enumerate(dirs):
            op = 'beq' if t else 'bne'
            if back:                      # backward branch over one pad, same stream either way
                body += ['1:', f'{op} x0,x0,2f', '2:'] + [PAD] * gap
            else:
                body += [f'{op} x0,x0,1f', '1:'] + [PAD] * gap
        return body
    N = 64
    half = [True, False] * (N // 2)                    # alternating
    blocked = [True] * (N // 2) + [False] * (N // 2)   # same taken count, grouped
    t7nt1 = ([True] * 7 + [False]) * (N // 8)          # isolated not-taken among taken
    nt7t1 = ([False] * 7 + [True]) * (N // 8)          # isolated taken among not-taken
    for tag, dirs in (('alt', half), ('blocked', blocked), ('t7nt1', t7nt1), ('nt7t1', nt7t1),
                      ('allt', [True] * N), ('allnt', [False] * N)):
        for gap in (0, 4):
            add(f'mispredict_fwd_{tag}_gap{gap}', 'mispredict', brseq(dirs, gap),
                events=N, warm=True, gap=gap)
        add(f'mispredict_back_{tag}_gap0', 'mispredict', brseq(dirs, 0, back=True),
            events=N, warm=True, gap=0)
    for kind in ('sequential','jal','jalr'):
        body=[]
        for i in range(32):
            if kind=='jalr':
                body += ['auipc x5,0','addi x5,x5,24']+[PAD]*2+['jalr x0,0(x5)',PAD]
            elif kind=='jal': body += [PAD]*4+['jal x0,1f',PAD,'1:']
            else: body += [PAD]*5
        add(f'jump_{kind}','jump',body,events=32)
    if ext=='IM':
        for op in ['mul','div','divu','rem'] + (['mulw','divw','divuw','remw'] if xlen==64 else []):
            for stride in (1,4,16):
                body=[f'{op} x{5+i%8},x17,x18' if i%stride==0 else independent[i] for i in range(128)]
                add(f'{op}_every{stride}','muldiv',body,events=128//stride)
        for op in ('mul','div'):
            # Reload nontrivial operands each group; consumer follows immediately.
            body=([f'{op} x5,x17,x18','add x8,x5,x19']+[PAD]*6)*16
            add(f'{op}_result_use','muldiv_use',body,events=16)
        # Corner operands kept separate from throughput cases.
        for op in ['mulh','mulhu','mulhsu','div','divu','rem','remu'] + (['divw','divuw','remw','remuw'] if xlen==64 else []):
            minimum = 'x23' if op.endswith('w') else 'x21'
            body=[f'{op} x5,x17,x0',f'{op} x6,{minimum},x22',f'{op} x7,x22,x18']+[PAD]*5
            add(f'corner_{op}','correctness',body*4,events=12)
    mixed=['lw x5,0(x20)','add x6,x5,x17','sw x6,128(x20)',
           'xor x7,x6,x18','bne x0,x0,1f',PAD,'1:',
           'mul x8,x17,x18' if ext=='IM' else 'add x8,x17,x18',PAD]
    add('mixed_embedded','mixed',mixed*16)
    return cases


def source(case, reps, xlen):
    setup=['.option norvc','.option norelax','.section .text','.global _start','_start:']
    setup += [f'addi x{i},x0,{i+2}' for i in range(1,32)]
    setup += ['lui x20,0x10000','lui x17,0x12345','addi x17,x17,165','addi x18,x0,7',
              'addi x21,x0,1',f'slli x21,x21,{xlen-1}','addi x22,x0,-1','lui x23,0x80000']
    # Distinct seeds make a dropped store or copy observable on readback.
    setup += [ins for i in range(64) for ins in (f'sw x14,{i*4}(x20)','addi x14,x14,1')]
    # Branch warmup has the same pattern and loop exit; report cold-reset seeds.
    if case.get('warm'):
        setup += ['li x30,16','warm_loop:']+case['body']+['addi x30,x30,-1','bne x30,x0,warm_loop']
    setup += [f'li x30,{reps}']+GUARD+['addi x0,x0,0x701']+GUARD+['kernel_loop:']
    setup += case['body']+['addi x30,x30,-1','bne x30,x0,kernel_loop']+GUARD
    setup += ['addi x0,x0,0x702']+GUARD
    # Read every touched word back; hash checks memory effects outside timed ROI.
    setup += [f'lw x5,{i*4}(x20)' for i in range(64)]+GUARD+['addi x0,x0,0x703']+GUARD
    setup += ['lui x20,0x10010','addi x15,x0,1']+GUARD+['sw x15,0(x20)','halt:','jal x0,halt']
    return '\n'.join(setup)+'\n'


def generate(reps):
    images=[]
    for xlen in (32,64):
        for ext in ('I','IM'):
            for case in kernels(xlen,ext):
                folder=OUT/'images'/f'rv{xlen}{ext.lower()}'/case['name']
                folder.mkdir(parents=True,exist_ok=True)
                src=folder/'kernel.S'; elf=folder/'kernel.elf'; binary=folder/'kernel.bin'
                src.write_text(source(case,reps,xlen))
                command(['riscv64-unknown-elf-gcc',f'-march=rv{xlen}{ext.lower()}',
                         '-mabi='+('ilp32' if xlen==32 else 'lp64'),'-nostdlib','-nostartfiles',
                         '-Wl,-Ttext=0','-Wl,--no-relax','-Wl,-e,_start',src,'-o',elf])
                command(['riscv64-unknown-elf-objcopy','-O','binary','-j','.text',elf,binary])
                data=binary.read_bytes()
                if len(data)>32768: raise ValueError('kernel exceeds original 32 KiB ROM')
                (folder/'kernel.hex').write_text(''.join(f'{int.from_bytes(data[i:i+4],"little"):08x}\n' for i in range(0,len(data),4)))
                (folder/'kernel.dis').write_text(command(['riscv64-unknown-elf-objdump','-d',elf]))
                expected=execute(data,xlen)
                meta={k:v for k,v in case.items() if k!='body'}
                meta.update(xlen=xlen,ext=ext,repetitions=reps,binary_sha256=sha(binary),
                            image=str(folder/'kernel.hex'),expected=expected)
                (folder/'expected.json').write_text(json.dumps(meta,indent=2)+'\n')
                images.append(meta)
            print(f'generated/reference-checked RV{xlen}{ext}',flush=True)
    (OUT/'images.json').write_text(json.dumps(images,indent=2)+'\n')
    return images


def monitor(v):
    src=Path(v['core_file']).read_text()
    hazard=(Path(v['dir'])/'Hazard_Unit.v').read_text()
    hmatch=re.search(r'HazardUnit\s+(\w+)\s*\(',src)
    h='core.'+hmatch.group(1)+'.'
    def signal(name,default="1'b0"):
        return 'core.'+name if prep.declared(src,name) else default
    mapping={
        'DIV':f'({signal("div_start")} || {signal("div_busy")})',
        'MUL':f'({signal("mul_start")} || {signal("mul_busy")})',
        'STORE':f'!({signal("write_done", "1\'b1")})',
        'OTHER':signal('pc_stall'), 'EXEC':"1'b0", 'LOAD':signal('load_use_hazard')}
    if 'ex_data_stall' in hazard:
        mapping['EXEC']=f'({h}ex_data_stall && core.EX_opcode != 7\'h03)'
        late_load = 'load_br_use_hazard' if 'load_br_use_hazard' in hazard else 'load_ex2_use_hazard'
        mapping['LOAD']=f'(({h}ex_data_stall && core.EX_opcode == 7\'h03) || {h}{late_load})'
    branch=signal('EX2_branch',signal('EX_branch'))
    mapping.update(BRANCH=f'({branch} && !core.EX_MEM_stall && !core.EX_MEM_flush)',
                   TAKEN=signal('branch_taken'),MISS=signal('branch_prediction_miss'))
    txt=(HERE/'monitor.v.in').read_text()
    for k,value in mapping.items(): txt=txt.replace('@'+k+'@',value)
    return txt,mapping


def build(v,jobs):
    # Separate build tree: existing architectural/Embench simulators are untouched.
    prep.ENV=str(OUT)
    out=Path(prep.prepare(v))
    top=out/'sim_top.v'
    txt,mapping=monitor(v)
    top.write_text(top.read_text().replace('\nendmodule\n','\n'+txt+'\nendmodule\n'))
    target=out.parent/'Vsim_top'
    files=[out/f for f in (out/'filelist.txt').read_text().splitlines()]
    includes=['-I'+str(out)]
    for p in (out/'headers',out/'modules',out/'modules/headers'):
        if p.is_dir(): includes.append('-I'+str(p))
    cmd=[shutil.which('verilator'),'--cc','--exe','--build','-j',str(jobs),
         '--top-module','sim_top','--Mdir',out.parent/'obj_dir','-O3',
         '-CFLAGS','-O2 -std=c++17','-Wno-fatal','-Wno-WIDTHEXPAND','-Wno-WIDTHTRUNC',
         '-Wno-UNOPTFLAT','-Wno-CASEINCOMPLETE','-Wno-LATCH','-Wno-MULTIDRIVEN',
         *includes,*files,ENV/'sim/tb_sim_top.cpp','-o',target]
    print('building '+v['name'],flush=True)
    command(cmd,OUT/'logs'/('build_'+v['name']+'.log'))
    sources={str(p):sha(p) for p in sorted(Path(v['dir']).rglob('*')) if p.suffix in ('.v','.vh')}
    (out.parent/'provenance.json').write_text(json.dumps(dict(variant=v,sources=sources,
        counter_mapping=mapping,command=list(map(str,cmd)),simulator_sha256=sha(target)),indent=2)+'\n')
    print('built '+v['name'],flush=True)


def run_one(v,case):
    folder=OUT/'runs'/v['name']/case['name']; folder.mkdir(parents=True,exist_ok=True)
    profile=folder/'profile.txt'
    cmd=[str(OUT/'build'/v['name']/'Vsim_top'),'+HEX='+case['image'],
         '+MICRO='+str(profile),'+MAX_CYCLES=30000000']
    start=time.monotonic()
    proc=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
    (folder/'simulation.log').write_text(proc.stdout)
    values={}
    if profile.exists():
        values={k:int(val) for k,val in (line.split() for line in profile.read_text().splitlines())}
    errors=[]
    if proc.returncode: errors.append('exit_'+str(proc.returncode))
    for k,expected in case['expected'].items():
        if values.get(k)!=expected: errors.append(f'{k}:expected={expected},got={values.get(k)}')
    if values.get('markers')!=3: errors.append('markers')
    if values.get('occupancy_8')!=values.get('branch'): errors.append('resolved_branch_count')
    if values.get('cycles',0)!=values.get('retired',0)+sum(values.get(f'empty_{i}',0) for i in range(8)):
        errors.append('cycle_accounting')
    if values.get('cycles',0)!=sum(values.get(f'occupancy_{i}',0) for i in range(8)):
        errors.append('occupancy_accounting')
    row=dict(variant=v['name'],kernel=case['name'],family=case['family'],xlen=v['xlen'],
             status='FAIL' if errors else 'PASS',errors=';'.join(errors),
             binary_sha256=case['binary_sha256'],repetitions=case['repetitions'],
             wall_seconds=round(time.monotonic()-start,3),**values)
    if values.get('retired'):
        row.update(cpi=values['cycles']/values['retired'],ipc=values['retired']/values['cycles'])
    (folder/'result.json').write_text(json.dumps(row,indent=2)+'\n')
    return row


def report(rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/'results.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    failed=[r for r in rows if r['status']!='PASS']
    text=['# Micro-kernel simulation results','',f'{len(rows)-len(failed)}/{len(rows)} runs passed functional and counter checks.','',
          'Cycles and CPI refer only to the retirement-bounded region. Occupancy buckets are not additive CPI penalties.',
          '', '| Variant | Runs | Pass | Independent ALU CPI | RAW gap 0 CPI | Load gap 0 CPI |',
          '|---|---:|---:|---:|---:|---:|']
    for variant in dict.fromkeys(r['variant'] for r in rows):
        subset=[r for r in rows if r['variant']==variant]
        def cpi(name):
            r=next((r for r in subset if r['kernel']==name),{})
            return f'{r["cpi"]:.4f}' if r.get('status')=='PASS' else '—'
        text.append(f'| {variant} | {len(subset)} | {sum(r["status"]=="PASS" for r in subset)} | {cpi("alu_independent")} | {cpi("add_gap0_dep")} | {cpi("load_gap0_dep")} |')
    text += ['','## Failed runs','']+[f'- {r["variant"]}/{r["kernel"]}: {r["errors"]}' for r in failed]
    if not failed: text+=['None.']
    (OUT/'REPORT.md').write_text('\n'.join(text)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['all','generate','build','run'],default='all')
    parser.add_argument('--repetitions',type=int,default=1024)
    parser.add_argument('--jobs',type=int,default=4)
    parser.add_argument('--variants',nargs='*')
    parser.add_argument('--kernels',nargs='*')
    args=parser.parse_args()
    (OUT/'logs').mkdir(parents=True,exist_ok=True)
    variants=[v for v in soc_variants() if not args.variants or v['name'] in args.variants]
    if not variants: parser.error('no matching variants')
    if args.phase in ('all','generate'): images=generate(args.repetitions)
    elif args.phase=='run': images=json.loads((OUT/'images.json').read_text())
    else: images=[]
    if args.phase in ('all','build'):
        for v in variants: build(v,args.jobs)
    if args.phase in ('all','run'):
        tasks=[(v,c) for v in variants for c in images if c['xlen']==v['xlen'] and c['ext']==v['ext'] and (not args.kernels or c['name'] in args.kernels)]
        rows=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures=[pool.submit(run_one,v,c) for v,c in tasks]
            for future in concurrent.futures.as_completed(futures):
                row=future.result(); rows.append(row)
                if row['status']!='PASS' or len(rows)%25==0:
                    print(f'{len(rows)}/{len(tasks)} {row["variant"]} {row["kernel"]} {row["status"]} {row["errors"]}',flush=True)
        rows.sort(key=lambda r:(r['variant'],r['kernel']))
        report(rows)
        print(f'Results: {OUT / "REPORT.md"}',flush=True)
        return int(any(r['status']!='PASS' for r in rows))
    return 0


if __name__=='__main__':
    sys.exit(main())
