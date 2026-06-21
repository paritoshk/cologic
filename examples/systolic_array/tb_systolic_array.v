// Testbench for systolic_array: drives a pre-skewed feed, checks against a golden
// in-TB matmul, and prints PASS / FAIL (the verifiable reward signal the harness reads).
`timescale 1ns/1ps
module tb;
  localparam N = 4, DW = 8, ACCW = 32;

  reg clk = 0, rst = 1;
  reg  signed [DW-1:0]   A [0:N-1][0:N-1];
  reg  signed [DW-1:0]   B [0:N-1][0:N-1];
  reg  signed [DW-1:0]   a_west  [0:N-1];
  reg  signed [DW-1:0]   b_north [0:N-1];
  wire signed [ACCW-1:0] c_out   [0:N-1][0:N-1];
  integer i, j, k, t, errors;
  integer golden [0:N-1][0:N-1];

  systolic_array #(.N(N), .DW(DW), .ACCW(ACCW)) dut (
    .clk(clk), .rst(rst), .a_west(a_west), .b_north(b_north), .c_out(c_out)
  );

  always #5 clk = ~clk;

  initial begin
    $dumpfile("dump.vcd");
    $dumpvars(0, tb);

    for (i = 0; i < N; i = i + 1)
      for (j = 0; j < N; j = j + 1) begin
        A[i][j] = (i + j) % 7 - 3;      // small signed operands
        B[i][j] = (i * 2 + j) % 5 - 2;
      end

    for (i = 0; i < N; i = i + 1)
      for (j = 0; j < N; j = j + 1) begin
        golden[i][j] = 0;
        for (k = 0; k < N; k = k + 1)
          golden[i][j] = golden[i][j] + A[i][k] * B[k][j];
      end

    for (i = 0; i < N; i = i + 1) begin a_west[i] = 0; b_north[i] = 0; end

    @(negedge clk); rst = 1;
    @(negedge clk); rst = 0;

    // feed t = 0 .. 3N+1: row i skewed by i, col j skewed by j; zeros outside the window
    for (t = 0; t < 3*N + 2; t = t + 1) begin
      for (i = 0; i < N; i = i + 1)
        a_west[i]  = (t >= i && t < i + N) ? A[i][t-i] : 0;
      for (j = 0; j < N; j = j + 1)
        b_north[j] = (t >= j && t < j + N) ? B[t-j][j] : 0;
      @(posedge clk);
      #1;
    end

    errors = 0;
    for (i = 0; i < N; i = i + 1)
      for (j = 0; j < N; j = j + 1)
        if (c_out[i][j] !== golden[i][j]) begin
          errors = errors + 1;
          $display("MISMATCH C[%0d][%0d] = %0d  expected %0d", i, j, c_out[i][j], golden[i][j]);
        end

    if (errors == 0) $display("PASS: %0dx%0d systolic matmul verified", N, N);
    else             $display("FAIL: %0d mismatches", errors);
    $finish;
  end
endmodule
