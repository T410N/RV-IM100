import json, html
S="/tmp/rv-im100"
rows=json.load(open(f"{S}/report_rows.json"))

STALL=[("1","pc"),("2","front-end"),("3","ID/EX"),("4","EXR/EX"),("5","EX/EX2"),
       ("6","EX/MEM"),("7","MEM/WB"),("8","load-use"),("9","div busy"),("10","mul busy")]
CPI_MAX=2.30

def fam(v): return "RV64" if v.startswith("RV64") else "RV32"
def esc(s): return html.escape(str(s))

def cpi_cell(x):
    pct=100.0*x/CPI_MAX
    return (f'<td class="num"><span class="bar" style="--w:{pct:.1f}%"></span>'
            f'<span class="v">{x:.3f}</span></td>')

def pct_cell(val, avail):
    if not avail: return '<td class="num na">n/a</td>'
    cls=" hot" if val>=10 else ""
    return (f'<td class="num"><span class="bar sm{cls}" style="--w:{min(val,40)/40*100:.1f}%"></span>'
            f'<span class="v">{val:.1f}</span></td>')

def perf_table(bench):
    out=[]
    last=None
    for r in rows:
        d=r[bench]; f=fam(r["v"])
        if f!=last:
            out.append(f'<tr class="grp"><th colspan="9">{f} family</th></tr>'); last=f
        br=d["branch"]; mis=d["mispred"]; ret=d["retired"]
        out.append(
          "<tr>"
          f'<th scope="row">{esc(r["v"])}</th>'
          + cpi_cell(d["cpi"])
          + f'<td class="num">{d["ipc"]:.3f}</td>'
          + f'<td class="num">{d["cycles"]:,}</td>'
          + f'<td class="num">{100*br/ret:.1f}</td>'
          + f'<td class="num">{mis:,}</td>'
          + f'<td class="num">{100*mis/br if br else 0:.1f}</td>'
          + f'<td class="num">{100*d["load"]/ret:.1f}</td>'
          + f'<td class="num">{d["mul"]:,}</td>'
          "</tr>")
    return "\n".join(out)

def stall_table(bench):
    out=[]; last=None
    for r in rows:
        d=r[bench]; av=r["avail"]; f=fam(r["v"])
        if f!=last:
            out.append(f'<tr class="grp"><th colspan="11">{f} family</th></tr>'); last=f
        cells="".join(pct_cell(d[f"s{i}"], av.get(i, False)) for i,_ in STALL)
        out.append(f'<tr><th scope="row">{esc(r["v"])}</th>{cells}</tr>')
    return "\n".join(out)

PERF_HEAD="".join(f"<th>{h}</th>" for h in
  ["CPI","IPC","cycles","br %","mispred","miss %","load %","mul"])
STALL_HEAD="".join(f"<th>{l}</th>" for _,l in STALL)

