"""T14 figures: regenerated from the same data as paper_numbers.csv.

Called by paper_numbers.py --figures.  Every figure is a single-column IEEE figure
(3.5 in wide), PDF, text >= 8 pt at final size, one y-axis, RV32/RV64 as the only two
categorical series (validated palette slots 1-2: CVD dE 24.7, normal-vision dE 33.6),
RV64 additionally hatched so series identity survives grayscale printing.
"""
import os, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RV32, RV64 = '#2a78d6', '#eb6834'
INK, INK2, GRID = '#0b0b0b', '#52514e', '#e3e2de'
W = 3.5

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Liberation Sans', 'Arial', 'DejaVu Sans'],
    'font.size': 8, 'axes.labelsize': 8, 'axes.titlesize': 8, 'xtick.labelsize': 8, 'ytick.labelsize': 8,
    'legend.fontsize': 8, 'axes.edgecolor': INK2, 'axes.labelcolor': INK, 'xtick.color': INK2, 'ytick.color': INK2,
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.linewidth': 0.6,
    'xtick.major.width': 0.6, 'ytick.major.width': 0.6, 'pdf.fonttype': 42, 'hatch.linewidth': 0.6,
})


def _ax(h=2.1):
    fig, ax = plt.subplots(figsize=(W, h))
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    return fig, ax


def _bars(ax, labels, s32, s64, ylabel, loc='upper left'):
    n = len(labels)
    x = range(n)
    bw = 0.38
    b1 = ax.bar([i - bw / 2 - 0.01 for i in x], s32, bw, color=RV32, edgecolor='white', linewidth=0.6, label='RV32')
    b2 = ax.bar([i + bw / 2 + 0.01 for i in x], s64, bw, color=RV64, edgecolor='white', linewidth=0.6,
                hatch='////', label='RV64')
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=35, ha='right')
    ax.set_ylabel(ylabel)
    ax.legend(frameon=False, loc=loc, ncol=2, handlelength=1.2, borderaxespad=0.2)
    ax.margins(x=0.02)
    if loc == 'upper left':                    # headroom so the legend never sits on a bar
        top = max(list(s32) + list(s64))
        ax.set_ylim(0, top * 1.28)
    return b1, b2


def _save(fig, out, name):
    fig.tight_layout(pad=0.3)
    p = os.path.join(out, name)
    fig.savefig(p)
    plt.close(fig)
    return p


