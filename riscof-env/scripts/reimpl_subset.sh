#!/usr/bin/env bash
# Re-implement only the named configs, from CONFIGURATIONS_perbench.csv.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; ROOT="$ENV_DIR/.."
OUT="$ENV_DIR/logs/final_impl"; mkdir -p "$OUT"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
for tag in "$@"; do
  v="${tag%_*}"; b="${tag##*_}"
  read -r xpr mem clk baud < <(python3 -c "
import csv
for r in csv.DictReader(open('$ROOT/evidence/CONFIGURATIONS_perbench.csv')):
    if r['variant']=='$v' and r['benchmark']=='$b':
        print(r['xpr'],r['mem_image'],r['clock_mhz'],r['baud_div'])")
  [ -z "${xpr:-}" ] && { echo "!! $tag: no config row"; continue; }
  proj="$ROOT/RV-IM100_RTL/project_files/$(dirname "$xpr")"
  mempath=$(find "$proj" -name "$mem" 2>/dev/null | grep -vE '\.cache/|\.runs/|\.gen/' | head -1)
  [ -z "$mempath" ] && mempath=$(find "$ROOT/benchmarks" -name "$mem" 2>/dev/null | head -1)
  [ -z "$mempath" ] && { echo "!! $tag: image $mem not found"; continue; }
  echo ">>> $tag  ${clk}MHz  $mem  $(date +%H:%M:%S)"
  python3 - "$proj" "$mem" "$baud" <<'PY'
import re,sys,pathlib
proj,image,baud=sys.argv[1],sys.argv[2],int(sys.argv[3])
skip=re.compile(r"\.cache/|\.runs/|\.gen/|\.ip_user_files/|\.sim/")
src=lambda p:[x for x in pathlib.Path(proj).rglob(p) if not skip.search(str(x))]
for f in src("Instruction_Memory.v"):
    t=f.read_text(errors="replace")
    f.write_text(re.sub(r'(\$readmemh\("\./)[^"]+(")',lambda m:m.group(1)+image+m.group(2),t))
for u in src("UART_TX.v"):
    s=u.read_text(errors="replace"); m=re.search(r"(BAUD_DIV\s*=\s*)(\d+)",s)
    if m: u.write_text(s[:m.start(2)]+str(baud)+s[m.end(2):])
PY
  rm -f "$proj"/*.lock
  timeout 7200 vivado -mode batch -nojournal -nolog -notrace \
      -source "$ENV_DIR/scripts/reimage_impl.tcl" \
      -tclargs "$ROOT/RV-IM100_RTL/project_files/$xpr" "$clk" "$mempath" "$OUT/$tag" > "$OUT/$tag.log" 2>&1
  if grep -q REIMAGE_OK "$OUT/$tag.log"; then
    lut=$(grep -m1 -oP '\|\s+Slice LUTs\*?\s+\|\s+\K[0-9]+' "$OUT/$tag/utilization.rpt" 2>/dev/null)
    ck=$(grep '^CLOCK ' "$OUT/$tag.log" | grep -v 'wns=none' | head -1 | sed -n 's/.*wns=\([^ ]*\).*/\1/p')
    echo "<<< $tag  LUT=$lut  WNS=$ck"
  else
    echo "!! $tag FAILED"; tail -3 "$OUT/$tag.log" | sed 's/^/    /'
  fi
done
echo "=== subset finished $(date) ==="
