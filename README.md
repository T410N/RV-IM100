# RV-IM100 — reproducibility guide (TVLSI-00554-2026 revision)

Single-lineage RISC-V design-space exploration on Artix-7 XC7A200T (`xc7a200tsbg484-1`,
Nexys Video): RV32/RV64, I/IM, 5–8 pipeline stages, 16 variants.
The design overview and block diagrams are in [`RV-IM100_RTL/README.md`](RV-IM100_RTL/README.md).

## Repository layout

| directory | contents |
|---|---|
| `RV-IM100_RTL/codes/` | RTL only, one folder per variant (`RV32s/`, `RV64s/`) |
| `RV-IM100_RTL/project_files/` | the Vivado projects: `RV{32,64}s/SoCs/<variant>_{Dhry,Coremark}` and `RV{32,64}s/cores/<variant>` |
| `benchmarks/` | Dhrystone 2.1 and CoreMark ports and their `.mem` images |
| `docs/` | block diagrams, architecture and timing-closure notes |
| `riscof-env/` | verification and measurement harness: RISCOF, riscv-tests, AAPG, Embench, profiling, SAIF power, micro-kernels; scripts, logs and reports |
| `comparison_cores/` | PicoRV32, VexRiscv and RVCoreP: synthesis wrappers and the throughput harness |
| `revision_0922/` | revision work, one folder per task (`T1`–`T14`) |
| `bitstream/`, `evidence/`, `Coremark_results_image/` | bitstream manifests and board results, configuration evidence, board CoreMark captures |
| `Research_data_*.xlsx` | the workbooks |

Vivado build output (`.runs`, `.cache`, `.sim`, `.hw`, `.ip_user_files`, `.gen`) is not
tracked: open a project and Vivado regenerates it from the sources. Reports and logs
archived from the measurement runs give absolute paths rooted at `/home/khwl/Desktop/RV-IM100`,
rewritten to this layout. Seven one-off tools in
`revision_0922/tools` and two workbook scripts in `riscof-env/scripts`
(`add_microkernel_sheets.py`, `fill_embench_rv32_sheet.py`) hard-code that root, so change it
to your checkout before running them. The other scripts locate the repository themselves.

## Data tag

**`rv-im100-data-2026-09`** (2026-09-16) marks the RTL behind every reported measurement:
SoC utilisation/timing/power, Dhrystone/CoreMark FPGA runs, Embench FPGA runs, RTL
simulation, verification and profiling. No RTL file changed after it. Every variant's RTL is
byte-identical across all 8 of its Vivado projects and the simulator source
(`revision_0922/T2`). Post-review RTL fixes, such as the AAPG IF/IO squash defect in
`revision_0922/T6`, go on a separate tag, never on this one.

## Variant naming map

