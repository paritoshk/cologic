"""The verifiable-reward core of Cologic.

Takes generated Verilog + a self-checking testbench, compiles and simulates it with
Icarus Verilog, and returns a scalar reward plus the raw signals the RL loop trains on:

    compiles    -> hard gate (iverilog exit 0)
    sim_passed  -> hard gate (testbench printed PASS, not FAIL)
    toggles     -> dynamic-power proxy from the VCD (lower better)
    sim_time    -> latency/compute proxy from the VCD (lower better)
    timing_slack-> None: needs synthesis (yosys + OpenSTA), not wired yet

Reward contract: 0.0 unless it both compiles AND passes. With a `baseline` it's a
relative score (1.0 == baseline, >1 better, <1 worse); without one it's just 1.0 on
pass and the caller normalizes using the raw metrics.
"""
import glob
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, asdict

from .vcd import parse_vcd


@dataclass
class Result:
    compiles: bool
    sim_passed: bool
    toggles: "int | None"
    sim_time: "int | None"
    timing_slack: None
    reward: float
    log: str

    def as_dict(self):
        return asdict(self)


def _score(toggles, sim_time, baseline, w_power, w_compute):
    if not baseline:
        return 1.0
    bp = baseline.get("toggles")
    bt = baseline.get("sim_time")
    p = (bp / max(toggles, 1)) if bp else 1.0
    c = (bt / max(sim_time, 1)) if bt else 1.0
    return round(w_power * p + w_compute * c, 4)


def evaluate(sources, top="tb", baseline=None, w_power=0.5, w_compute=0.5, timeout=60):
    """Compile + simulate `sources`, return a Result. `sources` is a list of .v paths."""
    sources = [os.path.abspath(s) for s in sources]
    work = tempfile.mkdtemp(prefix="cologic_")
    try:
        vvp_path = os.path.join(work, "sim.vvp")
        comp = subprocess.run(
            ["iverilog", "-g2012", "-s", top, "-o", vvp_path, *sources],
            capture_output=True, text=True, timeout=timeout,
        )
        if comp.returncode != 0:
            return Result(False, False, None, None, None, 0.0,
                          (comp.stderr or comp.stdout).strip())

        run = subprocess.run(
            ["vvp", vvp_path], cwd=work,
            capture_output=True, text=True, timeout=timeout,
        )
        out = run.stdout
        passed = ("PASS" in out) and ("FAIL" not in out) and run.returncode == 0

        toggles = sim_time = None
        vcd_path = os.path.join(work, "dump.vcd")
        if os.path.exists(vcd_path):
            toggles, sim_time = parse_vcd(vcd_path)

        reward = _score(toggles, sim_time, baseline, w_power, w_compute) if passed else 0.0
        return Result(True, passed, toggles, sim_time, None, reward, out.strip())
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _expand(args):
    files = []
    for a in args:
        files.extend(glob.glob(a) if any(c in a for c in "*?[") else [a])
    return files
