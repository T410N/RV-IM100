        .section .text.init
        .globl  main
        .type   main, @function
main:
        la      sp, begin_signature
        li      s1, 0xe5997aff
        li      a3, 1
        li      t6, 0x37730000
        li      s9, 0
        nop
        nop
        nop
        nop
        mulw    s6, s1, a3          /* s6 = 0xffffffffe5997aff */
        nop
        nop
        sw      s9, 0x20(sp)
        nop
        nop
        divuw   a3, s6, t6          /* a3 = 4 */
        nop
        nop
        divw    a6, t6, a3          /* must be 0x0DDCC000 */
        nop
        nop
        nop
        nop
        sd      a6, 0x00(sp)
        sd      a3, 0x08(sp)
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
