# RV-IM100
## Quantitive Performance Analysis on RISC-V Architecture about ISA Extension and Operating Speed Acceleration.
<img width="900" height="512" alt="KHWL_Original_RVIM100" src="https://github.com/user-attachments/assets/01d3e2d6-57d0-4e7e-b4a3-df2cbd42651a" />

An Architecture Design Guideline for RISC-V Extension and Speed improvement with Pipeline deepening.

## Introduction
This repository is about benchmarking and analyzing the results of **extended** RISC-V Processor based on [basic_RV32s](https://github.com/RISC-KC/basic_rv32s) and [ima_make_RV64](https://github.com/RISC-KC/ima_make_rv64).  
- **basic_RV32s**  
  Traditional MIPS 5-Stage Pipeline architectured RISC-V RV32I Processor implementation based on Patterson-Hennessy Methodology.
- **ima_make_RV64**  
  Based on basic_RV32s' microarchitecture, expands the design with M, A RISC-V standard extension for supporting Linux and improve performance by operating speed optimization and adopting Advanced Computer architectural theory.

## Directories
- **RV32s**: Vivado ready RV32 Project files for all configurations
- **RV64s**: Vivado ready RV64 Project files for all configurations
- **benchmarks**: CoreMark and Dhrystone RISC-V ported source codes and `.mem` file for Synthesis
  - **results**: Result screenshot of each benchmarks
- **codes**: RTL only directory for all configurations

## Contribution
- Show how to extend a RISC-V ISA with M-extension while using modular verilog design.
- Suggest an 8-stage pipeline extension roadmap for RISC-V basic 5-Stage pipeline Processor.
- Timing Closure methodology for improving clock speed.
- Benchmark performance with Dhrystone 2.1, CoreMark and analyze the results.

## Architecture Diagram 
### Final 8-Stage Pipelined Architecture(IF-IO-ID-EXR-EX-BR(EX2)-MEM-WB)
Based on MIPS 5-Stage architecture, basic_RV32s' architecture was designed, and extended to 8-stage originally by Hyunwoo Kang.
<img width="2676" height="1607" alt="RV64IM72F_8SP" src="https://github.com/user-attachments/assets/54ba627f-65c5-49fa-883e-63048430e746" />

### SoC Configuration
<img width="881" height="492" alt="59F5SP" src="https://github.com/user-attachments/assets/63cae7ca-6582-493d-9461-f5cef92835c2" />

## Benchmark Environment
- Vivado 2025.2
- Synthesis: Flow_PerfOptimized_high
- Implmentation: Performance_ExplorePostRoutePhysOpt
- FPGA
  - Digilent Nexys Video  
    (AMD Xilinx Artix-7 XC7A200T-1SBG484C : speed grade = -1)

### Programs
Used 2 benchmark programs.
- Dhrystone 2.1
  - `-O2`, 300,000 iterations, no main source code modifications.
- Coremark
  - `-O2`, Standard 2,000 iterations, no main source code modifications.

### Conditions
Benchmarked 10 Different extension/clock-speed/architecture setups.

- RV32I  
  1. RV32I46F_5SP  = RV32I, 46 Instructions, 5-Stage Pipelined
- RV64I  
  1. RV64I59F_5SP
- RV64IM  
  1. RV64IM72F_5SP
  2. RV64IM72F_6SP
  3. RV64IM72F_7SP
  4. RV64IM72F_8SP

- RV32IM
  1. RV32IM54F_5SP
  2. RV32IM54F_6SP
  3. RV32IM54F_7SP
  4. RV32IM54F_8SP

## Benchmark Results
### RV32 Performance & Speed

| Configuration | Dhrystones/s | DMIPS/MHz | CoreMark Iter/s | CoreMark/MHz | Core Fmax (MHz) | SoC Fmax (MHz) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| I_5SP | 87,378 | 1.105 @ 45MHz | 50 | 1.111 @ 45MHz | 57.948 | 45.204 |
| IM_5SP | 83,820 | 1.109 @ 43MHz | 117 | 2.721 @ 43MHz | 57.998 | 43.158 |
| IM_6SP | 94,161 | 1.072 @ 50MHz | 125 | 2.500 @ 50MHz | 68.681 | 50.682 |
| IM_7SP | 99,447 | 0.786 @ 72MHz | 142 | 1.972 @ 72MHz | 68.785 | 72.041 |
| IM_8SP | 143,668 | 0.654 @ 125MHz | 200 | 1.600 @ 125MHz | 105.186 | 126.247 |

### RV32 Resource

| Configuration | Core LUT | Core FF | Core DSP | Core Power (W) | SoC LUT | SoC LUTRAM | SoC FF | SoC BRAM | SoC DSP | SoC Power (W) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| I_5SP | 2,808 | 1,194 | 0 | 0.156 | 13,637 | 4,140 | 1,887 | 0 | 0 | 0.314 |
| IM_5SP | 3,755 | 1,719 | 4 | 0.166 | 12,646 | 4,140 | 2,160 | 0 | 4 | 0.320 |
| IM_6SP | 3,801 | 1,954 | 4 | 0.171 | 12,302 | 4,140 | 2,421 | 0 | 4 | 0.325 |
| IM_7SP | 3,184 | 2,084 | 4 | 0.158 | 3,046 | 44 | 2,190 | 16 | 4 | 0.317 |
| IM_8SP | 2,750 | 2,114 | 4 | 0.158 | 2,770 | 44 | 2,188 | 16 | 4 | 0.327 |

### RV64 Performance & Speed

| Configuration | Dhrystones/s | DMIPS/MHz | CoreMark Iter/s | CoreMark/MHz | Core Fmax (MHz) | SoC Fmax (MHz) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| I_5SP | 80,482 | 1.145 @ 40MHz | 37 | 0.935 @ 39.583MHz | 52.213 | 40.021 |
| IM_5SP | 76,767 | 1.150 @ 38MHz | 91 | 2.395 @ 38MHz | 50.712 | 38.016 |
| IM_6SP | 87,548 | 1.107 @ 45MHz | 100 | 2.222 @ 45MHz | 67.051 | 45.009 |
| IM_7SP | 78,124 | 0.808 @ 55MHz | 100 | 1.818 @ 55MHz | 65.261 | 55.948 |
| IM_8SP | 117,508 | 0.669 @ 100MHz | 153 | 1.530 @ 100MHz | 108.365 | 100.817 |

### RV64 Resource

| Configuration | Core LUT | Core FF | Core DSP | Core Power (W) | SoC LUT | SoC LUTRAM | SoC FF | SoC BRAM | SoC DSP | SoC Power (W) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| I_5SP | 5,675 | 2,362 | 0 | 0.194 | 20,839 | 8,280 | 3,384 | 0 | 0 | 0.388 |
| IM_5SP | 8,078 | 3,427 | 20 | 0.203 | 21,894 | 8,280 | 3,667 | 0 | 20 | 0.376 |
| IM_6SP | 8,412 | 3,893 | 20 | 0.224 | 22,648 | 8,280 | 4,206 | 0 | 20 | 0.397 |
| IM_7SP | 7,295 | 4,095 | 20 | 0.193 | 8,850 | 88 | 4,282 | 24 | 20 | 0.310 |
| IM_8SP | 6,755 | 4,347 | 20 | 0.185 | 9,563 | 88 | 4,522 | 24 | 20 | 0.246 |
