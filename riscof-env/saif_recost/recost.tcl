set xpr  [lindex $argv 0]
set saif [lindex $argv 1]
set out  [lindex $argv 2]
open_project -quiet $xpr
open_run [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]
report_power -file $out/power_vectorless.rpt
read_saif -strip_path tb_saif/dut $saif
report_power -file $out/power_saif.rpt
report_power -hier all -file $out/power_saif_hier.rpt
puts "RECOST_OK"
close_project
