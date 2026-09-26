import logging
import os
import re
import shutil
import subprocess

import riscof.utils as utils
from riscof.pluginTemplate import pluginTemplate

logger = logging.getLogger()


class rv_im100(pluginTemplate):
    """RISCOF DUT plugin for the RV-IM100 family.

    One plugin serves all 14 variants; the caller picks a variant by pointing
    dut_exe at that variant's Verilated simulator and ispec at the matching ISA
    yaml.  The -march string is derived from the yaml rather than hardcoded, so
    an RV32I core is built as rv32i_zicsr and never handed M instructions.
    """

    __model__ = "rv_im100"
    __version__ = "2.0.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = kwargs.get("config")
        if config is None:
            raise SystemExit("[rv_im100] missing config section in config.ini")

        # Resolve against the config file's directory, not the cwd, so runs can
        # be launched from anywhere.
        self.cfg_dir = os.path.abspath(kwargs.get("config_dir", os.getcwd()))

        def rel(p):
            return p if os.path.isabs(p) else os.path.abspath(os.path.join(self.cfg_dir, p))

        self.pluginpath = rel(config["pluginpath"])
        self.isa_spec = rel(config["ispec"])
        self.platform_spec = rel(config["pspec"])
        self.dut_exe = rel(config["dut_exe"])
        self.xprefix = config.get("cross_prefix", "riscv64-unknown-elf-")
        self.max_cycles = str(config.get("max_cycles", "20000000"))
        self.timeout = int(config.get("timeout", "600"))
        self.variant = config.get("variant", "rv_im100")

    def initialise(self, suite, work_dir, archtest_env):
        self.suite_dir = suite
        self.work_dir = work_dir
        self.archtest_env = archtest_env

    def build(self, isa_yaml, platform_yaml):
        ispec = utils.load_yaml(isa_yaml)["hart0"]
        self.xlen = "64" if 64 in ispec["supported_xlen"] else "32"

        # Base letters first, then the Z extensions.  Both toolchains are built
        # with --with-isa-spec=20191213, where zicsr is no longer implied by i,
        # so it has to be spelled out or every csr instruction fails to
        # assemble.  Order matters: the base part must precede any underscore.
        isa = ispec["ISA"]
        base = isa.split("Z")[0]
        march = "rv" + self.xlen
        for letter in ("I", "M", "A", "F", "D", "C"):
            if letter in base[4:]:
                march += letter.lower()
        for z in ("Zicsr", "Zifencei"):
            if z in isa:
                march += "_" + z.lower()
        self.march = march
        self.mabi = "lp64" if self.xlen == "64" else "ilp32"

        if not os.path.isfile(self.dut_exe):
            raise SystemExit("[rv_im100] simulator not found: %s" % self.dut_exe)
        if shutil.which(self.xprefix + "gcc") is None:
            raise SystemExit("[rv_im100] %sgcc not on PATH" % self.xprefix)

        logger.info("[rv_im100] variant=%s march=%s mabi=%s exe=%s",
                    self.variant, self.march, self.mabi, self.dut_exe)

        self.compile_cmd = (
            "{prefix}gcc -march={march} -mabi={mabi} "
            "-static -mcmodel=medany -fvisibility=hidden "
            "-nostdlib -nostartfiles "
            "-T {plugin}/env/link.ld -I {plugin}/env/ -I {env} "
            "{{src}} -o {{elf}} {{macros}}"
        ).format(prefix=self.xprefix, march=self.march, mabi=self.mabi,
                 plugin=self.pluginpath, env=self.archtest_env)

    def _sig_bounds(self, elf):
        out = subprocess.check_output([self.xprefix + "nm", elf], text=True)
        begin = end = None
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                if parts[2] == "begin_signature":
                    begin = parts[0]
                elif parts[2] == "end_signature":
                    end = parts[0]
        return begin, end

    def runTests(self, testList):
        for testname, entry in testList.items():
            src = entry["test_path"]
            tdir = entry["work_dir"]
            os.makedirs(tdir, exist_ok=True)

            elf = os.path.join(tdir, "dut.elf")
            hexf = os.path.join(tdir, "dut.hex")
            sig = os.path.join(tdir, self.name[:-1] + ".signature")
            log = os.path.join(tdir, "dut.log")

            macros = " ".join("-D" + m for m in entry.get("macros", []))
            cmd = self.compile_cmd.format(src=src, elf=elf, macros=macros)

            with open(log, "w") as lf:
                lf.write("$ %s\n" % cmd)
                r = subprocess.run(cmd, shell=True, cwd=tdir, text=True,
                                   capture_output=True)
                lf.write(r.stdout + r.stderr)
                if r.returncode != 0:
                    logger.error("[rv_im100] compile failed: %s", testname)
                    continue

                # One contiguous ROM image.  .data is included because its load
                # address sits right after .rodata; the boot code copies it into
                # RAM, which is why no separate data image is needed.
                bin_tmp = os.path.join(tdir, "dut.bin")
                oc = ("{p}objcopy -O binary -j .text.init -j .text -j .rodata "
                      "-j .data {e} {b}").format(p=self.xprefix, e=elf, b=bin_tmp)
                lf.write("\n$ %s\n" % oc)
                r = subprocess.run(oc, shell=True, cwd=tdir, text=True,
                                   capture_output=True)
                lf.write(r.stdout + r.stderr)
                if r.returncode != 0:
                    logger.error("[rv_im100] objcopy failed: %s", testname)
                    continue

                with open(bin_tmp, "rb") as bf, open(hexf, "w") as hf:
                    blob = bf.read()
                    if len(blob) % 4:
                        blob += b"\x00" * (4 - len(blob) % 4)
                    for i in range(0, len(blob), 4):
                        hf.write("%08x\n" % int.from_bytes(blob[i:i + 4], "little"))
                os.remove(bin_tmp)

                begin, end = self._sig_bounds(elf)
                if begin is None or end is None:
                    logger.error("[rv_im100] no signature symbols: %s", testname)
                    continue

                run = ("{exe} +HEX={hex} +SIG_BEGIN={b} +SIG_END={e} "
                       "+SIG_FILE={s} +MAX_CYCLES={c}").format(
                    exe=self.dut_exe, hex=hexf, b=begin, e=end, s=sig,
                    c=self.max_cycles)
                lf.write("\n$ %s\n" % run)
                try:
                    r = subprocess.run(run, shell=True, cwd=tdir, text=True,
                                       capture_output=True, timeout=self.timeout)
                    lf.write(r.stdout + r.stderr)
                    if "TIMEOUT" in r.stdout:
                        logger.warning("[rv_im100] %s hit the cycle limit", testname)
                except subprocess.TimeoutExpired:
                    # Never abort the sweep for one wedged test.
                    lf.write("\n[rv_im100] wall-clock timeout after %ds\n" % self.timeout)
                    logger.warning("[rv_im100] %s wall-clock timeout", testname)

            if os.path.isfile(sig):
                entry["result"] = sig
            else:
                logger.error("[rv_im100] no signature produced: %s", testname)
