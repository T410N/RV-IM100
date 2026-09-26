# Synthesize one cores/ project and report post-synthesis area and timing.
# Strategies are left exactly as the project defines them.
set xpr [lindex $argv 0]
set out [lindex $argv 1]

open_project -quiet $xpr
if {[get_property IS_READONLY [current_project]]} {
    puts "READONLY_SKIP $xpr"; close_project; exit 0
}
set synth [lindex [get_runs -filter {IS_SYNTHESIS}] 0]
puts "PROJECT [current_project]  TOP [get_property TOP [current_fileset]]"
puts "SYNTH_STRATEGY [get_property STRATEGY [get_runs $synth]]"

reset_run $synth
launch_runs $synth -jobs 8
wait_on_run $synth

set prog [get_property PROGRESS [get_runs $synth]]
puts "SYNTH_PROGRESS $prog"
if {$prog ne "100%"} { close_project; exit 0 }

file mkdir $out
open_run $synth -name synth_view
report_utilization    -file $out/utilization.rpt
report_timing_summary -file $out/timing.rpt
set fh [open $out/clocks.txt w]
foreach c [get_clocks] { puts $fh "CLOCK $c period=[get_property PERIOD $c] generated=[get_property IS_GENERATED $c]" }
close $fh
puts "SYNTH_OK $xpr"
close_project
