`timescale 1ns/1ps

module RV64IM72F6SP_SoC_tb #(
    parameter XLEN = 64
);
    reg clk;
    reg reset_n;
    reg btn_up;

    wire [7:0] led;
    wire uart_tx_in;

    RV64IM72F5SPSoCTOP rv64im72f_6sp_top (
        .clk(clk),
        .reset_n(reset_n),
        .btn_up(btn_up),

        .led(led),
        .uart_tx_in(uart_tx_in)
    );

    // Generate clock signal (period = 10ns)
    always #5 clk = ~clk;

    initial begin
        $dumpfile("testbenches/results/waveforms/RV64IM72F_6SP_SoC_tb.vcd");
        $dumpvars(0, rv64im72f_6sp_top);

        $display("==================== RV64IM72F_6SP_SoC Test START ====================");

        clk = 0;
        reset_n = 0;
        btn_up = 0;

        #10;

        reset_n = 1;

        #10;

        btn_up = 1;

        #10000;

        btn_up = 0;

        #364000;

        $display("\n====================  RV64IM72F_6SP_SoC Test END  ====================");
        $stop;
    end

endmodule
