# Write the post-implementation timing netlist + SDF for one project.
#   argv: <xpr> <outdir>
set xpr [lindex $argv 0]
set out [lindex $argv 1]
open_project -quiet $xpr
set impl [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]
if {[get_property PROGRESS [get_runs $impl]] ne "100%"} {
    puts "NOT_IMPLEMENTED"; close_project; return
}
open_run $impl
file mkdir $out
set top [get_property TOP [current_fileset]]
puts "TOP $top"
# timesim netlist + SDF: this is the shipped, routed design, so the switching
# activity we capture is the real one, not an RTL approximation
write_verilog -mode timesim -sdf_anno true -force $out/netlist.v
write_sdf              -process_corner slow -force $out/netlist.sdf
puts "NETLIST_BYTES [file size $out/netlist.v]"
puts "SDF_BYTES     [file size $out/netlist.sdf]"
puts "SAIF_NETLIST_OK"
close_project
