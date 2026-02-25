vlib questa_lib/work
vlib questa_lib/msim

vlib questa_lib/msim/xil_defaultlib

vmap xil_defaultlib questa_lib/msim/xil_defaultlib

vlog -work xil_defaultlib -64 -incr -mfcu  "+incdir+../../../../../../../../../../../tools/Xilinx/2025.2/data/rsb/busdef" "+incdir+../../../../RV32I46F5SP_MMIO_Dhrystone.gen/sources_1/ip/clk_wiz_0" \
"../../../../RV32I46F5SP_MMIO_Dhrystone.gen/sources_1/ip/clk_wiz_0/clk_wiz_0_sim_netlist.v" \


vlog -work xil_defaultlib \
"glbl.v"

