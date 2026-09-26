#!/usr/bin/env bash
# Rebuild Embench configurations that failed timing, at a clock they close at.
# Embench times with mcycle, so the cycle count is identical at any frequency
# the design meets timing at -- only the ability to run reliably changes.
set -uo pipefail
E="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; R="$E/.."
OUT="$R/bitstream/embench"
source /tools/Xilinx/2025.2/Vivado/settings64.sh
while [ $# -ge 3 ]; do
  v="$1"; b="$2"; clk="$3"; shift 3
  arch=RV32s; [[ "$v" == RV64* ]] && arch=RV64s
  work="$R/RV-IM100_RTL/project_files/$arch/SoCs/${v}_Embench_${b}"
  WX=$(find "$work" -maxdepth 1 -name '*.xpr' | head -1)
  [ -z "$WX" ] && { echo "!! $v/$b: no project at $work"; continue; }
  baud=$(python3 -c "print(round(float('$clk')*1e6/115200))")
  python3 - "$work" "$baud" <<'PY'
import re,sys,pathlib
proj,baud=sys.argv[1],int(sys.argv[2])
skip=re.compile(r"\.cache/|\.runs/|\.gen/|\.ip_user_files/|\.sim/")
for u in [x for x in pathlib.Path(proj).rglob("UART_TX.v") if not skip.search(str(x))]:
    s=u.read_text(errors="replace"); m=re.search(r"(BAUD_DIV\s*=\s*)(\d+)",s)
    if m: u.write_text(s[:m.start(2)]+str(baud)+s[m.end(2):]); print(f"  BAUD_DIV -> {baud}")
PY
  echo ">>> $v/$b retry at ${clk}MHz  $(date +%H:%M:%S)"
  rm -f "$work"/*.lock
  timeout 7200 vivado -mode batch -nojournal -nolog -notrace -source "$E/scripts/bitstream_impl.tcl" \
    -tclargs "$WX" "$clk" "$work/$b.mem" "$OUT/${v}_embench_${b}.bit" reimpl \
    > "$E/logs/embench_fpga/${v}_${b}.log" 2>&1
  wns=$(grep '^CLOCK ' "$E/logs/embench_fpga/${v}_${b}.log" | grep -v 'wns=none' | head -1 | sed -n 's/.*wns=\([^ ]*\).*/\1/p')
  echo "<<< $v/$b  WNS=${wns:-?}"
done
echo "=== retry finished $(date) ==="
