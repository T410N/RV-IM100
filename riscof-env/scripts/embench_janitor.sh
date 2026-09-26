#!/usr/bin/env bash
# Reclaim Vivado scratch as Embench builds finish.
#
# Runs alongside the build queue rather than inside it: editing a script bash is
# already executing can make it read garbage at shifted offsets, so this is a
# separate process that only ever deletes directories whose bitstream is
# already on disk and which no running Vivado is using.
set -uo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
while true; do
  active=$(ps -eo args --no-headers | grep -oE '/SoCs/[A-Za-z0-9_]+_Embench_[a-z0-9-]+' | sed 's|.*/||' | sort -u)
  for d in "$R"/RV-IM100_RTL/project_files/RV*/SoCs/*_Embench_*/; do
    v=$(basename "$d")
    grep -qx "$v" <<<"$active" && continue
    bench="${v##*_Embench_}"; var="${v%_Embench_*}"
    arch=RV32; [[ "$var" == RV64* ]] && arch=RV64
    bit="$R/bitstream/embench/$arch/$var/${var}_embench_${bench}.bit"
    [ -s "$bit" ] || [ -s "$R/bitstream/embench/$arch/Done/$var/${var}_embench_${bench}.bit" ] || continue
    for s in "$d"*.runs "$d"*.cache "$d"*.sim "$d"*.hw; do
      [ -d "$s" ] && rm -rf "$s"
    done
  done
  # stop once the queue is done
  pgrep -f embench_rv32_rebuild >/dev/null || { echo "queue finished; janitor exiting $(date)"; break; }
  sleep 120
done
