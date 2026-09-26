#!/usr/bin/env bash
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
mapfile -t J < <(python3 -c "
import json
for r in json.load(open('$ENV_DIR/logs/saif_regate.json')):
    print('\t'.join([r['variant'],r['bench'],r['xpr'],r['top']]))")
echo "=== re-measuring ${#J[@]} configs with the UART fast-forward, $(date) ==="
printf '%s\n' "${J[@]}" | tr '\t' ' ' | \
  xargs -P "${PAR:-3}" -n4 bash -c '"'"$ENV_DIR"'/scripts/saif_one.sh" "$@"' _
echo "=== finished $(date) ==="
