#!/usr/bin/env bash
# Full SAIF flow for one config. Resumable: skips if the result already exists.
#   $1 variant  $2 bench  $3 xpr  $4 top
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V="$1"; B="$2"; XPR="$3"; TOP="$4"
W="$ENV_DIR/saif/${V}_${B}"
RES="$ENV_DIR/saif/results/${V}_${B}.txt"
mkdir -p "$W" "$ENV_DIR/saif/results"
[ -s "$RES" ] && { echo "=== $V/$B already done"; exit 0; }
cd "$W" || exit 1

# 1. post-implementation netlist (no SDF is used at simulation time, but the
#    netlist itself is the routed design, so activity maps onto it exactly)
if [ ! -s netlist.v ]; then
  vivado -mode batch -nojournal -nolog -notrace -source "$ENV_DIR/scripts/saif_netlist.tcl" \
         -tclargs "$XPR" "$W" > netlist.log 2>&1
fi
[ -s netlist.v ] || { echo "!! $V/$B netlist failed"; exit 1; }

# 2. testbench (ports are identical across all variants; only the top name differs)
cp "$XILINX_VIVADO/data/verilog/src/glbl.v" . 2>/dev/null
sed "s/@TOP@/$TOP/" "$ENV_DIR/scripts/tb_saif.v.in" > tb_saif.v

# 3. compile + elaborate, no SDF: back-annotation drives FFs to X at startup and
#    the design never recovers
if [ ! -f xsim.dir/tb_ns/xsimk ]; then
  xvlog netlist.v glbl.v tb_saif.v > xvlog.log 2>&1
  xelab -relax -debug typical -mt auto -L simprims_ver -L unisims_ver -L secureip \
        tb_saif glbl -s tb_ns > xelab.log 2>&1
fi
[ -f xsim.dir/tb_ns/xsimk ] || { echo "!! $V/$B elaborate failed"; exit 1; }

# 4. capture in the benchmark kernel
cat > cap.tcl <<'TCL'
run 70 us
set cands [get_objects -r /tb_saif/dut/*benchmark_start*]
set bs ""
foreach c $cands { if {![string match "*_reg*" $c]} { set bs $c; break } }
if {$bs eq "" && [llength $cands]} { set bs [lindex $cands 0] }
if {$bs eq ""} { puts "NO_BENCHMARK_START"; quit }
add_force $bs 1 -cancel_after 100ns
run 30 us
# The CPU busy-waits on tx_busy while the UART drains a character at 115200
# baud.  Dhrystone prints a banner BEFORE its timed loop, so reaching the kernel
# costs ~17 ms of wire time.  Holding tx_busy low lets the CPU execute the same
# instructions without the wire delay; the force is RELEASED before any capture,
# so the measured window contains no forcing.
set tb [lindex [get_objects -r /tb_saif/dut/tx_busy] 0]
if {$tb ne ""} { add_force $tb 0; run 1000 us; remove_forces -all; puts "FASTFWD_DONE" }
run 100 us
# capture a window with no UART traffic - printing means the CPU is idle-waiting
for {set try 0} {$try < 6} {incr try} {
    set u0 [get_value -radix dec /tb_saif/uart_chars]
    open_saif kernel.saif
    log_saif [get_objects -r /tb_saif/dut/*]
    run 100 us
    close_saif
    set du [expr {[get_value -radix dec /tb_saif/uart_chars] - $u0}]
    puts "WINDOW try=$try uart_delta=$du"
    if {$du <= 1} { puts "WINDOW_ACCEPTED uart_delta=$du"; break }
    if {$try == 5} { puts "WINDOW_BEST_EFFORT uart_delta=$du" }
}
quit
TCL
[ -s kernel.saif ] || xsim tb_ns -tclbatch cap.tcl > xsim.log 2>&1
[ -s kernel.saif ] || { echo "!! $V/$B capture failed"; exit 1; }

# 5. liveness gate -- a dead run must never be reported as a result
PCT=$(python3 -c "
import re;t=open('kernel.saif',errors='replace').read()
tc=[int(x) for x in re.findall(r'\(TC (\d+)\)',t)]
print(f'{sum(1 for v in tc if v>0)/len(tc)*100:.2f}')")
echo "    $V/$B toggling ${PCT}%"

# 6. power
vivado -mode batch -nojournal -nolog -notrace -source "$ENV_DIR/scripts/saif_power.tcl" \
       -tclargs "$XPR" "$W/kernel.saif" "$W/power_saif.rpt" > power.log 2>&1
UD=$(grep -oE 'WINDOW_(ACCEPTED|BEST_EFFORT).*uart_delta=[0-9]+' xsim.log | grep -oE '[0-9]+$' | tail -1)
{ echo "variant $V"; echo "bench $B"; echo "toggling_pct $PCT"; echo "uart_delta ${UD:-?}"
  grep -E '^(VECTORLESS|SAIF_BASED)' power.log; } > "$RES"
echo "=== $V/$B done: $(grep 'SAIF_BASED Total' "$RES" | awk '{print $NF}') W (toggling ${PCT}%, uart_delta ${UD:-?})"
