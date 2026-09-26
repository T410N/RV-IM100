#!/usr/bin/env bash
# Re-open every implemented SoCs project and extract CORRECT per-clock Fmax,
# utilization (LUT/FF/BRAM/DSP) and vectorless power.  Read-only: no re-impl.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$ENV_DIR/../RV-IM100_RTL/project_files"
LOGS="$ENV_DIR/logs/vivado/retime"
PAR="${PAR:-2}"
mkdir -p "$LOGS"
source /tools/Xilinx/2025.2/Vivado/settings64.sh

mapfile -t XPRS < <(find "$REPO/RV32s/SoCs" "$REPO/RV64s/SoCs" -maxdepth 3 -name '*.xpr' \
                    2>/dev/null | grep -v /archive/ | sort)
echo "=== ${#XPRS[@]} projects, $PAR at a time, $(date) ==="
run_one() {
    local xpr="$1" name log
    # variant = the directory directly under SoCs/, not the .xpr's parent:
    # RV64IM_7SP_BRAM_Opt and RV64I_5SP nest their .xpr one level deeper.
    name="$(sed -E 's|.*/SoCs/([^/]+)/.*|\1|' <<<"$xpr")"
    [ "$name" = "RV64I5SP_SoC" ] && name=RV64I_5SP
    log="$LOGS/$name.log"
    rm -f "$(dirname "$xpr")/$(basename "$xpr" .xpr).lock" 2>/dev/null
    echo ">>> $name $(date +%H:%M:%S)"
    timeout 1800 vivado -mode batch -nojournal -nolog -notrace \
        -source "$ENV_DIR/scripts/retime.tcl" -tclargs "$xpr" > "$log" 2>&1
    echo "<<< $name rc=$? $(grep -c '^CLOCK' "$log") clocks $(date +%H:%M:%S)"
}
export -f run_one; export ENV_DIR LOGS
printf '%s\n' "${XPRS[@]}" | xargs -P "$PAR" -I{} bash -c 'run_one "$@"' _ {}
echo "=== finished $(date) ==="
