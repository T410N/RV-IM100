#!/usr/bin/env python3
"""T4: one authoritative SAIF power table, plus recomputed normalised metrics.

Per build (32):
  * power on the FINAL implementation with the captured activity (saif_recost/<tag>),
    every category, and read_saif coverage ("Design nets matched = a of b")
  * vectorless on the same implementation, for the delta
  * core-attributable dynamic = total dynamic - PLL - I/O   (from the category table)
  * core instance dynamic (hierarchy row of the CPU instance, which contains its
    memories) and the same without instruction/data memory
  * capture validity: core toggle count from kernel.saif vs its sibling image, the
    capture window from logs/saif_window_map_try0.csv
  * a v2 re-capture (saif_v2/<tag>) replaces a row when present and valid

Normalised metrics use TRUE CoreMark it/s (T3) and measured Dhrystone/s:
  CM/W, mJ per CoreMark iteration, uJ per Dhrystone iteration, and the same per
  core-attributable watt.

usage: saif_recost_collect.py <corrected_coremark.csv> <master.xlsx> <outdir>
"""
import csv, os, re, sys, glob
ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def cat(t, label):
    m = re.search(rf'^\|\s*{re.escape(label)}\s*\|\s*([<0-9.]+)', t, re.M)
    if not m:
        return 0.0
    return 0.0 if m.group(1).startswith('<') else float(m.group(1))


def hier(t):
    rows = {}
    for m in re.finditer(r'^\|(\s*)(\S+)\s*\|\s*([<0-9.]+)\s*\|', t, re.M):
        depth = len(m.group(1)) // 2
        v = 0.0 if m.group(3).startswith('<') else float(m.group(3))
        rows.setdefault((depth, m.group(2)), v)
    return rows


def power_block(d, rpt='power_saif.rpt'):
    t = open(f'{d}/{rpt}').read()
    r = dict(total=cat(t, 'Total On-Chip Power (W)'), dynamic=cat(t, 'Dynamic (W)'),
             static=cat(t, 'Device Static (W)'), clocks=cat(t, 'Clocks'), signals=cat(t, 'Signals'),
             logic=cat(t, 'Slice Logic'), bram=cat(t, 'Block RAM'), dsp=cat(t, 'DSPs'),
             pll=cat(t, 'PLL'), io=cat(t, 'I/O'))
    return r


def coverage(d):
    for f in (f'{d}/vivado.log', f'{d}/power.log'):
        if os.path.exists(f):
            m = re.search(r'Design nets matched = (\d+) of (\d+)', open(f).read())
            if m:
                return int(m.group(1)), int(m.group(2))
    return None, None


def core_toggles(saif):
    """Sum of toggle counts on nets inside the CPU instance (tb_saif/dut/rv*...).
    Scope is tracked by true parenthesis depth: a NET block's closing ')' must
    not pop an INSTANCE."""
    stack, depth, tc = [], 0, 0
    for line in open(saif):
        m = re.match(r'\s*\(INSTANCE\s+(\S+)', line)
        if m:
            stack.append((m.group(1), depth + 1))
        m2 = re.search(r'\(TC (\d+)\)\)', line)
        if m2 and len(stack) >= 3 and re.match(r'rv\d+i', stack[2][0]):
            tc += int(m2.group(1))
        depth += line.count('(') - line.count(')')
        while stack and depth < stack[-1][1]:
            stack.pop()
    return tc


