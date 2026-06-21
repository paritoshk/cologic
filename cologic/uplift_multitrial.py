"""Robustness of the Cologic loop's uplift: single-shot vs Plan->Forge->Prove over
K trials on a task, with pass-rate + mean-reward stats. n=1 is not credible because
the loop is stochastic (temperature) and can regress (over-edit -> broken build).

Honest finding (claude-haiku-4-5, hard stream_arb_fifo, K=5, 2026-06-20):
  single-shot pass@1 = 0.00  mean = 0.780
  loop        pass@1 = 0.00  mean = 0.796   -> uplift +0.016 (noise)
The loop frequently regresses to ~0.05 (broken compile) and never reaches a full
pass. Inference-time looping is NOT a reliable uplift on this task with this model;
a single lucky 0.78->1.0 trajectory does not reproduce. The real "model gets better"
story is weight training (RL/GRPO), not test-time iteration -- see agents/train.py.

  HUD_API_KEY=... python -m cologic.uplift_multitrial --model claude-haiku-4-5 --trials 5
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
TASKSETS = {"hard": HARD_TASKS, "heldout": HELDOUT_TASKS}


def make_forge(client: OpenAI, model: str, temperature: float, max_tokens: int):
    def forge(messages: list[dict]) -> str:
        r = client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, temperature=temperature,
        )
        return r.choices[0].message.content or ""
    return forge


def passed(reward: float) -> bool:
    return reward >= 1.0 - 1e-9


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-haiku-4-5")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--iters", type=int, default=6, help="max loop iterations per trial")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--taskset", default="hard", choices=sorted(TASKSETS))
    ap.add_argument("--task", default="", help="task_id; default = first in taskset")
    ap.add_argument("--out", default="cologic-verilog/results/uplift_multitrial.json")
    args = ap.parse_args()

    key = os.environ.get("HUD_API_KEY")
    if not key:
        raise SystemExit("set HUD_API_KEY (source .env.local)")
    client = OpenAI(api_key=key, base_url=GATEWAY, timeout=150)

    pool = TASKSETS[args.taskset]
    task = next((t for t in pool if t.task_id == args.task), pool[0])
    single = make_forge(client, args.model, 0.2, args.max_tokens)
    loopfn = make_forge(client, args.model, 0.5, args.max_tokens)

    trials = []
    print(f"model={args.model} task={task.task_id} trials={args.trials}\n")
    for k in range(args.trials):
        base = grade(single(build_messages(task)), task)
        best, hist = improve(task, forge_model=loopfn, grader=grade,
                             max_iters=args.iters, target_reward=1.0, patience=args.iters)
        row = {"trial": k, "single": round(base.reward, 4), "single_pass": passed(base.reward),
               "loop_best": round(best.reward, 4), "loop_pass": passed(best.reward),
               "curve": [round(a.reward, 4) for a in hist]}
        trials.append(row)
        print(f"trial {k}: single={row['single']:.3f}({'P' if row['single_pass'] else 'f'}) "
              f"loop={row['loop_best']:.3f}({'P' if row['loop_pass'] else 'f'}) curve={row['curve']}")

    K = len(trials)
    sp = sum(r["single_pass"] for r in trials) / K
    lp = sum(r["loop_pass"] for r in trials) / K
    sm = sum(r["single"] for r in trials) / K
    lm = sum(r["loop_best"] for r in trials) / K
    summary = {"model": args.model, "task": task.task_id, "trials": K,
               "single_pass_at_1": round(sp, 3), "loop_pass_at_1": round(lp, 3),
               "single_mean_reward": round(sm, 4), "loop_mean_reward": round(lm, 4),
               "uplift_pass": round(lp - sp, 3), "uplift_reward": round(lm - sm, 4),
               "per_trial": trials}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSINGLE pass@1={sp:.2f} mean={sm:.3f} | LOOP pass@1={lp:.2f} mean={lm:.3f} | "
          f"uplift pass {lp-sp:+.2f} reward {lm-sm:+.3f}\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
