# Fireworks RFT Workflow

Date: 2026-06-21 UTC

This repo's RFT path trains from the same reward seam used by local and Modal grading:

```python
grade(completion: str, task: Task) -> GradeResult
```

## Launch

The launcher assembles `fireworks_rft/`, copies `cologic/`, writes `dataset.jsonl`,
smoke-tests the evaluator with golden RTL, then calls Fireworks Eval Protocol.

```sh
modal run scripts/modal_fireworks_rft.py::launch --dry-run --force \
  --base-model accounts/fireworks/models/qwen3-0p6b \
  --account sorenmadsen \
  --output-model cologic-qwen3-rtl-rft
```

```sh
modal run scripts/modal_fireworks_rft.py::launch --force \
  --base-model accounts/fireworks/models/qwen3-0p6b \
  --account sorenmadsen \
  --output-model cologic-qwen3-rtl-rft
```

The dataset currently contains 16 rows: 10 seed combinational RTL tasks and 6
verified-gradient TPU/NPU tasks.

## Status

```sh
modal run scripts/modal_fireworks_rft.py::status \
  --job-id <job-id> \
  --account sorenmadsen
```

Raw Fireworks payload, including metrics/log URLs when present:

```sh
modal run scripts/modal_fireworks_rft.py::status \
  --job-id <job-id> \
  --account sorenmadsen \
  --raw
```

Cancel helper:

```sh
modal run scripts/modal_fireworks_rft.py::cancel \
  --job-id <job-id> \
  --account sorenmadsen
```

## Evaluation

Self-test the Modal grader with golden references:

```sh
modal run modal_app.py::main --selftest --split gradient \
  --out data/rft_eval_selftest_gradient.json
```

Probe whether a Fireworks model is callable through the account's inference API:

```sh
modal run modal_app.py::probe \
  --models-csv 'accounts/fireworks/models/qwen2p5-coder-7b-instruct,accounts/fireworks/models/qwen3-0p6b'
```

Run a before/after eval once both the base and RFT output model are callable:

```sh
RLHDL_MODEL=accounts/fireworks/models/qwen3-0p6b \
modal run modal_app.py::main --split heldout --n 1 \
  --out data/rft_eval_base_heldout.json \
  --dump data/rft_eval_base_heldout.jsonl

RLHDL_MODEL=accounts/sorenmadsen/models/cologic-qwen3-rtl-rft \
modal run modal_app.py::main --split heldout --n 1 \
  --out data/rft_eval_rft_heldout.json \
  --dump data/rft_eval_rft_heldout.jsonl
```

Repeat with `--split gradient` for the TPU/NPU tasks.

## Current Notes

- The earlier Gemma 4 RFT job `p0qwk2j6` failed in the trainer with
  `Model type gemma4 not supported`.
- A Qwen3 job `h8q9sbpg` was accepted by Fireworks RFT, but
  `accounts/fireworks/models/qwen3-0p6b` is not callable through the account's
  public inference endpoint, so standalone before/after eval requires deploying
  the base/output models or enabling inference access.
- Qwen3 job `h8q9sbpg` completed successfully and produced
  `accounts/sorenmadsen/models/cologic-qwen3-rtl-rft-0621b`. Fireworks reported
  128 rollout evaluations with average score `0.04849853125`, compiled average
  `0.0625`, and matched-fraction average `0.0230712890625`.
- The Fireworks API key in Modal can create RFT jobs/evaluators. The account's
  chat inference endpoint currently returns 404 for the probed public base model
  IDs, so base-vs-RFT eval is blocked until a callable/deployed base and output
  model are available.
