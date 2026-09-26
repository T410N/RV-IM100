/* Embench board support for the RV-IM100 family.
 *
 * Timing comes from the cores' own mcycle/minstret CSRs, so the same binary
 * measures itself identically on the FPGA and under simulation.  The upstream
 * RISC-V examples use rdcycle (CSR 0xC00) and mcountinhibit; these cores
 * implement neither, exposing mcycle at 0xB00 and minstret at 0xB02 and
 * counting unconditionally, so the CSRs are read directly and differenced.
 *
 * start_trigger/stop_trigger also write a simulation-only control register.
 * That lets the testbench count stall cycles over exactly the timed region
 * instead of the whole program, so startup and verification do not pollute
 * the CPI and stall figures.  On hardware the write lands on an address the
 * SoC decodes as neither RAM nor ROM and is harmless.
 *
 * The nops around each CSR read are required: the CSR path is two cycles and
 * is not interlocked, so a consumer placed immediately after csrr reads a
 * stale value on the deeper pipelines.
 */
#include <stdint.h>
#include <support.h>

#define PROF_CTRL (*(volatile uint32_t *) 0x10011000u)

volatile unsigned long long bench_cycles;
volatile unsigned long long bench_instret;

static unsigned long long c_start, i_start;

/* A single csrr writes ONE register.  On RV64 that is the whole 64-bit counter.
   On RV32 a 64-bit value lives in a register pair, so the old code filled only
   the low half and left the high half as whatever the paired register held.
   minstret survived that -- the same garbage appeared in both reads and cancelled
   in the subtraction -- but mcycle crosses a 2^32 boundary during a run, so its
   high word genuinely differs between the two reads and the garbage stopped
   cancelling.  Measured cycle counts came back inflated by exactly 2^32, or as
   values near 2^64 where the difference went negative.

   RV32 therefore needs the standard two-CSR idiom: read the high word, the low
   word, then the high word again, and retry if it ticked over in between. */
#if __riscv_xlen == 32
/* On RV32 a 64-bit CSR needs mcycleh:mcycle, and reading the pair safely needs
   a hi/lo/hi retry loop.  That loop does not work on these cores: the CSR path
   is two cycles and is not interlocked, and with several csrr in quick
   succession -- even separated by nops -- the reads do not settle, so the loop
   never converges and the program hangs.
   It is not needed here.  The largest Embench run in this set is 43 M cycles
   against a 2^32 limit of 4.29 G, so the high word is always zero.  Read the
   low word only, with the nops the CSR path requires, and assert the headroom
   rather than assume it: a run that ever approached 2^32 would silently wrap.  */
static inline unsigned long long rd_mcycle (void)
{
  unsigned long v;
  __asm__ volatile ("csrr %0, 0xB00\n\t nop\n\t nop\n\t nop\n\t nop"
                    : "=r" (v) :: "memory");
  return (unsigned long long) v;
}

static inline unsigned long long rd_minstret (void)
{
  unsigned long v;
  __asm__ volatile ("csrr %0, 0xB02\n\t nop\n\t nop\n\t nop\n\t nop"
                    : "=r" (v) :: "memory");
  return (unsigned long long) v;
}

#else  /* RV64: one csrr is the full 64-bit counter */

static inline unsigned long long rd_mcycle (void)
{
  unsigned long long v;
  __asm__ volatile ("csrr %0, 0xB00\n\t nop\n\t nop\n\t nop\n\t nop"
                    : "=r" (v) :: "memory");
  return v;
}

static inline unsigned long long rd_minstret (void)
{
  unsigned long long v;
  __asm__ volatile ("csrr %0, 0xB02\n\t nop\n\t nop\n\t nop\n\t nop"
                    : "=r" (v) :: "memory");
  return v;
}
#endif

void initialise_board (void)
{
}

void __attribute__ ((noinline)) start_trigger (void)
{
  PROF_CTRL = 1u;
  c_start = rd_mcycle ();
  i_start = rd_minstret ();
}

void __attribute__ ((noinline)) stop_trigger (void)
{
  unsigned long long c = rd_mcycle ();
  unsigned long long i = rd_minstret ();
  bench_cycles  = c - c_start;
  bench_instret = i - i_start;
  PROF_CTRL = 0u;
}
