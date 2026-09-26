# Retarget one SoC project to a specific .mem image and clock, then re-implement.
#   argv: <xpr> <freq MHz> <mem path> <report dir>
# Strategies are never touched.
set xpr  [lindex $argv 0]
set freq [lindex $argv 1]
set mem  [lindex $argv 2]
set out  [lindex $argv 3]

open_project -quiet $xpr
if {[get_property IS_READONLY [current_project]]} { puts "READONLY_SKIP $xpr"; close_project; return }
puts "PROJECT [current_project]"

# the image must be a project source or $readmemh will not resolve it
if {[llength [get_files -quiet [file tail $mem]]] == 0} {
    add_files -quiet -norecurse -fileset sources_1 $mem
    puts "MEM_ADDED [file tail $mem]"
} else {
    puts "MEM_PRESENT [file tail $mem]"
}

set synth [lindex [get_runs -filter {IS_SYNTHESIS}] 0]
set impl  [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]

set ip [get_ips -quiet clk_wiz_0]
if {[llength $ip]} {
    set cur [get_property CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $ip]
    if {abs($cur - $freq) > 0.0005} {
        set_property -dict [list CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $freq] $ip
        generate_target all $ip
        puts "PLL_RETUNED $cur -> $freq"
    } else { puts "PLL_UNCHANGED $freq" }
    # The IP's SYNTHESIS run must be reset whenever the .xci changes, even if it
    # is already at 100%: otherwise Vivado reuses the previously synthesized IP
    # netlist and the design keeps the OLD clock while the .xci reads the new one.
    foreach r [get_runs -quiet ${ip}_synth_1] {
        puts "IP_SYNTH_RESET $r (was [get_property PROGRESS [get_runs $r]])"
        reset_run $r
    }
} else { puts "NO_PLL fixed-by-xdc $freq" }

# An IP run left mid-flight by a killed session stays marked in-progress and
# launch_runs then waits on it forever with zero CPU.  Reset any that is not done.
foreach r [get_runs -quiet *clk_wiz*] {
    if {[get_property PROGRESS [get_runs $r]] ne "100%"} {
        puts "IP_RUN_RESET $r (was [get_property PROGRESS [get_runs $r]])"
        reset_run $r
    }
}

set nproc [exec nproc]
catch {set_param general.maxThreads $nproc}
# Implement from scratch.  With an incremental checkpoint the run starts from a
# previous routed design and only perturbs it, so the result depends on run
# history rather than on the sources alone -- that is what made repeated runs of
# the same configuration disagree.
set_property AUTO_INCREMENTAL_CHECKPOINT 0 [get_runs $impl]
catch {set_property INCREMENTAL_CHECKPOINT {} [get_runs $impl]}
catch {reset_property INCREMENTAL_CHECKPOINT [get_runs $impl]}
puts "INCREMENTAL_DISABLED"

puts "MAXTHREADS [get_param general.maxThreads]"

reset_run $impl
reset_run $synth
launch_runs $impl -jobs $nproc
wait_on_run $impl

set prog [get_property PROGRESS [get_runs $impl]]
puts "IMPL_PROGRESS $prog"
if {$prog ne "100%"} { close_project; return }

file mkdir $out
open_run $impl
foreach clk [lsort [get_clocks]] {
    set per [get_property PERIOD $clk]
    set p [get_timing_paths -delay_type max -to $clk -max_paths 1 -nworst 1]
    set s "none"
    if {[llength $p] > 0} { set s [get_property SLACK $p] }
    set fm "n/a"
    if {$s ne "none" && $s ne "" && $per > 0} { set fm [format %.3f [expr {1000.0/($per - $s)}]] }
    puts "CLOCK name=$clk period=$per mhz=[format %.3f [expr {1000.0/$per}]] wns=$s fmax=$fm"
}
report_utilization    -file $out/utilization.rpt
report_power          -file $out/power.rpt
report_timing_summary -file $out/timing.rpt
# guard: the clock the design actually got must match what was asked for
set got "none"
foreach clk [get_clocks] {
    set pp [get_timing_paths -delay_type max -to $clk -max_paths 1 -nworst 1]
    if {[llength $pp] > 0} { set got [expr {1000.0/[get_property PERIOD $clk]}] }
}
if {$got ne "none" && abs($got - $freq) > 0.05} {
    puts "CLOCK_MISMATCH asked ${freq} MHz but design runs at [format %.3f $got] MHz"
} else {
    puts "CLOCK_OK [format %.3f $got] MHz"
}
puts "REIMAGE_OK $xpr"
close_project
