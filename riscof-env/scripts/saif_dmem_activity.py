#!/usr/bin/env python3
"""T4 validity: data-memory activity in each captured SAIF.

A core spinning in _exit (or any idle loop) performs no loads or stores, so the
nets inside the data_memory instance barely toggle.  A core running CoreMark or
Dhrystone accesses data memory every few cycles.  Reports, per capture, the toggle
count inside data_memory (and inside the CPU instance for reference), normalised
per microsecond of window, so an idle capture stands out regardless of variant.
"""
import re, glob, os, sys, csv
ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def scan(saif):
    stack, depth = [], 0
    tot = {'core': 0, 'dmem': 0, 'imem': 0}
    dur = None
    for line in open(saif):
        if dur is None:
            m = re.search(r'\(DURATION\s+(\d+)\)', line)
            if m: dur = int(m.group(1))
        m = re.match(r'\s*\(INSTANCE\s+(\S+)', line)
        if m:
            stack.append((m.group(1), depth + 1))
        m2 = re.search(r'\(TC (\d+)\)\)', line)
        if m2 and len(stack) >= 3 and re.match(r'rv\d+i', stack[2][0]):
            tc = int(m2.group(1)); tot['core'] += tc
            names = [s[0] for s in stack[3:]]
            if 'data_memory' in names: tot['dmem'] += tc
            if 'instruction_memory' in names: tot['imem'] += tc
        depth += line.count('(') - line.count(')')
        while stack and depth < stack[-1][1]:
            stack.pop()
    us = (dur or 1) / 1e6          # TIMESCALE 1 ps
    return {k: v / us for k, v in tot.items()}, us

rows = []
for f in sorted(glob.glob(f'{ENV}/saif/*_*/kernel.saif')):
    tag = os.path.basename(os.path.dirname(f))
    r, us = scan(f)
    rows.append(dict(tag=tag, window_us=round(us, 1), core_TC_per_us=round(r['core']), dmem_TC_per_us=round(r['dmem']),
                     imem_TC_per_us=round(r['imem'])))
out = sys.argv[1] if len(sys.argv) > 1 else f'{ENV}/logs/saif_dmem_activity.csv'
with open(out, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for r in rows: print(f"{r['tag']:36s} core/us {r['core_TC_per_us']:>9d}  dmem/us {r['dmem_TC_per_us']:>8d}  imem/us {r['imem_TC_per_us']:>8d}")
