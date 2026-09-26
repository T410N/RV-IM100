#!/usr/bin/env python3
"""Cross-check the master workbook's SoC rows against the Vivado reports.

For every one of the 32 SoC builds, reads logs/final_impl/<variant>_<bench>/
{utilization,timing,power}.rpt -- the reports of the implementation the rows
claim to describe -- and compares LUT, LUTRAM, FF, BRAM, DSP, IO, PLL, SoC Fmax
and every vectorless power component with the workbook cell.

Writes logs/soc_report_audit.csv (report values, one row per build, with the
report timestamps and md5s for provenance) and prints every disagreement.
"""
import csv, hashlib, os, re, sys
import openpyxl

ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ROOT = os.path.dirname(ENV)
FI = f'{ENV}/logs/final_impl'
WB = sys.argv[1] if len(sys.argv) > 1 else f'{ROOT}/Research_data_MASTER_0921.xlsx'


def util(t, label):
    m = re.search(rf'^\|\s*{re.escape(label)}\s*\|\s*([0-9.]+)\s*\|', t, re.M)
    return float(m.group(1)) if m else 0.0


def power(t, label):
    m = re.search(rf'^\|\s*{re.escape(label)}\s*\|\s*([<0-9.]+)', t, re.M)
    if not m:
        return 0.0                           # report_power omits zero rows (trap #9)
    s = m.group(1)
    return 0.0 if s.startswith('<') else float(s)


def timing(t):
    period = float(re.search(r'^\s+clk_out1_clk_wiz_0(?:_1)?\s+\{[^}]*\}\s+([0-9.]+)', t, re.M).group(1))
    wns = float(re.search(r'Intra Clock Table.*?^\s+clk_out1_clk_wiz_0(?:_1)?\s+(-?[0-9.]+)', t, re.M | re.S).group(1))
    return period, wns


def report(v, b):
    d = f'{FI}/{v}_{b}'
    u, tm, pw = (open(f'{d}/{x}.rpt').read() for x in ('utilization', 'timing', 'power'))
    period, wns = timing(tm)
    r = dict(variant=v, bench=b,
             LUT=util(u, 'Slice LUTs'), LUTRAM=util(u, '  LUT as Memory'), FF=util(u, 'Slice Registers'),
             BRAM=util(u, 'Block RAM Tile'), DSP=util(u, 'DSPs'), IO=util(u, 'Bonded IOB'),
             PLL=util(u, 'PLLE2_ADV'), MMCM=util(u, 'MMCME2_ADV'),
             clock_MHz=round(1000 / period, 6), WNS=wns, SoC_Fmax=round(1000 / (period - wns), 3),
             P_total=power(pw, 'Total On-Chip Power (W)'), P_dynamic=power(pw, 'Dynamic (W)'),
             P_clocks=power(pw, 'Clocks'), P_signals=power(pw, 'Signals'), P_logic=power(pw, 'Slice Logic'),
             P_bram=power(pw, 'Block RAM'), P_dsp=power(pw, 'DSPs'), P_pll=power(pw, 'PLL'),
             P_io=power(pw, 'I/O'), P_static=power(pw, 'Device Static (W)'),
             Tj=power(pw, 'Junction Temperature (C)'))
    r['report_date'] = re.search(r'^\| Date\s*:\s*(.+?)\s*$', u, re.M).group(1)
    r['md5_util'] = hashlib.md5(u.encode()).hexdigest()[:10]
    r['md5_timing'] = hashlib.md5(tm.encode()).hexdigest()[:10]
    r['md5_power'] = hashlib.md5(pw.encode()).hexdigest()[:10]
    return r


# workbook columns in the SoC blocks (0-based within the row tuple)
COLS = dict(LUT=2, LUTRAM=3, FF=4, BRAM=5, DSP=6, IO=7, PLL=8, SoC_Fmax=9,
            P_clocks=12, P_signals=13, P_logic=14, P_bram=15, P_dsp=16, P_pll=17, P_io=18, P_static=19)


def main():
    wb = openpyxl.load_workbook(WB, data_only=True)
    rows, bad = [], []
    for arch in ('RV32', 'RV64'):
        ws = wb[f'{arch} SoC and FPGA']
        block = None
        for row in ws.iter_rows(values_only=True):
            h = row[1]
            if h in ('SoC Dhrystone', 'SoC Coremark'):
                block = 'dhrystone' if 'Dhry' in h else 'coremark'
                continue
            if h == 'Legend':
                block = None
            if not block or not h or not re.match(r'I_|IM_', str(h)):
                continue
            v = f'{arch}{h}'
            r = report(v, block)
            rows.append(r)
            for k, c in COLS.items():
                wbv = row[c]
                if wbv is None or wbv == '':
                    bad.append((v, block, k, 'EMPTY', r[k]))
                    continue
                tol = 0.0015 if k.startswith('P_') else (0.002 if k == 'SoC_Fmax' else 0)
                if abs(float(wbv) - r[k]) > tol:
                    bad.append((v, block, k, wbv, r[k]))
    out = f'{ENV}/logs/soc_report_audit.csv'
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'{len(rows)} builds checked against reports -> {out}')
    print(f'{len(bad)} disagreements (variant, bench, field, workbook, report):')
    for b in bad:
        print('  ', *b)


if __name__ == '__main__':
    main()
