#!/usr/bin/env bash
# Re-run capture + power for a saif_v2 build whose netlist/snapshot already exist.
set -uo pipefail
source /tools/Xilinx/2025.2/Vivado/settings64.sh
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; ROOT="$ENV_DIR/.."
tag="$1"; xpr="$ROOT/RV-IM100_RTL/project_files/$2"; W="$ENV_DIR/saif_v2/$tag"; cd "$W"
xsim tb_ns -tclbatch cap.tcl > xsim.log 2>&1
[ -s kernel.saif ] || { echo "!! $tag capture failed"; exit 1; }
rm -f "$(dirname "$xpr")"/*.lock
vivado -mode batch -nojournal -nolog -notrace -source power.tcl -tclargs "$xpr" "$W/kernel.saif" > power.log 2>&1
echo "=== $tag $(grep -m1 'Design nets matched' power.log) $(grep -m1 'Total On-Chip' power_saif.rpt)"
