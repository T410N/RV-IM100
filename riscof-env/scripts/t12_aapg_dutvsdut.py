#!/usr/bin/env python3
"""T12: AAPG verification without the link-address artefact.

An address-matched ISS reference is not available on this machine (see the report):
Sail 0.6 has no --ram-base, its base is constant-folded into the shipped binary, the
source tree needs the Sail compiler to rebuild, and Spike is not installed.  Stock Sail
cannot execute a DUT-mapped ELF at all (it hangs: the program lives outside its RAM
window).

So the primary metric becomes DUT-vs-DUT on the identical ROM image, which has no
artefact whatsoever: each variant's signature is compared word-by-word with its pool's
5-stage variant, which is RISCOF-clean (851/851 vs Sail) and carries none of the
control-flow defects found in T6.  Timed-out runs are never compared (their signature is
dumped however the run ended).

Outputs logs/t12_aapg_dutvsdut.csv and prints the per-variant summary.
"""
import csv, os, re, glob, sys

ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
POOL_REF = {'rv32i': 'RV32I_5SP', 'rv32im': 'RV32IM_5SP', 'rv64i': 'RV64I_5SP', 'rv64im': 'RV64IM_5SP'}


def sig(v, p):
    f = f'{ENV}/build/socs_{v}/aapg/{p}/dut.sig'
    return [l.strip() for l in open(f)] if os.path.exists(f) else None


def main():
    status = {(r['variant'].replace('socs_', ''), r['program']): r['status']
              for r in csv.DictReader(open(f'{ENV}/logs/aapg_results.csv'))}
    variants = sorted({m.group(1) for m in
                       (re.search(r'/build/socs_([^/]+)/aapg/', d) for d in glob.glob(f'{ENV}/build/socs_*/aapg/*/'))
                       if m})
    rows = []
    for v in variants:
        for d in sorted(glob.glob(f'{ENV}/build/socs_{v}/aapg/*/')):
            p = os.path.basename(d.rstrip('/'))
            pool = re.match(r'(rv\d+im|rv\d+i)', p).group(1)
            ref_v = POOL_REF[pool]
            st = status.get((v, p), '?')
            a, b = sig(v, p), sig(ref_v, p)
            if st == 'TIMEOUT' or status.get((ref_v, p)) == 'TIMEOUT':
                verdict, ndiff = ('TIMEOUT (not compared)' if st == 'TIMEOUT' else 'reference timed out'), ''
            elif a is None or b is None:
                verdict, ndiff = 'missing signature', ''
            elif v == ref_v:
                verdict, ndiff = 'reference', 0
            else:
                ndiff = sum(x != y for x, y in zip(a, b))
                verdict = 'IDENTICAL to 5SP' if ndiff == 0 else f'DIFFERS from 5SP'
            rows.append(dict(variant=v, program=p, pool=pool, reference=ref_v,
                             status_vs_sail=st, words_differing_vs_5SP=ndiff, verdict=verdict))
    out = f'{ENV}/logs/t12_aapg_dutvsdut.csv'
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    print(f'{len(rows)} runs -> {out}\n')
    print(f"{'variant':24s} {'identical':>10s} {'differs':>8s} {'timeout':>8s} {'ref':>4s}   (of 20)   vs Sail: MATCH/MISMATCH/TIMEOUT")
    for v in variants:
        rs = [r for r in rows if r['variant'] == v]
        ident = sum(r['verdict'] == 'IDENTICAL to 5SP' for r in rs)
        diff = sum(r['verdict'].startswith('DIFFERS') for r in rs)
        to = sum('TIMEOUT' in r['verdict'] for r in rs)
        ref = sum(r['verdict'] == 'reference' for r in rs)
        s = [sum(r['status_vs_sail'] == k for r in rs) for k in ('MATCH', 'MISMATCH', 'TIMEOUT')]
        print(f'{v:24s} {ident:>10d} {diff:>8d} {to:>8d} {ref:>4d}            {s[0]}/{s[1]}/{s[2]}')
    print('\nPrograms where a completing run differs from its 5SP reference:')
    bad = [r for r in rows if r['verdict'].startswith('DIFFERS')]
    for r in bad:
        print(f"   {r['variant']} {r['program']}: {r['words_differing_vs_5SP']} of 4096 words")
    if not bad:
        print('   none')


if __name__ == '__main__':
    main()
