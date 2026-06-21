"""Seed task library. Each task carries a golden reference used as the grading
oracle (see verifier.grade).

Two splits:
  TRAIN_TASKS   - what the policy trains/evals on during development.
  HELDOUT_TASKS - perturbations of the same concepts (renamed signals, changed
                  widths, recombined / inverted functions). These give the
                  *headline* number: warm-started Verilog models may have seen
                  public benchmarks, so the gain must be measured on tasks that
                  are structurally novel. held_out=True.

Difficulty is intentionally mixed so a warm-started 7B lands ~20-60% (dead-signal
guard from the RL de-risking checklist).
"""

from __future__ import annotations

from cologic.schema import Port, Task

TRAIN_TASKS: list[Task] = [
    Task(
        task_id="mux2",
        top_module="mux2",
        spec=(
            "Implement an 8-bit 2-to-1 multiplexer. When `sel` is 0, output `y` "
            "equals input `a`; when `sel` is 1, `y` equals input `b`."
        ),
        interface=[Port("a", "input", 8), Port("b", "input", 8), Port("sel", "input", 1), Port("y", "output", 8)],
        reference_rtl=(
            "module mux2(input [7:0] a, input [7:0] b, input sel, output [7:0] y);\n"
            "  assign y = sel ? b : a;\n"
            "endmodule\n"
        ),
        tags=["comb", "mux"],
    ),
    Task(
        task_id="mux4",
        top_module="mux4",
        spec=(
            "Implement an 8-bit 4-to-1 multiplexer. The 2-bit `sel` selects one of "
            "the four 8-bit inputs onto `y`: 0->a, 1->b, 2->c, 3->d."
        ),
        interface=[
            Port("a", "input", 8), Port("b", "input", 8), Port("c", "input", 8),
            Port("d", "input", 8), Port("sel", "input", 2), Port("y", "output", 8),
        ],
        reference_rtl=(
            "module mux4(input [7:0] a, input [7:0] b, input [7:0] c, input [7:0] d,\n"
            "            input [1:0] sel, output [7:0] y);\n"
            "  assign y = (sel == 2'd0) ? a : (sel == 2'd1) ? b : (sel == 2'd2) ? c : d;\n"
            "endmodule\n"
        ),
        tags=["comb", "mux"],
    ),
    Task(
        task_id="add4",
        top_module="add4",
        spec=(
            "Implement a 4-bit adder with carry-out. `sum` (4 bits) is the low 4 "
            "bits of `a + b`; `cout` (1 bit) is the carry out of the addition."
        ),
        interface=[Port("a", "input", 4), Port("b", "input", 4), Port("sum", "output", 4), Port("cout", "output", 1)],
        reference_rtl=(
            "module add4(input [3:0] a, input [3:0] b, output [3:0] sum, output cout);\n"
            "  assign {cout, sum} = a + b;\n"
            "endmodule\n"
        ),
        tags=["comb", "arith"],
    ),
    Task(
        task_id="cmp8",
        top_module="cmp8",
        spec=(
            "Implement an 8-bit unsigned comparator. Set `gt` when `a > b`, `eq` "
            "when `a == b`, and `lt` when `a < b`. Exactly one output is high."
        ),
        interface=[
            Port("a", "input", 8), Port("b", "input", 8),
            Port("gt", "output", 1), Port("eq", "output", 1), Port("lt", "output", 1),
        ],
        reference_rtl=(
            "module cmp8(input [7:0] a, input [7:0] b, output gt, output eq, output lt);\n"
            "  assign gt = a > b;\n  assign eq = a == b;\n  assign lt = a < b;\n"
            "endmodule\n"
        ),
        tags=["comb", "compare"],
    ),
    Task(
        task_id="alu8",
        top_module="alu8",
        spec=(
            "Implement an 8-bit ALU. The 2-bit `op` selects the operation on inputs "
            "`a` and `b`: 0 -> a+b, 1 -> a-b, 2 -> bitwise AND, 3 -> bitwise OR. "
            "Result goes to `y` (8 bits, low bits for add/sub)."
        ),
        interface=[Port("a", "input", 8), Port("b", "input", 8), Port("op", "input", 2), Port("y", "output", 8)],
        reference_rtl=(
            "module alu8(input [7:0] a, input [7:0] b, input [1:0] op, output [7:0] y);\n"
            "  assign y = (op == 2'd0) ? a + b :\n"
            "             (op == 2'd1) ? a - b :\n"
            "             (op == 2'd2) ? (a & b) : (a | b);\n"
            "endmodule\n"
        ),
        tags=["comb", "alu"],
    ),
    Task(
        task_id="dec3to8",
        top_module="dec3to8",
        spec=(
            "Implement a 3-to-8 one-hot decoder. The 3-bit `sel` chooses which one "
            "of the 8 output bits `y` is high (all others low); bit number `sel` is set."
        ),
        interface=[Port("sel", "input", 3), Port("y", "output", 8)],
        reference_rtl=(
            "module dec3to8(input [2:0] sel, output [7:0] y);\n"
            "  assign y = 8'b1 << sel;\n"
            "endmodule\n"
        ),
        tags=["comb", "decoder"],
    ),
    Task(
        task_id="popcount8",
        top_module="popcount8",
        spec=(
            "Implement a population count for an 8-bit input `a`. Output `count` "
            "(4 bits) is the number of bits in `a` that are 1 (0 through 8)."
        ),
        interface=[Port("a", "input", 8), Port("count", "output", 4)],
        reference_rtl=(
            "module popcount8(input [7:0] a, output [3:0] count);\n"
            "  assign count = a[0]+a[1]+a[2]+a[3]+a[4]+a[5]+a[6]+a[7];\n"
            "endmodule\n"
        ),
        tags=["comb", "reduction"],
    ),
    Task(
        task_id="shl8",
        top_module="shl8",
        spec=(
            "Implement an 8-bit logical left shifter. Output `y` is input `a` "
            "shifted left by `amt` (3 bits) positions, with zeros shifted in."
        ),
        interface=[Port("a", "input", 8), Port("amt", "input", 3), Port("y", "output", 8)],
        reference_rtl=(
            "module shl8(input [7:0] a, input [2:0] amt, output [7:0] y);\n"
            "  assign y = a << amt;\n"
            "endmodule\n"
        ),
        tags=["comb", "shift"],
    ),
    Task(
        task_id="absdiff8",
        top_module="absdiff8",
        spec=(
            "Implement an 8-bit unsigned absolute difference. Output `y` is the "
            "absolute value of `a - b`, i.e. the larger minus the smaller."
        ),
        interface=[Port("a", "input", 8), Port("b", "input", 8), Port("y", "output", 8)],
        reference_rtl=(
            "module absdiff8(input [7:0] a, input [7:0] b, output [7:0] y);\n"
            "  assign y = (a > b) ? (a - b) : (b - a);\n"
            "endmodule\n"
        ),
        tags=["comb", "arith"],
    ),
    Task(
        task_id="bin2gray8",
        top_module="bin2gray8",
        spec=(
            "Implement an 8-bit binary-to-Gray-code converter. Output `gray` is the "
            "Gray code of binary input `bin` (gray = bin XOR (bin >> 1))."
        ),
        interface=[Port("bin", "input", 8), Port("gray", "output", 8)],
        reference_rtl=(
            "module bin2gray8(input [7:0] bin, output [7:0] gray);\n"
            "  assign gray = bin ^ (bin >> 1);\n"
            "endmodule\n"
        ),
        tags=["comb", "encoding"],
    ),
]

