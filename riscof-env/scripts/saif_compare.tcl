# Power for several SAIF windows on one design, to test whether the captured
# window is in steady state.  argv: <xpr> <saif> [<saif> ...]
set xpr [lindex $argv 0]
open_project -quiet $xpr
open_run [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]
foreach saif [lrange $argv 1 end] {
    reset_switching_activity -all
    read_saif -strip_path tb_saif/dut $saif
    set s [report_power -return_string]
    set tot ""; set dyn ""
    foreach line [split $s "\n"] {
        if {[regexp {^\s*\|\s*Total On-Chip Power \(W\)\s*\|\s*([0-9.]+)} $line -> v]} { set tot $v }
        if {[regexp {^\s*\|\s*Dynamic \(W\)\s*\|\s*([0-9.]+)} $line -> v]} { set dyn $v }
    }
    puts "WINDOW [file tail $saif] total=$tot dynamic=$dyn"
}
puts "COMPARE_OK"
close_project