| paper designation | variant (data / directories) | ISA | stages | SoC top (Vivado) | core module | project directory |
|---|---|---|---|---|---|---|
| 46F5SP | RV32I_5SP | RV32I_Zicsr | 5 | `RV32I46F5SPMMIOSoCTOP` | `RV32I46F5SPMMIO` | `RV-IM100_RTL/project_files/RV32s/SoCs/RV32I_5SP*` |
| 54F5SP | RV32IM_5SP | RV32IM_Zicsr | 5 | `RV32IM72F5SPSoCTOP` | `RV64IM72F5SP`¹ | `RV-IM100_RTL/project_files/RV32s/SoCs/RV32IM_5SP*` |
| 54F6SP | RV32IM_6SP | RV32IM_Zicsr | 6 | `RV64IM72F5SPSoCTOP`¹ | `RV64IM72F6SP`¹ | `RV-IM100_RTL/project_files/RV32s/SoCs/RV32IM_6SP*` |
| *(ablation; proposed 54F7SP-A)* | RV32IM_7SP | RV32IM_Zicsr | 7 | `RV32IM72F7SPSoCTOP` | `RV32IM72F7SP` | `RV-IM100_RTL/project_files/RV32s/SoCs/RV32IM_7SP_{Dhry,Coremark,…}` |
| 54F7SP | RV32IM_7SP_BRAM | RV32IM_Zicsr | 7 | `RV64IM72F5SPSoCTOP`¹ | `RV32IM72F7SP` | `RV-IM100_RTL/project_files/RV32s/SoCs/RV32IM_7SP_BRAM*` |
| *(proposed 54F7SP-O)* | RV32IM_7SP_BRAM_Opt | RV32IM_Zicsr | 7 | `RV32IM72F7SPSoCTOP` | `RV32IM72F7SP` | `RV-IM100_RTL/project_files/RV32s/SoCs/RV32IM_7SP_BRAM_Opt*` |
| *(proposed 54F8SP-N)* | RV32IM_8SP_withoutOpt | RV32IM_Zicsr | 8 | `RV32IM72F8SPSoCTOP` | `RV32IM72F8SP` | `RV-IM100_RTL/project_files/RV32s/SoCs/RV32IM_8SP_withoutOpt*` |
| 54F8SP | RV32IM_8SP | RV32IM_Zicsr | 8 | `RV32IM72F8SPSoCTOP` | `RV32IM72F8SP` | `RV-IM100_RTL/project_files/RV32s/SoCs/RV32IM_8SP*` |
| 59F5SP | RV64I_5SP | RV64I_Zicsr | 5 | `RV64I59F5SPSoCTOP` | `RV64I59F5SP` | `RV-IM100_RTL/project_files/RV64s/SoCs/RV64I_5SP*` (legacy `RV64I5SP_SoC`) |
| 72F5SP | RV64IM_5SP | RV64IM_Zicsr | 5 | `RV64IM72F5SPSoCTOP` | `RV64IM72F5SP` | `RV-IM100_RTL/project_files/RV64s/SoCs/RV64IM_5SP*` |
| 72F6SP | RV64IM_6SP | RV64IM_Zicsr | 6 | `RV64IM72F5SPSoCTOP`¹ | `RV64IM72F6SP` | `RV-IM100_RTL/project_files/RV64s/SoCs/RV64IM_6SP*` |
| *(ablation; proposed 72F7SP-A)* | RV64IM_7SP | RV64IM_Zicsr | 7 | `RV64IM72F5SPSoCTOP`¹ | `RV64IM72F6SP`¹ | `RV-IM100_RTL/project_files/RV64s/SoCs/RV64IM_7SP*` |
| 72F7SP | RV64IM_7SP_BRAM | RV64IM_Zicsr | 7 | `RV64IM72F5SPSoCTOP`¹ | `RV64IM72F6SP`¹ | `RV-IM100_RTL/project_files/RV64s/SoCs/RV64IM_7SP_BRAM*` |
| *(proposed 72F7SP-O)* | RV64IM_7SP_BRAM_Opt | RV64IM_Zicsr | 7 | `RV64IM72F5SPSoCTOP`¹ | `RV64IM72F6SP`¹ | `RV-IM100_RTL/project_files/RV64s/SoCs/RV64IM_7SP_BRAM_Opt*` |
| *(proposed 72F8SP-N)* | RV64IM_8SP_withoutOpt | RV64IM_Zicsr | 8 | `RV64IM72F8SPSoCTOP` | `RV64IM72F8SP` | `RV-IM100_RTL/project_files/RV64s/SoCs/RV64IM_8SP_withoutOpt*` |
| 72F8SP | RV64IM_8SP | RV64IM_Zicsr | 8 | `RV64IM72F8SPSoCTOP` | `RV64IM72F8SP` | `RV-IM100_RTL/project_files/RV64s/SoCs/RV64IM_8SP*` |

¹ Module and top names are inherited from the design they were derived from; the pipeline
depth is set by the sources each project compiles (`revision_0922/T7` item 2). Each variant
has one Vivado project per benchmark image: `_Dhry`, `_Coremark`, `_Embench_<bench>`, plus
the legacy project used as the simulation source. Core-only (memory-externalised) projects
are in `RV-IM100_RTL/project_files/RV{32,64}s/cores/<variant>` (top `*_CORE`).
The 7-stage in the original manuscript is **IM_7SP_BRAM**. IM_7SP is the IO-stage-only
ablation (asynchronous/distributed-RAM instruction memory).

## Memory

| | instruction memory | data memory |
|---|---|---|
| RV32 | 32 KB ROM (7/8-stage: 8192 × 32 b; 5/6-stage declare 16384 × 32 b, but Vivado sizes the ROM from the image) | 32 KB (8192 × 32 b LUTRAM on 5/6/7SP; 4 × 8 KB byte-banked BRAM on 7SP_BRAM*, 8SP*) |
| RV64 | same | 64 KB (8192 × 64 b LUTRAM; 8 × 8 KB byte-banked BRAM) |

