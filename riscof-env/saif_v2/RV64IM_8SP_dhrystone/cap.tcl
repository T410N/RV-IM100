run 70 us
set cands [get_objects -r /tb_saif/dut/*benchmark_start*]
set bs ""
foreach c $cands { if {![string match "*_reg*" $c]} { set bs $c; break } }
if {$bs eq "" && [llength $cands]} { set bs [lindex $cands 0] }
if {$bs eq ""} { puts "NO_BENCHMARK_START"; quit }
add_force $bs 1 -cancel_after 100ns
run 30 us
set tb [lindex [get_objects -r /tb_saif/dut/tx_busy] 0]
if {$tb ne ""} { add_force $tb 0; run 1000 us; remove_forces -all; puts "FASTFWD_DONE" }
run 100 us
set pcq /tb_saif/dut/rv64im72f_6sp/program_counter/Q
puts "PCOBJ $pcq"
set steps [expr {100 / 10}]
for {set try 0} {$try < 6} {incr try} {
    set u0 [get_value -radix dec /tb_saif/uart_chars]
    open_saif kernel.saif
    log_saif [get_objects -r /tb_saif/dut/*]
    for {set s 0} {$s < $steps} {incr s} {
        if {[catch {set pv [get_value -radix hex $pcq]}]} {set pv NA}; puts "PC t=[current_time] pc=$pv"
        run 10 us
    }
    if {[catch {set pv [get_value -radix hex $pcq]}]} {set pv NA}; puts "PC t=[current_time] pc=$pv"
    close_saif
    set du [expr {[get_value -radix dec /tb_saif/uart_chars] - $u0}]
    puts "WINDOW try=$try uart_delta=$du len=100us"
    if {$du <= 1} { puts "WINDOW_ACCEPTED uart_delta=$du"; break }
    if {$try == 5} { puts "WINDOW_BEST_EFFORT uart_delta=$du" }
}
quit
