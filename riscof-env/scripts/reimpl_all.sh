#!/usr/bin/env bash
# Re-synthesize and implement every SoCs project, two at a time.
#
# Strategies are never touched -- reimpl.tcl only resets and relaunches, so each
# project keeps the synth/impl strategy it was set up with.
set -uo pipefail

ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$ENV_DIR/../RV-IM100_RTL/project_files"
LOGS="$ENV_DIR/logs/vivado"
PAR="${PAR:-2}"          # projects in flight; each uses -jobs 8

mkdir -p "$LOGS"
source /tools/Xilinx/2025.2/Vivado/settings64.sh

# Read-only projects go last, so a session the user closes mid-run still gets
# picked up on the retry pass at the end.
mapfile -t XPRS < <(find "$REPO/RV32s/SoCs" "$REPO/RV64s/SoCs" -maxdepth 3 -name '*.xpr' \
                    2>/dev/null | grep -v /archive/ | sort)
SKIPPED=()

echo "=== ${#XPRS[@]} projects, $PAR at a time, $(date) ==="

run_one() {
    local xpr="$1"
    local name
    name="$(basename "$(dirname "$xpr")")_$(basename "$xpr" .xpr)"
    local log="$LOGS/$name.log"
    # a stale lock from a crashed run would block open_project
    rm -f "$(dirname "$xpr")/$(basename "$xpr" .xpr).lock" 2>/dev/null
    echo ">>> start $name  $(date +%H:%M:%S)"
    vivado -mode batch -nojournal -nolog -notrace \
           -source "$ENV_DIR/scripts/reimpl.tcl" -tclargs "$xpr" \
           > "$log" 2>&1
    local rc=$?
    local prog
    if grep -q '^READONLY_SKIP' "$log"; then
        echo "<<< SKIP  $name  (open in another Vivado session)  $(date +%H:%M:%S)"
        return 0
    fi
    prog=$(grep -m1 '^IMPL_PROGRESS' "$log" | awk '{print $2}')
    local fmax
    fmax=$(grep -m1 '^FMAX_MHZ' "$log" | awk '{print $2}')
    echo "<<< done  $name  rc=$rc progress=${prog:-?} fmax=${fmax:-?}  $(date +%H:%M:%S)"
}
export -f run_one
export ENV_DIR LOGS

printf '%s\n' "${XPRS[@]}" | xargs -P "$PAR" -I{} bash -c 'run_one "$@"' _ {}

# retry anything that was locked earlier -- the session may have been closed
for f in "$LOGS"/*.log; do
    if grep -q '^READONLY_SKIP' "$f"; then
        x=$(grep -m1 '^READONLY_SKIP' "$f" | awk '{print $2}')
        echo ">>> retry $(basename "$f" .log)  $(date +%H:%M:%S)"
        run_one "$x"
    fi
done

echo
echo "=== summary ==="
printf "%-46s %-9s %-9s %s\n" PROJECT IMPL WNS FMAX_MHZ
for f in "$LOGS"/*.log; do
    n=$(basename "$f" .log)
    p=$(grep -m1 '^IMPL_PROGRESS' "$f" | awk '{print $2}')
    w=$(grep -m1 '^TIMING' "$f" | sed -n 's/.*wns=\([^ ]*\).*/\1/p')
    x=$(grep -m1 '^FMAX_MHZ' "$f" | awk '{print $2}')
    printf "%-46s %-9s %-9s %s\n" "$n" "${p:-FAILED}" "${w:-–}" "${x:-–}"
done
echo "=== finished $(date) ==="
