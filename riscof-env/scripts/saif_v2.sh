#!/usr/bin/env bash
# SAIF capture, v2 -- on the FINAL implementation, with window provenance.
#
# Differences from saif_one.sh, and why:
#   * the netlist is written from the project's current routed run, i.e. the
#     implementation whose utilisation/timing is reported (v1 captures were
#     taken on 09-12..09-14 netlists that were later re-implemented);
#   * the PC is sampled every 10 us across the capture window and logged, so
#     the window can be placed in the program with the ELF's symbol table --
#     a window in a spin loop is detectable, not just a window with UART traffic;
#   * read_saif coverage ("Design nets matched") is extracted and reported;
#   * report_power -hier is kept so a core-only figure (no PLL, no I/O) can be
#     derived.
# Output goes to saif_v2/<variant>_<bench>/; the v1 captures are left untouched.
#
#   $1 variant  $2 bench  $3 xpr (relative to RV-IM100_RTL/project_files/)  $4 top  [$5 window_us, default 100]
set -uo pipefail
ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; ROOT="$ENV_DIR/.."
source /tools/Xilinx/2025.2/Vivado/settings64.sh
V="$1"; B="$2"; XPR="$ROOT/RV-IM100_RTL/project_files/$3"; TOP="$4"; WIN="${5:-100}"
W="$ENV_DIR/saif_v2/${V}_${B}"
mkdir -p "$W"; cd "$W" || exit 1
rm -f "$(dirname "$XPR")"/*.lock

if [ ! -s netlist.v ]; then
  vivado -mode batch -nojournal -nolog -notrace -source "$ENV_DIR/scripts/saif_netlist.tcl" \
         -tclargs "$XPR" "$W" > netlist.log 2>&1
fi
[ -s netlist.v ] || { echo "!! $V/$B netlist failed"; exit 1; }

cp "$XILINX_VIVADO/data/verilog/src/glbl.v" . 2>/dev/null
sed "s/@TOP@/$TOP/" "$ENV_DIR/scripts/tb_saif.v.in" > tb_saif.v
if [ ! -f xsim.dir/tb_ns/xsimk ]; then
  xvlog netlist.v glbl.v tb_saif.v > xvlog.log 2>&1
  xelab -relax -debug typical -mt auto -L simprims_ver -L unisims_ver -L secureip \
        tb_saif glbl -s tb_ns > xelab.log 2>&1
fi
[ -f xsim.dir/tb_ns/xsimk ] || { echo "!! $V/$B elaborate failed"; exit 1; }

cat > cap.tcl <<TCL
run 70 us
set cands [get_objects -r /tb_saif/dut/*benchmark_start*]
set bs ""
foreach c \$cands { if {![string match "*_reg*" \$c]} { set bs \$c; break } }
if {\$bs eq "" && [llength \$cands]} { set bs [lindex \$cands 0] }
if {\$bs eq ""} { puts "NO_BENCHMARK_START"; quit }
add_force \$bs 1 -cancel_after 100ns
run 30 us
set tb [lindex [get_objects -r /tb_saif/dut/tx_busy] 0]
if {\$tb ne ""} { add_force \$tb 0; run 1000 us; remove_forces -all; puts "FASTFWD_DONE" }
run 100 us
set pcq [lindex [get_objects -r /tb_saif/dut/*/program_counter/Q] 0]
puts "PCOBJ \$pcq"
set steps [expr {$WIN / 10}]
for {set try 0} {\$try < 6} {incr try} {
    set u0 [get_value -radix dec /tb_saif/uart_chars]
    open_saif kernel.saif
    log_saif [get_objects -r /tb_saif/dut/*]
    for {set s 0} {\$s < \$steps} {incr s} {
        puts "PC t=[current_time] pc=[get_value -radix hex \$pcq]"
        run 10 us
    }
    puts "PC t=[current_time] pc=[get_value -radix hex \$pcq]"
    close_saif
    set du [expr {[get_value -radix dec /tb_saif/uart_chars] - \$u0}]
    puts "WINDOW try=\$try uart_delta=\$du len=${WIN}us"
    if {\$du <= 1} { puts "WINDOW_ACCEPTED uart_delta=\$du"; break }
    if {\$try == 5} { puts "WINDOW_BEST_EFFORT uart_delta=\$du" }
}
quit
TCL
[ -s kernel.saif ] || xsim tb_ns -tclbatch cap.tcl > xsim.log 2>&1
[ -s kernel.saif ] || { echo "!! $V/$B capture failed"; exit 1; }

cat > power.tcl <<'TCL'
set xpr  [lindex $argv 0]
set saif [lindex $argv 1]
open_project -quiet $xpr
open_run [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]
report_power -file power_vectorless.rpt
read_saif -strip_path tb_saif/dut $saif
report_power -file power_saif.rpt
report_power -hier all -file power_saif_hier.rpt
puts "SAIF_POWER_OK"
close_project
TCL
vivado -mode batch -nojournal -nolog -notrace -source power.tcl -tclargs "$XPR" "$W/kernel.saif" > power.log 2>&1
grep -q SAIF_POWER_OK power.log || { echo "!! $V/$B power failed"; exit 1; }
echo "=== $V/$B $(grep -m1 'Design nets matched' power.log) $(grep -m1 'Total On-Chip' power_saif.rpt)"
