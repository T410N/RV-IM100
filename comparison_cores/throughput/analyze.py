#!/usr/bin/env python3
"""Throughput of the comparison cores from the harness logs.

A run counts only if it ended on the harness halt, read the timer exactly twice,
and passed its benchmark's own correctness check: every Dhrystone "should be"
line, or CoreMark's CRC validation.  Throughput is computed from the cycles
between the two timer reads -- the window the software itself times.
    DMIPS/MHz      = runs * 1e6 / (cycles * 1757)
    CoreMark/MHz   = iterations * 1e6 / cycles
"""
import csv, re, pathlib
T = pathlib.Path(__file__).resolve().parent
CFG = {  # name: (core, ISA, memory model)
  "picorv32_la":   ("PicoRV32", "RV32IM", "look-ahead (picorv32 dhrystone/testbench.v)"),
  "picorv32_nola": ("PicoRV32", "RV32IM", "registered ready (picorv32 dhrystone/testbench_nola.v)"),
  "vexriscv":      ("VexRiscv", "RV32IM", "simple bus, response next cycle"),
  "rvcorep":       ("RVCoreP",  "RV32I",  "synchronous read, as its D_SYNC_IMEM/DMEM"),
}
DHRY_RUNS = 300000

def dhry_ok(text):
    lines = [l.rstrip() for l in text.splitlines()]
    bad, prev_ptr = [], None
    for i, l in enumerate(lines):
        m = re.match(r"\s*should be:\s*(.*)$", l)
        if not m: continue
        got = lines[i-1].split(":", 1)[1].strip()
        want = m.group(1).strip()
        name = lines[i-1].split(":", 1)[0].strip()
        if want == "Number_Of_Runs + 10":             ok = got == str(DHRY_RUNS + 10)
        elif want == "(implementation-dependent)":     ok = True; prev_ptr = got
        elif want.startswith("(implementation-dependent), same as above"): ok = got == prev_ptr
        else:                                          ok = got == want
        if not ok: bad.append(f"{name}={got} want {want}")
    n = sum(1 for l in lines if "should be:" in l)
    # Dhrystone 2.1 prints 22: 6 globals, 5 fields each of Ptr_Glob and Next_Ptr_Glob, 6 locals
    return (n == 22 and not bad), f"{n} checks" + (f"; FAIL {bad}" if bad else "")

rows = []
for cfg, (core, isa, mem) in CFG.items():
    for bench in ("dhrystone", "coremark"):
        text = (T/"out"/f"{cfg}_{bench}.log").read_text(errors="replace").replace("\r", "")
        reads  = [(int(a), int(b)) for a, b in re.findall(r"^TIMER (\d+) INSTRET (\d+)$", text, re.M)]
        timers = [a for a, _ in reads]
        instr  = reads[1][1] - reads[0][1] if len(reads) == 2 and reads[1][1] else None
        ended  = bool(re.search(r"^HALT cycles=\d+$", text, re.M)) and not re.search(r"^(FATAL|TIMEOUT)", text, re.M)
        if bench == "dhrystone":
            ok, note = dhry_ok(text); units = DHRY_RUNS
        else:
            ok = "Correct operation validated" in text and "Errors detected" not in text
            units = int(re.search(r"Iterations\s*:\s*(\d+)", text).group(1))
            crc = re.search(r"\[0\]crcfinal\s*:\s*(0x[0-9a-f]+)", text)
            note = f"crcfinal {crc.group(1) if crc else '?'}"
        valid = ended and len(timers) == 2 and ok
        cyc = timers[1] - timers[0] if len(timers) == 2 else None
        per = cyc / units if cyc else None
        score = (units * 1e6 / (cyc * 1757) if bench == "dhrystone" else units * 1e6 / cyc) if cyc else None
        rows.append(dict(config=cfg, core=core, isa=isa, memory=mem, benchmark=bench,
                         status="VALID" if valid else "INVALID", units=units, roi_cycles=cyc,
                         cycles_per_unit=round(per, 2) if per else "",
                         metric="DMIPS/MHz" if bench == "dhrystone" else "CoreMark/MHz",
                         value=round(score, 4) if score else "",
                         roi_instret=instr or "", cpi=round(cyc / instr, 4) if instr and cyc else "",
                         check=note))
# VexRiscv has no counter wired to the harness.  Retired-instruction count is
# architectural, and VexRiscv runs the same rv32im images as PicoRV32, so take it
# from there -- after checking PicoRV32's two memory models agree on it.
by = {(r["config"], r["benchmark"]): r for r in rows}
for b in ("dhrystone", "coremark"):
    la, nola, vx = by[("picorv32_la", b)], by[("picorv32_nola", b)], by[("vexriscv", b)]
    assert la["roi_instret"] == nola["roi_instret"], (b, la["roi_instret"], nola["roi_instret"])
    vx["roi_instret"] = la["roi_instret"]
    vx["cpi"] = round(vx["roi_cycles"] / la["roi_instret"], 4)
    vx["check"] += "; instret from PicoRV32 on the same image"
for r in rows:
    r["ipc"] = round(1 / r["cpi"], 4) if r["cpi"] else ""
with open(T/"out"/"throughput.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(f"  {'config':<15}{'bench':<11}{'status':<9}{'ROI cycles':>13}{'cyc/unit':>12}  {'value':>8} {'metric':<13} check")
for r in rows:
    print(f"  {r['config']:<15}{r['benchmark']:<11}{r['status']:<9}{r['roi_cycles']:>13}{r['cycles_per_unit']:>12}  "
          f"{r['value']:>8} {r['metric']:<13} CPI {str(r['cpi']):<7} {r['check']}")