HELDOUT_TASKS: list[Task] = [
    Task(  # mux2 perturbed: wider + renamed ports
        task_id="ho_mux2_w16",
        top_module="sel_mux",
        spec=(
            "Implement a 16-bit 2-to-1 multiplexer. When `s` is 0, output `out` "
            "equals input `in0`; when `s` is 1, `out` equals input `in1`."
        ),
        interface=[Port("in0", "input", 16), Port("in1", "input", 16), Port("s", "input", 1), Port("out", "output", 16)],
        reference_rtl=(
            "module sel_mux(input [15:0] in0, input [15:0] in1, input s, output [15:0] out);\n"
            "  assign out = s ? in1 : in0;\n"
            "endmodule\n"
        ),
        held_out=True,
        tags=["comb", "mux"],
    ),
    Task(  # cmp8 perturbed: narrower + renamed
        task_id="ho_cmp4",
        top_module="magnitude4",
        spec=(
            "Implement a 4-bit unsigned comparator. Set `greater` when `x > y`, "
            "`equal` when `x == y`, and `less` when `x < y`."
        ),
        interface=[
            Port("x", "input", 4), Port("y", "input", 4),
            Port("greater", "output", 1), Port("equal", "output", 1), Port("less", "output", 1),
        ],
        reference_rtl=(
            "module magnitude4(input [3:0] x, input [3:0] y, output greater, output equal, output less);\n"
            "  assign greater = x > y;\n  assign equal = x == y;\n  assign less = x < y;\n"
            "endmodule\n"
        ),
        held_out=True,
        tags=["comb", "compare"],
    ),
    Task(  # popcount perturbed: wider
        task_id="ho_popcount16",
        top_module="ones16",
        spec=(
            "Implement a population count for a 16-bit input `d`. Output `ones` "
            "(5 bits) is the number of 1 bits in `d` (0 through 16)."
        ),
        interface=[Port("d", "input", 16), Port("ones", "output", 5)],
        reference_rtl=(
            "module ones16(input [15:0] d, output [4:0] ones);\n"
            "  assign ones = $countones(d);\n"
            "endmodule\n"
        ),
        held_out=True,
        tags=["comb", "reduction"],
    ),
    Task(  # min/max recombination: train has min2-like via absdiff; here max
        task_id="ho_max2",
        top_module="pick_max",
        spec=(
            "Implement an 8-bit unsigned maximum. Output `m` is whichever of inputs "
            "`p` and `q` is larger (or either if equal)."
        ),
        interface=[Port("p", "input", 8), Port("q", "input", 8), Port("m", "output", 8)],
        reference_rtl=(
            "module pick_max(input [7:0] p, input [7:0] q, output [7:0] m);\n"
            "  assign m = (p > q) ? p : q;\n"
            "endmodule\n"
        ),
        held_out=True,
        tags=["comb", "compare"],
    ),
    Task(  # decoder perturbed: narrower
        task_id="ho_dec2to4",
        top_module="onehot2",
        spec=(
            "Implement a 2-to-4 one-hot decoder. The 2-bit `code` chooses which one "
            "of the 4 output bits `oh` is high; bit number `code` is set, others low."
        ),
        interface=[Port("code", "input", 2), Port("oh", "output", 4)],
        reference_rtl=(
            "module onehot2(input [1:0] code, output [3:0] oh);\n"
            "  assign oh = 4'b1 << code;\n"
            "endmodule\n"
        ),
        held_out=True,
        tags=["comb", "decoder"],
    ),
    Task(  # inverse of bin2gray: structurally novel vs train
        task_id="ho_gray2bin8",
        top_module="gray2bin8",
        spec=(
            "Implement an 8-bit Gray-code-to-binary converter. Output `bin` is the "
            "binary value whose Gray code is the input `gray` (the inverse of a "
            "binary-to-Gray conversion)."
        ),
        interface=[Port("gray", "input", 8), Port("bin", "output", 8)],
        reference_rtl=(
            "module gray2bin8(input [7:0] gray, output [7:0] bin);\n"
            "  assign bin = gray ^ (gray >> 1) ^ (gray >> 2) ^ (gray >> 3) ^\n"
            "               (gray >> 4) ^ (gray >> 5) ^ (gray >> 6) ^ (gray >> 7);\n"
            "endmodule\n"
        ),
        held_out=True,
        tags=["comb", "encoding"],
    ),
]

