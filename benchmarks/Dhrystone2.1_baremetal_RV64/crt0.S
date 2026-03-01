/*
 * crt0.S - C Runtime Startup for RV64I
 * 
 * Entry point: _start
 * 1. Initialize stack pointer
 * 2. Initialize global pointer
 * 3. Copy .data from ROM to RAM
 * 4. Clear .bss section
 * 5. Call main()
 * 6. Loop forever on return
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

    /* Copy .data section from ROM to RAM (8-byte aligned) */
    la      a0, _data_start      /* destination (RAM) */
    la      a1, _data_load       /* source (ROM) */
    la      a2, _data_end        /* end of destination */
    bgeu    a0, a2, 2f           /* skip if empty */
1:
    ld      t0, 0(a1)
    sd      t0, 0(a0)
    addi    a0, a0, 8
    addi    a1, a1, 8
    bltu    a0, a2, 1b
2:

    /* Clear .bss section (8-byte aligned) */
    la      a0, _bss_start
    la      a1, _bss_end
    bgeu    a0, a1, 4f           /* skip if empty */
3:
    sd      zero, 0(a0)
    addi    a0, a0, 8
    bltu    a0, a1, 3b
4:

    /* Set argc = 0, argv = NULL, envp = NULL */
    li      a0, 0
    li      a1, 0
    li      a2, 0

    /* Call main */
    call    main

    /* If main returns, loop forever */
    .global _exit
    .type _exit, @function
_exit:
    j       _exit

    .size _start, .-_start
