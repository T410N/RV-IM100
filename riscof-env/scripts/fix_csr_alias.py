#!/usr/bin/env python3
"""Fix the CSR address aliasing defect in the RV-IM100 core tops.

THE DEFECT
----------
The core top drives the CSR file's read address from the decoded immediate of
whatever instruction is in ID, unconditionally:

    csr_read_address = raw_imm[11:0];

For an S-type that immediate is the raw store offset, and CSR_File.v compares it
against the implemented CSR addresses with no opcode qualification
(`assign csr_access = valid_csr_address;`).  So `sd rs2, 768(rs1)` -- offset
768 = 0x300 = mstatus -- spuriously pulls csr_ready low for a cycle.  That raises
pc_stall, and PC_Controller has no pending-redirect register: it simply does
`else next_pc = pc;`, discarding a branch or jump redirect issued in the same
cycle.  Hazard_Unit flushes regardless, so the target instruction is destroyed
and never re-fetched.  In the arch tests this shows up as bge/bgeu/blt/bne
losing exactly the signature stores that use offset 768.

Four variants read the address from instruction[31:20] instead, which for an
S-type is {imm[11:5], rs2} and happens to miss the compare list -- they pass by
coincidence, not by correctness, and are patched here too.

THE FIX
-------
Present a CSR address only when the instruction actually is a CSR instruction.
12'hFFF is not in any variant's implemented set, so it reads as "no access".
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from variants import all_variants  # noqa: E402

PATCH_A_OLD = "csr_read_address = raw_imm[11:0];"
PATCH_A_NEW = "\n".join([
    "// Only a real CSR instruction may present a CSR address.  raw_imm is",
    "            // the decoded immediate of whatever sits in ID, so a store such as",
    "            // sd rs2,768(rs1) would otherwise alias onto 0x300 (mstatus), drop",
    "            // csr_ready, raise pc_stall, and make PC_Controller discard a",
    "            // branch redirect issued in the same cycle.",
    "            csr_read_address = ((opcode == `OPCODE_ENVIRONMENT) && (funct3 != `CSR_NONE))",
    "                               ? raw_imm[11:0] : 12'hFFF;",
])

IO_NOTE = """    // Same qualification on the IO-stage path.  instruction[31:20] for an
    // S-type is {imm[11:5], rs2}, which merely happens to miss the compare
    // list below -- a B- or R-type landing on 0x300 would reproduce the fault.
"""


def header_defining(vdir, macro):
    """Which .vh in this variant defines the macro, if any."""
    for root in (os.path.join(vdir, "headers"), vdir):
        if not os.path.isdir(root):
            continue
        for f in sorted(os.listdir(root)):
            if f.endswith(".vh"):
                with open(os.path.join(root, f), errors="ignore") as fh:
                    if re.search(r"^\s*`define\s+%s\b" % macro, fh.read(), re.M):
                        return f
    return None


def ensure_includes(src, needed):
    incs = set(re.findall(r'`include\s+"\./(\S+?)"', src))
    missing = [h for h in needed if h and h not in incs]
    if not missing:
        return src, []
    last = None
    for m in re.finditer(r'^`include\s+"\./\S+?"\s*$', src, re.M):
        last = m
    add = "".join('\n`include "./%s"' % h for h in missing)
    if last:
        return src[:last.end()] + add + src[last.end():], missing
    return add.lstrip("\n") + "\n" + src, missing


def patch_io_chain(src):
    """Qualify the IO-stage valid-CSR-address chain with a real CSR decode."""
    # the chain may carry a trailing // comment after the closing ";"
    m = re.search(r"( *)wire IO_valid_csr_address = (.*?;)([ \t]*//[^\n]*)?\n", src, re.S)
    if not m:
        return src, False
    indent, chain = m.group(1), m.group(2)
    if "IO_is_csr_insn" in src:
        return src, False
    chain = chain.rstrip().rstrip(";")
    # re-indent the continuation lines to sit under the new opening paren
    body = "\n".join(l.strip() for l in chain.splitlines())
    body = ("\n" + indent + "                             ").join(body.splitlines())
    new = (
        IO_NOTE
        + "%swire IO_is_csr_insn = (IO_instruction[6:0] == `OPCODE_ENVIRONMENT) &&\n" % indent
        + "%s                      (IO_instruction[14:12] != `CSR_NONE);\n" % indent
        + "%swire IO_valid_csr_address = IO_is_csr_insn &&\n" % indent
        + "%s                            (%s);\n" % (indent, body)
    )
    return src[:m.start()] + new + src[m.end():], True


def main():
    want = sys.argv[1:] or None
    for v in all_variants():
        if want and v["name"] not in want:
            continue
        path = v["core_file"]
        with open(path, errors="ignore") as fh:
            src = fh.read()
        orig = src
        did = []

        if PATCH_A_OLD in src:
            src = src.replace(PATCH_A_OLD, PATCH_A_NEW, 1)
            did.append("raw_imm")

        src, io = patch_io_chain(src)
        if io:
            did.append("IO_chain")

        if did:
            opc = header_defining(v["dir"], "OPCODE_ENVIRONMENT")
            csr = header_defining(v["dir"], "CSR_NONE")
            src, added = ensure_includes(src, [opc, csr])
            if added:
                did.append("+includes(%s)" % ",".join(added))

        if src != orig:
            with open(path, "w") as fh:
                fh.write(src)
            print("%-22s %s" % (v["name"], ", ".join(did)))
        else:
            print("%-22s (no change)" % v["name"])


if __name__ == "__main__":
    main()
