#!/usr/bin/env bash
# Re-capture SAIF from scratch for configs whose CLOCK changed.
# A SAIF records toggle counts over a simulated duration, so its implied
# activity rate belongs to the clock it was captured at; re-costing it against
# a design running at a different frequency understates switching.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
for tag in "$@"; do
  v="${tag%_*}"; b="${tag##*_}"
  read -r xpr top < <(python3 -c "
import json
for r in json.load(open('$ENV_DIR/logs/saif_jobs_perbench.json')):
    if r['variant']=='$v' and r['bench']=='$b': print(r['xpr'],r['top'])")
  [ -z "${xpr:-}" ] && { echo "!! $tag: no job"; continue; }
  # clear the stale capture so saif_one.sh does not skip it
  rm -rf "$ENV_DIR/saif/$tag" "$ENV_DIR/saif/results/$tag.txt"
  echo ">>> $tag  $top  $(date +%H:%M:%S)"
  "$ENV_DIR/scripts/saif_one.sh" "$v" "$b" "$xpr" "$top"
  r="$ENV_DIR/saif/results/$tag.txt"
  [ -s "$r" ] && { echo "<<< $tag"; cat "$r" | sed 's/^/    /'; } || echo "!! $tag produced no result"
done
echo "=== resim finished $(date) ==="
