#!/usr/bin/env python3
"""Stage a simulation-ready copy of one variant's RTL under build/<variant>/rtl.

The design RTL is copied verbatim except for Instruction_Memory.v, which is
adapted for architectural tests in three ways:

  * the ROM is grown from 32-64 KB to 2 MB, because jal-01.S alone expands to a
    1.18 MB text image once objcopy fills the jump ranges,
  * the address slices are widened to match, and
  * the hardcoded $readmemh of a benchmark .mem file (plus the hand-assembled
    trap handler the RTL preloads at data[7000], i.e. byte 0x6D60) is replaced
    by a +HEX plusarg.  That trap handler has to go: the arch tests install
    their own via mtvec, and their .text runs straight through 0x6D60.

Data_Memory.v loses only its benchmark $readmemh; .data reaches RAM through a
boot-time copy from ROM (see env/model_test.h), so the RAM's internal shape --
flat XLEN words on 5SP/6SP, eight byte banks on 8SP -- never has to be known
here.
"""
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import all_variants  # noqa: E402

ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# SoC-level modules: clock wizard IP, UART and the MMIO decoder all live above
# the core and are replaced by sim_top.
EXCLUDE = re.compile(r"(_SoC_TOP\.v$|^UART_TX\.v$|^Unified_UART_Controller\.v$|^MMIO_Interface\.v$)")

ROM_WORDS = 1 << 19          # 512 K words = 2 MB
DATA_BASE = 0x10000000


def strip_comments(s):
    s = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), s, flags=re.S)
    s = re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), s)
    return s


def replace_initial_block(src):
    """Replace the initial block containing $readmemh with a +HEX loader."""
    bare = strip_comments(src)
    start = None
    for m in re.finditer(r"\binitial\b\s*\bbegin\b", bare):
        # find the matching end
        depth = 0
        pos = m.start()
        for tok in re.finditer(r"\b(begin|end)\b", bare[m.start():]):
            if tok.group(1) == "begin":
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    pos = m.start() + tok.end()
                    break
        if "$readmemh" in bare[m.start():pos]:
            start = (m.start(), pos)
            break
    if start is None:
        raise RuntimeError("no initial block with $readmemh found")

    loader = (
        "initial begin : load_image\n"
        "\t\treg [8191:0] hex_path;\n"
        "\t\tinteger i;\n"
        "\t\tfor (i = 0; i < %d; i = i + 1) data[i] = 32'h0000_0000;\n"
        "\t\tif ($value$plusargs(\"HEX=%%s\", hex_path))\n"
        "\t\t\t$readmemh(hex_path, data);\n"
        "\tend" % ROM_WORDS
    )
    return src[:start[0]] + loader + src[start[1]:]


def patch_imem(src):
    src = re.sub(r"reg\s*\[31:0\]\s*data\s*\[0:\d+\]",
                 "reg [31:0] data [0:%d]" % (ROM_WORDS - 1), src)
    src = re.sub(r"pc\[(?:31|15):2\]", "pc[20:2]", src)
    src = re.sub(r"rom_address\[15:2\]", "rom_address[20:2]", src)
    src = re.sub(r"rom_address\[15:3\]", "rom_address[20:3]", src)
    src = re.sub(r"rom_address\[31:16\]\s*==\s*16'h0000",
                 "rom_address[31:21] == 11'h000", src)
    return replace_initial_block(src)


def patch_dmem(src):
    # Drop the benchmark data image; .data arrives via the boot copy loop.
    src = re.sub(r"^[ \t]*\$readmemh\s*\(\s*\"\./data_init\.mem\".*?\);[ \t]*\n",
                 "", src, flags=re.M | re.S)
    # Widen the load-from-ROM window to match the enlarged ROM.  Loads of
    # .rodata and of the .data load image both go through here, and a 1.18 MB
    # text image pushes them well past the original 64 KB decode.
    src = re.sub(r"address\[31:16\]\s*==\s*16'h0000",
                 "address[31:21] == 11'h000", src)
    return src



