open_project -quiet [lindex $argv 0]
set impl [lindex [get_runs -filter {IS_IMPLEMENTATION}] 0]
open_run $impl
set out [lindex $argv 1]
# Can Vivado describe the instruction ROM's BRAM layout?
if {[catch {write_mem_info -force $out/design.mmi} err]} {
    puts "MMI_FAILED $err"
} else {
    puts "MMI_WRITTEN [file size $out/design.mmi] bytes"
}
# What does the instruction memory actually infer to?
set cells [get_cells -hier -filter {PRIMITIVE_TYPE =~ BMEM.*.*}]
puts "BRAM_CELLS [llength $cells]"
foreach c [lrange $cells 0 3] { puts "  CELL $c  ref=[get_property REF_NAME $c]" }
# INIT strings are what updatemem would have to rewrite
set n 0
foreach c $cells { if {[llength [list_property $c INIT_00]]} { incr n } }
puts "CELLS_WITH_INIT $n"
puts "TRY_MMI_OK"
close_project
