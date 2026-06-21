"""Optimization task library (§9 floor).

An optimization task reuses the v1 `Task` schema, but its `reference_rtl` plays a
new role: it is the *correct-but-unoptimized baseline to beat*, not a spec oracle
for generation. The grader treats it as both the equivalence oracle AND the area
baseline. `tags` carries headroom metadata so task curation can be audited.

`mul8` is the seed floor design: a naive unrolled shift-add 8x8 multiplier. It is
correct but verbose, and carries real structural headroom. Alongside it we keep
two hand-written rewrites used to prove the equivalence gate BEFORE any model is
involved:

  MUL8_GOOD   - a behavioral `a*b`; equivalent, lets the synthesizer pick the
                best multiplier (the win we want the optimizer to discover).
  MUL8_BROKEN - the same shift-add structure with one partial product dropped;
                subtly wrong, so the gate must reject it on some input vectors.
"""

from __future__ import annotations

from rl_hdl.schema import Port, Task

# Naive baseline: each partial product spelled out, then summed. Correct, bloated.
MUL8_BASELINE = """module mul8(input [7:0] a, input [7:0] b, output [15:0] p);
  wire [15:0] pp0 = b[0] ? ({8'b0, a} << 0) : 16'b0;
  wire [15:0] pp1 = b[1] ? ({8'b0, a} << 1) : 16'b0;
  wire [15:0] pp2 = b[2] ? ({8'b0, a} << 2) : 16'b0;
  wire [15:0] pp3 = b[3] ? ({8'b0, a} << 3) : 16'b0;
  wire [15:0] pp4 = b[4] ? ({8'b0, a} << 4) : 16'b0;
  wire [15:0] pp5 = b[5] ? ({8'b0, a} << 5) : 16'b0;
  wire [15:0] pp6 = b[6] ? ({8'b0, a} << 6) : 16'b0;
  wire [15:0] pp7 = b[7] ? ({8'b0, a} << 7) : 16'b0;
  assign p = pp0 + pp1 + pp2 + pp3 + pp4 + pp5 + pp6 + pp7;
endmodule
"""

# Equivalent rewrite — the optimization the policy should converge on.
MUL8_GOOD = """module mul8(input [7:0] a, input [7:0] b, output [15:0] p);
  assign p = a * b;
endmodule
"""

# Subtly broken: pp3 is dropped from the sum. Wrong whenever b[3] is set.
MUL8_BROKEN = """module mul8(input [7:0] a, input [7:0] b, output [15:0] p);
  wire [15:0] pp0 = b[0] ? ({8'b0, a} << 0) : 16'b0;
  wire [15:0] pp1 = b[1] ? ({8'b0, a} << 1) : 16'b0;
  wire [15:0] pp2 = b[2] ? ({8'b0, a} << 2) : 16'b0;
  wire [15:0] pp4 = b[4] ? ({8'b0, a} << 4) : 16'b0;
  wire [15:0] pp5 = b[5] ? ({8'b0, a} << 5) : 16'b0;
  wire [15:0] pp6 = b[6] ? ({8'b0, a} << 6) : 16'b0;
  wire [15:0] pp7 = b[7] ? ({8'b0, a} << 7) : 16'b0;
  assign p = pp0 + pp1 + pp2 + pp4 + pp5 + pp6 + pp7;
endmodule
"""

mul8 = Task(
    task_id="opt_mul8",
    top_module="mul8",
    spec="Optimize this 8x8 unsigned multiplier for gate count while preserving its function.",
    interface=[Port("a", "input", 8), Port("b", "input", 8), Port("p", "output", 16)],
    reference_rtl=MUL8_BASELINE,
    n_vectors=256,  # dense enough that a dropped partial product is reliably caught
    tags=["comb", "arith", "headroom:resource-share"],
)

OPT_TASKS: list[Task] = [mul8]
BY_ID = {t.task_id: t for t in OPT_TASKS}
