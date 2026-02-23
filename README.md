# RV-IM100

## Quantitive Performance Analysis on RISC-V Architecture about ISA Extension and Operating Speed Acceleration.
An Architecture Design Guideline for RISC-V Extension and Speed improvement.

## Introduction
This repository is about benchmarking and analyzing the results of RISC-V Processor from [basic_RV32s](https://github.com/RISC-KC/basic_rv32s) and [ima_make_RV64](https://github.com/RISC-KC/ima_make_rv64).  
- **basic_RV32s**  
  Traditional MIPS 5-Stage Pipeline architectured RISC-V RV32I Processor implementation based on Patterson-Hennessy Methodology.
- **ima_make_RV64**  
  Based on basic_RV32s' microarchitecture, expands the design with M, A RISC-V standard extension and improve performance by operating speed optimization and adopting Advanced Computer architectural theorys.

## Benchmarks
### Environment
- Vivado 2025.2
- Synthesis: Flow_PerfOptimized_high
- Implmentation: Performance_ExplorePostRoutePhysOpt
  - opt_design-ExploreWithRemap
  - place_design-ExtraNetDelay_low
  - phys_opt_design-AggressiveFanoutOpt
  - route_design-NoTimingRelaxation
  - Post-Route Phys Opt Design - AggressiveExplore
 
- FPGA
  - Digilent Nexys Video  
    (AMD Xilinx Artix-7 XC7A200T-1SBG484C : speed grade = -1)

### Programs
Used 2 benchmark programs.
- Dhrystone 2.1
  - `-O2`, 300,000 iterations, no main source code modifications.
- Coremark
  - `-O2`, Standard 2,000 iterations, no main source code modifications.
- SPEC CPU 2017

### Conditions
Benchmarked 12 Different extension/clock-speed/architecture setups.

- RV32I  
  1. RV32I46F_5SP  - 50MHz  
- RV64I  
  1. RV64I59F_5SP  - 50MHz  
- RV64IM  
  1. RV64IM72F_5SP  - 50MHz  
  2. RV64IM72F_6SP  - Fmax  
  3. RV64IM72F_7SP  - Fmax  
  4. RV64IM72F_7SP_BRAM - Fmax
  5. RV64IM72F_8SP - 100MHz

- RV32IM
  1. RV32IM_5SP - Fmax
  2. RV32IM_6SP - Fmax
  3. RV32IM_7SP - Fmax
  4. RV32IM_7SP_BRAM - Fmax
  5. RV32IM_8SP - Fmax
 
### Performance Evaluation Factors
- Absoulte Performance : `per second(/sec)`
- Relative Performance : `per MHz(/MHz)`
- Maximum Frequency; Fmax: `MHz`
- Power Consumption: `mW`  
  <sup> from Vivado power estimation. Not an actual value. </sup>
- Resource Utilization: `LUT`, `FF`, `DSP`, `BRAM`, `LUTRAM`
- Synthesized Area: `mm^2`

## Performance Analysis
Explanation about the timing closure process and reasoning of the impact on performance from the architectural changes.
