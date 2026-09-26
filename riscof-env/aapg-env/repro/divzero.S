        .section .text.init
        .globl  main
main:   la      sp, begin_signature
        li      a1, 0x123456789abcdef
        li      a2, 0
        div     t0, a1, a2          /* -> -1 */
        divu    t1, a1, a2          /* -> all ones */
        rem     t2, a1, a2          /* -> a1 */
        divw    t3, a1, a2          /* -> -1 */
        sd      t0, 0x00(sp)
        sd      t1, 0x08(sp)
        sd      t2, 0x10(sp)
        sd      t3, 0x18(sp)
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
