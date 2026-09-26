# RISCOF environment for RV-IM100

Runs the official RISC-V Architecture Test Suite against all 14 processor
variants in `../RV-IM100_RTL/codes`, using the **Sail RISC-V C emulator** as the
reference model.

## Results

All variants pass the full I and M suites against the Sail golden model.
See `results_codes.csv` / `results_socs.csv`, or regenerate with
`python3 scripts/summarize.py`.  Per-run HTML reports are at
`work/<variant>/<group>/report.html`.

## RTL defects found and fixed

The first sweep failed 41 tests in `codes/` and 67 in `SoCs/`.  Five distinct
defects accounted for all of them.

**1. CSR address aliasing swallowed branch redirects** (`bge/bgeu/blt/bne`, 10
variants).  The core top drove the CSR file's read address from the decoded
immediate of *every* instruction, and `CSR_File.v` compared it with no opcode
qualification.  A store with offset 768 -- `0x300`, `mstatus` -- spuriously
dropped `csr_ready`, raising `pc_stall`; `PC_Controller` has no pending-redirect
register and simply discards the redirect, while `Hazard_Unit` flushes anyway,
so the branch target was lost and never re-fetched.  Fixed by presenting a CSR
address only for a real CSR instruction (`scripts/fix_csr_alias.py`).  Four
variants were passing only by coincidence -- they read `instruction[31:20]`,
which for an S-type is `{imm[11:5], rs2}` and happened to miss the compare list
-- and were fixed too.

**2. Store-data forwarding one stage too shallow** (`fence-01`, both 8SP).  The
ALU operand chain forwards EX > EX2 > MEM > WB > retire, but the store-data
chain stopped at WB, so a store whose producer had drained past WB read a stale
register value.  Fixed with a hold register in the EXR store-data path that
latches the forwarded value and holds it until the store advances.

**3. `retire_stall` forwarded a stale retire shadow** (`add/sub/or/xor`,
`mul*`, `rem*`).  "Retire" is a one-deep shadow of WB used as a fifth forwarding
source.  Freezing it without also asserting `MEM_WB_stall` let the instruction in
WB advance uncaptured, so retire kept pointing at an older write to the same
register and forwarded it ahead of the register file.  On `li x5, 0xfff7ffff`
(= `lui` + `addi`) the consumer received the `lui` value.  Removed.

**4. Unmasked shift amount** (`sll/sra/srl`, `RV32I_5SP`).  The RV32I ALU shifted
by the full 32-bit `rs2`; RISC-V requires `rs2[4:0]`.  Immediate shifts were
already truncated in the core top, which is why only the register-register forms
failed.

**5. `IF_imm` too narrow** (`jal-01`, RV64 5SP).  The branch-predictor immediate
was a 32-bit concatenation assigned to a 64-bit wire, so it was zero-extended
rather than sign-extended.  Every backward predicted-taken branch left the PC
with a permanent +2^32 bias, which later `AUIPC` results inherited.

**6. Divider special cases lost** (`div/divu/rem/remu`, `RV64IM_5SP`).
Divide-by-zero and signed-overflow results were combinational on `division_start`
-- a one-cycle pulse during which `Hazard_Unit` stalls `EX_MEM`, so the value was
never latched and the stale previous quotient was captured instead.  Replaced
with the 6SP divider, which registers the condition.

`codes/` is the canonical tree: RISCOF runs against it, so it is the only one
whose correctness is measured.  `scripts/propagate_to_socs.py` syncs the verified
RTL into the Vivado project trees, skipping files that legitimately differ per
project (the ROM image name, UART `BAUD_DIV`, and the SoC top):

```bash
python3 scripts/propagate_to_socs.py --target socs   --dry-run
python3 scripts/propagate_to_socs.py --target cores  --dry-run
```

### The cores/ projects

`RV32s/cores` and `RV64s/cores` wrap each design in a `*_CORE` top that
externalises the instruction and data memories, so Vivado measures core-only
area and Fmax without constant-propagating through the RAMs.  They are
measurement artifacts rather than runnable processors -- the 5/6/7-stage ones do
not even expose the ROM-bypass path, so a program could not load `.rodata` --
and the suite therefore cannot be run against them.  They are instead kept
correct by construction:

* every submodule is byte-identical to the RISCOF-verified `codes/` copy;
* the `*_CORE` top carries the same patches, and the inserted blocks are
  byte-identical to the verified ones;
* all 16 elaborate cleanly under `verilator --lint-only`.

Note the `*_CORE` top shares its *filename* with the `codes/` top but declares a
different module and port list, so propagation deliberately never copies it --
it is patched in place.

Fixing these also corrected a stale `misa` in the RV64 `cores/` CSR files:
`0x8000_0000_0000_0080` (bit 7) instead of `0x8000_0000_0000_1100` (I+M).  No
test reads `misa`, so the suite never caught it.

**Pre-existing defect left in place:** nine `cores/` tops declare
`im_instruction` both as an input port and again as an internal wire.  Vivado
tolerates the duplicate; Verilator rejects it.  It is unrelated to this campaign
and was not touched -- but it will block any stricter tool.

**Re-synthesis is still required.**  These fixes touch CSR decode, forwarding and
hazard logic, so every Fmax, LUT/FF, DSP and power figure must be re-measured
before it is reported.

## Versions

