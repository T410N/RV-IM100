# Fixed RTL — backup copies

Copies of the RTL files changed by the verification fixes, taken while those
fixes existed only as uncommitted edits in the working tree.  They are kept
under their original paths: `codes/...` mirrors `RV-IM100_RTL/codes/`, and
`RV32s/...`, `RV64s/...` mirror `RV-IM100_RTL/project_files/`.

These are copies, not the build source.  The build reads `RV-IM100_RTL/`;
`scripts/prepare_rtl.py` stages from there.  All 98 copies match the build
source in content (six 8SP files differ only in line endings).

## What is fixed here

| marker in the file | defect |
|---|---|
| `EXR_src_A_hold` / `EXR_src_B_hold` | 8SP stale ALU operand: a producer drains out of the one-deep retire shadow while EXR is stalled, the forward select falls to 0, and the ID-sampled register value is used. Hold the resolved operand until the instruction leaves EXR (clear on `ID_EXR_stall`, **not** `EXR_EX_stall`). |
| `divisor_latch` | Divider operand latch: `Divider_WORD`/`Divider_DWORD` latched `dividend_reg` at `division_start` then re-read the **live** ports in `INITIALIZE`, requiring operands stable for two cycles. Latch both at start and use the latched copies. |
| `flush_reg && !IF_IO_stall` | 7SP_BRAM IF/IO bubble: the load-use bubble injector did not account for `IF_IO_stall` deferring the redirect's second bubble, so a third bubble overwrote the branch target sitting in IF. |

The 26 files matching the third marker include pre-existing uses of the same
sub-expression; the behavioural change is in 3 `IF_IO_Register.v` copies under
`RV64IM_7SP_BRAM`.
