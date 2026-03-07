/*
 * syscalls.c - minimal BSP support for RV32I
 *
 * 목표:
 *  - Dhrystone 2.1 소스(dhry_1.c/dhry_2.c/dhry.h) 수정 없이 빌드
 *  - newlib(libc) 전체를 링크하지 않아서 ROM 안에 들어가게 만들기
 *
 * 제공:
 *  - UART 출력 (mini_libc.c의 printf/puts/putchar가 사용)
 *  - times() : -DTIMES 측정용 (tick = cycle)
 *
 * 주의:
 *  - crt0.S에 _exit가 이미 있으므로 여기서는 _exit를 정의하지 않는다.
 */

#include <stdint.h>
#include <sys/times.h>

/* ============================================================
 * UART MMIO
 * ============================================================ */
#define UART_TX_ADDR      (*(volatile uint32_t *)0x10010000u)
#define UART_STATUS_ADDR  (*(volatile uint32_t *)0x10010004u)
#define UART_BUSY_BIT     (1u << 0)

/* ============================================================
 * Clock / HZ
 * ============================================================ */
#ifndef HZ
#define HZ 50000000UL
#endif

/* ============================================================
 * CSR read helper for mcycle
 * On RV32, mcycle is split into mcycle (low 32 bits) and mcycleh (high 32 bits)
 * ============================================================ */
static inline uint32_t csr_read_mcycle(void) {
    uint32_t v;
    __asm__ volatile ("csrr %0, mcycle" : "=r"(v));
    return v;
}

static inline uint32_t csr_read_mcycleh(void) {
    uint32_t v;
    __asm__ volatile ("csrr %0, mcycleh" : "=r"(v));
    return v;
}

/* Read full 64-bit cycle counter with rollover protection */
static inline uint64_t read_mcycle64(void) {
    uint32_t hi1, hi2, lo;
    do {
        hi1 = csr_read_mcycleh();
        lo  = csr_read_mcycle();
        hi2 = csr_read_mcycleh();
    } while (hi1 != hi2);
    return ((uint64_t)hi1 << 32) | lo;
}

/* ============================================================
 * UART output
 * ============================================================ */
static void uart_wait_ready(void) {
    while (UART_STATUS_ADDR & UART_BUSY_BIT) {
        /* busy wait */
    }
}

void uart_putchar(char c) {
    uart_wait_ready();
    UART_TX_ADDR = (uint32_t)(uint8_t)c;
}

void uart_puts(const char *s) {
    while (*s) {
        if (*s == '\n') {
            uart_putchar('\r');
        }
        uart_putchar(*s++);
    }
}

/* ============================================================
 * times() - K&R style (no prototype) to match Dhrystone
 * tick = cycle, and HZ should be set to CPU frequency.
 *
 * NOTE: return type is int because Dhrystone declares `extern int times();`
 * ============================================================ */
int times(buf)
struct tms *buf;
{
    uint64_t cycles = read_mcycle64();
    long ticks = (long)cycles;

    if (buf) {
        buf->tms_utime  = ticks;
        buf->tms_stime  = 0;
        buf->tms_cutime = 0;
        buf->tms_cstime = 0;
    }

    return (int)ticks;
}