PORT_RE = re.compile(
    r"^[ \t]*(input|output)\s+(?:wire\s+|reg\s+)?(\[[^\]]+\]\s*)?(\w+)"
    r"\s*,?[ \t]*(?://[^\n]*)?$", re.M)

# Inputs the wrapper drives itself; every other input is tied off, which is what
# lets one template cover cores that carry extra pins (the RV-RTOS8 core adds
# timer_interrupt_pending and MMIO_read_data for its CLINT and memory-mapped IO).
DRIVEN = {"clk": "clk", "reset": "reset", "clk_enable": "1'b1"}

WANTED_OUTPUTS = {
    "retire_instruction": "retire_instruction",
    "MMIO_data_memory_write_data": "mmio_write_data",
    "MMIO_data_memory_address": "mmio_address",
    "MMIO_data_memory_write_enable": "mmio_write_enable",
    "SIM_dmem_address": "dmem_addr",
    "SIM_dmem_write_data": "dmem_wdata",
    "SIM_dmem_write_mask": "dmem_mask",
    "SIM_dmem_write_enable": "dmem_we",
    "SIM_retire_valid":   "retire_valid",
    "SIM_retire_pc":      "retire_pc",
    "SIM_retire_insn":    "retire_insn",
    "SIM_retire_rd_we":   "retire_rd_we",
    "SIM_retire_rd":      "retire_rd_sig",
    "SIM_retire_rd_data": "retire_rd_data",
    "SIM_prof":           "prof_flags",
}


def core_instantiation(src, module):
    """Build the core instantiation from the core's actual port list.

    Any input the wrapper does not drive is tied low, and any output it does
    not consume is left open.  That is what lets one template cover cores with
    extra pins -- the RV-RTOS8 core adds timer_interrupt_pending and
    MMIO_read_data for its CLINT and memory-mapped IO.
    """
    head = src[src.index("module " + module):]
    head = head[:head.index(");") + 2]

    conns = []
    for direction, width, name in PORT_RE.findall(head):
        width = (width or "").strip()
        if direction == "input":
            if name in DRIVEN:
                conns.append((name, DRIVEN[name]))
            elif width:
                # sim_zero is wide enough for any port in these designs
                conns.append((name, "sim_zero%s" % width))
            else:
                conns.append((name, "1'b0"))
        else:
            conns.append((name, WANTED_OUTPUTS.get(name, "")))

    # A port silently dropped here produces a floating input and a simulator
    # that never halts, which is expensive to debug -- so cross-check the count.
    declared = len(re.findall(r"^[ \t]*(?:input|output)\b", head, re.M))
    if declared != len(conns):
        raise RuntimeError(
            "port parse mismatch in %s: %d declared, %d matched" %
            (module, declared, len(conns)))

    w = max(len(n) for n, _ in conns)
    return "\n".join(
        "        .%-*s (%s)%s" % (w, n, v, "," if i < len(conns) - 1 else "")
        for i, (n, v) in enumerate(conns))


SIM_PORTS = """    output wire [XLEN-1:0]   SIM_dmem_address,
    output wire [XLEN-1:0]   SIM_dmem_write_data,
    output wire [XLEN/8-1:0] SIM_dmem_write_mask,
    output wire              SIM_dmem_write_enable,
    // Retire tap.  A wrong memory word is many cycles downstream of whatever
    // caused it, which is why six attempts to reproduce the 8SP divergence
    // synthetically all failed.  This exposes architectural state as it
    // retires so a run can be diffed against Sail's -v trace instruction by
    // instruction, and the *first* divergent instruction identified rather
    // than the first divergent memory word.
    output wire              SIM_retire_valid,
    output wire [XLEN-1:0]   SIM_retire_pc,
    output wire [31:0]       SIM_retire_insn,
    output wire              SIM_retire_rd_we,
    output wire [4:0]        SIM_retire_rd,
    output wire [XLEN-1:0]   SIM_retire_rd_data,
    // Profiling bundle.  Packed rather than 11 separate ports so the patcher
    // stays small; bit meanings are fixed by PROF_BITS below.  Any signal a
    // given variant does not have is tied low and reported as n/a, since the
    // pipelines genuinely differ (the 5-stage has no load_use_hazard, only
    // the 8-stage has EXR_EX).
    output wire [10:0]       SIM_prof
"""

