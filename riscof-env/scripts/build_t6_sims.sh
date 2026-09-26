#!/usr/bin/env bash
# T6: separate simulators with a testbench-only trigger monitor.
# Copies build/socs_<v>/rtl to build_t6/socs_<v>/rtl, adds to sim_top.v (the
# testbench, never synthesised) a counter of cycles where the IF/IO register
# suppresses the predicted-taken squash because an M-extension instruction is in
# ID:  clk_enable & branch_estimation & !IF_IO_stall & is_m_extend
# The count is appended to the +PROF file as "t6_trig <n>".  Core RTL untouched.
set -euo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for v in "$@"; do
  src="$ENV_DIR/build/socs_$v/rtl"; out="$ENV_DIR/build_t6/socs_$v"
  rm -rf "$out"; mkdir -p "$out"; cp -r "$src" "$out/rtl"
  python3 - "$out/rtl/sim_top.v" <<'PY'
import sys,re
p=sys.argv[1]; s=open(p).read()
mon='''
    // ---- T6 trigger monitor (testbench only) --------------------------------
    reg [63:0] t6_trig;
    initial t6_trig = 64'd0;
    always @(posedge clk) begin
        if (!reset && core.if_io_register.clk_enable && core.if_io_register.branch_estimation
            && !core.if_io_register.IF_IO_stall && core.if_io_register.is_m_extend)
            t6_trig <= t6_trig + 64'd1;
    end
'''
s=s.replace('    task dump_profile;', mon+'\n    task dump_profile;',1)
s=s.replace('$fwrite(fd, "cycles %0d\\n", n_cycles_run);','$fwrite(fd, "cycles %0d\\n", n_cycles_run);\n                    $fwrite(fd, "t6_trig %0d\\n", t6_trig);',1)
assert 't6_trig %0d' in s and 'core.if_io_register.is_m_extend' in s
open(p,'w').write(s)
PY
  rtl="$out/rtl"; incs=(-I"$rtl"); for sub in headers modules modules/headers; do [ -d "$rtl/$sub" ] && incs+=(-I"$rtl/$sub"); done
  mapfile -t files < <(sed "s#^#$rtl/#" "$rtl/filelist.txt")
  verilator --cc --exe --build -j 4 --top-module sim_top --Mdir "$out/obj_dir" -O3 -CFLAGS "-O2 -std=c++17" \
    -Wno-fatal -Wno-WIDTHEXPAND -Wno-WIDTHTRUNC -Wno-UNOPTFLAT -Wno-CASEINCOMPLETE -Wno-LATCH -Wno-MULTIDRIVEN \
    "${incs[@]}" "${files[@]}" "$ENV_DIR/sim/tb_sim_top.cpp" -o "$out/Vsim_top" > "$out/verilate.log" 2>&1 \
    && echo "built $v" || { echo "FAILED $v"; tail -5 "$out/verilate.log"; }
done
