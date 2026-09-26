#!/usr/bin/env bash
# T8: simulators with cause-based stall accounting (testbench only).
#
# Copies build/socs_<v>/rtl to build_t8/socs_<v>/rtl and adds to sim_top.v a monitor
# that assigns EVERY cycle to exactly one bucket, by a fixed priority ladder:
#
#   retired            an instruction (not a NOP) leaves WB this cycle
#   div_busy           divider occupied
#   mul_busy           multiplier occupied
#   load_use           load-use interlock          (variants that have the signal)
#   exec_use           EXR operand stall           (8-stage only: exr_data_stall)
#   csr_not_ready      CSR read latency
#   mispredict_flush   branch resolved against the prediction
#   taken_refill       predicted-taken redirect (front-end refill)
#   jump_redirect      JAL/JALR redirect
#   stall_other        any remaining stage/pc stall
#   frontend_empty     no retire, no stall asserted (drain/refill bubbles)
#
# The ladder ends in an unconditional else, so
#     sum(buckets) + retired == cycles
# exactly, which the runner checks.  Signals absent from a variant are compiled out,
# so each core is described by its own signals.  Nothing in the core is modified.
#
# usage: build_t8_sims.sh <variant> [...]
set -euo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for v in "$@"; do
  src="$ENV_DIR/build/socs_$v/rtl"; out="$ENV_DIR/build_t8/socs_$v"
  rm -rf "$out"; mkdir -p "$out"; cp -r "$src" "$out/rtl"
  python3 - "$out/rtl" <<'PY'
import sys, re, glob, os
rtl = sys.argv[1]
top = [f for f in glob.glob(rtl + '/RV*.v') if 'sim_top' not in f][0]
src = re.sub(r'//.*', '', open(top).read())
def has(sig):                       # declared, or an implicit net driven by a port
    return re.search(r'\b%s\b' % sig, src) is not None
core = lambda s: 'core.%s' % s
# optional signals, in ladder order after mul/div
names = ['div_busy', 'mul_busy']
cond = {n: (core(n) if has(n) else "1'b0") for n in names}      # absent on the I-only cores
# On the 8-stage, load_use_hazard == exr_data_stall == ex_data_stall || load_br_use_hazard,
# i.e. the reported "load-use" folds in execution-use.  Split them at the source.
eight = has('exr_data_stall')
hz = rtl + '/Hazard_Unit.v'
if eight:
    h = open(hz).read()
    loadw = 'load_br_use_hazard' if 'load_br_use_hazard' in h else 'load_ex2_use_hazard'
    for w in ('ex_data_stall', loadw):
        h = re.sub(r'wire %s =' % w, 'wire %s /*verilator public*/ =' % w, h, count=1)
    open(hz, 'w').write(h)
names += ['load_use', 'exec_use', 'csr_not_ready']
cond['load_use'] = ('core.hazard_unit.' + loadw if eight else
                    (core('load_use_hazard') if has('load_use_hazard') else "1'b0"))
cond['exec_use'] = 'core.hazard_unit.ex_data_stall' if eight else "1'b0"
cond['csr_not_ready'] = ('!' + core('csr_ready')) if has('csr_ready') else "1'b0"
for label, expr in (('mispredict_flush', core('branch_prediction_miss')),
                    ('taken_refill', core('branch_estimation')),
                    ('jump_redirect', core('jump')),
                    ('stall_other', core('pc_stall') + ' || |prof_flags[7:1]')):
    names.append(label); cond[label] = expr
names.append('frontend_empty')
decl = '\n'.join('    reg [63:0] t8_%s;' % n for n in names + ['retired_cycles'])
init = '\n'.join('        t8_%s = 64\'d0;' % n for n in names + ['retired_cycles'])
ladder = '            if (retire_valid && retire_insn != 32\'h00000013) t8_retired_cycles <= t8_retired_cycles + 64\'d1;\n'
for i, n in enumerate(names[:-1]):
    ladder += '            else if (%s) t8_%s <= t8_%s + 64\'d1;\n' % (cond[n], n, n)
ladder += '            else t8_frontend_empty <= t8_frontend_empty + 64\'d1;\n'
mon = """
    // ---- T8 cause-based stall accounting (testbench only) -------------------
%s
    initial begin
%s
    end
    always @(posedge clk) begin
        if (!reset) begin
%s        end
    end
""" % (decl, init, ladder)
s = open(rtl + '/sim_top.v').read()
s = s.replace('    task dump_profile;', mon + '\n    task dump_profile;', 1)
dump = ''.join('                    $fwrite(fd, "t8_%s %%0d\\n", t8_%s);\n' % (n, n) for n in names + ['retired_cycles'])
s = s.replace('$fwrite(fd, "cycles %0d\\n", n_cycles_run);',
              '$fwrite(fd, "cycles %0d\\n", n_cycles_run);\n' + dump.lstrip(), 1)
open(rtl + '/sim_top.v', 'w').write(s)
print('  buckets:', ' '.join(n for n in names if cond.get(n) != "1'b0"))
PY
  rtl="$out/rtl"; incs=(-I"$rtl"); for sub in headers modules modules/headers; do [ -d "$rtl/$sub" ] && incs+=(-I"$rtl/$sub"); done
  mapfile -t files < <(sed "s#^#$rtl/#" "$rtl/filelist.txt")
  verilator --cc --exe --build -j 4 --top-module sim_top --Mdir "$out/obj_dir" -O3 -CFLAGS "-O2 -std=c++17" \
    -Wno-fatal -Wno-WIDTHEXPAND -Wno-WIDTHTRUNC -Wno-UNOPTFLAT -Wno-CASEINCOMPLETE -Wno-LATCH -Wno-MULTIDRIVEN \
    "${incs[@]}" "${files[@]}" "$ENV_DIR/sim/tb_sim_top.cpp" -o "$out/Vsim_top" > "$out/verilate.log" 2>&1 \
    && echo "built $v" || { echo "FAILED $v"; tail -5 "$out/verilate.log"; }
done
