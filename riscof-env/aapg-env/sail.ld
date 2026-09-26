/* AAPG program layout for the Sail reference run.
 *
 * Sail boots at 0x80000000 with a flat RAM, so no copy loop is needed and
 * .data can sit at its virtual address.  Kept deliberately close to dut.ld so
 * the two runs differ only in where memory lives, never in what the program
 * does -- the signature comparison is only meaningful if both sides execute
 * the same instruction stream.
 */

OUTPUT_ARCH("riscv")
ENTRY(_start)

SECTIONS
{
    . = 0x80000000;
    .text.init : { *(.text.init) }
    .text      : { *(.text .text.*) . = ALIGN(8); }
    .rodata    : { . = ALIGN(8); *(.rodata .rodata.* rodata) . = ALIGN(8); }

    . = 0x80100000;
    /* AAPG reaches the signature as `la sp, begin_signature; add sp, sp, K`
       followed by a load or store with a 12-bit immediate, so an access can
       land up to 2048 bytes either side of the declared region.  On Sail
       those addresses are ordinary RAM; on the DUT anything below
       0x10000000 leaves the data memory entirely and anything above 32 KB
       aliases back into it, so the two models would legitimately disagree
       about memory the program was never meant to touch.  A 2 KB guard on
       each side -- inside the copied region, so both sides see the same
       zeros -- keeps every reachable address in real, identically
       initialised memory. */
    _data_start = .;
    . = . + 0x800;
    .data : { *(begin_signature*) *(.data .data.*) *(.sdata .sdata.*) }
    . = ALIGN(8);
    . = . + 0x800;
    _data_end = .;
    _data_lma = _data_start;      /* no copy needed; loop exits immediately */

    . = ALIGN(64);
    .tohost : { *(.tohost) }

    .bss (NOLOAD) : {
        . = ALIGN(8);
        _bss_start = .;
        *(.bss .bss.* .sbss .sbss.* COMMON)
        . = ALIGN(8);
        _bss_end = .;
    }

    . = ALIGN(16);
    . = . + 0x1000;
    _stack_end = .;
    _end = .;
}
