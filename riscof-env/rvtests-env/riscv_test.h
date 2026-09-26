#ifndef _ENV_RV_IM100_H
#define _ENV_RV_IM100_H

/* riscv-tests environment for the RV-IM100 family.
 *
 * Replaces env/p/riscv_test.h.  Upstream's version targets a Spike-like
 * machine with an HTIF tohost pipe, PMP, supervisor mode and a full trap
 * delegation setup; none of that exists in these cores.  Four adaptations,
 * each forced by something the RTL actually does:
 *
 *  1. RISCV_MULTICORE_DISABLE is dropped.  It spins on `csrr a0, mhartid;
 *     bnez a0, 1b`.  These cores do not implement mhartid and return garbage
 *     (0x42414E414E414E41 on the 64-bit designs), so every test would hang in
 *     that loop before reaching a single instruction under test.
 *
 *  2. The reset vector's trailing `mret` is dropped.  Upstream uses it to fall
 *     into the test body via mepc.  Nothing here needs the privilege
 *     transition -- we never leave M-mode -- and relying on the family's mret
 *     return semantics to land on an exact instruction is a needless risk, so
 *     the reset vector falls through instead.
 *
 *  3. The memory map is retargeted from 0x80000000 to ROM at 0x00000000 and
 *     RAM at 0x10000000, with .data copied out of ROM at boot.  See link.ld.
 *
 *  4. Pass/fail no longer goes ecall -> trap -> tohost.  It is a direct store
 *     of TESTNUM to 0x10010000, which sim_top snoops on the core's store taps
 *     and reports as halt_code.  There is no HTIF and no ecall handler worth
 *     building for a one-bit result.
 *
 * PMP, satp, medeleg/mideleg, mnstatus and stvec setup are all removed: those
 * CSRs are unimplemented family-wide, and writing them is at best a no-op.
 *
 * The nops around CSR accesses are deliberate, and match the arch-test model
 * header: the CSR read path is two cycles and is not interlocked against a
 * preceding register write, so `la t0, X` immediately followed by
 * `csrw mtvec, t0` reads a stale t0 on the deeper pipelines.  Padding here
 * rather than in the RTL keeps the design under test byte-identical to what
 * was synthesized.  Nothing in the test bodies is padded, so ordinary data
 * hazards are still fully exercised.
 */

#include "encoding.h"

#define TESTNUM gp

#define RVMODEL_TOHOST 0x10010000

/*----------------------------------------------------------------------*/
/* init: the tests invoke `init` after RVTEST_CODE_BEGIN.  Every variant  */
/* here is M-mode integer-only, so all four flavours are empty.           */
/*----------------------------------------------------------------------*/

#define RVTEST_RV32U  .macro init; .endm
#define RVTEST_RV64U  .macro init; .endm
#define RVTEST_RV32M  .macro init; .endm
#define RVTEST_RV64M  .macro init; .endm
#define RVTEST_RV32S  .macro init; .endm
#define RVTEST_RV64S  .macro init; .endm

#define EXTRA_TVEC_USER
#define EXTRA_TVEC_MACHINE
#define EXTRA_INIT
#define EXTRA_INIT_TIMER
#define EXTRA_DATA
#define FILTER_TRAP
#define FILTER_PAGE_FAULT

#define INIT_XREG                                                       \
  li x1, 0; li x2, 0; li x3, 0; li x4, 0; li x5, 0; li x6, 0;            \
  li x7, 0; li x8, 0; li x9, 0; li x10,0; li x11,0; li x12,0;            \
  li x13,0; li x14,0; li x15,0; li x16,0; li x17,0; li x18,0;            \
  li x19,0; li x20,0; li x21,0; li x22,0; li x23,0; li x24,0;            \
  li x25,0; li x26,0; li x27,0; li x28,0; li x29,0; li x30,0;            \
  li x31,0;

