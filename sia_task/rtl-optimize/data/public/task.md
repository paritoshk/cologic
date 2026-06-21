# Task: optimize Verilog designs for gate count, provably equivalent

You are improving a **target agent** (an automated RTL optimizer). Each generation,
the target agent is run as:

    python target_agent.py --dataset_dir <data/public> --working_dir <gen_dir>

and must, for every design listed in `--dataset_dir/manifest.json`, produce a
**smaller but exactly equivalent** Verilog module and write it to
`<working_dir>/submission/<design_id>.v`.

## What the target agent must do
- Read `manifest.json` (a list of `design_ids`). Each id resolves to a correct
  baseline module via `cologic.designs.BY_ID[id]` (gives `.reference_rtl`,
  `.top_module`, `.interface`).
- Rewrite each baseline to use **fewer gates** while keeping the **module name,
  port names, directions, and widths identical**.
- Write one optimized module per design to `submission/<design_id>.v`.
- It may sample candidates from the policy model (OpenAI-compatible client; model +
  base URL + key come from the environment), and it **should self-check** each
  candidate with the grader before submitting (see below).

## How outputs are scored (you cannot change this)
`evaluate.py` computes the reward with the **immutable grader** —
`cologic.grader.grade` = Verilator equivalence + Yosys gate count. There is **no
LLM judge** in the reward. A submission only earns credit if the grader confirms
it is exactly equivalent to the baseline; the score then rises with the gate-count
reduction. The target agent may import `cologic.grader.grade` to rank its own
candidates, but the official score is recomputed independently by `evaluate.py`.

## Where the real headroom is
Yosys's default synthesis already minimizes boolean logic, so cosmetic rewrites
win nothing. The wins that survive synthesis are **arithmetic-structural**:
- **Share arithmetic operators** under mutually-exclusive selects (e.g. compute one
  of two products with a single multiplier and muxed operands instead of two).
- Remove **redundant / duplicated arithmetic**.
- Strength-reduce constant multiplies/divides to shifts and adds.

## Hard rules
- Keep each module's name and interface exactly as the baseline.
- One module per `submission/<design_id>.v`, in a ```verilog code block or raw.
- Never try to influence `evaluate.py` or the grader — equivalence is checked by
  real silicon tooling and cannot be faked.
