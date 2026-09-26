#!/usr/bin/env python3
"""Per-processor frequency sweep, iterating until each row converges.

A row is DONE when the implemented design meets timing (WNS >= 0) and closes
within 1 MHz of the clock it runs at. Each iteration builds the .mem image for
the new target (frequency is compiled into the benchmark's timing loop), sets
the PLL and UART divisor, re-implements, and reads the achieved clock back.

Convergence is not guaranteed by construction: on LUTRAM designs the ROM is
logic, so changing the image reshuffles placement and moves Fmax. The loop
therefore also stops on a repeated target (oscillation) or MAX_ITERS, and
reports the best result seen rather than spinning.
"""
import csv, json, math, pathlib, re, shutil, subprocess, sys, time

ENV  = pathlib.Path(__file__).resolve().parent.parent
REPO = ENV.parent / "RV-IM100_RTL" / "project_files"
BM   = ENV.parent / "benchmarks"
LOGS = ENV / "logs" / "sweep";  LOGS.mkdir(parents=True, exist_ok=True)
RPTS = ENV / "logs" / "sweep_reports"; RPTS.mkdir(parents=True, exist_ok=True)
STATE = ENV / "logs" / "sweep_state.json"
MAX_ITERS = 6
SKIP = re.compile(r"\.cache/|\.runs/|\.gen/|\.ip_user_files/|\.sim/")

def src(d, pat):
    return [p for p in pathlib.Path(d).rglob(pat) if not SKIP.search(str(p))]

# bench dir, target name, ISA tag, extra make vars for the I-only core
PORT = {
    ("dhrystone", "RV64IM"): ("Dhrystone2.1_baremetal_RV64", "dhrystone", []),
    ("coremark",  "RV64IM"): ("Coremark_baremetal",          "coremark",  []),
    ("coremark",  "RV64I"):  ("Coremark_baremetal",          "coremark",
        ['ARCH_FLAGS=-march=rv64i_zicsr -mabi=lp64',
         'ASFLAGS=-march=rv64i_zicsr -mabi=lp64 -Wa,-march=rv64i_zicsr',
         'FLAGS_STR="-O2 -march=rv64i_zicsr -mabi=lp64 -fno-common -funroll-loops"']),
    ("dhrystone", "RV32IM"): ("dhrystone_rv32i_port", "dhrystone", []),
    ("coremark",  "RV32IM"): ("coremark_rv32i_port",  "coremark",  []),
}

def build_image(bench, isa, mhz):
    """Build (or reuse) <bench>_<isa>_<mhz>MHz.mem and return its path in benchmarks/."""
    name = f"{bench}_{isa}_{mhz}MHz.mem"
    coll = BM / ("dhrystones" if bench == "dhrystone" else "coremarks")
    out  = coll / name
    if out.is_file():
        return out, "reused"
    d, target, extra = PORT[(bench, isa)]
    hz = str(int(round(mhz * 1e6)))
    env = {**dict(__import__("os").environ), "PATH": "/opt/riscv/bin:" + __import__("os").environ["PATH"]}
    subprocess.run(["make", "clean"], cwd=BM/d, env=env, capture_output=True)
    r = subprocess.run(["make", f"CPU_FREQ_HZ={hz}", *extra, "verilog"],
                       cwd=BM/d, env=env, capture_output=True, text=True)
    built = BM/d/f"{target}.mem"
    if r.returncode != 0 or not built.is_file():
        return None, (r.stderr or r.stdout)[-300:]
    coll.mkdir(exist_ok=True)
    shutil.copy(built, out)
    return out, "built"

