# Same constraint the RV-IM100 cores are synthesized under: 5 ns (200 MHz).
# The constraint is deliberately unreachable so every design reports a negative
# WNS, and Fmax = 1000/(5 - WNS) is read off a fully-optimised result rather
# than one the tool stopped working on once it met an easy target.
create_clock -period 5.000 -name clk [get_ports clk]
