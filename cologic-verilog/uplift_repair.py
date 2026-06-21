"""Hard-task uplift: Gemma-4 single-shot vs Gemma-4 + Cologic loop on the
stream_arb_fifo repair task, graded by the REAL hidden grader (grade.py).

Single-shot = one greedy repair attempt. Loop = repair -> grade -> feed the
grader's critique back -> repair again, up to N iters, keep best reward. Same
model, same task, same grader. Policy via the HUD inference gateway.

  HUD_API_KEY=... python uplift_repair.py --model gemma-4-26b-a4b-it --iters 5
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).resolve().parent
TASK = HERE / "tasks" / "stream_arb_fifo_repair"
sys.path.insert(0, str(TASK / "donotaccess"))
import grade as G  # noqa: E402  the hidden grader

GATEWAY = os.environ.get("HUD_GATEWAY_URL", "https://inference.beta.hud.ai/v1")
PROMPT = (TASK / "prompt.md").read_text()
BUGGY = (TASK / "rtl" / "stream_arb_fifo.sv").read_text()
SYS = ("You are an expert SystemVerilog engineer. Repair the module so it meets the "
       "spec exactly. Output ONLY the complete corrected module in one ```verilog code "
       "block — no prose.")


def extract(text: str) -> str:
    m = re.search(r"```(?:verilog|systemverilog)?\s*(.*?)```", text, re.DOTALL)
    body = m.group(1) if m else text
    a, b = body.find("module"), body.rfind("endmodule")
    return body[a:b + len("endmodule")] if a != -1 and b != -1 else body.strip()


def grade_rtl(rtl: str) -> dict:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "stream_arb_fifo.sv"
        p.write_text(rtl)
        return G.grade(TASK, rtl_override=p, hidden_root=TASK / "donotaccess")


def critique(res: dict) -> str:
    subs = res.get("subscores", {})
    out = [f"reward={res.get('reward'):.3f}. Subscores:"]
    for name, s in subs.items():
        r = s.get("result", {})
        detail = r.get("detail", "")
        out.append(f"- {name}: {detail}")
        if name == "functional" and r.get("scenarios"):
            fails = [k for k, v in r["scenarios"].items() if v != "PASS"]
            if fails:
                out.append(f"  failing scenarios: {fails}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma-4-26b-a4b-it")
    ap.add_argument("--iters", type=int, default=5)
    ap.add_argument("--out", default="results/uplift_repair.json")
    args = ap.parse_args()
    client = OpenAI(api_key=os.environ["HUD_API_KEY"], base_url=GATEWAY)

    def ask(messages, temp):
        r = client.chat.completions.create(model=args.model, messages=messages,
                                           max_tokens=4096, temperature=temp)
        return r.choices[0].message.content or ""

    user0 = f"{PROMPT}\n\nRepair this RTL:\n```verilog\n{BUGGY}\n```"

    # single-shot (greedy)
    single = grade_rtl(extract(ask([{"role": "system", "content": SYS},
                                    {"role": "user", "content": user0}], 0.0)))
    print(f"single-shot reward = {single['reward']:.3f}")

    # cologic loop
    msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": user0}]
    best = single
    history = [single["reward"]]
    for i in range(args.iters):
        ans = ask(msgs, 0.3)
        rtl = extract(ans)
        res = grade_rtl(rtl)
        history.append(res["reward"])
        print(f"  loop iter {i+1}: reward = {res['reward']:.3f}")
        if res["reward"] > best["reward"]:
            best = res
        if res["reward"] >= 1.0 - 1e-9:
            break
        msgs += [{"role": "assistant", "content": ans},
                 {"role": "user", "content": critique(res) + "\n\nFix the remaining "
                  "issues. Output the full corrected module."}]

    summary = {"model": args.model, "task": "stream_arb_fifo_repair",
               "single_shot_reward": round(single["reward"], 4),
               "cologic_best_reward": round(best["reward"], 4),
               "uplift": round(best["reward"] - single["reward"], 4),
               "loop_history": [round(x, 4) for x in history]}
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    Path(args.out).write_text(json.dumps(summary, indent=2))
    print(f"\nsingle-shot={summary['single_shot_reward']}  cologic_best="
          f"{summary['cologic_best_reward']}  uplift={summary['uplift']:+}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
