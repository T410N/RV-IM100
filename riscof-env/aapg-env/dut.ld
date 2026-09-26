/* AAPG program layout for the RV-IM100 DUTs.
 *
 * AAPG's own script puts .text at 0 and the signature block at 0x80091000.
 * objcopy over that span would emit a 2 GB image of mostly padding, so the
 * signature is relocated into the cores' RAM at 0x10000000 and given a load
 * address in ROM directly after .text.  crt_dut.S copies it down before it
 * reads the register seeds out of it.
 *
 * The seed block is 16 KB (2048 dwords), and RAM is 32 KB on the smallest
 * variant, which leaves 16 KB for the stack the trap handler pushes onto.
 */

OUTPUT_ARCH("riscv")
ENTRY(_start)

MEMORY
{
    CODE (rx) : ORIGIN = 0x00000000, LENGTH = 2M
    DATA (rw) : ORIGIN = 0x10000000, LENGTH = 32K
}

SECTIONS
{
    .text.init : { *(.text.init) } > CODE
    .text      : { *(.text .text.*) . = ALIGN(8); } > CODE
    .rodata    : { . = ALIGN(8); *(.rodata .rodata.* rodata) . = ALIGN(8); } > CODE

    /* Register seeds + signature: loaded in ROM, copied into RAM at boot. */
    .data : AT ( ADDR(.rodata) + SIZEOF(.rodata) ) {
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
        . = ALIGN(8);
        _data_start = .;
        . = . + 0x800;
        *(begin_signature*)
        *(.data .data.*)
        *(.sdata .sdata.*)
        . = ALIGN(8);
        . = . + 0x800;
        _data_end = .;
    } > DATA
    _data_lma = LOADADDR(.data);

    .bss (NOLOAD) : {
        . = ALIGN(8);
        _bss_start = .;
        *(.bss .bss.* .sbss .sbss.* COMMON)
        . = ALIGN(8);
        _bss_end = .;
    } > DATA

    . = ALIGN(16);
    . = . + 0x1000;
    _stack_end = .;
    _end = .;
}

/* The generated program ends with `sw t5, tohost, t4`.  Pointing tohost at
   the halt MMIO address turns AAPG's own exit into the halt sim_top watches,
   so the program body needs no patching at all. */
tohost = 0x10010000;
