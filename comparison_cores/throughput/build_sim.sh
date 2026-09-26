#!/usr/bin/env bash
# Build one Verilator simulator per comparison-core configuration.
set -uo pipefail
T="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; C="$T/.."
export PATH=$HOME/tools/verilator/bin:$PATH
V="verilator --binary --timing -O3 --top-module tb -Wno-fatal -Wno-lint -Wno-style -Wno-TIMESCALEMOD --x-assign 0 --x-initial 0"
build() {  # name  sources/flags...
  local n=$1; shift
  rm -rf "$T/build/sim_$n"
  if $V --Mdir "$T/build/sim_$n" -o sim "$@" "$T/tb/tbmem.v" > "$T/build/sim_$n.log" 2>&1; then
    echo "  built $n"
  else
    echo "  FAILED $n (see build/sim_$n.log)"; tail -15 "$T/build/sim_$n.log" | sed 's/^/    /'
  fi
}
build picorv32_la   +define+LA "$T/tb/tb_picorv32.v" "$C/picorv32/picorv32.v"
build picorv32_nola            "$T/tb/tb_picorv32.v" "$C/picorv32/picorv32.v"
build vexriscv                 "$T/tb/tb_vexriscv.v" "$C/generated/VexRiscv_FullNoMmuNoCache_NoDebug.v"
build rvcorep  +incdir+"$C/rvcorep_orig/rvcorep_ver053" "$T/tb/tb_rvcorep.v" "$C/rvcorep_orig/rvcorep_ver053/proc.v"
