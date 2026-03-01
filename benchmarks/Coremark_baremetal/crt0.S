/*
 * crt0.S - Startup code for RV64I CoreMark
 */

    .section .text.init
    .global _start
    .type _start, @function

_start:
    /* Disable interrupts */
    csrw    mie, zero

    /* Initialize global pointer */
    .option push
    .option norelax
    la      gp, __global_pointer$
    .option pop

    /* Initialize stack pointer */
    la      sp, __stack_top

    /* Clear BSS section */
    la      t0, __bss_start
    la      t1, __bss_end
    bgeu    t0, t1, 2f
1:
    sd      zero, 0(t0)
    addi    t0, t0, 8
    bltu    t0, t1, 1b
2:

    /* Copy .data from ROM to RAM */
    la      t0, __data_load
    la      t1, __data_start
    la      t2, __data_end
    bgeu    t1, t2, 4f
3:
    ld      t3, 0(t0)
    sd      t3, 0(t1)
    addi    t0, t0, 8
    addi    t1, t1, 8
    bltu    t1, t2, 3b
4:

    /* Call main */
    li      a0, 0
    li      a1, 0
    call    main

    /* Infinite loop after main returns */
5:
    wfi
    j       5b

    .size _start, . - _start
