# Cologic — self-learning chip-design agent

RL for teaching hardware design languages. An agent generates RTL, an isolated sandbox
compiles + simulates it, and a **verifiable reward** scores the result. Those rewards
drive an RLVR loop, so the model gets measurably better each epoch.

This repo currently contains the **verifiable-reward core** — the part everything else
(Modal sandboxes, Fireworks fine-tuning, the Cologic visualizer) wraps around.

```
cologic/                 the harness
  reward.py              evaluate() — compile + sim + score  ← the core
  vcd.py                 toggle/latency proxies from the VCD
  __main__.py            CLI
examples/systolic_array/ a real, golden-checked RTL task
tests/                   runnable checks
```

## Setup

```bash
brew install icarus-verilog          # or: apt install iverilog
pip install -e .                     # core is stdlib-only; iverilog is the real dep
```

## Run it

```bash
python -m cologic "examples/systolic_array/*.v" --top tb
```

```json
{ "compiles": true, "sim_passed": true, "toggles": 145,
  "sim_time": 156000, "reward": 1.0, ... }
```

Or from Python — this is the function the RL loop calls per rollout:

```python
from cologic import evaluate
r = evaluate(["gen/design.v", "gen/tb.v"], top="tb")
r.reward         # 0.0 unless it compiles AND the testbench prints PASS
```

## The reward

| Signal         | Meaning                          | Source              |
|----------------|----------------------------------|---------------------|
| `compiles`     | hard gate                        | iverilog exit 0     |
| `sim_passed`   | hard gate (testbench prints PASS)| vvp stdout          |
| `toggles`      | dynamic-power proxy (lower=better)| VCD value-changes  |
| `sim_time`     | latency/compute proxy (lower=better)| VCD last timestamp |
| `timing_slack` | **not wired** — needs synthesis  | (yosys + OpenSTA)   |

`reward` is `0.0` unless it both compiles and passes. Pass a `--baseline` JSON of
`{toggles, sim_time}` to get a **relative** reward (1.0 == baseline, >1 better) — that's
the signal that rewards a clock-gated or fewer-cycle variant over the previous best.

**Writing a task:** give the harness a DUT plus a self-checking testbench that prints
`PASS` on success and `FAIL` (or a mismatch) otherwise. See `examples/systolic_array/`.

## Test

```bash
pytest -q          # sim tests auto-skip if iverilog isn't installed
```

## Not built yet (handoff)

- **Modal sandbox** — run `evaluate()` in a spawnable sandbox per rollout (`sandbox.py`).
- **Fireworks loop** — serve the model, feed `reward` back as the RLVR signal.
- **Timing closure** — synth with yosys + OpenSTA to get a real `timing_slack` gate.
