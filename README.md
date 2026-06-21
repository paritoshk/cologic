# rl-hdl

An **RL-with-verifiable-rewards (RLVR) environment** that teaches an LLM to
generate correct hardware (Verilog/RTL) from a spec. The reward comes from
**real silicon tooling — the Verilator simulator — not an LLM judge**. Hardware
computes the right function or it doesn't, so the grade physically cannot be faked.

See [docs/BRIEF.md](docs/BRIEF.md) for the full project brief, scope, and the
locked design decisions.

## How grading works

The reward seam both the verifier (CPU) and trainer (GPU) build against:

```python
grade(completion: str, task: Task) -> GradeResult(reward: float, info: dict)
```

Each `Task` carries a natural-language spec, an interface, and a **golden
reference** Verilog module. `grade()`:

1. Extracts the candidate module from the model's (often messy) output.
2. Builds a SystemVerilog testbench that instantiates the candidate **and** the
   golden reference, drives the same random input vectors into both, and counts
   matching output comparisons.
3. Compiles everything with `verilator --binary --timing` and runs it.

Reward is correctness-dominant and **dense** (no bare pass/fail):

| Outcome | Reward |
|---|---|
| No extractable module | `0.00` |
| Extracted, won't compile | `0.05` |
| Compiles but sim errors | `0.05` |
| Compiles + runs | `0.10 + 0.90 · (matching comparisons / total)` |

Comparing against a golden reference (rather than hand-authored expected values)
makes the reward dense for free and makes held-out reward-hacking checks trivial:
just reseed the random vectors.

## Tasks

`rl_hdl/tasks.py` ships training tasks, held-out tasks, and converted
verified-gradient tasks:

- **`TRAIN_TASKS`**: mux2, mux4, add4, cmp8, alu8, dec3to8, popcount8, shl8,
  absdiff8, bin2gray8.
- **`HELDOUT_TASKS`**: perturbed variants — widened/narrowed, renamed ports
  and modules, recombined functions, and an inverse (gray→bin). These give
  the **headline** metric: warm-start models may have seen public benchmarks, so
  the gain is measured on structurally novel tasks.
- **`GRADIENT_TASKS`**: clocked TPU-like matrix-multiply tasks distilled
  from real verified gradients in `YashKarthik/tpu`. One checks that repeated
  matrix multiplies do not reuse stale accumulator state; the other checks signed
  matrix elements and output-select control.

The repo also includes a documented seed mining corpus in
`data/verified_gradients.jsonl`, with reproducible provenance for real-repo RTL
gradients and links from mined gradients to the native `rl-hdl` tasks converted
from them.

Every task's golden reference is smoke-tested to self-grade to `1.0`, which
catches a malformed reference before it can poison training.

## Layout

```
rl_hdl/
  schema.py     # Task + GradeResult (the locked seam)
  extract.py    # robust Verilog module extraction from LLM output
  verifier.py   # grade() — Verilator-grounded dense reward
  tasks.py      # TRAIN_TASKS + HELDOUT_TASKS (+ golden references)
tests/
  test_verifier.py
docs/
  BRIEF.md      # full project brief
```

## Setup

Requires [Verilator](https://verilator.org) on `PATH` (`brew install verilator`).

```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest -q
```
