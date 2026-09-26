# Core-only out-of-context synthesis: area, per-clock timing, and power for the
# memory-externalised CPU top.  One pass, so the netlist is opened only once.
#
# Timing is reported PER CAPTURE CLOCK, never by dividing the global worst slack
# by [lindex [get_clocks] 0] -- that is the bug that made every SoC Fmax wrong.
# These are POST-SYNTHESIS numbers: routing is estimated, so they are comparable
# to each other but not to the SoC post-route results.
set xpr [lindex $argv 0]
open_project -quiet $xpr
if {[get_property IS_READONLY [current_project]]} {
    puts "READONLY_SKIP $xpr"; close_project; return
}
set synth [lindex [get_runs -filter {IS_SYNTHESIS}] 0]
puts "PROJECT [current_project]"
puts "TOP     [get_property TOP [current_fileset]]"
puts "STRATEGY [get_property STRATEGY [get_runs $synth]]"

reset_run $synth
launch_runs $synth -jobs 8
wait_on_run $synth
set prog [get_property PROGRESS [get_runs $synth]]
puts "SYNTH_PROGRESS $prog"
if {$prog ne "100%"} { close_project; return }

open_run $synth -name synth_view
foreach clk [lsort [get_clocks]] {
    set per [get_property PERIOD $clk]
    set p [get_timing_paths -delay_type max -to $clk -max_paths 1 -nworst 1]
    set s "none"
    if {[llength $p] > 0} { set s [get_property SLACK $p] }
    set fm "n/a"
    if {$s ne "none" && $s ne "" && $per > 0} {
        set fm [format %.3f [expr {1000.0 / ($per - $s)}]]
    }
    puts "CLOCK name=$clk period=$per mhz=[format %.3f [expr {1000.0/$per}]] wns=$s fmax=$fm"
}

set ut [report_utilization -return_string]
foreach line [split $ut "\n"] {
    # post-synthesis reports print "Slice LUTs*" (asterisk = includes LUTRAM)
    foreach {tag pat} {LUT "Slice LUTs\\*?" LUTLOGIC "LUT as Logic" LUTRAM "LUT as Memory" \
                       FF "Slice Registers" BRAM "Block RAM Tile" DSP "DSPs"} {
        if {[regexp "\\|\\s+$pat\\s*\\|\\s+(\[0-9\]+)\\s+\\|" $line -> n]} { puts "UTIL_$tag $n" }
    }
}
set pw [report_power -return_string]
foreach line [split $pw "\n"] {
    if {[regexp {^\s*\|\s*([A-Za-z0-9 /_-]+?)\s*\|\s*([0-9]+\.[0-9]+)\s*\|} $line -> cat val]} {
        puts "PWR [string trim $cat] = $val"
    }
}
close_project
puts "DONE"
