#!/usr/bin/env bash
# Build Embench benchmarks as FPGA images (.mem), one per benchmark.
#
# Differs from build_embench.sh in three ways:
#   - links main_fpga.c and uart_fpga.c instead of upstream main.c, so the
#     result leaves the chip over UART instead of being peeked out of memory
#   - enforces the REAL instruction memory size (32 KB).  link.ld declares CODE
#     as 2 MB, so a benchmark that overflows the ROM still links; xgboost does
#     exactly that at 39 KB and must be caught here rather than on the board.
#   - emits .mem (one hex word per line) for $readmemh
#
# No frequency argument: the UART divisor is in the RTL, and Embench times with
# mcycle, so unlike CoreMark and Dhrystone the image is clock-independent.
set -u
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EMB="${EMBENCH_SRC:-/home/khwl/embench-iot}"
ISA="${1:-rv64im}"
OUT="$ENV_DIR/build/embench_fpga/$ISA"
IMEM_BYTES=32768
PATH=/opt/riscv/bin:$PATH
PREFIX=riscv64-unknown-elf-
declare -A ABI=( [rv32i]=ilp32 [rv32im]=ilp32 [rv64i]=lp64 [rv64im]=lp64 )
mkdir -p "$OUT"

printf "%-16s %9s %9s %9s  %s\n" benchmark text bss "img B" status
ok=0; skip=0; fail=0
for d in "$EMB"/src/*/; do
  b=$(basename "$d")
  elf="$OUT/$b.elf"
  if ! ${PREFIX}gcc -march=${ISA}_zicsr -mabi=${ABI[$ISA]} -Os -static -mcmodel=medany -std=gnu11 \
       -nostartfiles --specs=nosys.specs \
       -ffunction-sections -fdata-sections -Wl,--gc-sections \
       -I"$ENV_DIR/embench-env" -I"$EMB/support" -I"$d" \
       -DCPU_MHZ=1 -DWARMUP_HEAT=1 -DGLOBAL_SCALE_FACTOR=1 -DBENCH_NAME="\"$b\"" \
       -T "$ENV_DIR/embench-env/link.ld" \
       "$ENV_DIR/embench-env/crt_embench.S" "$ENV_DIR/embench-env/boardsupport.c" \
       "$ENV_DIR/embench-env/uart_fpga.c" "$ENV_DIR/embench-env/main_fpga.c" \
       "$EMB/support/beebsc.c" "$d"/*.c \
       -lm -o "$elf" > "$OUT/$b.log" 2>&1
  then
    printf "%-16s %9s %9s %9s  BUILD FAILED\n" "$b" - - -
    fail=$((fail+1)); rm -f "$elf"; continue
  fi
  read -r text bss <<<$(${PREFIX}size -A "$elf" | awk '
    /^\.text/{t+=$2} /^\.rodata/{t+=$2} /^\.data/{t+=$2}
    /^\.bss/{b+=$2} /^\.sbss/{b+=$2} END{print t+0, b+0}')
  ${PREFIX}objcopy -O binary -j .text.init -j .text -j .rodata -j .data "$elf" "$elf.bin"
  sz=$(stat -c%s "$elf.bin")
  if [ "$sz" -gt "$IMEM_BYTES" ]; then
    printf "%-16s %9s %9s %9s  SKIP: image %d B exceeds %d B ROM\n" "$b" "$text" "$bss" "$sz" "$sz" "$IMEM_BYTES"
    rm -f "$elf.bin" "$elf"; skip=$((skip+1)); continue
  fi
  python3 - "$elf.bin" "$OUT/$b.mem" <<'PY'
import sys
b=open(sys.argv[1],'rb').read(); b+=b'\x00'*((-len(b))%4)
open(sys.argv[2],'w').write(''.join('%08x\n'%int.from_bytes(b[i:i+4],'little')
                                    for i in range(0,len(b),4)))
PY
  rm -f "$elf.bin"
  printf "%-16s %9s %9s %9s  ok\n" "$b" "$text" "$bss" "$sz"
  ok=$((ok+1))
done
echo
echo "$ISA: $ok built, $skip skipped (too large), $fail build failures  -> $OUT"
