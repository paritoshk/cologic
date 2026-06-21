"""Modal wrapper for the SIA harness-lever loop on the RTL-optimize task.

Turns the loop: SIA's meta/feedback agents evolve the optimizer scaffold
(`reference_target_agent.py`) across generations; each generation the target agent
optimizes the designs and `evaluate.py` scores it with the IMMUTABLE grader
(Verilator + Yosys). Single provider: meta + target both run on Fireworks
(meta via PydanticAI), so only the `fireworks-api` secret is needed.

Everything runs in one container that has the toolchain (so the agent + evaluate.py
can grade locally) and the repo (so SIA's per-generation venv installs `cologic`
editable).

  modal run scripts/modal_sia_run.py::validate          # cheap: no LLM calls
  modal run scripts/modal_sia_run.py::run --max-gen 2    # SPENDS (Fireworks)
"""

from __future__ import annotations

import json

import modal

REPO = "/root/rl-hdl"

# NO silicon toolchain here. Verification runs on the DEPLOYED `grade_opt_remote`
# Modal function (which already has Verilator+Yosys); the agent + evaluate.py call
# it by name. So this image is just Python deps + the repo — builds in seconds.
sia_image = (
    modal.Image.debian_slim(python_version="3.11")
    # `uv` so SIA builds its per-generation venv fast; sia-agent with the PydanticAI
    # meta impl (Fireworks/OpenAI-compatible); openai (target sampling) + modal (lookup).
    .pip_install("uv", "sia-agent[pydantic-ai]", "openai>=1.0", "modal>=0.64")
    # The repo: SIA's venv installs cologic editable from here, and the task dir ships.
    .add_local_dir(
        ".", REPO, copy=True,
        ignore=[".git", ".venv", "**/__pycache__", "runs", "data", "*.lock",
                "*.jsonl", "ve_*.json", "*_selftest.json"],
    )
)

app = modal.App("rl-hdl-sia")

TASK_DIR = f"{REPO}/sia_task/rtl-optimize"


@app.function(image=sia_image, timeout=300)
def validate() -> dict:
    """Cheap preflight: image built, sia importable, task/profiles well-formed. No LLM calls."""
    import subprocess
    from pathlib import Path

    out = {}
    out["sia_help_rc"] = subprocess.run(["sia", "run", "--help"], capture_output=True).returncode
    out["verilator"] = subprocess.run(["verilator", "--version"], capture_output=True, text=True).stdout.strip()[:40]
    out["yosys"] = subprocess.run(["yosys", "--version"], capture_output=True, text=True).stdout.strip()[:40]

    task = Path(TASK_DIR)
    out["task_md"] = (task / "data/public/task.md").exists()
    out["evaluate_py"] = (task / "data/public/evaluate.py").exists()
    out["reference_agent"] = (task / "reference/reference_target_agent.py").exists()
    out["profiles"] = sorted(p.name for p in (task / "profiles").glob("*.json"))
    out["providers"] = sorted(p.name for p in (task / "providers").glob("*.json"))
    out["public_designs"] = json.loads((task / "data/public/manifest.json").read_text())["designs"]
    # cologic is editable-installable from the repo (what SIA's venv will do)
    rc = subprocess.run(["uv", "pip", "install", "--system", "-e", REPO], capture_output=True, text=True)
    out["cologic_editable_install_rc"] = rc.returncode
    out["cologic_importable"] = subprocess.run(
        ["python", "-c", "import cologic, cologic.grader, cologic.upload; print('ok')"],
        capture_output=True, text=True,
    ).stdout.strip()
    return out


