# Re-open an already-implemented run and report CORRECT per-clock timing,
# full utilization, and power.  Read-only: no re-implementation.
#
# The old reimpl.tcl computed Fmax as 1000/(period-wns) using the GLOBAL worst
# slack and [lindex [get_clocks] 0] -- which is the 100 MHz board clock on every
# project.  The CPU runs on the clock-wizard output (38-130 MHz, per variant),
# so that Fmax was meaningless.  Here each clock is reported with the worst
# setup slack of the paths that END in its own domain.
set xpr [lindex $argv 0]
open_project $xpr
set impl [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]
puts "PROJECT [file rootname [file tail $xpr]]"
puts "DIR     [file tail [file dirname $xpr]]"
if {[get_property PROGRESS [get_runs $impl]] ne "100%"} {
    puts "NOT_IMPLEMENTED [get_property PROGRESS [get_runs $impl]]"
    close_project
    return
}
open_run $impl

foreach clk [lsort [get_clocks]] {
    set per [get_property PERIOD $clk]
    set p [get_timing_paths -delay_type max -to $clk -max_paths 1 -nworst 1]
    set s "none"
    if {[llength $p] > 0} { set s [get_property SLACK $p] }
    set h [get_timing_paths -delay_type min -to $clk -max_paths 1 -nworst 1]
    set hs "none"
    if {[llength $h] > 0} { set hs [get_property SLACK $h] }
    set fm "n/a"
    if {$s ne "none" && $s ne "" && $per > 0} {
        set fm [format %.3f [expr {1000.0 / ($per - $s)}]]
    }
    puts "CLOCK name=$clk period=$per mhz=[format %.3f [expr {1000.0/$per}]] wns=$s whs=$hs fmax=$fm"
}
set gp [get_timing_paths -delay_type max -max_paths 1 -nworst 1]
if {[llength $gp] > 0} {
    puts "GLOBAL_WNS [get_property SLACK $gp] to_clock=[get_property ENDPOINT_CLOCK $gp]"
}

set ut [report_utilization -return_string]
foreach line [split $ut "\n"] {
    foreach {tag pat} {LUT "Slice LUTs" LUTLOGIC "LUT as Logic" LUTRAM "LUT as Memory" \
                       FF "Slice Registers" BRAM "Block RAM Tile" DSP "DSPs" \
                       IO "Bonded IOB" MMCM "MMCME2_ADV" PLL "PLLE2_ADV"} {
        if {[regexp "\\|\\s+$pat\\s*\\|\\s+(\[0-9\]+)\\s+\\|" $line -> n]} { puts "UTIL_$tag $n" }
    }
}

# On-Chip Power Summary rows look like:  | Clocks | 0.014 | 3 | --- | --- |
set pw [report_power -return_string]
foreach line [split $pw "\n"] {
    if {[regexp {^\s*\|\s*([A-Za-z0-9 /_-]+?)\s*\|\s*([0-9]+\.[0-9]+)\s*\|} $line -> cat val]} {
        puts "PWR [string trim $cat] = $val"
    }
}
close_project
puts "DONE"
