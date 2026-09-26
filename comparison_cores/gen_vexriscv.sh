#!/usr/bin/env bash
# Generate VexRiscv Verilog for the GenFullNoMmuNoCache configuration.
# Uses the JDK bundled with Vivado and a locally-extracted sbt, so nothing is
# installed system-wide.  sbt fetches Scala 2.12.18 and SpinalHDL 1.13.0 on the
# first run, which is the slow part.
set -uo pipefail
export JAVA_HOME=/tools/Xilinx/2025.2/Vivado/tps/lnx64/jre11.0.16_1
export PATH="$JAVA_HOME/bin:$HOME/tools/sbt/sbt/bin:$PATH"
cd "$(dirname "$0")/VexRiscv"
echo "=== sbt runMain vexriscv.demo.GenFullNoMmuNoCache  $(date) ==="
sbt -batch "runMain vexriscv.demo.GenFullNoMmuNoCache"
rc=$?
echo "=== sbt exit $rc  $(date) ==="
ls -la VexRiscv.v 2>/dev/null && echo "GENERATED VexRiscv.v" || echo "NO VERILOG PRODUCED"
