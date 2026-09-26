#!/usr/bin/env bash
# Retarget every SoC project to the opposite benchmark and re-implement.
# Resumable: a project whose log already contains SWAP_OK is skipped, so this
# can be re-run after an interruption without redoing finished work.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$ENV_DIR/../RV-IM100_RTL/project_files"
OUT="$ENV_DIR/logs/swap_reports"
LOGS="$ENV_DIR/logs/swap"
PAR="${PAR:-2}"
mkdir -p "$OUT" "$LOGS"
source /tools/Xilinx/2025.2/Vivado/settings64.sh

one() {
    proj="$1"; fam="$2"; freq="$3"
    if grep -q SWAP_OK "$LOGS/$proj.log" 2>/dev/null; then
        echo "=== $proj already done, skipping"; return 0
    fi
    xpr=$(find "$REPO/$fam/SoCs/$proj" -maxdepth 3 -name '*.xpr' | head -1)
    [ -z "$xpr" ] && { echo "!! $proj: no .xpr"; return 0; }
    # a lock left by a crashed or suspended run makes the project read-only
    rm -f "$(dirname "$xpr")/$(basename "$xpr" .xpr).lock" 2>/dev/null
    echo ">>> $proj @${freq}MHz $(date +%H:%M:%S)"
    vivado -mode batch -nojournal -nolog -notrace \
        -source "$ENV_DIR/scripts/swap_impl.tcl" \
        -tclargs "$xpr" "$freq" "$OUT/$proj" > "$LOGS/$proj.log" 2>&1
    st=$(grep -oE 'SWAP_OK|READONLY_SKIP' "$LOGS/$proj.log" | tail -1)
    echo "<<< $proj ${st:-FAILED} $(date +%H:%M:%S)"
}
export -f one
export ENV_DIR REPO OUT LOGS

echo "=== swap + re-implementation, $PAR at a time, $(date) ==="
tr '\t' ' ' < "$ENV_DIR/logs/swap_list.tsv" | xargs -P "$PAR" -n3 bash -c 'one "$@"' _
echo "=== done $(date) ==="
