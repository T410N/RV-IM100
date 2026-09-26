#!/usr/bin/env bash
# Re-implement every (variant, benchmark) configuration and capture utilisation,
# timing and power from THAT implementation, so each workbook row describes one
# design rather than a composite of several.
#
# Sequential: Vivado implementation is already multi-threaded.
# Resumable: a config whose utilization.rpt exists is skipped.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$ENV_DIR/.."
OUT="$ENV_DIR/logs/final_impl"
mkdir -p "$OUT"
source /tools/Xilinx/2025.2/Vivado/settings64.sh

mapfile -t J < <(python3 -c "
import csv
for r in csv.DictReader(open('$ROOT/evidence/CONFIGURATIONS_perbench.csv')):
    print('\t'.join([r['variant'],r['benchmark'],r['xpr'],r['mem_image'],
                     r['clock_mhz'],r['baud_div']]))")
echo "=== ${#J[@]} configurations, $(date) ==="
n=0
for line in "${J[@]}"; do
    IFS=$'\t' read -r v b xpr mem clk baud <<<"$line"
    n=$((n+1)); tag="${v}_${b}"
    if [ -s "$OUT/$tag/utilization.rpt" ]; then echo "=== [$n/${#J[@]}] $tag done"; continue; fi
    proj="$ROOT/RV-IM100_RTL/project_files/$(dirname "$xpr")"
    echo ">>> [$n/${#J[@]}] $tag  ${clk}MHz  $mem  $(date +%H:%M:%S)"
    # locate the image: it may sit in the project or in the shared benchmarks library
    mempath=$(find "$proj" -name "$mem" 2>/dev/null | grep -vE '\.cache/|\.runs/|\.gen/' | head -1)
    [ -z "$mempath" ] && mempath=$(find "$ROOT/benchmarks" -name "$mem" 2>/dev/null | head -1)
    [ -z "$mempath" ] && { echo "!! $tag: image $mem not found"; continue; }
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
        -tclargs "$ROOT/RV-IM100_RTL/project_files/$xpr" "$clk" "$mempath" "$OUT/$tag" \
        > "$OUT/$tag.log" 2>&1
    if grep -q REIMAGE_OK "$OUT/$tag.log"; then
        lut=$(grep -m1 -oP '\|\s+Slice LUTs\*?\s+\|\s+\K[0-9]+' "$OUT/$tag/utilization.rpt" 2>/dev/null)
        ck=$(grep -m1 '^CLOCK' "$OUT/$tag.log" | sed -n 's/.*wns=\([^ ]*\).*/\1/p')
        echo "<<< [$n] $tag  LUT=$lut  WNS=$ck"
    else
        echo "!! [$n] $tag FAILED"
    fi
done
echo "=== finished $(date) ==="