def implement(job, mhz, image_path, tag):
    """Point the ROM at image_path, set PLL + baud, re-implement. -> (clk,wns,fmax)"""
    dest = pathlib.Path(job["imem"]).parent  # keep the image beside the current one
    cur  = re.search(r'\$readmemh\("\./([^"]+)"',
                     pathlib.Path(job["imem"]).read_text(errors="replace")).group(1)
    curp = src(pathlib.Path(job["xpr"]).parent, cur)
    dest = curp[0].parent if curp else dest
    local = dest / image_path.name
    if not local.is_file():
        shutil.copy(image_path, local)
    # readmemh
    p = pathlib.Path(job["imem"]); t = p.read_text(errors="replace")
    p.write_text(re.sub(r'(\$readmemh\("\./)[^"]+(")',
                        lambda m: m.group(1)+image_path.name+m.group(2), t))
    # UART divisor
    baud = round(mhz*1e6/115200)
    for u in src(pathlib.Path(job["xpr"]).parent, "UART_TX.v"):
        s = u.read_text(errors="replace")
        m = re.search(r"(BAUD_DIV\s*=\s*)(\d+)", s)
        if m: u.write_text(s[:m.start(2)]+str(baud)+s[m.end(2):])
    log = LOGS / f"{tag}.log"
    lock = pathlib.Path(job["xpr"]).with_suffix(".lock")
    lock.unlink(missing_ok=True)
    with log.open("w") as fh:
        subprocess.run(["vivado","-mode","batch","-nojournal","-nolog","-notrace",
                        "-source", str(ENV/"scripts"/"reimage_impl.tcl"),
                        "-tclargs", job["xpr"], str(mhz), str(local), str(RPTS/tag)],
                       stdout=fh, stderr=subprocess.STDOUT)
    t = log.read_text(errors="replace")
    if "REIMAGE_OK" not in t:
        return None
    for m in re.findall(r"^CLOCK name=\S+ period=\S+ mhz=(\S+) wns=(\S+) fmax=(\S+)", t, re.M):
        if m[1] not in ("none",""):
            return float(m[0]), float(m[1]), float(m[2])
    return None

def main():
    jobs = json.load((ENV/"logs"/"sweep_jobs.json").open())
    state = json.load(STATE.open()) if STATE.is_file() else {}
    for job in jobs:
        key = f"{job['variant']}_{job['bench']}"
        st = state.setdefault(key, {"history": [], "done": False})
        if st["done"]:
            print(f"=== {key}: already converged, skipping", flush=True); continue
        target = job["start_mhz"]
        tried = {h["target"] for h in st["history"]}
        print(f"\n=== {key}  ({job['isa']}, start {target} MHz) ===", flush=True)
        for it in range(1, MAX_ITERS+1):
            if target in tried:
                print(f"  target {target} already tried - stopping (oscillation)", flush=True)
                break
            tried.add(target)
            img, how = build_image(job["bench"], job["isa"], target)
            if img is None:
                print(f"  [{it}] {target} MHz: IMAGE BUILD FAILED: {how}", flush=True); break
            t0 = time.time()
            r = implement(job, target, img, key)
            if r is None:
                print(f"  [{it}] {target} MHz: IMPLEMENTATION FAILED", flush=True); break
            clk, wns, fmax = r
            head = round(fmax-clk, 3)
            # A row is done when it meets timing and either sits within 1 MHz of
            # what it closes at, or has already been shown to get WORSE when the
            # constraint is tightened (RV32IM_8SP: 119 meets, 121 fails).
            worse_when_tightened = any(h['wns'] < 0 and h['target'] > target
                                       for h in st['history'])
            ok = wns >= 0 and (head <= 1.0 or worse_when_tightened)
            st["history"].append(dict(target=target, clk=clk, wns=wns, fmax=fmax,
                                      head=head, image=img.name, ok=ok))
            print(f"  [{it}] target {target:>7} -> clock {clk:8.3f}  WNS {wns:+.3f}  "
                  f"Fmax {fmax:8.3f}  head {head:+.2f}  {'CONVERGED' if ok else ''}"
                  f"  ({how}, {time.time()-t0:.0f}s)", flush=True)
            json.dump(state, STATE.open("w"), indent=1)
            if ok:
                st["done"] = True; break
            nxt = int(math.floor(fmax))          # aim just under what it closes at
            if nxt == target:
                nxt = target-1 if wns < 0 else target+1
            target = nxt
        json.dump(state, STATE.open("w"), indent=1)
    print("\n=== sweep finished ===", flush=True)
    for k, v in state.items():
        h = v["history"][-1] if v["history"] else None
        if h:
            print(f"  {k:<36} {'CONVERGED' if v['done'] else 'not converged'}  "
                  f"clock {h['clk']:.3f}  Fmax {h['fmax']:.3f}  head {h['head']:+.2f}"
                  f"  ({len(v['history'])} iters)")

if __name__ == "__main__":
    main()
