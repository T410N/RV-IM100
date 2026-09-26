#!/usr/bin/env bash
# Re-image and re-implement, ONE PROJECT AT A TIME (parallel Vivado runs on this
# machine are slower, not faster).  Resumable: a run whose log has REIMAGE_OK is
# skipped, so this can be re-entered after an interruption.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS="$ENV_DIR/logs/reimage"; OUT="$ENV_DIR/logs/reimage_reports"
mkdir -p "$LOGS" "$OUT"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
# logs/reimage_jobs.tsv is prepared by the caller (see reimage_redo.json)
total=$(wc -l < "$ENV_DIR/logs/reimage_jobs.tsv"); n=0
while IFS=$'\t' read -r variant bench mhz baud xpr imem dest image cur; do
    n=$((n+1)); tag="${variant}_${bench}"
    if grep -q REIMAGE_OK "$LOGS/$tag.log" 2>/dev/null; then
        echo "=== [$n/$total] $tag already done, skipping"; continue
    fi
    echo ">>> [$n/$total] $tag  @${mhz}MHz  image=$image  $(date +%H:%M:%S)"
    # point the ROM at the new image and match the UART divisor to the clock
    python3 - "$imem" "$image" "$baud" "$(dirname "$xpr")" <<'PY'
import re,sys,pathlib
imem,image,baud,proj=sys.argv[1],sys.argv[2],int(sys.argv[3]),sys.argv[4]
p=pathlib.Path(imem); t=p.read_text(errors="replace")
t2=re.sub(r'(\$readmemh\("\./)[^"]+(")', lambda m: m.group(1)+image+m.group(2), t)
p.write_text(t2)
skip=re.compile(r"\.cache/|\.runs/|\.gen/|\.ip_user_files/|\.sim/")
for u in pathlib.Path(proj).rglob("UART_TX.v"):
    if skip.search(str(u)): continue
    s=u.read_text(errors="replace")
    m=re.search(r"(BAUD_DIV\s*=\s*)(\d+)",s)
    if m: u.write_text(s[:m.start(2)]+str(baud)+s[m.end(2):])
PY
    rm -f "$(dirname "$xpr")/$(basename "$xpr" .xpr).lock"
    timeout 7200 vivado -mode batch -nojournal -nolog -notrace \
        -source "$ENV_DIR/scripts/reimage_impl.tcl" \
        -tclargs "$xpr" "$mhz" "$dest" "$OUT/$tag" > "$LOGS/$tag.log" 2>&1
    st=$(grep -oE 'REIMAGE_OK|READONLY_SKIP|IMPL_PROGRESS .*' "$LOGS/$tag.log" | tail -1)
    fm=$(grep '^CLOCK' "$LOGS/$tag.log" | grep -v 'wns=none' | head -1 | sed -n 's/.*fmax=\([^ ]*\).*/\1/p')
    echo "<<< [$n/$total] $tag  ${st:-FAILED}  fmax=${fm:-?}  $(date +%H:%M:%S)"
done < "$ENV_DIR/logs/reimage_jobs.tsv"
echo "=== all done $(date) ==="
