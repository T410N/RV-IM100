// Testbench for every RV-IM100 variant.
//
// Deliberately knows nothing about the design: the program image reaches the
// ROM through Verilog $readmemh on +HEX, and the signature is written by
// sim_top's own dump task.  That keeps this file identical for all 14 cores --
// no Verilated hierarchy paths, so nothing here breaks when a variant renames
// a module or reshapes its data memory.

#include "Vsim_top.h"
#include "verilated.h"
#if VM_TRACE
# include "verilated_vcd_c.h"
#endif

#include <cstdio>
#include <cstdlib>
#include <cstring>

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);

    long max_cycles = 20000000;
    // Windowed VCD: dumping a whole run of tens of thousands of cycles makes
    // a file too large to open comfortably, and the interesting region is
    // usually a few hundred cycles wide.  +VCD_START / +VCD_END bound it.
    const char *vcd_path = 0;
    long vcd_start = 0, vcd_end = -1;
    for (int i = 1; i < argc; i++) {
        if (!strncmp(argv[i], "+MAX_CYCLES=", 12)) max_cycles = atol(argv[i] + 12);
        if (!strncmp(argv[i], "+VCD=", 5))        vcd_path  = argv[i] + 5;
        if (!strncmp(argv[i], "+VCD_START=", 11)) vcd_start = atol(argv[i] + 11);
        if (!strncmp(argv[i], "+VCD_END=", 9))    vcd_end   = atol(argv[i] + 9);
    }
#if VM_TRACE
    VerilatedVcdC *tfp = 0;
    if (vcd_path) { Verilated::traceEverOn(true); }
#endif

    Vsim_top *top = new Vsim_top;

#if VM_TRACE
    if (vcd_path) {
        tfp = new VerilatedVcdC;
        top->trace(tfp, 99);
        tfp->open(vcd_path);
    }
    uint64_t vcd_time = 0;
#endif

    long cyc_now = 0;
    auto in_window = [&]() {
        return cyc_now >= vcd_start && (vcd_end < 0 || cyc_now <= vcd_end);
    };
    auto tick = [&]() {
        top->clk = 1; top->eval();
#if VM_TRACE
        if (tfp && in_window()) tfp->dump(static_cast<uint64_t>(vcd_time++));
#endif
        top->clk = 0; top->eval();
#if VM_TRACE
        if (tfp && in_window()) tfp->dump(static_cast<uint64_t>(vcd_time++));
#endif
        cyc_now++;
    };

    top->clk = 0;
    top->do_dump = 0;
    top->reset = 1;
    for (int i = 0; i < 10; i++) tick();
    top->reset = 0;

    long cycle = 0;
    bool halted = false;
    while (cycle < max_cycles) {
        tick();
        cycle++;
#if VM_TRACE
        if (tfp && vcd_end >= 0 && cycle > vcd_end) { tfp->close(); tfp = 0; }
#endif
        if (top->sim_halt) { halted = true; break; }
    }

    // Dump whatever the run produced, however it ended -- a timed-out test
    // still yields a signature, which shows up as a mismatch rather than as a
    // missing file, and that is far easier to triage.
    top->do_dump = 1;
    tick();
    tick();

    // halt_code carries the value the program stored to tohost.  The arch
    // tests always store 1; riscv-tests stores TESTNUM-derived pass/fail, so
    // the exit status has to distinguish them: 0 pass, 1 test failed,
    // 2 timeout.
    unsigned code = top->halt_code;
    printf("[RISCOF-TB] %s cycles=%ld code=0x%08x\n",
           halted ? "HALT" : "TIMEOUT", cycle, code);
    fflush(stdout);

#if VM_TRACE
    if (tfp) { tfp->close(); }
#endif
    top->final();
    delete top;
    if (!halted) return 2;
    return (code == 1u) ? 0 : 1;
}
