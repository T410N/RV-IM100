# Post-synthesis power for one cores/ project.
# Vivado supports report_power on a synthesized (unplaced) netlist; it is less
# accurate than post-route because routing capacitance is estimated, so these
# are comparable to each other but not to the SoC post-route numbers.
set xpr [lindex $argv 0]
set out [lindex $argv 1]
open_project -quiet $xpr
if {[get_property IS_READONLY [current_project]]} { puts "READONLY_SKIP $xpr"; close_project; exit 0 }
set synth [lindex [get_runs -filter {IS_SYNTHESIS}] 0]
if {[get_property PROGRESS [get_runs $synth]] ne "100%"} { puts "NOT_SYNTHESIZED $xpr"; close_project; exit 0 }
file mkdir $out
open_run $synth -name pw
report_power -file $out/power.rpt
puts "POWER_OK $xpr"
close_project
