#!/usr/bin/env bash
# Regenerate bitstreams for configurations whose program or clock changed, so
# the FPGA is verified against what the workbook now reports.
#
# reuse mode: each project already holds the correct image and a routed design
# from the current measurement pass, so only write_bitstream is run.  The clock
# in the project is verified against the config before writing, and a mismatch
# is refused rather than silently producing a bitstream for the wrong clock.
set -uo pipefail
E="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; R="$E/.."
OUT="$R/bitstream/Updated"; mkdir -p "$OUT"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
for tag in "$@"; do
  v="${tag%_*}"; b="${tag##*_}"
  read -r xpr mem clk < <(python3 -c "
import csv
for r in csv.DictReader(open('$R/evidence/CONFIGURATIONS_perbench.csv')):
    if r['variant']=='$v' and r['benchmark']=='$b': print(r['xpr'],r['mem_image'],r['clock_mhz'])")
  [ -z "${xpr:-}" ] && { echo "!! $tag: no config row"; continue; }
  # the clock the project's routed design was actually built at
  built=$(grep '^CLOCK ' "$E/logs/final_impl/$tag.log" 2>/dev/null | grep -v 'wns=none' | head -1 \
          | sed -n 's/.*mhz=\([^ ]*\).*/\1/p')
  ok=$(python3 -c "print('yes' if abs(float('${built:-0}')-float('$clk'))<0.01 else 'no')")
  if [ "$ok" != yes ]; then
    echo "!! $tag: project built at ${built:-?} MHz but config says $clk -- refusing"; continue
  fi
  name=$(python3 -c "
f=float('$clk'); s=f'{f:.6f}'.rstrip('0').rstrip('.')
print(f'${v}_${b}_{s}MHz.bit')")
  proj="$R/RV-IM100_RTL/project_files/$(dirname "$xpr")"
  mempath=$(find "$proj" -name "$mem" 2>/dev/null | grep -vE '\.runs/|\.cache/|\.gen/' | head -1)
  [ -z "$mempath" ] && mempath=$(find "$R/benchmarks" -name "$mem" 2>/dev/null | head -1)
  echo ">>> $tag  ${clk}MHz  $mem  $(date +%H:%M:%S)"
  rm -f "$proj"/*.lock
  timeout 7200 vivado -mode batch -nojournal -nolog -notrace -source "$E/scripts/bitstream_impl.tcl" \
    -tclargs "$R/RV-IM100_RTL/project_files/$xpr" "$clk" "$mempath" "$OUT/$name" reuse > "$E/logs/regen_$tag.log" 2>&1
  if [ -s "$OUT/$name" ]; then
    echo "<<< $tag  -> $name  ($(du -h "$OUT/$name" | cut -f1))"
  else
    echo "!! $tag FAILED"; tail -4 "$E/logs/regen_$tag.log" | sed 's/^/    /'
  fi
done
echo "=== bitstream regeneration finished $(date) ==="
