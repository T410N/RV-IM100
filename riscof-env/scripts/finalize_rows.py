#!/usr/bin/env python3
"""Bring specific (variant, benchmark) rows to a clean, timing-met operating point
and regenerate their bitstreams.

For each row: build the .mem for the target frequency, set PLL + BAUD_DIV,
re-implement, read the ACHIEVED clock back. Then
  * if it violates  -> retarget at floor(Fmax) and retry
  * if the achieved clock differs from what the image was built for by more than
    0.05 MHz -> rebuild the image at the achieved frequency and re-implement, so
    the benchmark's own timing constant matches the clock it actually runs at
  * otherwise -> write the bitstream and stop
Bounded iterations; stops on a repeated target.
"""
import json, math, pathlib, re, shutil, subprocess, sys, time, os

ENV  = pathlib.Path(__file__).resolve().parent.parent
REPO = ENV.parent / "RV-IM100_RTL" / "project_files"
BM   = ENV.parent / "benchmarks"
BITS = ENV.parent / "bitstream"
LOGS = ENV / "logs" / "finalize"; LOGS.mkdir(parents=True, exist_ok=True)
RPTS = ENV / "logs" / "finalize_reports"; RPTS.mkdir(parents=True, exist_ok=True)
STATE = ENV / "logs" / "finalize_state.json"
MAX_ITERS = 5
SKIP = re.compile(r"\.cache/|\.runs/|\.gen/|\.ip_user_files/|\.sim/")
src = lambda d, pat: [p for p in pathlib.Path(d).rglob(pat) if not SKIP.search(str(p))]

PORT = {
    ("dhrystone","RV64IM"): ("Dhrystone2.1_baremetal_RV64","dhrystone",[]),
    ("coremark","RV64IM"):  ("Coremark_baremetal","coremark",[]),
    ("coremark","RV64I"):   ("Coremark_baremetal","coremark",
        ['ARCH_FLAGS=-march=rv64i_zicsr -mabi=lp64',
         'ASFLAGS=-march=rv64i_zicsr -mabi=lp64 -Wa,-march=rv64i_zicsr',
         'FLAGS_STR="-O2 -march=rv64i_zicsr -mabi=lp64 -fno-common -funroll-loops"']),
    ("dhrystone","RV64I"):  ("Dhrystone2.1_baremetal_RV64","dhrystone",
        ['ARCH_FLAGS=-march=rv64i_zicsr -mabi=lp64',
         'ASFLAGS=-march=rv64i_zicsr -mabi=lp64 -Wa,-march=rv64i_zicsr']),
    ("dhrystone","RV32IM"): ("dhrystone_rv32i_port","dhrystone",[]),
    ("coremark","RV32IM"):  ("coremark_rv32i_port","coremark",[]),
}

def fmt(mhz):
    s = f"{mhz:.6f}".rstrip("0").rstrip(".")
    return s

def build_image(bench, isa, mhz):
    name = f"{bench}_{isa}_{fmt(mhz)}MHz.mem"
    coll = BM / ("dhrystones" if bench == "dhrystone" else "coremarks")
    out = coll / name
    if out.is_file():
        return out, "reused"
    d, target, extra = PORT[(bench, isa)]
    env = {**os.environ, "PATH": "/opt/riscv/bin:" + os.environ["PATH"]}
    subprocess.run(["make","clean"], cwd=BM/d, env=env, capture_output=True)
    r = subprocess.run(["make", f"CPU_FREQ_HZ={int(round(mhz*1e6))}", *extra, "verilog"],
                       cwd=BM/d, env=env, capture_output=True, text=True)
    built = BM/d/f"{target}.mem"
    if r.returncode != 0 or not built.is_file():
        return None, (r.stderr or r.stdout)[-300:]
    coll.mkdir(exist_ok=True); shutil.copy(built, out)
    return out, "built"