TPU_REPEATED_MATMUL_TB = r"""
// auto-generated testbench for task __TASK_ID__
module tb;
  logic clk = 0;
  logic rst_n;
  logic ena;
  logic [7:0] ui_in;
  logic [7:0] uio_in;
  wire [7:0] uo_out__c, uo_out__r;
  wire [7:0] uio_out__c, uio_out__r;
  wire [7:0] uio_oe__c, uio_oe__r;

  __DUT__ dut_c (
      .ui_in(ui_in), .uo_out(uo_out__c), .uio_in(uio_in),
      .uio_out(uio_out__c), .uio_oe(uio_oe__c), .ena(ena),
      .clk(clk), .rst_n(rst_n)
  );
  __REF__ dut_r (
      .ui_in(ui_in), .uo_out(uo_out__r), .uio_in(uio_in),
      .uio_out(uio_out__r), .uio_oe(uio_oe__r), .ena(ena),
      .clk(clk), .rst_n(rst_n)
  );

  always #5 clk = ~clk;

  integer passed = 0;
  integer total = 0;
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
      for (i = 0; i < 4; i = i + 1) begin
        load_elem(0, i, a[i]);
      end
      for (i = 0; i < 4; i = i + 1) begin
        load_elem(1, i, b[i]);
      end
    end
  endtask

  task compare_outputs(input integer phase);
    begin
      repeat (3) @(posedge clk);
      for (i = 0; i < 4; i = i + 1) begin
        uio_in = ((i & 3) << 5) | (1 << 4);
        @(posedge clk);
        #1;
        total += 1;
        if (uo_out__c === uo_out__r) begin
          passed += 1;
        end else begin
          $display("MISMATCH scenario=%0d phase=%0d output=%0d candidate=%0d reference=%0d",
                   scenario, phase, i, $signed(uo_out__c), $signed(uo_out__r));
        end
        uio_in = 8'd0;
        @(posedge clk);
        #1;
      end
    end
  endtask

  initial begin
    unused = $urandom(__SEED__);
    reset_all();

    for (scenario = 0; scenario < __N_VECTORS__; scenario = scenario + 1) begin
      for (i = 0; i < 4; i = i + 1) begin
        a[i] = $urandom_range(0, 7);
        b[i] = $urandom_range(0, 7);
      end
      load_current_matrices();
      compare_outputs(0);

      for (i = 0; i < 4; i = i + 1) begin
        a[i] = $urandom_range(0, 7);
        b[i] = $urandom_range(0, 7);
      end
      load_current_matrices();
      compare_outputs(1);

      reset_all();
    end

    $display("RESULT %0d %0d", passed, total);
    $finish;
  end
endmodule
"""

