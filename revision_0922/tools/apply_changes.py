#!/usr/bin/env python3
"""Apply the reviewed change list to a frozen copy of the master workbook.

    Research_data_MASTER_0921.xlsx   (never modified)
        -> Research_data_0923_frozen.xlsx

Every addressable item of `Change list` in Revision_review_0923.xlsx is written
only after the target cell is confirmed to still hold the value the change list
recorded as "current"; anything that has moved is reported and skipped, never
guessed.  The text items are applied by locating their sentence in the sheet.
New measurements that have no cell in the master (T8, T9, T10, T12, T13, the
SAIF window map) are added as new sheets.

Sheet `Change log 0923` records what was written, with the evidence file.
"""
import copy, csv, datetime, os, re, shutil, sys
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter, column_index_from_string

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
REV = f'{ROOT}/revision_0922'
ENV = f'{ROOT}/riscof-env'
MASTER = f'{ROOT}/Research_data_MASTER_0921.xlsx'
REVIEW = f'{REV}/Revision_review_0923.xlsx'
OUT = f'{ROOT}/Research_data_0923_frozen.xlsx'

F = 'NanumGothic'
HDR = PatternFill('solid', fgColor='FFBFBFBF')
log = []            # (sheet, cell, field, old, new, reason, evidence)
skipped = []        # (sheet, cell, field, expected, found, why)


def rcsv(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f, delimiter='\t' if path.endswith('.tsv') else ','))


def num(x):
    if x is None or (isinstance(x, str) and x.strip() in ('', 'None')):
        return None
    if isinstance(x, (int, float)):
        return x
    s = str(x).strip()
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s


def same(a, b):
    """Is the cell value `a` the value `b` the change list recorded?"""
    if a is None and b is None:
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a)))
    sa, sb = str(a).strip(), str(b).strip()
    if sa == sb:
        return True
    try:                                    # '117' vs 117
        return abs(float(sa) - float(sb)) <= 1e-9 * max(1.0, abs(float(sa)))
    except ValueError:
        return sb in sa                     # change list stores a truncated note


def put(ws, cell, value, field, reason, evidence, expect='__any__'):
    c = ws[cell]
    old = c.value
    if expect != '__any__' and not same(old, expect):
        skipped.append((ws.title, cell, field, expect, old, 'current value has moved'))
        return False
    c.value = value
    log.append((ws.title, cell, field, old, value, reason, evidence))
    return True


def style_like(ws, src_ws, src_cell, dst_cell):
    s = src_ws[src_cell]
    d = ws[dst_cell]
    d.font = copy.copy(s.font)
    d.fill = copy.copy(s.fill)
    d.alignment = copy.copy(s.alignment)
    d.number_format = s.number_format


def new_sheet(wb, name, title, sub, headers, rows, widths=None, formats=None):
    ws = wb.create_sheet(name)
    ws['B2'] = title
    ws['B2'].font = Font(name=F, sz=11, b=True)
    ws['B3'] = sub
    ws['B3'].font = Font(name=F, sz=11)
    for j, h in enumerate(headers, 2):
        c = ws.cell(5, j, h)
        c.font = Font(name=F, sz=11, b=True)
        c.fill = HDR
        c.alignment = Alignment(wrap_text=True, vertical='bottom')
    for i, r in enumerate(rows, 6):
        for j, v in enumerate(r, 2):
            c = ws.cell(i, j, v)
            c.font = Font(name=F, sz=11)
            if formats and headers[j - 2] in formats:
                c.number_format = formats[headers[j - 2]]
    ws.column_dimensions['A'].width = 3
    for j, h in enumerate(headers, 2):
        w = (widths or {}).get(h)
        if w is None:
            vals = [len(str(h))] + [len(str(r[j - 2])) for r in rows[:300] if r[j - 2] is not None]
            w = min(max(vals) + 2, 46)
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.sheet_view.zoomScale = 90
    return ws


