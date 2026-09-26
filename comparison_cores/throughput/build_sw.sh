#!/usr/bin/env bash
# Build the harness Dhrystone and CoreMark images, rv32im and rv32i.
# Same sources, toolchain and flags as the RV-IM100 FPGA images
# (riscof-env/scripts/build_image_exact.sh); only the BSP timer and the crt0
# halt differ.  The nominal clocks set the software's own report scale only:
# every published figure is computed from harness cycle counts.
set -euo pipefail
T="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH=/opt/riscv/bin:$HOME/riscv32i-elf/bin:$PATH
DHRY_HZ=10000000       # Dhrystone rejects runs under 2*HZ ticks; 10 MHz keeps every core above it
CM_HZ=10000000         # CoreMark reports integer seconds; 10 MHz keeps every run over its 10 s check
CM_ITERS=300          # enough for the fastest core (VexRiscv) to clear CoreMark's 10 s check
mkdir -p "$T/build"
for isa in rv32im rv32i; do
  a="-march=${isa}_zicsr -mabi=ilp32"
  ( cd "$T/sw/dhrystone_rv32i_port" && make clean >/dev/null 2>&1
    make CPU_FREQ_HZ=$DHRY_HZ ARCH_FLAGS="$a" ASFLAGS="$a -Wa,-march=${isa}_zicsr" verilog >/dev/null
    cp dhrystone.mem "$T/build/dhrystone_$isa.mem"; cp dhrystone.elf "$T/build/dhrystone_$isa.elf" )
  ( cd "$T/sw/coremark_rv32i_port" && make clean >/dev/null 2>&1
    make CPU_FREQ_HZ=$CM_HZ ITERATIONS=$CM_ITERS ARCH_FLAGS="$a" ASFLAGS="$a -Wa,-march=${isa}_zicsr" \
         FLAGS_STR="\"-O2 $a -fno-common -funroll-loops\"" verilog >/dev/null
    cp coremark.mem "$T/build/coremark_$isa.mem"; cp coremark.elf "$T/build/coremark_$isa.elf" )
done
for f in "$T"/build/*.elf; do
  n=$(riscv64-unknown-elf-objdump -d "$f" | grep -cE '\scsrr?[sc]?i?\s' || true)
  m=$(riscv64-unknown-elf-objdump -d "$f" | grep -cE '\s(mul|mulh|mulhu|mulhsu|div|divu|rem|remu)\s' || true)
  printf "  %-22s %6s words   csr insns: %s   M insns: %s\n" "$(basename "$f" .elf)" \
    "$(wc -l < "${f%.elf}.mem")" "$n" "$m"
done
