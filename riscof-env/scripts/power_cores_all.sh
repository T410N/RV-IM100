#!/usr/bin/env bash
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$ENV_DIR/../RV-IM100_RTL/project_files"; OUT="$ENV_DIR/logs/core_reports"; LOGS="$ENV_DIR/logs/powercore"
mkdir -p "$OUT" "$LOGS"; source /tools/Xilinx/2025.2/Vivado/settings64.sh
mapfile -t X < <(find "$REPO/RV32s/cores" "$REPO/RV64s/cores" -maxdepth 3 -name '*.xpr' | grep -v /archive/ | sort)
echo "=== ${#X[@]} projects $(date) ==="
one(){ xpr="$1"; name="$(basename "$(dirname "$xpr")")"
  case "$xpr" in */RV64IM_5SP/*) name="RV64IM_5SP";; esac
  echo ">>> $name $(date +%H:%M:%S)"
  vivado -mode batch -nojournal -nolog -notrace -source "$ENV_DIR/scripts/power_core.tcl" \
    -tclargs "$xpr" "$OUT/$name" > "$LOGS/$name.log" 2>&1
  echo "<<< $name $(grep -oE 'POWER_OK|READONLY_SKIP|NOT_SYNTHESIZED' "$LOGS/$name.log"|head -1) $(date +%H:%M:%S)"; }
export -f one; export ENV_DIR OUT LOGS
printf '%s\n' "${X[@]}" | xargs -P 2 -I{} bash -c 'one "$@"' _ {}
echo "=== done $(date) ==="