# bit -> (candidate signal names, human label).  The pipelines renamed stages
# as they deepened, so a bit takes the first name that is actually *declared*
# in that core.  Matching on text alone is not enough: the 8-stage core still
# mentions ID_EX_stall in a comment and as a submodule port name while the
# real net is ID_EXR_stall.
PROF_BITS = [
    (["branch_prediction_miss"],        "branch mispredictions"),
    (["pc_stall"],                      "pc stall"),
    (["IF_ID_stall", "IF_IO_stall"],    "front-end stall"),
    (["ID_EX_stall", "ID_EXR_stall"],   "ID/EX stall"),
    (["EXR_EX_stall"],                  "EXR/EX stall"),
    (["EX_EX2_stall"],                  "EX/EX2 stall"),
    (["EX_MEM_stall"],                  "EX/MEM stall"),
    (["MEM_WB_stall"],                  "MEM/WB stall"),
    (["load_use_hazard"],               "load-use hazard"),
    (["div_busy"],                      "divider busy"),
    (["mul_busy"],                      "multiplier busy"),
]


def declared(src, name):
    """True only if `name` is declared as a wire/reg in this module."""
    return re.search(r"^[ \t]*(?:wire|reg)\b[^;]*\b%s\b" % re.escape(name),
                     src, re.M) is not None

SIM_ASSIGNS = """
    // Observability only, added by scripts/prepare_rtl.py.  These mirror the
    // signals driven into the DataMemory instance, so the testbench sees
    // stores in the same pipeline stage and with the same byte enables the
    // RAM does.  The existing MMIO_* taps cannot be used for this: on the
    // 5-stage cores they are a WB-stage view while the RAM is written from
    // MEM, and they carry no byte enables at all.
    //
    // The write enable is NOT simply the instance's write_enable port.  On
    // the BRAM-backed and 8-stage designs DataMemory takes two cycles per
    // store and internally qualifies the write with !write_phase, while the
    // top holds write_enable high across both cycles and re-points `address`
    // at a load waiting in EX2 for the second one.  Mirroring the raw port
    // would therefore record a phantom store at the load's address -- which
    // is exactly what it did, and it looked convincingly like an RTL bug.
    // write_done is the top-level view of write_phase, so !write_done marks
    // the single cycle the RAM is actually written.
    assign SIM_dmem_address      = {addr};
    assign SIM_dmem_write_data   = {wdata};
    assign SIM_dmem_write_mask   = {mask};
    assign SIM_dmem_write_enable = {wen};
{retire}{prof}
endmodule
"""

# The WB stage is named identically across the family, but a variant that
# lacks any of these gets a tied-off tap rather than a build failure.
RETIRE_SIGNALS = ["WB_pc", "WB_instruction", "WB_register_write_enable",
                  "WB_rd", "register_file_write_data",
                  "MEM_WB_stall", "MEM_WB_flush"]

RETIRE_ASSIGNS = """
    // Retire tap: the design's own notion of an instruction leaving WB.
    assign SIM_retire_valid   = !MEM_WB_stall && !MEM_WB_flush;
    assign SIM_retire_pc      = WB_pc;
    assign SIM_retire_insn    = WB_instruction;
    assign SIM_retire_rd_we   = WB_register_write_enable;
    assign SIM_retire_rd      = WB_rd;
    assign SIM_retire_rd_data = register_file_write_data;
"""

RETIRE_TIED = """
    assign SIM_retire_valid   = 1'b0;
    assign SIM_retire_pc      = {XLEN{1'b0}};
    assign SIM_retire_insn    = 32'b0;
    assign SIM_retire_rd_we   = 1'b0;
    assign SIM_retire_rd      = 5'b0;
    assign SIM_retire_rd_data = {XLEN{1'b0}};
"""


