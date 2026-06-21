"""Real eval via the HUD gateway + local Verilator grading.

The Modal/Fireworks sampling path is dead on this account (serverless 404s), and
the direct Fireworks deployment returns empty content, so this driver samples
through the working HUD gateway and grades locally. Writes an EvalReport JSON.

  source .env.local   # HUD_API_KEY
  python -m cologic.run_eval_hud --model Qwen/Qwen3-8B --n 5 --out baseline.json
  python -m cologic.run_eval_hud --model cologic-rtl   --n 5 --out cologic.json
"""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HUD_URL = "https://inference.beta.hud.ai/v1"


def _load_env(path: str = ".env.local") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--out", default="baseline.json")
    ap.add_argument("--max-workers", type=int, default=12)
    args = ap.parse_args()

    _load_env()
    from openai import OpenAI

    from cologic.eval import evaluate
    from cologic.prompt import build_messages
    from cologic.tasks import HELDOUT_TASKS
    from cologic.verifier import grade

    key = os.environ.get("HUD_API_KEY")
    if not key:
        raise SystemExit("set HUD_API_KEY (source .env.local)")
    client = OpenAI(api_key=key, base_url=os.environ.get("HUD_GATEWAY_URL", HUD_URL))

    # n==1 -> greedy for a stable read; otherwise sample for pass-rate spread.
    temp = 0.0 if args.n == 1 else 0.7

    def one(task):
        r = client.chat.completions.create(
            model=args.model, messages=build_messages(task), temperature=temp, max_tokens=1024
        )
        return task, (r.choices[0].message.content or "")

    jobs = [t for t in HELDOUT_TASKS for _ in range(args.n)]
    print(f"sampling n={args.n} from {args.model} for {len(HELDOUT_TASKS)} heldout tasks ({len(jobs)} calls) ...")
    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        pairs = list(pool.map(one, jobs))

    def grade_batch(ps):
        return [{"reward": (g := grade(c, t)).reward, "info": g.info, "task_id": t.task_id} for t, c in ps]

    report = evaluate(pairs, grade_batch, model=args.model)
    print("\n" + report.table() + "\n")
    Path(args.out).write_text(report.to_json())
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