def run(job, mhz, image, tag, write_bit):
    proj = pathlib.Path(job["xpr"]).parent
    cur = re.search(r'\$readmemh\("\./([^"]+)"',
                    pathlib.Path(job["imem"]).read_text(errors="replace")).group(1)
    curp = src(proj, cur)
    dest = (curp[0].parent if curp else src(proj,"*.mem")[0].parent) / image.name
    if not dest.is_file():
        shutil.copy(image, dest)
    p = pathlib.Path(job["imem"]); t = p.read_text(errors="replace")
    p.write_text(re.sub(r'(\$readmemh\("\./)[^"]+(")',
                        lambda m: m.group(1)+image.name+m.group(2), t))
    baud = round(mhz*1e6/115200)
    for u in src(proj, "UART_TX.v"):
        s = u.read_text(errors="replace")
        m = re.search(r"(BAUD_DIV\s*=\s*)(\d+)", s)
        if m: u.write_text(s[:m.start(2)]+str(baud)+s[m.end(2):])
    bit = BITS / f"{job['variant']}_{job['bench']}_{round(mhz)}MHz.bit"
    log = LOGS / f"{tag}.log"
    pathlib.Path(job["xpr"]).with_suffix(".lock").unlink(missing_ok=True)
    with log.open("w") as fh:
        subprocess.run(["vivado","-mode","batch","-nojournal","-nolog","-notrace",
            "-source", str(ENV/"scripts"/"bitstream_impl.tcl"),
            "-tclargs", job["xpr"], str(mhz), str(dest), str(bit),
            "reimpl" if not write_bit else "reimpl"], stdout=fh, stderr=subprocess.STDOUT)
    txt = log.read_text(errors="replace")
    m = re.search(r"^CLOCK name=\S+ mhz=(\S+) wns=(\S+) fmax=(\S+)", txt, re.M)
    if not m: return None
    return float(m.group(1)), float(m.group(2)), float(m.group(3)), bit, ("BITSTREAM_OK" in txt)

def main():
    jobs = json.load((ENV/"logs"/"finalize_jobs.json").open())
    state = json.load(STATE.open()) if STATE.is_file() else {}
    for job in jobs:
        key = f"{job['variant']}_{job['bench']}"
        st = state.setdefault(key, {"history": [], "done": False})
        if st["done"]:
            print(f"=== {key}: done already, skipping", flush=True); continue
        target = job["target"]; tried = set()
        print(f"\n=== {key}  ({job['isa']}, {job['why']}, start {target} MHz) ===", flush=True)
        for it in range(1, MAX_ITERS+1):
            if target in tried:
                print(f"  target {target} already tried - stopping", flush=True); break
            tried.add(target)
            img, how = build_image(job["bench"], job["isa"], target)
            if img is None:
                print(f"  [{it}] {target}: IMAGE BUILD FAILED: {how}", flush=True); break
            t0 = time.time()
            r = run(job, target, img, key, write_bit=True)
            if r is None:
                print(f"  [{it}] {target}: IMPLEMENTATION FAILED", flush=True); break
            clk, wns, fmax, bit, gotbit = r
            head_pct = (fmax-clk)/clk*100
            print(f"  [{it}] asked {target:<9} ran {clk:8.3f}  WNS {wns:+.3f}  Fmax {fmax:8.3f}"
                  f"  head {head_pct:+.2f}%  ({how}, {time.time()-t0:.0f}s)", flush=True)
            st["history"].append(dict(target=target, clk=clk, wns=wns, fmax=fmax,
                                      head_pct=round(head_pct,3), image=img.name, bit=bit.name))
            json.dump(state, STATE.open("w"), indent=1)
            if wns < 0:
                nxt = math.floor(fmax)
                target = nxt if nxt != target else target-1
                continue
            if abs(clk - target) > 0.05:
                print(f"       clock landed at {clk:.3f}, image built for {target} "
                      f"- rebuilding image to match", flush=True)
                target = round(clk, 3); continue
            # meeting timing is not enough: a design constrained below its limit
            # reports Fmax it will not actually hold, and tightening reveals more.
            # Keep climbing while more than 1% of the clock is unused.
            if head_pct > 1.0:
                nxt = math.floor(fmax)
                if nxt <= target:
                    print(f"       {head_pct:+.2f}% left but next target {nxt} is not "
                          f"above {target} - stopping", flush=True)
                else:
                    print(f"       {head_pct:+.2f}% still unused - climbing to {nxt}",
                          flush=True)
                    target = nxt; continue
            st["done"] = True
            print(f"       CONVERGED  bitstream {'written' if gotbit else 'MISSING'}: {bit.name}",
                  flush=True)
            break
        json.dump(state, STATE.open("w"), indent=1)
    print("\n=== finalize finished ===", flush=True)
    for k,v in state.items():
        h = v["history"][-1] if v["history"] else None
        if h: print(f"  {k:<34}{'OK ' if v['done'] else 'NOT DONE'}  "
                    f"clk {h['clk']:8.3f}  WNS {h['wns']:+.3f}  head {h['head_pct']:+.2f}%")

if __name__ == "__main__":
    main()