def make(D, VAR, LABEL, fpga, benches, out):
    os.makedirs(out, exist_ok=True)
    v = lambda a, x, k: D[(a, x)][k][0]
    labels = [LABEL[x] for x in VAR]
    made = []

    def per(k, fn=lambda y, a, x: y):
        return ([fn(v('RV32', x, k), 'RV32', x) for x in VAR], [fn(v('RV64', x, k), 'RV64', x) for x in VAR])

    specs = [
        ('fig_soc_fmax.pdf', 'soc_fmax_dhry', lambda y, a, x: y, 'SoC $F_\\mathrm{max}$ (MHz)'),
        ('fig_core_fmax.pdf', 'core_fmax', lambda y, a, x: y, 'Core-only $F_\\mathrm{max}$ (MHz)'),
        ('fig_dhry_abs.pdf', 'dhry_per_s', lambda y, a, x: y / 1757.0, 'DMIPS'),
        ('fig_dmips_mhz.pdf', 'dhry_per_s', lambda y, a, x: y / 1757.0 / v(a, x, 'dhry_mhz'), 'DMIPS/MHz'),
        ('fig_cm_abs.pdf', 'cm_true', lambda y, a, x: y, 'CoreMark (iterations/s)'),
        ('fig_cm_mhz.pdf', 'cm_true', lambda y, a, x: y / v(a, x, 'cm_mhz'), 'CoreMark/MHz'),
        ('fig_lut.pdf', 'core_lut', lambda y, a, x: y / 1000, 'Core LUTs (thousands)'),
        ('fig_ff.pdf', 'core_ff', lambda y, a, x: y / 1000, 'Core flip-flops (thousands)'),
    ]
    for name, k, fn, yl in specs:
        fig, ax = _ax()
        s32, s64 = per(k, fn)
        _bars(ax, labels, s32, s64, yl)
        made.append(_save(fig, out, name))

    # power: SAIF dynamic, Dhrystone windows (phase-matched across variants)
    fig, ax = _ax()
    s32 = [float(D[('RV32', x)]['saif_dhrystone'][0]['saif_dynamic']) for x in VAR]
    s64 = [float(D[('RV64', x)]['saif_dhrystone'][0]['saif_dynamic']) for x in VAR]
    _bars(ax, labels, s32, s64, 'Dynamic power, Dhrystone (W)')
    made.append(_save(fig, out, 'fig_power.pdf'))

    # energy per Dhrystone iteration, core-attributable
    fig, ax = _ax()
    s32 = [float(D[('RV32', x)]['norm'][0]['uJ_per_Dhry_iter_core_attr']) for x in VAR]
    s64 = [float(D[('RV64', x)]['norm'][0]['uJ_per_Dhry_iter_core_attr']) for x in VAR]
    _bars(ax, labels, s32, s64, 'Energy per Dhrystone iteration,\ncore-attributable ($\\mu$J)')
    made.append(_save(fig, out, 'fig_energy_dhry.pdf'))

    # CPI, two panels sharing the x categories (one axis each, same unit)
    fig, axs = plt.subplots(1, 2, figsize=(W * 2, 2.1), sharey=True)
    for ax, (bench, ck, ik) in zip(axs, (('Dhrystone', 'dh_cyc_iter', 'dh_ins_iter'), ('CoreMark', 'cm_cyc_iter', 'cm_ins_iter'))):
        ax.yaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        s32 = [v('RV32', x, ck) / v('RV32', x, ik) for x in VAR]
        s64 = [v('RV64', x, ck) / v('RV64', x, ik) for x in VAR]
        _bars(ax, labels, s32, s64, 'CPI' if bench == 'Dhrystone' else '')
        ax.set_title(bench, loc='left', color=INK)
    made.append(_save(fig, out, 'fig_cpi.pdf'))

    # 2x2 ablation around 7 -> 8: gain vs IM-7 in Dhrystones/s
    fig, ax = _ax(2.2)
    cats = ['Optimisations\nonly (IM-7 Opt)', 'EXR only\n(IM-8 noOpt)', 'Both\n(IM-8)', 'Sum of the\ntwo alone']
    def gains(a):
        b = v(a, 'IM_7SP_BRAM', 'dhry_per_s')
        eo = v(a, 'IM_7SP_BRAM_Opt', 'dhry_per_s') / b - 1
        ee = v(a, 'IM_8SP_withoutOpt', 'dhry_per_s') / b - 1
        eb = v(a, 'IM_8SP', 'dhry_per_s') / b - 1
        return [100 * eo, 100 * ee, 100 * eb, 100 * (eo + ee)]
    _bars(ax, cats, gains('RV32'), gains('RV64'), 'Dhrystone gain vs IM-7 (%)')
    ax.set_xticklabels(cats, rotation=0, ha='center')
    ax.axvline(2.5, color=INK2, linewidth=0.6, linestyle=(0, (2, 2)))
    made.append(_save(fig, out, 'fig_ablation.pdf'))

    # Embench geomean runtime relative to IM-5 (RV64 measured on FPGA; RV32 simulated until T1)
    def gm(a, x):
        rs = []
        for b in benches:
            if (a, x, b) in fpga and (a, 'IM_5SP', b) in fpga:
                c, m, _ = fpga[(a, x, b)]
                c0, m0, _ = fpga[(a, 'IM_5SP', b)]
                rs.append((c / m) / (c0 / m0))
        return math.exp(sum(map(math.log, rs)) / len(rs)) if len(rs) == len(benches) else float('nan')
    iv = [x for x in VAR if x != 'I_5SP']
    fig, ax = _ax()
    rv32_measured = all(str(fpga[k][2]).startswith('FPGA') for k in fpga if k[0] == 'RV32')
    _bars(ax, [LABEL[x] for x in iv], [gm('RV32', x) for x in iv], [gm('RV64', x) for x in iv],
          'Embench runtime vs IM-5\n(geomean of 5, lower is better)')
    ax.axhline(1.0, color=INK2, linewidth=0.6)
    if not rv32_measured:
        ax.set_title('RV32: RTL simulation (board runs pending)', loc='right', fontsize=7, color=INK2)
    made.append(_save(fig, out, 'fig_embench_geomean.pdf'))

    print(f'{len(made)} figures -> {out}')
    return made
