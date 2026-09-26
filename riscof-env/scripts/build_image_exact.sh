#!/usr/bin/env bash
# Build one .mem image compiled for the PLL's EXACT output frequency.
#
# The clock frequency is compiled into the benchmark's timing loop (Dhrystone
# -DHZ, CoreMark -DEE_TICKS_PER_SEC), so an image is only valid for the clock it
# was built for.  The MMCM emits 100*M/(D*O) MHz, which is generally not an
# integer -- 25/3/7 gives 119.047619048 MHz, not 119 -- so the image must be
# built from that exact value or every reported throughput is biased.
#
#   $1 variant (e.g. RV32IM_8SP)   $2 coremark|dhrystone   $3 exact MHz
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BM="$ROOT/benchmarks"
export PATH=/opt/riscv/bin:$HOME/riscv32i-elf/bin:$PATH
variant="$1"; bench="$2"; mhz="$3"

case "$variant" in
  RV64*) width=64 ;;
  RV32*) width=32 ;;
  *) echo "!! unknown width for $variant"; exit 1 ;;
esac
# I-only cores must not be handed M-extension code
case "$variant" in
  RV64I_*) isa=rv64i;  abi=lp64;  isaname=RV64I  ;;
  RV64IM*) isa=rv64im; abi=lp64;  isaname=RV64IM ;;
  RV32I_*) isa=rv32i;  abi=ilp32; isaname=RV32I  ;;
  RV32IM*) isa=rv32im; abi=ilp32; isaname=RV32IM ;;
  *) echo "!! unknown ISA for $variant"; exit 1 ;;
esac
if [ "$width" = 64 ]; then
  [ "$bench" = coremark ] && dir=Coremark_baremetal || dir=Dhrystone2.1_baremetal_RV64
else
  [ "$bench" = coremark ] && dir=coremark_rv32i_port || dir=dhrystone_rv32i_port
fi
[ "$bench" = coremark ] && target=coremark || target=dhrystone
[ "$bench" = coremark ] && sub=coremarks   || sub=dhrystones

hz=$(python3 -c "print(int(round(float('$mhz')*1e6)))")
name=$(python3 -c "
m=float('$mhz'); s=f'{m:.6f}'.rstrip('0').rstrip('.')
print(f'${target}_${isaname}_{s}MHz.mem')")
out="$BM/$sub/$name"

( cd "$BM/$dir" && make clean >/dev/null 2>&1 \
  && make CPU_FREQ_HZ="$hz" \
       ARCH_FLAGS="-march=${isa}_zicsr -mabi=${abi}" \
       ASFLAGS="-march=${isa}_zicsr -mabi=${abi} -Wa,-march=${isa}_zicsr" \
       FLAGS_STR="\"-O2 -march=${isa}_zicsr -mabi=${abi} -fno-common -funroll-loops\"" \
       verilog >/dev/null 2>&1 \
  && cp "$target.mem" "$out" )
if [ -s "$out" ]; then
  printf "  BUILT %-44s %s Hz  %s words\n" "$name" "$hz" "$(wc -l < "$out")"
  echo "$out"
else
  printf "  FAILED %-43s %s Hz\n" "$name" "$hz"; exit 1
fi
