#!/usr/bin/env bash
# Build the .mem images needed by the processors that either violate timing
# (need a slower image) or leave >1 MHz of headroom (can use a faster one).
#
# Frequency is compiled into each benchmark's timing loop -- Dhrystone via
# -DHZ, CoreMark via -DEE_TICKS_PER_SEC -- so an image is specific to one clock.
set -uo pipefail
BM="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../benchmarks" && pwd)"
OUT="$BM"
export PATH=/opt/riscv/bin:$PATH

build() {                       # dir target arch outname freq_mhz [extra make vars...]
    local dir="$1" target="$2" out="$3" mhz="$4"; shift 4
    local hz; hz=$(python3 -c "print(int(float('$mhz')*1e6))")
    ( cd "$BM/$dir" && make clean >/dev/null 2>&1 \
      && make CPU_FREQ_HZ="$hz" "$@" verilog >/dev/null 2>&1 \
      && cp "$target.mem" "$BM/$out" ) \
      && printf "  %-34s %8s MHz  %s lines\n" "$out" "$mhz" "$(wc -l < "$BM/$out")" \
      || printf "  %-34s %8s MHz  BUILD FAILED\n" "$out" "$mhz"
}

echo "=== RV64IM Dhrystone ==="
for f in 37 44 56 92 101; do
    build Dhrystone2.1_baremetal_RV64 dhrystone "dhrystones/dhrystone_RV64IM_${f}MHz.mem" "$f"
done
echo "=== RV64IM CoreMark ==="
for f in 48 92; do
    build Coremark_baremetal coremark "coremarks/coremark_RV64IM_${f}MHz.mem" "$f"
done
echo "=== RV64I CoreMark (I-only core: no M extension) ==="
build Coremark_baremetal coremark "coremarks/coremark_RV64I_38MHz.mem" 38 \
      ARCH_FLAGS="-march=rv64i_zicsr -mabi=lp64" \
      ASFLAGS="-march=rv64i_zicsr -mabi=lp64 -Wa,-march=rv64i_zicsr" \
      FLAGS_STR='"-O2 -march=rv64i_zicsr -mabi=lp64 -fno-common -funroll-loops"'
echo "=== RV32IM Dhrystone ==="
for f in 51 52 121; do
    build dhrystone_rv32i_port dhrystone "dhrystones/dhrystone_RV32IM_${f}MHz.mem" "$f"
done
echo "=== RV32IM CoreMark ==="
for f in 57 121; do
    build coremark_rv32i_port coremark "coremarks/coremark_RV32IM_${f}MHz.mem" "$f"
done