# ------------------------------------------------------------------ 1. copy
def main():
    shutil.copy(MASTER, OUT)
    wb = openpyxl.load_workbook(OUT)
    rv = openpyxl.load_workbook(REVIEW, data_only=True)
    cl = rv['Change list']
    items = [[cl.cell(r, c).value for c in range(1, 11)] for r in range(5, cl.max_row + 1) if cl.cell(r, 1).value]

    # board CoreMark re-runs supersede the simulation-derived score for those variants
    # (all 16 CoreMark runs: Total ticks transcribed from the board screenshots, Coremark_results_image/)
    board = {r['variant']: r for r in rcsv(f'{REV}/T3/T3_board_coremark_ticks.csv')}
    for b in board.values():
        b['true_its'] = int(b['iterations']) * float(b['run_MHz']) * 1e6 / int(b['board_total_ticks'])
        b['true_cm_mhz'] = int(b['iterations']) * 1e6 / int(b['board_total_ticks'])
    superseded = set()          # (sheet, cell) the board measurement will write instead

    # -------------------------------------------------------------- 2. addressable cells
    nmw0 = wb['Normalized metrics']
    for v in board:
        arch = v[:4]
        ws0 = wb[f'{arch} SoC and FPGA']
        for r in range(3, 11):
            if arch + str(ws0.cell(r, 2).value) == v:
                superseded.add((ws0.title, f'H{r}'))
        for r in range(6, nmw0.max_row + 1):
            if nmw0.cell(r, 2).value == v:
                superseded.update(('Normalized metrics', f'{c}{r}') for c in 'DEGKLM')
    for n, task, sheet, cell, rowlab, field, cur, prop, reason, ev in items:
        if (sheet, str(cell)) in superseded:
            continue
        if not re.fullmatch(r'[A-Z]+\d+', str(cell)):
            continue
        if sheet not in wb.sheetnames:
            skipped.append((sheet, cell, field, cur, None, 'sheet not in master'))
            continue
        put(wb[sheet], cell, prop, field, f'[{task}] {reason}', ev, expect=cur)

    # -------------------------------------------------------------- 3. SAIF derived cells and notes
    saif = {(r['variant'], r['bench']): r for r in rcsv(f'{REV}/T4/T4_saif_authoritative.csv')}
    for arch in ('RV32', 'RV64'):
        ws = wb[f'{arch} SoC and FPGA']
        block = None
        for r in range(1, ws.max_row + 1):
            lab = ws.cell(r, 2).value
            if lab in ('SoC Dhrystone', 'SoC Coremark'):
                block = 'dhrystone' if 'Dhry' in str(lab) else 'coremark'
                continue
            if lab == 'Legend':
                block = None
            if not block or not lab or not re.match(r'I_|IM_', str(lab)):
                continue
            s = saif.get((arch + lab, block))
            if not s:
                continue
            # 'vs vectorless' is stored as a fraction
            vv = round(float(s['dyn_vs_vectorless_pct']) / 100, 4)
            if not same(ws.cell(r, 26).value, vv):
                put(ws, f'Z{r}', vv, 'vs vectorless', '[T4] recomputed with the authoritative SAIF power',
                    'T4/T4_saif_authoritative.csv')
            # the per-row note repeats the SAIF numbers in prose, and calls the PLL an MMCM
            nc = ws.cell(r, 21)
            if isinstance(nc.value, str):
                old = nc.value
                new = old.replace("the MMCM's exact output", "the PLL's exact output")
                new = re.sub(r'activity-based dynamic [\d.]+ W vs vectorless [\d.]+ W \([-+]?[\d.]+%\)',
                             f"activity-based dynamic {float(s['saif_dynamic']):.3f} W vs vectorless "
                             f"{float(s['vectorless_dynamic']):.3f} W ({float(s['dyn_vs_vectorless_pct']):+.1f}%)", new)
                if (arch + lab, block) == ('RV64IM_8SP', 'coremark'):
                    new += ('  ||  The original capture was INVALID (the gate-level netlist idled in _exit and never '
                            'entered main); this row is the PC-verified re-capture on the final implementation.')
                if new != old:
                    put(ws, f'U{r}', new, 'row note', '[T4/T7] PLL naming and SAIF numbers reconciled with the cells',
                        'T4/T4_saif_power.md, T7/T7_metadata_checks.md')

    # the two Embench sheets repeat the CoreMark SAIF power of each SoC build
    for sheet, arch in (('Embench FPGA RV32', 'RV32'), ('Embench FPGA RV64', 'RV64')):
        ws = wb[sheet]
        start = next((r for r in range(1, ws.max_row + 1) if 'SAIF power' in str(ws.cell(r, 2).value or '')), None)
        if not start:
            skipped.append((sheet, '-', 'SAIF power block', 'header row', None, 'block not found'))
            continue
        cols = {4: 'saif_total', 5: 'saif_dynamic', 6: 'saif_clocks', 7: 'saif_signals', 8: 'saif_logic',
                9: 'saif_bram', 10: 'saif_dsp', 11: 'saif_pll', 12: 'saif_io', 13: 'saif_static'}
        for r in range(start + 1, ws.max_row + 1):
            lab = ws.cell(r, 2).value
            s4 = saif.get((arch + str(lab), 'coremark')) if lab else None
            if not s4:
                continue
            for col, key in cols.items():
                v = round(float(s4[key]), 3)
                if not same(ws.cell(r, col).value, v):
                    put(ws, f'{get_column_letter(col)}{r}', v, ws.cell(start, col).value,
                        '[T4] authoritative SAIF power (final implementation; the RV64 IM_8SP row replaces an invalid '
                        'idle-core capture)', 'T4/T4_saif_authoritative.csv')

    # board CoreMark re-runs: the score comes from the board's own Total ticks
    nmw = wb['Normalized metrics']
    nmsrc = {r['variant']: r for r in rcsv(f'{REV}/T4/T4_normalized_metrics.csv')}
    for v, b in board.items():
        arch, its, cmm = v[:4], b['true_its'], b['true_cm_mhz']
        why = (f"[T3] board: {b['iterations']} iterations, Total ticks {int(b['board_total_ticks']):,}, printed "
               f"{b['printed_its']} it/s.  Score = iterations x f / Total_ticks, CoreMark's own cycle count, at full "
               f"resolution")
        ev = 'T3/T3_board_coremark_ticks.csv'
        ws0 = wb[f'{arch} SoC and FPGA']
        for r in range(3, 11):
            if arch + str(ws0.cell(r, 2).value) == v:
                lbl = float(rcsv(f'{REV}/T3/T3_fragment_corrected_coremark.csv')[0]['CoreMark run MHz']) * 0 + \
                      float({x['variant']: x['CoreMark run MHz'] for x in
                             rcsv(f'{REV}/T3/T3_fragment_corrected_coremark.csv')}[v])
                put(ws0, f'H{r}', f"{cmm:.3f} @ {lbl:g}MHz", 'Coremarks/MHz (true)', why, ev)
        n = nmsrc.get(v)
        for r in range(6, nmw.max_row + 1):
            if nmw.cell(r, 2).value != v:
                continue
            W, lut = float(n['cm_total_W']), float(n['core_LUT'])
            for col, val, fld in (('D', round(its, 2), 'CoreMark (true it/s)'), ('E', round(cmm, 4), 'CM/MHz'),
                                  ('G', round(its / lut, 5), 'CM/LUT core'), ('K', round(its / W, 2), 'CM/W'),
                                  ('L', round(W / its * 1000, 4), 'mJ/iter'), ('M', round(its, 2), 'iters/s (true)')):
                put(nmw, f'{col}{r}', val, fld, why, ev)

    cmv = {r['variant']: r for r in rcsv(f'{REV}/T3/T3_fragment_corrected_coremark.csv')}
    # CM/LUT SoC is also derived from the CoreMark score, on the SoC LUT count of the CoreMark build
    socl = {r['variant']: float(r['LUT']) for r in rcsv(f'{REV}/T3/soc_rows_from_vivado_reports.csv')
            if r['bench'] == 'coremark'}
    nmw2 = wb['Normalized metrics']
    for r in range(6, nmw2.max_row + 1):
        v = nmw2.cell(r, 2).value
        if not v or v not in socl:
            continue
        its = board[v]['true_its'] if v in board else float(cmv[v]['TRUE it/s = f / cycles-per-iter'])
        val = round(its / socl[v], 5)
        if not same(nmw2.cell(r, 8).value, val):
            put(nmw2, f'H{r}', val, 'CM/LUT SoC',
                '[T3] recomputed from the true CoreMark score over the SoC LUT count of the CoreMark build'
                + (' (board re-run)' if v in board else ''),
                'T3/T3_fragment_corrected_coremark.csv, T3/soc_rows_from_vivado_reports.csv')

    # a board re-run also replaces the printed value on record
    for v, b in board.items():
        ws0 = wb[f'{v[:4]} SoC and FPGA']
        for r in range(3, 11):
            if v[:4] + str(ws0.cell(r, 2).value) == v:
                if not same(ws0.cell(r, 4).value, int(b['printed_its'])):
                    put(ws0, f'D{r}', int(b['printed_its']), 'Iterations/Sec (printed)',
                        f"[T3] {b['note']}", 'T3/T3_board_coremark_ticks.csv')

    # the printed CoreMark integer and the tick-derived score must not look like the same quantity
    for arch in ('RV32', 'RV64'):
        ws = wb[f'{arch} SoC and FPGA']
        put(ws, 'D2', 'Iterations/Sec (printed)', 'header',
            "[T3] CoreMark prints an integer-truncated score (HAS_FLOAT 0); this column is that printed value, kept as "
            "the raw board reading", 'T3/T3_coremark_anomaly_and_soc_rows.md')
        put(ws, 'H2', 'Coremarks/MHz (true)', 'header',
            "[T3] derived from CoreMark's own Total ticks, not from the printed integer",
            'T3/T3_fragment_corrected_coremark.csv')
        lr = next(r for r in range(1, ws.max_row + 1) if str(ws.cell(r, 2).value or '') == 'Legend')
        end_r = next(r for r in range(lr + 1, ws.max_row + 2) if not any(ws.cell(r, c).value for c in (2, 3)))
        for i, (k, txt) in enumerate([
                ('Iterations/Sec (printed)',
                 "CoreMark's port uses HAS_FLOAT 0, so time_in_secs() truncates to whole seconds and the printed "
                 "Iterations/Sec is an integer division: biased by +0.13% to +7.28%, and -9.75% on RV32 "
                 "IM_8SP_withoutOpt, which ran a mislabelled 100 MHz image at 114 MHz.  Column D is that printed value, "
                 "kept unedited as the raw board reading."),
                ('Coremarks/MHz (true)',
                 "iterations x f / Total_ticks: CoreMark's own cycle count of the timed region, at full resolution.  "
                 "Column H and the Normalized metrics sheet (CoreMark, CM/MHz, CM/W, mJ/iter, iters/s) use this, so H "
                 "is deliberately NOT column D divided by the clock.  The true iterations/sec per variant is in "
                 "Normalized metrics; papers should quote it and state the derivation.")], end_r):
            ws.cell(i, 2, k).font = copy.copy(ws.cell(lr + 1, 2).font)
            ws.cell(i, 3, txt).font = copy.copy(ws.cell(lr + 1, 3).font)
            log.append((ws.title, f'B{i}', 'legend', None, k,
                        '[T3] the printed and the tick-derived CoreMark scores are different quantities and must be labelled',
                        'T3/T3_coremark_anomaly_and_soc_rows.md'))
    nmw = wb['Normalized metrics']
    put(nmw, 'D5', 'CoreMark (true it/s)', 'header', '[T3] tick-derived, not the printed integer',
        'T3/T3_fragment_corrected_coremark.csv')
    put(nmw, 'M5', 'iters/s (true)', 'header', '[T3] tick-derived, not the printed integer',
        'T3/T3_fragment_corrected_coremark.csv')

    # -------------------------------------------------------------- 4. T1: the 40 RV32 Embench rows
    ws = wb['Embench FPGA RV32']
    frag = rcsv(f'{REV}/T1/T1_fragment_embench_fpga_rv32.csv')
    byblock = {}
    for r in frag:
        byblock.setdefault(r['block'], {})[r['variant']] = r
    block = None
    filled = 0
    for r in range(1, ws.max_row + 1):
        head = ws.cell(r, 2).value
        if head and str(head).startswith('RV32 '):
            block = str(head)
            continue
        if not block or not head or not re.match(r'I_|IM_', str(head)):
            continue
        d = byblock.get(block, {}).get(str(head))
        if not d:
            continue
        for col, key, fmt in ((3, 'FPGA cycles', '#,##0'), (4, 'FPGA instret', '#,##0'), (5, 'CPI', '0.0000'),
                              (6, 'sim cycles', '#,##0'), (7, 'sim = FPGA?', None), (8, 'verify', None),
                              (9, 'build MHz', None), (10, 'runtime ms', '0.000')):
            c = ws.cell(r, col)
            c.value = num(d[key])
            c.font = Font(name=F, sz=11)
            if fmt:
                c.number_format = fmt
        filled += 1
    log.append(('Embench FPGA RV32', f'C3:J{ws.max_row}', 'all 40 rows',
                'awaiting re-measurement (RV32 counter fix)', f'{filled} measured rows',
                '[T1] board runs 2026-09-23 on the rebuilt (v4 counter-read) bitstreams; 40/40 EXACT vs RTL simulation',
                'T1/T1_fragment_embench_fpga_rv32.csv'))
    if filled != 40:
        skipped.append(('Embench FPGA RV32', '-', 'all 40 rows', 40, filled, 'not every block row was matched'))

    # -------------------------------------------------------------- 5. T1: append the RV32 cross-check rows
    ws = wb['Embench FPGA vs simulation']
    rows = rcsv(f'{REV}/T1/T1_fragment_fpga_vs_sim_rows.csv')
    last = max(r for r in range(1, ws.max_row + 1)
               if ws.cell(r, 3).value is not None and str(ws.cell(r, 2).value or '').startswith('RV'))
    ws.insert_rows(last + 1, len(rows))
    for i, d in enumerate(rows, last + 1):
        for j, key in enumerate(['variant', 'benchmark', 'FPGA cycles', 'sim cycles', 'FPGA instret', 'sim instret',
                                 'cycles', 'instret'], 2):
            c = ws.cell(i, j, num(d[key]))
            style_like(ws, ws, f'{get_column_letter(j)}{last}', f'{get_column_letter(j)}{i}')
            c.value = num(d[key])
    log.append(('Embench FPGA vs simulation', f'B{last + 1}:I{last + len(rows)}', 'RV32 rows', 'absent',
                f'{len(rows)} rows appended', '[T1] 40/40 EXACT in both counters',
                'T1/T1_fragment_fpga_vs_sim_rows.csv'))

    # -------------------------------------------------------------- 6. text items
    def note(sheet, contains, new, field, reason, evidence, col=None):
        ws = wb[sheet]
        for r in range(1, ws.max_row + 1):
            for c in range(1, (col or ws.max_column) + 1):
                if col and c != col:
                    continue
                v = ws.cell(r, c).value
                if isinstance(v, str) and contains in v:
                    put(ws, f'{get_column_letter(c)}{r}', new, field, reason, evidence)
                    return True
        skipped.append((sheet, '-', field, contains, None, 'sentence not found'))
        return False

    note('Verification', "Embench 'no result' rows hit the simulation cycle limit",
         "Embench 'no result' rows are a 4 KB stack overflow in the Embench port, not a functional failure and not the "
         "simulation cycle limit: with a 12 KB stack huffbench, slre and wikisort complete with verify OK on all 16 variants.",
         'Embench note', '[T5] stack audit and 48 re-runs', 'T5/T5_embench_no_result.md')
    note('Verification', 'riscv-tests shortfalls are ma_data only',
         'riscv-tests shortfalls are ma_data only, which is optional in RISC-V.  Probed directly: misaligned loads and '
         'stores trap, except RV64 ld/lwu (silently aligned) and a misaligned sh on RV32IM_5SP/8SP/8SP_withoutOpt, '
         'which traps but still writes.', 'ma_data note', '[T7] direct probe on all 16',
         'T7/T7_metadata_checks.md, T7/misaligned_probe.S')

    # the randomized-testing prose block (rows 24-37 of Verification) is replaced wholesale
    ws = wb['Verification']
    start = next((r for r in range(1, ws.max_row + 1)
                  if str(ws.cell(r, 2).value or '').startswith('Randomized testing has two distinct failure modes')), None)
    if start:
        prose = [
            'Randomized testing (AAPG): one failure mode, root-caused, and it affects no reported measurement.',
            '  NON-TERMINATION is the only real divergence.  Root cause, found by delta-debugging to a 7-instruction',
            '  reproduction (aapg-env/repro/t6_min2.hex): IF_IO_Register skips the squash behind a predicted-taken',
            '  branch while an M-extension instruction is in ID (the !is_m_extend term).  When the prediction is',
            '  CORRECT, EX raises no mispredict, so the wrongly admitted sequential instruction commits.  5SP and 6SP',
            '  have no IF/IO stage and are immune, which is exactly the observed failure set.',
            '  A cycle-level trigger predicate counts the condition itself.  It fires ZERO times on every workload this',
            '  file reports: the full CoreMark and Dhrystone board binaries run to completion, all 19 Embench, and 338',
            '  micro-kernels, on all ten 7/8-stage variants.  Two independent monitors agree (committed-stream',
            '  continuity and branch-outcome consistency; value-level lock-step against the 5-stage core over ~75M',
            '  instructions per variant, 0 divergences).  No cycle count, CPI, frequency, area or power number is affected.',
            '  MISMATCH vs the Sail reference is NOT a second defect.  It is a link-address artefact: the DUT runs from',
            '  ROM at 0x00000000 and Sail from 0x80000000, so signature words holding address fragments differ.  Compared',
            '  DUT-to-DUT on the identical ROM image, every completing program is byte-identical to the 5-stage core',
            '  (113/113, 0 differing words of 4096).',
            '  Secondary defects found by the same monitors, none of which affects an FPGA number: a csrr/ret',
            '  fall-through on 5SP/6SP/7SP/7SP_BRAM (benign; it is the 13-14 instruction minstret offset in the Embench',
            '  FPGA sheets), and, on the ablation-only RV64IM_7SP, a wrong-path commit once per CoreMark iteration and',
            '  wrong byte loads in qrduino (simulation rows only).',
            'Randomized testing found two defects during development that are now fixed: a 7SP_BRAM branch defect',
            'and an 8SP divw bug, both reproducible from aapg-env/repro/.',
        ]
        end = ws.max_row
        old_n = end - start + 1
        for i, line in enumerate(prose):
            r = start + i
            if r > end:
                ws.cell(r, 2).font = copy.copy(ws.cell(start, 2).font)
            ws.cell(r, 2).value = line
        for r in range(start + len(prose), end + 1):
            ws.cell(r, 2).value = None
        log.append(('Verification', f'B{start}:B{start + len(prose) - 1}', 'randomized-testing note',
                    f'{old_n} lines: "two distinct failure modes", "Under investigation"',
                    f'{len(prose)} lines: root cause, trigger count 0, DUT-vs-DUT 113/113',
                    '[T6/T12] root cause proven; the mismatch mode is a reference-map artefact',
                    'T6/T6_aapg_divergence_scope.md, T12/T12_aapg_address_matched.md'))

    # Verification table: AAPG column and note column per variant
    t12 = rcsv(f'{REV}/T12/t12_aapg_dutvsdut.csv')
    agg = {}
    for r in t12:
        d = agg.setdefault(r['variant'], {'ident': 0, 'timeout': 0, 'ref': 0})
        v = r['verdict']
        d['ident' if v.startswith('IDENTICAL') else 'timeout' if v.startswith('TIMEOUT') else 'ref'] += 1
    ws = wb['Verification']
    for r in range(1, ws.max_row + 1):
        v = str(ws.cell(r, 2).value or '')
        if not v.startswith('RV'):
            continue
        d = agg.get(v)
        if not d:
            continue
        if d['ref']:
            newcol, newnote = f"{d['ref']}/20 reference", 'reference core for the DUT-vs-DUT comparison'
        else:
            newcol = f"{d['ident']}/{d['ident'] + d['timeout']} identical to 5SP"
            newnote = (f"{d['timeout']} non-terminations (T6 defect); every completing run byte-identical to the 5-stage core"
                       if d['timeout'] else 'all runs byte-identical to the 5-stage core')
        put(ws, f'F{r}', newcol, 'randomized (AAPG)',
            '[T12] compared DUT-to-DUT on the identical ROM image, not against Sail at a different link address',
            'T12/t12_aapg_dutvsdut.csv')
        put(ws, f'G{r}', newnote, 'note', '[T6/T12] the mismatch mode was a link-address artefact',
            'T12/T12_aapg_address_matched.md')

    # Embench-sim column: with a 12 KB stack every variant completes all 19 (T5)
    e12 = rcsv(f'{REV}/T5/T5_fragment_embench_12KBstack.csv')
    if len(e12) == 48 and all(r['verify'] == 'OK' for r in e12):
        for r in range(1, ws.max_row + 1):
            if str(ws.cell(r, 2).value or '').startswith('RV'):
                put(ws, f'E{r}', '19/19', 'Embench sim',
                    '[T5] the three non-completions were a 4 KB stack overflow; with a 12 KB stack all 19 complete '
                    'with verify OK (48/48 re-runs)', 'T5/T5_fragment_embench_12KBstack.csv')

    note('Contents', 'Randomized testing shows a control-flow divergence',
         'Randomized testing shows one control-flow divergence on the 7- and 8-stage variants: root-caused (T6), with a '
         'cycle-level trigger count of 0 on every workload reported here.  Not fixed: fixing it would invalidate all 32 '
         'bitstreams.', 'known-gaps note', '[T6] root cause and scope proven', 'T6/T6_aapg_divergence_scope.md')
    note('Contents', 'Embench RV32 on FPGA',
         'Embench RV32 on FPGA — complete: 40 board runs on the rebuilt bitstreams, 40/40 exact against RTL simulation.',
         'known-gaps note', '[T1] board runs 2026-09-23', 'T1/T1_rv32_embench_fpga.md')
    note('Contents', 'Deliberately blank',
         'Five Embench benchmarks measured on hardware after the counter-read fix, with CPI, build clock and derived '
         'runtime.  40/40 exact against RTL simulation.', 'sheet description', '[T1] board runs 2026-09-23',
         'T1/T1_rv32_embench_fpga.md')
    note('Contents', 'with the two randomized failure modes explained',
         'RISCOF, riscv-tests, Embench and randomized (AAPG) results per variant.  Randomized programs are compared '
         'DUT-to-DUT on the identical ROM image; the single failure mode is non-termination, root-caused in T6.',
         'sheet description', '[T6/T12] one failure mode, not two', 'T12/T12_aapg_address_matched.md')
    note('Contents', '40 of 40 RV64 rows match exactly',
         'Every FPGA cycle and instret against RTL simulation.  80 of 80 rows (40 RV64 + 40 RV32) match exactly.',
         'sheet description', '[T1] RV32 rows appended', 'T1/T1_fragment_fpga_vs_sim_rows.csv')
    note('Embench simulation', "'no result' = exceeded the 400M-cycle simulation limit",
         "green = also measured on FPGA.  'no result' for huffbench, slre and wikisort was a 4 KB stack overflow in the "
         "Embench port: rebuilt with a 12 KB stack, all three complete with verify OK on all 16 variants and their "
         "cycles are in this sheet.  xgboost completes but its verify_benchmark is vacuous at GLOBAL_SCALE_FACTOR=1.",
         'Embench note', '[T5] stack audit, 48 re-runs', 'T5/T5_embench_no_result.md')
    note('CPI and stalls', 'Counters live in the simulation wrapper',
         'Counters live in the simulation wrapper, not the core, so profiling cannot perturb the design.  The stall '
         'columns below are OVERLAPPING occupancies and must not be added: pc / front-end / ID-EX are identical by '
         'construction.  For an additive, cause-based partition of every cycle see the sheet "Stall breakdown by cause"; '
         'on the 8-stage variants the "load-use" signal there is split into true load-use (~1.9%) and execution-use (~8.6%).',
         'header note', '[T8] cause partition, 112/112 exact', 'T8/T8_stall_breakdown.md')

    # Embench FPGA RV64: nettle-aes footnote
    ws = wb['Embench FPGA RV64']
    r = next((r for r in range(1, ws.max_row + 1)
              if str(ws.cell(r, 2).value or '') == 'IM_5SP' and str(ws.cell(r, 9).value) in ('30', '30.0')), None)
    if r:
        put(ws, f'K{r}', 'build did not close timing at the 38 MHz variant clock (WNS -0.131 ns) or at 37 MHz '
                         '(-0.106 ns); rebuilt at 30 MHz, WNS +0.735.  Cycles are clock-independent, so only this row\'s '
                         'runtime is affected; at the variant clock the projection would be 138.58 ms, which is not a '
                         'measurement.  Note: IM-5 is the geomean baseline, so this row lowers every other variant\'s '
                         'reported speedup by about 4.6%.', 'nettle-aes footnote',
            '[T7] embench_retry2.log, MANIFEST.csv', 'T7/T7_metadata_checks.md')
    else:
        skipped.append(('Embench FPGA RV64', '-', 'nettle-aes footnote', 'IM_5SP row with 30 MHz', None, 'row not found'))

    # -------------------------------------------------------------- 7. T9 block in Microkernel penalties
    ws = wb['Microkernel penalties']
    pen = rcsv(f'{REV}/T9/t9_mispredict_penalties.csv')
    byvar = {}
    for p in pen:
        byvar.setdefault(p['variant'], []).append(p)
    start = next(r for r in range(ws.max_row, 0, -1) if ws.cell(r, 1).value) + 2
    ws.cell(start, 1, 'Branch misprediction penalty by direction (matched pairs; every branch targets the next '
                      'instruction, so taken and not-taken retire the identical stream)').font = Font(name=F, sz=11, b=True)
    hdr = ['variant', 'mispredict NT->T', 'mispredict T->NT', 'correctly predicted taken',
           'matched-pair blend', 'max least-squares residual %']
    for j, h in enumerate(hdr, 1):
        c = ws.cell(start + 1, j, h)
        c.font = Font(name=F, sz=11, b=True)
        c.fill = HDR
    order = [ws.cell(r, 1).value for r in range(7, 23)]
    for i, v in enumerate(order, start + 2):
        rs = byvar.get(v, [])
        if not rs:
            continue
        g = lambda k: float(rs[0][k])
        blend = (sum(float(x['pair_penalty_cycles']) for x in rs) / len(rs))
        for j, val in enumerate([v, g('penalty_nt_to_t'), g('penalty_t_to_nt'), g('taken_branch_cost'),
                                 round(blend, 2), max(float(x['max_residual_pct']) for x in rs)], 1):
            c = ws.cell(i, j, val)
            c.font = Font(name=F, sz=11)
    ws.cell(start + 2 + len(order), 1,
            'Two penalties, not one: from 7 stages on a taken branch costs 2 cycles even when correctly predicted, a '
            'not-taken misprediction 3 (7SP) or 4 (8SP), and a taken misprediction 5 (7SP) or 6 (8SP).  Identical for '
            'RV32 and RV64 and for forward and backward branches (48 fitted families, maximum residual 0.0%).'
            ).font = Font(name=F, sz=11)
    log.append(('Microkernel penalties', f'A{start}:F{start + 1 + len(order)}', 'mispredict penalty',
                'one flush penalty per depth', 'two direction-dependent penalties + taken-branch cost',
                '[T9] matched pairs and least squares over 6 branch patterns, residual 0.0%',
                'T9/t9_mispredict_penalties.csv'))

    # -------------------------------------------------------------- 8. new sheets
    t8 = rcsv(f'{ENV}/logs/t8_stall_breakdown.csv')
    keys = [k for k in t8[0] if k != 'variant' and k != 'benchmark']
    new_sheet(wb, 'Stall breakdown by cause',
              'Cause-based stall accounting: every cycle attributed to exactly one cause',
              'Priority partition, 112 runs (16 variants x Dhrystone, CoreMark and the five FPGA Embench).  '
              'sum(buckets) + retired-cycles == cycles on 112/112, and the instrumented simulator reproduces the '
              'production simulator\'s cycles and retired exactly on 112/112.  Counters live in a separate build '
              '(riscof-env/build_t8), never in the core.',
              ['variant', 'benchmark'] + keys,
              [[r['variant'], r['benchmark']] + [num(r[k]) for k in keys] for r in t8],
              formats={k: ('0.000' if k.endswith('_pct') else '#,##0') for k in keys})

    t12rows = [[r['variant'], r['program'], r['pool'], r['reference'], r['status_vs_sail'],
                num(r['words_differing_vs_5SP']), r['verdict']] for r in t12]
    new_sheet(wb, 'AAPG vs 5SP', 'Randomized programs compared DUT-to-DUT on the identical ROM image',
              'The Sail reference links at 0x80000000 and the DUT runs from 0x00000000, so signature words holding '
              'address fragments differ.  Comparing each variant with the 5-stage core on the same image removes that '
              'artefact: 113 of 113 completing runs are byte-identical, 0 differing words of 4096.  The remainder are '
              'non-terminations from the single T6 defect.',
              ['variant', 'program', 'pool', 'reference', 'status vs Sail', 'words differing vs 5SP', 'verdict'],
              t12rows)

    t10 = rcsv(f'{REV}/T10/t10_dynamic_mix.csv')
    k10 = list(t10[0].keys())
    new_sheet(wb, 'Dynamic instruction mix', 'Instructions per iteration and dynamic instruction mix',
              'Difference of two fixed-iteration images, which cancels fixed start-up overhead.  RTL simulation at the '
              'same commit as the bitstreams.',
              k10, [[num(r[k]) for k in k10] for r in t10])

    t13 = rcsv(f'{REV}/T13_worst_paths_soc.tsv')
    k13 = list(t13[0].keys())
    new_sheet(wb, 'Worst paths', 'Worst setup path of each SoC build',
              'From logs/final_impl/<build>/timing.rpt, the implementations these measurements come from.',
              k13, [[num(r[k]) for k in k13] for r in t13])

    win = rcsv(f'{REV}/T4/capture_window_map.csv')
    val = {}
    for r in rcsv(f'{REV}/T4/capture_validity_dmem_activity.csv'):
        tag = r['tag']
        bench = 'dhrystone' if tag.endswith('_dhrystone') else 'coremark'
        val[(tag.rsplit('_' + bench, 1)[0], bench)] = r
    kw = list(win[0].keys())
    vcols = [k for k in (list(val.values())[0] if val else {}) if k not in ('tag', 'window_us')]
    new_sheet(wb, 'SAIF capture windows', 'What each SAIF capture actually sampled',
              'Every capture samples 1200-1300 us of wall-clock time, which is NOT the same point in the program on '
              'every variant: by 1.2 ms a 102 MHz core has run 2.7x more cycles than a 38 MHz one.  Dhrystone windows '
              'are phase-matched on all 16; CoreMark windows are not (the fast variants are already in the matrix / CRC '
              'phase), so cross-variant ENERGY comparisons should use Dhrystone.  Verified by PC sampling in the two v2 '
              're-captures.',
              kw + vcols,
              [[num(r[k]) for k in kw] + [num(val.get((r['variant'], r['bench']), {}).get(k)) for k in vcols]
               for r in win])

    # -------------------------------------------------------------- 8b. CoreMark true score
    cmrows = rcsv(f'{REV}/T3/T3_fragment_corrected_coremark.csv')
    TRUE = 'TRUE it/s = f / cycles-per-iter'
    order = [r for r in cmrows if r['variant'].startswith('RV32')] + [r for r in cmrows if r['variant'].startswith('RV64')]
    hdr = ['variant', 'run MHz', 'image compiled for MHz', 'cycles / iteration', 'instructions / iteration', 'CPI',
           'iterations', 'Total ticks (predicted)', 'Total ticks (board)', 'printed secs (int)', 'printed Iterations/Sec',
           'true Iterations/Sec', 'true CoreMark/MHz', 'printed error %', 'score from', 'replay reproduces the print']
    body = []
    for i, r in enumerate(order, 6):
        b = board.get(r['variant'])
        body.append([r['variant'], float(b['run_MHz']) if b else float(r['CoreMark run MHz']),
                     114.0 if r['variant'] == 'RV32IM_8SP_withoutOpt' else float(r['image compiled for MHz']),
                     float(r['CoreMark cycles/iter (sim)']), float(r['CoreMark instr/iter']), float(r['CoreMark CPI']),
                     int(b['iterations']) if b else int(r['board iterations (replayed)']),
                     f'=H{i}*E{i}',                       # predicted ticks = iterations x simulated cycles/iteration
                     int(b['board_total_ticks']) if b else None,
                     int(b['printed_secs']) if b else int(r['board int seconds (replayed)']),
                     int(b['printed_its']) if b else int(r['printed it/s (replayed)']),
                     f'=IF(J{i}="",C{i}*1000000/E{i},H{i}*C{i}*1000000/J{i})',   # board ticks win when present
                     f'=M{i}/C{i}',                       # true CoreMark/MHz
                     f'=100*(L{i}-M{i})/M{i}',            # bias of the printed integer
                     'board Total ticks' if b else 'simulated cycles/iteration',
                     ('yes, and it predicted the re-run exactly' if r['variant'] == 'RV32IM_8SP_withoutOpt' else
                      ('yes' if r['replay == master'] == 'True' else 'NO'))])
    ws = new_sheet(wb, 'CoreMark true score',
                   'CoreMark: the printed score, the tick-derived score, and how one becomes the other',
                   "CoreMark's timed region is measured in mcycle ticks and printed as \"Total ticks\".  This port sets "
                   "HAS_FLOAT 0, so time_in_secs() truncates to whole seconds and the printed Iterations/Sec is an "
                   "integer division of an integer: the published score, but quantised.  Both quantities are kept here.",
                   hdr, body,
                   formats={'cycles / iteration': '#,##0.0', 'instructions / iteration': '#,##0.0', 'CPI': '0.0000',
                            'iterations': '#,##0', 'Total ticks (predicted)': '#,##0', 'Total ticks (board)': '#,##0',
                            'true Iterations/Sec': '0.00',
                            'true CoreMark/MHz': '0.0000', 'printed error %': '+0.00;-0.00;0.00',
                            'run MHz': '0.######', 'image compiled for MHz': '0.######'},
                   widths={'variant': 24, 'image compiled for MHz': 13, 'instructions / iteration': 13,
                           'Total ticks (board)': 16, 'Total ticks (predicted)': 16, 'score from': 16,
                           'printed Iterations/Sec': 12, 'printed secs (int)': 10, 'true Iterations/Sec': 12,
                           'replay reproduces the print': 13, 'printed error %': 11})
    notes = [
        ('How each column is obtained', True),
        ('  Every row is a board measurement.  iterations, Total ticks and the printed Iterations/Sec are read from '
         'the UART output of each CoreMark bitstream (Coremark_results_image/, transcribed to '
         'revision_0922/T3/T3_board_coremark_ticks.csv); every transcription reproduces its own printed seconds and '
         'Iterations/Sec, and every crcfinal is the expected value.  run MHz is the PLL output from the Vivado report.', False),
        ('  true Iterations/Sec = iterations x f / Total_ticks: CoreMark\'s own cycle count of the timed region, at '
         'full resolution.  true CoreMark/MHz = iterations x 1e6 / Total_ticks, which does not depend on the clock at all.', False),
        ('  cycles / iteration comes from two fixed-iteration images (10 and 20) run on the RTL simulator and '
         'differenced.  Total ticks (predicted) = iterations x that value; it matches the board to -0.004% .. -0.013% '
         'on all 16, and replaying core_main.c\'s auto-calibration with it reproduces every printed integer.  The '
         'simulation is therefore a cross-check here, not the source of the score.', False),
        ('Which number to publish', True),
        ('  Quote the true score and state the derivation, e.g. "CoreMark\'s integer-second timing (HAS_FLOAT 0) '
         'truncates the printed Iterations/Sec by up to 7%; we report iterations x f / Total_ticks from the same run."  '
         'The Normalized metrics sheet and column H of the SoC sheets already use the true score; column D of the SoC '
         'sheets keeps the printed value unedited as the raw board reading.', False),
        ('RV32 IM_8SP_withoutOpt is the one row with a second, separate error', True),
        ('  Its project loads coremark_RV32IM_114MHz.mem, but that file is byte-identical to the 100 MHz image '
         '(md5 bb5eaf...), so the program believed the clock was 100 MHz while the PLL ran at 113.999088 MHz.  Its '
         'printed 166 it/s is therefore biased -9.75%, in the opposite direction to every other row.', False),
        ('  Re-run 2026-09-23 with a correctly built image: the board printed exactly the predicted 187 Iterations/Sec '
         '(Total ticks 1,859,182,144), true score 183.95 it/s.  The printed 187 is still 1.66% high: the correct image '
         'makes the calibration choose 3000 iterations and 16 truncated seconds, so the quantisation changes sign and '
         'size rather than vanishing - the reason the printed integer should not be published.', False),
        ('Dhrystone is unaffected: it computes a float from cycle-resolution time, and the simulated cycles/iteration '
         'predict every master Dhrystones/s to within -0.20% .. +0.14% on all 16.', False),
        ('Source: revision_0922/T3/T3_board_coremark_ticks.csv (board), T3_fragment_corrected_coremark.csv (simulation), '
         'T3_coremark_anomaly_and_soc_rows.md', False),
    ]
    r0 = 6 + len(body) + 2
    for i, (txt, bold) in enumerate(notes, r0):
        c = ws.cell(i, 2, txt)
        c.font = Font(name=F, sz=11, b=bold)
    log.append(('CoreMark true score', f'B5:Q{5 + len(body)}', 'new sheet', None,
                f'{len(body)} variants: printed and tick-derived score side by side, with the derivation as formulas',
                '[T3] the printed Iterations/Sec is integer-truncated; the true score comes from CoreMark\'s own Total ticks',
                'T3/T3_fragment_corrected_coremark.csv'))

    # -------------------------------------------------------------- 8c. external-core throughput
    # (was only ever added to an older copy of the master; rebuilt here from its sources)
    old = openpyxl.load_workbook(os.path.expanduser('~/Documents/Research_data_MASTER_0921.xlsx'), data_only=True)
    oldws = old['Core throughput'] if 'Core throughput' in old.sheetnames else None
    notes_top = [oldws.cell(r, 1).value for r in (3, 4, 5)] if oldws else []
    notes_bot = [oldws.cell(r, 1).value for r in (23, 24, 25, 26)] if oldws else []
    tp = rcsv(f'{ROOT}/comparison_cores/throughput/out/throughput.csv')
    ccw = wb['Core comparison']
    cc = {str(ccw.cell(r, 2).value): (ccw.cell(r, 4).value, ccw.cell(r, 11).value) for r in range(6, ccw.max_row + 1)
          if ccw.cell(r, 2).value}
    ext = [('picorv32_nola', 'picorv32', 'registered-ready memory (dhrystone/testbench_nola.v)'),
           ('picorv32_la', 'picorv32', 'look-ahead memory (dhrystone/testbench.v) -- best case'),
           ('vexriscv', 'vexriscv_nodebug', 'GenFullNoMmuNoCache, DebugPlugin removed'),
           ('rvcorep', 'rvcorep', 'v0.5.3 default configuration')]
    trows = []
    for cfg, ccname, desc in ext:
        d = {r['benchmark']: r for r in tp if r['config'] == cfg}
        lut, fmax = cc[ccname]
        dm, cmm = float(d['dhrystone']['value']), float(d['coremark']['value'])
        trows.append([d['dhrystone']['core'], d['dhrystone']['isa'], desc, dm, cmm, float(d['dhrystone']['cpi']),
                      float(d['coremark']['cpi']), lut, fmax, round(dm * fmax, 1), round(cmm * fmax, 1),
                      'cycle-accurate simulation, RV-IM100 images'])
    trows.append([None] * 12)
    for r in cmrows:
        v = r['variant']
        if not v.startswith('RV32'):
            continue
        ws0 = wb['RV32 SoC and FPGA']
        dm = next(float(str(ws0.cell(k, 5).value).split('@')[0]) for k in range(3, 11)
                  if 'RV32' + str(ws0.cell(k, 2).value) == v)
        lut, fmax = cc[v]
        cmm = board[v]['true_cm_mhz']
        trows.append([v, 'RV32I' if v == 'RV32I_5SP' else 'RV32IM', 'RV-IM100', dm, round(cmm, 4),
                      round(float(r['Dhrystone cycles/iter']) / float(r['Dhrystone instr/iter']), 4),
                      float(r['CoreMark CPI']), lut, fmax, round(dm * fmax, 1), round(cmm * fmax, 1),
                      'FPGA: Dhrystone board run; CoreMark board Total ticks'])
    ws = new_sheet(wb, 'Core throughput', 'Throughput of the comparison cores, measured under the RV-IM100 methodology',
                   notes_top[0] if notes_top else '',
                   ['core', 'ISA', 'configuration', 'DMIPS/MHz', 'CoreMark/MHz', 'CPI (Dhry)', 'CPI (CM)', 'LUT (core)',
                    'core-only Fmax (MHz)', 'DMIPS @ Fmax', 'CoreMark @ Fmax', 'source'],
                   trows, widths={'configuration': 44, 'source': 40, 'core': 22},
                   formats={'DMIPS/MHz': '0.000', 'CoreMark/MHz': '0.000', 'CPI (Dhry)': '0.000', 'CPI (CM)': '0.000'})
    r0 = 6 + len(trows) + 1
    tail = notes_top[1:] + notes_bot + [
        'RV-IM100 CoreMark/MHz is iterations x 1e6 / Total_ticks from the board (CoreMark true score sheet).  '
        'External-core throughput is cycle-accurate simulation at the synthesized core boundary, not a board run.']
    for i, t in enumerate(tail, r0):
        ws.cell(i, 2, t).font = Font(name=F, sz=11)
    wb._sheets.remove(ws)
    wb._sheets.insert(wb.sheetnames.index('Core comparison') + 1, ws)
    log.append(('Core throughput', f'B5:M{5 + len(trows)}', 'new sheet', None,
                'external cores (4 configurations) + RV-IM100 RV32 variants: DMIPS/MHz, CoreMark/MHz, CPI, LUT, Fmax',
                '[R1.4/R3.6] throughput of PicoRV32, VexRiscv and RVCoreP on the RV-IM100 benchmark images',
                'comparison_cores/throughput/out/throughput.csv, comparison_cores/PROVENANCE.md'))

    # -------------------------------------------------------------- 9. Contents rows for the new sheets
    ws = wb['Contents']
    r = next(r for r in range(1, ws.max_row + 1) if str(ws.cell(r, 2).value or '') == 'Known gaps')
    ws.insert_rows(r, 8)
    for i, (nm, desc) in enumerate([
            ('Core throughput', 'DMIPS/MHz, CoreMark/MHz and CPI of PicoRV32, VexRiscv and RVCoreP measured on the '
                                'RV-IM100 benchmark images, beside the RV32 variants.'),
            ('CoreMark true score', 'The printed CoreMark integer and the tick-derived score side by side, with the '
                                    'derivation as live formulas and the withoutOpt image error.'),
            ('Stall breakdown by cause', 'Additive, cause-based partition of every cycle: 112 runs, exact on 112/112.  '
                                         'Splits the 8-stage "load-use" signal into load-use and execution-use.'),
            ('AAPG vs 5SP', 'Randomized programs compared with the 5-stage core on the identical ROM image: 113/113 identical.'),
            ('Dynamic instruction mix', 'Instructions per iteration and dynamic mix, from the difference of two iteration counts.'),
            ('Worst paths', 'Worst setup path of each SoC build, from the final implementation reports.'),
            ('SAIF capture windows', 'Which cycles, instructions and functions each SAIF capture sampled, and the '
                                     'idle-core validity check.')], r):
        ws.cell(i, 2, nm).font = copy.copy(ws.cell(r - 1, 2).font)
        ws.cell(i, 3, desc).font = copy.copy(ws.cell(r - 1, 3).font)
    ws.cell(3, 2, f'built 2026-09-21; revised and frozen {datetime.date.today().isoformat()} '
                  f'(revision_0922/, see sheet "Change log 0923")')

    order_after = wb.sheetnames.index('Normalized metrics') + 1
    sh = wb['CoreMark true score']
    wb._sheets.remove(sh)
    wb._sheets.insert(order_after, sh)

    # -------------------------------------------------------------- 10. change log
    ws = new_sheet(wb, 'Change log 0923', 'Every cell this file changes relative to Research_data_MASTER_0921.xlsx',
                   'Applied by revision_0922/tools/apply_changes.py from the reviewed change list in '
                   'revision_0922/Revision_review_0923.xlsx.  The master file is unmodified.  Each row names the task '
                   'that produced the number and the report that justifies it.',
                   ['#', 'sheet', 'cell', 'field', 'old value', 'new value', 'reason', 'evidence'],
                   [[i] + [str(x)[:400] if isinstance(x, str) else x for x in row] for i, row in enumerate(log, 1)],
                   widths={'reason': 58, 'evidence': 34, 'old value': 30, 'new value': 30, 'sheet': 24, 'field': 20})
    for r in range(6, 6 + len(log)):
        for c in (6, 7, 8, 9):
            ws.cell(r, c).alignment = Alignment(wrap_text=True, vertical='top')
    if skipped:
        r0 = 6 + len(log) + 2
        ws.cell(r0, 2, 'NOT applied (target had moved; left as the master had it)').font = Font(name=F, sz=11, b=True)
        for i, s in enumerate(skipped, r0 + 1):
            for j, v in enumerate(s, 2):
                ws.cell(i, j, str(v)[:200]).font = Font(name=F, sz=11)

    wb.save(OUT)
    print(f'wrote {OUT}')
    print(f'applied {len(log)} changes across {len({l[0] for l in log})} sheets; '
          f'{len(wb.sheetnames)} sheets total')
    if skipped:
        print(f'NOT applied: {len(skipped)}')
        for s in skipped:
            print('   ', s[0], s[1], s[2], '| expected', str(s[3])[:60], '| found', str(s[4])[:60], '|', s[5])


if __name__ == '__main__':
    main()
