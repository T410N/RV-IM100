#!/usr/bin/env bash
# Run Dhrystone and CoreMark on every comparison-core configuration.
set -uo pipefail
T="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; mkdir -p "$T/out"
job() {  # cfg bench
  local isa=rv32im; [ "$1" = rvcorep ] && isa=rv32i
  "$T/build/sim_$1/sim" +IMAGE="$T/build/$2_$isa.mem" +MAX_CYCLES=3000000000 \
    > "$T/out/$1_$2.log" 2>&1
  echo "done $1 $2 rc=$?"
}
for c in picorv32_la picorv32_nola vexriscv rvcorep; do
  for b in dhrystone coremark; do job $c $b & done
done
wait
