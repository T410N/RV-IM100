#!/usr/bin/env bash
# Restore a Vivado project to the exact configuration that produced one bitstream,
# then re-implement.  Everything needed is in CONFIGURATIONS.csv, so any row of the
# results workbook can be reproduced from scratch.
#
#   ./restore_config.sh <variant> <dhrystone|coremark> [--implement]
#
# Without --implement it only sets the sources and reports what changed, so you can
# inspect before committing an hour of tool time.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V="${1:?variant}"; B="${2:?dhrystone|coremark}"; DO_IMPL="${3:-}"

read -r XPR MEM CLK BAUD < <(python3 - "$ROOT" "$V" "$B" <<'PY'
import csv,sys
root,v,b=sys.argv[1:4]
for r in csv.DictReader(open(f"{root}/evidence/CONFIGURATIONS.csv")):
    if r["variant"]==v and r["benchmark"]==b:
        print(r["xpr"], r["mem_image"], r["clock_mhz"], r["baud_div"]); break
else:
    raise SystemExit(f"no configuration for {v}/{b}")
PY
)
PROJ="$ROOT/RV-IM100_RTL/project_files/$(dirname "$XPR")"
echo "variant   : $V / $B"
echo "project   : $XPR"
echo "image     : $MEM"
echo "clock     : $CLK MHz   BAUD_DIV $BAUD"

if ! python3 - "$PROJ" "$MEM" "$BAUD" <<'PY'
import re,sys,pathlib
proj,image,baud=sys.argv[1],sys.argv[2],int(sys.argv[3])
skip=re.compile(r"\.cache/|\.runs/|\.gen/|\.ip_user_files/|\.sim/")
src=lambda p:[x for x in pathlib.Path(proj).rglob(p) if not skip.search(str(x))]
# images may live in the project OR in the shared benchmarks library, where they
# are added to the project as out-of-tree sources
lib=pathlib.Path(proj).parents[2]/"benchmarks"
found = src(image) or [x for x in lib.rglob(image)] if lib.is_dir() else src(image)
if not found:
    raise SystemExit(f"ERROR: {image} found neither in the project nor in benchmarks/")
print(f"  image located: {found[0]}")
for f in src("Instruction_Memory.v"):
    t=f.read_text(errors="replace")
    n=re.sub(r'(\$readmemh\("\./)[^"]+(")',lambda m:m.group(1)+image+m.group(2),t)
    if n!=t: f.write_text(n); print(f"  set $readmemh -> {image}")
for u in src("UART_TX.v"):
    s=u.read_text(errors="replace"); m=re.search(r"(BAUD_DIV\s*=\s*)(\d+)",s)
    if m and m.group(2)!=str(baud):
        u.write_text(s[:m.start(2)]+str(baud)+s[m.end(2):]); print(f"  set BAUD_DIV -> {baud}")
PY
then
    echo "FAILED: could not set the sources"; exit 1
fi

if [ "$DO_IMPL" != "--implement" ]; then
    echo "sources set. re-run with --implement to set the PLL and re-implement."
    exit 0
fi
source /tools/Xilinx/2025.2/Vivado/settings64.sh
MEMPATH=$(find "$PROJ" -name "$MEM" | grep -vE '\.cache/|\.runs/|\.gen/' | head -1)
rm -f "$PROJ"/*.lock
vivado -mode batch -nojournal -nolog -notrace \
  -source "$ROOT/riscof-env/scripts/reimage_impl.tcl" \
  -tclargs "$ROOT/RV-IM100_RTL/project_files/$XPR" "$CLK" "$MEMPATH" "$ROOT/evidence/restore_${V}_${B}" \
  | grep -E '^(PLL_|IP_|IMPL_PROGRESS|CLOCK|REIMAGE_OK|CLOCK_MISMATCH)'
