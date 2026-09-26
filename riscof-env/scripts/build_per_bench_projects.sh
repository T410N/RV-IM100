#!/usr/bin/env bash
# Give every (variant, benchmark) pair its OWN Vivado project, so a measured
# state can never be overwritten by work on the other benchmark.
#
#   RV32s/SoCs/RV32IM_7SP_Dhry/      dhrystone image, its clock, its BAUD_DIV
#   RV32s/SoCs/RV32IM_7SP_Coremark/  coremark  image, its clock, its BAUD_DIV
#
# Sequential (Vivado implementation is already multi-threaded) and resumable:
# a config whose utilization.rpt exists is skipped.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$ENV_DIR/.."
OUT="$ENV_DIR/logs/final_impl"
mkdir -p "$OUT"
source /tools/Xilinx/2025.2/Vivado/settings64.sh

mapfile -t J < <(python3 -c "
import csv
for r in csv.DictReader(open('$ROOT/evidence/CONFIGURATIONS.csv')):
    print('\t'.join([r['variant'],r['benchmark'],r['xpr'],r['mem_image'],
                     r['clock_mhz'],r['baud_div']]))")
echo "=== ${#J[@]} per-benchmark projects, $(date) ==="
n=0
for line in "${J[@]}"; do
    IFS=$'\t' read -r v b xpr mem clk baud <<<"$line"
    n=$((n+1))
    suf=$([ "$b" = dhrystone ] && echo Dhry || echo Coremark)
    tag="${v}_${suf}"
    [ -s "$OUT/$tag/utilization.rpt" ] && { echo "=== [$n/${#J[@]}] $tag done"; continue; }

    srcdir="$ROOT/RV-IM100_RTL/project_files/$(dirname "$xpr")"
    fam=$(echo "$xpr" | cut -d/ -f1)
    dstdir="$ROOT/RV-IM100_RTL/project_files/$fam/SoCs/$tag"
    base=$(basename "$xpr")
    echo ">>> [$n/${#J[@]}] $tag  ${clk}MHz  $mem  $(date +%H:%M:%S)"

    if [ ! -f "$dstdir/$base" ]; then
        rm -rf "$dstdir"; mkdir -p "$dstdir"
        for part in "$base" "${base%.xpr}.srcs" "${base%.xpr}.gen"; do
            [ -e "$srcdir/$part" ] && cp -a "$srcdir/$part" "$dstdir"/
        done
    fi
    # point this project at its own benchmark, permanently
    python3 - "$dstdir" "$mem" "$baud" <<'PY'
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
    mempath=$(find "$dstdir" -name "$mem" 2>/dev/null | grep -vE '\.cache/|\.runs/|\.gen/' | head -1)
    [ -z "$mempath" ] && mempath=$(find "$ROOT/benchmarks" -name "$mem" 2>/dev/null | head -1)
    [ -z "$mempath" ] && { echo "!! $tag: image $mem not found"; continue; }

    rm -f "$dstdir"/*.lock
    timeout 7200 vivado -mode batch -nojournal -nolog -notrace \
        -source "$ENV_DIR/scripts/reimage_impl.tcl" \
        -tclargs "$dstdir/$base" "$clk" "$mempath" "$OUT/$tag" \
        > "$OUT/$tag.log" 2>&1
    if grep -q REIMAGE_OK "$OUT/$tag.log"; then
        lut=$(grep -m1 -oP '\|\s+Slice LUTs\*?\s+\|\s+\K[0-9]+' "$OUT/$tag/utilization.rpt" 2>/dev/null)
        w=$(grep -m1 '^CLOCK' "$OUT/$tag.log" | sed -n 's/.*wns=\([^ ]*\).*/\1/p')
        echo "<<< [$n] $tag  LUT=$lut  WNS=$w  $(date +%H:%M:%S)"
    else
        echo "!! [$n] $tag FAILED"
    fi
done
echo "=== finished $(date) ==="
