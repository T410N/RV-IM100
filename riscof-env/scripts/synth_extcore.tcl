# Core-only synthesis for an external comparison core, under the same
# methodology as the RV-IM100 cores: same part, same 5 ns constraint, core
# alone with its memory interface at the top-level boundary, out-of-context so
# no I/O buffers are inserted and the area is the core's own.
#   argv: <name> <top> <xdc> <out dir> <source files...>
set name [lindex $argv 0]
set top  [lindex $argv 1]
set xdc  [lindex $argv 2]
set out  [lindex $argv 3]
set clkp [lindex $argv 4]
set srcs [lrange $argv 5 end]
set part xc7a200tsbg484-1

file mkdir $out
create_project -in_memory -part $part
foreach f $srcs { read_verilog -quiet $f }
# The clock port name differs per core, so the XDC is written per core.  It must
# be read BEFORE synth_design: the RV-IM100 cores are synthesized timing-driven
# from their project XDC, and constraining afterwards would leave synthesis
# untimed and understate Fmax -- not a like-for-like comparison.
set gx [file join $out gen_clock.xdc]
file mkdir $out
set fh [open $gx w]
puts $fh "create_clock -period 5.000 -name coreclk \[get_ports $clkp\]"
close $fh
read_xdc -quiet $gx
puts "EXTCORE $name top=$top part=$part sources=[llength $srcs]"

# -mode out_of_context: no I/O buffers, so the report is core logic only.
synth_design -top $top -part $part -mode out_of_context
if {[llength [get_clocks -quiet coreclk]] == 0} {
    puts "EXTCORE_FAIL $name: constraint did not attach to port '$clkp'"
    exit 1
}
puts "EXTCORE_CLOCK $name port=$clkp attached=[llength [get_clocks -quiet coreclk]]"
opt_design -quiet

report_utilization    -file $out/utilization.rpt
report_timing_summary -file $out/timing.rpt

set p [get_timing_paths -delay_type max -max_paths 1 -nworst 1]
if {[llength $p]} {
    set s [get_property SLACK [lindex $p 0]]
    puts [format "EXTCORE_RESULT %s wns=%.3f fmax=%.3f" $name $s [expr {1000.0/(5.0-$s)}]]
} else { puts "EXTCORE_RESULT $name wns=none" }
foreach r {"CLB LUTs" "Slice LUTs" "CLB Registers" "Slice Registers" "Block RAM Tile" "DSPs"} {
    puts "EXTCORE_UTIL $name $r"
}
puts "EXTCORE_OK $name"
