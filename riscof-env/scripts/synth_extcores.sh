#!/usr/bin/env bash
# Core-only synthesis of the three comparison cores, under the RV-IM100
# methodology.  See comparison_cores/PROVENANCE.md for sources and caveats.
set -uo pipefail
E="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; C="$E/../comparison_cores"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
run() {  # name top clkport sources...
  local nm=$1 top=$2 clk=$3; shift 3
  echo ">>> $nm"
  timeout 3600 vivado -mode batch -nojournal -nolog -notrace -source "$E/scripts/synth_extcore.tcl" \
    -tclargs "$nm" "$top" unused "$E/logs/extcore/$nm" "$clk" "$@" \
    > "$E/logs/extcore/$nm.log" 2>&1
  grep -E '^(EXTCORE_CLOCK|EXTCORE_RESULT|EXTCORE_FAIL)' "$E/logs/extcore/$nm.log" | sed 's/^/    /'
}
run picorv32 picorv32_top clk "$C/picorv32/picorv32.v" "$C/synth/picorv32/picorv32_top.v"
run rvcorep  RVCore       CLK "$C/rvcorep_orig/rvcorep_ver053/proc.v"
run vexriscv VexRiscv     clk "$C/generated/VexRiscv_FullNoMmuNoCache.v"
python3 "$E/scripts/collect_extcores.py"
