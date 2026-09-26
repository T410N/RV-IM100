# Retarget one SoC project to the opposite benchmark: set the clock-wizard
# output frequency, re-implement, and write the reports in the same session.
# Strategies are never touched.
set xpr  [lindex $argv 0]
set freq [lindex $argv 1]
set out  [lindex $argv 2]

open_project -quiet $xpr
if {[get_property IS_READONLY [current_project]]} { puts "READONLY_SKIP $xpr"; close_project; exit 0 }

set synth [lindex [get_runs -filter {IS_SYNTHESIS}] 0]
set impl  [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]
puts "PROJECT [current_project]"

# Retune the PLL only where the SoC has one; the 8-stage RV64 SoC drives the
# core straight off the board clock, constrained in the XDC.
set ip [get_ips -quiet clk_wiz_0]
if {[llength $ip]} {
    set cur [get_property CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $ip]
    puts "PLL_CURRENT $cur  PLL_TARGET $freq"
    if {abs($cur - $freq) > 0.0005} {
        set_property -dict [list CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $freq] $ip
        generate_target all $ip
        set iprun [get_runs -quiet ${ip}_synth_1]
        if {[llength $iprun]} { reset_run $iprun }
        puts "PLL_RETUNED $freq"
    } else { puts "PLL_UNCHANGED $freq" }
    # An IP out-of-context run left mid-flight by a killed/suspended session stays
    # marked in-progress, and launch_runs then waits on it forever.  Reset any IP
    # run that is not COMPLETE -- the PLL_UNCHANGED path above used to skip this,
    # which wedged RV64IM_7SP_BRAM_Opt for 6.5 h with zero CPU.
    foreach iprun [get_runs -quiet *_synth_1] {
        if {[get_property IS_SYNTHESIS [get_runs $iprun]] &&
            [string match "*clk_wiz*" $iprun] &&
            [get_property PROGRESS [get_runs $iprun]] ne "100%"} {
            puts "IP_RUN_RESET $iprun (was [get_property PROGRESS [get_runs $iprun]])"
            reset_run $iprun
        }
    }
} else { puts "NO_PLL fixed-by-xdc $freq" }

# 16-core machine: let synthesis/implementation use all of it.  Vivado caps
# general.maxThreads at 8 for some tasks and will warn if it clamps.
set nproc [exec nproc]
catch {set_param general.maxThreads $nproc} msg
puts "MAXTHREADS requested $nproc -> [get_param general.maxThreads]"
reset_run $impl
reset_run $synth
launch_runs $impl -jobs $nproc
wait_on_run $impl

set prog [get_property PROGRESS [get_runs $impl]]
puts "IMPL_PROGRESS $prog"
if {$prog ne "100%"} { close_project; exit 0 }

file mkdir $out
open_run $impl
report_utilization    -file $out/utilization.rpt
report_power          -file $out/power.rpt
report_timing_summary -file $out/timing.rpt
set fh [open $out/clocks.txt w]
foreach c [get_clocks] { puts $fh "CLOCK $c period=[get_property PERIOD $c] generated=[get_property IS_GENERATED $c]" }
close $fh
puts "SWAP_OK $xpr"
close_project
