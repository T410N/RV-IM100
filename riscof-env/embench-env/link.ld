/* Embench memory map for RV-IM100.
 *
 * ROM is hardwired at 0x00000000 and data RAM at 0x10000000, and only ROM is
 * loaded from the program image, so .data is given a load address in ROM and
 * copied into RAM by crt_embench.S.
 *
 * DATA is 32 KB, the smallest RAM in the family (the RV32 5SP/6SP/7SP cores
 * decode ram_address as address[14:2] over 8192 words).  Benchmarks whose
 * working set exceeds that will not link, which is the correct outcome --
 * silently running a variant with a different memory size would invalidate
 * the comparison.
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

    .data : AT ( ADDR(.rodata) + SIZEOF(.rodata) ) {
        . = ALIGN(8);
        _data_start = .;
        *(.data .data.*)
        *(.sdata .sdata.*)
        . = ALIGN(8);
        _data_end = .;
    } > DATA
    _data_lma = LOADADDR(.data);
    _global_pointer = _data_start + 0x400;

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
