# Set the clk_wiz to a requested frequency and report what the MMCM ACTUALLY
# resolves to, without implementing.  The exact value is what the benchmark
# image must be compiled for.
#   argv: <xpr> <requested_mhz>
open_project -quiet [lindex $argv 0]
set freq [lindex $argv 1]
set ip [lindex [get_ips -quiet clk_wiz_0] 0]
if {$ip eq ""} { puts "PROBE_NO_PLL"; close_project; return }
set cur [get_property CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $ip]
if {abs($cur - $freq) > 0.0005} {
    set_property -dict [list CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $freq] $ip
    generate_target all $ip
}
set m [get_property CONFIG.MMCM_CLKFBOUT_MULT_F $ip]
set d [get_property CONFIG.MMCM_DIVCLK_DIVIDE $ip]
set o [get_property CONFIG.MMCM_CLKOUT0_DIVIDE_F $ip]
set inp [get_property CONFIG.PRIM_IN_FREQ $ip]
puts [format "PROBE requested=%s M=%s D=%s O=%s exact=%.9f" \
      $freq $m $d $o [expr {double($inp)*$m/($d*$o)}]]
puts "PROBE_OK"
close_project
