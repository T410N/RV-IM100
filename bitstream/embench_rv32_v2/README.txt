Superseded RV32 Embench bitstreams, second iteration.

v1 read a 64-bit counter with a single csrr, which on RV32 fills only half a
register pair.  The fix for that read mcycleh/mcycle/mcycleh with a retry loop,
but emitted the three csrr instructions back to back with no nops between them.

The CSR path on these cores is two cycles and is not interlocked -- boardsupport.c
says so explicitly -- so a consumer immediately after csrr reads a stale value.
With three reads in a row the stale value is whatever the previous csr read
produced, and because start_trigger calls rd_mcycle() just before rd_minstret(),
minstret returned the mcycle value.  Every measured CPI came out as exactly
1.000, with cycles and instret differing only by the two instructions between
the reads.

Cycles from these bitstreams are correct and match simulation.  instret is not.
Do not use them.
