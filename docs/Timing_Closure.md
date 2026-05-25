# Timing Closure Methodology

Pipeline deepening addresses timing at the structural level, but each configuration also requires RTL-level optimization to eliminate secondary critical paths. Our timing closure process follows a three-phase iterative approach:

1. Analyze post-implementation timing reports to identify the dominant critical path.
2. Apply targeted RTL modifications without altering pipeline structure.
3. Evaluate whether remaining paths necessitate stage insertion.

## 7-Stage RTL Optimization

Static timing analysis on the initial 7-stage SoC (operating at 55.9 MHz) under a 10 ns constraint identified the critical path as a single-cycle chain in the **EX stage** with a total delay of 16.1 ns (logic 5.0 ns, net 11.1 ns). Net delay accounted for 69% of the total, indicating that high fan-out routing on forwarding control signals was the primary bottleneck.

Twelve RTL optimizations were applied iteratively across three categories:

- **Forwarding network optimizations**
- **Pre-computation**: relocating operations to earlier stages where inputs were already registered.
- **Deferral**: moving operations to later stages as deliberate trade-offs.

The three most effective optimizations were:

- MEM forwarding data pre-registration (-2.394 ns)
  - Eliminated the MEM-stage opcode decode from the forwarding data selection path.
- **WB forwarding data pre-registration** (-0.942 ns)
- One-hot multiplexer conversion (-0.739 ns)
  - Flattened the cascaded 4-level forwarding multiplexer to a single wide-OR level, reducing the forwarding fan-out from 177 to 88.

The cumulative effect was a **29% reduction in data path delay** (16.1 to 11.4 ns). The overall trend is downward, although individual steps occasionally show net delay increases due to placement variation across synthesis runs.

## Residual Critical Path and EXR Stage Insertion

The residual critical path after RTL optimization consisted of three serially irreducible components:

- Hazard detection (~2 ns)
- Forwarding and source selection (~2 ns)
- 64-bit ALU computation (~4 ns)

Including ~2.5 ns clock overhead, the minimum period was constrained to ~10.5 ns. Closing the gap to 10 ns (100 MHz) required inserting the **EXR stage**.

## Design Principle

A common principle underlies both pre-computation and deferral: an operation need not be evaluated in the pipeline stage where its result is consumed. Advancing computations to stages where inputs are already available, or deferring them to stages with less timing pressure, enables workload balancing without modifying pipeline structure.



## Cumulative Timing Closure Results for the 7-Stage Pipeline

| Category        | Optimization           | Logic (ns) | Net (ns) | Total (ns) |
| --------------- | ---------------------- | ---------- | -------- | ---------- |
|                 | Initial 7-stage        | 5.0        | 11.1     | 16.1       |
| Forwarding      | One-hot MUX conv.      | 4.1        | 11.2     | 15.4       |
|                 | Retire fwd. elim.      | 4.9        | 10.1     | 15.0       |
|                 | CSR fwd. elim.         | 5.7        | 9.0      | 14.7       |
|                 | BR fwd. pre-reg.       | 4.0        | 10.4     | 15.4       |
|                 | MEM fwd. data pre-reg. | 3.4        | 9.6      | 13.0       |
|                 | WB fwd. data pre-reg.  | 4.5        | 7.6      | 12.1       |
|                 | Encoded MUX restruct.  | 3.2        | 9.2      | 12.4       |
| Pre-computation | MMIO cmp. (MEM→BR)     | 5.4        | 6.6      | 12.0       |
|                 | CSR valid. (ID→IO)     | 3.1        | 8.6      | 11.6       |
|                 | Hazard sig. (EX→ID)    | 3.1        | 8.8      | 11.9       |
| Deferral        | Exc.Det. (EX→BR)       | 4.8        | 7.2      | 12.0       |
|                 | JALR res. (EX→BR)      | 3.4        | 8.4      | 11.9       |
|                 | ALU sign-ext. (EX→BR)  | 2.8        | 8.5      | 11.4       |
|                 | **Final 7-stage**      | **2.8**    | **8.5**  | **~11.4**  |