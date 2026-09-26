#!/usr/bin/env bash
# Re-cost the captured SAIF against the clean implementations, for the configs
# whose netlist changed.  The SAIF itself is reusable: it records toggle counts
# from executing the program, which placement does not alter.  What changes is
# the routing capacitance those toggles drive, which report_power recomputes.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; ROOT="$ENV_DIR/.."
source /tools/Xilinx/2025.2/Vivado/settings64.sh
OUT="$ENV_DIR/logs/repower"; mkdir -p "$OUT"
for tag in "$@"; do
  v="${tag%_*}"; b="${tag##*_}"
  xpr=$(python3 -c "
import csv
for r in csv.DictReader(open('$ROOT/evidence/CONFIGURATIONS_perbench.csv')):
    if r['variant']=='$v' and r['benchmark']=='$b': print(r['xpr'])")
  [ -z "$xpr" ] && { echo "!! $tag: no config row"; continue; }
  echo ">>> $tag  $(date +%H:%M:%S)"
  rm -f "$ROOT/RV-IM100_RTL/project_files/$(dirname "$xpr")"/*.lock
  timeout 3600 vivado -mode batch -nojournal -nolog -notrace \
    -source "$ENV_DIR/scripts/saif_power.tcl" \
    -tclargs "$ROOT/RV-IM100_RTL/project_files/$xpr" "$ENV_DIR/saif/$tag/kernel.saif" "$OUT/$tag.rpt" \
    > "$OUT/$tag.log" 2>&1
  if grep -q SAIF_POWER_OK "$OUT/$tag.log"; then
    echo "<<< $tag  $(grep -E '^(VECTORLESS|SAIF_BASED)' "$OUT/$tag.log" | tr '\n' ' ')"
    grep -E '^CONF' "$OUT/$tag.log" | head -2 | sed 's/^/    /'
  else
    echo "!! $tag FAILED"; tail -3 "$OUT/$tag.log" | sed 's/^/    /'
  fi
done
echo "=== repower finished $(date) ==="
