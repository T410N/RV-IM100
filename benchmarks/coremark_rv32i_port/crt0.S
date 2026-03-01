/*
 * crt0.S - C Runtime Startup for RV32I46F_5SP
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
    /* Note: mstatus is read-only in this implementation, skip interrupt disable */
    /* csrci   mstatus, 0x8 */

    /* Initialize global pointer */
    .option push
    .option norelax
    la      gp, __global_pointer$
    .option pop

    /* Initialize stack pointer */
    la      sp, __stack_top

    /* Copy .data section from ROM to RAM */
    la      a0, _data_start      /* destination (RAM) */
    la      a1, _data_load       /* source (ROM) */
    la      a2, _data_end        /* end of destination */
    bgeu    a0, a2, 2f           /* skip if empty */
1:
    lw      t0, 0(a1)
    sw      t0, 0(a0)
    addi    a0, a0, 4
    addi    a1, a1, 4
    bltu    a0, a2, 1b
2:

    /* Clear .bss section */
    la      a0, _bss_start
    la      a1, _bss_end
    bgeu    a0, a1, 4f           /* skip if empty */
3:
    sw      zero, 0(a0)
    addi    a0, a0, 4
    bltu    a0, a1, 3b
4:

    /* Call global constructors (C++) - skip if not needed */
    /* la      a0, __libc_init_array */
    /* jalr    a0 */

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
