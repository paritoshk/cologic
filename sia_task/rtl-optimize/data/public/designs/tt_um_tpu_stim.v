// Scaffold-fill stimulus for tt_um_tpu (2x2 signed matmul accelerator).
//
// The harness owns the differential testbench shell: the free-running clk, the
// dual __DUT__/__REF__ instantiation, the input/output port declarations, the
// `rlhdl_sample` comparator (checks every output of candidate vs reference), and
// the `RESULT <passed> <total>` line. This file supplies only module-scope
// helpers plus `task stimulus;` — the entry point the harness calls. It drives
// the input ports by name, advances time with @(posedge clk), and calls
// `rlhdl_sample;` wherever candidate and reference must agree.

  integer scenario;
  integer i;
  integer unused;
  logic [7:0] a [0:3];
  logic [7:0] b [0:3];

  task reset_all;
    begin
      ena = 1'b1;
      ui_in = 8'd0;
      uio_in = 8'd0;
      rst_n = 1'b0;
      repeat (5) @(posedge clk);
      rst_n = 1'b1;
      repeat (2) @(posedge clk);
    end
  endtask

  // Load one matrix element: sel picks matrix A(0)/B(1), idx picks the cell.
  task load_elem(input integer sel, input integer idx, input [7:0] value);
    begin
      ui_in = value;
      uio_in = ((sel & 1) << 1) | ((idx & 3) << 2) | 1;
      @(posedge clk);
      #1;
      uio_in = 8'd0;
      @(posedge clk);
      #1;
    end
  endtask

  task load_current_matrices;
    begin
      for (i = 0; i < 4; i = i + 1) load_elem(0, i, a[i]);
      for (i = 0; i < 4; i = i + 1) load_elem(1, i, b[i]);
    end
  endtask

  // Walk the four output cells of A*B, sampling candidate-vs-reference at each.
  task sample_outputs;
    begin
      repeat (3) @(posedge clk);
      for (i = 0; i < 4; i = i + 1) begin
        uio_in = ((i & 3) << 5) | (1 << 4);
        @(posedge clk);
        #1;
        rlhdl_sample;
        uio_in = 8'd0;
        @(posedge clk);
        #1;
      end
    end
  endtask

  task stimulus;
    begin
      unused = $urandom(__SEED__);
      reset_all();
      for (scenario = 0; scenario < __N_VECTORS__; scenario = scenario + 1) begin
        for (i = 0; i < 4; i = i + 1) begin
          a[i] = $urandom_range(0, 7);
          b[i] = $urandom_range(0, 7);
        end
        load_current_matrices();
        sample_outputs();

        for (i = 0; i < 4; i = i + 1) begin
          a[i] = $urandom_range(0, 7);
          b[i] = $urandom_range(0, 7);
        end
        load_current_matrices();
        sample_outputs();

        reset_all();
      end
    end
  endtask
