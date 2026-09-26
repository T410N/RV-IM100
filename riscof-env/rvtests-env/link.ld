/* riscv-tests memory map for RV-IM100.
 *
 * Same shape as the architectural-test script: ROM is hardwired at
 * 0x00000000 and data RAM at 0x10000000, and only ROM is loaded from the
 * program image.  .data therefore gets a load address in ROM and is copied
 * into RAM by the reset vector in riscv_test.h.
 *
 * riscv-tests puts its test vectors in .data and reads them during the run,
 * so that copy is not optional here the way it nearly is for the arch tests.
 *
 * DATA is capped at 32 KB to match the smallest RAM in the family (the RV32
 * 5SP/6SP/7SP cores decode ram_address as address[14:2] over 8192 words).
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

    /* Loaded into ROM after .rodata, copied to RAM by the reset vector. */
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
    . = . + 0x1000;
    _stack_end = .;

    _end = .;
}
