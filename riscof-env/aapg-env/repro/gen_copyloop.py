#!/usr/bin/env python3
"""Tight ld -> sd copy loop, the shape crt_dut.S uses to stage .data.

    1: ld   t3, 0(t0)
       sd   t3, 0(t1)      <- data comes from the immediately preceding load
       addi t0, t0, 8
       addi t1, t1, 8
       bltu t1, t2, 1b

Source is a known pattern in .rodata (so it lives in ROM, as the real copy
does); destination is the signature.  Every copied dword must match.
"""
import sys
n = int(sys.argv[1])          # dwords to copy
print(f'''        .section .text.init
        .globl  main
        .type   main, @function
main:
        la      t0, srcdata
        la      t1, begin_signature
        la      t2, begin_signature + {n*8}
1:      ld      t3, 0(t0)
        sd      t3, 0(t1)
        addi    t0, t0, 8
        addi    t1, t1, 8
        bltu    t1, t2, 1b
        j       write_tohost
write_tohost:
        li      t5, 1
        sw      t5, tohost, t4
1:      j       1b

        .section .rodata
        .align  4
srcdata:''')
for i in range(n):
    print(f"        .dword  0x{(0xA5A5000000000000 | (i*0x1111111 + 0x123456789)) & 0xFFFFFFFFFFFFFFFF:016x}")
print(f'''
        .data
        .align  4
        .globl  begin_signature
begin_signature:
        .fill   {n}, 8, 0
        .align  4
        .globl  end_signature
end_signature:''')
