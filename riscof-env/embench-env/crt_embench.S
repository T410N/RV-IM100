/* Startup for Embench on RV-IM100.
 *
 * Same shape as the architectural-test and riscv-tests boot code: there is no
 * loader, so .data is copied out of ROM into RAM before anything runs.  After
 * main() returns, the timed-region counters and the pass/fail result are
 * printed over the UART and the run is ended with a store to the halt address.
 */
        .section .text.init, "ax"
        .globl  _start
        .type   _start, @function
_start:
        /* copy .data from its load address in ROM into RAM */
        la      t0, _data_lma
        la      t1, _data_start
        la      t2, _data_end
1:      bgeu    t1, t2, 2f
#if __riscv_xlen == 64
        ld      t3, 0(t0)
        sd      t3, 0(t1)
        addi    t0, t0, 8
        addi    t1, t1, 8
#else
        lw      t3, 0(t0)
        sw      t3, 0(t1)
        addi    t0, t0, 4
        addi    t1, t1, 4
#endif
        j       1b
2:      /* zero .bss */
        la      t0, _bss_start
        la      t1, _bss_end
3:      bgeu    t0, t1, 4f
#if __riscv_xlen == 64
        sd      zero, 0(t0)
        addi    t0, t0, 8
#else
        sw      zero, 0(t0)
        addi    t0, t0, 4
#endif
        j       3b
4:      la      sp, _stack_end
        la      gp, _global_pointer
        li      a0, 0
        li      a1, 0
        call    main
        mv      s0, a0                 /* 0 == benchmark verified */

        /* report: "EMBENCH <cycles> <instret> <ok|BAD>\n" */
        la      a0, msg_tag
        call    puts_
        la      t0, bench_cycles
#if __riscv_xlen == 64
        ld      a0, 0(t0)
#else
        lw      a0, 0(t0)
#endif
        call    puthex
        li      a0, ' '
        call    putc
        la      t0, bench_instret
#if __riscv_xlen == 64
        ld      a0, 0(t0)
#else
        lw      a0, 0(t0)
#endif
        call    puthex
        li      a0, ' '
        call    putc
        beqz    s0, 5f
        la      a0, msg_bad
        j       6f
5:      la      a0, msg_ok
6:      call    puts_
        li      a0, '\n'
        call    putc

        /* End of run.  A distinct address from the UART so the printing above
           does not look like a completion signal to the testbench; the SoC
           decodes it as neither RAM nor ROM, so it is inert on hardware. */
        li      t1, 1
        li      t2, 0x10012000
        nop
        nop
        nop
        nop
7:      sw      t1, 0(t2)
        j       7b

/* --- tiny UART helpers (0x10010000 is the transmit register) -------------- */
putc:
        li      t0, 0x10010000
        sw      a0, 0(t0)
        ret

puts_:
        mv      t3, a0
1:      lbu     a0, 0(t3)
        beqz    a0, 2f
        li      t0, 0x10010000
        sw      a0, 0(t0)
        addi    t3, t3, 1
        j       1b
2:      ret

/* Hexadecimal print of the value in a0.
 *
 * Hex rather than decimal deliberately: decimal conversion needs a divide,
 * and these binaries also run on the I-only cores where div/rem do not exist.
 * Shifts and masks are available everywhere, so one routine serves the whole
 * family.  The harness parses the hex.  */
puthex:
        mv      t3, a0
        la      t4, numbuf
        addi    t5, t4, 20
        sb      zero, 0(t5)
        bnez    t3, 1f
        addi    t5, t5, -1
        li      t6, '0'
        sb      t6, 0(t5)
        j       3f
1:      beqz    t3, 3f
        andi    t0, t3, 15
        srli    t3, t3, 4
        li      t6, 10
        blt     t0, t6, 2f
        addi    t0, t0, 'a' - 10
        j       9f
2:      addi    t0, t0, '0'
9:      addi    t5, t5, -1
        sb      t0, 0(t5)
        j       1b
3:      mv      a0, t5
        j       puts_

        .section .rodata
msg_tag: .asciz "EMBENCH "
msg_ok:  .asciz "ok"
msg_bad: .asciz "BAD"

        .section .bss
        .align 3
numbuf: .space 32
