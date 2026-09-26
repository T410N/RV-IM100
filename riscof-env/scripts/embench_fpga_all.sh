#!/usr/bin/env bash
# Build FPGA bitstreams for the Embench subset: 5 benchmarks x 16 variants.
#
# Each (variant, benchmark) gets its own project directory,
#   <variant>_Embench_<benchmark>
# copied from that variant's CoreMark project, so no measured project is ever
# retargeted and each Embench build keeps the state it was measured in.
#
# The clock is held at the variant's measured operating frequency: Embench
# reports cycles from mcycle, so the frequency does not affect the result, but
# the copied project's BAUD_DIV already matches that clock and the UART output
# has to stay readable.  Embench images are clock-independent for the same
# reason, so no image is rebuilt per frequency.
#
# Resumable: a configuration whose bitstream already exists is skipped.
set -uo pipefail
E="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; R="$E/.."
BENCHES=(matmult-int crc32 nettle-aes statemate md5sum)
OUT="$R/bitstream/embench"; mkdir -p "$OUT"
LOGS="$E/logs/embench_fpga"; mkdir -p "$LOGS"
source /tools/Xilinx/2025.2/Vivado/settings64.sh

mapfile -t T < <(python3 -c "
import json
for r in json.load(open('$E/logs/embench_targets.json')):
    print('\t'.join([r['variant'],r['isa'],str(r['clock']),str(r['baud']),r['xpr']]))")
total=$(( ${#T[@]} * ${#BENCHES[@]} )); n=0
echo "=== ${#T[@]} variants x ${#BENCHES[@]} benchmarks = $total builds, $(date) ==="
for line in "${T[@]}"; do
  IFS=$'\t' read -r v isa clk baud xpr <<<"$line"
  src="$R/RV-IM100_RTL/project_files/$(dirname "$xpr")"
  arch=$(dirname "$(dirname "$(dirname "$xpr")")")   # RV32s | RV64s
  for b in "${BENCHES[@]}"; do
    n=$((n+1)); tag="${v}_${b}"
    bit="$OUT/${v}_embench_${b}.bit"
    if [ -s "$bit" ]; then echo "=== [$n/$total] $tag already built"; continue; fi
    mem="$E/build/embench_fpga/$isa/$b.mem"
    if [ ! -s "$mem" ]; then echo "!! [$n/$total] $tag: no image $mem"; continue; fi
    work="$R/RV-IM100_RTL/project_files/$arch/SoCs/${v}_Embench_${b}"
    if [ ! -d "$work" ]; then
      cp -a "$src" "$work"
      rm -rf "$work"/*.runs "$work"/*.cache "$work"/*.hw "$work"/*.sim
      find "$work" -name '*.mem' -delete 2>/dev/null
    fi
    cp "$mem" "$work/$b.mem"
    python3 - "$work" "$b.mem" <<'PY'
import re,sys,pathlib
proj,image=sys.argv[1],sys.argv[2]
skip=re.compile(r"\.cache/|\.runs/|\.gen/|\.ip_user_files/|\.sim/")
for f in [x for x in pathlib.Path(proj).rglob("Instruction_Memory.v") if not skip.search(str(x))]:
    t=f.read_text(errors="replace")
    f.write_text(re.sub(r'(\$readmemh\("\./)[^"]+(")',lambda m:m.group(1)+image+m.group(2),t))
PY
    WX=$(find "$work" -maxdepth 1 -name '*.xpr' | head -1)
    echo ">>> [$n/$total] $tag  ${clk}MHz  $(date +%H:%M:%S)"
    rm -f "$work"/*.lock
    timeout 7200 vivado -mode batch -nojournal -nolog -notrace \
      -source "$E/scripts/bitstream_impl.tcl" \
      -tclargs "$WX" "$clk" "$work/$b.mem" "$bit" reimpl > "$LOGS/$tag.log" 2>&1
    wns=$(grep '^CLOCK ' "$LOGS/$tag.log" 2>/dev/null | grep -v 'wns=none' | head -1 | sed -n 's/.*wns=\([^ ]*\).*/\1/p')
    if [ -s "$bit" ]; then
      echo "<<< [$n/$total] $tag  WNS=${wns:-?}  $(du -h "$bit" | cut -f1)"
    else
      echo "!! [$n/$total] $tag FAILED (WNS=${wns:-?})"; tail -3 "$LOGS/$tag.log" | sed 's/^/    /'
    fi
  done
done
echo "=== embench fpga finished $(date) ==="
