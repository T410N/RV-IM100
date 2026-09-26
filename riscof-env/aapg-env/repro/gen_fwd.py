#!/usr/bin/env python3
"""Store-data forwarding reproducer.

    and  t6, s3, a0     <- producer
    <N nops>
    s{b,h,w,d} t6, off(sp)   <- consumer stores the freshly-produced value

The target word is seeded first, so a stale forward shows up as the seed
value surviving where the new byte should be.
"""
import sys
n = int(sys.argv[1]); width = sys.argv[2]
store = {"b":"sb","h":"sh","w":"sw","d":"sd"}[width]
nops = "\n".join(["        nop"]*n)
print(f'''        .section .text.init
        .globl  main
        .type   main, @function
main:
        la      sp, begin_signature
        li      t3, 0x00c0ffee00c0ffee
        sd      t3, 0x40(sp)
        nop
        nop
        nop
        nop
        nop
        nop
        nop
        nop
        li      s3, 0x1122334455667788
        li      a0, -1
        and     t6, s3, a0          /* t6 = 0x1122334455667788 */
{nops}
        {store}      t6, 0x40(sp)
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
