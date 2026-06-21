"""GRPO training of the forked doer (cologic-rtl) on the HUD platform.

Managed loop per the HUD training docs: roll out the taskset with within-group
spread, hand the Runs to TrainingClient.step (forward_backward + optim_step),
repeat. Watches the checkpoint tree for rising mean_reward / non-trivial
reward_std — if every rollout scores the same, GRPO advantage is 0 and nothing
learns, so we log the spread and bail early.

Run (project python with hud-python installed):
  export $(grep -v '^#' .env.local | xargs)
  python agents/train.py [steps] [group]
"""
import asyncio
import os
import sys

from hud import Job, Taskset, TrainingClient
from hud.agents import create_agent

SLUG = os.environ.get("COLOGIC_TRAIN_SLUG", "cologic-rtl")
TASKSET = os.environ.get("COLOGIC_TASKSET", "cologic-verilog")
STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
GROUP = int(sys.argv[2]) if len(sys.argv) > 2 else 8
LR = float(os.environ.get("COLOGIC_LR", "1e-5"))


async def main() -> None:
    agent = create_agent(SLUG, completion_kwargs={"extra_body": {"return_token_ids": True}})
    trainer = TrainingClient(SLUG)
    taskset = Taskset.from_api(TASKSET)
    session = await Job.start(SLUG, group=GROUP)
    print(f"train slug={SLUG} taskset={TASKSET} steps={STEPS} group={GROUP} lr={LR}", flush=True)

    for step in range(STEPS):
        start = len(session.runs)
        await taskset.run(agent, job=session)
        batch = session.runs[start:]
        rewards = [getattr(r, "reward", 0.0) or 0.0 for r in batch]
        spread = (max(rewards) - min(rewards)) if rewards else 0.0
        mean = sum(rewards) / len(rewards) if rewards else 0.0
        print(f"[rollout {step}] n={len(batch)} mean={mean:.3f} spread={spread:.3f} "
              f"min={min(rewards, default=0):.3f} max={max(rewards, default=0):.3f}", flush=True)

        if spread == 0.0:
            print("[warn] zero within-group spread -> GRPO advantage is 0, no gradient. "
                  "Stopping; the taskset is all-or-nothing for this model.", flush=True)
            break

        res = await trainer.step(batch, learning_rate=LR, loss_fn="ppo", group_size=GROUP)
        print(f"[step {step}] optim done: {res}", flush=True)

    print("=== checkpoints ===", flush=True)
    for c in await trainer.checkpoints():
        print(f"  {c.name}  mean_reward={getattr(c,'mean_reward',None)} "
              f"std={(getattr(c,'metrics',{}) or {}).get('reward_std')}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
