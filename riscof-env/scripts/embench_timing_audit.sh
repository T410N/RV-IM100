#!/usr/bin/env bash
# Quarantine any Embench bitstream whose build violated timing.
#
# embench_fpga_all.sh treats "the .bit exists" as success, but Vivado writes a
# loadable bitstream even when WNS is negative.  Such a design may misbehave on
# hardware, so it must not sit in the output directory looking usable.
# Run after the queue finishes, or any time to check progress.
set -uo pipefail
E="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; R="$E/.."
OUT="$R/bitstream/embench"; mkdir -p "$OUT/failed_timing"
bad=0; ok=0
for lg in "$E"/logs/embench_fpga/*.log; do
  tag=$(basename "$lg" .log); v="${tag%_*}"; b="${tag##*_}"
  wns=$(grep '^CLOCK ' "$lg" 2>/dev/null | grep -v 'wns=none' | head -1 | sed -n 's/.*wns=\([^ ]*\).*/\1/p')
  [ -z "$wns" ] && continue
  bit="$OUT/${v}_embench_${b}.bit"
  if python3 -c "import sys; sys.exit(0 if float('$wns')<0 else 1)"; then
    if [ -s "$bit" ]; then mv "$bit" "$OUT/failed_timing/"; fi
    echo "  VIOLATES $tag  WNS=$wns  -> quarantined"; bad=$((bad+1))
  else ok=$((ok+1)); fi
done
echo "  timing-clean: $ok   violating: $bad"
