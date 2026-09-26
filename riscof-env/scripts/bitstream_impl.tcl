# Produce one bitstream.
#   argv: <xpr> <freq MHz> <mem path> <out .bit> <mode: reuse|reimpl>
#
# reuse  - the project already holds this image and is routed; only the
#          write_bitstream step is run.
# reimpl - the image/clock changed, so synthesis and implementation are reset
#          and the whole flow runs through to the bitstream.
set xpr  [lindex $argv 0]
set freq [lindex $argv 1]
set mem  [lindex $argv 2]
set bit  [lindex $argv 3]
set mode [lindex $argv 4]

open_project -quiet $xpr
if {[get_property IS_READONLY [current_project]]} { puts "READONLY_SKIP $xpr"; close_project; return }
puts "PROJECT [current_project]  MODE $mode"

set synth [lindex [get_runs -filter {IS_SYNTHESIS}] 0]
set impl  [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]

if {$mode eq "reimpl"} {
    if {[llength [get_files -quiet [file tail $mem]]] == 0} {
        add_files -quiet -norecurse -fileset sources_1 $mem
        puts "MEM_ADDED [file tail $mem]"
    }
    set ip [get_ips -quiet clk_wiz_0]
    if {[llength $ip]} {
        set cur [get_property CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $ip]
        if {abs($cur - $freq) > 0.0005} {
            set_property -dict [list CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $freq] $ip
            generate_target all $ip
            puts "PLL_RETUNED $cur -> $freq"
        } else { puts "PLL_UNCHANGED $freq" }
        # the IP synth run must be reset whenever the .xci changes, even at 100%,
        # or Vivado reuses the old IP netlist and the clock silently stays put
        foreach r [get_runs -quiet ${ip}_synth_1] {
            puts "IP_SYNTH_RESET $r"
            reset_run $r
        }
    } else { puts "NO_PLL fixed-by-xdc $freq" }
    foreach r [get_runs -quiet *clk_wiz*] {
        if {[get_property PROGRESS [get_runs $r]] ne "100%"} { reset_run $r }
    }
    reset_run $impl
    reset_run $synth
}

set nproc [exec nproc]
catch {set_param general.maxThreads $nproc}
# never reuse a previous placement: bitstreams must match the reported numbers
set_property AUTO_INCREMENTAL_CHECKPOINT 0 [get_runs $impl]
launch_runs $impl -to_step write_bitstream -jobs $nproc
wait_on_run $impl

set prog [get_property PROGRESS [get_runs $impl]]
puts "IMPL_PROGRESS $prog"
if {$prog ne "100%"} { close_project; return }

open_run $impl
foreach clk [lsort [get_clocks]] {
    set p [get_timing_paths -delay_type max -to $clk -max_paths 1 -nworst 1]
    if {[llength $p] > 0} {
        set per [get_property PERIOD $clk]
        set s [get_property SLACK $p]
        puts "CLOCK name=$clk mhz=[format %.3f [expr {1000.0/$per}]] wns=$s\
 fmax=[format %.3f [expr {1000.0/($per-$s)}]]"
    }
}
set src [glob -nocomplain [file join [get_property DIRECTORY [get_runs $impl]] *.bit]]
if {[llength $src] == 0} { puts "NO_BITSTREAM_PRODUCED"; close_project; return }
file mkdir [file dirname $bit]
file copy -force [lindex $src 0] $bit
puts "BITSTREAM_OK [file tail $bit] ([file size $bit] bytes)"
close_project
