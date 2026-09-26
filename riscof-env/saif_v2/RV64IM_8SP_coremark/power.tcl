set xpr  [lindex $argv 0]
set saif [lindex $argv 1]
open_project -quiet $xpr
open_run [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]
report_power -file power_vectorless.rpt
read_saif -strip_path tb_saif/dut $saif
report_power -file power_saif.rpt
report_power -hier all -file power_saif_hier.rpt
puts "SAIF_POWER_OK"
close_project
