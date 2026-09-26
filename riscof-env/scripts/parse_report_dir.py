#!/usr/bin/env python3
"""Parse a saved <tag>/ report dir (utilization.rpt, power.rpt) + its run log.

Used for rows whose project no longer holds that benchmark's image, so they
cannot be re-measured without another implementation run.
"""
import re, pathlib

CATS = ["Clocks","Slice Logic","Signals","Block RAM","DSPs","PLL","MMCM","I/O","Static Power","Total"]

def util(p):
    t = pathlib.Path(p).read_text(errors="replace"); out = {}
    for tag, pat in (("lut",r"Slice LUTs\*?"),("lut_logic",r"LUT as Logic"),
                     ("lutram",r"LUT as Memory"),("ff",r"Slice Registers"),
                     ("bram",r"Block RAM Tile"),("dsp",r"DSPs"),("io",r"Bonded IOB"),
                     ("mmcm",r"MMCME2_ADV"),("pll",r"PLLE2_ADV")):
        m = re.search(rf"\|\s+{pat}\s*\|\s+(\d+)\s+\|", t)
        if m: out.setdefault(tag, int(m.group(1)))
    return out

def power(p):
    t = pathlib.Path(p).read_text(errors="replace"); out = {}
    for line in t.splitlines():
        m = re.match(r"^\s*\|\s*([A-Za-z0-9 /_-]+?)\s*\|\s*([0-9]+\.[0-9]+)\s*\|", line)
        if m and m.group(1).strip() in CATS and m.group(1).strip() not in out:
            out[m.group(1).strip()] = float(m.group(2))
            if m.group(1).strip() == "Total": break
    return out

def clocks(logp):
    t = pathlib.Path(logp).read_text(errors="replace")
    for m in re.findall(r"^CLOCK name=(\S+) period=\S+ mhz=(\S+) wns=(\S+) fmax=(\S+)", t, re.M):
        if m[2] not in ("none",""):
            return dict(core_clk=m[0], constraint_mhz=float(m[1]),
                        wns_ns=float(m[2]), fmax_mhz=float(m[3]))
    return None

def row(tag, rptdir, logp):
    c = clocks(logp)
    if not c: return None
    u = util(pathlib.Path(rptdir)/"utilization.rpt")
    w = power(pathlib.Path(rptdir)/"power.rpt")
    g = lambda k: w.get(k, 0.0)
    return dict(**c, lut=u.get("lut") or (u.get("lut_logic",0)+u.get("lutram",0)),
                lut_logic=u.get("lut_logic"), lutram=u.get("lutram",0), ff=u.get("ff"),
                bram=u.get("bram",0), dsp=u.get("dsp",0), io=u.get("io",0),
                pll=(u.get("pll",0)+u.get("mmcm",0)),
                p_clocks=g("Clocks"), p_signals=g("Signals"), p_logic=g("Slice Logic"),
                p_bram=g("Block RAM"), p_dsp=g("DSPs"),
                p_pll=w.get("PLL", w.get("MMCM",0.0)), p_io=g("I/O"),
                p_static=w.get("Static Power"), p_total=w.get("Total"))
