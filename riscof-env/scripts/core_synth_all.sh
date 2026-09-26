#!/usr/bin/env bash
# Core-only synthesis for every cores/ project.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$ENV_DIR/../RV-IM100_RTL/project_files"
LOGS="$ENV_DIR/logs/coresynth"
PAR="${PAR:-2}"
mkdir -p "$LOGS"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
mapfile -t XPRS < <(find "$REPO/RV32s/cores" "$REPO/RV64s/cores" -maxdepth 3 -name '*.xpr' \
                    2>/dev/null | grep -v /archive/ | sort)
echo "=== ${#XPRS[@]} core projects, $PAR at a time, $(date) ==="
one() {
    local xpr="$1" name log
    name="$(sed -E 's|.*/cores/([^/]+)/.*|\1|' <<<"$xpr")"
    log="$LOGS/$name.log"
    rm -f "$(dirname "$xpr")/$(basename "$xpr" .xpr).lock" 2>/dev/null
    echo ">>> $name $(date +%H:%M:%S)"
    timeout 3600 vivado -mode batch -nojournal -nolog -notrace \
        -source "$ENV_DIR/scripts/core_synth.tcl" -tclargs "$xpr" > "$log" 2>&1
    echo "<<< $name rc=$? $(grep -m1 -oE 'DONE|READONLY_SKIP|SYNTH_PROGRESS .*' "$log") $(date +%H:%M:%S)"
}
export -f one; export ENV_DIR LOGS
printf '%s\n' "${XPRS[@]}" | xargs -P "$PAR" -I{} bash -c 'one "$@"' _ {}
echo "=== finished $(date) ==="
