#!/usr/bin/env python3
"""Discover the RV-IM100 variants under codes/ and describe each one.

Module names in this repo do not track their directories (five different SoC
tops are all literally named RV64IM72F5SPSoCTOP, and the RV32IM cores carry
RV64IM names), so every field here is read out of the RTL rather than derived
from the path.
"""
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "RV-IM100_RTL", "project_files"))
CODES = os.path.join(REPO, "..", "codes")

ORDER = [
    ("RV32s", "RV32I_5SP"),
    ("RV32s", "RV32IM_5SP"),
    ("RV32s", "RV32IM_6SP"),
    ("RV32s", "RV32IM_7SP"),
    ("RV32s", "RV32IM_7SP_BRAM"),
    ("RV32s", "RV32IM_7SP_BRAM_Opt"),
    ("RV32s", "RV32IM_8SP"),
    ("RV64s", "RV64I_5SP"),
    ("RV64s", "RV64IM_5SP"),
    ("RV64s", "RV64IM_6SP"),
    ("RV64s", "RV64IM_7SP"),
    ("RV64s", "RV64IM_7SP_BRAM"),
    ("RV64s", "RV64IM_7SP_BRAM_Opt"),
    ("RV64s", "RV64IM_8SP"),
]


def core_file(vdir):
    """The core top is the one file with the MMIO taps that is not a SoC top."""
    hits = []
    for f in sorted(os.listdir(vdir)):
        if not f.endswith(".v") or f.endswith("_SoC_TOP.v"):
            continue
        p = os.path.join(vdir, f)
        with open(p, errors="ignore") as fh:
            src = fh.read()
        if "MMIO_data_memory_address" in src and re.search(r"^module\s+\w+", src, re.M):
            hits.append((p, src))
    if len(hits) != 1:
        raise RuntimeError("expected exactly one core top in %s, found %d" % (vdir, len(hits)))
    return hits[0]


def describe(family, name):
    vdir = os.path.join(CODES, family, name)
    path, src = core_file(vdir)
    module = re.search(r"^module\s+(\w+)", src, re.M).group(1)
    xlen = int(re.search(r"parameter\s+XLEN\s*=\s*(\d+)", src).group(1))
    ext = "IM" if re.search(r"_5SP|_6SP|_7SP|_8SP", name) and "IM" in name else "I"
    return {
        "name": name,
        "family": family,
        "dir": vdir,
        "core_file": path,
        "core_module": module,
        "xlen": xlen,
        "ext": ext,
        "isa": "RV%d%sZicsr" % (xlen, ext),
        "incdir": os.path.join(vdir, "headers") if os.path.isdir(os.path.join(vdir, "headers")) else vdir,
    }


def all_variants():
    src = os.environ.get("RVIM_SOURCE", "codes")
    if src == "socs":
        return soc_variants()
    if src == "rtos8":
        return rtos8_variants()
    if src == "cores":
        return core_variants()
    return [describe(f, n) for f, n in ORDER]


# The cores/ projects wrap each design in a *_CORE top that externalises the
# instruction and data memories, so Vivado measures core-only area and Fmax
# without constant-propagating through the RAMs.  They are measurement
# artifacts, not runnable processors -- the async family does not even expose
# the ROM-bypass path -- so they are fixed by equivalence with codes/ and
# checked with a lint elaboration rather than by running the test suite.
CORE_PROJECTS = [
    ("RV32I_5SP",             "RV32s/cores/RV32I_5SP"),
    ("RV32IM_5SP",            "RV32s/cores/RV32IM_5SP"),
    ("RV32IM_6SP",            "RV32s/cores/RV32IM_6SP"),
    ("RV32IM_7SP",            "RV32s/cores/RV32IM_7SP"),
    ("RV32IM_7SP_BRAM",       "RV32s/cores/RV32IM_7SP_BRAM"),
    ("RV32IM_7SP_BRAM_Opt",   "RV32s/cores/RV32IM_7SP_BRAM_Opt"),
    ("RV32IM_8SP",            "RV32s/cores/RV32IM_8SP"),
    ("RV32IM_8SP_withoutOpt", "RV32s/cores/RV32IM_8SP_withoutOpt"),
    ("RV64I_5SP",             "RV64s/cores/RV64I_5SP"),
    ("RV64IM_5SP",            "RV64s/cores/RV64IM_5SP"),
    ("RV64IM_6SP",            "RV64s/cores/RV64IM_6SP"),
    ("RV64IM_7SP",            "RV64s/cores/RV64IM_7SP"),
    ("RV64IM_7SP_BRAM",       "RV64s/cores/RV64IM_7SP_BRAM"),
    ("RV64IM_7SP_BRAM_Opt",   "RV64s/cores/RV64IM_7SP_BRAM_Opt"),
    ("RV64IM_8SP",            "RV64s/cores/RV64IM_8SP"),
    ("RV64IM_8SP_withoutOpt", "RV64s/cores/RV64IM_8SP_withoutOpt"),
]


def _find_core_rtl_dir(project):
    root = os.path.join(REPO, project)
    hits = []
    for dirpath, _dirs, files in os.walk(root):
        low = dirpath.lower()
        if ".srcs" not in dirpath or "backup" in low or "archive" in low:
            continue
        for f in files:
            if not f.endswith(".v") or f.endswith("_SoC_TOP.v"):
                continue
            with open(os.path.join(dirpath, f), errors="ignore") as fh:
                src = fh.read()
            if "MMIO_data_memory_address" in src and re.search(r"^module\s+\w+", src, re.M):
                hits.append(dirpath)
    if not hits:
        raise RuntimeError("no core RTL under %s" % project)
    return sorted(set(hits))[0]


