#!/usr/bin/env bash
# Two-phase remainder:
#   A. re-implementations, SEQUENTIAL -- Vivado is already multi-threaded and
#      saturates all cores, so running these in parallel is slower, not faster.
#   B. simulations, PARALLEL -- xsim's kernel is single-threaded (one core each),
#      so throughput comes from running several configs at once.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
PAR="${PAR:-4}"          # leave cores free for the user's own Vivado work

echo "=== PHASE A: re-implementations (sequential) $(date) ==="
mapfile -t A < <(python3 -c "
import json
for r in json.load(open('$ENV_DIR/logs/saif_phaseA.json')):
    print('\t'.join([r['variant'],r['bench'],r['xpr'],r['top'],str(r['mhz']),str(r['baud']),r['mempath']]))")
n=0
for line in "${A[@]}"; do
    IFS=$'\t' read -r v b xpr top mhz baud mem <<<"$line"
    n=$((n+1)); W="$ENV_DIR/saif/${v}_${b}"
    [ -s "$W/netlist.v" ] && { echo "=== [A$n] $v/$b netlist exists"; continue; }
    echo ">>> [A$n/${#A[@]}] $v/$b @${mhz}MHz $(basename "$mem")  $(date +%H:%M:%S)"
    python3 - "$(dirname "$xpr")" "$(basename "$mem")" "$baud" <<'PY'
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
    if grep -q REIMAGE_OK "$ENV_DIR/saif/${v}_${b}_impl.log"; then
        mkdir -p "$W"
        vivado -mode batch -nojournal -nolog -notrace -source "$ENV_DIR/scripts/saif_netlist.tcl" \
               -tclargs "$xpr" "$W" > "$W/netlist.log" 2>&1
        echo "<<< [A$n] $v/$b netlist $( [ -s "$W/netlist.v" ] && echo ok || echo FAILED)"
    else
        echo "!! [A$n] $v/$b re-implementation FAILED"
    fi
done

echo "=== PHASE B: simulations ($PAR in parallel) $(date) ==="
python3 - "$ENV_DIR" > "$ENV_DIR/logs/saif_simlist.tsv" <<'PY'
import json,sys,pathlib
E=sys.argv[1]; out=[]
for f in ("saif_phaseB.json","saif_phaseA.json"):
    for r in json.load(open(f"{E}/logs/{f}")):
        if pathlib.Path(f"{E}/saif/results/{r['variant']}_{r['bench']}.txt").is_file(): continue
        if not pathlib.Path(f"{E}/saif/{r['variant']}_{r['bench']}/netlist.v").is_file(): continue
        out.append("\t".join([r['variant'],r['bench'],r['xpr'],r['top']]))
print("\n".join(out))
PY
echo "  $(wc -l < "$ENV_DIR/logs/saif_simlist.tsv") simulations queued"
tr '\t' ' ' < "$ENV_DIR/logs/saif_simlist.tsv" | \
  xargs -P "$PAR" -n4 bash -c '"'"$ENV_DIR"'/scripts/saif_one.sh" "$@"' _
echo "=== finished $(date) ==="
