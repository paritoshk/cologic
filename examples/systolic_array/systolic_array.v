// Output-stationary NxN systolic array. Computes C = A x B for signed integers.
// A flows west->east, B flows north->south, each PE holds one accumulator C[i][j].
// Inputs are pre-skewed by the testbench (row i delayed by i, col j delayed by j),
// so at PE(i,j) on every cycle the incoming a/b share the same contraction index k.
module systolic_array #(
  parameter N    = 4,   // array dimension
  parameter DW   = 8,   // input operand width
  parameter ACCW = 32   // accumulator width
)(
  input  wire                    clk,
  input  wire                    rst,
  input  wire signed [DW-1:0]    a_west  [0:N-1],          // left edge, one per row
  input  wire signed [DW-1:0]    b_north [0:N-1],          // top edge, one per col
  output wire signed [ACCW-1:0]  c_out   [0:N-1][0:N-1]    // accumulators
);
  reg signed [DW-1:0]   a_reg [0:N-1][0:N-1];   // a passed east, registered
  reg signed [DW-1:0]   b_reg [0:N-1][0:N-1];   // b passed south, registered
  reg signed [ACCW-1:0] acc   [0:N-1][0:N-1];

  integer i, j;
  always @(posedge clk) begin
    if (rst) begin
      for (i = 0; i < N; i = i + 1)
        for (j = 0; j < N; j = j + 1) begin
          a_reg[i][j] <= 0;
          b_reg[i][j] <= 0;
          acc[i][j]   <= 0;
        end
    end else begin
      for (i = 0; i < N; i = i + 1)
        for (j = 0; j < N; j = j + 1) begin
          // incoming operands: from the edge on the boundary, else from the neighbor
          // ponytail: inlined the two muxes; a named a_in/b_in wire array reads no clearer here
          a_reg[i][j] <= (j == 0) ? a_west[i]  : a_reg[i][j-1];
          b_reg[i][j] <= (i == 0) ? b_north[j] : b_reg[i-1][j];
          acc[i][j]   <= acc[i][j]
                       + ((j == 0) ? a_west[i]  : a_reg[i][j-1])
                       * ((i == 0) ? b_north[j] : b_reg[i-1][j]);
        end
    end
  end

  genvar gi, gj;
  generate
    for (gi = 0; gi < N; gi = gi + 1)
      for (gj = 0; gj < N; gj = gj + 1) begin : outmap
        assign c_out[gi][gj] = acc[gi][gj];
      end
  endgenerate
endmodule