TPU_REPEATED_MATMUL_REF = r"""
module tt_um_tpu (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);
    reg signed [7:0] a0, a1, a2, a3;
    reg signed [7:0] b0, b1, b2, b3;

    wire load_en = uio_in[0];
    wire load_sel_b = uio_in[1];
    wire [1:0] load_index = uio_in[3:2];
    wire output_en = uio_in[4];
    wire [1:0] output_sel = uio_in[6:5];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            a0 <= 8'sd0; a1 <= 8'sd0; a2 <= 8'sd0; a3 <= 8'sd0;
            b0 <= 8'sd0; b1 <= 8'sd0; b2 <= 8'sd0; b3 <= 8'sd0;
        end else if (load_en) begin
            if (!load_sel_b) begin
                case (load_index)
                    2'd0: a0 <= ui_in;
                    2'd1: a1 <= ui_in;
                    2'd2: a2 <= ui_in;
                    2'd3: a3 <= ui_in;
                endcase
            end else begin
                case (load_index)
                    2'd0: b0 <= ui_in;
                    2'd1: b1 <= ui_in;
                    2'd2: b2 <= ui_in;
                    2'd3: b3 <= ui_in;
                endcase
            end
        end
    end

    wire signed [15:0] c00 = a0 * b0 + a1 * b2;
    wire signed [15:0] c01 = a0 * b1 + a1 * b3;
    wire signed [15:0] c10 = a2 * b0 + a3 * b2;
    wire signed [15:0] c11 = a2 * b1 + a3 * b3;

    reg [7:0] selected;
    always @(*) begin
        case (output_sel)
            2'd0: selected = c00[7:0];
            2'd1: selected = c01[7:0];
            2'd2: selected = c10[7:0];
            2'd3: selected = c11[7:0];
        endcase
    end

    assign uo_out = output_en ? selected : 8'd0;
    assign uio_out = {output_en, 7'b0};
    assign uio_oe = 8'b1000_0000;

    wire _unused = &{ena, uio_in[7]};
endmodule
"""

