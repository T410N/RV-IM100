#!/usr/bin/env bash
# Verilate one variant into build/<variant>/Vsim_top.
#
# Usage: scripts/build_sim.sh <variant> [<variant> ...]
#        scripts/build_sim.sh all
set -euo pipefail

ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERILATOR="${VERILATOR:-verilator}"

variants=("$@")
if [ "${1:-}" = "all" ] || [ $# -eq 0 ]; then
    mapfile -t variants < <(python3 "$ENV_DIR/scripts/variants.py" | tail -n +2 | awk '{print $1}')
fi

failed=()
for v in "${variants[@]}"; do
    rtl="$ENV_DIR/build/$v/rtl"
    out="$ENV_DIR/build/$v"
    if [ ! -d "$rtl" ]; then
        echo "!! $v: no staged RTL, run scripts/prepare_rtl.py first" >&2
        exit 1
    fi

    incs=(-I"$rtl")
    for sub in headers modules modules/headers; do
        [ -d "$rtl/$sub" ] && incs+=(-I"$rtl/$sub")
    done
    mapfile -t files < <(sed "s#^#$rtl/#" "$rtl/filelist.txt")

    echo "==> verilating $v"
    rm -rf "$out/obj_dir" "$out/Vsim_top"
    # VCD=1 builds a trace-enabled simulator (slower; use only for debugging)
    trace_flags=()
    if [ "${VCD:-0}" = "1" ]; then trace_flags=(--trace --trace-structs --trace-depth 99); fi

    "$VERILATOR" --cc --exe --build -j "$(nproc)" \
        "${trace_flags[@]}" \
        --top-module sim_top \
        --Mdir "$out/obj_dir" \
        -O3 -CFLAGS "-O2 -std=c++17" \
        -Wno-fatal \
        -Wno-WIDTHEXPAND -Wno-WIDTHTRUNC -Wno-UNOPTFLAT \
        -Wno-CASEINCOMPLETE -Wno-LATCH -Wno-MULTIDRIVEN \
        "${incs[@]}" \
        "${files[@]}" \
        "$ENV_DIR/sim/tb_sim_top.cpp" \
        -o "$out/Vsim_top" \
        > "$ENV_DIR/logs/verilate_$v.log" 2>&1 \
        || { echo "!! $v: verilation FAILED (see logs/verilate_$v.log)" >&2
             failed+=("$v"); continue; }

    echo "    $out/Vsim_top"
done

if [ ${#failed[@]} -gt 0 ]; then
    echo
    echo "did not elaborate: ${failed[*]}" >&2
fi
