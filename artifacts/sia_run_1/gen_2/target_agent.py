"""Target agent: RTL optimizer for gate-count reduction with provable equivalence.

Generation 2 improvements over Gen 1:
1. MAX_TOKENS increased from 2048 to 16384 — kimi-k2p7-code is a reasoning model
   that generates 3,000–8,000 tokens of chain-of-thought before the Verilog code
   block. 2048 tokens caused ALL candidates to be cut off mid-reasoning (no_module).
2. Removed `compiled` guard from repair loop — all non-equivalent candidates now
   receive repair attempts (was silently skipping no_module and compile_error).
3. Specialized no_module recovery — when the model produces no code block at all,
   use a direct "code only" prompt to get just the Verilog (no reasoning requested).
4. Extract module before grading — apply extract_module() before calling the grader
   so we pass clean Verilog, not raw reasoning prose + code.
5. Adaptive hill climbing — if a candidate improves best_rtl, subsequent candidates
   refine it rather than restarting from the baseline.
6. Usage logging — record completion_tokens per call to detect truncation.

Contract (set by SIA):
    python target_agent.py --dataset_dir <data/public> --working_dir <gen_dir>

For each design in manifest.json: reads baseline RTL, samples structural rewrites from
the policy model (OpenAI-compatible Fireworks), self-checks each with the IMMUTABLE
deployed Modal grader (Verilator + Yosys), repairs failures, writes the best verified
module to submission/<id>.v.

Verification is ALWAYS done via grade_opt_remote. No LLM equivalence checks. Fail
loudly on grader errors — no fallbacks.
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
#
# MAX_TOKENS: Gen 2 critical fix. kimi-k2p7-code is a reasoning model that
# produces thousands of tokens of chain-of-thought before outputting code.
# Gen 1 used 2048, which was exhausted during reasoning — no code was ever
# produced. 16384 gives room for ~6k reasoning + ~2k Verilog code.
# ---------------------------------------------------------------------------
N_CANDIDATES      = int(os.environ.get("COLOGIC_N_CANDIDATES",  "6"))
TEMPERATURE       = float(os.environ.get("COLOGIC_TEMPERATURE", "0.9"))
MAX_REPAIR_ROUNDS = int(os.environ.get("COLOGIC_MAX_REPAIR",    "2"))
MAX_TOKENS        = int(os.environ.get("COLOGIC_MAX_TOKENS",    "16384"))

# ---------------------------------------------------------------------------
# Rewrite strategies (synth-surviving, arithmetic-structural)
# Strategy 0 is deliberately broad — it asks the model to identify the most
# impactful optimization for whatever circuit it sees, rather than blindly
# applying a specific technique.
# ---------------------------------------------------------------------------
STRATEGIES = [
    # Strategy 0: Circuit-aware analysis — pick the most impactful optimization
    (
        "Analyze the circuit and apply the single most impactful structural optimization:\n"
        "  (a) If it MUXes two or more separate arithmetic operations on a shared select,\n"
        "      merge into ONE operator with muxed operands: y=(s?a:c)*(s?b:d) not two ops.\n"
        "  (b) If it counts set bits (popcount), rewrite as an explicit binary adder tree:\n"
        "      layer-1 adds pairs, layer-2 adds layer-1 outputs, etc. to a final sum.\n"
        "  (c) If it manually computes a product via partial products or shifts, collapse to\n"
        "      a single `assign p = a * b;` and let the synthesizer handle it.\n"
        "  (d) Replace constant multiplications with shifts+adds (x*8->x<<3, x*5->(x<<2)+x).\n"
        "Choose whichever gives the largest gate-count reduction."
    ),
    # Strategy 1: Clean rewrite — simple forms that synthesize smallest
    (
        "Rewrite the module as simply as possible:\n"
        "  - For a multiplier: `assign p = a * b;`\n"
        "  - For a 4:1 or N:1 mux: use a case statement on sel.\n"
        "  - For popcount: `assign count = a[0]+a[1]+a[2]+...+a[N];`\n"
        "  - For conditional arithmetic: single operator with muxed inputs.\n"
        "Remove any hand-coded loop, bit-mask, or partial-product structure — let the "
        "synthesizer produce the smallest netlist from a clean high-level description."
    ),
    # Strategy 2: Arithmetic operator sharing (key for matrix-multiply circuits)
    (
        "Share arithmetic operators under mutually-exclusive selects: replace "
        "two separate multipliers/adders used in a ternary or case-select with "
        "a single shared operator whose operands are muxed before the operation. "
        "E.g.: replace `y = s ? (a*b) : (c*d)` with `y = (s?a:c) * (s?b:d)`. "
        "Do the same for adders and subtractors."
    ),
    # Strategy 3: Strength reduction and constant folding
    (
        "Strength-reduce constant multiplies/divides to shifts and adds "
        "(e.g. `x * 8` -> `x << 3`, `x * 5` -> `(x << 2) + x`). "
        "Fold compile-time constants. Remove zero-padding and unnecessary width extensions."
    ),
    # Strategy 4: Case/mux simplification
    (
        "Simplify and flatten cascaded case/if-else chains into the most compact "
        "equivalent combinational form. For N:1 mux structures, use a clean case "
        "statement or nested ternaries with minimum logic."
    ),
    # Strategy 5: Dead code elimination and common subexpression elimination
    (
        "Identify and eliminate dead code; merge equivalent branches; "
        "apply common subexpression elimination. Look for signals that are "
        "computed but have the same value under all reachable conditions."
    ),
]

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
SYSTEM_REWRITE = (
    "You are an expert hardware engineer specialising in RTL synthesis optimisation. "
    "You are given a CORRECT Verilog module. Rewrite it to use FEWER gates while "
    "preserving EXACT functional equivalence. "
    "Keep the module name, port names, port directions, and port widths IDENTICAL. "
    "Output EXACTLY ONE Verilog module in a single ```verilog code block. "
    "No prose after the code block."
)

SYSTEM_REFINE = (
    "You are an expert hardware engineer specialising in RTL synthesis optimisation. "
    "You are given a Verilog module that has ALREADY been partially optimized. "
    "Reduce its gate count FURTHER while preserving EXACT functional equivalence. "
    "Keep the module name, port names, port directions, and port widths IDENTICAL to "
    "the ORIGINAL interface. "
    "Output EXACTLY ONE Verilog module in a single ```verilog code block. "
    "No prose after the code block."
)

SYSTEM_REPAIR = (
    "You are an expert hardware engineer. Your previous Verilog rewrite was rejected "
    "by the equivalence checker. Fix it so it is EXACTLY equivalent to the original "
    "module while keeping it as small as possible. "
    "Keep the module name and interface IDENTICAL to the original. "
    "Output EXACTLY ONE Verilog module in a single ```verilog code block. "
    "No prose after the code block."
)

# Used when stage=no_module: model produced reasoning but no code block at all.
# Skip chain-of-thought — demand code immediately.
SYSTEM_CODE_ONLY = (
    "You are an expert hardware engineer. "
    "Output ONLY a ```verilog code block containing the optimized Verilog module. "
    "No analysis, no prose — just the code block."
)


# ---------------------------------------------------------------------------
# LLM call helper
# ---------------------------------------------------------------------------
def _chat(messages: list[dict]) -> tuple[str, dict]:
    """Call the model; return (text_response, usage_dict)."""
    resp = _client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        top_p=0.95,
        max_tokens=MAX_TOKENS,
    )
    content = resp.choices[0].message.content or ""
    usage = {}
    if resp.usage:
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
            "cost_usd": 0,  # per-provider pricing unknown
        }
    # Warn if the model was cut off — completion_tokens == MAX_TOKENS likely
    # means reasoning was truncated and no code block was produced.
    if usage.get("completion_tokens") == MAX_TOKENS:
        _log("WARN", f"completion_tokens == MAX_TOKENS ({MAX_TOKENS}); model may be cut off!")
    return content, usage


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------
def _rewrite_user(task, strategy: str) -> str:
    return (
        f"Optimize the following Verilog module for gate count.\n"
        f"Strategy:\n{strategy}\n\n"
        f"```verilog\n{task.reference_rtl}\n```\n\n"
        f"Return the optimized module `{task.top_module}` with the SAME name and interface."
    )


def _refine_user(task, current_rtl: str, current_info: dict, strategy: str) -> str:
    ref_cells = current_info.get("ref_cells", "?")
    cand_cells = current_info.get("cand_cells", "?")
    # Strip any markdown fences so the current best appears as clean Verilog.
    clean_rtl = extract_module(current_rtl, task.top_module) or current_rtl
    return (
        f"This module has been optimized from {ref_cells} to {cand_cells} cells. "
        f"Push it further — target fewer than {cand_cells} cells.\n\n"
        f"Strategy to try:\n{strategy}\n\n"
        f"Current optimized module ({cand_cells} cells):\n"
        f"```verilog\n{clean_rtl}\n```\n\n"
        f"Original interface to preserve (module `{task.top_module}`, same ports):\n"
        f"```verilog\n{task.reference_rtl}\n```\n\n"
        f"Return a further-optimized version with fewer than {cand_cells} cells, "
        f"preserving exact equivalence."
    )


def _repair_user(task, candidate: str, info: dict) -> str:
    clean_cand = extract_module(candidate, task.top_module) or candidate
    stage = info.get("stage", "unknown")
    if stage == "compile_error":
        why = "it did not compile:\n" + info.get("log", "")[:800]
    else:
        p, t = info.get("eq_passed", 0), info.get("eq_total", 0)
        why = (
            f"it compiles but is NOT equivalent — "
            f"{t - p}/{t} output-vector comparisons mismatch."
        )
    return (
        f"Original (correct) module:\n\n```verilog\n{task.reference_rtl}\n```\n\n"
        f"Your rewrite was rejected: {why}\n\n"
        f"Your rejected rewrite:\n\n```verilog\n{clean_cand}\n```\n\n"
        f"Return a corrected, equivalent module with the SAME name and interface as the original."
    )


def _code_only_user(task, strategy: str) -> str:
    """Prompt for when the model produced no code at all (stage=no_module).

    Skips reasoning context — just asks for the Verilog directly.
    """
    return (
        f"Output ONLY the optimized Verilog module in a ```verilog code block.\n\n"
        f"Optimization goal: {strategy}\n\n"
        f"Module to optimize:\n```verilog\n{task.reference_rtl}\n```\n\n"
        f"Return module `{task.top_module}` with the SAME name and interface, but fewer gates."
    )


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
                    f"(temp={TEMPERATURE}, repair<={MAX_REPAIR_ROUNDS}, max_tokens={MAX_TOKENS})")

    # Grade the baseline so we have a valid lower bound
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

        # ------------------------------------------------------------------
        # Adaptive hill climbing:
        # If a previous candidate improved over baseline, build on it.
        # Otherwise, try a fresh strategy on the baseline.
        # ------------------------------------------------------------------
        if best_rtl is not task.reference_rtl and best.info.get("cand_cells") is not None:
            approach = f"refine{i}"
            _log("HARNESS", f"{task.task_id}: refining best "
                            f"({best.info.get('cand_cells')} cells) round {i} — "
                            f"{strategy[:56]}...")
            user_text = _refine_user(task, best_rtl, best.info, strategy)
            messages: list[dict] = [
                {"role": "system", "content": SYSTEM_REFINE},
                {"role": "user", "content": user_text},
            ]
        else:
            approach = f"rewrite{i}"
            _log("HARNESS", f"{task.task_id}: sampling rewrite {i} — {strategy[:56]}...")
            user_text = _rewrite_user(task, strategy)
            messages = [
                {"role": "system", "content": SYSTEM_REWRITE},
                {"role": "user", "content": user_text},
            ]

        raw, usage = _chat(messages)
        all_messages.extend(messages + [{"role": "assistant", "content": raw, "usage": usage}])

        # Extract the Verilog module before grading — pass clean code, not prose
        cand = extract_module(raw, task.top_module) or raw

        r = grade(cand, task, approach)
        rounds = 0

        # ------------------------------------------------------------------
        # Gen 2 fix: repair ALL non-equivalent results.
        # Gen 1 had: `and r.info.get("compiled")` which silently skipped
        # no_module (stage=no_module means compiled=False) and compile errors.
        # We now attempt repair for every failure mode.
        # ------------------------------------------------------------------
        while rounds < MAX_REPAIR_ROUNDS and not r.info.get("equivalent"):
            rounds += 1
            stage = r.info.get("stage", "unknown")
            _log("HARNESS", f"{task.task_id}: {approach} not equivalent "
                            f"(stage={stage}) — repair {rounds}/{MAX_REPAIR_ROUNDS}")

            if stage == "no_module":
                # Model produced no code at all — use a code-only prompt to
                # force it to output the Verilog block directly.
                repair_user = _code_only_user(task, strategy[:120])
                repair_msgs = [
                    {"role": "system", "content": SYSTEM_CODE_ONLY},
                    {"role": "user", "content": repair_user},
                ]
            else:
                # compile_error or equivalence failure — show what went wrong
                repair_user = _repair_user(task, cand, r.info)
                repair_msgs = [
                    {"role": "system", "content": SYSTEM_REPAIR},
                    {"role": "user", "content": repair_user},
                ]

            raw_r, usage_r = _chat(repair_msgs)
            all_messages.extend(
                repair_msgs + [{"role": "assistant", "content": raw_r, "usage": usage_r}]
            )

            cand = extract_module(raw_r, task.top_module) or raw_r
            r = grade(cand, task, f"{approach}+repair{rounds}")

        candidate_log.append({
            "origin": approach,
            "strategy": strategy[:80],
            "repair_rounds": rounds,
            "reward": r.reward,
            "stage": r.info.get("stage"),
            "equivalent": bool(r.info.get("equivalent")),
            "area_improvement": r.info.get("area_improvement"),
        })

        if r.reward > best.reward:
            best, best_rtl = r, cand
            _log("HARNESS", f"{task.task_id}: new best at {approach}, "
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
    _log("MAIN", f"model={MODEL}  candidates={N_CANDIDATES}  "
                 f"temp={TEMPERATURE}  max_tokens={MAX_TOKENS}")

    manifest = json.loads((dataset_dir / "manifest.json").read_text())
    designs  = manifest["designs"]

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
            "messages": messages,
        })

        print(f"{design_id}: stage={info.get('stage')} equiv={info.get('equivalent')} "
              f"area={info.get('area_improvement')}")

    # Save execution trajectory
    traj_path = working_dir / "agent_execution.json"
    traj_path.write_text(json.dumps(trajectory, indent=2))
    _log("MAIN", f"trajectory saved to {traj_path}")


if __name__ == "__main__":
    main()