TPU_SIGNED_OUTPUT_TB = r"""
// auto-generated testbench for task __TASK_ID__
module tb;
  logic clk = 0;
  logic rst_n;
  logic ena;
  logic [7:0] ui_in;
  logic [7:0] uio_in;
  wire [7:0] uo_out__c, uo_out__r;
  wire [7:0] uio_out__c, uio_out__r;
  wire [7:0] uio_oe__c, uio_oe__r;

  __DUT__ dut_c (
      .ui_in(ui_in), .uo_out(uo_out__c), .uio_in(uio_in),
      .uio_out(uio_out__c), .uio_oe(uio_oe__c), .ena(ena),
      .clk(clk), .rst_n(rst_n)
  );
  __REF__ dut_r (
      .ui_in(ui_in), .uo_out(uo_out__r), .uio_in(uio_in),
      .uio_out(uio_out__r), .uio_oe(uio_oe__r), .ena(ena),
      .clk(clk), .rst_n(rst_n)
  );

  always #5 clk = ~clk;

  integer passed = 0;
  integer total = 0;
  integer scenario;
  integer i;
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
      for (i = 0; i < 4; i = i + 1) begin
        load_elem(0, i, a[i]);
      end
      for (i = 0; i < 4; i = i + 1) begin
        load_elem(1, i, b[i]);
      end
    end
  endtask

  task compare_all_outputs;
    begin
      repeat (3) @(posedge clk);
      for (i = 0; i < 4; i = i + 1) begin
        uio_in = ((i & 3) << 5) | (1 << 4);
        @(posedge clk);
        #1;
        total += 1;
        if (uo_out__c === uo_out__r) begin
          passed += 1;
        end else begin
          $display("MISMATCH scenario=%0d output=%0d candidate=%0d reference=%0d",
                   scenario, i, $signed(uo_out__c), $signed(uo_out__r));
        end
        uio_in = 8'd0;
        @(posedge clk);
        #1;
      end
    end
  endtask

  task set_scenario(input integer id);
    begin
      scenario = id;
      case (id)
        0: begin
          a[0] = 8'sd1;  a[1] = 8'sd2;  a[2] = 8'sd3;  a[3] = 8'sd4;
          b[0] = 8'sd5;  b[1] = 8'sd6;  b[2] = 8'sd7;  b[3] = 8'sd8;
        end
        1: begin
          a[0] = -8'sd3; a[1] = 8'sd4;  a[2] = 8'sd5;  a[3] = -8'sd6;
          b[0] = 8'sd7;  b[1] = -8'sd8; b[2] = 8'sd9;  b[3] = 8'sd10;
        end
        2: begin
          a[0] = -8'sd8; a[1] = -8'sd7; a[2] = 8'sd6;  a[3] = 8'sd5;
          b[0] = 8'sd4;  b[1] = -8'sd3; b[2] = -8'sd2; b[3] = 8'sd1;
        end
        default: begin
          a[0] = 8'sd12; a[1] = -8'sd11; a[2] = -8'sd10; a[3] = 8'sd9;
          b[0] = -8'sd6; b[1] = 8'sd5;   b[2] = 8'sd4;    b[3] = -8'sd3;
        end
      endcase
    end
  endtask

  initial begin
    reset_all();

    for (scenario = 0; scenario < 4; scenario = scenario + 1) begin
      set_scenario(scenario);
      load_current_matrices();
      compare_all_outputs();
      reset_all();
    end

    $display("RESULT %0d %0d", passed, total);
    $finish;
  end
endmodule
"""

