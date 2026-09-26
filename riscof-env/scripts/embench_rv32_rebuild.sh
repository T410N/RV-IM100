#!/usr/bin/env bash
# Rebuild only the RV32 Embench bitstreams, after the RV32 counter-read fix.
#
# RV64 is untouched: on RV64 a single csrr reads the whole 64-bit counter, and
# all 30 RV64 measurements already matched simulation exactly.  Only the 40 RV32
# bitstreams carry the broken read and need replacing.
#
# Output goes to bitstream/embench/RV32/<variant>/, the layout the directory now
# uses.  Resumable: a configuration whose bitstream exists is skipped.
set -uo pipefail
E="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; R="$E/.."
BENCHES=(matmult-int crc32 nettle-aes statemate md5sum)
LOGS="$E/logs/embench_fpga"; mkdir -p "$LOGS"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
mapfile -t T < <(python3 -c "
import json
for r in json.load(open('$E/logs/embench_targets.json')):
    if r['variant'].startswith('RV32'):
        print('\t'.join([r['variant'],r['isa'],str(r['clock']),str(r['baud']),r['xpr']]))")
total=$(( ${#T[@]} * ${#BENCHES[@]} )); n=0
echo "=== RV32 rebuild: ${#T[@]} variants x ${#BENCHES[@]} = $total builds, $(date) ==="
for line in "${T[@]}"; do
  IFS=$'\t' read -r v isa clk baud xpr <<<"$line"
  out="$R/bitstream/embench/RV32/$v"; mkdir -p "$out"
  for b in "${BENCHES[@]}"; do
    n=$((n+1)); tag="${v}_${b}"; bit="$out/${v}_embench_${b}.bit"
    [ -s "$bit" ] && { echo "=== [$n/$total] $tag already built"; continue; }
    mem="$E/build/embench_fpga/$isa/$b.mem"
    [ -s "$mem" ] || { echo "!! [$n/$total] $tag: no image"; continue; }
    work="$R/RV-IM100_RTL/project_files/RV32s/SoCs/${v}_Embench_${b}"
    [ -d "$work" ] || { echo "!! [$n/$total] $tag: no project at $work"; continue; }
    cp "$mem" "$work/$b.mem"
    WX=$(find "$work" -maxdepth 1 -name '*.xpr' | head -1)
    echo ">>> [$n/$total] $tag  ${clk}MHz  $(date +%H:%M:%S)"
    rm -f "$work"/*.lock
    timeout 7200 vivado -mode batch -nojournal -nolog -notrace \
      -source "$E/scripts/bitstream_impl.tcl" \
      -tclargs "$WX" "$clk" "$work/$b.mem" "$bit" reimpl > "$LOGS/$tag.log" 2>&1
    wns=$(grep '^CLOCK ' "$LOGS/$tag.log" 2>/dev/null | grep -v 'wns=none' | head -1 | sed -n 's/.*wns=\([^ ]*\).*/\1/p')
    if [ -s "$bit" ]; then echo "<<< [$n/$total] $tag  WNS=${wns:-?}"
    else echo "!! [$n/$total] $tag FAILED (WNS=${wns:-?})"; fi
  done
done
echo "=== RV32 rebuild finished $(date) ==="