def patch_core(src):
    """Add observability outputs driven from the DataMemory instance."""
    m = re.search(r"DataMemory\s+(?:#\s*\([^)]*\)\s*)?\w+\s*\((.*?)\n\s*\);",
                  src, re.S)
    if m is None:
        raise RuntimeError("no DataMemory instantiation found")
    body = m.group(1)

    def port(name, required=True):
        pm = re.search(r"\.%s\s*\(\s*(.*?)\s*\)\s*,?\s*(?:\n|$)" % name, body, re.S)
        if pm is None:
            if required:
                raise RuntimeError("DataMemory port .%s not found" % name)
            return None
        return pm.group(1).strip()

    wen = "(%s)" % port("write_enable")
    # Single-phase memories (5SP/6SP/7SP) expose no write_done and drive the
    # RAM straight from write_enable; two-phase ones must be qualified or the
    # second cycle is recorded as a spurious write.
    done = port("write_done", required=False)
    if done is not None:
        wen += " && !(%s)" % done
    ce = port("clk_enable", required=False)
    if ce is not None:
        wen = "(%s) && " % ce + wen

    have = all(re.search(r"\b%s\b" % sig, src) for sig in RETIRE_SIGNALS)

    bits = []
    for i, (names, label) in enumerate(PROF_BITS):
        pick = next((n for n in names if declared(src, n)), None)
        bits.append("    assign SIM_prof[%2d] = %s;   // %s"
                    % (i, pick if pick else "1'b0",
                       label if pick else label + " -- not in this variant"))
    prof = "\n    // Profiling taps (see PROF_BITS in scripts/prepare_rtl.py).\n" \
           + "\n".join(bits) + "\n"

    exprs = dict(addr=port("address"), wdata=port("write_data"),
                 mask=port("write_mask"), wen=wen,
                 retire=(RETIRE_ASSIGNS if have else RETIRE_TIED),
                 prof=prof)

    src, n = re.subn(
        r"(output\s+wire\s+MMIO_data_memory_write_enable\s*)\n(\s*\);)",
        lambda mm: mm.group(1) + ",\n" + SIM_PORTS + mm.group(2),
        src, count=1)
    if n != 1:
        raise RuntimeError("could not extend the core port list")

    src, n = re.subn(r"\nendmodule\s*$", SIM_ASSIGNS.format(**exprs), src, count=1)
    if n != 1:
        raise RuntimeError("could not append observability assigns")
    return src