GRADIENT_TASKS: list[Task] = [
    Task(
        task_id="vg_tpu_repeated_matmul2x2",
        top_module="tt_um_tpu",
        spec=(
            "Implement a Tiny Tapeout-style 2x2 matrix multiply accelerator. "
            "`ui_in` carries one signed 8-bit matrix element. When `uio_in[0]` "
            "is high on a clock edge, store `ui_in` into matrix A if `uio_in[1]` "
            "is 0 or matrix B if `uio_in[1]` is 1; `uio_in[3:2]` selects the "
            "row-major element index. When `uio_in[4]` is high, output the "
            "selected low 8 bits of A*B on `uo_out`, with `uio_in[6:5]` selecting "
            "C00, C01, C10, or C11. Repeated matrix multiplies must be independent: "
            "loading a new A and B must not accumulate stale partial sums from a "
            "previous multiplication."
        ),
        interface=[
            Port("ui_in", "input", 8),
            Port("uo_out", "output", 8),
            Port("uio_in", "input", 8),
            Port("uio_out", "output", 8),
            Port("uio_oe", "output", 8),
            Port("ena", "input", 1),
            Port("clk", "input", 1),
            Port("rst_n", "input", 1),
        ],
        reference_rtl=TPU_REPEATED_MATMUL_REF,
        n_vectors=16,
        seed=6,
        clocked=True,
        testbench_template=TPU_REPEATED_MATMUL_TB,
        allow_extra_modules=True,
        tags=["clocked", "verified-gradient", "tpu", "systolic-array", "matmul"],
    ),
    Task(
        task_id="vg_tpu_signed_outputs2x2",
        top_module="tt_um_tpu",
        spec=(
            "Implement a Tiny Tapeout-style 2x2 signed matrix multiply accelerator. "
            "`ui_in` carries one signed 8-bit matrix element. When `uio_in[0]` is "
            "high on a clock edge, store `ui_in` into matrix A if `uio_in[1]` is "
            "0 or matrix B if `uio_in[1]` is 1; `uio_in[3:2]` selects the row-major "
            "element index. When `uio_in[4]` is high, output the selected low 8 bits "
            "of A*B on `uo_out`, with `uio_in[6:5]` selecting C00, C01, C10, or C11. "
            "The design must treat loaded matrix elements as signed values and each "
            "output select must return the corresponding matrix product element."
        ),
        interface=[
            Port("ui_in", "input", 8),
            Port("uo_out", "output", 8),
            Port("uio_in", "input", 8),
            Port("uio_out", "output", 8),
            Port("uio_oe", "output", 8),
            Port("ena", "input", 1),
            Port("clk", "input", 1),
            Port("rst_n", "input", 1),
        ],
        reference_rtl=TPU_REPEATED_MATMUL_REF,
        n_vectors=4,
        seed=8,
        clocked=True,
        testbench_template=TPU_SIGNED_OUTPUT_TB,
        allow_extra_modules=True,
        tags=["clocked", "verified-gradient", "tpu", "systolic-array", "signed", "matmul"],
    ),
]

# --- Hard task: real EDA design with genuine headroom -----------------------
# The ho_* heldout tasks are saturated (frontier models pass single-shot), so
# they show no uplift. This 2-lane round-robin ready/valid FIFO arbiter is a
# real EDA design (sequential + arbitration + no-latch constraint) where weak
# models actually fail. Golden reference is the verified stream_arb_fifo from
# cologic-verilog/.../stream_arb_fifo_golden.sv. Clocked equivalence grading:
# candidate and golden get identical random stimulus, outputs compared per cycle.

