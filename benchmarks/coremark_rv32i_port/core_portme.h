/*
 * core_portme.h - CoreMark porting header for RV32I46F_5SP
 *
 * Target: RV32I (no FPU, no M extension)
 * Clock: 50MHz
 * Memory: ROM 64KB @ 0x00000000, RAM 32KB @ 0x10000000
 */

#ifndef CORE_PORTME_H
#define CORE_PORTME_H

/************************/
/* Data types and settings */
/************************/

/* Configuration : HAS_FLOAT
 * RV32I has no FPU, so we disable floating point.
 */
#ifndef HAS_FLOAT
#define HAS_FLOAT 0
#endif

/* Configuration : HAS_TIME_H
 * Baremetal - no time.h available
 */
#ifndef HAS_TIME_H
#define HAS_TIME_H 0
#endif

/* Configuration : USE_CLOCK
 * We use mcycle CSR instead of clock()
 */
#ifndef USE_CLOCK
#define USE_CLOCK 0
#endif

/* Configuration : HAS_STDIO
 * Baremetal - no stdio.h available
 */
#ifndef HAS_STDIO
#define HAS_STDIO 0
#endif

/* Configuration : HAS_PRINTF
 * We provide our own ee_printf implementation
 */
#ifndef HAS_PRINTF
#define HAS_PRINTF 0
#endif

/* Definitions : COMPILER_VERSION, COMPILER_FLAGS, MEM_LOCATION */
#ifndef COMPILER_VERSION
#ifdef __GNUC__
#define COMPILER_VERSION "GCC"__VERSION__
#else
#define COMPILER_VERSION "Unknown"
#endif
#endif

#ifndef COMPILER_FLAGS
#define COMPILER_FLAGS FLAGS_STR
#endif

#ifndef MEM_LOCATION
#define MEM_LOCATION "STACK"
#endif

/* Data Types for RV32I */
typedef signed short   ee_s16;
typedef unsigned short ee_u16;
typedef signed int     ee_s32;
typedef unsigned int   ee_u32;
typedef unsigned char  ee_u8;
typedef ee_u32         ee_ptr_int;
typedef unsigned int   ee_size_t;

/* No FPU - define dummy float types */
#if HAS_FLOAT
typedef double         ee_f32;
#endif

#ifndef NULL
#define NULL ((void *)0)
#endif

/* align_mem :
 * This macro is used to align an offset to point to a 32b value.
 */
#define align_mem(x) (void *)(4 + (((ee_ptr_int)(x) - 1) & ~3))

/* Configuration : CORE_TICKS
 * Define type of return from the timing functions.
 * We use 32-bit ticks from mcycle CSR.
 */
#define CORETIMETYPE ee_u32
typedef ee_u32 CORE_TICKS;

/* Configuration : SEED_METHOD
 * SEED_VOLATILE - use volatile variables for seeds
 */
#ifndef SEED_METHOD
#define SEED_METHOD SEED_VOLATILE
#endif

/* Configuration : MEM_METHOD
 * MEM_STACK - allocate data on stack (simplest, no malloc needed)
 */
#ifndef MEM_METHOD
#define MEM_METHOD MEM_STACK
#endif

/* Configuration : MULTITHREAD
 * Single-threaded execution
 */
#ifndef MULTITHREAD
#define MULTITHREAD 1
#define USE_PTHREAD 0
#define USE_FORK    0
#define USE_SOCKET  0
#endif

/* Configuration : MAIN_HAS_NOARGC
 * Baremetal - no command line arguments
 */
#ifndef MAIN_HAS_NOARGC
#define MAIN_HAS_NOARGC 1
#endif

/* Configuration : MAIN_HAS_NORETURN
 * main() returns int for compatibility
 */
#ifndef MAIN_HAS_NORETURN
#define MAIN_HAS_NORETURN 0
#endif

/* Variable : default_num_contexts
 * Single context for this port
 */
extern ee_u32 default_num_contexts;

typedef struct CORE_PORTABLE_S
{
    ee_u8 portable_id;
} core_portable;

/* target specific init/fini */
void portable_init(core_portable *p, int *argc, char *argv[]);
void portable_fini(core_portable *p);

/* Run type selection based on TOTAL_DATA_SIZE */
#if !defined(PROFILE_RUN) && !defined(PERFORMANCE_RUN) && !defined(VALIDATION_RUN)
#if (TOTAL_DATA_SIZE == 1200)
#define PROFILE_RUN 1
#elif (TOTAL_DATA_SIZE == 2000)
#define PERFORMANCE_RUN 1
#else
#define VALIDATION_RUN 1
#endif
#endif

/* ee_printf declaration */
int ee_printf(const char *fmt, ...);

#endif /* CORE_PORTME_H */
