set pcq /tb_saif/dut/rv64im72f_6sp/program_counter/Q
run 70 us
set cands [get_objects -r /tb_saif/dut/*benchmark_start*]
set bs ""
foreach c $cands { if {![string match "*_reg*" $c]} { set bs $c; break } }
if {$bs eq "" && [llength $cands]} { set bs [lindex $cands 0] }
puts "BS $bs"
add_force $bs 1 -cancel_after 100ns
foreach s {cpu_clk_enable internal_reset clk_locked} {
  set o [lindex [get_objects -r /tb_saif/dut/$s] 0]
  if {$o ne ""} { puts "SIG $s = [get_value $o]" }
}
set tb [lindex [get_objects -r /tb_saif/dut/tx_busy] 0]
add_force $tb 0
for {set i 0} {$i < 115} {incr i} {
  run 2 us
  if {[catch {set pv [get_value -radix hex $pcq]}]} {set pv NA}
  set ce [get_value [lindex [get_objects -r /tb_saif/dut/cpu_clk_enable] 0]]
  puts "DBG t=[current_time] pc=$pv cpu_en=$ce"
}
quit