| Component | Version |
|---|---|
| RISCOF | 1.25.3 (`riscv_config` 3.18.3, `riscv_isac` 0.18.0) |
| riscv-arch-test | 2.7.4 (`6f7f47bd`, `riscv-non-isa/riscv-arch-test`) |
| Reference model | Sail RISC-V 0.6 C emulator (`riscv_sim_RV32` / `riscv_sim_RV64`), built with Sail 0.18.0 |
| DUT simulator | Verilator 5.050 |
| Toolchain | `riscv64-unknown-elf-gcc` 15.2.0 (multilib) for the DUT; `riscv32-unknown-elf-gcc` 15.2.0 for the RV32 reference |

## Running

```bash
python3 scripts/variants.py          # list the 14 variants discovered in codes/
python3 scripts/prepare_rtl.py       # stage simulation RTL into build/<variant>/rtl
./scripts/build_sim.sh all           # verilate each variant -> build/<variant>/Vsim_top
python3 scripts/gen_isa_yaml.py      # regenerate the four ISA yamls
python3 scripts/run.py               # run every variant against Sail
python3 scripts/summarize.py         # collect results
```

`scripts/run.py` accepts variant names and `--group I|M` to narrow the sweep.
Re-run `prepare_rtl.py` **and** `build_sim.sh` after any change to the design
RTL — `riscof run` recompiles the tests but never rebuilds the simulator.

## How a test runs

RISCOF compiles each test twice, once for the DUT's memory map and once for
Sail's, runs both, and compares the signature region byte for byte. The DUT
path is:

1. `riscv64-unknown-elf-gcc -march=rv{32,64}i[m]_zicsr` with `env/link.ld`,
2. `objcopy` of `.text.init .text .rodata .data` into one contiguous ROM image,
3. `Vsim_top +HEX=... +SIG_BEGIN=... +SIG_END=... +SIG_FILE=...`,
4. the wrapper writes the signature when the run ends.

The `-march` string comes from the declared ISA yaml, so an RV32I core is built
as `rv32i_zicsr` and RISCOF never selects M tests for it.

## Adaptations, and why each is needed

The cores were built as FPGA SoCs with no external bus, no loader and no
end-of-test convention, so a few things had to be added. All of them live in
generated copies under `build/<variant>/rtl`; nothing in `../RV-IM100_RTL/codes` is
modified.

**Instruction memory grown to 2 MB** (`scripts/prepare_rtl.py`). `jal-01.S`
expands to a 1.18 MB text image once `objcopy` fills the jump ranges, against
an RTL ROM of 32–64 KB. The address slices widen to match (`pc[20:2]`), and the
ROM-access decode in both `Instruction_Memory.v` and `Data_Memory.v` widens from
a 64 KB window to 2 MB, since `.rodata` and the `.data` load image both sit past
64 KB in the larger tests.

**Benchmark image and preloaded trap handler removed.** Each
`Instruction_Memory.v` hardcodes `$readmemh` of a benchmark `.mem` and then
overwrites `data[7000]` onward with a hand-assembled trap handler — byte address
0x6D60, which is the `mtvec` reset value. The tests install their own handler and
their `.text` runs straight through 0x6D60, so both are replaced by a `+HEX`
plusarg.

**`.data` is copied from ROM at boot** (`plugins/rv_im100/env/`). The linker
script gives `.data` a load address in ROM and a virtual address in RAM;
`RVMODEL_BOOT` copies it down and zeroes `.bss`. This avoids having to preload
the RAM directly, which would mean knowing each variant's RAM shape — flat
32-bit words on the RV32 cores, flat 64-bit on the RV64 cores, eight byte banks
on the 8-stage designs.

**Four observability outputs added to each core** (`SIM_dmem_*`, added by
`prepare_rtl.py`). These mirror the address, write data, byte mask and write
enable already driven into the `DataMemory` instance, letting `sim_top` maintain
a byte-accurate shadow of RAM and dump the signature from it. They are read-only
taps and change no behaviour. The pre-existing `MMIO_data_memory_*` ports cannot
serve this purpose: on the 5-stage cores they are a WB-stage view while the RAM
is written from MEM, and they carry no byte enables at all, which corrupts every
sub-word store (`sb`, `sh`, and `sw` on RV64).

**Halt convention.** `RVMODEL_HALT` stores to `0x1001_0000`, the design's own
UART TX MMIO address. `Data_Memory` decodes it as neither RAM nor ROM, so
nothing in the core reacts; `sim_top` snoops it and stops.

**NOPs around CSR accesses in `RVMODEL_BOOT`.** The CSR read path takes two
cycles and is not interlocked against a preceding register write, so
`la t0, X` immediately followed by `csrw mtvec, t0` reads a stale `t0` on the
deeper pipelines. The padding is confined to the model boot and halt hooks —
which are model-specific by design — so ordinary data hazards are still
exercised by the tests themselves.

## Known deviations from stock upstream

`riscv-test-suite/env/arch_test.h` in the arch-test checkout carries an
uncommitted local edit: `TEST_JALR_OP` guards `LA(rd,5b)` with `.ifnc rd,x0`.
Both the DUT and the reference compile with it, so results stay self-consistent,
but it is a deviation from released 2.7.4 and should be reverted or documented
before the results are published.

`riscof arch-test --show-version` reports "Not the riscv-arch-test repo" because
the clone's remote is `riscv-non-isa/riscv-arch-test` while RISCOF matches
against `riscv/`. Cosmetic, but it blanks the suite-version field in the report
headers.

Do **not** run `riscof arch-test --clone` against the existing checkout: it
`rmtree`s the target first, then fetches the current latest tag, which is a much
newer restructured suite without the golden references.

## Scope

Machine-mode `Zicsr` only. The privileged test group is out of scope: the arch
test M-mode trap framework uses `mscratch` as its scratch pointer, and
`CSR_File.v` implements ten CSRs with neither `mscratch` nor `mtval`.
