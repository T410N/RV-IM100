#!/usr/bin/env bash
# Generate all 32 bitstreams (16 variants x 2 benchmarks) into bitstream/.
#
# Phase 1: the image each project already holds -- routed already, so only the
#          write_bitstream step runs (fast).
# Phase 2: the other benchmark -- switch the .mem, PLL and UART divisor, then
#          re-implement from scratch and write the bitstream.
#
# One Vivado at a time. Resumable: a target whose .bit already exists is skipped.
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ENV_DIR/../bitstream"
LOGS="$ENV_DIR/logs/bitstream"
mkdir -p "$OUT" "$LOGS"
source /tools/Xilinx/2025.2/Vivado/settings64.sh

PHASE="${PHASE:-both}"
mapfile -t JOBS < <(python3 - "$ENV_DIR" "$PHASE" <<'PY'
import json, sys
targets = json.load(open(f"{sys.argv[1]}/logs/bitstream_targets.json"))
phase = sys.argv[2]
want = {"loaded": [True], "reimpl": [False], "both": [True, False]}[phase]
# loaded ones first: they are quick and bank half the deliverable early
for r in sorted(targets, key=lambda x: (not x["loaded"], x["variant"], x["bench"])):
    if r["loaded"] not in want:
        continue
    print("\t".join([r["variant"], r["bench"], str(r["mhz"]), str(r["baud"]),
                     r["xpr"], r["image"], "reuse" if r["loaded"] else "reimpl"]))
PY
)
total=${#JOBS[@]}; n=0
echo "=== $total bitstreams to generate ($(date)) ==="
for line in "${JOBS[@]}"; do
    IFS=$'\t' read -r variant bench mhz baud xpr image mode <<<"$line"
    n=$((n+1)); tag="${variant}_${bench}_$(printf '%.0f' "$mhz")MHz"
    bit="$OUT/$tag.bit"
    if [ -s "$bit" ]; then echo "=== [$n/$total] $tag exists, skipping"; continue; fi
    proj="$(dirname "$xpr")"
    echo ">>> [$n/$total] $tag  ($mode, ${mhz}MHz, $image)  $(date +%H:%M:%S)"
    if [ "$mode" = "reimpl" ]; then
        # point the ROM at the other benchmark and match the UART divisor
        python3 - "$proj" "$image" "$baud" <<'PY'
import re, sys, pathlib
proj, image, baud = sys.argv[1], sys.argv[2], int(sys.argv[3])
skip = re.compile(r"\.cache/|\.runs/|\.gen/|\.ip_user_files/|\.sim/")
src = lambda pat: [p for p in pathlib.Path(proj).rglob(pat) if not skip.search(str(p))]
mem = next((p for p in src(image)), None)
if mem is None:                       # not in the project yet - copy it in
    ref = src("*.mem")[0].parent
    for coll in ("dhrystones", "coremarks"):
        cand = pathlib.Path(proj).parents[3] / "benchmarks" / coll / image
        if cand.is_file():
            import shutil; shutil.copy(cand, ref / image); break
for f in src("Instruction_Memory.v"):
    t = f.read_text(errors="replace")
    f.write_text(re.sub(r'(\$readmemh\("\./)[^"]+(")', lambda m: m.group(1)+image+m.group(2), t))
for u in src("UART_TX.v"):
    s = u.read_text(errors="replace")
    m = re.search(r"(BAUD_DIV\s*=\s*)(\d+)", s)
    if m: u.write_text(s[:m.start(2)]+str(baud)+s[m.end(2):])
PY
    fi
    mempath=$(find "$proj" -name "$image" 2>/dev/null | grep -v '\.cache/\|\.runs/\|\.gen/' | head -1)
    rm -f "$proj/$(basename "$xpr" .xpr).lock"
    timeout 10800 vivado -mode batch -nojournal -nolog -notrace \
        -source "$ENV_DIR/scripts/bitstream_impl.tcl" \
        -tclargs "$xpr" "$mhz" "${mempath:-$image}" "$bit" "$mode" > "$LOGS/$tag.log" 2>&1
    st=$(grep -oE 'BITSTREAM_OK.*|NO_BITSTREAM_PRODUCED|READONLY_SKIP|IMPL_PROGRESS .*' "$LOGS/$tag.log" | tail -1)
    ck=$(grep -m1 '^CLOCK' "$LOGS/$tag.log" | sed -n 's/.*mhz=\([^ ]*\) wns=\([^ ]*\).*/\1MHz wns=\2/p')
    echo "<<< [$n/$total] $tag  ${st:-FAILED}  ${ck}  $(date +%H:%M:%S)"
done
echo "=== done $(date).  bitstreams: $(ls "$OUT"/*.bit 2>/dev/null | wc -l)/32 ==="
