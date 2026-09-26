#!/usr/bin/env python3
"""Two dependent divides, N instructions apart.

    divuw a3, s6, t6       first divide
    <N nops>
    divw  a6, t6, a3       second divide consumes the first's result

Taken from the AAPG case that diverges on 8SP: t6 = 0x37730000, and the
first divide yields a3 = 4, so divw must give 0x37730000/4 = 0x0DDCC000.
"""
import sys
n=int(sys.argv[1])
nops="\n".join(["        nop"]*n)
print(f'''        .section .text.init
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
{nops}
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
end_signature:''')
