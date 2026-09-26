`timescale 1ns/1ps
// SAIF capture testbench.
// The SoC gates its CPU clock with cpu_clk_enable, which latches on
// benchmark_start (from btn_up) and only AFTER the 3-stage reset sync has
// released -- which itself waits for the MMCM to lock.  Pressing the button
// too early is silently lost, so press well after lock and hold.
module tb_saif;
    reg clk = 0, reset_n = 0, btn_up = 0;
    wire [7:0] led;
    wire uart_tx_in;

    RV64IM72F5SPSoCTOP dut (
        .clk(clk), .reset_n(reset_n), .btn_up(btn_up),
        .led(led), .uart_tx_in(uart_tx_in)
    );

    always #5 clk = ~clk;            // 100 MHz board clock

    integer uart_chars = 0;
    reg prev_tx = 1'b1;
    always @(posedge clk) begin
        if (prev_tx && !uart_tx_in) uart_chars = uart_chars + 1;
        prev_tx <= uart_tx_in;
    end

    initial begin
        reset_n = 0;  btn_up = 0;
        // clk_locked is NOT in the reset synchroniser's sensitivity list, so
        // releasing reset before the MMCM locks latches X into reset_sync and
        // the X never clears.  Hold reset until well past lock (~10 us).
        #30000  reset_n = 1;         // release reset at 30 us, after lock
        #30000  btn_up  = 1;         // press at 60 us
        // held high for the rest of the run: benchmark_start latches once
    end
endmodule
