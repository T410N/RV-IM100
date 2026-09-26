#!/usr/bin/env bash
# SAIF power for every config in saif_jobs.json, one at a time. Resumable.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
mapfile -t J < <(python3 -c "
import json
for r in json.load(open('$ENV_DIR/logs/saif_jobs.json')):
    print('\t'.join([r['variant'],r['bench'],r['xpr'],r['top']]))")
echo "=== ${#J[@]} configs, $(date) ==="
n=0
for line in "${J[@]}"; do
    IFS=$'\t' read -r v b xpr top <<<"$line"
    n=$((n+1)); echo ">>> [$n/${#J[@]}] $v/$b  $(date +%H:%M:%S)"
    "$ENV_DIR/scripts/saif_one.sh" "$v" "$b" "$xpr" "$top"
done
echo "=== finished $(date) ==="
