#!/usr/bin/env bash
# T4: re-cost every captured SAIF on the FINAL implementation of its build, and record
# how much of the design the activity annotated.  One authoritative table results
# (collect with saif_recost_collect.py).  Read-only on the projects: open_run + report.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; ROOT="$ENV_DIR/.."
source /tools/Xilinx/2025.2/Vivado/settings64.sh
OUT="$ENV_DIR/saif_recost"; mkdir -p "$OUT"
cat > "$OUT/recost.tcl" <<'TCL'
set xpr  [lindex $argv 0]
set saif [lindex $argv 1]
set out  [lindex $argv 2]
open_project -quiet $xpr
open_run [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]
report_power -file $out/power_vectorless.rpt
read_saif -strip_path tb_saif/dut $saif
report_power -file $out/power_saif.rpt
report_power -hier all -file $out/power_saif_hier.rpt
puts "RECOST_OK"
close_project
TCL
job() {
  tag="$1"; v="${tag%_*}"; b="${tag##*_}"
  xpr=$(python3 -c "
import csv
for r in csv.DictReader(open('$ROOT/evidence/CONFIGURATIONS_perbench.csv')):
    if r['variant']=='$v' and r['benchmark']=='$b': print(r['xpr'])")
  d="$OUT/$tag"; mkdir -p "$d"
  [ -s "$d/power_saif.rpt" ] && { echo "skip $tag"; return; }
  rm -f "$ROOT/RV-IM100_RTL/project_files/$(dirname "$xpr")"/*.lock
  timeout 3600 vivado -mode batch -nojournal -nolog -notrace -source "$OUT/recost.tcl" \
     -tclargs "$ROOT/RV-IM100_RTL/project_files/$xpr" "$ENV_DIR/saif/$tag/kernel.saif" "$d" > "$d/vivado.log" 2>&1
  echo "$tag $(grep -m1 'Design nets matched' $d/vivado.log) $(grep -c RECOST_OK $d/vivado.log)"
}
export -f job; export OUT ROOT ENV_DIR
ls "$ENV_DIR/saif" | grep -E '_(coremark|dhrystone)$' | xargs -P 2 -I{} bash -c 'job {}'
echo "=== recost finished $(date)"