#if __riscv_xlen == 64
# define LREG ld
# define SREG sd
# define REGWIDTH 8
#else
# define LREG lw
# define SREG sw
# define REGWIDTH 4
#endif

/*----------------------------------------------------------------------*/
/* Halt: store TESTNUM to the tohost MMIO address and spin.              */
/* 1 means pass; anything else is a failure code the testbench reports.  */
/*----------------------------------------------------------------------*/

#define RVTEST_HALT                                                     \
        li t2, RVMODEL_TOHOST;                                          \
        nop; nop; nop; nop;                                             \
1:      sw TESTNUM, 0(t2);                                              \
        j 1b;

#define RVTEST_CODE_BEGIN                                               \
        .section .text.init;                                            \
        .align  6;                                                      \
        .weak stvec_handler;                                            \
        .weak mtvec_handler;                                            \
        .globl _start;                                                  \
_start:                                                                 \
        j reset_vector;                                                 \
        .align 2;                                                       \
trap_vector:                                                            \
        /* Any trap that reaches here is unexpected.  If the test        \
           supplied its own mtvec_handler, defer to it; otherwise fail   \
           with a code that cannot be mistaken for a pass. */            \
        la t5, mtvec_handler;                                           \
        beqz t5, 1f;                                                    \
        jr t5;                                                          \
1:      ori TESTNUM, TESTNUM, 1337;                                     \
        RVTEST_HALT;                                                    \
reset_vector:                                                           \
        INIT_XREG;                                                      \
        /* copy .data out of ROM into RAM -- there is no loader */       \
        la   t0, _data_lma;                                             \
        la   t1, _data_start;                                           \
        la   t2, _data_end;                                             \
rvtest_copy_data:                                                       \
        bgeu t1, t2, rvtest_zero_bss;                                   \
        LREG t3, 0(t0);                                                 \
        SREG t3, 0(t1);                                                 \
        addi t0, t0, REGWIDTH;                                          \
        addi t1, t1, REGWIDTH;                                          \
        j    rvtest_copy_data;                                          \
rvtest_zero_bss:                                                        \
        la   t0, _bss_start;                                            \
        la   t1, _bss_end;                                              \
rvtest_bss_loop:                                                        \
        bgeu t0, t1, rvtest_boot_done;                                  \
        SREG x0, 0(t0);                                                 \
        addi t0, t0, REGWIDTH;                                          \
        j    rvtest_bss_loop;                                           \
rvtest_boot_done:                                                       \
        la   sp, _stack_end;                                            \
        li TESTNUM, 0;                                                  \
        la t0, trap_vector;                                             \
        nop; nop; nop; nop;                                             \
        csrw mtvec, t0;                                                 \
        nop; nop; nop; nop;                                             \
        init;                                                           \
        EXTRA_INIT;                                                     \
        EXTRA_INIT_TIMER;

#define RVTEST_CODE_END                                                 \
        /* falling off the end of a test is a failure, not a trap */     \
        ori TESTNUM, TESTNUM, 1337;                                     \
        RVTEST_HALT

#define RVTEST_PASS                                                     \
        fence;                                                          \
        li TESTNUM, 1;                                                  \
        RVTEST_HALT

#define RVTEST_FAIL                                                     \
        fence;                                                          \
1:      beqz TESTNUM, 1b;                                               \
        sll TESTNUM, TESTNUM, 1;                                        \
        or TESTNUM, TESTNUM, 1;                                         \
        RVTEST_HALT

/*----------------------------------------------------------------------*/
/* Data section.  No .tohost/.fromhost pair: there is no HTIF, and
   emitting them would only create an orphan section for the linker. */
/*----------------------------------------------------------------------*/

#define RVTEST_DATA_BEGIN                                               \
        EXTRA_DATA                                                      \
        .align 4; .global begin_signature; begin_signature:

#define RVTEST_DATA_END                                                 \
        .align 4; .global end_signature; end_signature:

#endif /* _ENV_RV_IM100_H */
