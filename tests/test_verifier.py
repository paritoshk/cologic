"""End-to-end checks that the Verilator-grounded reward behaves: correct designs
score 1.0, broken-but-compiling designs score the compile floor, garbage scores 0.
"""

import shutil

import pytest

from rl_hdl import grade
from rl_hdl.schema import Port, Task
from rl_hdl.tasks import BY_ID, SEED_TASKS
from rl_hdl.verifier import COMPILE_ERROR_REWARD, COMPILE_FLOOR

pytestmark = pytest.mark.skipif(shutil.which("verilator") is None, reason="verilator not installed")

MUX = BY_ID["mux2"]


@pytest.mark.parametrize("task", SEED_TASKS, ids=[t.task_id for t in SEED_TASKS])
def test_golden_reference_self_grades_full(task):
    """Every task's own reference, fed as the completion, must score 1.0.

    This is the oracle's smoke test: a malformed reference (bad width, typo,
    wrong logic) would surface here before it ever poisons training.
    """
    r = grade(task.reference_rtl, task)
    assert r.info["stage"] == "graded", f"{task.task_id}: {r.info.get('log', '')[:400]}"
    assert r.reward == pytest.approx(1.0), f"{task.task_id}: {r.info}"


def test_correct_design_scores_full():
    good = """```verilog
module mux2(input [7:0] a, input [7:0] b, input sel, output [7:0] y);
  assign y = sel ? b : a;
endmodule
```"""
    r = grade(good, MUX)
    assert r.info["stage"] == "graded"
    assert r.reward == pytest.approx(1.0)
    assert r.info["passed"] == r.info["total"] > 0


def test_wrong_but_compiling_scores_floor():
    # Always outputs a, ignoring sel: compiles, fails ~half the vectors.
    wrong = """module mux2(input [7:0] a, input [7:0] b, input sel, output [7:0] y);
  assign y = a;
endmodule"""
    r = grade(wrong, MUX)
    assert r.info["stage"] == "graded"
    assert COMPILE_FLOOR <= r.reward < 1.0


def test_renamed_module_still_binds():
    # Model used a different module name; grader should rename it to the top.
    renamed = """module my_mux(input [7:0] a, input [7:0] b, input sel, output [7:0] y);
  assign y = sel ? b : a;
endmodule"""
    r = grade(renamed, MUX)
    assert r.reward == pytest.approx(1.0)


def test_syntax_error_scores_compile_error():
    broken = """module mux2(input [7:0] a, input [7:0] b, input sel, output [7:0] y);
  assign y = sel ? b : a   // missing semicolon
endmodule"""
    r = grade(broken, MUX)
    assert r.info["stage"] == "compile_error"
    assert r.reward == COMPILE_ERROR_REWARD


def test_port_named_like_tb_internal_var():
    # A DUT port named `i` must not collide with the testbench loop counter.
    task = Task(
        task_id="passthru_i",
        spec="pass input i to output o",
        top_module="passthru_i",
        interface=[Port("i", "input", 4), Port("o", "output", 4)],
        reference_rtl="module passthru_i(input [3:0] i, output [3:0] o); assign o = i; endmodule",
    )
    good = "module passthru_i(input [3:0] i, output [3:0] o); assign o = i; endmodule"
    r = grade(good, task)
    assert r.info["stage"] == "graded" and r.reward == pytest.approx(1.0)


def test_no_module_scores_zero():
    r = grade("Sure! Here is how a multiplexer works conceptually...", MUX)
    assert r.info["stage"] == "no_module"
    assert r.reward == 0.0
