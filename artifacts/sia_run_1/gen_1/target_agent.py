"""Target agent: RTL optimizer for gate-count reduction with provable equivalence.

For each design in <dataset_dir>/manifest.json, samples structural rewrites from
the policy model, self-checks each with the immutable Modal grader (Verilator +
Yosys), and writes the best equivalent module to <working_dir>/submission/<id>.v.

Usage:
    python target_agent.py --dataset_dir <data/public> --working_dir <gen_dir>
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace

import modal
from openai import OpenAI

from cologic.extract import extract_module
from cologic.upload import task_from_manifest_entry

# ---------------------------------------------------------------------------
# Immutable verifier: Verilator (equivalence) + Yosys (gate count).
# This is the ONLY way to check equivalence or gate count — there is NO local
# Verilator or Yosys in this environment.  NEVER replace with an LLM guess.
# ---------------------------------------------------------------------------
_grader = modal.Function.from_name("rl-hdl", "grade_opt_remote")


def _log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


def grade(rtl: str, task, label: str = "") -> SimpleNamespace:
    """Run the deployed Modal verifier and return a SimpleNamespace with .reward / .info.

    Raises on any error — never falls back to a guess.
    """
    _log("SIM", f"{task.task_id} {label}: verifying via deployed Modal grader (Verilator + Yosys)")
    out = _grader.remote(rtl, task)  # raises on failure — no fallback
    r = SimpleNamespace(reward=out["reward"], info=out["info"])
    i = r.info
    cells = (f"{i.get('ref_cells')}->{i.get('cand_cells')}"
             if i.get("cand_cells") is not None else "n/a")
    ai = i.get("area_improvement")
    ai_s = f" ({ai * 100:+.1f}%)" if ai is not None else ""
    _log("FOOTPRINT", f"{task.task_id} {label}: equiv={i.get('equivalent')} "
                      f"cells {cells}{ai_s} reward={r.reward:.3f}")
    return r


# ---------------------------------------------------------------------------
# Policy model (Fireworks / OpenAI-compatible)
# ---------------------------------------------------------------------------
MODEL = os.environ.get("COLOGIC_TARGET_MODEL", "accounts/fireworks/models/kimi-k2p7-code")
_client = OpenAI(
    api_key=os.environ.get("FIREWORKS_API_KEY"),
    base_url=os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"),
    max_retries=6,
)

# ---------------------------------------------------------------------------
# Tunable knobs
# ---------------------------------------------------------------------------
N_CANDIDATES   = int(os.environ.get("COLOGIC_N_CANDIDATES",   "6"))
TEMPERATURE    = float(os.environ.get("COLOGIC_TEMPERATURE",  "0.9"))
MAX_REPAIR_ROUNDS = int(os.environ.get("COLOGIC_MAX_REPAIR",  "2"))
MAX_TOKENS     = int(os.environ.get("COLOGIC_MAX_TOKENS",     "2048"))

# ---------------------------------------------------------------------------
# Rewrite strategies (synth-surviving, arithmetic-structural)
# ---------------------------------------------------------------------------
STRATEGIES = [
    "Share arithmetic operators under mutually-exclusive selects: replace "
    "`y = s ? (a*b) : (c*d)` with a single multiplier and muxed operands "
    "`y = (s?a:c) * (s?b:d)`. Do the same for adders and subtractors.",
    "Remove redundant or duplicated arithmetic sub-expressions; fold constants "
    "into simpler forms.",
    "Strength-reduce constant multiplies/divides to shifts and adds/subtracts "
    "(e.g. `x * 8` → `x << 3`, `x * 5` → `(x << 2) + x`).",
    "Simplify and flatten nested if-else / case chains into the most compact "
    "equivalent combinational form.",
    "Restructure the datapath to minimise operator count while remaining exactly "
    "equivalent: merge, hoist, or factor common sub-expressions.",
]

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
SYSTEM_REWRITE = (
    "You are an expert hardware engineer specialising in RTL synthesis optimisation. "
    "You will be given a CORRECT Verilog module. Rewrite it to use FEWER gates while "
    "preserving EXACT functional equivalence. Keep the module name, port names, port "
    "directions, and port widths absolutely identical. Respond with exactly one Verilog "
    "module in a single ```verilog code block — no prose, no comments outside the block."
)
SYSTEM_REPAIR = (
    "You are an expert hardware engineer. Your previous Verilog rewrite failed the "
    "formal equivalence check. Fix it so it is EXACTLY equivalent to the original "
    "while keeping the gate count as small as possible. Keep the module name and all "
    "port declarations identical to the original. Respond with exactly one Verilog "
    "module in a single ```verilog code block — no prose."
)


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------
def _rewrite_msgs(task, strategy: str, dataset_dir: str, working_dir: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_REWRITE},
        {"role": "user", "content": (
            f"CONTEXT (for your information only — do not access the filesystem):\n"
            f"  Dataset directory (READ-ONLY): {dataset_dir}\n"
            f"  Working directory (READ-WRITE): {working_dir}\n\n"
            f"Optimize the following Verilog module for gate count.\n"
            f"Apply this strategy where it helps:\n  {strategy}\n\n"
            f"```verilog\n{task.reference_rtl}\n```\n\n"
            f"Return the optimized module `{task.top_module}` with the same name and interface."
        )},
    ]


def _repair_msgs(task, candidate: str, info: dict, dataset_dir: str, working_dir: str) -> list[dict]:
    p, t = info.get("eq_passed", 0), info.get("eq_total", 0)
    if info.get("stage") == "compile_error":
        why = "it did not compile:\n" + info.get("log", "")[:600]
    else:
        why = f"it compiles but is NOT equivalent — {t - p}/{t} output-vector comparisons mismatch."
    return [
        {"role": "system", "content": SYSTEM_REPAIR},
        {"role": "user", "content": (
            f"CONTEXT (for your information only — do not access the filesystem):\n"
            f"  Dataset directory (READ-ONLY): {dataset_dir}\n"
            f"  Working directory (READ-WRITE): {working_dir}\n\n"
            f"Original (correct) module:\n\n```verilog\n{task.reference_rtl}\n```\n\n"
            f"Your rewrite was rejected because {why}\n\n"
            f"Your rejected rewrite:\n\n```verilog\n{candidate}\n```\n\n"
            f"Return a corrected, exactly equivalent module with the same name and interface."
        )},
    ]


# ---------------------------------------------------------------------------
# LLM call helper — records the full message exchange for trajectory logging
# ---------------------------------------------------------------------------
def _chat(messages: list[dict]) -> tuple[str, list[dict]]:
    """Call the model; return (text_response, trajectory_messages)."""
    resp = _client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        top_p=0.95,
        max_tokens=MAX_TOKENS,
    )
    content = resp.choices[0].message.content or ""
    traj = list(messages) + [{"role": "assistant", "content": content}]
    return content, traj


# ---------------------------------------------------------------------------
# Per-design optimiser
# ---------------------------------------------------------------------------
def optimize_one(
    task,
    dataset_dir: str,
    working_dir: str,
) -> tuple[str, dict, list[dict], list[dict]]:
    """Return (best_rtl, best_info, candidate_log, trajectory_messages)."""
    _log("HARNESS", f"optimizing {task.task_id}: baseline + {N_CANDIDATES} rewrites "
                    f"(temp={TEMPERATURE}, repair<={MAX_REPAIR_ROUNDS})")

    # -- Grade the baseline so we have a valid lower bound --
    best_rtl = task.reference_rtl
    best = grade(best_rtl, task, "baseline")
    candidate_log = [{
        "origin": "baseline",
        "reward": best.reward,
        "stage": best.info.get("stage"),
        "equivalent": bool(best.info.get("equivalent")),
    }]
    all_messages: list[dict] = []

    for i in range(N_CANDIDATES):
        strategy = STRATEGIES[i % len(STRATEGIES)]
        _log("HARNESS", f"{task.task_id}: sampling rewrite {i} — {strategy[:56]}...")

        msgs = _rewrite_msgs(task, strategy, dataset_dir, working_dir)
        cand, traj = _chat(msgs)
        all_messages.extend(traj)

        r = grade(cand, task, f"rewrite{i}")
        rounds = 0

        while (rounds < MAX_REPAIR_ROUNDS
               and r.info.get("compiled")
               and not r.info.get("equivalent")):
            rounds += 1
            _log("HARNESS", f"{task.task_id}: rewrite {i} not equivalent — repair {rounds}")
            repair_msgs = _repair_msgs(task, cand, r.info, dataset_dir, working_dir)
            cand, traj = _chat(repair_msgs)
            all_messages.extend(traj)
            r = grade(cand, task, f"rewrite{i}+repair{rounds}")

        candidate_log.append({
            "origin": f"rewrite{i}",
            "strategy": strategy,
            "repair_rounds": rounds,
            "reward": r.reward,
            "stage": r.info.get("stage"),
            "equivalent": bool(r.info.get("equivalent")),
            "area_improvement": r.info.get("area_improvement"),
        })

        if r.reward > best.reward:
            best, best_rtl = r, cand
            _log("HARNESS", f"{task.task_id}: new best at rewrite {i}, "
                            f"reward={best.reward:.3f}")

    ai = best.info.get("area_improvement")
    ai_s = f"{ai * 100:+.1f}%" if ai is not None else "n/a"
    _log("RESULT", f"{task.task_id}: best equiv={best.info.get('equivalent')} "
                   f"area={ai_s} reward={best.reward:.3f}")

    return best_rtl, best.info, candidate_log, all_messages


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(
        description="RTL gate-count optimizer — produces submission/<id>.v for each design."
    )
    ap.add_argument("--dataset_dir", required=True,
                    help="Path to the dataset directory (READ-ONLY).")
    ap.add_argument("--working_dir", required=True,
                    help="Path to the working directory (READ-WRITE).")
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    working_dir = Path(args.working_dir)
    submission  = working_dir / "submission"
    submission.mkdir(parents=True, exist_ok=True)

    _log("MAIN", f"dataset_dir={dataset_dir}  working_dir={working_dir}")
    _log("MAIN", f"model={MODEL}  candidates={N_CANDIDATES}  temp={TEMPERATURE}")

    manifest = json.loads((dataset_dir / "manifest.json").read_text())
    designs  = manifest["designs"]

    # Single-execution task: one trajectory file covering all designs
    # (this is one cohesive optimisation run, not independent separate samples)
    trajectory: list[dict] = []

    for entry in designs:
        design_id = entry["id"]
        _log("MAIN", f"--- starting design {design_id} ---")

        # Load task via the shared, clocked-aware loader (matches evaluate.py)
        task = task_from_manifest_entry(entry, dataset_dir)

        best_rtl, info, candidate_log, messages = optimize_one(
            task,
            dataset_dir=str(dataset_dir),
            working_dir=str(working_dir),
        )

        # Extract just the module (strip surrounding noise if any)
        module_text = extract_module(best_rtl, task.top_module) or best_rtl
        out_path = submission / f"{design_id}.v"
        out_path.write_text(module_text.strip() + "\n")
        _log("MAIN", f"{design_id}: written to {out_path}")

        trajectory.append({
            "design_id": design_id,
            "best_reward": info.get("reward"),
            "stage": info.get("stage"),
            "equivalent": bool(info.get("equivalent")),
            "area_improvement": info.get("area_improvement"),
            "candidates": candidate_log,
            # Full LLM message exchange for this design (system-user-assistant turns)
            "messages": messages,
        })

        print(f"{design_id}: stage={info.get('stage')} equiv={info.get('equivalent')} "
              f"area={info.get('area_improvement')}")

    # Save single execution trajectory
    traj_path = working_dir / "agent_execution.json"
    traj_path.write_text(json.dumps(trajectory, indent=2))
    _log("MAIN", f"trajectory saved to {traj_path}")


if __name__ == "__main__":
    main()
