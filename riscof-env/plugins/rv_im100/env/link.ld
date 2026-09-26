/* RV-IM100 memory map for architectural tests.
 *
 * The cores have no external bus: instruction ROM is hardwired at 0x00000000
 * and data RAM at 0x10000000, both inside the core.  Only ROM is loaded from
 * the program image, so .data is given a load address in ROM and copied into
 * RAM by the boot code in model_test.h.  That keeps the harness independent of
 * how each variant shapes its RAM internally.
 *
 * DATA is capped at 32 KB: the RV32 5SP/6SP/7SP cores decode ram_address as
 * address[14:2] over 8192 words, which is the smallest RAM in the family.
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

    .text : {
        *(.text .text.*)
        . = ALIGN(8);
    } > CODE

    .rodata : {
        . = ALIGN(8);
        *(.rodata .rodata.* .srodata .srodata.*)
        . = ALIGN(8);
    } > CODE

    /* Loaded into ROM immediately after .rodata, copied to RAM at boot. */
    .data : AT ( ADDR(.rodata) + SIZEOF(.rodata) ) {
        . = ALIGN(8);
        _data_start = .;
        *(.data .data.*)
        *(.sdata .sdata.*)
        . = ALIGN(8);
        _data_end = .;
    } > DATA
    _data_lma = LOADADDR(.data);

    .bss (NOLOAD) : {
        . = ALIGN(8);
        _bss_start = .;
        *(.bss .bss.*)
        *(.sbss .sbss.*)
        *(COMMON)
        . = ALIGN(8);
        _bss_end = .;
    } > DATA

    . = ALIGN(16);
    _stack_start = .;
    . = . + 0x1000;
    _stack_end = .;

    _end = .;
}
