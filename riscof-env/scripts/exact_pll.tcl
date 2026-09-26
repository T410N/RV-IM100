# Exact MMCM output frequency for the project's registered clk_wiz.
#   argv: <xpr> <tag>
open_project -quiet [lindex $argv 0]
set tag [lindex $argv 1]
foreach ip [get_ips -quiet] {
    set m [get_property CONFIG.MMCM_CLKFBOUT_MULT_F $ip]
    set d [get_property CONFIG.MMCM_DIVCLK_DIVIDE $ip]
    set o [get_property CONFIG.MMCM_CLKOUT0_DIVIDE_F $ip]
    set req [get_property CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $ip]
    set inp [get_property CONFIG.PRIM_IN_FREQ $ip]
    if {$m eq "" || $d eq "" || $o eq ""} { continue }
    set exact [expr {double($inp)*$m/($d*$o)}]
    puts [format "EXACT %s ip=%s in=%s M=%s D=%s O=%s requested=%s exact=%.9f" \
          $tag $ip $inp $m $d $o $req $exact]
}
puts "EXACT_OK $tag"
close_project
