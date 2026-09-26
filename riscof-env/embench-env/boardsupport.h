/* Embench board support for RV-IM100.  See boardsupport.c. */
#ifndef BOARDSUPPORT_H
#define BOARDSUPPORT_H

/* Cycles and retired instructions for the timed region, filled in by
   stop_trigger() and printed by the startup code once main() returns. */
extern volatile unsigned long long bench_cycles;
extern volatile unsigned long long bench_instret;

#endif
