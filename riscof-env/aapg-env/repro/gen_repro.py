#!/usr/bin/env python3
"""Emit the store->load reproducer with N nops between the store and the load."""
import sys
n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
nops = "\n".join(["        nop"] * n)
print(f'''/* Store -> load reproducer, {n} nop(s) of separation.
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
{nops}
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
end_signature:''')
