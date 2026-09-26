#!/usr/bin/env bash
# Remaining SAIF configs: point each project at the other benchmark image,
# re-implement (the netlist must carry the right ROM contents), then measure.
# Resumable at both stages.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
mapfile -t J < <(python3 -c "
import json
for r in json.load(open('$ENV_DIR/logs/saif_todo.json')):
    print('\t'.join([r['variant'],r['bench'],r['xpr'],r['top'],
                     str(r['mhz']),str(r['baud']),r['mempath']]))")
echo "=== ${#J[@]} configs, $(date) ==="
n=0
for line in "${J[@]}"; do
    IFS=$'\t' read -r v b xpr top mhz baud mem <<<"$line"
    n=$((n+1)); W="$ENV_DIR/saif/${v}_${b}"
    if [ -s "$ENV_DIR/saif/results/${v}_${b}.txt" ]; then echo "=== [$n] $v/$b done"; continue; fi
    echo ">>> [$n/${#J[@]}] $v/$b @${mhz}MHz $(basename "$mem")  $(date +%H:%M:%S)"
    if [ ! -s "$W/netlist.v" ]; then
        proj="$(dirname "$xpr")"
        python3 - "$proj" "$(basename "$mem")" "$baud" <<'PY'
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
        rm -f "$(dirname "$xpr")/$(basename "$xpr" .xpr).lock"
        timeout 7200 vivado -mode batch -nojournal -nolog -notrace \
            -source "$ENV_DIR/scripts/reimage_impl.tcl" \
            -tclargs "$xpr" "$mhz" "$mem" "$ENV_DIR/logs/saif_reimpl/${v}_${b}" \
            > "$ENV_DIR/saif/${v}_${b}_impl.log" 2>&1
        grep -q REIMAGE_OK "$ENV_DIR/saif/${v}_${b}_impl.log" \
            || { echo "!! [$n] $v/$b re-implementation failed"; continue; }
    fi
    "$ENV_DIR/scripts/saif_one.sh" "$v" "$b" "$xpr" "$top"
done
echo "=== finished $(date) ==="
