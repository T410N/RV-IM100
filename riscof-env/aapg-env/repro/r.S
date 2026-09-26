/* Store -> load reproducer, 0 nop(s) of separation.
 *
 * The load must not modify memory.  On the affected variants the preceding
 * store's data is written a second time, at the load's address.
 */
        .section .text.init
        .globl  main
        .type   main, @function
main:
        la      sp, begin_signature
        li      t3, 0x00c0ffee00c0ffee
        sd      t3, 0x08(sp)          /* seed the load target with a known value */
        nop
        nop
        nop
        nop
        nop
        nop
        nop
        nop
        li      s1, 0x1122334455667788
        sd      s1, 0x40(sp)          /* the store   */

        ld      s6, 0x08(sp)          /* the load    */
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
