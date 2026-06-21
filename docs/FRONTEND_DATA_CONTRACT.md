# Frontend instructions — Cologic demo (`web/`)

_Written 2026-06-20 from the `kabul` workspace. The frontend is OWNED by the parallel
agent in `charlotte` (it rewrote `index.html` + added `data.json`). Coordinate before editing `web/`._

## 1. Reconciliation with Soren — DONE, nothing to pull

Checked `upstream` (`sorenjmadsen/rl-hdl`) vs `origin` (`paritoshk/cologic`):

- **Soren made ZERO `web/` changes** since the common base (`05ac053`):
  `git diff 05ac053 upstream/main -- web/` is **empty**.
- All frontend evolution is on **our** side: `index.html` rewritten to fetch `data.json`,
  plus new `web/data.json` and `web/die.html`.

**Action: none.** `paritoshk/cologic` is the canonical frontend. Do **not** merge Soren's `web/`
(it's the old static version). Keep deploying from `origin/main` (Vercel root = `web`).

## 2. The data contract — `web/data.json` (already wired)

`index.html` does `fetch('./data.json',{cache:'no-store'})` and renders from it, with the
hardcoded values as fallback. To update the demo, **regenerate `data.json` and push** — no JS edits.

```jsonc
{
  "source": "baseline+cologic eval",
  "baseline_model": "Qwen/Qwen3-8B",     // the BEFORE model (weak base, ho_* has headroom)
  "cologic_model":  "cologic-rtl",        // the AFTER model (GRPO-trained fork on HUD)
  "gate": 0.6,                            // deploy-gate line on the chart
  "baseline_pass_at_1": 0.267,            // headline BEFORE number
  "cologic_pass_at_1":  0.3,              // headline AFTER number
  "uplift": 0.033,                        // cologic - baseline
  "n_per_task": 5,                        // rollouts per task (whisker/CI)
  "per_task": [                           // grouped bars + table, one row per task
    { "id":"ho_mux2_w16","short":"mux2_w16","baseline":1.0,"cologic":1.0,"bp":"5/5","cp":"5/5" }
    // ...6 ho_* tasks: baseline/cologic = pass-rate; bp/cp = "passes/samples"
  ],
  "epochs": null                          // training curve — NOT YET POPULATED (see gaps)
}
```

`baseline` → the `gem`-style bar (before), `cologic` → the green bar (after). The page derives
SVG from these; you only ever touch the JSON.

## 3. What is REAL vs what is NOT (honesty — non-negotiable)

**REAL today** (from the RL/weight-training track, the parallel agent's eval):
- `baseline_pass_at_1` 0.267 → `cologic_pass_at_1` 0.300, uplift **+0.033**, on Qwen3-8B vs the
  `cologic-rtl` GRPO fork. Per-task ho_* numbers are measured. This is the legitimate
  "weight training makes the model better" story — modest but honest, on a base model weak
  enough that ho_* isn't saturated (unlike Gemma-4/Haiku, which solve ho_* single-shot).

**NOT real / do NOT chart:**
- **The inference-time Plan→Forge→Prove loop is NOT an uplift story.** Measured this session
  (Haiku, hard `stream_arb_fifo`, 5 trials): single 0.780 / loop 0.796, both pass@1=0.00,
  uplift +0.016 (noise); the loop regresses to broken builds. One lucky 0.78→1.0 run does not
  reproduce. Keep it off the site. (Evidence: `cologic/uplift_multitrial.py`, PR #6.)
- **`epochs` is `null`** → the "watch it get better" training curve has **no real data yet**.
  Either hide that figure or populate `epochs` with real per-step pass@1 from the GRPO run
  (`agents/train.py` checkpoints). Do not resurrect the fake `0.567→0.667` series.
- **Power / compute-efficiency cards** have **no real source** (the RL eval emits pass@1/reward,
  not mW or compute %). Drop them or label "illustrative". Power may say `rel.` only if backed by
  the yosys gate-count proxy in the repair grader — it is NOT in `data.json`, so don't imply it.

## 4. To refresh the numbers
1. Run the eval that emits the schema above (the parallel agent's `cologic/baseline_local.py` /
   `chart_baseline.py`, or extend it). Write `web/data.json`.
2. To add the training curve: populate `"epochs": [{step, pass_at_1}, …]` from the GRPO
   checkpoints; wire the Benchmark page's Figure-2 to it (replace the hardcoded `series`).
3. Commit `web/data.json` (+ any `index.html` render change) → push `origin/main` → Vercel
   auto-deploys. Verify: `curl <prod>/data.json` matches, hard-refresh the site.

## 5. Open question for the team
The headline number is the **RL track** (Qwen3-8B → cologic-rtl, +0.033), not the inference loop.
If you want a bigger/clearer gap: (a) more GRPO steps, (b) report mean-reward uplift alongside
pass@1, or (c) add the hard `stream_arb_fifo` task to the RL taskset (it has real headroom and a
functional-only grader — `cologic/tasks.py:HARD_TASKS`, landed in #4).
