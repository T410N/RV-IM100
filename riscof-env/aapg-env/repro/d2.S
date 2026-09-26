        .section .text.init
        .globl  main
        .type   main, @function
main:
        la      sp, begin_signature
        li      t6, 0x37730000
        li      s6, 0xdef12345
        nop
        nop
        nop
        nop
        divuw   a3, s6, t6          /* first divide  */
        nop
        nop
        nop
        nop
        divw    a6, t6, a3          /* second divide, depends on a3 */
        nop
        nop
        nop
        nop
        sd      a3, 0x00(sp)
        sd      a6, 0x08(sp)
        j       write_tohost
write_tohost:
        li      t5, 1
        sw      t5, tohost, t4
1:      j       1b
        .data
        .align  4
        .globl  begin_signature
begin_signature: .fill 8, 8, 0
        .align  4
        .globl  end_signature
end_signature:
