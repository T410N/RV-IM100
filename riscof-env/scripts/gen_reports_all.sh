#!/usr/bin/env bash
# Regenerate uniform impl reports for every SoCs project except the skip list.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$ENV_DIR/../RV-IM100_RTL/project_files"
OUT="$ENV_DIR/logs/impl_reports"
LOGS="$ENV_DIR/logs/genrpt"
# RV32I_5SP is open in another Vivado session; RV32IM_5SP is being
# re-implemented by the user.  Touching either would collide.
SKIP_RE='SoCs/(RV32I_5SP|RV32IM_5SP)/'
mkdir -p "$OUT" "$LOGS"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
mapfile -t XPRS < <(find "$REPO/RV32s/SoCs" "$REPO/RV64s/SoCs" -maxdepth 3 -name '*.xpr' \
                    | grep -v /archive/ | grep -vE "$SKIP_RE" | sort)
echo "=== ${#XPRS[@]} projects, $(date) ==="
one() {
  xpr="$1"; name="$(basename "$(dirname "$xpr")")"
  case "$xpr" in */RV64IM_7SP_BRAM_Opt/*) name="RV64IM_7SP_BRAM_Opt";; esac
  echo ">>> $name $(date +%H:%M:%S)"
  vivado -mode batch -nojournal -nolog -notrace \
    -source "$ENV_DIR/scripts/gen_reports.tcl" -tclargs "$xpr" "$OUT/$name" \
    > "$LOGS/$name.log" 2>&1
  echo "<<< $name $(grep -oE 'REPORTS_OK|READONLY_SKIP|INCOMPLETE' "$LOGS/$name.log" | head -1) $(date +%H:%M:%S)"
}
export -f one; export ENV_DIR OUT LOGS
printf '%s\n' "${XPRS[@]}" | xargs -P 2 -I{} bash -c 'one "$@"' _ {}
echo "=== done $(date) ==="
