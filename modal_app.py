"""Modal app: parallel Verilator grading + the baseline eval entrypoint.

Grading runs in Modal containers (one Verilator build, fanned out with .map),
so rollouts/sec scales with container count rather than local cores. Inference
(Fireworks) runs locally in the entrypoint and is just concurrent HTTP.

Usage:
  modal run modal_app.py --selftest            # no API key; goldens -> pass@1 = 1.0
  modal run modal_app.py --split heldout --n 5 # zero-shot baseline (needs FIREWORKS_API_KEY)
  modal run modal_app.py --split train  --n 1
"""

from __future__ import annotations

from pathlib import Path

import modal

VERILATOR_TAG = "v5.038"

grader_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "git", "make", "g++", "autoconf", "flex", "bison",
        "help2man", "libfl-dev", "ccache", "perl",
    )
    .run_commands(
        f"git clone --depth 1 --branch {VERILATOR_TAG} "
        "https://github.com/verilator/verilator.git /tmp/verilator",
        "cd /tmp/verilator && autoconf && ./configure && "
        "make -j$(nproc) && make install && rm -rf /tmp/verilator",
    )
    .add_local_python_source("rl_hdl")
)

# Lightweight image for inference — just the OpenAI-compatible client. The
# Fireworks key arrives via the `fireworks-api` Modal Secret, so sampling has no
# dependency on the caller's local Python env.
inference_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("openai>=1.0")
    .add_local_python_source("rl_hdl")
)

app = modal.App("rl-hdl")


@app.function(image=grader_image, timeout=180)
def grade_remote(completion: str, task) -> dict:
    """Grade one (completion, task) in a container. Task pickles via rl_hdl."""
    from rl_hdl.verifier import grade

    r = grade(completion, task)
    return {"reward": r.reward, "info": r.info, "task_id": task.task_id}


@app.function(image=inference_image, secrets=[modal.Secret.from_name("fireworks-api")])
def list_models(substr: str = "") -> list[str]:
    """Return Fireworks model ids visible to this account (optionally filtered)."""
    import os

    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["FIREWORKS_API_KEY"],
        base_url=os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"),
    )
    ids = [m.id for m in client.models.list().data]
    return sorted(i for i in ids if substr.lower() in i.lower())


@app.function(image=inference_image, secrets=[modal.Secret.from_name("fireworks-api")], timeout=600)
def sample_remote(task, n: int, model: str, max_tokens: int) -> list[dict]:
    """Sample `n` completions for one task from Fireworks, inside Modal.

    Each item is {text, finish_reason} so the caller can see truncation.
    """
    from rl_hdl.inference import complete_raw

    temperature = 0.0 if n == 1 else 0.7  # greedy for a stable n=1 baseline read
    out = []
    for _ in range(n):
        text, finish = complete_raw(task, model=model, temperature=temperature, max_tokens=max_tokens)
        out.append({"text": text, "finish_reason": finish})
    return out


@app.local_entrypoint()
def main(
    split: str = "heldout",
    n: int = 1,
    selftest: bool = False,
    out: str = "baseline.json",
    dump: str = "",
):
    from collections import Counter

    from rl_hdl.eval import aggregate
    from rl_hdl.tasks import HELDOUT_TASKS, TRAIN_TASKS

    tasks = {"heldout": HELDOUT_TASKS, "train": TRAIN_TASKS}[split]

    if selftest:
        # Feed each task its own golden reference: a green end-to-end check of the
        # Modal grader with no model / API key required (expect pass@1 = 1.0).
        samples = [(t, t.reference_rtl, "selftest") for t in tasks]
        model = "selftest-golden"
    else:
        from rl_hdl.inference import max_tokens_setting, model_id

        model = model_id()
        mt = max_tokens_setting()
        print(f"sampling n={n} from {model} (max_tokens={mt}) for {len(tasks)} {split} tasks (in Modal) ...")
        per_task = list(sample_remote.map(
            tasks, [n] * len(tasks), [model] * len(tasks), [mt] * len(tasks)
        ))
        samples = [(t, s["text"], s["finish_reason"]) for t, lst in zip(tasks, per_task) for s in lst]

    pairs = [(t, txt) for t, txt, _ in samples]
    results = list(grade_remote.map([c for _, c in pairs], [t for t, _ in pairs]))

    report = aggregate(pairs, results, model=model)
    print("\n" + report.table() + "\n")
    print("finish_reason:", dict(Counter(f for _, _, f in samples)))
    Path(out).write_text(report.to_json())
    print(f"wrote {out}")

    if dump:
        import json

        with open(dump, "w") as fh:
            for (t, txt, finish), res in zip(samples, results):
                fh.write(json.dumps({
                    "task_id": t.task_id,
                    "finish_reason": finish,
                    "reward": res["reward"],
                    "stage": res["info"].get("stage"),
                    "completion": txt,
                }) + "\n")
        print(f"wrote {dump} ({len(samples)} records)")


@app.local_entrypoint()
def models(substr: str = ""):
    """List Fireworks models available to the account, e.g. --substr coder."""
    ids = list_models.remote(substr)
    print(f"\n{len(ids)} models" + (f" matching {substr!r}" if substr else "") + ":")
    for i in ids:
        print(f"  {i}")
    print()


@app.local_entrypoint()
def bench(total: int = 64):
    """Measure grading throughput (rollouts/sec) through the parallel grader.

    Grades golden references (correct, so they exercise the full compile+sim path)
    fanned out with .map across autoscaled containers.
    """
    import time

    from rl_hdl.tasks import SEED_TASKS

    goldens = [(t, t.reference_rtl) for t in SEED_TASKS]
    pairs = [goldens[i % len(goldens)] for i in range(total)]
    comps = [c for _, c in pairs]
    tks = [t for t, _ in pairs]

    t0 = time.time()
    results = list(grade_remote.map(comps, tks))
    dt = time.time() - t0

    ok = sum(r["reward"] == 1.0 for r in results)
    print(f"\ngraded {len(results)} designs in {dt:.1f}s "
          f"({len(results) / dt:.1f} grades/sec), {ok}/{len(results)} == 1.0\n")
