/* Linker Script for RV32I46F_5SP Processor */
/* Memory Map:
 *   IMEM (ROM): 0x0000_0000 - 0x0000_FFFF (64KB)
 *   DMEM (RAM): 0x1000_0000 - 0x1000_7FFF (32KB)
 *   UART_TX:    0x1001_0000
 *   UART_STATUS:0x1001_0004
 */

OUTPUT_ARCH(riscv)
ENTRY(_start)

/* Memory regions */
MEMORY
{
    ROM (rx)  : ORIGIN = 0x00000000, LENGTH = 64K
    RAM (rwx) : ORIGIN = 0x10000000, LENGTH = 32K
}

/* Stack and Heap sizes (can be overridden by command line) */
__stack_size = DEFINED(__stack_size) ? __stack_size : 0x800;
__heap_size  = DEFINED(__heap_size)  ? __heap_size  : 0x1000;

SECTIONS
{
    /* Code section - placed in ROM */
    .text : ALIGN(4)
    {
        *(.text.init)
        *(.text.unlikely .text.unlikely.*)
        *(.text.startup .text.startup.*)
        *(.text .text.*)
        *(.gnu.linkonce.t.*)
    } > ROM

    /* Read-only data - placed in ROM */
    .rodata : ALIGN(4)
    {
        *(.rdata)
        *(.rodata .rodata.*)
        *(.gnu.linkonce.r.*)
        *(.srodata.cst16)
        *(.srodata.cst8)
        *(.srodata.cst4)
        *(.srodata.cst2)
        *(.srodata .srodata.*)
    } > ROM

    /* Small read-only data */
    .srodata : ALIGN(4)
    {
        *(.srodata .srodata.*)
    } > ROM

    /* End of ROM sections - used for data initialization */
    _etext = .;
    PROVIDE(etext = .);

    /* Initialized data - loaded from ROM, runs in RAM */
    .data : ALIGN(4)
    {
        _data_start = .;
        __DATA_BEGIN__ = .;
        *(.data .data.*)
        *(.gnu.linkonce.d.*)
        . = ALIGN(8);
        PROVIDE(__global_pointer$ = . + 0x800);
        *(.sdata .sdata.*)
        *(.sdata2 .sdata2.*)
        *(.gnu.linkonce.s.*)
        _data_end = .;
    } > RAM AT > ROM

    _data_load = LOADADDR(.data);

    /* Uninitialized data - in RAM */
    .bss (NOLOAD) : ALIGN(4)
    {
        _bss_start = .;
        __BSS_START__ = .;
        *(.sbss .sbss.*)
        *(.gnu.linkonce.sb.*)
        *(.bss .bss.*)
        *(.gnu.linkonce.b.*)
        *(COMMON)
        . = ALIGN(4);
        _bss_end = .;
        __BSS_END__ = .;
    } > RAM

    /* Heap section */
    .heap (NOLOAD) : ALIGN(8)
    {
        PROVIDE(__heap_start = .);
        PROVIDE(_heap_start = .);
        . = . + __heap_size;
        PROVIDE(__heap_end = .);
        PROVIDE(_heap_end = .);
    } > RAM

    /* Stack section - at the end of RAM */
    .stack (NOLOAD) : ALIGN(16)
    {
        PROVIDE(__stack_bottom = .);
        . = . + __stack_size;
        PROVIDE(__stack_top = .);
        PROVIDE(_sp = .);
    } > RAM

    /* Provide end of used RAM */
    _end = .;
    PROVIDE(end = .);
}
