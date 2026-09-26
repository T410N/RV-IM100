# Re-run synthesis and implementation for one project, preserving its strategies.
#
# The RTL changed underneath these projects, so the existing runs are stale.
# reset_run clears the results but leaves STRATEGY, constraints and all other
# run properties untouched -- nothing here sets a strategy.

set xpr [lindex $argv 0]

open_project $xpr

# A project already open elsewhere (e.g. a Vivado GUI session) opens read-only,
# and reset_run would fail with a confusing error.  Say so and move on.
if {[get_property IS_READONLY [current_project]]} {
    puts "READONLY_SKIP $xpr -- project is open in another Vivado session"
    close_project
    exit 0
}

set synth [lindex [get_runs -filter {IS_SYNTHESIS}] 0]
set impl  [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]

puts "PROJECT   [current_project]"
puts "PART      [get_property PART [current_project]]"
puts "SYNTH_RUN $synth  strategy=[get_property STRATEGY [get_runs $synth]]"
puts "IMPL_RUN  $impl   strategy=[get_property STRATEGY [get_runs $impl]]"

reset_run $impl
reset_run $synth

launch_runs $impl -jobs 8
wait_on_run $impl

set sstat [get_property STATUS   [get_runs $synth]]
set istat [get_property STATUS   [get_runs $impl]]
set iprog [get_property PROGRESS [get_runs $impl]]
puts "SYNTH_STATUS $sstat"
puts "IMPL_STATUS  $istat"
puts "IMPL_PROGRESS $iprog"

if {$iprog eq "100%"} {
    open_run $impl
    set wns [get_property SLACK [get_timing_paths -delay_type max -max_paths 1 -nworst 1]]
    set whs [get_property SLACK [get_timing_paths -delay_type min -max_paths 1 -nworst 1]]
    # Fmax implied by the worst setup path against the constrained clock
    set clks [get_clocks]
    set per "n/a"
    if {[llength $clks] > 0} {
        set per [get_property PERIOD [lindex $clks 0]]
    }
    set luts [get_property STATS.LUT [get_runs $impl]]
    set ffs  [get_property STATS.FF  [get_runs $impl]]
    puts "TIMING wns=$wns whs=$whs period=$per luts=$luts ffs=$ffs"
    if {$per ne "n/a" && $wns ne ""} {
        set fmax [expr {1000.0 / ($per - $wns)}]
        puts "FMAX_MHZ [format %.2f $fmax]"
    }
}

close_project
puts "DONE $xpr"
