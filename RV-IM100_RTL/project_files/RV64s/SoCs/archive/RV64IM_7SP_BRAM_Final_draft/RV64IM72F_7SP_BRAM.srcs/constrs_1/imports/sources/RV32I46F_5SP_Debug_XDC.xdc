### Nexys Video Constraints File for CPU Debug System
### Target Board: Nexys Video (Artix-7 XC7A200T)

##########################################################################################
# Clock Signal
##########################################################################################
# 100MHz system clock
set_property -dict { PACKAGE_PIN R4    IOSTANDARD LVCMOS33 } [get_ports { clk }];
create_clock -name sys_clk_pin -period 10.00 -waveform {0 5} [get_ports clk]

##########################################################################################
# Reset button (CPU_RESET)
##########################################################################################
set_property -dict { PACKAGE_PIN G4  IOSTANDARD LVCMOS15 } [get_ports { reset_n }];

##########################################################################################
# UART (uart_tx)
##########################################################################################
set_property -dict { PACKAGE_PIN AA19  IOSTANDARD LVCMOS33 } [get_ports { uart_tx_in }];

##########################################################################################
# Push buttons (5-button navigation)
##########################################################################################
set_property -dict { PACKAGE_PIN F15 IOSTANDARD LVCMOS12 } [get_ports { btn_up }];

##########################################################################################
# LEDs
##########################################################################################
set_property -dict { PACKAGE_PIN T14   IOSTANDARD LVCMOS25 } [get_ports { led[0] }];
set_property -dict { PACKAGE_PIN T15   IOSTANDARD LVCMOS25 } [get_ports { led[1] }];
set_property -dict { PACKAGE_PIN T16   IOSTANDARD LVCMOS25 } [get_ports { led[2] }];
set_property -dict { PACKAGE_PIN U16   IOSTANDARD LVCMOS25 } [get_ports { led[3] }];
set_property -dict { PACKAGE_PIN V15   IOSTANDARD LVCMOS25 } [get_ports { led[4] }];
set_property -dict { PACKAGE_PIN W16   IOSTANDARD LVCMOS25 } [get_ports { led[5] }];
set_property -dict { PACKAGE_PIN W15   IOSTANDARD LVCMOS25 } [get_ports { led[6] }];
set_property -dict { PACKAGE_PIN Y13   IOSTANDARD LVCMOS25 } [get_ports { led[7] }];

##########################################################################################
# Timing constraints
##########################################################################################
# False path constraints for async I/O
set_false_path -from [get_ports reset_n]
set_false_path -from [get_ports {btn_*}]
set_false_path -to [get_ports {led[*]}]
set_false_path -to [get_ports uart_tx_in]

##########################################################################################
# Configuration constraints
##########################################################################################
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property CONFIG_MODE SPIx4 [current_design]