def main():
    cmcsv, master, out = sys.argv[1:4]
    true_cm = {r['variant']: float(r['TRUE it/s = f / cycles-per-iter']) for r in csv.DictReader(open(cmcsv))}
    import openpyxl
    wb = openpyxl.load_workbook(master, data_only=True)
    dhry, luts = {}, {}
    for arch in ('RV32', 'RV64'):
        ws = wb[f'{arch} SoC and FPGA']
        for r in ws.iter_rows(min_row=3, max_row=10, values_only=True):
            if r[1]:
                dhry[arch + r[1]] = r[2]
                luts[arch + r[1]] = r[19]
    win = {(r['variant'], r['bench']): r for r in csv.DictReader(open(f'{ENV}/logs/saif_window_map_try0.csv'))}
    rows = []
    for d in sorted(glob.glob(f'{ENV}/saif_recost/*_*/')):
        tag = os.path.basename(d.rstrip('/'))
        v, b = tag.rsplit('_', 1)
        if not os.path.exists(f'{d}/power_saif.rpt'):
            continue
        src, dd = 'v1 capture re-costed on final impl', d
        v2 = f'{ENV}/saif_v2/{tag}'
        if os.path.exists(f'{v2}/power_saif.rpt'):
            src, dd = 'v2 capture on final impl', v2
        p = power_block(dd)
        vl = power_block(dd, 'power_vectorless.rpt') if os.path.exists(f'{dd}/power_vectorless.rpt') else power_block(d, 'power_vectorless.rpt')
        h = hier(open(f'{dd}/power_saif_hier.rpt').read())
        core = next((val for (dep, n), val in h.items() if dep == 1 and re.match(r'rv\d+i', n)), None)
        mem = sum(val for (dep, n), val in h.items() if dep == 2 and n in ('data_memory', 'instruction_memory'))
        a, n = coverage(dd)
        saif = f'{dd}/kernel.saif' if os.path.exists(f'{dd}/kernel.saif') else f'{ENV}/saif/{tag}/kernel.saif'
        tc = core_toggles(saif)
        w = win.get((v, b), {})
        row = dict(variant=v, bench=b, source=src, **{f'saif_{k}': round(x, 4) for k, x in p.items()},
                   vectorless_total=vl['total'], vectorless_dynamic=vl['dynamic'],
                   dyn_vs_vectorless_pct=round(100 * (p['dynamic'] - vl['dynamic']) / vl['dynamic'], 1) if vl['dynamic'] else '',
                   core_attributable_dyn=round(p['dynamic'] - p['pll'] - p['io'], 4),
                   core_instance_dyn=core, core_instance_dyn_excl_mem=round(core - mem, 4) if core is not None else '',
                   nets_matched=a, nets_total=n, coverage_pct=round(100 * a / n, 1) if a else '',
                   core_toggle_count=tc, window_cycles=f"{w.get('start_cycle','')}-{w.get('end_cycle','')}",
                   window_instret=f"{w.get('instret_start','')}-{w.get('instret_end','')}",
                   window_functions=w.get('top_functions', ''))
        rows.append(row)
    # validity: a capture whose core toggles are < 25% of its sibling image's is flagged
    by = {(r['variant'], r['bench']): r for r in rows}
    for r in rows:
        sib = by.get((r['variant'], 'dhrystone' if r['bench'] == 'coremark' else 'coremark'))
        ratio = r['core_toggle_count'] / sib['core_toggle_count'] if sib and sib['core_toggle_count'] else None
        r['core_toggles_vs_sibling'] = round(ratio, 3) if ratio else ''
        r['valid'] = 'INVALID: core idle in window' if ratio is not None and ratio < 0.25 else 'ok'
    os.makedirs(out, exist_ok=True)
    with open(f'{out}/T4_saif_authoritative.csv', 'w', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
    # normalised metrics
    nm = []
    for v in sorted({r['variant'] for r in rows}):
        cm, dh = by.get((v, 'coremark')), by.get((v, 'dhrystone'))
        its = true_cm.get(v)
        e = dict(variant=v, true_coremark_its=its, dhrystones_per_s=dhry.get(v), core_LUT=luts.get(v))
        if cm and its:
            e.update(cm_total_W=cm['saif_total'], cm_valid=cm['valid'],
                     CM_per_W=round(its / cm['saif_total'], 2), mJ_per_CM_iter=round(1000 * cm['saif_total'] / its, 4),
                     CM_per_W_core_attr=round(its / cm['core_attributable_dyn'], 2) if cm['core_attributable_dyn'] else '',
                     mJ_per_CM_iter_core_attr=round(1000 * cm['core_attributable_dyn'] / its, 4),
                     CM_per_kLUT_core=round(1000 * its / luts[v], 3) if luts.get(v) else '')
        if dh and dhry.get(v):
            e.update(dh_total_W=dh['saif_total'], dh_valid=dh['valid'],
                     uJ_per_Dhry_iter=round(1e6 * dh['saif_total'] / dhry[v], 4),
                     uJ_per_Dhry_iter_core_attr=round(1e6 * dh['core_attributable_dyn'] / dhry[v], 4))
        nm.append(e)
    keys = sorted({k for e in nm for k in e}, key=lambda k: list(nm[0]).index(k) if k in nm[0] else 99)
    with open(f'{out}/T4_normalized_metrics.csv', 'w', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=keys); wr.writeheader(); wr.writerows(nm)
    print(f'{len(rows)} builds -> {out}/T4_saif_authoritative.csv; {len(nm)} variants -> T4_normalized_metrics.csv')
    for r in rows:
        print(f"{r['variant']:22s} {r['bench']:9s} {r['saif_total']:.3f} dyn {r['saif_dynamic']:.3f} core-attr {r['core_attributable_dyn']:.3f} "
              f"cov {r['coverage_pct']}% tog/sib {r['core_toggles_vs_sibling']} {r['valid']} [{r['source'][:2]}]")


if __name__ == '__main__':
    main()
