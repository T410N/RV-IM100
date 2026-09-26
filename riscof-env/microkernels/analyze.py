#!/usr/bin/env python3
"""Derive matched-pair penalties and publication figures from checked runs."""
import csv
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
OUT=HERE/'out'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-plots',action='store_true',help='write analysis and provenance without Matplotlib')
    args=parser.parse_args()
    rows=list(csv.DictReader((OUT/'results.csv').open()))
    lookup={(r['variant'],r['kernel']):r for r in rows}
    images=json.loads((OUT/'images.json').read_text())
    meta={(r['xlen'],r['ext'],r['name']):r for r in images}
    penalties=[]
    for r in rows:
        if not r['kernel'].endswith('_dep'): continue
        control=lookup.get((r['variant'],r['kernel'][:-4]+'_control'))
        if not control: continue
        ext='IM' if 'IM_' in r['variant'] else 'I'
        m=meta[int(r['xlen']),ext,r['kernel']]
        events=m['events']*m['repetitions']
        valid=r['status']==control['status']=='PASS' and r['retired']==control['retired'] and r['mispred']==control['mispred']
        penalties.append(dict(variant=r['variant'],kernel=r['kernel'],gap=m['gap'],
            events=events,status='VALID' if valid else 'INVALID',
            delta_cycles=int(r.get('cycles') or 0)-int(control.get('cycles') or 0),
            cycles_per_dependency=(int(r['cycles'])-int(control['cycles']))/events if valid else '',
            delta_load_occupancy=int(r.get('occupancy_3') or 0)-int(control.get('occupancy_3') or 0),
            delta_exec_occupancy=int(r.get('occupancy_4') or 0)-int(control.get('occupancy_4') or 0)))
    with (OUT/'dependency_penalties.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(penalties[0])); w.writeheader(); w.writerows(penalties)
    variants=list(dict.fromkeys(r['variant'] for r in rows))
    text=['# Measured dependency penalties','',
          'Matched binaries have equal retired instruction counts and branch-miss counts. Each cell is extra cycles per dependency, relative to the matched independent consumer.',
          '', '| Variant | ALU gap 0 | ALU gap 1 | Load gap 0 | Load gap 1 | Load gap 2 |',
          '|---|---:|---:|---:|---:|---:|']
    for v in variants:
        def val(kernel):
            p=next((p for p in penalties if p['variant']==v and p['kernel']==kernel),{})
            return f'{p["cycles_per_dependency"]:.4f}' if p.get('status')=='VALID' else '—'
        text.append('| '+v+' | '+' | '.join(val(k) for k in ('add_gap0_dep','add_gap1_dep','load_gap0_dep','load_gap1_dep','load_gap2_dep'))+' |')
    text+=['','These differences measure the tested instruction pairs. They do not establish penalties for all opcodes or dependency types. Unoptimized/optimized naming follows the existing repository; this campaign does not certify a twelve-change RTL ablation.','',
           '## Branch and jump observations','',
           '| Variant | Taken branch: excess cycles/retired branch | Taken branch misses | JAL: excess cycles/jump | JALR: excess cycles/jump |',
           '|---|---:|---:|---:|---:|']
    for v in variants:
        def excess(name,key):
            r=lookup.get((v,name),{})
            return f'{(int(r["cycles"])-int(r["retired"]))/int(r[key]):.4f}' if r.get('status')=='PASS' and int(r[key]) else '—'
        br=lookup.get((v,'branch_taken_gap8'),{})
        text.append(f'| {v} | {excess("branch_taken_gap8","branch")} | {br.get("mispred","—")} | {excess("jump_jal","jump")} | {excess("jump_jalr","jump")} |')
    text+=['','Excess cycles include loop overhead, operand hazards, and pipeline recovery. These ratios are descriptive, not isolated misprediction or refill penalties. Branch patterns are generated at multiple static sites sharing the global counter; the outer loop also trains the predictor.','',
           '## Matched direct-jump cost','',
           'JAL and the sequential control retire equal instruction counts and execute the same loop branches. Where both checks pass and branch-miss counts agree, their difference measures the incremental cost of replacing one independent instruction with JAL to a nearby target. It includes all redirect/recovery work, without claiming to separate front-end refill from branch resolution.','',
           '| Variant | Extra cycles/JAL |', '|---|---:|']
    for v in variants:
        a=lookup.get((v,'jump_jal'),{}); b=lookup.get((v,'jump_sequential'),{})
        valid=a.get('status')==b.get('status')=='PASS' and a['retired']==b['retired'] and a['mispred']==b['mispred']
        value=f'{(int(a["cycles"])-int(b["cycles"]))/int(a["jump"]):.4f}' if valid else '—'
        text.append(f'| {v} | {value} |')
    text+=['','## Arithmetic and store service cost','',
           'Extra cycles per instruction relative to the independent-ALU body with equal retired counts and branch misses. Normal arithmetic uses the fixed nontrivial operands documented in the assembly; corner operands are separate tests. A dash means unsupported or unmatched.','',
           '| Variant | MUL | DIV | DIVW | SW |', '|---|---:|---:|---:|---:|']
    for v in variants:
        base=lookup.get((v,'alu_independent'),{})
        def cost(kernel,event):
            r=lookup.get((v,kernel),{})
            good=r.get('status')==base.get('status')=='PASS' and r['retired']==base['retired'] and r['mispred']==base['mispred']
            return f'{(int(r["cycles"])-int(base["cycles"]))/int(r[event]):.4f}' if good and int(r[event]) else '—'
        text.append('| '+v+' | '+' | '.join(cost(k,e) for k,e in (('mul_every1','mul'),('div_every1','div'),('divw_every1','div'),('memory_store_100','store')))+' |')
    text+=['',
           '## Provenance','', 'See `provenance/` for source hashes, per-variant counter mappings, build commands, simulator hashes, tool versions, and generator hashes. Generated assembly, disassembly, ELF and binary files are in `images/`; regenerate them with the documented command.']
    (OUT/'ANALYSIS.md').write_text('\n'.join(text)+'\n')
    provenance=OUT/'provenance'; provenance.mkdir(exist_ok=True)
    for file in (OUT/'build').glob('*/provenance.json'):
        (provenance/(file.parent.name+'.json')).write_text(file.read_text())
    info={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.suffix in ('.py','.in')}
    info['tools']={tool:subprocess.check_output([tool,'--version'],text=True).splitlines()[0] for tool in ('riscv64-unknown-elf-gcc','verilator')}
    info['results_sha256']=hashlib.sha256((OUT/'results.csv').read_bytes()).hexdigest()
    (provenance/'campaign.json').write_text(json.dumps(info,indent=2)+'\n')
    if args.no_plots:
        print(f'Wrote {len(penalties)} matched pairs, analysis and provenance.')
        return
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(10,7),sharex=True)
    for i,xlen in enumerate((32,64)):
        for j,prefix in enumerate(('add','load')):
            ax=axes[i,j]
            groups={}
            for v in variants:
                if f'RV{xlen}IM_' not in v: continue
                ps=sorted((p for p in penalties if p['variant']==v and p['kernel'].startswith(prefix+'_') and p['status']=='VALID'),key=lambda p:p['gap'])
                key=tuple((p['gap'],p['cycles_per_dependency']) for p in ps)
                if key: groups.setdefault(key,[]).append(v.split('IM_',1)[1])
            for points,names in groups.items():
                # Group exactly coincident curves instead of hiding six lines.
                label=', '.join(names)
                if len(names)>3: label=('5SP, ' if '5SP' in names else '')+'6SP, all 7SP variants'
                elif len(names)==3: label='6SP / all 7SP variants'
                elif names==['8SP','8SP_withoutOpt']: label='8SP, with/without Opt'
                ax.plot([p[0] for p in points],[p[1] for p in points],marker='o',label=label)
            ax.set_title(f'RV{xlen}: {"ALU" if prefix=="add" else "load"} → ALU dependency')
            ax.set_ylabel('Extra cycles / dependency'); ax.grid(alpha=.25); ax.set_xticks(range(5))
            ax.legend(fontsize=7,loc='upper right')
            if i==1: ax.set_xlabel('Independent instructions between producer and consumer')
    fig.tight_layout()
    fig.savefig(OUT/'dependency_penalties.pdf')
    fig.savefig(OUT/'dependency_penalties.png',dpi=180)
    print(f'Wrote {len(penalties)} matched pairs, analysis, provenance and figures.')


if __name__=='__main__': main()
