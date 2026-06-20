"""Seed task library (combinational v1). Each task carries a golden reference
used as the grading oracle (see verifier.grade).

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

from rl_hdl.schema import Port, Task

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

SEED_TASKS: list[Task] = TRAIN_TASKS + HELDOUT_TASKS
BY_ID = {t.task_id: t for t in SEED_TASKS}
