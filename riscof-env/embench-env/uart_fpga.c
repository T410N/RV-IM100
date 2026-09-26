/* UART output for running Embench on the FPGA.
 *
 * In simulation the testbench peeked bench_cycles/bench_instret straight out of
 * memory.  On hardware there is no such access, so the result has to leave the
 * chip through the only channel the SoCs have: the memory-mapped UART at
 * 0x10010000, with a busy flag at 0x10010004 bit 0.  This is the same protocol
 * the Dhrystone and CoreMark ports use.
 *
 * The baud divisor lives in the RTL (UART_TX.v BAUD_DIV), not here, so this code
 * is frequency-independent: the same binary is correct at every clock the family
 * runs at, and the image does NOT have to be rebuilt per frequency the way the
 * CoreMark and Dhrystone images do.
 */
#include <stdint.h>

#define UART_TX     (*(volatile uint32_t *) 0x10010000u)
#define UART_STATUS (*(volatile uint32_t *) 0x10010004u)
#define UART_BUSY   (1u << 0)

void uart_putchar (char c)
{
  while (UART_STATUS & UART_BUSY)
    ;
  UART_TX = (uint32_t) (unsigned char) c;
}

void uart_puts (const char *s)
{
  while (*s)
    uart_putchar (*s++);
}

/* No printf: newlib's would pull in a formatter far larger than the 32 KB
   instruction memory can spare next to a benchmark. */
void uart_putu64 (unsigned long long v)
{
  char buf[21];
  int i = 0;
  if (v == 0)
    {
      uart_putchar ('0');
      return;
    }
  while (v > 0 && i < 20)
    {
      buf[i++] = (char) ('0' + (v % 10u));
      v /= 10u;
    }
  while (i > 0)
    uart_putchar (buf[--i]);
}
