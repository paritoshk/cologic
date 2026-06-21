"""Run the Plan->Forge->Prove self-improvement loop on the HUD gateway.

  Plan  = big planner  (gemma-4-31b-it)   strategy / critique of the last attempt
  Forge = doer policy  (Qwen/Qwen3-8B)    writes/rewrites RTL   <- the RL target
  Prove = Verilator grade()               verifiable reward

This is the live-demo loop: a strong model teaching a smaller one to write better
Verilog, scored by real silicon tooling, iterating until it stops improving.

Usage:
  export $(grep -v '^#' .env.local | xargs)   # HUD_API_KEY
  python -m agents.run_loop [task_id] [max_iters]
"""
from __future__ import annotations

import os
import sys

from agents.loop import improve
from cologic.inference import gateway_model_fn
from cologic.tasks import TRAIN_TASKS

PLANNER = os.environ.get("COLOGIC_PLANNER", "gemma-4-31b-it")
DOER = os.environ.get("COLOGIC_DOER", "Qwen/Qwen3-8B")


def main() -> None:
    task_id = sys.argv[1] if len(sys.argv) > 1 else "add4"
    max_iters = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    task = next((t for t in TRAIN_TASKS if t.task_id == task_id), TRAIN_TASKS[0])

    forge = gateway_model_fn(DOER, temperature=0.7)
    plan = gateway_model_fn(PLANNER, temperature=0.4)

    print(f"task={task.task_id}  doer={DOER}  planner={PLANNER}  max_iters={max_iters}")
    best, history = improve(task, forge_model=forge, plan_model=plan, max_iters=max_iters)
    for a in history:
        print(f"  iter {a.iteration}: reward={a.reward:.3f}  {a.feedback[:70]}")
    print(f"BEST reward={best.reward:.3f} at iter {best.iteration} / {len(history)} iters")


if __name__ == "__main__":
    main()
