"""Runnable checks for the reward harness. Sim tests skip if iverilog is absent."""
import glob
import os
import shutil

import pytest

from cologic import evaluate, parse_vcd

EX = os.path.join(os.path.dirname(__file__), "..", "examples", "systolic_array")
SRC = sorted(glob.glob(os.path.join(EX, "*.v")))
needs_iverilog = pytest.mark.skipif(shutil.which("iverilog") is None, reason="no iverilog")


def test_vcd_parse(tmp_path):
    vcd = tmp_path / "d.vcd"
    vcd.write_text("$enddefinitions $end\n#0\n0!\nb1010 !\n#10\n1!\n")
    toggles, end_time = parse_vcd(str(vcd))
    assert toggles == 3 and end_time == 10


@needs_iverilog
def test_good_design_passes():
    r = evaluate(SRC, top="tb")
    assert r.compiles and r.sim_passed
    assert r.reward == 1.0
    assert r.toggles and r.sim_time


@needs_iverilog
def test_compile_failure_is_zero_reward():
    r = evaluate([SRC[0]], top="tb")  # only the DUT, no testbench -> top 'tb' missing
    assert not r.sim_passed and r.reward == 0.0


@needs_iverilog
def test_baseline_makes_reward_relative():
    base = evaluate(SRC, top="tb")
    worse = {"toggles": base.toggles * 2, "sim_time": base.sim_time * 2}
    r = evaluate(SRC, top="tb", baseline=worse)
    assert r.reward == pytest.approx(2.0)  # half the cost of baseline -> 2x score