STREAM_ARB_FIFO_REF = r"""module stream_arb_fifo #(
    parameter int width_p = 8,
    parameter int depth_p = 8,
    parameter int count_width_lp = $clog2(depth_p + 1),
    parameter int addr_width_lp = $clog2(depth_p)
) (
    input  logic                    clk_i,
    input  logic                    reset_i,

    input  logic [width_p-1:0]      data0_i,
    input  logic                    valid0_i,
    output logic                    ready0_o,

    input  logic [width_p-1:0]      data1_i,
    input  logic                    valid1_i,
    output logic                    ready1_o,

    output logic                    valid_o,
    output logic [width_p-1:0]      data_o,
    input  logic                    yumi_i,

    output logic [count_width_lp-1:0] count_o,
    output logic                    selected_lane_o
);
    localparam logic [count_width_lp-1:0] depth_count_lp = count_width_lp'(depth_p);
    localparam logic [addr_width_lp-1:0] last_addr_lp = addr_width_lp'(depth_p - 1);

    logic [width_p-1:0] mem [0:depth_p-1];
    logic [addr_width_lp-1:0] wr_ptr_r;
    logic [addr_width_lp-1:0] rd_ptr_r;
    logic [count_width_lp-1:0] count_r;
    logic rr_next_r;
    logic can_accept;
    logic push0;
    logic push1;
    logic push_fire;
    logic pop_fire;

    assign count_o = count_r;
    assign valid_o = (count_r != '0);
    assign data_o = mem[rd_ptr_r];
    assign pop_fire = yumi_i && valid_o;
    assign can_accept = (count_r < depth_count_lp) || pop_fire;

    always_comb begin
        ready0_o = 1'b0;
        ready1_o = 1'b0;
        selected_lane_o = 1'b0;
        if (can_accept) begin
            if (valid0_i && valid1_i) begin
                ready0_o = !rr_next_r;
                ready1_o = rr_next_r;
                selected_lane_o = rr_next_r;
            end else if (valid0_i) begin
                ready0_o = 1'b1;
                selected_lane_o = 1'b0;
            end else if (valid1_i) begin
                ready1_o = 1'b1;
                selected_lane_o = 1'b1;
            end
        end
    end

    assign push0 = ready0_o && valid0_i;
    assign push1 = ready1_o && valid1_i;
    assign push_fire = push0 || push1;

    function automatic logic [addr_width_lp-1:0] incr_ptr(
        input logic [addr_width_lp-1:0] ptr
    );
        if (ptr == last_addr_lp) begin
            incr_ptr = '0;
        end else begin
            incr_ptr = ptr + addr_width_lp'(1);
        end
    endfunction

    always_ff @(posedge clk_i) begin
        if (reset_i) begin
            wr_ptr_r <= '0;
            rd_ptr_r <= '0;
            count_r <= '0;
            rr_next_r <= 1'b0;
        end else begin
            if (push_fire) begin
                mem[wr_ptr_r] <= push0 ? data0_i : data1_i;
                wr_ptr_r <= incr_ptr(wr_ptr_r);
                rr_next_r <= push0;
            end

            if (pop_fire) begin
                rd_ptr_r <= incr_ptr(rd_ptr_r);
            end

            unique case ({push_fire, pop_fire})
                2'b10: count_r <= count_r + count_width_lp'(1);
                2'b01: count_r <= count_r - count_width_lp'(1);
                default: count_r <= count_r;
            endcase
        end
    end
endmodule
"""

