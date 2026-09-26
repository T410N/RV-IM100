#ifndef _COMPLIANCE_MODEL_H
#define _COMPLIANCE_MODEL_H

/* RV-IM100 model hooks for riscv-arch-test.
 *
 * Boot does three things the cores cannot do for themselves: copy .data from
 * its load address in ROM into RAM (there is no loader, and the harness only
 * writes the ROM image), zero .bss, and install a trap vector.
 *
 * The nops around every CSR access are deliberate.  The CSR read path takes
 * two cycles and is not interlocked against a preceding register write, so
 * `la t0, X` immediately followed by `csrw mtvec, t0` reads a stale t0 on the
 * deeper pipelines.  Padding here rather than in the RTL keeps the design
 * under test byte-identical to what was synthesized.  Nothing else in this
 * file pads, so ordinary data hazards are still exercised by the tests.
 */

/* No tohost/fromhost pair: the suite never references them, and halting is a
 * store to the MMIO address below, which sim_top snoops on the core's store
 * taps.  Emitting them would only create an orphan section for the linker. */
#define RVMODEL_DATA_SECTION

#define RVMODEL_HALT                                                          \
    .option push;                                                             \
    .option norvc;                                                            \
    li t1, 1;                                                                 \
    li t2, 0x10010000;                                                        \
    nop; nop; nop; nop;                                                       \
rvmodel_halt_loop:                                                            \
    sw t1, 0(t2);                                                             \
    j rvmodel_halt_loop;                                                      \
    .option pop;                                                              \
    .align 3;                                                                 \
    /* Placed after the halt loop so sequential fetch never reaches the mret */\
rvmodel_trap_vector:                                                          \
    csrr t0, mepc;                                                            \
    nop; nop; nop; nop;                                                       \
    addi t0, t0, 4;                                                           \
    csrw mepc, t0;                                                            \
    nop; nop; nop; nop;                                                       \
    mret;

#define RVMODEL_BOOT                                                          \
    .section .text.init;                                                      \
    .align 3;                                                                 \
    .globl _start;                                                            \
    .option norvc;                                                            \
_start:                                                                       \
    /* .data lives in ROM at _data_lma; copy it down to RAM */                \
    la   t0, _data_lma;                                                       \
    la   t1, _data_start;                                                     \
    la   t2, _data_end;                                                       \
rvmodel_copy_data:                                                            \
    bgeu t1, t2, rvmodel_zero_bss;                                            \
    LREG t3, 0(t0);                                                           \
    SREG t3, 0(t1);                                                           \
    addi t0, t0, REGWIDTH;                                                    \
    addi t1, t1, REGWIDTH;                                                    \
    j    rvmodel_copy_data;                                                   \
rvmodel_zero_bss:                                                             \
    la   t0, _bss_start;                                                      \
    la   t1, _bss_end;                                                        \
rvmodel_bss_loop:                                                             \
    bgeu t0, t1, rvmodel_boot_done;                                           \
    SREG x0, 0(t0);                                                           \
    addi t0, t0, REGWIDTH;                                                    \
    j    rvmodel_bss_loop;                                                    \
rvmodel_boot_done:                                                            \
    la   sp, _stack_end;                                                      \
    la   t0, rvmodel_trap_vector;                                             \
    nop; nop; nop; nop;                                                       \
    csrw mtvec, t0;                                                           \
    nop; nop; nop; nop;

#define RVMODEL_DATA_BEGIN                                                    \
    RVMODEL_DATA_SECTION                                                      \
    .align 4; .global begin_signature; begin_signature:

#define RVMODEL_DATA_END                                                      \
    .align 4; .global end_signature; end_signature:

/* No interrupt controller in these designs. */
#define RVMODEL_SET_MSW_INT
#define RVMODEL_CLEAR_MSW_INT
#define RVMODEL_CLEAR_MTIMER_INT
#define RVMODEL_CLEAR_MEXT_INT
#define RVMODEL_SET_NMI
#define RVMODEL_CLEAR_NMI
#define RVMODEL_SET_MEXT_INT
#define RVMODEL_SET_MTIMER_INT

#define RVMODEL_IO_INIT
#define RVMODEL_IO_WRITE_STR(_SP, _STR)
#define RVMODEL_IO_CHECK()
#define RVMODEL_IO_ASSERT_GPR_EQ(_SP, _R, _I)
#define RVMODEL_IO_ASSERT_SFPR_EQ(_F, _R, _I)
#define RVMODEL_IO_ASSERT_DFPR_EQ(_D, _R, _I)

#endif /* _COMPLIANCE_MODEL_H */
