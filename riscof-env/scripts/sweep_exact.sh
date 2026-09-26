#!/usr/bin/env bash
# Frequency sweep with a MATCHING image at every point.
#
# The benchmark's timing loop is compiled for one clock, and the ROM contents
# are part of the synthesized design, so holding one image across a sweep
# measures a different processor at every point.  Here each point: asks the
# MMCM what it actually resolves the requested frequency to, builds the image
# for THAT exact value, then implements.
#
# Runs on a COPY of the project so the measured state is never disturbed.
#   $1 variant   $2 benchmark   $3.. requested frequencies
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; ROOT="$ENV_DIR/.."
v="$1"; b="$2"; shift 2
source /tools/Xilinx/2025.2/Vivado/settings64.sh
read -r xpr < <(python3 -c "
import csv
for r in csv.DictReader(open('$ROOT/evidence/CONFIGURATIONS_perbench.csv')):
    if r['variant']=='$v' and r['benchmark']=='$b': print(r['xpr'])")
src="$ROOT/RV-IM100_RTL/project_files/$(dirname "$xpr")"
work="$ROOT/RV-IM100_RTL/project_files/.sweep/${v}_${b}"
OUT="$ENV_DIR/logs/sweep_exact/${v}_${b}"; mkdir -p "$OUT"
if [ ! -d "$work" ]; then
  mkdir -p "$(dirname "$work")"
  cp -a "$src" "$work"
  rm -rf "$work"/*.runs "$work"/*.cache "$work"/*.hw "$work"/*.sim
  echo "  working copy: .sweep/${v}_${b}  (source project untouched)"
fi
WXPR=$(find "$work" -maxdepth 1 -name '*.xpr' | head -1)
echo "=== $v/$b  sweep with matching images  $(date) ==="
printf "%12s %16s %10s %10s %12s  %s\n" ASKED EXACT WNS LUT FMAX verdict
for f in "$@"; do
  tag="f${f}"
  rm -f "$work"/*.lock
  ex=$(timeout 900 vivado -mode batch -nojournal -nolog -notrace -source "$ENV_DIR/scripts/probe_pll.tcl" \
        -tclargs "$WXPR" "$f" 2>&1 | sed -n 's/.*exact=\([0-9.]*\).*/\1/p' | head -1)
  [ -z "$ex" ] && { printf "%12s %16s  PROBE FAILED\n" "$f" "-"; continue; }
  img=$(bash "$ENV_DIR/scripts/build_image_exact.sh" "$v" "$b" "$ex" 2>/dev/null | tail -1)
  [ ! -s "${img:-/nonexistent}" ] && { printf "%12s %16s  IMAGE BUILD FAILED\n" "$f" "$ex"; continue; }
  baud=$(python3 -c "print(round(float('$ex')*1e6/115200))")
  dest=$(find "$work" -name '*.mem' 2>/dev/null | grep -vE '\.cache/|\.runs/|\.gen/' | head -1)
  cp "$img" "$(dirname "${dest:-$work}")/$(basename "$img")"
  python3 - "$work" "$(basename "$img")" "$baud" <<'PY'
import re,sys,pathlib
proj,image,baud=sys.argv[1],sys.argv[2],int(sys.argv[3])
skip=re.compile(r"\.cache/|\.runs/|\.gen/|\.ip_user_files/|\.sim/")
src=lambda p:[x for x in pathlib.Path(proj).rglob(p) if not skip.search(str(x))]
for f in src("Instruction_Memory.v"):
    t=f.read_text(errors="replace")
    f.write_text(re.sub(r'(\$readmemh\("\./)[^"]+(")',lambda m:m.group(1)+image+m.group(2),t))
for u in src("UART_TX.v"):
    s=u.read_text(errors="replace"); m=re.search(r"(BAUD_DIV\s*=\s*)(\d+)",s)
    if m: u.write_text(s[:m.start(2)]+str(baud)+s[m.end(2):])
PY
  timeout 7200 vivado -mode batch -nojournal -nolog -notrace -source "$ENV_DIR/scripts/reimage_impl.tcl" \
      -tclargs "$WXPR" "$ex" "$(dirname "${dest:-$work}")/$(basename "$img")" "$OUT/$tag" > "$OUT/$tag.log" 2>&1
  wns=$(grep '^CLOCK ' "$OUT/$tag.log" | grep -v 'wns=none' | head -1 | sed -n 's/.*wns=\([^ ]*\).*/\1/p')
  lut=$(grep -m1 -oP '\|\s+Slice LUTs\*?\s+\|\s+\K[0-9]+' "$OUT/$tag/utilization.rpt" 2>/dev/null)
  if [ -z "$wns" ]; then vd="FAILED"; fmax="-"; else
    fmax=$(python3 -c "print(f'{1000.0/(1000.0/float(\"$ex\")-float(\"$wns\")):.3f}')")
    vd=$(python3 -c "print('FAILS' if float('$wns')<0 else 'meets')")
  fi
  printf "%12s %16s %10s %10s %12s  %s\n" "$f" "$ex" "${wns:--}" "${lut:--}" "$fmax" "$vd"
done
echo "=== done $(date) ==="