SIM_TOP = r"""// Generated by scripts/prepare_rtl.py -- do not edit.
// Simulation wrapper for {variant} (core {module}, XLEN={xlen}).
`timescale 1ns / 1ps

module sim_top #(
    parameter XLEN = {xlen}
)(
    input  wire clk,
    input  wire reset,
    input  wire do_dump,
    output reg  sim_halt,
    // riscv-tests encodes pass/fail in the value stored to tohost
    // (1 = pass, (n<<1)|1 = failing test n), so the data has to escape
    // alongside the halt flag.  The arch tests ignore it.
    output reg [31:0] halt_code
);
    // A store to this address ends the test.  It is the design's own UART TX
    // MMIO address, which Data_Memory decodes as neither RAM nor ROM, so
    // nothing else in the core reacts to it.
    // 0x10010000 is the SoC's UART transmit register, which the arch tests and
    // riscv-tests reuse as their "test finished" signal.  Programs that also
    // print (Embench) need a distinct exit address, so the halt address is
    // overridable with +HALT_ADDR=<hex>; 0x10012000 is decoded as neither RAM
    // nor ROM, so storing there is harmless on hardware.
    reg [31:0] TOHOST_ADDR;
    initial begin
        TOHOST_ADDR = 32'h1001_0000;
        void'($value$plusargs("HALT_ADDR=%h", TOHOST_ADDR));
    end
    localparam        BYTES       = XLEN / 8;

    wire [31:0]      retire_instruction;
    wire [XLEN-1:0]  mmio_write_data;
    wire [XLEN-1:0]  mmio_address;
    wire             mmio_write_enable;

    wire [XLEN-1:0]   dmem_addr;
    wire [XLEN-1:0]   dmem_wdata;
    wire [BYTES-1:0]  dmem_mask;
    wire              dmem_we;

    wire              retire_valid;
    wire [XLEN-1:0]   retire_pc;
    wire [31:0]       retire_insn;
    wire              retire_rd_we;
    wire [4:0]        retire_rd_sig;
    wire [XLEN-1:0]   retire_rd_data;
    wire [10:0]       prof_flags;

    wire [1023:0] sim_zero = 1024'b0;

    {module} #(.XLEN(XLEN)) core (
{core_inst}
    );

    // Byte-granular shadow of the data RAM, written from the same signals the
    // RAM sees.  Dumping from here rather than from inside Data_Memory is what
    // keeps this wrapper identical across all 14 variants -- the RAM is a flat
    // 32-bit array on some cores, a flat 64-bit array on others and eight byte
    // banks on the 8-stage designs.
    reg [7:0] shadow [0:65535];

    // Data_Memory ignores the low address bits and selects bytes with the
    // mask, so the shadow has to key off the aligned word base the same way.
    wire [15:0] word_base = mmio_align(dmem_addr[15:0]);
    wire        in_ram    = (dmem_addr[31:16] == 16'h1000);
    // Halt is detected on EITHER tap.  Neither alone is enough across the
    // family: RV-RTOS8 gates its DataMemory write enable with mmio_hit, so the
    // halt store never reaches the RAM port; and on some RV-IM100 cores the
    // MMIO tap is a WB-stage view that does not carry the store.
    wire        is_tohost = (dmem_we           && dmem_addr[31:0]    == TOHOST_ADDR)
                         || (mmio_write_enable && mmio_address[31:0] == TOHOST_ADDR);
    // UART traffic is always watched at the fixed transmit address, whatever
    // the halt address has been moved to.
    wire        is_uart_dmem = dmem_we           && dmem_addr[31:0]    == 32'h1001_0000;
    wire        is_uart_mmio = mmio_write_enable && mmio_address[31:0] == 32'h1001_0000;
    wire        is_uart      = is_uart_dmem || is_uart_mmio;
    // The UART needs its own data selector.  tohost_data is keyed to
    // TOHOST_ADDR, which +HALT_ADDR can move elsewhere; using it for the UART
    // then always fell through to mmio_write_data and captured nulls on the
    // 5-stage cores, where that tap is a WB-stage view that does not carry
    // the store.
    wire [XLEN-1:0] uart_data = is_uart_dmem ? dmem_wdata : mmio_write_data;
    wire [XLEN-1:0] tohost_data =
        (dmem_we && dmem_addr[31:0] == TOHOST_ADDR) ? dmem_wdata : mmio_write_data;

    function [15:0] mmio_align;
        input [15:0] a;
        begin
            mmio_align = (XLEN == 64) ? {{a[15:3], 3'b000}} : {{a[15:2], 2'b00}};
        end
    endfunction

    reg [8191:0] sig_file;   // 1024 chars: work paths run long
    reg [31:0]   sig_begin;
    reg [31:0]   sig_end;
    reg          have_sig;
    reg          got;
    reg          dumped;
    integer      i;
    integer      b;

    initial begin
        for (i = 0; i < 65536; i = i + 1) shadow[i] = 8'h00;
        sim_halt  = 1'b0;
        halt_code = 32'h0;
        dumped    = 1'b0;
        sig_begin = 32'h0;
        sig_end   = 32'h0;
        have_sig  = 1'b0;
        if ($value$plusargs("SIG_FILE=%s", sig_file)) have_sig = 1'b1;
        got = $value$plusargs("SIG_BEGIN=%h", sig_begin);
        got = $value$plusargs("SIG_END=%h", sig_end);
    end

    always @(posedge clk) begin
        if (dmem_we && in_ram) begin
            for (b = 0; b < BYTES; b = b + 1) begin
                if (dmem_mask[b])
                    shadow[word_base + b] <= dmem_wdata[8*b +: 8];
            end
        end
    end

    // 0x10010000 is also the SoC's UART transmit register, so a benchmark's
    // first printf would otherwise be read as "test finished".  +NOHALT keeps
    // the core running for a full benchmark, and +UART=<file> captures the
    // byte stream, which is how the benchmark's own score is recovered.
    reg          no_halt;
    reg          uart_prev;
    reg [8191:0] uart_path;
    integer      uart_fd;
    reg          have_uart;

    // Stopping after a fixed number of retired instructions makes CPI
    // directly comparable across pipeline depths: every variant executes
    // exactly the same work, so only the cycle count differs.  Comparing at a
    // fixed *cycle* budget would instead compare different amounts of work.
    reg [63:0] max_instr;
    reg        have_max_instr;

    initial begin
        max_instr      = 64'd0;
        have_max_instr = $value$plusargs("MAX_INSTR=%d", max_instr);
        no_halt   = $test$plusargs("NOHALT") ? 1'b1 : 1'b0;
        uart_prev = 1'b0;
        uart_fd   = 0;
        have_uart = 1'b0;
        if ($value$plusargs("UART=%s", uart_path)) begin
            uart_fd   = $fopen(uart_path, "w");
            have_uart = (uart_fd != 0);
        end
    end

    always @(posedge clk) begin
        if (reset) begin
            sim_halt  <= 1'b0;
            halt_code <= 32'h0;
        end else begin
            // One store must produce one character.  The BRAM-backed and
            // 8-stage cores hold a store across two cycles and it is visible
            // on both the dmem and mmio taps, so recording on the level
            // duplicated every byte ("EEMMBBEENNCCHH").  Record on the rising
            // edge instead.
            if (is_uart && !uart_prev && have_uart)
                $fwrite(uart_fd, "%c", uart_data[7:0]);
            uart_prev <= is_uart;
            if (is_tohost && !sim_halt && !no_halt) begin
                sim_halt  <= 1'b1;
                halt_code <= tohost_data[31:0];
            end
            if (have_max_instr && !sim_halt && n_retired >= max_instr) begin
                sim_halt  <= 1'b1;
                halt_code <= 32'h1;
            end
        end
    end

    // Optional retire trace, enabled by +TRACE=<file>.  One line per
    // instruction leaving WB, in the same order Sail's -v trace prints them,
    // so the two can be diffed directly to find the first architecturally
    // divergent instruction.
    reg [8191:0] trace_path;
    integer      trace_fd;
    reg          have_trace;

    initial begin
        trace_fd   = 0;
        have_trace = 1'b0;
        if ($value$plusargs("TRACE=%s", trace_path)) begin
            trace_fd   = $fopen(trace_path, "w");
            have_trace = (trace_fd != 0);
        end
    end

    // ---- profiling counters -------------------------------------------
    // Counted here rather than in the core so nothing added for measurement
    // can affect synthesis, timing or area.  Instruction-mix counts come from
    // the retire tap and are therefore identical in meaning across every
    // pipeline depth; stall counts come from each variant's own signals.
    integer p;
    reg [63:0] prof_cyc  [0:10];      // cycles each flag was asserted
    reg [63:0] prof_edge [0:10];      // rising edges (for event counts)
    reg [10:0] prof_prev;

    reg [63:0] n_retired, n_branch, n_jump, n_load, n_store, n_mul, n_div;
    reg [63:0] n_cycles_run;

    initial begin
        for (p = 0; p < 11; p = p + 1) begin
            prof_cyc[p]  = 64'd0;
            prof_edge[p] = 64'd0;
        end
        prof_prev = 11'd0;
        n_retired = 0; n_branch = 0; n_jump = 0;
        n_load = 0; n_store = 0; n_mul = 0; n_div = 0; n_cycles_run = 0;
    end

    // Decode straight from the retired instruction word.
    wire [6:0] r_op  = retire_insn[6:0];
    wire [2:0] r_f3  = retire_insn[14:12];
    wire [6:0] r_f7  = retire_insn[31:25];
    wire       r_is_m = ((r_op == 7'h33) || (r_op == 7'h3b)) && (r_f7 == 7'h01);

    always @(posedge clk) begin
        if (!reset) begin
            n_cycles_run <= n_cycles_run + 64'd1;
            for (p = 0; p < 11; p = p + 1) begin
                if (prof_flags[p])                     prof_cyc[p]  <= prof_cyc[p]  + 64'd1;
                if (prof_flags[p] && !prof_prev[p])    prof_edge[p] <= prof_edge[p] + 64'd1;
            end
            prof_prev <= prof_flags;

            // A NOP is architecturally inert; excluding it matches the core's
            // own minstret definition, which the paper should state.
            if (retire_valid && retire_insn != 32'h00000013) begin
                n_retired <= n_retired + 64'd1;
                if (r_op == 7'h63)                  n_branch <= n_branch + 64'd1;
                if (r_op == 7'h6f || r_op == 7'h67) n_jump   <= n_jump   + 64'd1;
                if (r_op == 7'h03)                  n_load   <= n_load   + 64'd1;
                if (r_op == 7'h23)                  n_store  <= n_store  + 64'd1;
                if (r_is_m &&  r_f3[2])             n_div    <= n_div    + 64'd1;
                if (r_is_m && !r_f3[2])             n_mul    <= n_mul    + 64'd1;
            end
        end
    end

    task dump_profile;
        integer fd;
        reg [8191:0] path;
        begin
            if ($value$plusargs("PROF=%s", path)) begin
                fd = $fopen(path, "w");
                if (fd != 0) begin
                    $fwrite(fd, "cycles %0d\n", n_cycles_run);
                    $fwrite(fd, "retired %0d\n", n_retired);
                    $fwrite(fd, "branch %0d\n", n_branch);
                    $fwrite(fd, "jump %0d\n", n_jump);
                    $fwrite(fd, "load %0d\n", n_load);
                    $fwrite(fd, "store %0d\n", n_store);
                    $fwrite(fd, "mul %0d\n", n_mul);
                    $fwrite(fd, "div %0d\n", n_div);
                    for (p = 0; p < 11; p = p + 1)
                        $fwrite(fd, "bit%0d_cycles %0d bit%0d_events %0d\n",
                                p, prof_cyc[p], p, prof_edge[p]);
                    $fclose(fd);
                end
            end
        end
    endtask

    // Cycle number is included so a divergence found in the trace can be
    // located directly in a waveform without counting retires by hand.
    reg [63:0] cycle_count;
    always @(posedge clk) begin
        if (reset) cycle_count <= 64'd0;
        else       cycle_count <= cycle_count + 64'd1;
    end

    // Stores are logged too.  The retire trace alone records only register
    // writes, so a store that writes the wrong value or address stays
    // invisible until something loads it back -- which is exactly what
    // happened chasing the nettle-sha256 failure, where the "first
    // divergence" appeared at a load whose memory had been corrupted much
    // earlier.
    // Log one line per store, on the rising edge of the write.  Level
    // triggering recorded a store once per cycle it was held, so a store
    // spanning a stall appeared several times and the traces could not be
    // aligned between variants -- the 6-stage core logged one store four
    // times.  The write itself is idempotent, so only the logging was wrong.
    reg store_prev;
    always @(posedge clk) begin
        if (reset) store_prev <= 1'b0;
        else begin
            if (have_trace && dmem_we && in_ram && !store_prev)
                $fwrite(trace_fd, "S %h %h %h\n", dmem_addr, dmem_wdata, dmem_mask);
            store_prev <= dmem_we && in_ram;
        end
    end

    always @(posedge clk) begin
        if (!reset && have_trace && retire_valid) begin
            if (retire_rd_we && retire_rd_sig != 5'd0)
                $fwrite(trace_fd, "%0d %h %h x%0d=%h\n", cycle_count,
                        retire_pc, retire_insn, retire_rd_sig, retire_rd_data);
            else
                $fwrite(trace_fd, "%0d %h %h -\n", cycle_count,
                        retire_pc, retire_insn);
        end
    end

    // The testbench raises do_dump once the run ends, however it ended.
    always @(posedge clk) begin
        if (do_dump && !dumped) begin
            dumped <= 1'b1;
            dump_signature;
            dump_profile;
        end
    end

    task dump_signature;
        integer     fd;
        reg [31:0]  addr;
        reg [31:0]  off;
        begin
            if (have_sig && sig_end > sig_begin) begin
                fd = $fopen(sig_file, "w");
                if (fd == 0) begin
                    $display("[sim_top] cannot open signature file");
                end else begin
                    for (addr = sig_begin; addr < sig_end; addr = addr + 4) begin
                        off = addr - 32'h{data_base};
                        $fwrite(fd, "%02x%02x%02x%02x\n",
                                shadow[off + 3], shadow[off + 2],
                                shadow[off + 1], shadow[off + 0]);
                    end
                    $fclose(fd);
                end
            end
        end
    endtask
endmodule
"""


