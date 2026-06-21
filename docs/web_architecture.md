# Cologic web — data flow (how the live site works)

The site is three static pages plus a live data store. Nothing on the page is
hardcoded except copy and styling; every number comes from one JSON record.

## The pieces

```
 eval (Python)                         data store                 site (Vercel static)
 ─────────────                         ──────────                 ────────────────────
 cologic.run_eval_hud   ──┐
   (HUD gateway sample,    │  publish   ┌───────────────┐  GET    web/index.html  (Foundry)
    Verilator grade)       ├──────────► │ Modal Dict    │ ◄────── web/benchmark.html
 cologic.export_web ──────┘            │ "cologic-state"│         web/die.html
   (--publish)                         └───────┬───────┘         each: fetch(ENDPOINT)
                                               │  GET /state              │ on fail ↓
                                       serve.py (Modal asgi)       web/data.json (fallback)
                                       https://yc-hack27--cologic-web-web.modal.run/state
```

## The record (one JSON, served at `/state`, also committed as `web/data.json`)

```jsonc
{
  "updated_at": "",
  "source": "baseline+cologic eval",
  "benchmark": {                 // REAL — Verilator-graded eval
    "baseline_model": "Qwen/Qwen3-8B", "baseline_pass_at_1": 0.267,
    "cologic_model": "cologic-rtl",    "cologic_pass_at_1": 0.300,
    "uplift": 0.033, "gate": 0.60, "n_per_task": 5,
    "per_task": [ { "id", "short", "baseline", "cologic", "bp", "cp" }, ... ]
  },
  "foundry": {                   // demo design panel (synthesis figures illustrative)
    "design": "tensor-mac / systolic_8×8", "objective": "power", "pdk": "sky130hd",
    "epoch": 1284, "power_rel": 142, "compute_pct": 71, "clock_mhz": 910,
    "sim_status": "PASS", "demo": true,
    "agents": [ { "role": "PLAN", "level": 2, "target": "PE[1][3]", "verb": "probing" }, ... ],
    "rtl": "// systolic_array.v ..."
  }
}
```

## What's real vs illustrative (honest)
- **Real:** `benchmark.*` — `cologic.run_eval_hud` samples Verilog from a model via the
  HUD gateway, grades it with local Verilator against golden testbenches, and
  `cologic.eval` aggregates pass@1. Current: baseline `Qwen/Qwen3-8B` 0.267 vs
  `cologic-rtl` 0.300 (n=5/task, heldout). The Foundry shows this as the pass@1 tile;
  the benchmark page shows the full per-task breakdown.
- **Illustrative (DEMO):** `foundry.power_rel / compute_pct / clock_mhz` — synthesis
  figures from the design demo. Marked `demo:true`, badged `DEMO`, and called out in
  the page footer. Wire them to real numbers by running yosys/OpenSTA in the eval and
  overwriting these fields in `cologic.store.publish`.

## How to update the live numbers
```bash
source .env.local                                   # HUD_API_KEY
python -m cologic.run_eval_hud --model Qwen/Qwen3-8B --n 5 --out baseline.json
python -m cologic.run_eval_hud --model cologic-rtl  --n 5 --out cologic.json
python -m cologic.export_web --publish              # writes web/data.json AND pushes to the live store
```
The endpoint reflects it immediately; the site polls `/state` every 8 s. Commit
`web/data.json` so the static fallback stays current too, then redeploy the site.

## Why a fallback
The pages fetch the Modal endpoint first; if it's slow/down they load the committed
`web/data.json` (same shape). So the site is "live" when the store is up and never
blank when it isn't.

## Infra
- `serve.py` — Modal app `cologic-web`, `modal deploy serve.py`. Read-only GET, CORS `*`.
- `cologic/store.py` — record schema + `publish()` (writes the Modal Dict) + `--seed`.
- The store is a `modal.Dict` (lightweight KV), not a database — one record under key `latest`.
