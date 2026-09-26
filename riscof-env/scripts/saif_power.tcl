# Activity-based power from a captured SAIF, on the implemented design.
#   argv: <xpr> <saif> <out.rpt>
set xpr  [lindex $argv 0]
set saif [lindex $argv 1]
set out  [lindex $argv 2]
open_project -quiet $xpr
set impl [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]
open_run $impl
# vectorless first, as the baseline to compare against
set v [report_power -return_string]
foreach line [split $v "\n"] {
    if {[regexp {^\s*\|\s*(Total On-Chip Power \(W\)|Dynamic \(W\)|Device Static \(W\))\s*\|\s*([0-9.]+)} $line -> k val]} {
        puts "VECTORLESS $k = $val"
    }
}
read_saif -strip_path tb_saif/dut $saif
puts "SAIF_READ [file tail $saif]"
report_power -file $out
set s [report_power -return_string]
foreach line [split $s "\n"] {
    if {[regexp {^\s*\|\s*(Total On-Chip Power \(W\)|Dynamic \(W\)|Device Static \(W\))\s*\|\s*([0-9.]+)} $line -> k val]} {
        puts "SAIF_BASED $k = $val"
    }
}
# how much of the design the SAIF actually covered
foreach line [split $s "\n"] {
    if {[regexp -nocase {confidence|coverage} $line]} { puts "CONF $line" }
}
puts "SAIF_POWER_OK"
close_project
