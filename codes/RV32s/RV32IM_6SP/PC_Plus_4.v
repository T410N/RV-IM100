module PCPlus4 # (
    parameter XLEN = 32
)(
    input [XLEN-1:0] pc,        // Current pc value
	output [XLEN-1:0] pc_plus_4 // pc+4 value
);
    assign pc_plus_4 = pc + 4;

endmodule