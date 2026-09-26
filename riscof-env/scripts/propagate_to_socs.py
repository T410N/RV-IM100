#!/usr/bin/env python3
"""Copy the verified RTL from codes/ into the Vivado SoC project trees.

codes/ is the canonical source for this campaign: RISCOF runs against it, so it
is the only tree whose correctness has been measured.  The SoCs projects hold
their own copies, and those are what Vivado synthesizes -- so once a fix is
verified, the two must be brought back into agreement or the re-synthesis would
measure different RTL than the one that passed.

Twelve of the fourteen designs were already byte-identical once line endings
were normalised.  This script makes the rest match and reports exactly what it
changed, so the sync is auditable rather than silent.

Usage:
    scripts/propagate_to_socs.py --dry-run      # report differences only
    scripts/propagate_to_socs.py                # copy codes/ -> SoCs/
"""
import argparse
import filecmp
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import variants as V  # noqa: E402


# Files that legitimately differ per project and must never be overwritten:
# the ROM image names a different benchmark build, UART_TX carries a
# clock-frequency-dependent BAUD_DIV, and the SoC top wires board-specific IP.
SKIP = {"Instruction_Memory.v", "UART_TX.v", "Unified_UART_Controller.v"}


def skip(f):
    return f in SKIP or f.endswith("_SoC_TOP.v")


def build_map(target):
    """Pair each codes/ variant with its counterpart in the target tree."""
    import importlib
    os.environ["RVIM_SOURCE"] = target
    importlib.reload(V)
    pick = V.soc_variants if target == "socs" else V.core_variants
    dst = {v["name"].split("_", 1)[1]: v["dir"] for v in pick()}
    os.environ["RVIM_SOURCE"] = "codes"
    importlib.reload(V)
    cod = {v["name"]: v["dir"] for v in V.all_variants()}
    # The cores/ projects hold a memory-externalised *_CORE top under the SAME
    # filename as the codes/ top but with a different module and port list, so
    # the top must never be copied there -- it is patched in place instead.
    tops = {}
    if target == "cores":
        os.environ["RVIM_SOURCE"] = "codes"
        importlib.reload(V)
        tops = {v["name"]: os.path.basename(v["core_file"]) for v in V.all_variants()}
    return [(n, cod[n], dst[n], tops.get(n)) for n in cod if n in dst], \
           [n for n in cod if n not in dst]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--target", choices=["socs", "cores"], default="socs")
    args = ap.parse_args()

    pairs, unmatched = build_map(args.target)
    total = 0
    for name, cdir, sdir, keep_top in sorted(pairs):
        changed = []
        for f in sorted(os.listdir(cdir)):
            if not f.endswith((".v", ".vh")) or skip(f) or f == keep_top:
                continue
            src, dst = os.path.join(cdir, f), os.path.join(sdir, f)
            if not os.path.isfile(dst):
                continue          # SoCs-only layout difference; leave alone
            if filecmp.cmp(src, dst, shallow=False):
                continue
            changed.append(f)
            if not args.dry_run:
                shutil.copyfile(src, dst)
        # headers live in a subdirectory on most variants
        hsrc = os.path.join(cdir, "headers")
        hdst = os.path.join(sdir, "headers")
        if os.path.isdir(hsrc) and os.path.isdir(hdst):
            for f in sorted(os.listdir(hsrc)):
                if not f.endswith(".vh"):
                    continue
                a, b = os.path.join(hsrc, f), os.path.join(hdst, f)
                if os.path.isfile(b) and not filecmp.cmp(a, b, shallow=False):
                    changed.append("headers/" + f)
                    if not args.dry_run:
                        shutil.copyfile(a, b)
        total += len(changed)
        print("%-22s %s" % (name, ", ".join(changed) if changed else "in sync"))

    for n in unmatched:
        print("%-22s (no SoCs counterpart)" % n)
    print("\n%s %d file(s)" % ("would copy" if args.dry_run else "copied", total))


if __name__ == "__main__":
    main()
