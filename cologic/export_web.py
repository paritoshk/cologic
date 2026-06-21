"""Export real eval results to web/data.json — the frontend's data contract.

The web UI fetches ./data.json and renders from it. Today the file is produced
here from real eval runs; later the same shape can be served live from a Modal
HTTP endpoint and the frontend just changes its fetch URL.

Inputs (use whichever exist):
  --uplift   cologic-verilog/results/uplift.json   (single-shot vs Plan/Forge/Prove loop)
  --baseline baseline.json                          (a single model's n-sample eval)

Run:
  python -m cologic.export_web --uplift cologic-verilog/results/uplift.json
  python -m cologic.export_web --demo        # write a snapshot seed (no real run)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

GATE = 0.60  # deployment gate (pass@1) shown on the chart

# Last-known snapshot (pre-real-run seed). Marked source="snapshot" so the UI can
# flag it as illustrative until a real run overwrites it.
SNAPSHOT = {
    "source": "snapshot",
    "model": "loop (Plan/Forge/Prove)",
    "gate": GATE,
    "baseline_pass_at_1": 0.567,
    "cologic_pass_at_1": 0.667,
    "uplift": 0.100,
    "n_per_task": 5,
    "per_task": [
        {"id": "ho_mux2_w16", "short": "mux2_w16", "baseline": 1.00, "cologic": 1.00, "bp": "5/5", "cp": "5/5"},
        {"id": "ho_cmp4", "short": "cmp4", "baseline": 1.00, "cologic": 1.00, "bp": "5/5", "cp": "5/5"},
        {"id": "ho_popcount16", "short": "popcount16", "baseline": 0.20, "cologic": 0.40, "bp": "1/5", "cp": "2/5"},
        {"id": "ho_max2", "short": "max2", "baseline": 1.00, "cologic": 1.00, "bp": "5/5", "cp": "5/5"},
        {"id": "ho_dec2to4", "short": "dec2to4", "baseline": 0.20, "cologic": 0.40, "bp": "1/5", "cp": "2/5"},
        {"id": "ho_gray2bin8", "short": "gray2bin8", "baseline": 0.00, "cologic": 0.20, "bp": "0/5", "cp": "1/5"},
    ],
    "epochs": None,  # only set when a real RFT learning curve exists
}


def _short(task_id: str) -> str:
    return task_id[3:] if task_id.startswith("ho_") else task_id


def from_uplift(uplift: dict) -> dict:
    """Map uplift_run.py output (single-shot vs loop) to the web contract."""
    rows = []
    for r in uplift["per_task"]:
        b = 1.0 if r["single_shot_pass"] else 0.0
        c = 1.0 if r["cologic_pass"] else 0.0
        rows.append({
            "id": r["task_id"], "short": _short(r["task_id"]),
            "baseline": b, "cologic": c,
            "bp": f"{int(b)}/1", "cp": f"{int(c)}/1",
        })
    return {
        "source": "uplift.json",
        "model": uplift.get("model", "loop"),
        "gate": GATE,
        "baseline_pass_at_1": uplift["baseline_pass_at_1"],
        "cologic_pass_at_1": uplift["cologic_pass_at_1"],
        "uplift": uplift["uplift"],
        "n_per_task": 1,
        "per_task": rows,
        "epochs": None,
    }


def from_baseline(baseline: dict) -> dict:
    """Map a single EvalReport (one model, n samples) — baseline only, cologic==baseline."""
    n = baseline["n_per_task"]
    rows = []
    for t in baseline["per_task"]:
        rows.append({
            "id": t["task_id"], "short": _short(t["task_id"]),
            "baseline": round(t["pass_rate"], 2), "cologic": round(t["pass_rate"], 2),
            "bp": f"{t['n_pass']}/{n}", "cp": f"{t['n_pass']}/{n}",
        })
    p1 = baseline["pass_at_1"]
    return {
        "source": "baseline.json",
        "model": baseline["model"],
        "gate": GATE,
        "baseline_pass_at_1": p1,
        "cologic_pass_at_1": p1,
        "uplift": 0.0,
        "n_per_task": n,
        "per_task": rows,
        "epochs": None,
    }


def from_two_baselines(baseline: dict, cologic: dict) -> dict:
    """Two EvalReports (baseline model vs Cologic model, n samples each) -> contract.

    This is the real apples-to-apples benchmark: same heldout tasks, same n, two
    models. Maps to the UI's baseline/cologic columns and per-task n_pass/n counts.
    """
    n = baseline["n_per_task"]
    cg = {t["task_id"]: t for t in cologic["per_task"]}
    rows = []
    for t in baseline["per_task"]:
        c = cg.get(t["task_id"], t)
        rows.append({
            "id": t["task_id"], "short": _short(t["task_id"]),
            "baseline": round(t["pass_rate"], 2), "cologic": round(c["pass_rate"], 2),
            "bp": f"{t['n_pass']}/{n}", "cp": f"{c['n_pass']}/{cologic['n_per_task']}",
        })
    return {
        "source": "baseline+cologic eval",
        "baseline_model": baseline["model"],
        "cologic_model": cologic["model"],
        "model": cologic["model"],
        "gate": GATE,
        "baseline_pass_at_1": round(baseline["pass_at_1"], 3),
        "cologic_pass_at_1": round(cologic["pass_at_1"], 3),
        "uplift": round(cologic["pass_at_1"] - baseline["pass_at_1"], 3),
        "n_per_task": n,
        "per_task": rows,
        "epochs": None,
    }


def build(uplift_path: str | None, baseline_path: str | None, cologic_path: str | None = None) -> dict:
    if baseline_path and cologic_path and Path(baseline_path).exists() and Path(cologic_path).exists():
        return from_two_baselines(
            json.loads(Path(baseline_path).read_text()),
            json.loads(Path(cologic_path).read_text()),
        )
    if uplift_path and Path(uplift_path).exists():
        data = from_uplift(json.loads(Path(uplift_path).read_text()))
    elif baseline_path and Path(baseline_path).exists():
        data = from_baseline(json.loads(Path(baseline_path).read_text()))
    else:
        raise SystemExit("no input found; pass --uplift / --baseline, or --demo for the snapshot seed")
    # Enrich baseline counts from a real baseline.json when both are present.
    if uplift_path and baseline_path and Path(baseline_path).exists():
        bl = {t["task_id"]: t for t in json.loads(Path(baseline_path).read_text())["per_task"]}
        n = json.loads(Path(baseline_path).read_text())["n_per_task"]
        for row in data["per_task"]:
            if row["id"] in bl:
                row["baseline"] = round(bl[row["id"]]["pass_rate"], 2)
                row["bp"] = f"{bl[row['id']]['n_pass']}/{n}"
    return data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uplift", default="cologic-verilog/results/uplift.json")
    ap.add_argument("--baseline", default="baseline.json")
    ap.add_argument("--cologic", default="cologic.json", help="second EvalReport (Cologic model)")
    ap.add_argument("--out", default="web/data.json")
    ap.add_argument("--demo", action="store_true", help="write the snapshot seed, no real run")
    args = ap.parse_args()

    data = SNAPSHOT if args.demo else build(args.uplift, args.baseline, args.cologic)
    Path(args.out).write_text(json.dumps(data, indent=2) + "\n")
    tag = data["source"]
    print(f"wrote {args.out}  (source={tag}, baseline={data['baseline_pass_at_1']}, "
          f"cologic={data['cologic_pass_at_1']}, uplift={data['uplift']})")


def _selfcheck() -> None:
    up = {
        "model": "claude-haiku-4-5", "baseline_pass_at_1": 0.5, "cologic_pass_at_1": 0.75, "uplift": 0.25,
        "per_task": [
            {"task_id": "ho_cmp4", "single_shot_pass": True, "cologic_pass": True},
            {"task_id": "ho_dec2to4", "single_shot_pass": False, "cologic_pass": True},
        ],
    }
    d = from_uplift(up)
    assert d["per_task"][0] == {"id": "ho_cmp4", "short": "cmp4", "baseline": 1.0, "cologic": 1.0, "bp": "1/1", "cp": "1/1"}
    assert d["per_task"][1]["baseline"] == 0.0 and d["per_task"][1]["cologic"] == 1.0
    assert d["uplift"] == 0.25 and d["source"] == "uplift.json"
    assert _short("ho_mux2_w16") == "mux2_w16" and _short("plain") == "plain"
    print("export_web selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