def prepare(v):
    out = os.path.join(ENV, "build", v["name"], "rtl")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    for f in sorted(os.listdir(v["dir"])):
        srcp = os.path.join(v["dir"], f)
        if os.path.isdir(srcp):
            continue
        if not f.endswith(".v") or EXCLUDE.search(f):
            continue
        with open(srcp, errors="ignore") as fh:
            text = fh.read()
        if f == "Instruction_Memory.v":
            text = patch_imem(text)
        elif f == "Data_Memory.v":
            text = patch_dmem(text)
        elif srcp == v["core_file"]:
            text = patch_core(text)
        with open(os.path.join(out, f), "w") as fh:
            fh.write(text)

    # headers: keep them next to the sources so the `include "./x.vh" forms work
    hdrs = os.path.join(v["dir"], "headers")
    if os.path.isdir(hdrs):
        shutil.copytree(hdrs, os.path.join(out, "headers"))
        # RV-RTOS8 includes its headers as "./modules/headers/x.vh", relative
        # to the project root rather than to the source file, so stage a second
        # copy under that path.
        shutil.copytree(hdrs, os.path.join(out, "modules", "headers"))
    for f in sorted(os.listdir(v["dir"])):
        if f.endswith(".vh"):
            shutil.copy(os.path.join(v["dir"], f), out)

    # Two include conventions appear in these repos.  The RV-IM100 family lists
    # every module on the compiler command line and includes only headers; the
    # RV-RTOS8 core `include`s its submodules as "./modules/X.v", so those must
    # be staged under modules/ and compiled through the top file alone --
    # passing them separately would define every module twice.
    staged = sorted(f for f in os.listdir(out) if f.endswith(".v"))
    core_name = os.path.basename(v["core_file"])
    with open(os.path.join(out, core_name), errors="ignore") as fh:
        includes_modules = bool(re.search(r'`include\s+"\.?/?modules/\w+\.v"', fh.read()))

    if includes_modules:
        mod = os.path.join(out, "modules")
        os.makedirs(mod, exist_ok=True)
        for f in staged:
            shutil.copy(os.path.join(out, f), mod)
            os.remove(os.path.join(out, f))
        filelist = ["sim_top.v", os.path.join("modules", core_name)]
    else:
        filelist = ["sim_top.v"] + staged

    with open(os.path.join(out, "filelist.txt"), "w") as fh:
        fh.write("\n".join(filelist) + "\n")

    with open(os.path.join(out, "sim_top.v"), "w") as fh:
        with open(v["core_file"], errors="ignore") as cf:
            patched_core = patch_core(cf.read())
        fh.write(SIM_TOP.format(
            variant=v["name"], module=v["core_module"], xlen=v["xlen"],
            core_inst=core_instantiation(patched_core, v["core_module"]),
            data_base="%08x" % DATA_BASE))
    return out


if __name__ == "__main__":
    want = sys.argv[1:] or None
    for v in all_variants():
        if want and v["name"] not in want:
            continue
        out = prepare(v)
        print("%-22s -> %s (%d files)" % (v["name"], out, len(os.listdir(out))))
