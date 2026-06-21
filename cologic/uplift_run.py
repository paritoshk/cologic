"""Measure the Cologic loop's uplift over single-shot, apples-to-apples.

Same model, same heldout tasks, local Verilator grading:
  baseline arm  = one greedy completion per task           (single-shot)
  cologic arm   = agents.improve() Plan->Forge->Prove loop (multi-attempt + feedback)

The delta is purely the loop's contribution. Policy runs through the HUD inference
gateway (Fireworks has no accessible models on this account). Honest: this measures
inference-time self-improvement, not weight training (that's the fork+RL flywheel).

  HUD_API_KEY=... python -m cologic.uplift_run --model claude-haiku-4-5 --iters 4
"""
from __future__ import annotations

import argparse
import json
import os

from openai import OpenAI

from agents.loop import improve
from cologic.prompt import build_messages
from cologic.verifier import grade
from cologic.tasks import HARD_TASKS, HELDOUT_TASKS

GATEWAY = os.environ.get("HUD_GATEWAY_URL", "https://inference.beta.hud.ai/v1")

# Saturated ho_* tasks (HELDOUT) show ~zero uplift; the real headroom is the hard
# stream_arb_fifo design task. Default to it; --taskset heldout keeps the old set.
TASKSETS = {"hard": HARD_TASKS, "heldout": HELDOUT_TASKS}


def make_forge(client: OpenAI, model: str, temperature: float):
    def forge(messages: list[dict]) -> str:
        r = client.chat.completions.create(
            model=model, messages=messages, max_tokens=2048, temperature=temperature,
        )
        return r.choices[0].message.content or ""
    return forge


def passed(reward: float) -> bool:
    return reward >= 1.0 - 1e-9  # full pass == compiles AND testbench prints PASS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-haiku-4-5")
    ap.add_argument("--iters", type=int, default=4, help="max loop iterations")
    ap.add_argument("--taskset", default="hard", choices=sorted(TASKSETS),
                    help="hard = stream_arb_fifo (real headroom); heldout = saturated ho_*")
    ap.add_argument("--tasks", default="", help="comma task_ids; default = all in --taskset")
    ap.add_argument("--out", default="cologic-verilog/results/uplift.json")
    args = ap.parse_args()

    key = os.environ.get("HUD_API_KEY")
    if not key:
        raise SystemExit("set HUD_API_KEY (source .env.local)")
    client = OpenAI(api_key=key, base_url=GATEWAY)

    tasks = TASKSETS[args.taskset]
    if args.tasks:
        want = set(args.tasks.split(","))
        tasks = [t for t in tasks if t.task_id in want]

    greedy = make_forge(client, args.model, 0.0)
    loopfn = make_forge(client, args.model, 0.3)

    rows = []
    print(f"model={args.model}  tasks={len(tasks)}  loop_iters={args.iters}\n")
    print(f"{'task':14} {'single':>7} {'cologic':>8}  {'loop iters->pass'}")
    for t in tasks:
        base = grade(greedy(build_messages(t)), t)            # single-shot
        best, hist = improve(t, forge_model=loopfn, grader=grade,
                             max_iters=args.iters, target_reward=1.0, patience=args.iters)
        b_ok, c_ok = passed(base.reward), passed(best.reward)
        rows.append({"task_id": t.task_id, "single_shot_pass": b_ok, "single_shot_reward": base.reward,
                     "cologic_pass": c_ok, "cologic_reward": best.reward,
                     "iters_to_best": best.iteration + 1, "attempts": len(hist),
                     "reward_curve": [round(a.reward, 4) for a in hist]})
        print(f"{t.task_id:14} {('PASS' if b_ok else 'fail'):>7} {('PASS' if c_ok else 'fail'):>8}  "
              f"{len(hist)} -> {'PASS' if c_ok else 'fail'} @iter{best.iteration+1}")

    base_p1 = sum(r["single_shot_pass"] for r in rows) / len(rows)
    col_p1 = sum(r["cologic_pass"] for r in rows) / len(rows)
    summary = {"model": args.model, "n_tasks": len(rows), "loop_iters": args.iters,
               "baseline_pass_at_1": round(base_p1, 3), "cologic_pass_at_1": round(col_p1, 3),
               "uplift": round(col_p1 - base_p1, 3), "per_task": rows}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nbaseline pass@1 = {base_p1:.3f}   cologic pass@1 = {col_p1:.3f}   "
          f"uplift = {col_p1 - base_p1:+.3f}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
