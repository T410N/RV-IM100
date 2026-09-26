#!/usr/bin/env bash
# Map the frequency/slack curve for one project by varying ONLY the PLL.
# The ROM image is held constant so the design is identical at every point and
# the sweep isolates the clock; benchmark timing numbers from these builds are
# meaningless by design, only the timing closure matters.
#   $1 project dir   $2 ROM image (held constant)   $3.. frequencies
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJ="$1"; shift
MEMNAME="$1"; shift          # hold this exact image constant across the sweep
FREQS="$*"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
XPR=$(find "$PROJ" -maxdepth 1 -name '*.xpr' | head -1)
MEM=$(find "$PROJ" -name "$MEMNAME" 2>/dev/null | grep -vE '\.cache/|\.runs/|\.gen/' | head -1)
[ -z "$MEM" ] && { echo "!! image $MEMNAME not found under $PROJ"; exit 1; }
NAME=$(basename "$PROJ")
OUT="$ENV_DIR/logs/fmax_sweep/$NAME"; mkdir -p "$OUT"
echo "=== $NAME  image $(basename "$MEM")  $(date) ==="
printf "%10s %10s %10s %10s  %s\n" ASKED RAN WNS FMAX verdict
for f in $FREQS; do
    tag="f${f}"
    if [ ! -s "$OUT/$tag.log" ]; then
        rm -f "$PROJ"/*.lock
        timeout 7200 vivado -mode batch -nojournal -nolog -notrace \
            -source "$ENV_DIR/scripts/reimage_impl.tcl" \
            -tclargs "$XPR" "$f" "$MEM" "$OUT/$tag" > "$OUT/$tag.log" 2>&1
    fi
    line=$(grep -m1 '^CLOCK ' "$OUT/$tag.log" 2>/dev/null | grep -v 'wns=none')
    [ -z "$line" ] && line=$(grep '^CLOCK ' "$OUT/$tag.log" 2>/dev/null | grep -v 'wns=none' | head -1)
    ran=$(sed -n 's/.*mhz=\([^ ]*\).*/\1/p' <<<"$line")
    wns=$(sed -n 's/.*wns=\([^ ]*\).*/\1/p' <<<"$line")
    fmx=$(sed -n 's/.*fmax=\([^ ]*\).*/\1/p' <<<"$line")
    if [ -z "$wns" ]; then v="FAILED"; else
        v=$(python3 -c "
w=float('$wns')
print('FAILS' if w<0 else ('marginal (<0.05 ns)' if w<0.05 else 'solid'))")
    fi
    printf "%10s %10s %10s %10s  %s\n" "$f" "${ran:--}" "${wns:--}" "${fmx:--}" "$v"
done
echo "=== done $(date) ==="