doc=f"""<title>RV-IM100 Pipeline Profile</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<style>
:root {{
  --ground:#F5F7F9; --panel:#FFFFFF; --panel-2:#EEF1F5;
  --ink:#131820; --ink-2:#48525F; --ink-3:#78838F;
  --line:#DCE1E8; --line-2:#C6CED8;
  --accent:#35558A; --accent-soft:#DCE5F2;
  --warn:#A2621A; --warn-soft:#F2E4CF;
  --good:#2C7A66;
  --shadow:0 1px 2px rgba(19,24,32,.05), 0 8px 24px -12px rgba(19,24,32,.16);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ground:#0D1117; --panel:#151B23; --panel-2:#1C242E;
    --ink:#E3E8EF; --ink-2:#A3AEBC; --ink-3:#76818F;
    --line:#242D38; --line-2:#33404E;
    --accent:#7FA3D9; --accent-soft:#1E2B3F;
    --warn:#D9A055; --warn-soft:#33281A;
    --good:#5FB59C;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 28px -14px rgba(0,0,0,.7);
  }}
}}
:root[data-theme="dark"] {{
  --ground:#0D1117; --panel:#151B23; --panel-2:#1C242E;
  --ink:#E3E8EF; --ink-2:#A3AEBC; --ink-3:#76818F;
  --line:#242D38; --line-2:#33404E;
  --accent:#7FA3D9; --accent-soft:#1E2B3F;
  --warn:#D9A055; --warn-soft:#33281A;
  --good:#5FB59C;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 28px -14px rgba(0,0,0,.7);
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:15px; line-height:1.6;
  -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:1120px; margin:0 auto; padding:0 24px 96px; }}
.eyebrow {{
  font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:11px; letter-spacing:.13em; text-transform:uppercase;
  color:var(--ink-3); font-weight:500;
}}
header.mast {{
  border-bottom:1px solid var(--line); margin-bottom:40px;
  padding:56px 0 28px;
}}
h1 {{
  font-size:clamp(30px,4.2vw,44px); line-height:1.1; margin:10px 0 14px;
  font-weight:700; letter-spacing:-.022em; text-wrap:balance;
}}
.sub {{ color:var(--ink-2); max-width:66ch; margin:0; font-size:16px; }}
.meta {{
  display:flex; flex-wrap:wrap; gap:0 28px; margin-top:24px;
  font-family:"IBM Plex Mono",monospace; font-size:12px; color:var(--ink-2);
}}
.meta b {{ color:var(--ink); font-weight:500; }}
section {{ margin-top:52px; }}
h2 {{
  font-size:20px; font-weight:600; letter-spacing:-.012em;
  margin:0 0 6px; text-wrap:balance;
}}
.lede {{ color:var(--ink-2); margin:0 0 20px; max-width:70ch; }}
.finding {{
  background:var(--panel); border:1px solid var(--line);
  border-left:3px solid var(--accent);
  border-radius:3px; padding:22px 24px; box-shadow:var(--shadow);
  display:grid; gap:16px; grid-template-columns:minmax(0,1fr) auto; align-items:center;
}}
@media (max-width:720px) {{ .finding {{ grid-template-columns:1fr; }} }}
.finding p {{ margin:8px 0 0; color:var(--ink-2); max-width:62ch; }}
.finding .big {{
  font-family:"IBM Plex Mono",monospace; font-weight:600;
  font-size:clamp(28px,5vw,40px); color:var(--warn); line-height:1;
  white-space:nowrap; font-variant-numeric:tabular-nums;
}}
.finding .big small {{ display:block; font-size:11px; letter-spacing:.11em;
  text-transform:uppercase; color:var(--ink-3); margin-top:8px; font-weight:500; }}
.scroll {{ overflow-x:auto; border:1px solid var(--line); border-radius:3px;
  background:var(--panel); box-shadow:var(--shadow); }}
table {{ border-collapse:collapse; width:100%; font-size:13px; }}
caption {{ text-align:left; padding:14px 18px 0; color:var(--ink-3);
  font-family:"IBM Plex Mono",monospace; font-size:11px;
  letter-spacing:.1em; text-transform:uppercase; }}
th, td {{ padding:7px 12px; text-align:left; white-space:nowrap; }}
thead th {{
  font-family:"IBM Plex Mono",monospace; font-size:11px; font-weight:500;
  letter-spacing:.06em; color:var(--ink-3); text-transform:uppercase;
  border-bottom:1px solid var(--line-2); text-align:right;
}}
thead th:first-child {{ text-align:left; }}
tbody th {{ font-weight:500; font-size:13px;
  font-family:"IBM Plex Mono",monospace; color:var(--ink); }}
tbody tr:not(.grp):hover {{ background:var(--panel-2); }}
tr.grp th {{
  font-family:"IBM Plex Mono",monospace; font-size:10px; font-weight:600;
  letter-spacing:.14em; text-transform:uppercase; color:var(--accent);
  padding:16px 12px 5px; border-bottom:1px solid var(--line);
}}
td.num {{ text-align:right; font-family:"IBM Plex Mono",monospace;
  font-variant-numeric:tabular-nums; position:relative; }}
td.num .v {{ position:relative; }}
td.num .bar {{
  position:absolute; right:8px; top:50%; transform:translateY(-50%);
  height:16px; width:var(--w); max-width:calc(100% - 12px);
  background:var(--accent-soft); border-radius:2px; z-index:0;
}}
td.num .bar.sm {{ height:13px; }}
td.num .bar.hot {{ background:var(--warn-soft); }}
td.na {{ color:var(--ink-3); }}
.caveats {{ border:1px solid var(--line-2); border-radius:3px;
  background:var(--panel); padding:6px 24px 20px; }}
.caveats ol {{ margin:0; padding-left:20px; }}
.caveats li {{ margin:14px 0; color:var(--ink-2); max-width:74ch; }}
.caveats li b {{ color:var(--ink); font-weight:600; }}
code {{ font-family:"IBM Plex Mono",monospace; font-size:.92em;
  background:var(--panel-2); padding:1px 5px; border-radius:2px; }}
pre {{ margin:0; background:var(--panel); border:1px solid var(--line);
  border-radius:3px; padding:16px 18px; overflow-x:auto;
  font-family:"IBM Plex Mono",monospace; font-size:12.5px;
  line-height:1.7; color:var(--ink-2); }}
pre b {{ color:var(--ink); font-weight:500; }}
footer {{ margin-top:56px; padding-top:20px; border-top:1px solid var(--line);
  color:var(--ink-3); font-size:12px; font-family:"IBM Plex Mono",monospace; }}
a {{ color:var(--accent); }}
:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}
</style>

<div class="wrap">
<header class="mast">
  <div class="eyebrow">RV-IM100 · verification data · 2026-09-06</div>
  <h1>Pipeline profile across sixteen variants</h1>
  <p class="sub">Cycle-accurate CPI, instruction mix, branch behaviour and stall-cycle
  breakdown for every RV-IM100 SoC variant, measured on the same ROM images the
  FPGA runs used. Collected for the TVLSI revision (R1.3, R2.3, R3.4, R3.5).</p>
  <div class="meta">
    <span><b>16</b> variants</span>
    <span><b>2</b> benchmarks</span>
    <span><b>10,000,000</b> retired instructions each</span>
    <span><b>32/32</b> runs reached budget</span>
  </div>
</header>

<section>
  <div class="eyebrow">Headline</div>
  <h2>Load-use stalls explain the 8-stage CPI regression</h2>
  <div class="finding">
    <div>
      <p>Cycles lost to load-use hazards stay near <b>1.2%</b> from six through
      seven stages, then jump to <b>~18%</b> at eight. That single term accounts
      for most of the CPI increase from 1.66 to 2.20 on Dhrystone, and turns the
      paper's execution-use-hazard argument from an inference into a measurement.</p>
    </div>
    <div class="big">1.2 → 18%<small>load-use stall cycles, 7SP → 8SP</small></div>
  </div>
</section>

<section>
  <div class="eyebrow">Method</div>
  <h2>How these numbers were taken</h2>
  <p class="lede">Counters live in the simulation wrapper, never in the core, so the
  RTL profiled here is bit-identical to the RTL that produced the Fmax, area and
  power figures. Each variant runs the ROM image from its own Vivado project.
  Runs stop after a fixed <em>retired-instruction</em> count rather than a fixed
  cycle count — every variant then performs identical work and only the cycle
  count differs, which is what makes CPI comparable across pipeline depths.</p>
</section>

<section>
  <div class="eyebrow">Dhrystone</div>
  <h2>CPI and instruction mix</h2>
  <div class="scroll"><table>
    <caption>10M retired instructions · bar scaled to CPI 2.30</caption>
    <thead><tr><th>variant</th>{PERF_HEAD}</tr></thead>
    <tbody>{perf_table('dh')}</tbody>
  </table></div>
</section>

<section>
  <div class="eyebrow">CoreMark</div>
  <h2>CPI and instruction mix</h2>
  <div class="scroll"><table>
    <caption>10M retired instructions · bar scaled to CPI 2.30</caption>
    <thead><tr><th>variant</th>{PERF_HEAD}</tr></thead>
    <tbody>{perf_table('cm')}</tbody>
  </table></div>
</section>

<section>
  <div class="eyebrow">Dhrystone</div>
  <h2>Stall cycles, percent of total</h2>
  <p class="lede">A stall propagates backwards through the pipeline, so the pc,
  front-end and ID/EX columns are one stall observed at several stages — they are
  <em>not</em> additive. Stages a variant does not have read <code>n/a</code>
  rather than zero, since zero would wrongly say "never stalled". Amber marks
  columns at or above 10%.</p>
  <div class="scroll"><table>
    <caption>bar scaled to 40% of cycles</caption>
    <thead><tr><th>variant</th>{STALL_HEAD}</tr></thead>
    <tbody>{stall_table('dh')}</tbody>
  </table></div>
</section>

<section>
  <div class="eyebrow">CoreMark</div>
  <h2>Stall cycles, percent of total</h2>
  <div class="scroll"><table>
    <caption>bar scaled to 40% of cycles</caption>
    <thead><tr><th>variant</th>{STALL_HEAD}</tr></thead>
    <tbody>{stall_table('cm')}</tbody>
  </table></div>
</section>

<section>
  <div class="eyebrow">Before citing these numbers</div>
  <h2>Caveats that belong in the paper</h2>
  <div class="caveats"><ol>
    <li><b>NOPs are excluded from the retired count</b>, matching the cores' own
    <code>minstret</code> definition. This shifts IPC slightly against a
    Sail-counted instruction total, so state the definition rather than leaving
    it implicit.</li>
    <li><b>I-only variants run different binaries</b> from the IM variants — no
    hardware multiply, so the compiler emits a software routine. CPI is
    comparable within the IM family and across pipeline depth, but not directly
    between I and IM. The pipeline-depth axis, which is the paper's main claim,
    is unaffected.</li>
    <li><b>These are fixed-instruction windows, not complete benchmark runs.</b>
    The published Dhrystone and CoreMark scores still come from the FPGA runs;
    these figures characterise microarchitectural behaviour, not final scores.</li>
    <li><b>Stall percentages are not additive</b> across the pipeline columns,
    for the reason given above. Summing them produces a meaningless total.</li>
    <li><b>Mispredictions are identical across 5SP, 6SP and 7SP</b> — same binary,
    same predictor, same branch outcomes — and rise slightly at 7SP_BRAM and 8SP,
    where predictor state updates later relative to fetch. The designs do have a
    branch predictor, so Reviewer 1's misprediction request applies and is
    answered.</li>
  </ol></div>
</section>

<section>
  <div class="eyebrow">Reproduce</div>
  <h2>Commands</h2>
  <pre><b>cd riscof-env</b>
RVIM_SOURCE=socs python3 scripts/prepare_rtl.py
RVIM_SOURCE=socs scripts/build_sim.sh all
python3 scripts/profile_all.py --instr 10000000

<b># outputs</b>
logs/profile.csv            per-variant counters, machine readable
logs/profile_report.txt     the formatted tables</pre>
</section>

<footer>
  RV-IM100 · profiling counters in <code>scripts/prepare_rtl.py</code>,
  driver in <code>scripts/profile_all.py</code> · data in
  <code>logs/profile.csv</code>
</footer>
</div>
"""
open(f"{S}/report/profile.html","w").write(doc)
print("wrote profile.html  (%d bytes)" % len(doc))
