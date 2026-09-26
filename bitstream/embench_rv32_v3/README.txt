Superseded RV32 Embench bitstreams, third iteration.  These HANG on the board
and print nothing.

v1  a single csrr read a 64-bit value, which on RV32 fills only half a register
    pair; cycle counts came back inflated by 2^32 or worse.
v2  read mcycleh/mcycle/mcycleh with a retry loop, but with no nops between the
    reads.  The CSR path is two cycles and not interlocked, so minstret returned
    the mcycle value read moments earlier and every CPI came out as 1.000.
v3  (these) added the nops back.  The retry loop still never converges on these
    cores -- the PC spins inside rd_counter -- so the program never reaches its
    UART output.  Confirmed in simulation: 60,000,000 cycles with no halt, PC
    confined to the rd_counter block.

The working version reads only the low 32 bits with its nops, and no loop.  That
is valid because the largest run here is 43 M cycles against a 2^32 limit of
4.29 G, so the high word is always zero.  Verified in simulation before release:
crc32 on RV32IM_5SP stores instret 4,183,419 and cycles 5,578,813, CPI 1.3336,
against a reference of 4,183,251 / 5,578,645 -- both offset by the same 168
harness instructions inside the timed region.
