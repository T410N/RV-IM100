        .section .text.init
        .globl  main
        .type   main, @function
main:
        la      sp, begin_signature
        li      t3, 0x1111111111111111
        li      t4, 0x2222222222222222
        li      t5, 0x33
        sd      t3, 0x00(sp)         /* seed A */
        sd      t3, 0x40(sp)         /* seed B */
        nop
        nop
        nop
        nop
        nop
        nop
        nop
        nop
        sd      t4, 0x00(sp)         /* store 1 -> A must become 2222... */
        add     a4, a4, zero
        add     a4, a4, zero
        add     a4, a4, zero
        sb      t5, 0x40(sp)         /* store 2 -> B low byte must become 0x33 */
        j       write_tohost
write_tohost:
        li      t5, 1
        sw      t5, tohost, t4
1:      j       1b

        .data
        .align  4
        .globl  begin_signature
begin_signature:
        .fill   16, 8, 0
        .align  4
        .globl  end_signature
end_signature:
