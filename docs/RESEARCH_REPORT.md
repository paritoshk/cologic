# Cologic — making the demo real (research-engineer report)

_2026-06-21. Goal: replace the demo's illustrative numbers with measured ones, honestly._

## TL;DR

- The original `0.567 → 0.667` "RLVR uplift" curve **does not reproduce** — the `ho_*` heldout tasks
  are **saturated** (current frontier models solve them single-shot, pass@1 = 1.000).
- We added a **hard task with real headroom** (`stream_arb_fifo`, a 2-lane round-robin ready/valid
  FIFO arbiter) graded by a **functional-only** Verilator equivalence oracle.
- The **inference-time** Plan→Forge→Prove loop is **not a reliable uplift** (measured noise, +0.016).
- The **real "model improves" result is weight training (RL/GRPO)**: the trained `cologic-rtl` fork
  beats the `Qwen/Qwen3-8B` baseline **0.267 → 0.300 pass@1 (+0.033)** on `ho_*` — measured, live in
  `web/data.json`.
- The demo is deployed: Foundry homepage + real benchmark + die diagram + the **live RTL optimizer**.

## What's real vs illustrative (the honesty ledger)

| thing | status | source |
|---|---|---|
| Benchmark pass@1 (Qwen3-8B 0.267 → cologic-rtl 0.300, +0.033) | **REAL** | RL eval → `web/data.json` |
| Per-task `ho_*` bars (mux2/cmp4/popcount16/…) | **REAL** | same eval |
| RTL optimizer gate-count / area reductions (e.g. tt_um_tpu 1460→450, −69%) | **REAL, per-run** | Soren's live Modal backend (Verilator equiv + Yosys PPA) |
| Hard `stream_arb_fifo` grader (golden 1.000 / broken 0.586 / stub 0.416) | **REAL** | `cologic/verifier.py` (local Verilator) |
| Foundry homepage animation (`116 rel` power, `94 %` compute) | **ILLUSTRATIVE** | hardcoded in the no-source compiled bundle; labeled as such by the overlay banner |
| "Power" in mW | **NOT AVAILABLE** | grader emits yosys gate-count/logic-depth proxies, not mW (needs sky130+OpenSTA) |

## Key findings

1. **`ho_*` is saturated / likely contaminated.** Gemma-4 and Haiku solve all six single-shot. A
   saturated taskset cannot demonstrate any method's value; charting it would be the opposite of real.
   Fix: measure on tasks where the baseline actually fails.

2. **Inference-time looping is noise on this setup.** Apples-to-apples, claude-haiku-4-5 on the hard
   `stream_arb_fifo`, K=5 trials (`cologic/uplift_multitrial.py`): single mean **0.780**, loop mean
   **0.796**, both pass@1 = 0.00, uplift **+0.016**. The loop frequently regresses to a broken build
   (the model over-edits) and never reaches a full pass. One lucky 0.78→1.0 run does not reproduce.
   A measurement bug was found and fixed along the way: reasoning models (e.g. `gemma-4-26b-a4b-it`)
   spend their whole budget in `<thought>` and truncate to a *fake* `no_module` failure at 2048
   tokens — `uplift_run.py` now has a configurable `--max-tokens` (default 8192). `gemma-4-26b-a4b-it`
   and `gemma-4-31b-it` are runaway reasoners that never emit code within the gateway's ~300s ceiling;
   `claude-haiku-4-5` terminates cleanly and is the usable policy.

3. **Weight training is the real story.** The RL-trained `cologic-rtl` fork measurably beats its
   `Qwen3-8B` base (+0.033 pass@1) — small but honest, on a base model weak enough that `ho_*` isn't
   saturated. This is the number on the live benchmark. (GRPO harness: `agents/train.py`, HUD
   `TrainingClient`; it self-guards against zero within-group reward spread.)

## Deployment

New Vercel project **`cologic-optimizer`** (separate from the benchmark project; `origin` stays
`paritoshk/cologic`, nothing on Soren's repo):

- `/` — Foundry homepage (compiled bundle) + a self-healing overlay: nav to all pages + a banner
  showing the **real** `data.json` numbers, with the animation labeled illustrative.
- `/benchmark.html` — real charts from `data.json`.
- `/die.html` — the die diagram.
- `/optimizer/` — Soren's **live** RTL optimizer SPA (`POST /optimize` + poll `/jobs/{id}` on
  `yc-hack27--rl-hdl-web.modal.run`, CORS open). Needs the `X-RLHDL-Token` pasted at runtime.

## What's left / next

- **`X-RLHDL-Token` from Soren** — to smoke-test the optimizer end-to-end and put a *real* measured
  optimizer run (gate-count/area) on the homepage instead of the illustrative animation.
- **GRPO continues on the `charlotte` track** (it owns `cologic-rtl`). As it trains further, regenerate
  `web/data.json` and the live numbers move automatically.
- **Real power/timing in mW** — add sky130 + OpenSTA to the grader image; swap the gate-count proxy
  for real switching energy + slack. Until then, "rel." stays labeled as a proxy, never mW.

## Reproduce

```
export $(grep -v '^#' .env.local | xargs)          # HUD_API_KEY, FIREWORKS_API_KEY
python -m cologic.uplift_multitrial --model claude-haiku-4-5 --trials 5   # the +0.016 noise finding
python -c "import cologic.tasks as T; from cologic.verifier import grade; t=T.BY_ID['stream_arb_fifo']; print(grade(t.reference_rtl,t).reward)"  # -> 1.0
pytest -q                                          # 32 passed
```
