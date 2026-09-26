#!/usr/bin/env python3
"""Exact shape from the AAPG divergence: mulw, store, divuw, divw.

    mulw  s6, s1, a3     multiplier
    sw    s9, 0(sp)
    divuw a3, s6, t6     divider, consumes the multiply
    divw  a6, t6, a3     divider, consumes the previous divide

Register values are the ones the trace shows at that point, so the
arithmetic is identical: a3 = 4 and a6 must be 0x37730000/4 = 0x0DDCC000.
"""
import sys
g1=int(sys.argv[1]); g2=int(sys.argv[2]); g3=int(sys.argv[3])
f=lambda n: "\n".join(["        nop"]*n)
print(f'''        .section .text.init
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
{f(g1)}
        sw      s9, 0x20(sp)
{f(g2)}
        divuw   a3, s6, t6          /* a3 = 4 */
{f(g3)}
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
end_signature:''')
