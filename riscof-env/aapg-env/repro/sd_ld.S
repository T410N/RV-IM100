/* Minimal reproducer: a store immediately followed by a load.
 *
 * Expected: memory at sig+0x40 holds the stored pattern; sig+0x08 is
 * untouched and still holds its initial value.
 */
        .section .text.init
        .globl  main
        .type   main, @function
main:
        la      sp, begin_signature
        li      s1, 0x1122334455667788
        sd      s1, 0x40(sp)          /* store  -> sig+0x40 */
        ld      s6, 0x08(sp)          /* load   <- sig+0x08 (must not write) */
        j       write_tohost
write_tohost:
        li      t5, 1
        sw      t5, tohost, t4
1:      j       1b

        .data
        .align  4
        .globl  begin_signature
begin_signature:
        .dword  0xdead0000dead0000    /* +0x00 */
        .dword  0xdead0008dead0008    /* +0x08  <- the load target */
        .dword  0xdead0010dead0010
        .dword  0xdead0018dead0018
        .dword  0xdead0020dead0020
        .dword  0xdead0028dead0028
        .dword  0xdead0030dead0030
        .dword  0xdead0038dead0038
        .dword  0xdead0040dead0040    /* +0x40  <- the store target */
        .dword  0xdead0048dead0048
        .dword  0xdead0050dead0050
        .dword  0xdead0058dead0058
        .align  4
        .globl  end_signature
end_signature:
