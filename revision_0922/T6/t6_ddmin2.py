#!/usr/bin/env python3
"""T6 stage 2: shrink t6_min.hex further, over EVERY instruction that executes.

Stage 1 (t6_ddmin.py) only NOPed the PCs of the committed window, so original
code the reduced program falls through into (0x5f3c-0x5fa4) was left intact.
Here every non-NOP word between the entry jump target and the failing branch is
a candidate, and the oracle is architectural, not "ref passes":

    DUT (RV32IM_7SP) shows a P1/P3 violation (cf_monitor.py)  and
    REF (RV32IM_5SP) shows none

so a reduction that merely changes the correct outcome is rejected.
"""
import os, subprocess, json

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.abspath(os.path.join(HERE, '..', '..'))
TMP = os.environ.get('CFTMP', '/tmp/rv-im100')
NOP = 0x13
LO, BR = 0x5d30, 0x6014


def mon(v, words, tag):
    h = f'{TMP}/dd2_{tag}.hex'
    open(h, 'w').write(''.join(f'{w:08x}\n' for w in words))
    r = subprocess.run(['/tmp/xlsxenv/bin/python', f'{ENV}/scripts/cf_monitor.py', v, h, h, '30000'],
                       capture_output=True, text=True, env=dict(os.environ, CFTMP=TMP))
    d = json.loads(r.stdout)
    return d['violations'] + d['branch_outcome_errors'], d


def ok(words):
    dv, _ = mon('RV32IM_7SP', words, 'dut')
    if not dv:
        return False
    rv, _ = mon('RV32IM_5SP', words, 'ref')
    return rv == 0


def main():
    base = [int(w, 16) for w in open(f'{HERE}/t6_min.hex').read().split()]
    assert ok(base), 'stage-1 image does not satisfy the architectural oracle'
    cand = [a for a in range(LO, BR, 4) if base[a // 4] != NOP]
    print('candidates', len(cand), flush=True)

    def img(keep):
        w = list(base)
        for a in cand:
            if a not in keep:
                w[a // 4] = NOP
        return w
    cur = list(cand)
    n = 2
    while len(cur) >= 2:
        chunk = max(1, len(cur) // n)
        red = False
        for i in range(0, len(cur), chunk):
            t = cur[:i] + cur[i + chunk:]
            if ok(img(set(t))):
                cur, n, red = t, max(n - 1, 2), True
                print('  kept', len(cur), flush=True)
                break
        if not red:
            if n >= len(cur):
                break
            n = min(len(cur), 2 * n)
    final = img(set(cur))
    open(f'{HERE}/t6_min2.hex', 'w').write(''.join(f'{w:08x}\n' for w in final))
    res = {}
    for v in ['RV32IM_5SP', 'RV32IM_6SP', 'RV32IM_7SP', 'RV32IM_7SP_BRAM', 'RV32IM_7SP_BRAM_Opt',
              'RV32IM_8SP_withoutOpt', 'RV32IM_8SP']:
        c, d = mon(v, final, 'r' + v)
        res[v] = dict(violations=c, first_branch_error=(d['first_branch_errors'] or [None])[0])
    kept = [(hex(a), f'{base[a // 4]:08x}') for a in cur] + [(hex(BR), f'{base[BR // 4]:08x}')]
    json.dump(dict(kept=kept, results=res), open(f'{HERE}/t6_ddmin2.json', 'w'), indent=1)
    print('kept:', kept)
    for v, r in res.items():
        print(' ', v, r['violations'], r['first_branch_error'])


if __name__ == '__main__':
    main()
