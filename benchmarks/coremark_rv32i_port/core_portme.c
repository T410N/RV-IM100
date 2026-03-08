/*
 * core_portme.c - CoreMark porting layer for RV32I46F_5SP
 *
 * Implements timing using mcycle CSR (50MHz clock)
 */

#include "coremark.h"
#include "core_portme.h"

/* Volatile seed variables for SEED_VOLATILE method */
#if VALIDATION_RUN
volatile ee_s32 seed1_volatile = 0x3415;
volatile ee_s32 seed2_volatile = 0x3415;
volatile ee_s32 seed3_volatile = 0x66;
#endif
#if PERFORMANCE_RUN
volatile ee_s32 seed1_volatile = 0x0;
volatile ee_s32 seed2_volatile = 0x0;
volatile ee_s32 seed3_volatile = 0x66;
#endif
#if PROFILE_RUN
volatile ee_s32 seed1_volatile = 0x8;
volatile ee_s32 seed2_volatile = 0x8;
volatile ee_s32 seed3_volatile = 0x8;
#endif

volatile ee_s32 seed4_volatile = ITERATIONS;
volatile ee_s32 seed5_volatile = 0;

/* ============================================================
 * CSR read helpers for mcycle (64-bit cycle counter)
 * ============================================================ */
static inline ee_u32 csr_read_mcycle(void) {
    ee_u32 v;
    __asm__ volatile ("csrr %0, mcycle" : "=r"(v));
    return v;
}

static inline ee_u32 csr_read_mcycleh(void) {
    ee_u32 v;
    __asm__ volatile ("csrr %0, mcycleh" : "=r"(v));
    return v;
}

/* Read 64-bit mcycle with rollover protection */
static inline ee_u32 read_mcycle32(void) {
    return csr_read_mcycle();
}

/* ============================================================
 * Timing implementation using mcycle CSR
 * ============================================================ */

/* Timer resolution and ticks per second
 * CPU runs at 50MHz, so 50,000,000 ticks per second
 */
#define EE_TICKS_PER_SEC 72000000

static CORETIMETYPE start_time_val, stop_time_val;

/* Function : start_time
 * Called right before starting the timed portion of the benchmark.
 */
void start_time(void)
{
    start_time_val = read_mcycle32();
}

/* Function : stop_time
 * Called right after ending the timed portion of the benchmark.
 */
void stop_time(void)
{
    stop_time_val = read_mcycle32();
}

/* Function : get_time
 * Return elapsed ticks between start_time and stop_time.
 */
CORE_TICKS get_time(void)
{
    CORE_TICKS elapsed = (CORE_TICKS)(stop_time_val - start_time_val);
    return elapsed;
}

/* Function : time_in_secs
 * Convert ticks to seconds.
 * Since HAS_FLOAT=0, we return integer seconds.
 */
secs_ret time_in_secs(CORE_TICKS ticks)
{
    secs_ret retval = (secs_ret)(ticks / EE_TICKS_PER_SEC);
    return retval;
}

/* Default number of contexts (single-threaded) */
ee_u32 default_num_contexts = 1;

/* Function : portable_init
 * Target specific initialization code.
 * For baremetal RV32I, most initialization is done in crt0.S
 */
void portable_init(core_portable *p, int *argc, char *argv[])
{
    (void)argc;
    (void)argv;

    /* Verify data type sizes */
    if (sizeof(ee_ptr_int) != sizeof(ee_u8 *))
    {
        ee_printf("ERROR! Please define ee_ptr_int to a type that holds a pointer!\n");
    }
    if (sizeof(ee_u32) != 4)
    {
        ee_printf("ERROR! Please define ee_u32 to a 32b unsigned type!\n");
    }

    p->portable_id = 1;
}

/* Function : portable_fini
 * Target specific finalization code.
 */
void portable_fini(core_portable *p)
{
    p->portable_id = 0;
}

/* Function : portable_malloc
 * Not used when MEM_METHOD == MEM_STACK, but provide stub
 */
void *portable_malloc(ee_size_t size)
{
    (void)size;
    return NULL;
}

/* Function : portable_free
 * Not used when MEM_METHOD == MEM_STACK, but provide stub
 */
void portable_free(void *p)
{
    (void)p;
}

/* Note: get_seed_32 is defined in core_util.c when SEED_METHOD == SEED_VOLATILE */
