#!/usr/bin/env python3
"""T9: branch misprediction penalty from matched-pair micro-kernels.

Every branch in these kernels targets the next instruction, so taken and not-taken
retire the identical stream.  Kernels of one family therefore differ only in the
branch PATTERN: same instruction count, same branch count, and (for alt vs blocked)
the same number of taken branches.

Two independent estimates per variant and family:

  matched pair   penalty = (cycles(alt) - cycles(blocked)) / (miss(alt) - miss(blocked))
                 with the taken counts equal, so nothing else differs.

  least squares  cycles = a + b*taken + c*miss(NT->T) + d*miss(T->NT) fitted over all
                 six patterns (allt, allnt, alt, blocked, t7nt1, nt7t1); b is the cost
                 of a correctly predicted taken branch, c and d the two penalties.

Writes out/t9_mispredict_penalties.csv.
"""
import csv, os, itertools
HERE = os.path.dirname(os.path.abspath(__file__))


def lstsq(A, y):
    """Least squares by normal equations with Gaussian elimination (no numpy)."""
    n = len(A[0])
    M = [[sum(A[k][i] * A[k][j] for k in range(len(A))) for j in range(n)] +
         [sum(A[k][i] * y[k] for k in range(len(A)))] for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i]))
        if abs(M[p][i]) < 1e-9:
            return None
        M[i], M[p] = M[p], M[i]
        for r in range(n):
            if r != i:
                f = M[r][i] / M[i][i]
                for c in range(i, n + 1):
                    M[r][c] -= f * M[i][c]
    return [M[i][n] / M[i][i] for i in range(n)]


def main():
    rows = [r for r in csv.DictReader(open(f'{HERE}/out/results.csv'))
            if r['kernel'].startswith('mispredict') and r['status'] == 'PASS']
    by = {(r['variant'].replace('socs_', ''), r['kernel']): r for r in rows}
    variants = sorted({v for v, _ in by})
    fams = [('forward, gap 0', 'fwd', 'gap0'), ('forward, gap 4', 'fwd', 'gap4'), ('backward, gap 0', 'back', 'gap0')]
    out = []
    for v in variants:
        for label, kind, gap in fams:
            pats = ['allt', 'allnt', 'alt', 'blocked', 't7nt1', 'nt7t1']
            k = {p: by.get((v, f'mispredict_{kind}_{p}_{gap}')) for p in pats}
            if any(x is None for x in k.values()):
                continue
            g = lambda p, f: float(k[p][f])
            row = dict(variant=v, family=label,
                       retired_identical=len({k[p]['retired'] for p in pats}) == 1,
                       branches=int(g('alt', 'branch')))
            # matched pair: alt vs blocked
            dt = g('alt', 'taken') - g('blocked', 'taken')
            dm = g('alt', 'mispred') - g('blocked', 'mispred')
            row['pair_taken_delta'] = int(dt)
            row['pair_mispred_delta'] = int(dm)
            row['pair_penalty_cycles'] = round((g('alt', 'cycles') - g('blocked', 'cycles')) / dm, 3) if dm else ''
            # least squares over all six patterns
            A, y = [], []
            for p in pats:
                A.append([1.0, g(p, 'taken'), g(p, 'mispred_nt_to_t'), g(p, 'mispred_t_to_nt')])
                y.append(g(p, 'cycles'))
            sol = lstsq(A, y)
            if sol:
                a, b, c, d = sol
                row['taken_branch_cost'] = round(b, 3)
                row['penalty_nt_to_t'] = round(c, 3)
                row['penalty_t_to_nt'] = round(d, 3)
                resid = max(abs(sum(A[i][j] * sol[j] for j in range(4)) - y[i]) for i in range(len(y)))
                row['max_residual_cycles'] = round(resid, 1)
                row['max_residual_pct'] = round(100 * resid / max(y), 4)
            for p in pats:
                row[f'{p}_cycles'] = int(g(p, 'cycles'))
                row[f'{p}_mispred'] = int(g(p, 'mispred'))
            out.append(row)
    dst = f'{HERE}/out/t9_mispredict_penalties.csv'
    with open(dst, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)
    print(f'{len(out)} rows -> {dst}\n')
    hdr = f"{'variant':24s} {'family':16s} {'pair':>7s} {'NT->T':>7s} {'T->NT':>7s} {'taken':>7s} {'resid%':>7s}"
    print(hdr); print('-' * len(hdr))
    for r in out:
        print(f"{r['variant']:24s} {r['family']:16s} {r.get('pair_penalty_cycles',''):>7} "
              f"{r.get('penalty_nt_to_t',''):>7} {r.get('penalty_t_to_nt',''):>7} "
              f"{r.get('taken_branch_cost',''):>7} {r.get('max_residual_pct',''):>7}")


if __name__ == '__main__':
    main()