# Clocked equivalence TB: drive candidate and golden with identical random
# handshake stimulus, compare all observable outputs every cycle with `===`
# (an X on the candidate counts as a mismatch -> catches combinational latches).
STREAM_ARB_FIFO_TB = r"""// auto-generated testbench for task __TASK_ID__
module tb;
  localparam int width_p = 8;
  localparam int depth_p = 8;
  localparam int cw = $clog2(depth_p + 1);

  logic clk = 0;
  logic reset_i;
  logic [width_p-1:0] data0_i, data1_i;
  logic valid0_i, valid1_i, yumi_i;

  wire ready0_o__c, ready1_o__c, valid_o__c, selected_lane_o__c;
  wire ready0_o__r, ready1_o__r, valid_o__r, selected_lane_o__r;
  wire [width_p-1:0] data_o__c, data_o__r;
  wire [cw-1:0] count_o__c, count_o__r;

  __DUT__ dut_c (
      .clk_i(clk), .reset_i(reset_i),
      .data0_i(data0_i), .valid0_i(valid0_i), .ready0_o(ready0_o__c),
      .data1_i(data1_i), .valid1_i(valid1_i), .ready1_o(ready1_o__c),
      .valid_o(valid_o__c), .data_o(data_o__c), .yumi_i(yumi_i),
      .count_o(count_o__c), .selected_lane_o(selected_lane_o__c)
  );
  __REF__ dut_r (
      .clk_i(clk), .reset_i(reset_i),
      .data0_i(data0_i), .valid0_i(valid0_i), .ready0_o(ready0_o__r),
      .data1_i(data1_i), .valid1_i(valid1_i), .ready1_o(ready1_o__r),
      .valid_o(valid_o__r), .data_o(data_o__r), .yumi_i(yumi_i),
      .count_o(count_o__r), .selected_lane_o(selected_lane_o__r)
  );

  always #5 clk = ~clk;

  integer passed = 0;
  integer total = 0;
  integer i;

  task automatic check_outputs;
    begin
      total += 1; if (ready0_o__c        === ready0_o__r)        passed += 1;
      total += 1; if (ready1_o__c        === ready1_o__r)        passed += 1;
      total += 1; if (valid_o__c         === valid_o__r)         passed += 1;
      total += 1; if (count_o__c         === count_o__r)         passed += 1;
      total += 1; if (selected_lane_o__c === selected_lane_o__r) passed += 1;
      // data_o is only architecturally defined when the reference FIFO is non-empty.
      total += 1; if (!valid_o__r || (data_o__c === data_o__r))  passed += 1;
    end
  endtask

  initial begin
    void'($urandom(__SEED__));
    reset_i = 1'b1; valid0_i = 0; valid1_i = 0; yumi_i = 0; data0_i = 0; data1_i = 0;
    repeat (3) @(posedge clk);
    #1; reset_i = 1'b0;

    for (i = 0; i < __N_VECTORS__; i = i + 1) begin
      data0_i  = $urandom;
      data1_i  = $urandom;
      valid0_i = $urandom & 1;
      valid1_i = $urandom & 1;
      yumi_i   = $urandom & 1;
      #1;                 // let combinational outputs settle on the new inputs
      check_outputs();
      @(posedge clk);
      #1;
    end

    $display("RESULT %0d %0d", passed, total);
    $finish;
  end
endmodule
"""

HARD_TASKS: list[Task] = [
    Task(
        task_id="stream_arb_fifo",
        top_module="stream_arb_fifo",
        spec=(
            "Implement a synthesizable two-lane, single-output ready/valid FIFO "
            "arbiter named `stream_arb_fifo`, width 8, depth 8, with synchronous "
            "active-high reset (`reset_i`). Two input lanes (data0_i/valid0_i/"
            "ready0_o and data1_i/valid1_i/ready1_o) feed one FIFO drained through "
            "valid_o/data_o/yumi_i. Requirements: assert ready on a lane only when "
            "the FIFO can accept (not full, OR a pop fires this cycle so a slot frees); "
            "accept either lone valid lane; when BOTH lanes are valid, round-robin "
            "arbitrate (alternate which lane wins on successive accepts, starting with "
            "lane 0 after reset); push the selected lane's data and advance the write "
            "pointer; pop on `yumi_i && valid_o`; allow a simultaneous full pop+push in "
            "one cycle; maintain `count_o` and assert `valid_o` whenever the FIFO is "
            "non-empty; drive `selected_lane_o` to the lane being accepted (0 when idle); "
            "and avoid all combinational latches (every output assigned on every path)."
        ),
        interface=[
            Port("clk_i", "input", 1),
            Port("reset_i", "input", 1),
            Port("data0_i", "input", 8),
            Port("valid0_i", "input", 1),
            Port("ready0_o", "output", 1),
            Port("data1_i", "input", 8),
            Port("valid1_i", "input", 1),
            Port("ready1_o", "output", 1),
            Port("valid_o", "output", 1),
            Port("data_o", "output", 8),
            Port("yumi_i", "input", 1),
            Port("count_o", "output", 4),
            Port("selected_lane_o", "output", 1),
        ],
        reference_rtl=STREAM_ARB_FIFO_REF,
        n_vectors=96,
        seed=3,
        clocked=True,
        testbench_template=STREAM_ARB_FIFO_TB,
        held_out=True,
        tags=["clocked", "hard", "eda", "fifo", "arbiter", "ready-valid", "round-robin"],
    ),
]

SEED_TASKS: list[Task] = TRAIN_TASKS + HELDOUT_TASKS + GRADIENT_TASKS + HARD_TASKS
BY_ID = {t.task_id: t for t in SEED_TASKS}
