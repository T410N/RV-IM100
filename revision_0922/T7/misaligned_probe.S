# Misaligned-access probe.  Results at RES (0x10000200), one XLEN word each:
#   for each probe: loaded value, mcause seen (0 = no trap)
# then the 16 bytes of the store area after the misaligned stores.
#define NOPS nop; nop; nop; nop; nop
    .section .text.init
    .globl _start
_start:
    la    t0, handler
    csrw  mtvec, t0
    NOPS
    li    s0, 0x10000100        # data area
    li    s1, 0x10000200        # results
    li    t1, 0x44332211
    sw    t1, 0(s0)
    li    t1, 0x88776655
    sw    t1, 4(s0)
    li    t1, 0xccbbaa99
    sw    t1, 8(s0)
    li    t1, 0x00ffeedd
    sw    t1, 12(s0)
    NOPS
#define PROBE(...) li a1, 0; li a0, 0; NOPS; __VA_ARGS__; NOPS; SREG a0, 0(s1); SREG a1, XB(s1); addi s1, s1, 2*XB
    PROBE(lh a0, 1(s0))
    PROBE(lh a0, 3(s0))
    PROBE(lw a0, 1(s0))
    PROBE(lw a0, 2(s0))
    PROBE(lhu a0, 5(s0))
#if XB == 8
    PROBE(ld a0, 4(s0))
    PROBE(ld a0, 1(s0))
    PROBE(lwu a0, 6(s0))
#endif
    li    t1, 0x5a5a5a5a
    li a1, 0; NOPS; sh t1, 1(s0); NOPS; SREG a1, 0(s1); addi s1, s1, XB
    li a1, 0; NOPS; sw t1, 6(s0); NOPS; SREG a1, 0(s1); addi s1, s1, XB
    li a1, 0; NOPS; sh t1, 11(s0); NOPS; SREG a1, 0(s1); addi s1, s1, XB
    NOPS
    lw t2, 0(s0);  NOPS; SREG t2, 0(s1); addi s1, s1, XB
    lw t2, 4(s0);  NOPS; SREG t2, 0(s1); addi s1, s1, XB
    lw t2, 8(s0);  NOPS; SREG t2, 0(s1); addi s1, s1, XB
    lw t2, 12(s0); NOPS; SREG t2, 0(s1); addi s1, s1, XB
    NOPS
    li t0, 0x10010000
    li t1, 1
    sw t1, 0(t0)
1:  j 1b
    .align 4
handler:
    csrr  a1, mcause
    NOPS
    csrr  t3, mepc
    NOPS
    addi  t3, t3, 4
    csrw  mepc, t3
    NOPS
    mret
