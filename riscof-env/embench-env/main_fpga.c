/* Embench entry point for the FPGA: run one benchmark and report over UART.
 *
 * Upstream main.c only returns !correct, which is invisible on hardware.  The
 * line emitted here is deliberately machine-readable and self-identifying, so a
 * capture can be attributed to a benchmark without relying on the order in which
 * bitstreams were loaded:
 *
 *   EMBENCH <name> cycles=<n> instret=<n> verify=<OK|FAIL>
 *
 * BENCH_NAME is supplied by the build as a string literal.
 */
#include "support.h"
#include "boardsupport.h"

extern void uart_putchar (char c);
extern void uart_puts (const char *s);
extern void uart_putu64 (unsigned long long v);

#ifndef BENCH_NAME
#define BENCH_NAME "unknown"
#endif

int __attribute__ ((used))
main (int argc __attribute__ ((unused)), char *argv[] __attribute__ ((unused)))
{
  int result;
  int correct;

  initialise_board ();
  initialise_benchmark ();
  warm_caches (WARMUP_HEAT);

  start_trigger ();
  result = benchmark ();
  stop_trigger ();

  correct = verify_benchmark (result);

  uart_puts ("EMBENCH " BENCH_NAME " cycles=");
  uart_putu64 (bench_cycles);
  uart_puts (" instret=");
  uart_putu64 (bench_instret);
  uart_puts (correct ? " verify=OK\n" : " verify=FAIL\n");

  /* Hold here: the SoCs have no exit path, and returning would run off into
     whatever follows in memory while the UART is still draining. */
  for (;;)
    ;
}
