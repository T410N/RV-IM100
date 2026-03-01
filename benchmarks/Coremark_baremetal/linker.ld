/*
 * Linker script for RV64I CoreMark
 * Adjust ORIGIN and LENGTH for your target hardware
 */

OUTPUT_ARCH(riscv)
OUTPUT_FORMAT("elf64-littleriscv", "elf64-littleriscv", "elf64-littleriscv")
ENTRY(_start)

/* Memory layout - adjust for your hardware */
MEMORY
{
    ROM (rx)  : ORIGIN = 0x00000000, LENGTH = 64K
    RAM (rwx) : ORIGIN = 0x10000000, LENGTH = 32K
}

/* Stack and heap sizes */
__stack_size = DEFINED(__stack_size) ? __stack_size : 4K;
__heap_size  = DEFINED(__heap_size)  ? __heap_size  : 4K;

SECTIONS
{
    /* Code section in ROM */
    .text : ALIGN(8)
    {
        *(.text.init)
        *(.text .text.*)
        *(.rodata .rodata.*)
        . = ALIGN(8);
    } > ROM

    /* Initialized data - loaded in ROM, copied to RAM */
    .data : ALIGN(8)
    {
        __data_start = .;
        *(.data .data.*)
        *(.sdata .sdata.*)
        . = ALIGN(8);
        __data_end = .;
    } > RAM AT > ROM

    __data_load = LOADADDR(.data);

    /* Uninitialized data in RAM */
    .bss (NOLOAD) : ALIGN(8)
    {
        __bss_start = .;
        *(.bss .bss.*)
        *(.sbss .sbss.*)
        *(COMMON)
        . = ALIGN(8);
        __bss_end = .;
    } > RAM

    /* Heap */
    .heap (NOLOAD) : ALIGN(8)
    {
        __heap_start = .;
        . += __heap_size;
        __heap_end = .;
    } > RAM

    /* Stack */
    .stack (NOLOAD) : ALIGN(16)
    {
        __stack_bottom = .;
        . += __stack_size;
        __stack_top = .;
    } > RAM

    /* Global pointer for linker relaxation */
    __global_pointer$ = MIN(__data_start + 0x800, MAX(__data_start + 0x800, __bss_end - 0x800));
}