def core_variants():
    return [_describe_dir(l, _find_core_rtl_dir(p), "cores_")
            for l, p in CORE_PROJECTS]


def rtos8_variants():
    """RV64_RV-RTOS8: an RV64IM 8-stage SoC with a CLINT, VGA and PS/2.

    A separate lineage from the RV-IM100 family, and materially richer on the
    CSR side -- it implements mscratch, mie and mip, and reports mhartid 0.
    """
    vdir = os.path.join(REPO, "RV64_RV-RTOS8", "modules")
    v = _describe_dir("RV64_RV_RTOS8", vdir, "", ext="IM")
    v["cfg"] = "rv64im_rtos8"   # its own ISA yaml: mscratch, writable MIE, mhartid 0
    return [v]


# ---------------------------------------------------------------------------
# Alternative source tree: the Vivado SoC projects under RV32s/SoCs and
# RV64s/SoCs.  Set RVIM_SOURCE=socs to sweep these instead of codes/.
#
# The SoCs tree also carries the two _withoutOpt 8-stage cores, which codes/
# does not.  RV64s/SoCs/archive holds superseded revisions and is skipped.
# ---------------------------------------------------------------------------

SOC_PROJECTS = [
    ("RV32I_5SP",             "RV32s/SoCs/RV32I_5SP"),
    ("RV32IM_5SP",            "RV32s/SoCs/RV32IM_5SP"),
    ("RV32IM_6SP",            "RV32s/SoCs/RV32IM_6SP"),
    ("RV32IM_7SP",            "RV32s/SoCs/RV32IM_7SP"),
    ("RV32IM_7SP_BRAM",       "RV32s/SoCs/RV32IM_7SP_BRAM"),
    ("RV32IM_7SP_BRAM_Opt",   "RV32s/SoCs/RV32IM_7SP_BRAM_Opt"),
    ("RV32IM_8SP",            "RV32s/SoCs/RV32IM_8SP"),
    ("RV32IM_8SP_withoutOpt", "RV32s/SoCs/RV32IM_8SP_withoutOpt"),
    ("RV64I_5SP",             "RV64s/SoCs/RV64I5SP_SoC"),
    ("RV64IM_5SP",            "RV64s/SoCs/RV64IM_5SP"),
    ("RV64IM_6SP",            "RV64s/SoCs/RV64IM_6SP"),
    ("RV64IM_7SP",            "RV64s/SoCs/RV64IM_7SP"),
    ("RV64IM_7SP_BRAM",       "RV64s/SoCs/RV64IM_7SP_BRAM"),
    ("RV64IM_7SP_BRAM_Opt",   "RV64s/SoCs/RV64IM_7SP_BRAM_Opt"),
    ("RV64IM_8SP",            "RV64s/SoCs/RV64IM_8SP"),
    ("RV64IM_8SP_withoutOpt", "RV64s/SoCs/RV64IM_8SP_withoutOpt"),
]

def _find_rtl_dir(project):
    """Locate the directory holding the core RTL inside a Vivado project.

    Only the project's own sources count: some projects keep sibling backup
    trees (RV64IM_8SP has a pre_retire_stall_backup) that must not be picked
    up, and the core-only projects export a memory-externalised *_CORE top
    this harness cannot drive.
    """
    root = os.path.join(REPO, project)
    hits = []
    for dirpath, _dirs, files in os.walk(root):
        low = dirpath.lower()
        if ".srcs" not in dirpath or "backup" in low or "archive" in low:
            continue
        for f in files:
            if not f.endswith(".v") or f.endswith("_SoC_TOP.v"):
                continue
            with open(os.path.join(dirpath, f), errors="ignore") as fh:
                src = fh.read()
            if ("MMIO_data_memory_address" in src
                    and "DataMemory data_memory" in src
                    and re.search(r"^module\s+\w+", src, re.M)):
                hits.append(dirpath)
    if not hits:
        raise RuntimeError("no core RTL under %s" % project)
    return sorted(set(hits))[0]


def _describe_dir(label, vdir, prefix, ext=None):
    path, src = core_file(vdir)
    module = re.search(r"^module\s+(\w+)", src, re.M).group(1)
    xlen = int(re.search(r"parameter\s+XLEN\s*=\s*(\d+)", src).group(1))
    ext = ext or ("IM" if "IM" in label else "I")
    return {
        "name": prefix + label,
        "family": "RV32s" if xlen == 32 else "RV64s",
        "dir": vdir,
        "core_file": path,
        "core_module": module,
        "xlen": xlen,
        "ext": ext,
        "isa": "RV%d%sZicsr" % (xlen, ext),
        "incdir": os.path.join(vdir, "headers") if os.path.isdir(os.path.join(vdir, "headers")) else vdir,
    }


def soc_variants():
    out = []
    for label, project in SOC_PROJECTS:
        out.append(_describe_dir(label, _find_rtl_dir(project), "socs_"))
    return out


if __name__ == "__main__":
    print("%-22s %-24s %-5s %-4s %-14s %s" % ("VARIANT", "CORE MODULE", "XLEN", "EXT", "ISA", "HEADERS"))
    for v in all_variants():
        print("%-22s %-24s %-5d %-4s %-14s %s" % (
            v["name"], v["core_module"], v["xlen"], v["ext"], v["isa"],
            "headers/" if v["incdir"].endswith("headers") else "flat"))