@app.function(image=sia_image, secrets=[modal.Secret.from_name("fireworks-api")], timeout=5400, cpu=4.0)
def sia_run_remote(
    max_gen: int, run_id: int, target_model: str, meta_model: str,
    n_candidates: int, temperature: float, max_repair: int, meta_max_turns: int,
) -> dict:
    """Run `sia run` for the harness lever and return each generation's score."""
    import os
    import subprocess
    from pathlib import Path

    task = Path(TASK_DIR)

    # The target agent runs in SIA's per-generation venv; it needs cologic (Task
    # building from RTL), openai (sampling), and modal (to call the deployed verifier).
    (task / "reference/requirements.txt").write_text(f"openai>=1.0\nmodal>=0.64\n-e {REPO}\n")

    # Inject the chosen models into the profiles (single provider: fireworks).
    _patch_profile(task / "profiles/fireworks-target.json", target_model)
    _patch_profile(task / "profiles/fireworks-meta.json", meta_model)

    work = Path("/root/work")
    work.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["SIA_PROVIDERS_DIR"] = str(task / "providers")
    env["SIA_PROFILES_DIR"] = str(task / "profiles")
    # Give the meta/feedback agent enough tool turns to read context + write the
    # full target_agent.py (the default cap of 20 is too few).
    env["SIA_MAX_TURNS"] = str(meta_max_turns)
    # Harness knobs the seed agent reads (the search space SIA then evolves).
    env["COLOGIC_TARGET_MODEL"] = target_model
    env["COLOGIC_N_CANDIDATES"] = str(n_candidates)
    env["COLOGIC_TEMPERATURE"] = str(temperature)
    env["COLOGIC_MAX_REPAIR"] = str(max_repair)

    cmd = [
        "sia", "run", "--task_dir", str(task), "--max_gen", str(max_gen),
        "--run_id", str(run_id), "--no-web",
        "--meta-agent-profile", "fireworks-meta",
        "--target-agent-profile", "fireworks-target",
    ]
    proc = subprocess.run(cmd, cwd=str(work), env=env, capture_output=True, text=True)

    run_dir = work / "runs" / f"run_{run_id}"
    generations = []
    if run_dir.exists():
        for gdir in sorted(run_dir.glob("gen_*")):
            rj = gdir / "results.json"
            generations.append({
                "gen": gdir.name,
                "results": json.loads(rj.read_text()) if rj.exists() else None,
                "has_target_agent": (gdir / "target_agent.py").exists(),
            })
    return {
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-6000:],
        "stderr_tail": proc.stderr[-3000:],
        "generations": generations,
    }


def _patch_profile(path, model: str) -> None:
    data = json.loads(path.read_text())
    data["model"] = model
    path.write_text(json.dumps(data, indent=2) + "\n")


@app.local_entrypoint()
def main(
    max_gen: int = 2,
    run_id: int = 1,
    target_model: str = "accounts/fireworks/models/kimi-k2p7-code",
    meta_model: str = "accounts/fireworks/models/kimi-k2p7-code",
    n_candidates: int = 4,
    temperature: float = 0.9,
    max_repair: int = 1,
    meta_max_turns: int = 60,
):
    """Run the SIA harness loop. SPENDS Fireworks tokens (meta + target x generations)."""
    r = sia_run_remote.remote(max_gen, run_id, target_model, meta_model,
                              n_candidates, temperature, max_repair, meta_max_turns)
    print(f"\nsia run rc={r['returncode']}\n")
    print(f"{'generation':<10} {'mean_reward':>12} {'mean_area_impr':>15} {'equiv':>8}")
    print("-" * 50)
    for g in r["generations"]:
        res = g["results"] or {}
        ai = res.get("mean_area_improvement")
        ai_s = "n/a" if ai is None else f"{ai * 100:+.1f}%"
        eq = f"{res.get('n_equivalent', '?')}/{res.get('n_total', '?')}"
        print(f"{g['gen']:<10} {res.get('mean_reward', 0):>12.4f} {ai_s:>15} {eq:>8}")
    if r["returncode"] != 0:
        print("\n--- stderr tail ---\n" + r["stderr_tail"])


@app.local_entrypoint()
def validate_entry():
    """Cheap preflight (no LLM calls): modal run scripts/modal_sia_run.py::validate_entry"""
    import json as _json

    print(_json.dumps(validate.remote(), indent=2))