Map: ROM at `0x0000_0000`, RAM at `0x1000_0000`, UART TX `0x1001_0000`. Embench links a
32 KB DATA region with a 4 KB stack (`riscof-env/embench-env/link.ld`). That is too small for
huffbench/slre/wikisort, whose re-measurement uses a 12 KB stack
(`revision_0922/T5/link_12KBstack.ld`); the five FPGA benchmarks fit the 4 KB stack. All
builds use one PLLE2_ADV (no MMCM).

## Toolchain

| tool | version |
|---|---|
| Vivado | 2025.2 (SW build 6299465); synthesis `Flow_PerfOptimized_high`, implementation `Performance_ExplorePostRoutePhysOpt`, incremental disabled |
| GCC | `riscv64-unknown-elf-gcc` 15.2.0 (multilib); CoreMark/Dhrystone `-O2 -funroll-loops`, Embench `-Os` |
| Verilator | 5.050 |
| RISCOF | 1.25.3 (`riscv_config` 3.18.3, `riscv_isac` 0.18.0); riscv-arch-test `old-framework-2.x` @ `6f7f47bd` (2.7.4, one local `arch_test.h` edit) |
| Reference model | Sail RISC-V 0.6 C emulator (`sail_cSim`, run live) |
| AAPG | `riscof-env/aapg-env/` |
| Python | 3.12 (`openpyxl` for the workbook scripts) |

## One command per flow

All paths relative to `riscof-env/`. The Vivado flows source
`/tools/Xilinx/2025.2/Vivado/settings64.sh` themselves.

| flow | command |
|---|---|
| Benchmark image at an exact clock | `scripts/build_image_exact.sh <variant> <coremark\|dhrystone> <MHz>` |
| SoC implementation, all 32 (utilisation/timing/power) | `scripts/reimpl_all32.sh` |
| Bitstreams, Dhrystone/CoreMark (32) | `scripts/bitstream_all.sh` |
| Embench FPGA images / RV32 bitstreams (40) | `scripts/build_embench_fpga.sh`, then `scripts/embench_rv32_rebuild.sh` |
| Core-only synthesis (16, 5 ns constraint) | `scripts/core_synth_all.sh` |
| External cores (PicoRV32, RVCoreP, VexRiscv) | `scripts/synth_extcores.sh` |
| Simulators (Verilator, all 16) | `python3 scripts/prepare_rtl.py && RVIM_SOURCE=socs scripts/build_sim.sh all` |
| Embench in simulation (19 × 16) | `scripts/build_embench.sh && python3 scripts/run_embench.py` |
| RISCOF (all variants vs Sail) | `python3 scripts/run.py && python3 scripts/summarize.py` |
| riscv-tests | `python3 scripts/run_rvtests.py` |
| AAPG randomized testing | `python3 scripts/run_aapg.py` |
| CPI / stall profiling (Dhrystone, CoreMark) | `python3 scripts/profile_all.py` |
| Micro-kernels (112 kernels × 16) | `python3 microkernels/run.py` |
| SAIF capture (one build) | `scripts/saif_v2.sh <variant> <bench> <xpr> <top>` (PC-sampled window) |
| SAIF re-cost on the final implementations (32) | `scripts/saif_recost_all.sh && python3 scripts/saif_recost_collect.py …` |
| RV32 Embench FPGA cross-check | `python3 scripts/t1_rv32_embench.py simref`, then `… compare` |
| AAPG-defect trigger monitor (T6) | `scripts/build_t6_sims.sh <variants…>` (separate `build_t6/`, testbench-only) |
| Workbook audits | `python3 scripts/soc_report_audit.py` |

## Data

- `Research_data_MASTER_0921.xlsx`: the master workbook (pre-revision values).
- `Research_data_0923_frozen.xlsx`: the frozen workbook the revised manuscript's tables and
  numbers are generated from.
- `revision_0922/`: the revision work. One folder per task with a written report, CSV
  fragments and tools; `Revision_review_0923.xlsx` collects every fragment plus a change
  list (current → proposed value for each master cell).
- `revision_0922/paper_numbers.csv`: every number used in the paper, generated by
  `revision_0922/tools/paper_numbers.py` (T14).
- `bitstream/`: the bitstream manifests and the board results measured with them (`.bit` files are
  not tracked; the flows above rebuild them). `bitstream/embench/MANIFEST.csv` lists clock and
  WNS per bitstream.
- `riscof-env/STATUS.md`: history of RTL defects found and fixed before the data tag.
