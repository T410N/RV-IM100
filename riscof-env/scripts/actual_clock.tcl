# What frequency does the implemented design ACTUALLY generate?
#   argv: <xpr>
open_project -quiet [lindex $argv 0]
set impl [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]
open_run $impl
puts "PROJECT [get_property NAME [current_project]]"
# the MMCM/PLL primitives actually placed in the design
foreach c [get_cells -hier -filter {REF_NAME =~ MMCM* || REF_NAME =~ PLL*}] {
    set m [get_property CLKFBOUT_MULT_F $c]
    set d [get_property DIVCLK_DIVIDE $c]
    set o [get_property CLKOUT0_DIVIDE_F $c]
    set pin [get_property CLKIN1_PERIOD $c]
    if {$m eq "" || $d eq "" || $o eq ""} { continue }
    set fin [expr {1000.0/$pin}]
    puts [format "MMCM %s ref=%s M=%s D=%s O=%s fin=%.4f exact_out=%.6f MHz" \
          $c [get_property REF_NAME $c] $m $d $o $fin [expr {$fin*$m/($d*$o)}]]
}
# what timing analysis actually used
foreach clk [lsort [get_clocks]] {
    set per [get_property PERIOD $clk]
    set src [get_property SOURCE_PINS $clk]
    set paths [get_timing_paths -delay_type max -to $clk -max_paths 1 -nworst 1]
    set s "none"
    if {[llength $paths]} { set s [get_property SLACK [lindex $paths 0]] }
    puts [format "CONSTRAINT %s period=%s implied_mhz=%.6f wns=%s" $clk $per [expr {1000.0/$per}] $s]
}
puts "ACTUAL_CLOCK_OK"
close_project
