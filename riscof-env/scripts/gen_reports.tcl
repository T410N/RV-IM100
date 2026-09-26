# Open each implemented design and write utilization / power / timing reports
# into one uniform place.
#
# The runs themselves emit different report sets depending on each project's
# report strategy -- one project wrote only four .rpt files -- so the numbers
# are regenerated here instead, guaranteeing the same reports exist for every
# variant and that they all come from the routed design.

set xpr [lindex $argv 0]
set out [lindex $argv 1]

open_project -quiet $xpr
if {[get_property IS_READONLY [current_project]]} {
    puts "READONLY_SKIP $xpr"
    close_project
    exit 0
}

set impl [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]
if {[get_property PROGRESS [get_runs $impl]] ne "100%"} {
    puts "INCOMPLETE $xpr [get_property PROGRESS [get_runs $impl]]"
    close_project
    exit 0
}

file mkdir $out
open_run $impl

report_utilization      -file $out/utilization.rpt
report_power            -file $out/power.rpt
report_timing_summary   -file $out/timing.rpt

# The SoC clock is the one the core actually runs on: the clock-wizard output
# where the SoC instantiates one, otherwise the board clock driving everything.
set fh [open $out/clocks.txt w]
foreach c [get_clocks] {
    set per  [get_property PERIOD $c]
    set src  [get_property IS_GENERATED $c]
    set n    [llength [all_fanout -flat -endpoints_only [get_pins -quiet -of_objects $c]]]
    puts $fh "CLOCK $c period=$per generated=$src"
}
close $fh

puts "REPORTS_OK $xpr"
close_project
