#!/usr/bin/env bash
# Build every Embench-IoT benchmark for each ISA the family implements.
#
# -std=gnu11 is explicit: GCC 15 defaults to C23, where `bool` is a keyword,
# and wikisort does `typedef uint8_t bool`.  Fixing it by the standard rather
# than by patching the benchmark keeps the sources upstream-identical.
#
# newlib is linked (-nostartfiles, not -nostdlib) but its startup is not: the
# benchmarks need memcpy/memcmp/strchr and, on the I-only targets, libgcc's
# software multiply and divide.  --specs=nosys.specs supplies the syscall
# stubs newlib references; nothing here actually calls them.
#
# Benchmarks that do not fit the 32 KB data RAM are reported and skipped
# rather than being built against a larger memory: running some variants with
# a different memory size would invalidate the comparison.
set -u
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EMB="${EMBENCH_SRC:-/home/khwl/embench-iot}"
OUT="$ENV_DIR/build/embench"
PATH=/opt/riscv/bin:$PATH
PREFIX=riscv64-unknown-elf-

mkdir -p "$OUT"
declare -A ABI=( [rv32i]=ilp32 [rv32im]=ilp32 [rv64i]=lp64 [rv64im]=lp64 )

for isa in rv32i rv32im rv64i rv64im; do
  mkdir -p "$OUT/$isa"
  ok=0; fail=0; failed=""
  for d in "$EMB"/src/*/; do
    b=$(basename "$d")
    elf="$OUT/$isa/$b.elf"
    log="$OUT/$isa/$b.log"
    if ${PREFIX}gcc -march=${isa}_zicsr -mabi=${ABI[$isa]} -Os -static -mcmodel=medany -std=gnu11 \
         -nostartfiles --specs=nosys.specs \
         -ffunction-sections -fdata-sections -Wl,--gc-sections \
         -I"$ENV_DIR/embench-env" -I"$EMB/support" -I"$d" \
         -DCPU_MHZ=1 -DWARMUP_HEAT=1 -DGLOBAL_SCALE_FACTOR=1 \
         -T "$ENV_DIR/embench-env/link.ld" \
         "$ENV_DIR/embench-env/crt_embench.S" "$ENV_DIR/embench-env/boardsupport.c" \
         "$EMB/support/main.c" "$EMB/support/beebsc.c" "$d"/*.c \
         -lm -o "$elf" > "$log" 2>&1
    then
      ${PREFIX}objcopy -O binary -j .text.init -j .text -j .rodata -j .data "$elf" "$elf.bin"
      python3 - "$elf.bin" "$OUT/$isa/$b.hex" <<'PY'
import sys
b=open(sys.argv[1],'rb').read(); b+=b'\x00'*((-len(b))%4)
open(sys.argv[2],'w').write(''.join('%08x\n'%int.from_bytes(b[i:i+4],'little')
                                    for i in range(0,len(b),4)))
PY
      rm -f "$elf.bin"; ok=$((ok+1))
    else
      fail=$((fail+1)); failed="$failed $b"
      rm -f "$elf"
    fi
  done
  printf "  %-8s built %2d  failed %2d %s\n" "$isa" "$ok" "$fail" "$failed"
done
