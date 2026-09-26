/* Timing-free board support, for trace comparison only.
 *
 * The normal boardsupport.c reads mcycle/minstret, whose values legitimately
 * differ between microarchitectures.  Diffing retire traces built with it
 * therefore reports the cycle counter as the "first divergence" and every
 * value derived from it thereafter, hiding any real difference.
 *
 * This build removes the CSR reads so both cores execute an identical,
 * deterministic instruction stream and the first genuine divergence is the
 * first one the diff finds.  Not for measurement -- it reports no timing.
 */
#include <stdint.h>
#include <support.h>

volatile unsigned long long bench_cycles;
volatile unsigned long long bench_instret;

void initialise_board (void) { }
void __attribute__ ((noinline)) start_trigger (void) { }
void __attribute__ ((noinline)) stop_trigger (void)
{
  bench_cycles  = 0;
  bench_instret = 0;
}
