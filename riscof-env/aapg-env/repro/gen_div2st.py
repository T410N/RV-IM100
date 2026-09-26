#!/usr/bin/env python3
"""divuw (multi-cycle) shortly before two stores; second store must land."""
import sys
gap_div=int(sys.argv[1]); gap_st=int(sys.argv[2])
f1="\n".join(["        add     a4, a4, zero"]*gap_div)
f2="\n".join(["        add     a4, a4, zero"]*gap_st)
print(f'''        .section .text.init
        .globl  main
        .type   main, @function
main:
        la      sp, begin_signature
        li      t3, 0x1111111111111111
        li      t5, 0x33
        sd      t3, 0x00(sp)
        sd      t3, 0x40(sp)
        nop
        nop
        nop
        nop
        li      s0, 0x123456789
        li      s4, 0x7
        divuw   a3, s0, s4          /* multi-cycle, stalls the pipe */
{f1}
        li      t4, 0x2222222222222222
        sd      t4, 0x00(sp)        /* store 1 */
{f2}
        sb      t5, 0x40(sp)        /* store 2 -- must land */
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
