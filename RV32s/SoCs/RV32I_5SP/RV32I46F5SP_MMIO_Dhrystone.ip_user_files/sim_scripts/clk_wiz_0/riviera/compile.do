transcript off
onbreak {quit -force}
onerror {quit -force}
transcript on

vlib work
vlib riviera/xil_defaultlib

vmap xil_defaultlib riviera/xil_defaultlib

vlog -work xil_defaultlib  -incr -v2k5 "+incdir+../../../../../../../../../../../tools/Xilinx/2025.2/data/rsb/busdef" "+incdir+../../../../RV32I46F5SP_MMIO_Dhrystone.gen/sources_1/ip/clk_wiz_0" -l xil_defaultlib \
"../../../../RV32I46F5SP_MMIO_Dhrystone.gen/sources_1/ip/clk_wiz_0/clk_wiz_0_sim_netlist.v" \


vlog -work xil_defaultlib \
"glbl.v"

